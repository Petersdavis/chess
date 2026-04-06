import requests
import base64
import json
import os

BASE_URL = "http://localhost:5000"
PGN_PATH = os.path.join(os.path.dirname(__file__), "test", "game1.pgn")


def test_pgn():
    with open(PGN_PATH, "r") as f:
        #f is a base64 encoded string
        pgn = base64.b64decode(f.read()).decode()

    print(f"Sending {PGN_PATH} to {BASE_URL}/analyze/pgn ...\n")
    print(f"PGN: {pgn}")
    response = requests.post(
        f"{BASE_URL}/analyze/pgn",
        json={"pgn": pgn, "depth": 12},
        timeout=120,
    )

    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return

    data = response.json()

    headers = data.get("headers", {})
    print(f"Event : {headers.get('Event', '?')}")
    print(f"White : {headers.get('White', '?')} ({headers.get('WhiteElo', '?')})")
    print(f"Black : {headers.get('Black', '?')} ({headers.get('BlackElo', '?')})")
    print(f"Result: {headers.get('Result', '?')}")
    print(f"Depth : {data.get('depth')}")
    print(f"Moves : {len(data.get('moves', []))}\n")

    print(f"{'#':<4} {'Move':<8} {'Type':<5} {'Score':>8}  {'Best Move'}")
    print("-" * 45)
    for i, move in enumerate(data.get("moves", []), start=1):
        ev = move["evaluation"]
        ev_type = ev.get("type", "?")
        ev_value = ev.get("value", 0)
        score = f"M{ev_value}" if ev_type == "mate" else f"{ev_value / 100:.2f}"
        print(f"{i:<4} {move['move']:<8} {ev_type:<5} {score:>8}  {move.get('best_move', '-')}")


if __name__ == "__main__":
    test_pgn()
