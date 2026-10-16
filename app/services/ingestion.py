from pathlib import Path
from typing import Optional
from uuid import uuid4
import json
import aiofiles
from fastapi import UploadFile

from app.config import settings
from app.utils.files import ensure_dir, get_project_dirs


class IngestionService:
    """Приёмка сырых видео и текстового ТЗ."""

    async def create_project(
        self,
        video: UploadFile,
        brief: str,
        project_id: Optional[str] = None,
    ) -> dict:
        project_id = project_id or str(uuid4())
        dirs = get_project_dirs(project_id)

        original_name = video.filename or "video.mp4"
        ext = Path(original_name).suffix.lower()
        if ext not in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}:
            ext = ".mp4"

        video_path = dirs["raw"] / f"source{ext}"

        async with aiofiles.open(video_path, "wb") as f:
            while chunk := await video.read(1024 * 1024):
                await f.write(chunk)

        async with aiofiles.open(dirs["brief"], "w", encoding="utf-8") as f:
            await f.write(brief.strip())

        meta = {
            "project_id": project_id,
            "original_filename": original_name,
            "source_video": str(video_path),
            "brief": brief.strip(),
            "status": "ingested",
            "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }

        async with aiofiles.open(dirs["meta"], "w", encoding="utf-8") as f:
            await f.write(json.dumps(meta, ensure_ascii=False, indent=2))

        return meta

    def get_project(self, project_id: str) -> dict | None:
        dirs = get_project_dirs(project_id)
        if not dirs["meta"].exists():
            return None
        return json.loads(dirs["meta"].read_text(encoding="utf-8"))

    def list_projects(self) -> list[dict]:
        raw_root = settings.storage_path / "raw"
        if not raw_root.exists():
            return []
        projects = []
        for d in sorted(raw_root.iterdir(), reverse=True):
            meta_path = d / "meta.json"
            if meta_path.exists():
                try:
                    projects.append(json.loads(meta_path.read_text(encoding="utf-8")))
                except Exception:
                    continue
        return projects
