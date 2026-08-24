from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
import redis
import csv
import io
from uuid import uuid4
from fastapi import File, UploadFile
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
from app.schemas.suggestion import (
    SuggestionCreateRequest,
    SuggestionResponse,
    SuggestionApproveRequest,
    SuggestionRejectRequest,
    ClarificationCreateRequest,
    ClarificationResponse,
    ClarificationRespondRequest,
    ReviewCreateRequest,
    ReviewResponse,
    ReviewCompleteRequest,
    ReviewAssignRequest,
)
from app.services.background_job_service import BackgroundJobService
from app.services.canonical_rule_service import CanonicalRuleService
from app.services.classifier import RealClassifier
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
    RealRuleComparisonService as RuleComparisonService,
    RealRuleConflictService as RuleConflictService,
)
from app.services.rule_extractor import RealRuleExtractor
from app.services.schema_validator import SchemaValidator
from app.services.feedback_service import FeedbackService
from app.services.suggestion_service import SuggestionService
from app.services.clarification_service import ClarificationService
from app.services.review_routing_service import ReviewRoutingService
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
    EvaluationResponse,
)
from app.services.evaluation_service import EvaluationService
from app.schemas.workspace import (
    WorkspaceCreateRequest,
    WorkspaceResponse,
)
from app.services.workspace_service import WorkspaceService

app = FastAPI(title="Rule Intelligence Engine API", version="1.0.0")

# Dependency injection setup
def get_db():
    from sqlalchemy.orm import Session
    from app.db.database import SessionLocal
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

# Create service instances (for now, instantiated per-request for simplicity)
def get_suggestion_service():
    return SuggestionService()

def get_clarification_service():
    return ClarificationService()

def get_review_routing_service():
    return ReviewRoutingService()

def get_evaluation_service():
    return EvaluationService()

def get_workspace_service():
    return WorkspaceService()

# Health and readiness checks
@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "healthy"}

@app.get("/ready", include_in_schema=False)
def readiness_check():
    return {"status": "ready"}

# --- Feedback Analysis Endpoints ---

@app.post(
    "/v1/feedback/analyze",
    response_model=FeedbackAnalysisResponse,
)
def analyze_feedback(
    payload: FeedbackAnalysisRequest,
    db=Depends(get_db),
    classifier: RealClassifier = Depends(),
    suggestion_service: SuggestionService = Depends(),
    clarification_service: ClarificationService = Depends(),
):
    """Analyze feedback text using ML baseline."""
    # Classify the feedback
    classification_result = classifier.classify(
        feedback=payload.feedback_text,
        domain_context=payload.schema_context,
    )

    # Extract rules
    # TODO: Fix this - suggestion_service[0] is wrong
    extracted_rules = suggestion_service.extract(
        feedback=payload.feedback_text,
        classification=classification_result,
        schema_context=payload.schema_context,
    )

    # Check for duplicates and conflicts
    # (would use duplicate/conflict services)

    # Create suggestion if actionable
    if classification_result.is_actionable:
        suggestion = suggestion_service.create_suggestion(
            db=db,
            workspace_id=payload.workspace_id or "default",
            feedback_id=payload.feedback_id,
            suggested_rule={"business_term": extracted_rules.rules[0].business_term if extracted_rules.rules else None,
                          "operation": extracted_rules.rules[0].operation if extracted_rules.rules else None},
            confidence=classification_result.confidence,
        )
    else:
        suggestion = None

    # Create clarification if needed
    if classification_result.requires_clarification:
        clarification = clarification_service.create_clarification(
            db=db,
            feedback_id=payload.feedback_id,
            classification=classification_result,
            extraction=extracted_rules,
        )
    else:
        clarification = None

    return FeedbackAnalysisResponse(
        feedback_id=payload.feedback_id,
        feedback_type=classification_result.feedback_type,
        rule_category=classification_result.rule_category,
        is_actionable=classification_result.is_actionable,
        requires_clarification=classification_result.requires_clarification,
        confidence=classification_result.confidence,
        extracted_rules=extracted_rules,
        suggestion=suggestion,
        clarification=clarification,
    )


