FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask flask-cors kafka-python

COPY app.py .

EXPOSE 8000

CMD ["python", "app.py"]
