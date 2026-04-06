"""
Job: persist_firestore

  new.game     -->  [TagWithCollection("games")]    --|
  new.analysis -->  [TagWithCollection("analyses")] --|-->  union  -->  [FirestoreWriter]  -->  Firestore
  new.puzzle   -->  [TagWithCollection("puzzles")]  --|
  new.player   -->  [TagWithCollection("players")]  --|

Single job that handles all Firestore persistence. Each upstream topic carries
records with a generated `id` field; this job wraps them in a Firestore
envelope and writes to the appropriate collection.

Submit:
    flink run -py /opt/flink/jobs/persist_firestore.py
"""

import json
import socket
import os
from loguru import logger
from google.cloud import firestore

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.common.restart_strategy import RestartStrategies
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaOffsetsInitializer
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream.functions import MapFunction, RuntimeContext

from topics import NEW_GAME, NEW_ANALYSIS, NEW_PUZZLE, NEW_PLAYER

KAFKA_BOOTSTRAP         = "kafka:9092"
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "firebase-emulator:8080")
FIRESTORE_PROJECT       = os.getenv("GOOGLE_CLOUD_PROJECT", "demo-local")

TOPIC_COLLECTION = {
    NEW_GAME:     "games",
    NEW_ANALYSIS: "analyses",
    NEW_PUZZLE:   "puzzles",
    NEW_PLAYER:   "players",
}


def _build_source(topic: str, group_suffix: str) -> KafkaSource:
    return (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BOOTSTRAP)
        .set_topics(topic)
        .set_group_id(f"persist-firestore-{group_suffix}")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )


class TagWithCollection(MapFunction):
    def __init__(self, collection: str):
        self.collection = collection

    def map(self, value):
        record = json.loads(value)
        doc_id = record.get("id")
        if not doc_id:
            logger.warning(f"Missing 'id' in {self.collection} record, dropping: {value[:120]}")
            return value
        return json.dumps({
            "collection": self.collection,
            "doc_id":     doc_id,
            "data":       record,
        })


class FirestoreWriter(MapFunction):
    def open(self, runtime_context: RuntimeContext):
        hostname = socket.gethostname()
        logger.add(f"/var/log/flink/{hostname}.persist_firestore.log", rotation="10 MB", retention="7 days")
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

    streams = []
    for topic, suffix in [
        (NEW_GAME,     "games"),
        (NEW_ANALYSIS, "analysis"),
        (NEW_PUZZLE,   "puzzles"),
        (NEW_PLAYER,   "players"),
    ]:
        stream = (
            env
            .from_source(_build_source(topic, suffix), WatermarkStrategy.no_watermarks(), topic)
            .map(TagWithCollection(TOPIC_COLLECTION[topic]), output_type=Types.STRING())
        )
        streams.append(stream)

    first, *rest = streams
    (
        first
        .union(*rest)
        .map(FirestoreWriter(), output_type=Types.STRING())
        .print()
    )

    env.execute("persist_firestore")


if __name__ == "__main__":
    main()
