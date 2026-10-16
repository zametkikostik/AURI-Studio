from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path
import logging

from app.api.routes import router
from app.config import settings
from app.core.openrouter import load_persisted_key, openrouter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)

load_persisted_key()  # ключ из storage/settings.json или .env

app = FastAPI(
    title="AURI Studio",
    description="AI-Native Video Orchestrator & Autonomous Editor",
    version="0.1.0",
)

app.include_router(router, prefix="/api/v1", tags=["AURI"])

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "ffmpeg": settings.FFMPEG_PATH,
        "ffprobe": settings.FFPROBE_PATH,
        "openrouter_configured": openrouter.is_configured,
    }
