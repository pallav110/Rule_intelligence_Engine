from fastapi import FastAPI, HTTPException

from app.services.domain_pack_loader import DomainPackLoader, DomainPackNotFoundError
from app.services.classifier import MockClassifier
from app.services.feedback_preprocessor import FeedbackPreprocessor
from app.services.feedback_service import FeedbackService
from app.services.rule_extractor import MockRuleExtractor
from app.services.schema_validator import SchemaValidator
from app.services.feedback_preprocessor import FeedbackValidationError

from app.schemas.feedback import (
    FeedbackAnalysisRequest,
    FeedbackAnalysisResponse,
)

app = FastAPI(
    title="Rule Intelligence Engine",
    version="0.1.0"
)

loader = DomainPackLoader()

feedback_service = FeedbackService(
    preprocessor=FeedbackPreprocessor(),
    domain_loader=loader,
    classifier=MockClassifier(),
    extractor=MockRuleExtractor(),
    validator=SchemaValidator(),
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.get("/v1/domain-pack/{pack_id}")
def get_domain_pack(pack_id: str):
    try:
        return loader.load_domain_config(pack_id)
    except DomainPackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/domain-pack/{pack_id}/schema")
def get_domain_pack_schema(pack_id: str):
    try:
        return loader.load_schema(pack_id)
    except DomainPackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/domain-pack/{pack_id}/relationships")
def get_domain_pack_relationships(pack_id: str):
    try:
        return loader.load_relationships(pack_id)
    except DomainPackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc