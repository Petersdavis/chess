FROM eclipse-temurin:21-jre-jammy

# Install Node.js, Python for Python functions, and other utilities
RUN apt-get update && apt-get install -y curl python3 python3-pip python3-venv \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install firebase-tools
RUN npm install -g firebase-tools

WORKDIR /app

# Add a script to initialize the venv inside the container
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Use the entrypoint script to initialize and start
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
