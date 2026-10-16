import subprocess
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import aiofiles
import logging

from app.config import settings
from app.core.openrouter import openrouter
from app.utils.files import ensure_dir, get_project_dirs

logger = logging.getLogger("auri.vision")


class VisionIndexer:
    """Сэмплирование кадров + описание через Vision-модели OpenRouter."""

    def get_duration(self, video_path: str | Path) -> float:
        cmd = [
            settings.FFPROBE_PATH, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        return float(result.stdout.strip())

    def sample_frames(
        self,
        video_path: str | Path,
        output_dir: str | Path,
        interval_sec: float = 4.0,
        max_frames: int = 40,
    ) -> List[Dict[str, Any]]:
        output_dir = Path(output_dir)
        ensure_dir(output_dir)

        duration = self.get_duration(video_path)
        timestamps = []
        t = 0.0
        while t < duration and len(timestamps) < max_frames:
            timestamps.append(round(t, 2))
            t += interval_sec

        frames = []
        for i, ts in enumerate(timestamps):
            frame_path = output_dir / f"frame_{i:04d}_{ts:.2f}.jpg"
            cmd = [
                settings.FFMPEG_PATH, "-y",
                "-ss", str(ts),
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "3",
                str(frame_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"Failed to extract frame at {ts}s: {result.stderr[:200]}")
                continue
            frames.append({"timestamp": ts, "path": str(frame_path)})

        logger.info(f"Extracted {len(frames)} frames")
        return frames

    async def describe_frames(
        self,
        frames: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_concurrent: int = 4,
    ) -> List[Dict[str, Any]]:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _one(frame: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    desc = await openrouter.vision_describe(
                        image_path=frame["path"],
                        model=model,
                    )
                    return {
                        "timestamp": frame["timestamp"],
                        "path": frame["path"],
                        "description": desc.strip(),
                    }
                except Exception as e:
                    logger.error(f"Vision error at {frame['timestamp']}s: {e}")
                    return {
                        "timestamp": frame["timestamp"],
                        "path": frame["path"],
                        "description": f"[ошибка анализа: {e}]",
                    }

        results = await asyncio.gather(*[_one(f) for f in frames])
        results = sorted(results, key=lambda x: x["timestamp"])
        return results

    async def index(
        self,
        video_path: str | Path,
        project_id: str,
        interval_sec: float = 4.0,
        max_frames: int = 35,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        dirs = get_project_dirs(project_id)

        frames = self.sample_frames(
            video_path=video_path,
            output_dir=dirs["frames"],
            interval_sec=interval_sec,
            max_frames=max_frames,
        )

        descriptions = await self.describe_frames(frames, model=model)

        async with aiofiles.open(dirs["frame_descriptions"], "w", encoding="utf-8") as f:
            await f.write(json.dumps(descriptions, ensure_ascii=False, indent=2))

        return {
            "frames_dir": str(dirs["frames"]),
            "descriptions_path": str(dirs["frame_descriptions"]),
            "descriptions": descriptions,
            "frames_count": len(descriptions),
        }
