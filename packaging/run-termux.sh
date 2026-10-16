#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== AURI Studio (Termux / Android) ==="

if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

# Redis
if ! redis-cli ping >/dev/null 2>&1; then
  echo "Starting Redis..."
  redis-server --daemonize yes
fi

echo "Starting Celery worker (concurrency=1)..."
python -m celery -A app.workers.celery_app worker --loglevel=info --concurrency=1 &
WORKER_PID=$!

cleanup() {
  kill $WORKER_PID 2>/dev/null || true
}
trap cleanup EXIT

echo ""
echo "API: http://localhost:8000"
echo "Откройте этот адрес в браузере телефона."
echo ""

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
