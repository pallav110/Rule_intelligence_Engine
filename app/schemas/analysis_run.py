from datetime import datetime
from typing import Any
from pydantic import BaseModel

class AnalysisRunResponse(BaseModel):
    analysis_run_id: str
    feedback_id: str
    workspace_id: str
    model_version_id: str | None = None
    dataset_version_id: str | None = None
    taxonomy_version: str | None = None
    domain_pack_id: str | None = None
    threshold_configuration: dict[str, Any] | None = None
    processing_mode: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
