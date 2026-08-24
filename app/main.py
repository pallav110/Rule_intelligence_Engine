from fastapi import Depends, FastAPI, HTTPException, status
import redis
from sqlalchemy import text
import os
from app.db.database import engine
from app.db.database import get_db
from app.db.models.rule import Rule
from app.db.models.evaluation_run import EvaluationRun
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
from app.schemas.model_version import (
    ModelVersionCreateRequest,
    ModelVersionResponse,
)
from app.services.model_version_service import ModelVersionService
from app.schemas.dataset import (
    DatasetVersionCreateRequest,
    DatasetVersionResponse,
    DatasetVersionListResponse,
)
from app.services.dataset_version_service import DatasetVersionService
from app.schemas.evaluation import (
    EvaluationCreateRequest,
    EvaluationMetricResponse,
    EvaluationResponse,
)
from app.services.evaluation_service import EvaluationService

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
model_version_service = ModelVersionService()
dataset_version_service = DatasetVersionService()
evaluation_service = EvaluationService(
    classifier=MockClassifier(),
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/ready")
def readiness_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        redis_url = os.getenv(
            "REDIS_URL",
            "redis://localhost:6379/0",
        )

        redis_client = redis.from_url(redis_url)
        redis_client.ping()
        redis_client.close()

        return {"status": "ready"}

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Readiness check failed: {exc}",
        ) from exc

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

@app.post(
    "/v1/datasets",
    response_model=DatasetVersionResponse,
)
def create_dataset_version(
    payload: DatasetVersionCreateRequest,
    db=Depends(get_db),
):
    try:
        dataset_version = dataset_version_service.create(
            db=db,
            dataset_name=payload.dataset_name,
            version=payload.version,
            domain_pack_version=payload.domain_pack_version,
            annotation_version=payload.annotation_version,
            source=payload.source,
            path=payload.path,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return DatasetVersionResponse(
        dataset_version_id=dataset_version.dataset_version_id,
        dataset_name=dataset_version.dataset_name,
        version=dataset_version.version,
        domain_pack_version=dataset_version.domain_pack_version,
        annotation_version=dataset_version.annotation_version,
        source=dataset_version.source,
        path=dataset_version.path,
        status=dataset_version.status,
    )

@app.get(
    "/v1/datasets/{dataset_version_id}",
    response_model=DatasetVersionResponse,
)
def get_dataset_version(
    dataset_version_id: str,
    db=Depends(get_db),
):
    dataset_version = dataset_version_service.get(
        db=db,
        dataset_version_id=dataset_version_id,
    )

    if dataset_version is None:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset version not found: {dataset_version_id}",
        )

    return DatasetVersionResponse(
        dataset_version_id=dataset_version.dataset_version_id,
        dataset_name=dataset_version.dataset_name,
        version=dataset_version.version,
        domain_pack_version=dataset_version.domain_pack_version,
        annotation_version=dataset_version.annotation_version,
        source=dataset_version.source,
        path=dataset_version.path,
        status=dataset_version.status,
    )

@app.get(
    "/v1/datasets",
    response_model=DatasetVersionListResponse,
)
def list_dataset_versions(
    dataset_name: str | None = None,
    db=Depends(get_db),
):
    dataset_versions = dataset_version_service.list(
        db=db,
        dataset_name=dataset_name,
    )

    return DatasetVersionListResponse(
        datasets=[
            DatasetVersionResponse(
                dataset_version_id=dataset.dataset_version_id,
                dataset_name=dataset.dataset_name,
                version=dataset.version,
                domain_pack_version=dataset.domain_pack_version,
                annotation_version=dataset.annotation_version,
                source=dataset.source,
                path=dataset.path,
                status=dataset.status,
            )
            for dataset in dataset_versions
        ],
    )

