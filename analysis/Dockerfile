FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the stockfish tarball (using wildcard in case it's still named .crdownload or .tar)
# Make sure to wait until your download is finished before building!
COPY stockfish-ubuntu-x86-64*.tar* /tmp/stockfish.tar

# Install tar and dependencies, extract stockfish, put it in bin, and clean up
RUN apt-get update && apt-get install -y tar procps && \
    mkdir -p /tmp/stockfish && \
    tar -xf /tmp/stockfish.tar -C /tmp/stockfish && \
    # The tarball might have nested directories, we just find the binary and move it
    find /tmp/stockfish -type f -name "stockfish*" -executable -exec mv {} /usr/local/bin/stockfish \; && \
    # Ensure it's executable
    chmod +x /usr/local/bin/stockfish && \
    rm -rf /tmp/stockfish /tmp/stockfish.tar && \
    # Verify installation
    echo "quit" | stockfish && \
    rm -rf /var/lib/apt/lists/*

# Copy the python dependencies and application code
COPY . .

# Install Flask and the python-stockfish wrapper
# gunicorn is used to serve the flask app robustly
RUN pip install --no-cache-dir Flask stockfish gunicorn python-chess

# Expose port 5000 for the flask server
EXPOSE 5000

# Run the Flask app with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "analyzer:app"]
