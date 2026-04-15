import os
import json
import glob
import re
import sys
import chess.pgn
import itertools

# Configuration
MAX_DEPTH = 10  # Limit to 10 full moves (20 plies)

print("--- DEBUG: Script started ---", flush=True)

# Import the canonical openings database
try:
    # Add script directory to sys.path to ensure opening_data can be imported
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from opening_data import OPENINGS
    print(f"--- DEBUG: Imported {len(OPENINGS)} openings from opening_data ---", flush=True)
except ImportError:
    print("Warning: opening_data.py not found. Intelligence pre-seeding disabled.", flush=True)
    OPENINGS = {}

def parse_opening_moves(move_string):
    """
    Cleans an opening move string like '1. e4 c6 2. d4 d5' 
    into a list of pure SAN moves ['e4', 'c6', 'd4', 'd5'].
    """
    parts = move_string.split()
    return [p for p in parts if not re.match(r'^\d+\.?\.?\.?$', p)]

def process_pgn_into_tree(pgn_path, master_tree):
    """
    Worker function to process a single PGN file directly into the master tree.
    Uses board state re-use for maximum performance.
    """
    games_processed = 0
    try:
        with open(pgn_path, encoding='utf-8', errors='replace') as pgn_file:
            while True:
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break
                
                games_processed += 1
                if(games_processed % 5 != 1):
                    continue
                board = game.board()
                current_level = master_tree
                
                # Limit the depth of unique moves to MAX_DEPTH
                for move in itertools.islice(game.mainline_moves(), MAX_DEPTH):
                    san_move = board.san(move)
                    if san_move not in current_level:
                        current_level[san_move] = {}
                    
                    current_level = current_level[san_move]
                    board.push(move)
    except Exception as e:
        print(f"Error processing {pgn_path}: {e}", flush=True)
    
    return games_processed

def build_book(database_path, output_file):
    """
    Builds a nested dictionary of moves, pre-seeded with opening names.
    Optimized for streaming and board re-use with periodic atomic saves.
    """
    book_tree = {}

    # --- PHASE 1: Intelligence Pre-seeding ---
    print(f"Pre-seeding {len(OPENINGS)} canonical openings...", flush=True)
    for key, data in OPENINGS.items():
        moves = parse_opening_moves(data.get("moves", ""))
        name = data.get("name")
        
        current_level = book_tree
        # Limit the depth of canonical openings to MAX_DEPTH
        for move in moves[:MAX_DEPTH]:
            if move not in current_level:
                current_level[move] = {}
            current_level = current_level[move]
        
        if name:
            current_level["_n"] = name

    # --- PHASE 2: Tactical Archive Digitization ---
    pgn_files = glob.glob(os.path.join(database_path, "**/*.pgn"), recursive=True)
    if not pgn_files:
        print(f"Warning: No PGN files found in {database_path}. Exporting pre-seeded tree only.", flush=True)
    else:
        print(f"Digitizing {len(pgn_files)} archive files...", flush=True)
        total_games = 0
        for i, pgn_path in enumerate(pgn_files):
            # Print current file for visibility
            filename = os.path.basename(pgn_path)
            print(f"[{i+1}/{len(pgn_files)}] Processing {filename}...", flush=True)
            
            count = process_pgn_into_tree(pgn_path, book_tree)
            total_games += count
            
            # Atomic checkpoint saves every 5 files
            if (i + 1) == len(pgn_files):
                print(f"  Checkpoint: Saving progress ({total_games} total engagements synthesized)...", flush=True)
                temp_file = output_file + ".tmp"
                with open(temp_file, 'w') as f:
                    json.dump(book_tree, f, indent=2)
                # Atomically replace old file
                if os.path.exists(output_file):
                    os.remove(output_file)
                os.rename(temp_file, output_file)
        print(f"Synthesis complete. Processed {total_games} total engagements.", flush=True)
    
    print(f"Master Book finalized at: {output_file}", flush=True)

if __name__ == "__main__":
    # Ensure BASE_DIR is correct regardless of where script is called from
    SCRIPT_PATH = os.path.abspath(__file__)
    BASE_DIR = os.path.dirname(SCRIPT_PATH)
    
    # Logic for database path: openings/database
    DB_PATH = os.path.join(BASE_DIR, "database")
    OUTPUT_PATH = os.path.join(BASE_DIR, "bookmoves.json")
    
    if not os.path.exists(DB_PATH):
        print(f"Database directory {DB_PATH} not found. Running pre-seeding only.", flush=True)
    
    build_book(DB_PATH, OUTPUT_PATH)
