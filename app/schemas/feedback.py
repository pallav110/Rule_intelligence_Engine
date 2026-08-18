from pydantic import BaseModel, Field


class FeedbackAnalysisRequest(BaseModel):
    feedback: str = Field(min_length=1)
    domain: str = Field(min_length=1)

from typing import Any


class ClassificationResponse(BaseModel):
    feedback_type: str
    rule_category: str | None
    is_actionable: bool
    requires_clarification: bool
    confidence: float


class ValidationErrorResponse(BaseModel):
    field: str
    reason: str


class ValidationResponse(BaseModel):
    valid: bool
    errors: list[ValidationErrorResponse]


class FeedbackAnalysisResponse(BaseModel):
    feedback_id: str
    classification: ClassificationResponse
    rules: list[dict[str, Any]]
    validation: ValidationResponse