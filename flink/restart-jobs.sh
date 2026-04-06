#!/bin/bash
# Cancels all running Flink jobs and resubmits them in dependency order.
# Usage: ./flink/restart-jobs.sh

set -eo pipefail

JOBMANAGER="manager"

JOBS_DIR="/opt/flink/jobs"
JOBS=(
  firestore_writer.py
  analysis_job.py
  game_scraper.py
  game_url_collector.py
  create_player.py
)

echo "==> Cancelling all running jobs..."
RUNNING=$(docker exec "$JOBMANAGER" flink list 2>/dev/null | grep -oP '(?<=: )([a-f0-9]{32})' || true)

if [ -z "$RUNNING" ]; then
  echo "    No running jobs found."
else
  for JOB_ID in $RUNNING; do
    echo "    Cancelling $JOB_ID..."
    docker exec "$JOBMANAGER" flink cancel "$JOB_ID"
  done
fi

echo ""
echo "==> Submitting jobs..."
for JOB in "${JOBS[@]}"; do
  echo "    Submitting $JOB..."
  MSYS_NO_PATHCONV=1 docker exec -w "$JOBS_DIR" "$JOBMANAGER" flink run -d -py "$JOB" || echo "    [FAILED] $JOB"
done

echo ""
echo "==> Done. Running jobs:"
docker exec "$JOBMANAGER" flink list -a
