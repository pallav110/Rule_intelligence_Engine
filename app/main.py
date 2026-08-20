from fastapi import Depends, FastAPI, HTTPException

from app.db.database import get_db
from app.db.models.rule import Rule
from app.schemas.feedback import (
    FeedbackAnalysisRequest,
    FeedbackAnalysisResponse,
    FeedbackBatchAnalysisRequest,
    FeedbackBatchAnalysisResponse,
    RuleComparisonRequest,
    RuleCompareRequest,
    RuleComparisonResponse,
)
from app.schemas.jobs import (
    JobCreateRequest,
    JobResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
)
from app.services.background_job_service import BackgroundJobService
from app.services.canonical_rule_service import CanonicalRuleService
from app.services.classifier import MockClassifier
from app.services.domain_pack_loader import (
    DomainPackLoader,
    DomainPackNotFoundError,
)
from app.services.feedback_preprocessor import (
    FeedbackPreprocessor,
    FeedbackValidationError,
)
from app.services.feedback_service import FeedbackService
from app.services.metrics_service import MetricsService
from app.services.rule_comparison_service import (
    MockRuleComparator,
    MockRuleComparisonService,
    MockRuleConflictService,
)
from app.services.rule_extractor import MockRuleExtractor
from app.services.schema_validator import SchemaValidator
from app.tasks import process_background_job


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

background_job_service = BackgroundJobService()


@app.post(
    "/v1/feedback/analyze",
    response_model=FeedbackAnalysisResponse,
)
def analyze_feedback(
    payload: FeedbackAnalysisRequest,
    db=Depends(get_db),
):
    try:
        return feedback_service.analyze(
            db=db,
            workspace_id=payload.workspace_id,
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
def analyze_feedback_batch(
    payload: FeedbackBatchAnalysisRequest,
    db=Depends(get_db),
):
    results = []

    for item in payload.items:
        try:
            results.append(
    feedback_service.analyze(
        db=db,
        workspace_id=item.workspace_id,
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
    return {
        "domain_packs": loader.list_available_packs()
    }


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
def check_duplicate(
    payload: RuleComparisonRequest,
    db=Depends(get_db),
):
    existing_rules = [
        {
            "rule_id": rule.rule_id,
            "rule_category": rule.rule_category,
            "operation": rule.operation,
            "conditions": rule.conditions,
            "affected_tables": rule.affected_tables,
            "affected_columns": rule.affected_columns,
        }
        for rule in db.query(Rule).filter(
            Rule.workspace_id == payload.workspace_id
        ).all()
    ]

    result = MockRuleComparisonService().check_duplicate(
        payload.rule,
        existing_rules,
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
def check_conflict(
    payload: RuleComparisonRequest,
    db=Depends(get_db),
):
    existing_rules = [
        {
            "rule_id": rule.rule_id,
            "rule_category": rule.rule_category,
            "operation": rule.operation,
            "conditions": rule.conditions,
            "affected_tables": rule.affected_tables,
            "affected_columns": rule.affected_columns,
        }
        for rule in db.query(Rule).filter(
            Rule.workspace_id == payload.workspace_id
        ).all()
    ]

    result = MockRuleConflictService().check_conflict(
        payload.rule,
        existing_rules,
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


@app.post(
    "/v1/workspaces",
    response_model=WorkspaceResponse,
)
def create_workspace(
    payload: WorkspaceCreateRequest,
    db=Depends(get_db),
):
    workspace = background_job_service.create_workspace(
        db=db,
        name=payload.name,
    )

    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        name=workspace.name,
    )


@app.post(
    "/v1/jobs",
    response_model=JobResponse,
)
def create_background_job(
    payload: JobCreateRequest,
    db=Depends(get_db),
):
    try:
        job = background_job_service.create_job(
            db=db,
            workspace_id=payload.workspace_id,
            job_type=payload.job_type,
            idempotency_key=payload.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    if job.status == "pending":
        process_background_job.delay(job.job_id)

    return JobResponse(
        job_id=job.job_id,
        workspace_id=job.workspace_id,
        job_type=job.job_type,
        status=job.status,
        idempotency_key=job.idempotency_key,
    )


@app.get(
    "/v1/jobs/{job_id}",
    response_model=JobResponse,
)
def get_background_job(
    job_id: str,
    db=Depends(get_db),
):
    job = background_job_service.get_job(
        db=db,
        job_id=job_id,
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}",
        )

    return JobResponse(
        job_id=job.job_id,
        workspace_id=job.workspace_id,
        job_type=job.job_type,
        status=job.status,
        idempotency_key=job.idempotency_key,
    )