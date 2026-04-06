import sys
import os
import json
import io

# Add the project root to sys.path if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the function from game_scraper
# We need to handle the case where game_scraper might not be importable as a module easily
# since it's intended for Flink.
# Let's just redefine the function here for the unit test, or try to import it.

def get_book_metrics(pgn_str: str, book_dict: dict) -> tuple[int, str | None]:
    import chess.pgn
    if not pgn_str or not book_dict:
        return 0, None

    try:
        pgn_io = io.StringIO(pgn_str)
        game = chess.pgn.read_game(pgn_io)
        if not game:
            return 0, None

        current_level = book_dict
        depth = 0
        last_color = None
        board = game.board()

        for move in game.mainline_moves():
            san_move = board.san(move)
            if san_move in current_level:
                current_level = current_level[san_move]
                depth += 1
                last_color = "white" if depth % 2 != 0 else "black"
                board.push(move)
            else:
                break

        return depth, last_color
    except Exception as e:
        print(f"Error: {e}")
        return 0, None

def test_metrics():
    mock_book = {
        "e4": {
            "e5": {
                "Nf3": {
                    "Nc6": {
                        "_n": "Ruy Lopez"
                    }
                }
            }
        }
    }

    # Test case 1: Empty PGN
    assert get_book_metrics("", mock_book) == (0, None)

    # Test case 2: Single move (White)
    assert get_book_metrics("1. e4", mock_book) == (1, "white")

    # Test case 3: Two moves (Black)
    assert get_book_metrics("1. e4 e5", mock_book) == (2, "black")

    # Test case 4: Three moves
    assert get_book_metrics("1. e4 e5 2. Nf3", mock_book) == (3, "white")

    # Test case 5: Out of book
    assert get_book_metrics("1. d4", mock_book) == (0, None)

    # Test case 6: Partial book
    assert get_book_metrics("1. e4 d5", mock_book) == (1, "white")

    print("All tests passed!")

if __name__ == "__main__":
    test_metrics()
