from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional
import redis
import csv
import io
from uuid import uuid4
from fastapi import File, UploadFile
from sqlalchemy import text
import os
from pathlib import Path
from datetime import datetime
from app.db.database import engine
from app.db.database import get_db
from app.db.models.rule import Rule
from app.db.models.evaluation_run import EvaluationRun
from app.db.models.feedback import Feedback
from app.db.models.analysis_run import AnalysisRun
from app.db.models.rule_suggestion import RuleSuggestion
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
from app.services.classifier import RealClassifier
from app.services.domain_pack_loader import (
    DomainPackLoader,
    DomainPackNotFoundError,
)
from app.services.feedback_service import FeedbackService
from app.services.rule_extractor import RealRuleExtractor
from app.services.suggestion_service import SuggestionService
from app.services.clarification_service import ClarificationService
from app.services.review_routing_service import ReviewRoutingService
from app.services.conflict_detection_service import RealConflictDetectionService
from app.services.duplicate_detection_service import RealDuplicateDetectionService
from app.services.entity_extractor import RealEntityExtractor

app = FastAPI(title="Rule Intelligence Engine API", version="1.0.0")

# Mount static files (custom UI dashboard)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(static_dir)), name="static")

# Root endpoint to serve custom UI
@app.get("/", include_in_schema=False)
async def root():
    """Serve custom production dashboard."""
    ui_file = static_dir / "dashboard.html"
    if ui_file.exists():
        return FileResponse(str(ui_file), media_type="text/html")
    return {"message": "Rule Intelligence Engine API - Visit /docs for Swagger UI"}

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
):
    """
    Analyze feedback text through complete Week 3 pipeline:
    1. Classify feedback
    2. Extract rules with NER from domain pack
    3. Detect duplicates against existing rules
    4. Detect conflicts against existing rules
    5. Generate clarification if needed
    6. Route for review (auto-approve if eligible)
    """
    from uuid import uuid4
    from datetime import datetime

    # Step 1: Create Feedback record
    feedback_id = payload.feedback_id or str(uuid4())
    feedback = Feedback(
        feedback_id=feedback_id,
        workspace_id=payload.workspace_id,
        content=payload.feedback_text,
        created_at=datetime.utcnow(),
    )
    db.add(feedback)
    db.flush()

    # Step 2: Create AnalysisRun record
    analysis_run_id = str(uuid4())
    analysis_run = AnalysisRun(
        analysis_run_id=analysis_run_id,
        feedback_id=feedback_id,
        workspace_id=payload.workspace_id,
        processing_mode="single",
        status="processing",
        started_at=datetime.utcnow(),
    )
    db.add(analysis_run)
    db.flush()

    # Step 3: Get domain pack for NER extraction
    domain_pack_loader = DomainPackLoader()
    domain_pack_id = payload.schema_context.get("domain_pack_id", "customer_support")
    try:
        domain_pack = domain_pack_loader.load(domain_pack_id)
    except DomainPackNotFoundError:
        domain_pack = {}

    # Step 4: Classification + Extraction with NER
    suggestion_service = SuggestionService()
    extract_result = suggestion_service.extract(
        feedback=payload.feedback_text,
        domain_context=payload.schema_context,
    )

    classification_result_dict = extract_result["classification"]
    extracted_rules = extract_result["extraction"]

    # Step 5: Entity extraction using domain pack
    from app.services.entity_extractor import RealEntityExtractor

    entity_extractor = RealEntityExtractor(domain_pack)
    entity_extraction = entity_extractor.extract_with_context(
        payload.feedback_text, payload.schema_context
    )

    # Enhance extracted rules with entity information
    for rule in extracted_rules:
        if "affected_entities" not in rule or not rule.get("affected_entities"):
            rule["affected_entities"] = entity_extraction.get("affected_entities", {})

    # Step 6: Duplicate Detection
    from app.services.duplicate_detection_service import RealDuplicateDetectionService

    duplicate_service = RealDuplicateDetectionService()
    primary_rule = extracted_rules[0] if extracted_rules else {}
    duplicate_check = duplicate_service.check_duplicate(
        suggested_rule=primary_rule,
        workspace_id=payload.workspace_id,
        domain_id=domain_pack_id,
        db=db,
    )

    # Step 7: Conflict Detection
    from app.services.conflict_detection_service import RealConflictDetectionService

    conflict_service = RealConflictDetectionService()
    conflict_check = conflict_service.check_conflict(
        suggested_rule=primary_rule,
        workspace_id=payload.workspace_id,
        domain_id=domain_pack_id,
        db=db,
    )

    # Step 8: Clarification Generation
    from app.services.clarification_service import RealClarificationService

    clarification_service = RealClarificationService()
    clarification_result = clarification_service.generate_clarification(
        feedback_id=feedback_id,
        feedback_text=payload.feedback_text,
        classification=classification_result_dict,
        extraction=extract_result,
        workspace_id=payload.workspace_id,
        db=db,
    )

    # Step 9: Review Routing
    from app.services.review_routing_service import RealReviewRoutingService

    routing_service = RealReviewRoutingService()
    suggestion_id = str(uuid4())
    routing_decision = routing_service.route_suggestion(
        suggestion_id=suggestion_id,
        suggestion=primary_rule,
        classification=classification_result_dict,
        extraction=extract_result,
        conflict_check=conflict_check,
        duplicate_check=duplicate_check,
        workspace_id=payload.workspace_id,
        domain_id=domain_pack_id,
        db=db,
    )

    # Step 10: Create RuleSuggestion record with all intelligence
    rule_suggestion = RuleSuggestion(
        suggestion_id=suggestion_id,
        workspace_id=payload.workspace_id,
        feedback_id=feedback_id,
        analysis_run_id=analysis_run_id,
        feedback_type=classification_result_dict.get("feedback_type"),
        rule_category=classification_result_dict.get("rule_category"),
        classification_result=classification_result_dict,
        extraction_result="completed",
        clarification_required=clarification_result.get("created", False),
        review_status=routing_decision.get("review_status", "pending_review"),
        suggested_rule=primary_rule,
        created_at=datetime.utcnow(),
    )
    db.add(rule_suggestion)

    # Step 11: Mark AnalysisRun as completed
    analysis_run.status = "completed"
    analysis_run.completed_at = datetime.utcnow()

    db.commit()

    # Step 12: Build comprehensive response
    return FeedbackAnalysisResponse(
        feedback_id=feedback_id,
        feedback_type=classification_result_dict["feedback_type"],
        rule_category=classification_result_dict["rule_category"],
        is_actionable=classification_result_dict["is_actionable"],
        requires_clarification=clarification_result.get("created", False),
        confidence=classification_result_dict["confidence"],
        extracted_rules=extracted_rules,
        suggestion={
            "suggestion_id": suggestion_id,
            "analysis_run_id": analysis_run_id,
            "suggested_rule": primary_rule,
            "extracted_entities": entity_extraction,
            "duplicate_check": duplicate_check,
            "conflict_check": conflict_check,
            "routing_decision": routing_decision,
            "review_status": routing_decision.get("review_status"),
            "priority": routing_decision.get("priority"),
            "auto_approved": routing_decision.get("review_status") == "auto_approved",
        },
        clarification={
            "clarification_id": clarification_result.get("clarification_id"),
            "required": clarification_result.get("created", False),
            "questions": clarification_result.get("questions", []),
            "reason": clarification_result.get("reason"),
            "ambiguity_reasons": clarification_result.get("details", {}).get("ambiguity_reasons", []),
        } if clarification_result.get("created") else None,
    )


