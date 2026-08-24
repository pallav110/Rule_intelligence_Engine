from typing import Any

from pydantic import BaseModel, Field


class FeedbackAnalysisRequest(BaseModel):
    workspace_id: str
    feedback_id: str
    feedback_text: str = Field(min_length=1)
    schema_context: dict = Field(default_factory=dict)


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
    feedback_type: str
    rule_category: str
    is_actionable: bool
    requires_clarification: bool
    confidence: float
    extracted_rules: Any = None
    suggestion: Any = None
    clarification: Any = None


class FeedbackBatchAnalysisRequest(BaseModel):
    items: list[FeedbackAnalysisRequest] = Field(min_length=1)


class FeedbackBatchAnalysisResponse(BaseModel):
    results: list[FeedbackAnalysisResponse]


class RuleComparisonRequest(BaseModel):
    workspace_id: str
    rule: dict[str, Any]

class RuleCompareRequest(BaseModel):
    rule_a: dict[str, Any]
    rule_b: dict[str, Any]


class RuleComparisonResponse(BaseModel):
    relationship: str
    confidence: float
    matching_rule_id: str | None = None
    conflicting_rule_id: str | None = None
    details: dict[str, Any] = {}