#!/bin/bash
set -e

# Change to the project directory
cd /app

# Ensure we have a Linux-compatible venv for the functions
if [ -d "functions" ]; then
    echo "Found functions directory. Initializing Linux venv..."
    python3 -m venv functions/venv
    
    # Activate and install dependencies inside the container
    source functions/venv/bin/activate
    
    if [ -f "functions/requirements.txt" ]; then
        echo "Installing requirements from /app/functions/requirements.txt..."
        pip install --upgrade pip
        pip install -r functions/requirements.txt
    fi
else
    echo "Warning: /app/functions not found. Skipping venv initialization."
fi

# Run the original command
echo "Starting Firebase Emulator..."
exec firebase emulators:start --project demo-local \
  --export-on-exit=/data/emulator-export \
  --import=/data/emulator-export
