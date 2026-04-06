"""
Job: firestore_join_game_player

  add.game  -->  [JoinGamePlayer]  -->  firestore.join

Consumed game records from `add.game` and prepares a join request
to associate game data with player metadata in Firestore.

Submit:
    flink run -py /opt/flink/jobs/firestore_join_game_player.py
"""

import json
import socket
from loguru import logger
from kafka import KafkaProducer

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaOffsetsInitializer,
)
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.common.watermark_strategy import WatermarkStrategy
from pyflink.datastream.functions import MapFunction, RuntimeContext

from topics import ADD_GAME, FIRESTORE_JOIN

KAFKA_BOOTSTRAP = "kafka:9092"
SOURCE_TOPIC    = ADD_GAME
SINK_TOPIC      = FIRESTORE_JOIN


class JoinGamePlayer(MapFunction):
    def open(self, runtime_context: RuntimeContext):
        hostname = socket.gethostname()
        logger.add(f"/var/log/flink/{hostname}.firestore_join_game_player.log", rotation="10 MB", retention="7 days")
        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: v.encode("utf-8"),
        )

    def close(self):
        self.producer.flush()
        self.producer.close()

    def map(self, value):
        # Implementation of join logic would go here
        # For now, just forward the record to the join topic
        self.producer.send(SINK_TOPIC, value)
        self.producer.flush()
        return value


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BOOTSTRAP)
        .set_topics(SOURCE_TOPIC)
        .set_group_id("firestore-join-game-player")
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    (
        env
        .from_source(source, WatermarkStrategy.no_watermarks(), SOURCE_TOPIC)
        .map(JoinGamePlayer(), output_type=Types.STRING())
        .print()
    )

    env.execute("firestore_join_game_player")


if __name__ == "__main__":
    main()
