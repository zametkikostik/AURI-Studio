from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Optional
import json

from app.services.ingestion import IngestionService
from app.workers.tasks import full_pipeline, index_project, create_timeline, render_project
from app.utils.files import get_project_dirs
from app.api.schemas import ProjectCreateResponse, JobResponse, ProjectStatus

router = APIRouter()
ingestion = IngestionService()


@router.post("/projects", response_model=ProjectCreateResponse)
async def create_project(
    video: UploadFile = File(...),
    brief: str = Form(...),
    auto_start: bool = Form(True),
    language: str = Form("ru"),
):
    if not brief.strip():
        raise HTTPException(400, "Brief (ТЗ) не может быть пустым")

    meta = await ingestion.create_project(video=video, brief=brief)

    if auto_start:
        full_pipeline.delay(meta["project_id"], language=language)

    return ProjectCreateResponse(
        project_id=meta["project_id"],
        status="ingested" if not auto_start else "processing",
        message="Проект создан" + (" и пайплайн запущен" if auto_start else ""),
    )


@router.get("/projects")
async def list_projects():
    return ingestion.list_projects()


@router.get("/projects/{project_id}", response_model=ProjectStatus)
async def get_project(project_id: str):
    meta = ingestion.get_project(project_id)
    if not meta:
        raise HTTPException(404, "Project not found")
    return ProjectStatus(
        project_id=project_id,
        status=meta.get("status", "unknown"),
        original_filename=meta.get("original_filename"),
        brief=meta.get("brief"),
        output_path=meta.get("output_path"),
        created_at=meta.get("created_at"),
    )


@router.post("/projects/{project_id}/index", response_model=JobResponse)
async def start_index(project_id: str, language: str = "ru"):
    meta = ingestion.get_project(project_id)
    if not meta:
        raise HTTPException(404, "Project not found")
    task = index_project.delay(project_id, language=language)
    return JobResponse(task_id=task.id, status="started", message="Indexing started")


@router.post("/projects/{project_id}/timeline", response_model=JobResponse)
async def start_timeline(project_id: str, model: Optional[str] = None):
    meta = ingestion.get_project(project_id)
    if not meta:
        raise HTTPException(404, "Project not found")
    task = create_timeline.delay(project_id, model=model)
    return JobResponse(task_id=task.id, status="started", message="Director started")


@router.post("/projects/{project_id}/render", response_model=JobResponse)
async def start_render(project_id: str):
    meta = ingestion.get_project(project_id)
    if not meta:
        raise HTTPException(404, "Project not found")
    task = render_project.delay(project_id)
    return JobResponse(task_id=task.id, status="started", message="Rendering started")


@router.post("/projects/{project_id}/run", response_model=JobResponse)
async def run_full(project_id: str, language: str = "ru", model: Optional[str] = None):
    meta = ingestion.get_project(project_id)
    if not meta:
        raise HTTPException(404, "Project not found")
    task = full_pipeline.delay(project_id, language=language, model=model)
    return JobResponse(task_id=task.id, status="started", message="Full pipeline started")


@router.get("/projects/{project_id}/timeline")
async def get_timeline(project_id: str):
    dirs = get_project_dirs(project_id)
    if not dirs["timeline"].exists():
        raise HTTPException(404, "Timeline not ready yet")
    return json.loads(dirs["timeline"].read_text(encoding="utf-8"))


@router.get("/projects/{project_id}/download")
async def download_result(project_id: str):
    dirs = get_project_dirs(project_id)
    if not dirs["final_video"].exists():
        raise HTTPException(404, "Final video not ready")
    return FileResponse(
        path=dirs["final_video"],
        filename=f"auri_{project_id[:8]}.mp4",
        media_type="video/mp4",
    )


@router.get("/projects/{project_id}/otio")
async def download_otio(project_id: str):
    dirs = get_project_dirs(project_id)
    otio_path = dirs["indexed"] / "timeline.otio"
    if not otio_path.exists():
        if not dirs["timeline"].exists():
            raise HTTPException(404, "Timeline not ready yet")
        try:
            from app.services.rendering.timeline import save_otio, HAS_OTIO
            if not HAS_OTIO:
                raise HTTPException(501, "opentimelineio not installed")
            plan = json.loads(dirs["timeline"].read_text(encoding="utf-8"))
            source = dirs["source_video"]
            source_map = {"main": str(source)} if source else {}
            save_otio(plan, otio_path, source_map=source_map)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"OTIO export failed: {e}")
    return FileResponse(
        path=otio_path,
        filename=f"auri_{project_id[:8]}.otio",
        media_type="application/json",
    )


@router.get("/jobs/{task_id}")
async def get_job_status(task_id: str):
    from app.workers.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "status": result.status,
    }
    if result.status == "PROGRESS":
        response["meta"] = result.info
    elif result.status == "SUCCESS":
        response["result"] = result.result
    elif result.status == "FAILURE":
        response["error"] = str(result.result)
    return response
