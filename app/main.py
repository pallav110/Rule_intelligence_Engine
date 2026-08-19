from fastapi import FastAPI, HTTPException

from app.services.domain_pack_loader import (
    DomainPackLoader,
    DomainPackNotFoundError,
)
from app.services.classifier import MockClassifier
from app.services.feedback_preprocessor import (
    FeedbackPreprocessor,
    FeedbackValidationError,
)
from app.services.feedback_service import FeedbackService
from app.services.rule_extractor import MockRuleExtractor
from app.services.schema_validator import SchemaValidator
from app.services.canonical_rule_service import CanonicalRuleService
from app.services.rule_comparison_service import (
    MockRuleComparator,
    MockRuleComparisonService,
    MockRuleConflictService,
)
from app.services.metrics_service import MetricsService

from app.schemas.feedback import (
    FeedbackAnalysisRequest,
    FeedbackAnalysisResponse,
    FeedbackBatchAnalysisRequest,
    FeedbackBatchAnalysisResponse,
    RuleComparisonRequest,
    RuleCompareRequest,
    RuleComparisonResponse,
)


app = FastAPI(
    title="Rule Intelligence Engine",
    version="0.1.0",
)

loader = DomainPackLoader()

feedback_service = FeedbackService(
    preprocessor=FeedbackPreprocessor(),
    domain_loader=loader,
    classifier=MockClassifier(),
    extractor=MockRuleExtractor(),
    validator=SchemaValidator(),
    canonical_rule_service=CanonicalRuleService(),
)


@app.post(
    "/v1/feedback/analyze",
    response_model=FeedbackAnalysisResponse,
)
def analyze_feedback(payload: FeedbackAnalysisRequest):
    try:
        return feedback_service.analyze(
            feedback=payload.feedback,
            domain=payload.domain,
        )
    except FeedbackValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.post(
    "/v1/feedback/batch-analyze",
    response_model=FeedbackBatchAnalysisResponse,
)
def analyze_feedback_batch(payload: FeedbackBatchAnalysisRequest):
    results = []

    for item in payload.items:
        try:
            results.append(
                feedback_service.analyze(
                    feedback=item.feedback,
                    domain=item.domain,
                )
            )
        except FeedbackValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

    return FeedbackBatchAnalysisResponse(
        results=results,
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/v1/domain-packs")
def list_domain_packs():
    return {"domain_packs": loader.list_available_packs()}


@app.get("/v1/taxonomy/{pack_id}")
def get_taxonomy(pack_id: str):
    try:
        return loader.load_taxonomy(pack_id)
    except DomainPackNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@app.get("/v1/domain-pack/{pack_id}")
def get_domain_pack(pack_id: str):
    try:
        return loader.load_domain_config(pack_id)
    except DomainPackNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@app.get("/v1/domain-pack/{pack_id}/schema")
def get_domain_pack_schema(pack_id: str):
    try:
        return loader.load_schema(pack_id)
    except DomainPackNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@app.get("/v1/domain-pack/{pack_id}/relationships")
def get_domain_pack_relationships(pack_id: str):
    try:
        return loader.load_relationships(pack_id)
    except DomainPackNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@app.post(
    "/v1/rules/check-duplicate",
    response_model=RuleComparisonResponse,
)
def check_duplicate(payload: RuleComparisonRequest):
    result = MockRuleComparisonService().check_duplicate(
        payload.rule,
        payload.existing_rules,
    )

    return RuleComparisonResponse(
        relationship=result.relationship,
        confidence=result.confidence,
        matching_rule_id=result.matching_rule_id,
    )


@app.post(
    "/v1/rules/check-conflict",
    response_model=RuleComparisonResponse,
)
def check_conflict(payload: RuleComparisonRequest):
    result = MockRuleConflictService().check_conflict(
        payload.rule,
        payload.existing_rules,
    )

    return RuleComparisonResponse(
        relationship=result.relationship,
        confidence=result.confidence,
        conflicting_rule_id=result.conflicting_rule_id,
    )


@app.post(
    "/v1/rules/compare",
    response_model=RuleComparisonResponse,
)
def compare_rules(payload: RuleCompareRequest):
    result = MockRuleComparator().compare(
        payload.rule_a,
        payload.rule_b,
    )

    return RuleComparisonResponse(
        relationship=result.relationship,
        confidence=result.confidence,
        details=result.details,
    )


@app.get("/v1/models/metrics")
def get_model_metrics():
    return MetricsService().get_metrics()