# --- Suggestion APIs ---

@app.post("/v1/suggestions", response_model=SuggestionResponse)
def create_suggestion_route(
    payload: SuggestionCreateRequest,
    db=Depends(get_db),
    suggestion_service: SuggestionService = Depends(),
):
    suggestion = suggestion_service.create_suggestion(
        db=db,
        workspace_id=payload.workspace_id,
        feedback_id=payload.feedback_id,
        suggested_rule=payload.suggested_rule,
        confidence=payload.confidence,
    )
    return SuggestionResponse(
        suggestion_id=suggestion.suggestion_id,
        workspace_id=suggestion.workspace_id,
        feedback_id=suggestion.feedback_id,
        suggested_rule=suggestion.suggested_rule,
        status=suggestion.status,
        confidence_score=suggestion.confidence_score,
        created_at=suggestion.created_at,
        reviewed_by=suggestion.reviewed_by,
        reviewed_at=suggestion.reviewed_at,
    )


@app.get("/v1/suggestions/{suggestion_id}", response_model=SuggestionResponse)
def get_suggestion_route(
    suggestion_id: str,
    db=Depends(get_db),
    suggestion_service: SuggestionService = Depends(),
):
    suggestion = suggestion_service.get_suggestion(db=db, suggestion_id=suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail=f"Suggestion not found: {suggestion_id}")
    return SuggestionResponse(
        suggestion_id=suggestion.suggestion_id,
        workspace_id=suggestion.workspace_id,
        feedback_id=suggestion.feedback_id,
        suggested_rule=suggestion.suggested_rule,
        status=suggestion.status,
        confidence_score=suggestion.confidence_score,
        created_at=suggestion.created_at,
        reviewed_by=suggestion.reviewed_by,
        reviewed_at=suggestion.reviewed_at,
    )


@app.post("/v1/suggestions/{suggestion_id}/approve", response_model=SuggestionResponse)
def approve_suggestion_route(
    suggestion_id: str,
    payload: SuggestionApproveRequest,
    db=Depends(get_db),
    suggestion_service: SuggestionService = Depends(),
):
    suggestion = suggestion_service.approve_suggestion(
        db=db,
        suggestion_id=suggestion_id,
        reviewer_id=payload.reviewer_id,
    )
    return SuggestionResponse(
        suggestion_id=suggestion.suggestion_id,
        workspace_id=suggestion.workspace_id,
        feedback_id=suggestion.feedback_id,
        suggested_rule=suggestion.suggested_rule,
        status=suggestion.status,
        confidence_score=suggestion.confidence_score,
        created_at=suggestion.created_at,
        reviewed_by=suggestion.reviewed_by,
        reviewed_at=suggestion.reviewed_at,
    )


@app.post("/v1/suggestions/{suggestion_id}/reject", response_model=SuggestionResponse)
def reject_suggestion_route(
    suggestion_id: str,
    payload: SuggestionRejectRequest,
    db=Depends(get_db),
    suggestion_service: SuggestionService = Depends(),
):
    suggestion = suggestion_service.reject_suggestion(
        db=db,
        suggestion_id=suggestion_id,
        reviewer_id=payload.reviewer_id,
        rejection_reason=payload.rejection_reason,
    )
    return SuggestionResponse(
        suggestion_id=suggestion.suggestion_id,
        workspace_id=suggestion.workspace_id,
        feedback_id=suggestion.feedback_id,
        suggested_rule=suggestion.suggested_rule,
        status=suggestion.status,
        confidence_score=suggestion.confidence_score,
        created_at=suggestion.created_at,
        reviewed_by=suggestion.reviewed_by,
        reviewed_at=suggestion.reviewed_at,
    )