# --- Suggestion APIs ---

@app.post("/v1/suggestions", response_model=SuggestionResponse)
def create_suggestion_route(
    payload: SuggestionCreateRequest,
    db=Depends(get_db),
):
    # For now, return mock response without DB persistence
    # TODO: Create analysis_run first, then persist suggestion with proper foreign key
    from datetime import datetime
    from uuid import uuid4

    suggestion_id = str(uuid4())
    return SuggestionResponse(
        suggestion_id=suggestion_id,
        workspace_id=payload.workspace_id,
        feedback_id=payload.feedback_id,
        suggested_rule=payload.suggested_rule,
        status="pending_review",
        confidence_score=payload.confidence,
        created_at=datetime.utcnow(),
        reviewed_by=None,
        reviewed_at=None,
    )


@app.get("/v1/suggestions/{suggestion_id}", response_model=SuggestionResponse)
def get_suggestion_route(
    suggestion_id: str,
    db=Depends(get_db),
):
    # Return mock response
    from datetime import datetime
    return SuggestionResponse(
        suggestion_id=suggestion_id,
        workspace_id="default",
        feedback_id="mock-feedback",
        suggested_rule={"business_term": "example", "operation": "exclude"},
        status="pending_review",
        confidence_score=0.85,
        created_at=datetime.utcnow(),
        reviewed_by=None,
        reviewed_at=None,
    )


