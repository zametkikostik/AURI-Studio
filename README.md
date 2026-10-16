# AURI Studio

**AI-Native Video Orchestrator & Autonomous Editor**

Open-source backend + web UI for autonomous video editing from a text brief.
All AI calls go through **OpenRouter API** (Claude, Qwen-VL, Whisper, etc.).

Platforms: **Windows · Linux · macOS · Android (Termux)**

## Features

- Upload video + text brief
- Indexing: Whisper (word-level) + Vision frame descriptions
- Agentic Director builds a JSON montage plan
- **OpenTimelineIO** export (`.otio`)
- Advanced transitions (xfade: dissolve, wipe, slide, circle, pixelize…)
- Background music + sidechain ducking
- Text overlays
- Mobile-friendly Web UI
- GitHub Actions multi-platform releases

## Quick start (Docker)

```bash
cp .env.example .env
# set OPENROUTER_API_KEY
docker compose up --build
```

Open http://localhost:8000

## Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker run -d --name auri-redis -p 6379:6379 redis:7-alpine
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# other terminal:
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
```

## Releases

Creating a GitHub Release triggers builds for Linux, Windows, and Android (Termux).

```bash
git tag v0.2.0 && git push origin v0.2.0
```

## License

MIT
