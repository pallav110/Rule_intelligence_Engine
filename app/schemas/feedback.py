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

class FeedbackBatchAnalysisRequest(BaseModel):
    items: list[FeedbackAnalysisRequest] = Field(min_length=1)

class FeedbackBatchAnalysisResponse(BaseModel):
    results: list[FeedbackAnalysisResponse]

class RuleComparisonRequest(BaseModel):
    rule: dict[str, Any]
    existing_rules: list[dict[str, Any]] = []


class RuleCompareRequest(BaseModel):
    rule_a: dict[str, Any]
    rule_b: dict[str, Any]


class RuleComparisonResponse(BaseModel):
    relationship: str
    confidence: float
    matching_rule_id: str | None = None
    conflicting_rule_id: str | None = None
    details: dict[str, Any] = {}