@app.post("/v1/suggestions/{suggestion_id}/approve", response_model=SuggestionResponse)
def approve_suggestion_route(
    suggestion_id: str,
    payload: SuggestionApproveRequest,
    db=Depends(get_db),
):
    from datetime import datetime
    return SuggestionResponse(
        suggestion_id=suggestion_id,
        workspace_id="default",
        feedback_id="mock-feedback",
        suggested_rule={"business_term": "example", "operation": "exclude"},
        status="approved",
        confidence_score=0.85,
        created_at=datetime.utcnow(),
        reviewed_by=payload.reviewer_id or "auto",
        reviewed_at=datetime.utcnow(),
    )


@app.post("/v1/suggestions/{suggestion_id}/reject", response_model=SuggestionResponse)
def reject_suggestion_route(
    suggestion_id: str,
    payload: SuggestionRejectRequest,
    db=Depends(get_db),
):
    from datetime import datetime
    return SuggestionResponse(
        suggestion_id=suggestion_id,
        workspace_id="default",
        feedback_id="mock-feedback",
        suggested_rule={"business_term": "example", "operation": "exclude"},
        status="rejected",
        confidence_score=0.85,
        created_at=datetime.utcnow(),
        reviewed_by=payload.reviewer_id or "auto",
        reviewed_at=datetime.utcnow(),
    )


@app.get("/v1/suggestions", response_model=List[SuggestionResponse])
def list_suggestions_route(
    db=Depends(get_db),
    workspace_id: Optional[str] = None,
    status: Optional[str] = None,
):
    from datetime import datetime
    # Return mock suggestions
    return [
        SuggestionResponse(
            suggestion_id="sug-1",
            workspace_id=workspace_id or "default",
            feedback_id="feedback-1",
            suggested_rule={"business_term": "revenue", "operation": "exclude"},
            status=status or "pending_review",
            confidence_score=0.85,
            created_at=datetime.utcnow(),
            reviewed_by=None,
            reviewed_at=None,
        )
    ]


# --- Clarification APIs ---

@app.post("/v1/clarifications", response_model=ClarificationResponse)
def create_clarification_route(
    payload: ClarificationCreateRequest,
    db=Depends(get_db),
):
    from datetime import datetime
    from uuid import uuid4
    # Return mock response
    return ClarificationResponse(
        clarification_id=str(uuid4()),
        feedback_id=payload.feedback_id,
        questions=["What is the exact scope?", "Are there exceptions?"],
        reason="Classification indicates need for clarification",
        status="pending",
        response=None,
        created_at=datetime.utcnow(),
        responded_at=None,
    )


@app.get("/v1/clarifications/{clarification_id}", response_model=ClarificationResponse)
def get_clarification_route(
    clarification_id: str,
    db=Depends(get_db),
):
    from datetime import datetime
    # Return mock response
    return ClarificationResponse(
        clarification_id=clarification_id,
        feedback_id="mock-feedback",
        questions=["What is the exact scope?"],
        reason="Classification indicates need for clarification",
        status="pending",
        response=None,
        created_at=datetime.utcnow(),
        responded_at=None,
    )


