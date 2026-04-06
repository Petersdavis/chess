# Chess Trainer — Architecture

## Overview

The pipeline is event-driven, built around Apache Flink for stream processing, Redis for fast ephemeral state, and Firestore as the persistent store.

---

## Workflow

### 1. User Input
A username is submitted (via API or UI), triggering the pipeline.
curl -X POST http://localhost:8000/api/ingest -H "Content-Type: application/json" -d '{"username": "pdavis"}'


### 2. Game Ingestion
- **2a.** Fetch PGN games from Chess.com API (rate-limited ingester).
- **2b.** Store raw game documents in Firestore `/games/{game_id}` (PGN base64-encoded).
- **2c.** Track `user → [game_id, ...]` mapping in Redis (`user:games:{username}`).
- **2d.** Compute and store opening stats per user in Redis (`user:openings:{username}`).

### 3. Stockfish Analysis
- **3a.** Each ingested game is pushed onto the `games.ingested` Flink topic.
- **3b.** A Flink job consumes the topic, calls the Stockfish analysis service, and writes the structured `GameAnalysis` result to Firestore `/analyses/{game_id}`.

### 4. Puzzle Generation
- `puzzle_job` consumes the `firestore.writes` topic, filtering for `collection == "analyses"`.
- Finds the 3 moves with the largest `|delta_cp|` (centipawn swing) in each game.
- Writes one puzzle per candidate back to `firestore.writes` (`collection: "puzzles"`), which `firestore_writer` persists to `/puzzles/{game_id}_p{rank}`.

### 5. Opening Recommendations
- Flink consumes `games.analyzed` topic.
- Aggregates opening performance from Redis stats.
- Writes recommendations to Firestore `/recommendations/{username}`.

### 6. Daily Cron Job
- A scheduled job runs once per day per active user.
- Fetches any new games since last ingestion.
- Re-enters the pipeline at step 2.

---

## Services

| Service             | Role                                      | Port(s)         |
|---------------------|-------------------------------------------|-----------------|
| `firebase-emulator` | Firestore + Auth + Functions (local dev)  | 4000, 8080, 9099, 5001 |
| `stockfish`         | PGN/FEN analysis REST API                 | 5000            |
| `flink-jobmanager`  | Flink cluster coordinator                 | 8081            |
| `flink-taskmanager` | Flink job execution worker                | —               |
| `redis`             | User→game index, opening stats cache      | 6379            |

---

## Flink Topics

| Topic                  | Producer(s)                            | Consumer(s)                        |
|------------------------|----------------------------------------|------------------------------------|
| `games.analysis`       | Ingester                               | `analysis_job`                     |
| `firestore.writes`     | `game_scraper`, `analysis_job`, `puzzle_job` | `firestore_writer`, `puzzle_job` |
| `users.new`            | API / UI                               | Ingester                           |
| `users.daily-refresh`  | Cron job                               | Ingester                           |

---

## Data Stores

### Firestore Collections
- `/games/{game_id}` — raw game data (PGN, players, outcome)
- `/analyses/{game_id}` — structured Stockfish analysis (`GameAnalysis`)
- `/puzzles/{puzzle_id}` — generated puzzles
- `/recommendations/{username}` — opening recommendations

### Redis Keys
- `user:games:{username}` — list of game IDs
- `user:openings:{username}` — hash of opening → stats (wins/losses/draws)
