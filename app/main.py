from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional
import redis
import csv
import io
import json
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
    ClassificationResponse,
    ExtractionResponse,
    SchemaValidationResponse,
    DuplicateDetectionResponse,
    ConflictDetectionResponse,
    ClarificationResponse as FeedbackClarificationResponse,
    RoutingDecisionResponse,
    PerFieldConfidence,
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
from app.schemas.jobs import (
    JobCreateRequest,
    JobResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
)
from app.schemas.evaluation import (
    EvaluationCreateRequest,
    EvaluationMetricResponse,
    EvaluationResponse,
)
from app.schemas.suggestion import (
    SuggestionCreateRequest,
    SuggestionResponse,
    SuggestionApproveRequest,
    SuggestionRejectRequest,
    ClarificationCreateRequest,
    ClarificationRespondRequest,
    ReviewCreateRequest,
    ReviewResponse,
    ReviewCompleteRequest,
    ReviewAssignRequest,
)
from app.services.classifier import RealClassifier
from app.services.feedback_service import FeedbackService
from app.services.suggestion_service import SuggestionService
from app.services.clarification_service import ClarificationService
from app.services.review_routing_service import ReviewRoutingService
from app.services.conflict_detection_service import RealConflictDetectionService
from app.services.duplicate_detection_service import RealDuplicateDetectionService
from app.services.domain_pack_detector import detect_domain_pack

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

# Phase 2 testing endpoint
@app.get("/test/phase2", include_in_schema=False)
async def phase2_test():
    """Serve Phase 2 testing UI for classification, extraction, validation."""
    ui_file = static_dir / "phase2-test.html"
    if ui_file.exists():
        return FileResponse(str(ui_file), media_type="text/html")
    return {"message": "Phase 2 test UI not found"}

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

# --- Helper APIs ---

