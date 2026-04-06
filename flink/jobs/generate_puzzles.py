"""
Job: generate_puzzles

  new.analysis  -->  [ExtractPuzzles]  -->  new.puzzle

Reads analysis records from `new.analysis`, finds moves with significant
centipawn swings, and publishes raw puzzle records to `new.puzzle`.
Each puzzle gets its own nanoid `id`.

Input (new.analysis):
    {
        "id":      "<nanoid>",
        "game_id": "344089823",
        "moves":   [ ... ]
    }

Output (new.puzzle):
    {
        "id":           "<nanoid>",
        "game_id":      "<nanoid of parent game>",
        "puzzle_rank":  1,
        "move_number":  12,
        ...
    }

Submit:
    flink run -py /opt/flink/jobs/generate_puzzles.py
"""

import json
import socket
from loguru import logger
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
from pyflink.datastream.functions import FlatMapFunction, RuntimeContext

from topics import NEW_ANALYSIS, NEW_PUZZLE

KAFKA_BOOTSTRAP = "kafka:9092"
SOURCE_TOPIC    = NEW_ANALYSIS
SINK_TOPIC      = NEW_PUZZLE
TOP_N_PUZZLES   = 3


class ExtractPuzzles(FlatMapFunction):
    """
    For each analysis record from add.analysis, selects top puzzles and
    publishes to firestore.write.
    """

    def open(self, runtime_context: RuntimeContext):
        hostname = socket.gethostname()
        logger.add(f"/var/log/flink/{hostname}.generate_puzzles.log", rotation="10 MB", retention="7 days")

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: v.encode("utf-8"),
        )

    def close(self):
        self.producer.flush()
        self.producer.close()

    def flat_map(self, value):
        analysis = json.loads(value)
        game_id  = analysis.get("game_id")
        doc_id   = analysis.get("id")
        moves    = analysis.get("moves", [])

        if not game_id or not doc_id or not moves:
            return

        candidates = [m for m in moves if m.get("delta_cp") is not None]
        if not candidates:
            return

        candidates.sort(key=lambda m: abs(m["delta_cp"]), reverse=True)
        top_puzzles = candidates[:TOP_N_PUZZLES]

        for rank, move in enumerate(top_puzzles, start=1):
            solution = move["top_moves"][0] if move.get("top_moves") else {}
            puzzle = {
                "id":           nanoid(),
                "game_id":      doc_id,
                "puzzle_rank":  rank,
                "move_number":  move["move_number"],
                "color":        move["color"],
                "fen":          move["fen_before"],
                "played_move":  move["san"],
                "solution_uci": solution.get("uci"),
                "solution_san": solution.get("san"),
                "delta_cp":     move["delta_cp"],
                "abs_delta_cp": abs(move["delta_cp"]),
                "top_moves":    move.get("top_moves", []),
            }
            self.producer.send(SINK_TOPIC, json.dumps(puzzle))

        self.producer.flush()
        logger.info(f"Emitted {len(top_puzzles)} puzzles for game {game_id}")
        yield value


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)
    env.set_restart_strategy(RestartStrategies.fixed_delay_restart(5, 15000))
    env.enable_checkpointing(60_000)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BOOTSTRAP)
        .set_topics(SOURCE_TOPIC)
        .set_group_id("generate-puzzles")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    (
        env
        .from_source(source, WatermarkStrategy.no_watermarks(), SOURCE_TOPIC)
        .flat_map(ExtractPuzzles(), output_type=Types.STRING())
        .print()
    )

    env.execute("generate_puzzles")


if __name__ == "__main__":
    main()
