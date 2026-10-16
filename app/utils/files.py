from pathlib import Path
from app.config import settings


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_project_dirs(project_id: str) -> dict[str, Path]:
    """Возвращает все стандартные директории проекта"""
    root = settings.storage_path
    raw = ensure_dir(root / "raw" / project_id)
    indexed = ensure_dir(root / "indexed" / project_id)
    output = ensure_dir(root / "output" / project_id)
    frames = ensure_dir(indexed / "frames")

    return {
        "raw": raw,
        "indexed": indexed,
        "output": output,
        "frames": frames,
        "source_video": next(raw.glob("source.*"), None),
        "brief": raw / "brief.txt",
        "meta": raw / "meta.json",
        "audio_wav": indexed / "audio.wav",
        "transcript": indexed / "transcript.json",
        "frame_descriptions": indexed / "frame_descriptions.json",
        "timeline": indexed / "timeline.json",
        "timeline_otio": indexed / "timeline.otio",
        "index_summary": indexed / "index_summary.json",
        "final_video": output / "final.mp4",
    }
