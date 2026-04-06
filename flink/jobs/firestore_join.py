"""
Job: firestore_join

  firestore.join  -->  [FirestoreJoinWriter]  -->  Firestore

Final job in the join pipeline that performs the actual Firestore 
join/update logic based on join requests received on the `firestore.join` topic.

Submit:
    flink run -py /opt/flink/jobs/firestore_join.py
"""

import json
import socket
import os
from loguru import logger
from google.cloud import firestore

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaOffsetsInitializer,
)
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream.functions import MapFunction, RuntimeContext

from topics import FIRESTORE_JOIN

KAFKA_BOOTSTRAP         = "kafka:9092"
SOURCE_TOPIC            = FIRESTORE_JOIN
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "firebase-emulator:8080")
FIRESTORE_PROJECT       = os.getenv("GOOGLE_CLOUD_PROJECT", "demo-local")


class FirestoreJoinWriter(MapFunction):
    def open(self, runtime_context: RuntimeContext):
        hostname = socket.gethostname()
        logger.add(f"/var/log/flink/{hostname}.firestore_join.log", rotation="10 MB", retention="7 days")
        os.environ.setdefault("FIRESTORE_EMULATOR_HOST", FIRESTORE_EMULATOR_HOST)
        self.db = firestore.Client(project=FIRESTORE_PROJECT)

    def close(self):
        self.db.close()

    def map(self, value):
        # Implementation of Firestore join logic would go here
        # For example, updating a document based on content from both game and player.
        logger.info(f"Processing join request: {value[:100]}")
        return value


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BOOTSTRAP)
        .set_topics(SOURCE_TOPIC)
        .set_group_id("firestore-join")
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    (
        env
        .from_source(source, WatermarkStrategy.no_watermarks(), SOURCE_TOPIC)
        .map(FirestoreJoinWriter(), output_type=Types.STRING())
        .print()
    )

    env.execute("firestore_join")


if __name__ == "__main__":
    main()
