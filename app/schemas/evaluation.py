from typing import Any

from pydantic import BaseModel, Field


class EvaluationCreateRequest(BaseModel):
    model_version_id: str = Field(min_length=1, max_length=100)
    dataset_version_id: str = Field(min_length=1, max_length=100)


class EvaluationMetricResponse(BaseModel):
    metric_name: str
    metric_value: float
    metric_details: dict[str, Any] | None = None


class EvaluationResponse(BaseModel):
    evaluation_run_id: str
    model_version_id: str
    dataset_version_id: str
    status: str
    started_at: Any | None = None
    completed_at: Any | None = None
    metrics: list[EvaluationMetricResponse]
