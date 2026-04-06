"""
Job: chess_com_fetch_games

  chesscom.new.archive  -->  [FetchAndParseGames]  -->  new.game

Reads archive URLs from `chesscom.new.archive`, fetches every game in each archive,
deduplicates against Redis, parses new games into a structured record with a
generated nanoid `id`, and publishes to `new.game`.

Downstream jobs (`persist_firestore`, `generate_stockfish`) each consume
from `new.game` independently via their own consumer groups.

Input  (chesscom.new.archive):
    {"username": "pdavis", "archive_url": "https://api.chess.com/pub/player/pdavis/games/2024/01"}

Output (new.game):
    {
        "id":       "<nanoid>",
        "game_id":  "344089823",
        "username": "pdavis",
        "white":    "pdavis",
        "black":    "55nate",
        "outcome":  "white",
        "pgn":      "<base64>",
        "url":      "https://www.chess.com/game/live/344089823",
        "book_move_depth": 10,
        "last_book_move": "black"
    }

Submit:
    flink run -py /opt/flink/jobs/chess_com_fetch_games.py
"""

import base64
import json
import socket
import requests
from loguru import logger
import redis as redis_client
import time
import io
import os
import chess.pgn
from kafka import KafkaProducer
from nanoid import generate as nanoid

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.common.restart_strategy import RestartStrategies
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaOffsetsInitializer,
)
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream.functions import MapFunction, RuntimeContext

from topics import CHESSCOM_NEW_ARCHIVE, NEW_GAME

KAFKA_BOOTSTRAP  = "kafka:9092"
SOURCE_TOPIC     = CHESSCOM_NEW_ARCHIVE
SINK_TOPIC       = NEW_GAME
REDIS_HOST       = "redis"
REDIS_PORT       = 6379
CHESS_UA         = "chess-trainer/0.0 (username: pdavis; contact: petersdavis@gmail.com)"
BOOK_PATH        = os.getenv("CHESS_BOOK_PATH", "openings/bookmoves.json")


def get_book_metrics(pgn_str: str, book_dict: dict) -> tuple[int, str | None]:
    """
    Traverses the opening book using the game's move sequence.
    Returns (depth, last_move_color).
    """
    if not pgn_str or not book_dict:
        return 0, None

    try:
        pgn_io = io.StringIO(pgn_str)
        game = chess.pgn.read_game(pgn_io)
        if not game:
            return 0, None

        current_level = book_dict
        depth = 0
        last_color = None
        board = game.board()

        for move in game.mainline_moves():
            san_move = board.san(move)
            if san_move in current_level:
                current_level = current_level[san_move]
                depth += 1
                last_color = "white" if depth % 2 != 0 else "black"
                board.push(move)
            else:
                break

        return depth, last_color
    except Exception as e:
        logger.error(f"Error analyzing book depth: {e}")
        return 0, None


def _extract_username(player) -> str:
    if isinstance(player, str):
        return player.split("/")[-1]
    if isinstance(player, dict):
        return player.get("username", "")
    return ""


def _parse_game(game: dict, username: str) -> dict | None:
    """Parse a raw Chess.com game object into a structured record."""
    game_id = game.get("url", "").split("/")[-1]
    if not game_id:
        return None

    white_data = game.get("white", {})
    black_data = game.get("black", {})

    if isinstance(white_data, dict) and "result" in white_data:
        if white_data["result"] == "win":
            outcome = "white"
        elif black_data.get("result") == "win":
            outcome = "black"
        else:
            outcome = "draw"
    else:
        outcome = None

    raw_pgn = game.get("pgn") or ""
    encoded_pgn = base64.b64encode(raw_pgn.encode()).decode() if raw_pgn else None

    return {
        "game_id":  game_id,
        "username": username,
        "white":    _extract_username(white_data),
        "black":    _extract_username(black_data),
        "outcome":  outcome,
        "pgn":      encoded_pgn,
        "tcn":      game.get("tcn"),
        "url":      game.get("url"),
    }


class FetchAndPublishGames(MapFunction):
    """
    For each archive URL:
      1. Fetch all games from Chess.com.
      2. Skip any game already recorded in Redis.
      3. Parse new games and publish to both Kafka topics.
    """

    def open(self, runtime_context: RuntimeContext):
        hostname = socket.gethostname()
        logger.add(f"/var/log/flink/{hostname}.chess_com_fetch_games.log", rotation="10 MB", retention="7 days")

        self.redis = redis_client.Redis(
            host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
        )
        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: v.encode("utf-8"),
        )

        # Load Opening Book
        if os.path.exists(BOOK_PATH):
            logger.info(f"Loading opening book from {BOOK_PATH}...")
            start_time = time.time()
            with open(BOOK_PATH, "r") as f:
                self.book = json.load(f)
            logger.info(f"Book loaded in {time.time() - start_time:.2f}s")
        else:
            logger.warning(f"Opening book not found at {BOOK_PATH}. Book analysis will be disabled.")
            self.book = {}

    def close(self):
        self.producer.flush()
        self.producer.close()
        self.redis.close()

    def map(self, value):
        data        = json.loads(value)
        username    = data["username"]
        archive_url = data["archive_url"]
        logger.info(f"Processing archive {archive_url} for {username}")
        try:
            resp = requests.get(archive_url, headers={"User-Agent": CHESS_UA}, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch archive {archive_url} for {username}: {e}")
            return value
        games = resp.json().get("games", [])

        for game in games:
            game_id = game.get("url", "").split("/")[-1]
            if not game_id:
                continue

            record = _parse_game(game, username)
            if not record:
                continue

            # Book Analysis
            raw_pgn = game.get("pgn", "")
            depth, last_color = get_book_metrics(raw_pgn, self.book)
            record["book_move_depth"] = depth
            record["last_book_move"]  = last_color

            record["id"] = nanoid()
            self.producer.send(SINK_TOPIC, json.dumps(record))

        self.producer.flush()
        return value


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)
    env.set_restart_strategy(RestartStrategies.fixed_delay_restart(5, 15000))
    env.enable_checkpointing(30_000)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BOOTSTRAP)
        .set_topics(SOURCE_TOPIC)
        .set_group_id("chesscom-fetch-games")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    (
        env
        .from_source(source, WatermarkStrategy.no_watermarks(), SOURCE_TOPIC)
        .map(FetchAndPublishGames(), output_type=Types.STRING())
        .print()
    )

    env.execute("chess_com_fetch_games")


if __name__ == "__main__":
    main()
