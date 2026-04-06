FROM flink:1.19-scala_2.12

# Install Python and PyFlink (must match Flink version)
RUN apt-get update && apt-get install -y python3 python3-pip wget && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    pip3 install --no-cache-dir apache-flink==1.19.0 requests redis google-cloud-firestore kafka-python loguru nanoid && \
    rm -rf /var/lib/apt/lists/*

# Kafka connector + client JARs — connector is a thin JAR so kafka-clients must be added separately
RUN wget -q -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/org/apache/flink/flink-connector-kafka/3.2.0-1.19/flink-connector-kafka-3.2.0-1.19.jar && \
    wget -q -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/org/apache/kafka/kafka-clients/3.4.0/kafka-clients-3.4.0.jar
