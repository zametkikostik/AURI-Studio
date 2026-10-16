from pydantic import BaseModel, Field
from typing import Optional, Any


class ProjectCreateResponse(BaseModel):
    project_id: str
    status: str
    message: str = "Project created"


class JobResponse(BaseModel):
    task_id: str
    status: str
    message: str = "Task started"


class ProjectStatus(BaseModel):
    project_id: str
    status: str
    original_filename: Optional[str] = None
    brief: Optional[str] = None
    output_path: Optional[str] = None
    created_at: Optional[str] = None
    extra: Optional[dict[str, Any]] = None


class TimelineResponse(BaseModel):
    project_id: str
    timeline: dict[str, Any]
