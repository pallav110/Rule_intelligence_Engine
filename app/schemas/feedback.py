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
    model: str | None = None  # Which model produced this result (distilbert / baseline)
    model_version_id: str | None = None
    model_version: str | None = None
    registry_status: str | None = None  # active_ml / baseline_fallback / no_active_model


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
    model: str | None = None  # Which model produced this result (distilbert_token_classifier / baseline)
    model_version_id: str | None = None
    model_version: str | None = None
    registry_status: str | None = None  # active_ml / baseline_fallback / no_active_model


class SchemaValidationResponse(BaseModel):
    status: str  # PASS, PARTIAL, FAIL
    coverage: float  # 0.0-1.0
    mandatory_fields_valid: bool
    validation_errors: list[str] = Field(default_factory=list)
    schema_loaded: bool  # Whether schema was actually loaded for validation
    validated_fields: list[str] = Field(default_factory=list)  # Fields that passed validation
    invalid_fields: list[str] = Field(default_factory=list)  # Fields that failed validation
    validation_checks: dict[str, bool] = Field(default_factory=dict)  # Individual check results


class DuplicateDetectionResponse(BaseModel):
    status: str  # Spec §8.6: Exact Duplicate, Semantic Duplicate, Modification, Unique Rule
    relationship: str  # Spec §8.6 compliant relationship
    relationship_internal: str | None = None  # Internal classifier value (backward compat)
    is_duplicate: bool = False
    matching_rule_id: str | None = None
    confidence: float = 0.0
    retrieval_stage: int = 0
    similar_rules: list[dict[str, Any]] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ConflictDetectionResponse(BaseModel):
    status: str  # Spec §8.7: Conflict, Compatible, Extension, Modification, No Conflict
    relationship: str
    has_conflict: bool = False
    conflict_type: str | None = None  # Spec §8.7 compliant conflict type
    conflict_type_internal: str | None = None  # Internal classifier value (backward compat)
    confidence: float = 0.0
    retrieval_stage: int = 0
    conflicting_rule_ids: list[str] = Field(default_factory=list)
    related_compatible_rule_ids: list[str] = Field(default_factory=list)
    conflict_details: list[dict[str, Any]] = Field(default_factory=list)  # Only actual conflicts with details
    details: dict[str, Any] = Field(default_factory=dict)



class ClarificationResponse(BaseModel):
    clarification_id: str | None = None
    required: bool
    questions: list[str] = Field(default_factory=list)
    reason: str = ""
    ambiguity_reasons: list[str] = Field(default_factory=list)


class RoutingDecisionResponse(BaseModel):
    review_status: str  # pending_review, clarification_required, auto_approved, etc.
    priority: str = "normal"  # normal, high, urgent, auto_approve
    reason: str = ""
    suggested_reviewer_type: str | None = None  # automated, domain_expert, manager, senior_reviewer, qa
    suggested_reviewer_id: str | None = None
    auto_approval_eligible: bool = False
    reasoning: dict[str, Any] = Field(default_factory=dict)  # confidence/impact/complexity/risk scores + factors


class PreprocessingResponse(BaseModel):
    original_text: str
    processed_text: str
    preprocessing_steps: list[dict[str, Any]]
    detected_keywords: list[str]
    detected_schema_refs: list[str]
    language_normalized: bool


# Spec-compliant response per Section 5.2
class FeedbackAnalysisResponse(BaseModel):
    suggestion_id: str
    feedback_id: str
    status: str = "PENDING_REVIEW"
    preprocessing: PreprocessingResponse
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
