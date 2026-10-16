@echo off
echo Starting AURI Studio (Windows)...

REM Check Redis
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo Redis not running. Trying Docker...
    docker start auri-redis 2>nul || docker run -d --name auri-redis -p 6379:6379 redis:7-alpine
)

echo Starting Celery worker...
start "AURI Worker" cmd /k celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

echo Starting FastAPI...
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
