# Agents Architecture & Concepts

## Chess Sniper Concept
The core offering of this application is the **Chess Sniper**. 

**Workflow:**
1. **Target Acquisition**: The customer provides a target username from a chess platform (e.g., `chess.com` or `lichess`).
2. **Data Ingestion**: Our system automatically pulls the target's public historical games via the platform's API.
3. **Analysis & Profiling**: We deeply analyze the target's playstyle, opening repertoire, time management, and common tactical or positional weaknesses.
4. **Sniper Training**: We build a hyper-targeted set of training materials—including interactive puzzles, annotated games, and specific opening traps—designed solely to help our customer defeat that exact individual.

## Microservice Architecture
To ensure scalability, system responsiveness, and fault isolation, we will be utilizing a **microservice architecture**. This is especially critical for segregating high-compute tasks from the user-facing application.

### 1. Gateway & User API (Flask)
- **Role**: Primary backend that serves the React frontend.
- **Responsibilities**: User authentication, frontend routing, database reads, and task orchestration. It delegates heavy workloads to other services to maintain a snappy UI.

### 2. Data Ingestion Service
- **Role**: Fetching and parsing raw game data.
- **Responsibilities**: Connects to external APIs (`lichess.org/api` and `chess.com`), normalizes raw PGN (Portable Game Notation) formats into structured database objects, and manages rate-limiting.

### 3. Engine Analysis Service (High Compute)
- **Role**: The heavy lifter of the application.
- **Responsibilities**: Runs chess engine instances (e.g., Stockfish) on the ingested games. It performs the intensive computational work required to evaluate positions, detect inaccuracies, and assess objective board states. 
- **Scalability**: Can be scaled horizontally (e.g., via Kubernetes or Docker Swarm) independently based on the number of requested sniper profiles in the queue.

### 4. Report & Training Generation Service
- **Role**: Intelligence synthesizer.
- **Responsibilities**: Consumes the raw evaluations from the Engine Analysis Service and transforms them into actionable training materials. This could involve LLM agents to draft psychological profiles and generate human-readable advice.


### 5. Coding Style
- **Object-Oriented lite**  Typically use classes for interface control.  Don't store too much state in the classes.  Prefer composition over inheritance.