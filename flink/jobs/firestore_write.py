"""
Job: firestore_write

  firestore.write  -->  [FirestoreWriter]  -->  Firestore /{collection}/{doc_id}

Single job that handles all Firestore persistence. Consumes from the
`firestore.write` topic and writes to the local Firestore emulator or
production.

Input (firestore.write):
    {
        "collection": "games",
        "doc_id":     "344089823",
        "data":       { ... }
    }

Submit:
    flink run -py /opt/flink/jobs/firestore_write.py
"""

import json
import socket
import os
from loguru import logger
from google.cloud import firestore

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

from topics import FIRESTORE_WRITE

KAFKA_BOOTSTRAP         = "kafka:9092"
SOURCE_TOPIC            = FIRESTORE_WRITE
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "firebase-emulator:8080")
FIRESTORE_PROJECT       = os.getenv("GOOGLE_CLOUD_PROJECT", "demo-local")


class FirestoreWriter(MapFunction):
    """
    Writes each envelope to the appropriate Firestore collection.
    """

    def open(self, runtime_context: RuntimeContext):
        hostname = socket.gethostname()
        logger.add(f"/var/log/flink/{hostname}.firestore_write.log", rotation="10 MB", retention="7 days")

        os.environ.setdefault("FIRESTORE_EMULATOR_HOST", FIRESTORE_EMULATOR_HOST)
        self.db = firestore.Client(project=FIRESTORE_PROJECT)

    def close(self):
        self.db.close()

    def map(self, value):
        envelope   = json.loads(value)
        collection = envelope.get("collection")
        doc_id     = envelope.get("doc_id")
        data       = envelope.get("data")

        if not collection or not doc_id or not data:
            logger.warning(f"Dropping malformed envelope: {value[:120]}")
            return value

        doc = {k: v for k, v in data.items() if v is not None}
        self.db.collection(collection).document(doc_id).set(doc, merge=True)
        logger.info(f"Written {collection}/{doc_id}")
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
        .set_group_id("firestore-write")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    (
        env
        .from_source(source, WatermarkStrategy.no_watermarks(), SOURCE_TOPIC)
        .map(FirestoreWriter(), output_type=Types.STRING())
        .print()
    )

    env.execute("firestore_write")


if __name__ == "__main__":
    main()
