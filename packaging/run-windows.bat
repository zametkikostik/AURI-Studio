@echo off
cd /d "%~dp0"
echo === AURI Studio (Windows) ===

if not exist .env (
  if exist .env.example (
    copy .env.example .env
    echo Created .env — please set OPENROUTER_API_KEY
  )
)

REM Try to start Redis via Docker
docker start auri-redis 2>nul || docker run -d --name auri-redis -p 6379:6379 redis:7-alpine 2>nul

echo Starting Celery worker...
start "AURI Worker" cmd /c "python -m celery -A app.workers.celery_app worker --loglevel=info --concurrency=2"

echo Starting API on http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
