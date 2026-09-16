from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4

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


# Specific job create request schemas per spec §5.11-5.15

class TrainModelJobRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=50)
    model_type: str = Field(min_length=1, max_length=50, description="classifier, token_classifier, etc.")
    dataset_version_id: str
    hyperparameters: Optional[Dict[str, Any]] = None
    idempotency_key: str = Field(min_length=1, max_length=100)


class GenerateDatasetJobRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=50)
    domain_pack_id: str = Field(min_length=1, max_length=50)
    num_samples: int = Field(gt=0, le=100000)
    seed_feedback_ids: Optional[list[str]] = None
    idempotency_key: str = Field(min_length=1, max_length=100)


class RunEvaluationJobRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=50)
    model_version_id: str
    dataset_version_id: str
    idempotency_key: str = Field(min_length=1, max_length=100)


class UpdateEmbeddingIndexJobRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=50)
    domain_pack_id: str = Field(min_length=1, max_length=50)
    rule_ids: Optional[list[str]] = None
    idempotency_key: str = Field(min_length=1, max_length=100)


class BatchFeedbackJobRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=50)
    feedback_items: list[str]
    domain_pack_id: Optional[str] = None
    idempotency_key: str = Field(min_length=1, max_length=100)


class JobCreateResponse(BaseModel):
    job_id: str
    workspace_id: str
    job_type: str
    status: str
    idempotency_key: str
    progress: int = 0
    message: str
