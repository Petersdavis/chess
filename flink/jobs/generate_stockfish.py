"""
Job: generate_stockfish

  new.game  -->  [AnalyzeWithStockfish]  -->  new.analysis

Reads game records from `new.game`, sends the PGN to the Stockfish analysis
service, and publishes the structured result to `new.analysis`.

The analysis record reuses the game's `id` (nanoid) so callers can look up
analysis by the same key. The chess.com `game_id` is preserved as a field.

Input (new.game):
    {
        "id":      "<nanoid>",
        "game_id": "344089823",
        "pgn":     "<base64>",
        ...
    }

Output (new.analysis):
    {
        "id":      "<same nanoid as game>",
        "game_id": "344089823",
        "depth":   15,
        ...
    }

Submit:
    flink run -py /opt/flink/jobs/generate_stockfish.py
"""

import json
import socket
import requests
from loguru import logger
from kafka import KafkaProducer

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

from topics import NEW_GAME, NEW_ANALYSIS

KAFKA_BOOTSTRAP   = "kafka:9092"
SOURCE_TOPIC      = NEW_GAME
SINK_TOPIC        = NEW_ANALYSIS
STOCKFISH_URL     = "http://stockfish:5000/analyze/pgn"
ANALYSIS_DEPTH    = 8
ANALYSIS_ALTS     = 5


class AnalyzeWithStockfish(MapFunction):
    """
    Calls the Stockfish analysis service for each game and publishes the result
    to add.analysis via kafka-python.
    """

    def open(self, runtime_context: RuntimeContext):
        hostname = socket.gethostname()
        logger.add(f"/var/log/flink/{hostname}.generate_stockfish.log", rotation="10 MB", retention="7 days")

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: v.encode("utf-8"),
        )

    def close(self):
        self.producer.flush()
        self.producer.close()

    def map(self, value):
        game    = json.loads(value)
        pgn     = game.get("pgn")
        game_id = game.get("game_id")
        doc_id  = game.get("id")

        if not pgn or not game_id or not doc_id:
            return value

        try:
            resp = requests.post(
                STOCKFISH_URL,
                json={"pgn": pgn, "depth": ANALYSIS_DEPTH, "alternatives": ANALYSIS_ALTS},
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Stockfish request failed for game {game_id}: {e}")
            return value

        analysis = resp.json()
        if "error" in analysis:
            logger.error(f"Stockfish error for game {game_id}: {analysis['error']}")
            return value

        analysis["id"]      = doc_id
        analysis["game_id"] = game_id

        self.producer.send(SINK_TOPIC, json.dumps(analysis))
        self.producer.flush()
        return value


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(5)
    env.set_restart_strategy(RestartStrategies.fixed_delay_restart(5, 15000))
    env.enable_checkpointing(30_000)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BOOTSTRAP)
        .set_topics(SOURCE_TOPIC)
        .set_group_id("generate-stockfish")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    (
        env
        .from_source(source, WatermarkStrategy.no_watermarks(), SOURCE_TOPIC)
        .map(AnalyzeWithStockfish(), output_type=Types.STRING())
        .print()
    )

    env.execute("generate_stockfish")


if __name__ == "__main__":
    main()
