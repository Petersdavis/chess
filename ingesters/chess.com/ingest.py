import time
import logging
import base64
from typing import List, Dict, Any, Iterator
import requests
from google.cloud import firestore

logger = logging.getLogger(__name__)


###
# Todo:    1:  need to have a strategy to keep a user updated.abs
#            2:  need to avoid duplicates
#            3:  need to have a priority queue of users to update
#            4:  should have a players database -- holding lists of games.
#
###


class RateLimitedClient:
    """A minimal HTTP client that enforces a rate limit."""
    
    def __init__(self, requests_per_second: float = 1.0):
        self.delay = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self.headers = {
            "User-Agent": "chess-trainer/0.0 (username: pdavis; contact: petersdavis@gmail.com)"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get(self, url: str) -> Dict[str, Any]:
        """Perform a GET request, ensuring the rate limit."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        
        logger.debug(f"Fetching: {url}")
        response = self.session.get(url)
        self.last_request_time = time.time()
        
        response.raise_for_status()
        return response.json()


class ChessComIngester:
    """Ingests player details and games from chess.com API."""
    
    BASE_URL = "https://api.chess.com/pub/player"

    def __init__(self, client: RateLimitedClient = None, db=None):
        # Use composition: the client handles HTTP and rate limiting
        self.client = client or RateLimitedClient(requests_per_second=1.0)
        self.db = db

    def get_player_profile(self, username: str) -> Dict[str, Any]:
        """Pull player details."""
        url = f"{self.BASE_URL}/{username}"
        return self.client.get(url)

    def get_game_archives(self, username: str) -> List[str]:
        """Get a list of monthly archive URLs for the player."""
        url = f"{self.BASE_URL}/{username}/games/archives"
        data = self.client.get(url)
        return data.get("archives", [])

    def get_games_from_archive(self, archive_url: str) -> List[Dict[str, Any]]:
        """Pull games from a specific archive URL."""
        data = self.client.get(archive_url)
        return data.get("games", [])

    def get_all_games(self, username: str) -> Iterator[Dict[str, Any]]:
        """Yield all games for a user across all archives."""
        logger.info(f"Fetching archives for {username}...")
        archives = self.get_game_archives(username)
        logger.info(f"Found {len(archives)} archives.")
        for archive_url in archives:
            logger.info(f"Fetching games from {archive_url}...")
            games = self.get_games_from_archive(archive_url)
            logger.info(f"Yielding {len(games)} games from {archive_url}...")
            for game in games:
                yield game

    def ingest_games_to_firestore(self, username: str):
        """Fetches all games for a user and writes them to the Firestore /games/ collection."""
        if self.db is None:
            import os
            # When using the emulator without default credentials, a project ID is still required.
            kwargs = {}
            if os.environ.get("FIRESTORE_EMULATOR_HOST") and not os.environ.get("GOOGLE_CLOUD_PROJECT"):
                kwargs["project"] = "demo-local"
            
            logger.info(f"Initializing Firestore client. Emulator Host: {os.environ.get('FIRESTORE_EMULATOR_HOST')}")
            self.db = firestore.Client(**kwargs)
            logger.info("Firestore client initialized successfully.")
            
        games_ref = self.db.collection('games')
        
        for game in self.get_all_games(username):
            white_uname = self._extract_username(game.get('white'))
            black_uname = self._extract_username(game.get('black'))

            outcome = None
            if isinstance(game.get('white'), dict) and 'result' in game.get('white'):
                white_result = game['white'].get('result')
                black_result = game['black'].get('result')
                if white_result == 'win':
                    outcome = 'white'
                elif black_result == 'win':
                    outcome = 'black'
                else:
                    outcome = 'draw'

            doc_id = game.get('url', '').split('/')[-1] or None
            
            raw_pgn = game.get('pgn')
            encoded_pgn = base64.b64encode(raw_pgn.encode()).decode() if raw_pgn else None

            game_doc = {
                'white': white_uname,
                'black': black_uname,
                'outcome': outcome,
                'pgn': encoded_pgn,
                'tcn': game.get('tcn')
            }
            # Remove keys with None values to keep Firestore documents clean
            game_doc = {k: v for k, v in game_doc.items() if v is not None}
            
            logger.info(f"Attempting to write game {doc_id} to Firestore...")
            if doc_id:
                games_ref.document(doc_id).set(game_doc, merge=True)
            else:
                games_ref.add(game_doc)
                
            logger.info(f"Successfully ingested game {doc_id}")

    def _extract_username(self, player_data) -> str:
        if isinstance(player_data, str):
            # Example: "https://api.chess.com/pub/player/erik"
            return player_data.split('/')[-1]
        elif isinstance(player_data, dict):
            return player_data.get('username', '')
        return ""


if __name__ == "__main__":
    import os
    
    # Setup emulator environment for local execution
    if "FIRESTORE_EMULATOR_HOST" not in os.environ:
        os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"
    if "GOOGLE_CLOUD_PROJECT" not in os.environ:
        os.environ["GOOGLE_CLOUD_PROJECT"] = "demo-local"

    # Example usage / test
    logging.basicConfig(level=logging.INFO)
    ingester = ChessComIngester()
    test_user = "pdavis"
    
    print(f"Starting Firestore ingestion for user '{test_user}'...")
    ingester.ingest_games_to_firestore(test_user)
    print("Ingestion complete.")