@app.post(
    "/v1/evaluations",
    response_model=EvaluationResponse,
)
def create_evaluation(
    payload: EvaluationCreateRequest,
    db=Depends(get_db),
):
    try:
        evaluation_run = evaluation_service.evaluate(
            db=db,
            model_version_id=payload.model_version_id,
            dataset_version_id=payload.dataset_version_id,
        )
    except ValueError as exc:
        message = str(exc)

        if "not found" in message.lower():
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=message,
        ) from exc

    metrics = MetricsService().get_metrics(
        db=db,
        evaluation_run_id=evaluation_run.evaluation_run_id,
    )

    return EvaluationResponse(
        evaluation_run_id=evaluation_run.evaluation_run_id,
        model_version_id=evaluation_run.model_version_id,
        dataset_version_id=evaluation_run.dataset_version_id,
        status=evaluation_run.status,
        started_at=evaluation_run.started_at,
        completed_at=evaluation_run.completed_at,
        metrics=[
            EvaluationMetricResponse(**metric)
            for metric in metrics["metrics"]
        ],
    )


@app.get(
    "/v1/evaluations/{evaluation_run_id}",
    response_model=EvaluationResponse,
)
def get_evaluation(
    evaluation_run_id: str,
    db=Depends(get_db),
):
    try:
        result = MetricsService().get_metrics(
            db=db,
            evaluation_run_id=evaluation_run_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    evaluation_run = db.get(
        EvaluationRun,
        evaluation_run_id,
    )

    return EvaluationResponse(
        evaluation_run_id=evaluation_run.evaluation_run_id,
        model_version_id=evaluation_run.model_version_id,
        dataset_version_id=evaluation_run.dataset_version_id,
        status=evaluation_run.status,
        started_at=evaluation_run.started_at,
        completed_at=evaluation_run.completed_at,
        metrics=[
            EvaluationMetricResponse(**metric)
            for metric in result["metrics"]
        ],
    )


@app.get("/v1/models/metrics")
def get_model_metrics():
    return MetricsService().get_metrics()

@app.post(
    "/v1/models",
    response_model=ModelVersionResponse,
)
def create_model_version(
    payload: ModelVersionCreateRequest,
    db=Depends(get_db),
):
    try:
        model_version = model_version_service.create(
            db=db,
            model_name=payload.model_name,
            version=payload.version,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return ModelVersionResponse(
        model_version_id=model_version.model_version_id,
        model_name=model_version.model_name,
        version=model_version.version,
        status=model_version.status,
        artifact_path=model_version.artifact_path,
    )


@app.get(
    "/v1/models/{model_version_id}",
    response_model=ModelVersionResponse,
)
def get_model_version(
    model_version_id: str,
    db=Depends(get_db),
):
    model_version = model_version_service.get(
        db=db,
        model_version_id=model_version_id,
    )

    if model_version is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model version not found: {model_version_id}",
        )

    return ModelVersionResponse(
        model_version_id=model_version.model_version_id,
        model_name=model_version.model_name,
        version=model_version.version,
        status=model_version.status,
        artifact_path=model_version.artifact_path,
    )


@app.post(
    "/v1/models/{model_version_id}/approve",
    response_model=ModelVersionResponse,
)
def approve_model_version(
    model_version_id: str,
    db=Depends(get_db),
):
    try:
        model_version = model_version_service.approve(
            db=db,
            model_version_id=model_version_id,
        )
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return ModelVersionResponse(
        model_version_id=model_version.model_version_id,
        model_name=model_version.model_name,
        version=model_version.version,
        status=model_version.status,
        artifact_path=model_version.artifact_path,
    )


@app.post(
    "/v1/models/{model_version_id}/activate",
    response_model=ModelVersionResponse,
)
def activate_model_version(
    model_version_id: str,
    db=Depends(get_db),
):
    try:
        model_version = model_version_service.activate(
            db=db,
            model_version_id=model_version_id,
        )
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return ModelVersionResponse(
        model_version_id=model_version.model_version_id,
        model_name=model_version.model_name,
        version=model_version.version,
        status=model_version.status,
        artifact_path=model_version.artifact_path,
    )

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