@app.post("/v1/clarifications/{clarification_id}/respond", response_model=ClarificationResponse)
def respond_to_clarification_route(
    clarification_id: str,
    payload: ClarificationRespondRequest,
    db=Depends(get_db),
):
    from datetime import datetime
    # Return mock response
    return ClarificationResponse(
        clarification_id=clarification_id,
        feedback_id="mock-feedback",
        questions=["What is the exact scope?"],
        reason="Classification indicates need for clarification",
        status="answered",
        response=payload.response,
        created_at=datetime.utcnow(),
        responded_at=datetime.utcnow(),
    )


# --- Review APIs ---

@app.post("/v1/reviews", response_model=ReviewResponse)
def create_review_route(
    payload: ReviewCreateRequest,
    db=Depends(get_db),
):
    from datetime import datetime
    from uuid import uuid4
    # Return mock response
    return ReviewResponse(
        review_id=str(uuid4()),
        suggestion_id=payload.suggestion_id,
        reviewer_id=payload.reviewer_id or "auto",
        status="assigned",
        priority=payload.priority or "normal",
        decision=None,
        notes=None,
        assigned_at=datetime.utcnow(),
        completed_at=None,
    )


@app.get("/v1/reviews/{review_id}", response_model=ReviewResponse)
def get_review_route(
    review_id: str,
    db=Depends(get_db),
):
    from datetime import datetime
    # Return mock response
    return ReviewResponse(
        review_id=review_id,
        suggestion_id="sug-1",
        reviewer_id="reviewer-1",
        status="assigned",
        priority="normal",
        decision=None,
        notes=None,
        assigned_at=datetime.utcnow(),
        completed_at=None,
    )


@app.post("/v1/reviews/{review_id}/complete", response_model=ReviewResponse)
def complete_review_route(
    review_id: str,
    payload: ReviewCompleteRequest,
    db=Depends(get_db),
):
    from datetime import datetime
    # Return mock response
    return ReviewResponse(
        review_id=review_id,
        suggestion_id="sug-1",
        reviewer_id="reviewer-1",
        status="completed",
        priority="normal",
        decision=payload.decision,
        notes=payload.notes,
        assigned_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )


@app.post("/v1/reviews/{review_id}/assign", response_model=ReviewResponse)
def assign_reviewer_route(
    review_id: str,
    payload: ReviewAssignRequest,
    db=Depends(get_db),
):
    from datetime import datetime
    # Return mock response
    return ReviewResponse(
        review_id=review_id,
        suggestion_id="sug-1",
        reviewer_id=payload.reviewer_id,
        status="assigned",
        priority="normal",
        decision=None,
        notes=None,
        assigned_at=datetime.utcnow(),
        completed_at=None,
    )


# --- Evaluation APIs ---

@app.post("/v1/evaluations", response_model=EvaluationResponse)
def create_evaluation_route(
    payload: EvaluationCreateRequest,
    db=Depends(get_db),
):
    from datetime import datetime
    from uuid import uuid4
    # Return mock response
    return EvaluationResponse(
        evaluation_id=str(uuid4()),
        workspace_id=payload.workspace_id,
        name=payload.name,
        description=payload.description,
        status="created",
        created_at=datetime.utcnow(),
    )


@app.get("/v1/evaluations/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation_route(
    evaluation_id: str,
    db=Depends(get_db),
):
    from datetime import datetime
    # Return mock response
    return EvaluationResponse(
        evaluation_id=evaluation_id,
        workspace_id="default",
        name="Evaluation",
        description="Mock evaluation",
        status="created",
        created_at=datetime.utcnow(),
    )


# --- Workspace APIs ---

@app.post("/v1/workspaces", response_model=WorkspaceResponse)
def create_workspace_route(
    payload: WorkspaceCreateRequest,
    db=Depends(get_db),
):
    from datetime import datetime
    from uuid import uuid4
    # Return mock response
    return WorkspaceResponse(
        workspace_id=str(uuid4()),
        name=payload.name,
        description=payload.description,
        status="active",
        created_at=datetime.utcnow(),
    )


@app.get("/v1/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace_route(
    workspace_id: str,
    db=Depends(get_db),
):
    from app.services.workspace_service import WorkspaceService
    workspace_service = WorkspaceService()
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