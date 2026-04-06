"""
Job: chess_com_fetch_profile

  chesscom.new.player  -->  [FetchPlayerProfile]  -->  new.player

Reads a username trigger from `chesscom.new.player`, fetches the Chess.com
player profile, generates a nanoid `id`, and emits the enriched record to
`new.player` for `persist_firestore` to write to the players collection.

Input  (chesscom.new.player):
    {"username": "pdavis"}

Output (new.player):
    { "id": "<nanoid>", "username": "pdavis", "name": "Peter Davis", "player_id": 4477708 }

Submit:
    flink run -py /opt/flink/jobs/chess_com_fetch_profile.py
"""

import json
import socket
import requests
from loguru import logger
from kafka import KafkaProducer
from nanoid import generate as nanoid

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaOffsetsInitializer,
)
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream.functions import MapFunction, RuntimeContext

from topics import CHESSCOM_NEW_PLAYER, NEW_PLAYER

KAFKA_BOOTSTRAP = "kafka:9092"
SOURCE_TOPIC    = CHESSCOM_NEW_PLAYER
SINK_TOPIC      = NEW_PLAYER
CHESS_UA        = "chess-trainer/0.0 (username: pdavis; contact: petersdavis@gmail.com)"


class FetchPlayerProfile(MapFunction):
    """
    For each username message, call the Chess.com player profile endpoint and
    publish a filtered Firestore write envelope to the firestore.write topic.
    """

    def open(self, runtime_context: RuntimeContext):
        hostname = socket.gethostname()
        logger.add(f"/var/log/flink/{hostname}.chess_com_fetch_profile.log", rotation="10 MB", retention="7 days")

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: v.encode("utf-8"),
        )

    def close(self):
        self.producer.flush()
        self.producer.close()

    def map(self, value):
        if not value or not value.strip():
            return value

        try:
            data     = json.loads(value)
            username = data.get("username")
            if not username:
                return value

            url  = f"https://api.chess.com/pub/player/{username}"
            resp = requests.get(url, headers={"User-Agent": CHESS_UA}, timeout=10)
            
            if resp.status_code == 404:
                logger.warning(f"Player {username} not found on Chess.com")
                return value
                
            resp.raise_for_status()
            profile = resp.json()

            player = {
                "id":        nanoid(),
                "name":      profile.get("name"),
                "username":  profile.get("username"),
                "player_id": profile.get("player_id"),
            }

            self.producer.send(SINK_TOPIC, json.dumps(player))
            self.producer.flush()

            logger.info(f"Published profile for {username} to {SINK_TOPIC}")

        except Exception as e:
            logger.error(f"Error fetching profile for {value}: {e}")

        return value


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BOOTSTRAP)
        .set_topics(SOURCE_TOPIC)
        .set_group_id("chesscom-fetch-profile")
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    (
        env
        .from_source(source, WatermarkStrategy.no_watermarks(), SOURCE_TOPIC)
        .map(FetchPlayerProfile(), output_type=Types.STRING())
        .print()
    )

    env.execute("chess_com_fetch_profile")


if __name__ == "__main__":
    main()
