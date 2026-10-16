#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "=== AURI Studio (Linux) ==="

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "Created .env from .env.example — please set OPENROUTER_API_KEY"
  fi
fi

# Prefer system python if present, else try bundled
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  PYTHON=python
fi

# Start Redis if possible
if command -v redis-cli >/dev/null 2>&1; then
  if ! redis-cli ping >/dev/null 2>&1; then
    if command -v docker >/dev/null 2>&1; then
      docker start auri-redis 2>/dev/null || docker run -d --name auri-redis -p 6379:6379 redis:7-alpine
    else
      echo "Warning: Redis not running. Start it manually."
    fi
  fi
fi

# Worker in background
echo "Starting Celery worker..."
$PYTHON -m celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 &
WORKER_PID=$!

cleanup() {
  echo "Stopping worker..."
  kill $WORKER_PID 2>/dev/null || true
}
trap cleanup EXIT

echo "Starting API on http://0.0.0.0:8000"
$PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8000