@app.get("/v1/suggestions", response_model=List[SuggestionResponse])
def list_suggestions_route(
    db=Depends(get_db),
    suggestion_service: SuggestionService = Depends(),
    workspace_id: Optional[str] = None,
    status: Optional[str] = None,
):
    suggestions = suggestion_service.list_suggestions(
        db=db,
        workspace_id=workspace_id,
        status=status,
    )
    return [
        SuggestionResponse(
            suggestion_id=s.suggestion_id,
            workspace_id=s.workspace_id,
            feedback_id=s.feedback_id,
            suggested_rule=s.suggested_rule,
            status=s.status,
            confidence_score=s.confidence_score,
            created_at=s.created_at,
            reviewed_by=s.reviewed_by,
            reviewed_at=s.reviewed_at,
        )
        for s in suggestions
    ]


# --- Clarification APIs ---

@app.post("/v1/clarifications", response_model=ClarificationResponse)
def create_clarification_route(
    payload: ClarificationCreateRequest,
    db=Depends(get_db),
    clarification_service: ClarificationService = Depends(),
):
    clarification = clarification_service.create_clarification(
        db=db,
        feedback_id=payload.feedback_id,
        classification=payload.classification,
        extraction=payload.extraction,
    )
    if clarification is None:
        # No clarification needed
        from app.schemas.suggestion import ClarificationResponse
        return ClarificationResponse(
            clarification_id="",
            feedback_id=payload.feedback_id,
            questions=[],
            reason="",
            status="completed",
            response="",
            created_at=datetime.utcnow(),
            responded_at=datetime.utcnow(),
        )
    return ClarificationResponse(
        clarification_id=clarification.clarification_id,
        feedback_id=clarification.feedback_id,
        questions=clarification.questions,
        reason=clarification.reason,
        status=clarification.status,
        response=clarification.response,
        created_at=clarification.created_at,
        responded_at=clarification.responded_at,
    )


@app.get("/v1/clarifications/{clarification_id}", response_model=ClarificationResponse)
def get_clarification_route(
    clarification_id: str,
    db=Depends(get_db),
    clarification_service: ClarificationService = Depends(),
):
    clarification = clarification_service.get_clarification(db=db, clarification_id=clarification_id)
    if clarification is None:
        raise HTTPException(status_code=404, detail=f"Clarification not found: {clarification_id}")
    return ClarificationResponse(
        clarification_id=clarification.clarification_id,
        feedback_id=clarification.feedback_id,
        questions=clarification.questions,
        reason=clarification.reason,
        status=clarification.status,
        response=clarification.response,
        created_at=clarification.created_at,
        responded_at=clarification.responded_at,
    )


@app.post("/v1/clarifications/{clarification_id}/respond", response_model=ClarificationResponse)
def respond_to_clarification_route(
    clarification_id: str,
    payload: ClarificationRespondRequest,
    db=Depends(get_db),
    clarification_service: ClarificationService = Depends(),
):
    clarification = clarification_service.respond_to_clarification(
        db=db,
        clarification_id=clarification_id,
        response=payload.response,
    )
    return ClarificationResponse(
        clarification_id=clarification.clarification_id,
        feedback_id=clarification.feedback_id,
        questions=clarification.questions,
        reason=clarification.reason,
        status=clarification.status,
        response=clarification.response,
        created_at=clarification.created_at,
        responded_at=clarification.responded_at,
    )


# --- Review APIs ---

@app.post("/v1/reviews", response_model=ReviewResponse)
def create_review_route(
    payload: ReviewCreateRequest,
    db=Depends(get_db),
    review_routing_service: ReviewRoutingService = Depends(),
):
    review = review_routing_service.create_review(
        db=db,
        suggestion_id=payload.suggestion_id,
        reviewer_id=payload.reviewer_id,
        priority=payload.priority,
    )
    return ReviewResponse(
        review_id=review.review_id,
        suggestion_id=review.suggestion_id,
        reviewer_id=review.reviewer_id,
        status=review.status,
        priority=review.priority,
        assigned_at=review.assigned_at,
        completed_at=review.completed_at,
    )


