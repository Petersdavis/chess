import json
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from kafka import KafkaProducer

app = Flask(__name__)
CORS(app)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

def get_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode(),
    )

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify({"message": "Hello from Flask backend managed by PDM!"})

@app.route('/api/ingest', methods=['POST'])
def ingest():
    data = request.json
    if not data or 'username' not in data:
        return jsonify({"error": "Missing 'username'"}), 400

    username = data['username'].strip().lower()
    get_producer().send("users.new", {"username": username})
    return jsonify({"queued": username})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
