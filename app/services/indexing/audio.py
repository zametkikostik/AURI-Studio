import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional
import aiofiles
import logging

from app.config import settings
from app.core.openrouter import openrouter
from app.utils.files import ensure_dir, get_project_dirs

logger = logging.getLogger("auri.audio")


class AudioIndexer:
    """Извлечение аудио + транскрипция через Whisper (OpenRouter)."""

    def extract_audio(self, video_path: str | Path, output_wav: str | Path) -> Path:
        output_wav = Path(output_wav)
        ensure_dir(output_wav.parent)

        cmd = [
            settings.FFMPEG_PATH, "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output_wav),
        ]

        logger.info(f"Extracting audio: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed:\n{result.stderr}")

        return output_wav

    async def transcribe(
        self,
        video_path: str | Path,
        project_id: str,
        language: str = "ru",
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        dirs = get_project_dirs(project_id)
        audio_path = dirs["audio_wav"]
        transcript_path = dirs["transcript"]

        self.extract_audio(video_path, audio_path)

        logger.info(f"Transcribing with model={model or settings.DEFAULT_WHISPER_MODEL}")
        transcript = await openrouter.transcribe(
            audio_path=audio_path,
            model=model,
            language=language,
        )

        async with aiofiles.open(transcript_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(transcript, ensure_ascii=False, indent=2))

        return {
            "audio_path": str(audio_path),
            "transcript_path": str(transcript_path),
            "transcript": transcript,
        }