@app.get("/v1/reviews/{review_id}", response_model=ReviewResponse)
def get_review_route(
    review_id: str,
    db=Depends(get_db),
    review_routing_service: ReviewRoutingService = Depends(),
):
    review = review_routing_service.get_review(db=db, review_id=review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Review not found: {review_id}")
    return ReviewResponse(
        review_id=review.review_id,
        suggestion_id=review.suggestion_id,
        reviewer_id=review.reviewer_id,
        status=review.status,
        priority=review.priority,
        assigned_at=review.assigned_at,
        completed_at=review.completed_at,
    )


@app.post("/v1/reviews/{review_id}/complete", response_model=ReviewResponse)
def complete_review_route(
    review_id: str,
    payload: ReviewCompleteRequest,
    db=Depends(get_db),
    review_routing_service: ReviewRoutingService = Depends(),
):
    review = review_routing_service.complete_review(
        db=db,
        review_id=review_id,
        decision=payload.decision,
        notes=payload.notes,
    )
    return ReviewResponse(
        review_id=review.review_id,
        suggestion_id=review.suggestion_id,
        reviewer_id=review.reviewer_id,
        status=review.status,
        priority=review.priority,
        decision=review.decision,
        notes=review.notes,
        assigned_at=review.assigned_at,
        completed_at=review.completed_at,
    )


@app.post("/v1/reviews/{review_id}/assign", response_model=ReviewResponse)
def assign_reviewer_route(
    review_id: str,
    payload: ReviewAssignRequest,
    db=Depends(get_db),
    review_routing_service: ReviewRoutingService = Depends(),
):
    review = review_routing_service.assign_reviewer(
        db=db,
        review_id=review_id,
        reviewer_id=payload.reviewer_id,
    )
    return ReviewResponse(
        review_id=review.review_id,
        suggestion_id=review.suggestion_id,
        reviewer_id=review.reviewer_id,
        status=review.status,
        priority=review.priority,
        assigned_at=review.assigned_at,
        completed_at=review.completed_at,
    )


# --- Evaluation APIs ---

@app.post("/v1/evaluations", response_model=EvaluationResponse)
def create_evaluation_route(
    payload: EvaluationCreateRequest,
    db=Depends(get_db),
    evaluation_service: EvaluationService = Depends(),
):
    evaluation = evaluation_service.create_evaluation(
        db=db,
        workspace_id=payload.workspace_id,
        name=payload.name,
        description=payload.description,
        ground_truth_data=payload.ground_truth_data,
    )
    return EvaluationResponse(
        evaluation_id=evaluation.evaluation_id,
        workspace_id=evaluation.workspace_id,
        name=evaluation.name,
        description=evaluation.description,
        status=evaluation.status,
        created_at=evaluation.created_at,
    )


@app.get("/v1/evaluations/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation_route(
    evaluation_id: str,
    db=Depends(get_db),
    evaluation_service: EvaluationService = Depends(),
):
    evaluation = evaluation_service.get_evaluation(db=db, evaluation_id=evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail=f"Evaluation not found: {evaluation_id}")
    return EvaluationResponse(
        evaluation_id=evaluation.evaluation_id,
        workspace_id=evaluation.workspace_id,
        name=evaluation.name,
        description=evaluation.description,
        status=evaluation.status,
        created_at=evaluation.created_at,
    )


# --- Workspace APIs ---

@app.post("/v1/workspaces", response_model=WorkspaceResponse)
def create_workspace_route(
    payload: WorkspaceCreateRequest,
    db=Depends(get_db),
    workspace_service: WorkspaceService = Depends(),
):
    workspace = workspace_service.create_workspace(
        db=db,
        name=payload.name,
        description=payload.description,
    )
    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        name=workspace.name,
        description=workspace.description,
        status=workspace.status,
        created_at=workspace.created_at,
    )


@app.get("/v1/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace_route(
    workspace_id: str,
    db=Depends(get_db),
    workspace_service: WorkspaceService = Depends(),
):
    workspace = workspace_service.get_workspace(db=db, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail=f"Workspace not found: {workspace_id}")
    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        name=workspace.name,
        description=workspace.description,
        status=workspace.status,
        created_at=workspace.created_at,
    )

# List all routes for debugging
@app.on_event("startup")
def list_routes():
    import inspect
    routes = [(route.path, route.methods) for route in app.routes if hasattr(route, 'methods')]
    print(f"Registered {len(routes)} API routes")