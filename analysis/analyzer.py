from flask import Flask, request, jsonify
from stockfish import Stockfish
import chess
import chess.pgn
import base64
import io
import os
import re

app = Flask(__name__)

# Initialize stockfish from the path we put it in the Dockerfile
STOCKFISH_PATH = "/usr/local/bin/stockfish"

def get_stockfish():
    """Returns a new stockfish instance configured to use available threads/hash."""
    stockfish = Stockfish(path=STOCKFISH_PATH)
    stockfish.update_engine_parameters({
        "Threads": 1, 
        "Hash": 256
    })
    return stockfish

def _decode_pgn(pgn: str) -> str:
    """Base64-decode the PGN if encoded, then normalize for python-chess."""
    try:
        pgn = base64.b64decode(pgn.encode()).decode()
    except Exception:
        pass  # Not base64 — use as-is
    # Put each header tag on its own line
    pgn = re.sub(r'\]\s*\[', ']\n[', pgn.strip())
    # Ensure a blank line between the last header and the move text
    pgn = re.sub(r'(\])\s*(\d)', r'\1\n\n\2', pgn)
    return pgn


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Expects a JSON payload:
    {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "depth": 15
    }
    """
    data = request.json
    if not data or 'fen' not in data:
        return jsonify({"error": "Missing 'fen' parameter"}), 400
        
    fen = data['fen']
    depth = data.get('depth', 15)
    
    stockfish = None
    try:
        stockfish = get_stockfish()
        stockfish.set_fen_position(fen)
        stockfish.set_depth(depth)
        
        evaluation = stockfish.get_evaluation()
        best_move = stockfish.get_best_move()
        top_moves = stockfish.get_top_moves(3)
        
        return jsonify({
            "evaluation": evaluation,
            "best_move": best_move,
            "top_moves": top_moves,
            "fen": fen,
            "depth": depth
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if stockfish:
            try:
                stockfish.quit()
            except Exception:
                pass

def _raw_to_score(centipawn, mate) -> dict:
    if mate is not None:
        return {"type": "mate", "value": mate}
    return {"type": "cp", "value": centipawn}


def _score_as_cp(score: dict) -> float | None:
    """Return the score in centipawns from White's perspective, or None for mate."""
    if score["type"] == "mate":
        return None
    return score["value"]


def _precision(played_cp: float | None, best_cp: float | None, color: str) -> float:
    """0–100 score of how close the played move was to the engine's best."""
    if played_cp is None or best_cp is None:
        return 100.0 if played_cp == best_cp else 0.0
    # Scores are from White's perspective; negate for Black so positive = good for mover.
    if color == "black":
        played_cp = -played_cp
        best_cp   = -best_cp
    if best_cp <= 0:
        # Already a losing position for the mover; any move is 100%
        return 100.0
    return round(max(0.0, min(100.0, played_cp / best_cp * 100)), 1)


@app.route('/analyze/pgn', methods=['POST'])
def analyze_pgn():
    """
    Expects a JSON payload:
    {
        "pgn": "<pgn string, optionally base64-encoded>",
        "depth": 15,
        "alternatives": 5
    }
    """
    data = request.json
    if not data or 'pgn' not in data:
        return jsonify({"error": "Missing 'pgn' parameter"}), 400

    depth        = data.get('depth', 15)
    alternatives = data.get('alternatives', 5)

    try:
        game = chess.pgn.read_game(io.StringIO(_decode_pgn(data['pgn'])))
    except Exception as e:
        return jsonify({"error": f"Failed to parse PGN: {str(e)}"}), 400

    if game is None:
        return jsonify({"error": "Invalid or empty PGN"}), 400

    stockfish = None
    try:
        stockfish = get_stockfish()
        stockfish.set_depth(depth)
        stockfish.set_turn_perspective(chess.WHITE)

        moves          = []
        board          = game.board()
        w_precisions   = []
        b_precisions   = []
        prev_played_cp = None

        for move in game.mainline_moves():
            fen_before  = board.fen()
            color       = "white" if board.turn == chess.WHITE else "black"
            move_number = board.fullmove_number
            san         = board.san(move)

            # --- evaluate BEFORE the move to get alternatives ---
            stockfish.set_fen_position(fen_before)
            raw_top = stockfish.get_top_moves(alternatives)

            top_moves = []
            for tm in raw_top:
                try:
                    tm_san = board.san(chess.Move.from_uci(tm["Move"]))
                except Exception:
                    tm_san = tm["Move"]
                top_moves.append({
                    "uci":   tm["Move"],
                    "san":   tm_san,
                    "score": _raw_to_score(tm["Centipawn"], tm["Mate"]),
                })

            best_score = top_moves[0]["score"] if top_moves else None

            # --- evaluate AFTER the move for played_score ---
            board.push(move)
            fen_after = board.fen()
            
            stockfish.set_fen_position(fen_after)
            ev = stockfish.get_evaluation()
            played_score = {"type": ev["type"], "value": ev["value"]}

            # --- delta_cp and precision ---
            best_cp   = _score_as_cp(best_score) if best_score else None
            played_cp = _score_as_cp(played_score)
            delta_cp  = round(played_cp - prev_played_cp, 1) if (played_cp is not None and prev_played_cp is not None) else None
            prev_played_cp = played_cp
            precision = _precision(played_cp, best_cp, color)

            (w_precisions if color == "white" else b_precisions).append(precision)

            moves.append({
                "move_number":  move_number,
                "color":        color,
                "san":          san,
                "fen_before":   fen_before,
                "fen_after":    fen_after,
                "played_score": played_score,
                "best_score":   best_score,
                "delta_cp":     delta_cp,
                "precision":    precision,
                "top_moves":    top_moves,
            })

        # --- final position score ---
        stockfish.set_fen_position(board.fen())
        final_ev    = stockfish.get_evaluation()
        final_score = {"type": final_ev["type"], "value": final_ev["value"]}

        avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else 0.0

        return jsonify({
            "headers":         dict(game.headers),
            "depth":           depth,
            "final_score":     final_score,
            "white_precision": avg(w_precisions),
            "black_precision": avg(b_precisions),
            "moves":           moves,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if stockfish:
            try:
                stockfish.quit()
            except Exception:
                pass


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
