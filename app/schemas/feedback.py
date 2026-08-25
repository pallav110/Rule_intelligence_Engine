from typing import Any

from pydantic import BaseModel, Field


class FeedbackAnalysisRequest(BaseModel):
    workspace_id: str
    feedback_id: str | None = None
    feedback_text: str = Field(min_length=1)
    schema_context: dict = Field(default_factory=dict)
    submitted_by: str | None = None


class ClassificationResponse(BaseModel):
    feedback_type: str  # business_rule_correction, unclear_feedback, etc.
    rule_category: str | None  # metric_definition, filter_rule, etc.
    confidence: float  # 0.0-1.0
    is_actionable: bool


class PerFieldConfidence(BaseModel):
    """Per-field confidence with semantic label."""
    business_term: float  # confidence in the identified business term (0.0-1.0)
    operation: float  # confidence in the extracted operation (0.0-1.0)
    conditions: float  # confidence in extracted conditions (0.0-1.0)
    scope: float  # confidence in extracted scope (0.0-1.0)
    affected_entities: float  # confidence in affected entities (0.0-1.0)


class ExtractionResponse(BaseModel):
    extracted_rules: list[dict[str, Any]]  # Single authoritative rules (not candidates)
    candidate_rules: list[dict[str, Any]]  # Alternative interpretations from glossary
    rules: list[dict[str, Any]]  # Single authoritative rule (first extracted)
    confidence: PerFieldConfidence  # Per-field confidence with semantic labels
    evidence: str = ""
    rule_count: dict[str, int]  # {"extracted": int, "candidates": int}


class SchemaValidationResponse(BaseModel):
    status: str  # PASS, PARTIAL, FAIL
    coverage: float  # 0.0-1.0
    mandatory_fields_valid: bool
    validation_errors: list[str] = Field(default_factory=list)
    schema_loaded: bool  # Whether schema was actually loaded for validation


class DuplicateDetectionResponse(BaseModel):
    status: str  # none, exact_duplicate, semantic_duplicate, extension, modification
    relationship: str
    similar_rules: list[dict[str, Any]] = Field(default_factory=list)


class ConflictDetectionResponse(BaseModel):
    status: str  # no_conflict, potential_conflict, direct_conflict
    relationship: str
    conflicting_rules: list[dict[str, Any]] = Field(default_factory=list)


class ClarificationResponse(BaseModel):
    clarification_id: str | None = None
    required: bool
    questions: list[str] = Field(default_factory=list)
    reason: str = ""
    ambiguity_reasons: list[str] = Field(default_factory=list)


class RoutingDecisionResponse(BaseModel):
    review_status: str  # pending_review, clarification_required, auto_approved, etc.
    priority: str = "normal"  # normal, high, urgent
    reason: str = ""


# Spec-compliant response per Section 5.2
class FeedbackAnalysisResponse(BaseModel):
    suggestion_id: str
    feedback_id: str
    status: str = "PENDING_REVIEW"
    classification: ClassificationResponse
    extraction: ExtractionResponse
    schema_validation: SchemaValidationResponse
    duplicate_detection: DuplicateDetectionResponse
    conflict_detection: ConflictDetectionResponse
    clarification_required: bool = False
    clarification: ClarificationResponse | None = None
    routing_decision: RoutingDecisionResponse


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
    confidence: float  # Confidence that rules are related
    matching_rule_id: str | None = None
    conflicting_rule_id: str | None = None
    details: dict[str, Any] = {}
