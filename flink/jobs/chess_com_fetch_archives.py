"""
Job: chess_com_fetch_archives

  chesscom.new.player  -->  [FetchArchiveUrls]  -->  chesscom.new.archive

Reads a username from the `chesscom.new.player` topic, hits the Chess.com archives
endpoint to get every monthly archive URL for that player, and emits one
message per URL to the `chesscom.new.archive` topic for downstream scraping.

Input  (chesscom.new.player):
    {"username": "pdavis"}

Output (chesscom.new.archive):
    {"username": "pdavis", "archive_url": "https://api.chess.com/pub/player/pdavis/games/2024/01"}

Submit:
    flink run -py /opt/flink/jobs/chess_com_fetch_archives.py
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

from topics import CHESSCOM_NEW_PLAYER, CHESSCOM_NEW_ARCHIVE

KAFKA_BOOTSTRAP = "kafka:9092"
SOURCE_TOPIC    = CHESSCOM_NEW_PLAYER
SINK_TOPIC      = CHESSCOM_NEW_ARCHIVE
CHESS_UA        = "chess-trainer/0.0 (username: pdavis; contact: petersdavis@gmail.com)"


class FetchArchiveUrls(MapFunction):
    """
    For each username message, call the Chess.com archives endpoint and
    publish one record per monthly archive URL directly to Kafka.
    """

    def open(self, runtime_context: RuntimeContext):
        hostname = socket.gethostname()
        logger.add(f"/var/log/flink/{hostname}.chess_com_fetch_archives.log", rotation="10 MB", retention="7 days")

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
        data     = json.loads(value)
        username = data.get("username")
        if not username:
            return value

        url  = f"https://api.chess.com/pub/player/{username}/games/archives"
        resp = requests.get(url, headers={"User-Agent": CHESS_UA}, timeout=10)
        resp.raise_for_status()

        count = 0
        for archive_url in resp.json().get("archives", []):
            msg = json.dumps({"username": username, "archive_url": archive_url})
            self.producer.send(SINK_TOPIC, msg)
            count += 1
            if count > 3: # Temporary limit for development
                break

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
        .set_group_id("chesscom-fetch-archives")
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    (
        env
        .from_source(source, WatermarkStrategy.no_watermarks(), SOURCE_TOPIC)
        .map(FetchArchiveUrls(), output_type=Types.STRING())
        .print()
    )

    env.execute("chess_com_fetch_archives")


if __name__ == "__main__":
    main()
