#!/usr/bin/env bash
set -e

echo ">>> Starting Redis (if not running)..."
if ! redis-cli ping > /dev/null 2>&1; then
  if command -v docker > /dev/null; then
    docker start auri-redis 2>/dev/null || docker run -d --name auri-redis -p 6379:6379 redis:7-alpine
  else
    echo "Redis is not running and Docker not found. Please start Redis manually."
    exit 1
  fi
fi

echo ">>> Starting Celery worker in background..."
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 &
WORKER_PID=$!

echo ">>> Starting FastAPI..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Cleanup
kill $WORKER_PID 2>/dev/null || true
