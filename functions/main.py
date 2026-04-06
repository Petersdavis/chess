import json
import logging
from firebase_functions import https_fn, firestore_fn, identity_fn
from firebase_admin import initialize_app, firestore
from datetime import datetime

initialize_app()

# Configuration for Kafka Bridge
KAFKA_BOOTSTRAP = "kafka:9092"
TOPIC_USERS_NEW = "users.new"

@https_fn.on_request()
def hello_world(req: https_fn.Request) -> https_fn.Response:
    return https_fn.Response("Hello from Firebase Functions (Dockerized!)")

@identity_fn.before_user_created()
def create_user_profile(event: identity_fn.AuthBlockingEvent) -> identity_fn.BeforeCreateResponse | None:
    """
    Triggers when a new user signs up via Firebase Auth.
    Ensures a synchronized profile exists in the /users collection.
    """
    db = firestore.client()
    user = event.data
    
    user_data = {
        "uid": user.uid,
        "email": user.email,
        "displayName": user.display_name or "New Recruit",
        "photo_url": user.photo_url,
        "metadata": {
            "createdAt": datetime.utcnow().isoformat(),
            "lastSignIn": None,
        },
        "role": "user",
        "status": "basic",
        "onboardingComplete": False,
        "platforms": {
            "chessCom": None,
            "lichess": None
        }
    }
    
    # Store the profile in the 'users' collection using the Auth UID as the document ID
    db.collection("users").document(user.uid).set(user_data)
    print(f"Successfully initialized profile for UID: {user.uid}")
    return None

@firestore_fn.on_document_written(document="users/{uid}")
def on_user_profile_change(event: firestore_fn.Event[firestore_fn.Change[firestore_fn.DocumentSnapshot | None]]) -> None:
    """
    Triggers when a user profile is updated.
    Detects if a Chess.com handle was added/changed and triggers ingestion.
    """
    try:
        from kafka import KafkaProducer
    except ImportError:
        logging.error("Kafka-python library missing. Ingestion trigger delayed.")
        return

    before = event.data.before.to_dict() if event.data.before else {}
    after = event.data.after.to_dict() if event.data.after else {}

    old_platforms = before.get("platforms", {}) or {}
    new_platforms = after.get("platforms", {}) or {}

    old_chess = old_platforms.get("chessCom")
    new_chess = new_platforms.get("chessCom")

    if new_chess and new_chess != old_chess:
        print(f"Detected mapping update: {new_chess} for {event.params['uid']}")
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                request_timeout_ms=5000
            )
            
            message = {"username": new_chess}
            producer.send(TOPIC_USERS_NEW, message)
            producer.flush()
            producer.close()
            print(f"Bridge to Flink complete for topic: {TOPIC_USERS_NEW}")
        except Exception as e:
            logging.error(f"Kafka Bridge failure: {e}")