@app.post("/api/detect-domain-pack")
def detect_domain_pack_endpoint(payload: FeedbackAnalysisRequest):
    """Auto-detect which domain pack feedback belongs to based on content analysis."""
    feedback_text = payload.feedback_text or ""
    detected_domain, confidence = detect_domain_pack(feedback_text)

    return {
        "detected_domain": detected_domain,
        "confidence": round(confidence, 3),
        "recommended": detected_domain if confidence > 0.3 else None,
        "reasoning": f"Domain auto-detected with {confidence*100:.1f}% confidence"
    }

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
    Analyze feedback through complete 8-step Phase 2 pipeline:
    1. Classify feedback
    2. Extract rules with enhanced evidence & confidence
    3. Schema validation (PASS/PARTIAL/FAIL + coverage)
    4. Duplicate detection
    5. Conflict detection
    6. Clarification generation
    7. Review routing
    8. Persist suggestion
    """
    from uuid import uuid4
    from datetime import datetime
    from app.services.enhanced_rule_extractor import EnhancedRuleExtractor
    from app.services.schema_validation_service import SchemaValidationService
    from app.services.duplicate_detection_service import RealDuplicateDetectionService
    from app.services.conflict_detection_service import RealConflictDetectionService
    from app.services.clarification_service import RealClarificationService
    from app.services.review_routing_service import RealReviewRoutingService

    # Step 1: Create Feedback record
    feedback_id = payload.feedback_id or str(uuid4())
    feedback = Feedback(
        feedback_id=feedback_id,
        workspace_id=payload.workspace_id,
        feedback_text=payload.feedback_text,
        submitted_by=payload.submitted_by,
        processing_status="processing",
        created_at=datetime.utcnow(),
    )
    db.add(feedback)
    db.flush()

    # Step 2: Create AnalysisRun record
    analysis_run_id = str(uuid4())
    suggestion_id = str(uuid4())
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

    # STEP 1: Classification (with domain-aware baseline model)
    domain_pack_id = payload.schema_context.get("domain_pack_id", "customer_support")
    classifier = RealClassifier(domain=domain_pack_id)
    classification_result = classifier.classify(
        payload.feedback_text, payload.schema_context
    )
    classification_result_dict = {
        "feedback_type": classification_result.get("feedback_type", "unclear_feedback"),
        "rule_category": classification_result.get("rule_category", "unknown"),
        "is_actionable": classification_result.get("is_actionable", False),
        "confidence": classification_result.get("confidence", 0.5),
    }

    # STEP 2: Rule Extraction (with glossary, evidence, per-field confidence)
    extractor = EnhancedRuleExtractor()
    extraction_result = extractor.extract(payload.feedback_text, payload.schema_context)
    extracted_rules = extraction_result.get("extraction", {}).get("extracted_rules", [])

    # STEP 3: Schema Validation
    # Load actual schema from domain pack for validation
    domain_pack_id = payload.schema_context.get("domain_pack_id", "ecommerce")
    domain_schema = {}
    try:
        schema_path = Path(__file__).parent.parent / "rie_ml" / "domain-packs" / domain_pack_id / "schema" / "schema.json"
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                domain_schema = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load schema for {domain_pack_id}: {e}")

    # Pass domain_pack_schema in schema_context to ensure validator has access
    full_schema_context = dict(payload.schema_context) if payload.schema_context else {}
    full_schema_context["domain_pack_schema"] = domain_schema

    schema_validator = SchemaValidationService(schema_context=full_schema_context)
    schema_validation_results = []
    for rule in extracted_rules:
        validation = schema_validator.validate_rule(rule, domain_schema)
        schema_validation_results.append(validation)

    # Aggregate schema validation
    schema_validation = {
        "status": "PASS" if all(v["status"] == "PASS" for v in schema_validation_results) else
                  "PARTIAL" if any(v["status"] in ["PASS", "PARTIAL"] for v in schema_validation_results) else "FAIL",
        "coverage": sum(v["coverage"] for v in schema_validation_results) / len(schema_validation_results) if schema_validation_results else 0.0,
        "mandatory_fields_valid": all(v["mandatory_fields_valid"] for v in schema_validation_results),
        "validation_errors": [e for v in schema_validation_results for e in v["validation_errors"]],
    }

    # STEP 4: Persist Suggestion (BEFORE clarification/routing to satisfy FK constraints)
    primary_rule = extracted_rules[0] if extracted_rules else {}
    rule_suggestion = RuleSuggestion(
        suggestion_id=suggestion_id,
        workspace_id=payload.workspace_id,
        feedback_id=feedback_id,
        analysis_run_id=analysis_run_id,
        feedback_type=classification_result_dict.get("feedback_type"),
        rule_category=classification_result_dict.get("rule_category"),
        classification_result=classification_result_dict,
        extraction_result="completed",
        clarification_required=False,  # Will update after clarification check
        review_status="pending_review",  # Will update after routing
        suggested_rule=primary_rule,
        created_at=datetime.utcnow(),
    )
    db.add(rule_suggestion)
    db.flush()  # Flush to ensure suggestion is persisted before FK references

    # STEP 5: Duplicate Detection
    duplicate_service = RealDuplicateDetectionService()
    duplicate_check = duplicate_service.check_duplicate(
        suggested_rule=primary_rule,
        workspace_id=payload.workspace_id,
        domain_id=domain_pack_id,
        db=db,
    )

    # STEP 6: Conflict Detection
    conflict_service = RealConflictDetectionService()
    conflict_check = conflict_service.check_conflict(
        suggested_rule=primary_rule,
        workspace_id=payload.workspace_id,
        domain_id=domain_pack_id,
        db=db,
    )

    # STEP 7: Clarification Generation (NOW safe to reference suggestion)
    clarification_service = RealClarificationService()
    clarification_result = clarification_service.generate_clarification(
        feedback_id=feedback_id,
        feedback_text=payload.feedback_text,
        classification=classification_result_dict,
        extraction=extraction_result,
        workspace_id=payload.workspace_id,
        suggestion_id=suggestion_id,
        analysis_run_id=analysis_run_id,
        db=db,
    )

    # STEP 8: Review Routing
    routing_service = RealReviewRoutingService()
    routing_decision = routing_service.route_suggestion(
        suggestion_id=suggestion_id,
        suggestion=primary_rule,
        classification=classification_result_dict,
        extraction=extraction_result,
        conflict_check=conflict_check,
        duplicate_check=duplicate_check,
        workspace_id=payload.workspace_id,
        domain_id=domain_pack_id,
        db=db,
    )

    # Update suggestion with clarification and routing results
    rule_suggestion.clarification_required = clarification_result.get("created", False)
    rule_suggestion.review_status = routing_decision.get("review_status", "pending_review")

    analysis_run.status = "completed"
    analysis_run.completed_at = datetime.utcnow()
    db.commit()

    # Build spec-compliant response with per-module confidence
    clarification_required = clarification_result.get("created", False)

    # Build extraction confidence with semantic labels
    per_field_confidence = extraction_result.get("extraction", {}).get("confidence", {})
    if per_field_confidence:
        extraction_confidence = PerFieldConfidence(**per_field_confidence)
    else:
        # Fallback from overall confidence
        overall = extraction_result.get("extraction_confidence", 0.5)
        extraction_confidence = PerFieldConfidence(
            business_term=overall,
            operation=overall,
            conditions=overall,
            scope=overall,
            affected_entities=overall
        )

    # Schema validation with schema_loaded flag
    schema_validation_results = schema_validation_results  # Already computed
    schema_loaded = schema_validation_results[0].get("schema_loaded", False) if schema_validation_results else False
    schema_validation_obj = SchemaValidationResponse(
        status=schema_validation["status"],
        coverage=schema_validation["coverage"],
        mandatory_fields_valid=schema_validation["mandatory_fields_valid"],
        validation_errors=schema_validation["validation_errors"],
        schema_loaded=schema_loaded
    )

    # Build extraction response with proper structure
    extraction_data = extraction_result.get("extraction", {})
    extraction_response = ExtractionResponse(
        extracted_rules=extraction_data.get("extracted_rules", []),
        candidate_rules=extraction_data.get("candidate_rules", []),
        rules=extraction_data.get("rules", []),
        confidence=extraction_confidence,
        evidence=extraction_result.get("evidence", ""),
        rule_count=extraction_result.get("rule_count", {"extracted": 0, "candidates": 0})
    )

    return FeedbackAnalysisResponse(
        feedback_id=feedback_id,
        suggestion_id=suggestion_id,
        status="PENDING_REVIEW",
        classification=ClassificationResponse(
            feedback_type=classification_result_dict["feedback_type"],
            rule_category=classification_result_dict["rule_category"],
            confidence=classification_result_dict["confidence"],
            is_actionable=classification_result_dict["is_actionable"],
        ),
        extraction=extraction_response,
        schema_validation=schema_validation_obj,
        duplicate_detection=DuplicateDetectionResponse(
            status=duplicate_check.get("status", "none"),
            relationship=duplicate_check.get("relationship", "unrelated"),
            similar_rules=duplicate_check.get("similar_rules", []),
        ),
        conflict_detection=ConflictDetectionResponse(
            status=conflict_check.get("status", "no_conflict"),
            relationship=conflict_check.get("relationship", "compatible"),
            conflicting_rules=conflict_check.get("conflicting_rules", []),
        ),
        clarification_required=clarification_required,
        clarification=FeedbackClarificationResponse(
            clarification_id=clarification_result.get("clarification_id"),
            required=clarification_required,
            questions=clarification_result.get("questions", []),
            reason=clarification_result.get("reason", ""),
            ambiguity_reasons=clarification_result.get("ambiguity_reasons", []),
        ) if clarification_required else None,
        routing_decision=RoutingDecisionResponse(
            review_status=routing_decision.get("review_status", "pending_review"),
            priority=routing_decision.get("priority", "normal"),
            reason=routing_decision.get("reason", "")
        ),
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
    from app.db.models.workspace import Workspace

    workspace_id = str(uuid4())
    workspace = Workspace(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        status="active",
        created_at=datetime.utcnow(),
    )
    db.add(workspace)
    db.commit()

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
):
    from app.db.models.workspace import Workspace
    workspace = db.get(Workspace, workspace_id)
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