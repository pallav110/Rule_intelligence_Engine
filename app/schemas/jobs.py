from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    description: str | None = None
    status: str
    created_at: datetime


class JobCreateRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=50)
    job_type: str = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=1, max_length=100)


class JobResponse(BaseModel):
    job_id: str
    workspace_id: str
    job_type: str
    status: str
    idempotency_key: str
    progress: int = 0
    completed_at: datetime | None = None
