import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from app.workers.celery_app import celery_app
from app.services.ingestion import IngestionService
from app.services.indexing.audio import AudioIndexer
from app.services.indexing.vision import VisionIndexer
from app.services.director.agent import DirectorAgent
from app.services.rendering.ffmpeg_engine import FFmpegEngine
from app.services.rendering.timeline import save_otio, HAS_OTIO
from app.utils.files import get_project_dirs, ensure_dir

logger = logging.getLogger("auri.tasks")


def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(bind=True, name="auri.index_project")
def index_project(self, project_id: str, language: str = "ru"):
    self.update_state(state="PROGRESS", meta={"stage": "audio", "progress": 5})

    dirs = get_project_dirs(project_id)
    source = dirs["source_video"]
    if not source or not source.exists():
        raise FileNotFoundError(f"Source video not found for {project_id}")

    audio_indexer = AudioIndexer()
    audio_result = run_async(
        audio_indexer.transcribe(video_path=source, project_id=project_id, language=language)
    )
    self.update_state(state="PROGRESS", meta={"stage": "vision", "progress": 40})

    vision_indexer = VisionIndexer()
    vision_result = run_async(
        vision_indexer.index(video_path=source, project_id=project_id, interval_sec=4.0, max_frames=30)
    )

    summary = {
        "project_id": project_id,
        "status": "indexed",
        "audio": {"transcript_path": audio_result["transcript_path"]},
        "vision": {"frames_count": vision_result["frames_count"], "descriptions_path": vision_result["descriptions_path"]},
    }
    dirs["index_summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    meta = json.loads(dirs["meta"].read_text(encoding="utf-8"))
    meta["status"] = "indexed"
    dirs["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    self.update_state(state="PROGRESS", meta={"stage": "done", "progress": 100})
    return summary


@celery_app.task(bind=True, name="auri.create_timeline")
def create_timeline(self, project_id: str, model: Optional[str] = None):
    self.update_state(state="PROGRESS", meta={"stage": "director", "progress": 10})

    dirs = get_project_dirs(project_id)

    transcript = json.loads(dirs["transcript"].read_text(encoding="utf-8"))
    frames = json.loads(dirs["frame_descriptions"].read_text(encoding="utf-8"))
    brief = dirs["brief"].read_text(encoding="utf-8")

    director = DirectorAgent(model=model)
    plan = run_async(
        director.create_timeline(
            user_brief=brief,
            transcript=transcript,
            frame_descriptions=frames,
            source_id="main",
        )
    )

    dirs["timeline"].write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    otio_path = None
    if HAS_OTIO:
        try:
            source = dirs["source_video"]
            source_map = {"main": str(source)} if source else {}
            otio_file = dirs["indexed"] / "timeline.otio"
            save_otio(plan, otio_file, source_map=source_map)
            otio_path = str(otio_file)
        except Exception as e:
            logger.warning(f"OTIO export failed: {e}")

    meta = json.loads(dirs["meta"].read_text(encoding="utf-8"))
    meta["status"] = "timeline_ready"
    if otio_path:
        meta["otio_path"] = otio_path
    dirs["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    self.update_state(state="PROGRESS", meta={"stage": "done", "progress": 100})
    return {
        "project_id": project_id,
        "clips_count": len(plan.get("clips", [])),
        "timeline_path": str(dirs["timeline"]),
        "otio_path": otio_path,
    }


@celery_app.task(bind=True, name="auri.render_project")
def render_project(self, project_id: str):
    self.update_state(state="PROGRESS", meta={"stage": "rendering", "progress": 10})

    dirs = get_project_dirs(project_id)
    plan = json.loads(dirs["timeline"].read_text(encoding="utf-8"))
    source = dirs["source_video"]

    engine = FFmpegEngine()
    output = engine.render(
        plan=plan,
        source_map={"main": str(source)},
        output_path=dirs["final_video"],
    )

    meta = json.loads(dirs["meta"].read_text(encoding="utf-8"))
    meta["status"] = "rendered"
    meta["output_path"] = str(output)
    dirs["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    self.update_state(state="PROGRESS", meta={"stage": "done", "progress": 100})
    return {"project_id": project_id, "output_path": str(output), "status": "rendered"}


@celery_app.task(bind=True, name="auri.full_pipeline")
def full_pipeline(self, project_id: str, language: str = "ru", model: Optional[str] = None):
    self.update_state(state="PROGRESS", meta={"stage": "indexing", "progress": 5})
    index_project(project_id, language=language)

    self.update_state(state="PROGRESS", meta={"stage": "timeline", "progress": 45})
    create_timeline(project_id, model=model)

    self.update_state(state="PROGRESS", meta={"stage": "render", "progress": 70})
    result = render_project(project_id)

    self.update_state(state="PROGRESS", meta={"stage": "done", "progress": 100})
    return result
