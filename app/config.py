from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path
import platform
import shutil


def find_ffmpeg() -> str:
    """Автоматически ищет ffmpeg в системе (Windows / Linux / macOS / Termux)"""
    path = shutil.which("ffmpeg")
    if path:
        return path

    if platform.system() == "Windows":
        candidates = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                return c

    termux = Path("/data/data/com.termux/files/usr/bin/ffmpeg")
    if termux.exists():
        return str(termux)

    return "ffmpeg"


def find_ffprobe() -> str:
    path = shutil.which("ffprobe")
    if path:
        return path

    if platform.system() == "Windows":
        candidates = [
            r"C:\ffmpeg\bin\ffprobe.exe",
            r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                return c

    termux = Path("/data/data/com.termux/files/usr/bin/ffprobe")
    if termux.exists():
        return str(termux)

    return "ffprobe"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    DEFAULT_LLM_MODEL: str = "anthropic/claude-3.5-sonnet"
    DEFAULT_VISION_MODEL: str = "qwen/qwen-2-vl-72b-instruct"
    DEFAULT_WHISPER_MODEL: str = "openai/whisper-large-v3"

    STORAGE_ROOT: str = "./storage"
    FFMPEG_PATH: str = find_ffmpeg()
    FFPROBE_PATH: str = find_ffprobe()

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    @property
    def storage_path(self) -> Path:
        p = Path(self.STORAGE_ROOT)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
