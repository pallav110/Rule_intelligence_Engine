from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
import redis
import csv
import io
import json
from uuid import uuid4
from fastapi import File, UploadFile
from sqlalchemy import text
import os
from pathlib import Path
from datetime import datetime, timezone
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

# Register Phase 3 E2E endpoints
from app.services.phase3_e2e_service import register_phase3_e2e_endpoints
register_phase3_e2e_endpoints(app)

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

# Phase 3 testing endpoint
@app.get("/test/phase3", include_in_schema=False)
async def phase3_test():
    """Serve Phase 3 testing UI for duplicate & conflict detection."""
    ui_file = static_dir / "phase3-test.html"
    if ui_file.exists():
        return FileResponse(str(ui_file), media_type="text/html")
    return {"message": "Phase 3 test UI not found"}

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

# --- Phase 3 Testing Endpoints (Duplicate & Conflict Detection) ---

@app.post("/v1/rules/check-duplicate")
def check_duplicate_endpoint(
    payload: dict,
    db=Depends(get_db),
):
    """
    Dedicated endpoint for testing duplicate detection with pgvector.

    Request:
    {
        "rule": {...suggested rule...},
        "workspace_id": "WS001",
        "domain_id": "ecommerce"
    }

    Response:
    {
        "is_duplicate": bool,
        "relationship": "exact_duplicate|semantic_duplicate|modification|...",
        "matching_rule_id": str or null,
        "confidence": float (0.0-1.0),
        "semantic_similarity": float (from pgvector),
        "retrieval_stage": int (number of candidates),
        "details": {...}
    }
    """
    try:
        suggested_rule = payload.get("rule", {})
        workspace_id = payload.get("workspace_id", "default")
        domain_id = payload.get("domain_id", "ecommerce")

        service = RealDuplicateDetectionService()
        result = service.check_duplicate(
            suggested_rule=suggested_rule,
            workspace_id=workspace_id,
            domain_id=domain_id,
            db=db,
        )

        return result
    except Exception as e:
        print(f"Error in duplicate detection: {e}")
        import traceback
        traceback.print_exc()
        return {
            "is_duplicate": False,
            "relationship": "unrelated",
            "matching_rule_id": None,
            "confidence": 0.0,
            "semantic_similarity": 0.0,
            "retrieval_stage": 0,
            "details": {"error": str(e)},
        }


@app.post("/v1/rules/check-conflict")
def check_conflict_endpoint(
    payload: dict,
    db=Depends(get_db),
):
    """
    Dedicated endpoint for testing conflict detection with pgvector.

    Request:
    {
        "rule": {...suggested rule...},
        "workspace_id": "WS001",
        "domain_id": "ecommerce"
    }

    Response:
    {
        "has_conflict": bool,
        "conflict_type": "direct_conflict|potential_conflict|temporal_conflict|scope_conflict|no_conflict",
        "conflicting_rule_ids": [str, ...],
        "confidence": float (0.0-1.0),
        "semantic_similarity": float (from pgvector),
        "retrieval_stage": int (number of candidates),
        "details": {...}
    }
    """
    try:
        suggested_rule = payload.get("rule", {})
        workspace_id = payload.get("workspace_id", "default")
        domain_id = payload.get("domain_id", "ecommerce")

        service = RealConflictDetectionService()
        result = service.check_conflict(
            suggested_rule=suggested_rule,
            workspace_id=workspace_id,
            domain_id=domain_id,
            db=db,
        )

        return result
    except Exception as e:
        print(f"Error in conflict detection: {e}")
        import traceback
        traceback.print_exc()
        return {
            "has_conflict": False,
            "conflict_type": "no_conflict",
            "conflicting_rule_ids": [],
            "confidence": 0.0,
            "semantic_similarity": 0.0,
            "retrieval_stage": 0,
            "details": {"error": str(e)},
        }

# --- Task 4: Clarification & Re-analysis Endpoints ---




@app.post("/v1/feedback/{feedback_id}/re-analyze")
def re_analyze_feedback(
    feedback_id: str,
    payload: dict,
    db=Depends(get_db),
):
    """
    Re-analyze feedback with clarification response.
    Preserves original feedback immutability.

    Request:
    {
        "clarification_response": "clarified feedback",
        "workspace_id": "WS001",
        "domain_id": "ecommerce"
    }

    Response: Full FeedbackAnalysisResponse with updated results
    """
    try:
        from app.db.models.feedback import Feedback
        from app.services.clarification_service import RealClarificationService
        from app.services.classifier import RealClassifier
        from app.services.enhanced_rule_extractor import EnhancedRuleExtractor
        from app.services.schema_validation_service import SchemaValidationService
        from app.services.duplicate_detection_service import RealDuplicateDetectionService
        from app.services.conflict_detection_service import RealConflictDetectionService
        from app.services.review_routing_service import RealReviewRoutingService

        # Get original feedback
        feedback = db.query(Feedback).filter_by(feedback_id=feedback_id).first()
        if not feedback:
            return {"error": f"Feedback {feedback_id} not found"}

        workspace_id = payload.get("workspace_id", feedback.workspace_id)
        domain_id = payload.get("domain_id", "ecommerce")
        clarification_response = payload.get("clarification_response", "")

        # Augmented feedback with clarification
        augmented_feedback = f"{feedback.feedback_text}\n\n[CLARIFICATION PROVIDED]\n{clarification_response}"

        # Re-run full pipeline with augmented feedback
        schema_context = {"domain_pack_id": domain_id}

        # Classification
        classifier = RealClassifier(domain=domain_id)
        classification_result = classifier.classify(augmented_feedback, schema_context)
        classification_result_dict = {
            "feedback_type": classification_result.get("feedback_type", "unclear_feedback"),
            "rule_category": classification_result.get("rule_category", "unknown"),
            "is_actionable": classification_result.get("is_actionable", False),
            "confidence": classification_result.get("confidence", 0.5),
        }

        # Extraction
        extractor = EnhancedRuleExtractor()
        extraction_result = extractor.extract(augmented_feedback, schema_context)
        extracted_rules = extraction_result.get("extraction", {}).get("extracted_rules", [])
        primary_rule = extracted_rules[0] if extracted_rules else {}

        # Duplicate Detection
        duplicate_service = RealDuplicateDetectionService()
        duplicate_check = duplicate_service.check_duplicate(
            suggested_rule=primary_rule,
            workspace_id=workspace_id,
            domain_id=domain_id,
            db=db,
        )

        # Conflict Detection
        conflict_service = RealConflictDetectionService()
        conflict_check = conflict_service.check_conflict(
            suggested_rule=primary_rule,
            workspace_id=workspace_id,
            domain_id=domain_id,
            db=db,
        )

        # Review Routing
        routing_service = RealReviewRoutingService()
        routing_decision = routing_service.route_suggestion(
            suggestion_id=None,
            suggestion=primary_rule,
            classification=classification_result_dict,
            extraction=extraction_result,
            conflict_check=conflict_check,
            duplicate_check=duplicate_check,
            workspace_id=workspace_id,
            domain_id=domain_id,
            db=db,
        )

        return {
            "success": True,
            "feedback_id": feedback_id,
            "original_feedback_preserved": True,
            "clarification_response": clarification_response,
            "augmented_feedback_used": True,
            "re_analysis_results": {
                "classification": classification_result_dict,
                "extracted_rules_count": len(extracted_rules),
                "duplicate_check": duplicate_check,
                "conflict_check": conflict_check,
                "routing_decision": routing_decision,
            }
        }

    except Exception as e:
        print(f"Error re-analyzing feedback: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
        }

# --- Task 6: Human Review Workflow APIs ---

@app.post("/v1/suggestions/{suggestion_id}/approve")
def approve_suggestion(
    suggestion_id: str,
    payload: dict,
    db=Depends(get_db),
):
    """
    Approve a suggestion and transition to APPROVED status.

    Request:
    {
        "approved_by": "reviewer_email",
        "comments": "Looks good for production",
        "create_rule": true
    }

    Response:
    {
        "success": true,
        "suggestion_id": "...",
        "new_status": "approved",
        "rule_id": "..." (if create_rule=true)
    }
    """
    try:
        from app.services.suggestion_lifecycle_service import SuggestionLifecycleService
        from app.db.models.rule_suggestion import RuleSuggestion

        # Get current suggestion
        suggestion = db.query(RuleSuggestion).filter_by(suggestion_id=suggestion_id).first()
        if not suggestion:
            return {"success": False, "error": f"Suggestion {suggestion_id} not found"}

        # Transition to APPROVED
        lifecycle_service = SuggestionLifecycleService()
        transition_result = lifecycle_service.transition_status(
            suggestion_id=suggestion_id,
            from_status=suggestion.review_status,
            to_status="approved",
            transitioned_by=payload.get("approved_by", "system"),
            reason=payload.get("comments", "Approved for rule creation"),
            metadata={"comments": payload.get("comments"), "create_rule": payload.get("create_rule", True)},
            db=db,
        )

        if not transition_result["success"]:
            return transition_result

        # Optionally create rule immediately
        rule_id = None
        if payload.get("create_rule", True):
            rule_result = create_rule_from_suggestion(suggestion_id, payload.get("approved_by"), db)
            if rule_result["success"]:
                rule_id = rule_result["rule_id"]
                # Transition to RULE_CREATED
                lifecycle_service.transition_status(
                    suggestion_id=suggestion_id,
                    from_status="approved",
                    to_status="rule_created",
                    transitioned_by=payload.get("approved_by", "system"),
                    reason="Rule created from approved suggestion",
                    metadata={"rule_id": rule_id},
                    db=db,
                )

        return {
            "success": True,
            "suggestion_id": suggestion_id,
            "new_status": "rule_created" if rule_id else "approved",
            "rule_id": rule_id,
            "audit_entry_id": transition_result["audit_entry_id"],
        }

    except Exception as e:
        print(f"Error approving suggestion: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.post("/v1/suggestions/{suggestion_id}/reject")
def reject_suggestion(
    suggestion_id: str,
    payload: dict,
    db=Depends(get_db),
):
    """
    Reject a suggestion and transition to REJECTED status.

    Request:
    {
        "rejected_by": "reviewer_email",
        "reason": "Conflicts with existing policy",
        "comments": "Cannot approve due to..."
    }

    Response:
    {
        "success": true,
        "suggestion_id": "...",
        "new_status": "rejected"
    }
    """
    try:
        from app.services.suggestion_lifecycle_service import SuggestionLifecycleService
        from app.db.models.rule_suggestion import RuleSuggestion

        # Get current suggestion
        suggestion = db.query(RuleSuggestion).filter_by(suggestion_id=suggestion_id).first()
        if not suggestion:
            return {"success": False, "error": f"Suggestion {suggestion_id} not found"}

        # Transition to REJECTED
        lifecycle_service = SuggestionLifecycleService()
        transition_result = lifecycle_service.transition_status(
            suggestion_id=suggestion_id,
            from_status=suggestion.review_status,
            to_status="rejected",
            transitioned_by=payload.get("rejected_by", "system"),
            reason=payload.get("reason", "Rejected by reviewer"),
            metadata={"comments": payload.get("comments"), "reason": payload.get("reason")},
            db=db,
        )

        return transition_result

    except Exception as e:
        print(f"Error rejecting suggestion: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.post("/v1/rules/{rule_id}/activate")
def activate_rule(
    rule_id: str,
    payload: dict,
    db=Depends(get_db),
):
    """
    Activate a created rule and transition suggestion to RULE_ACTIVATED.

    Request:
    {
        "activated_by": "admin_email",
        "effective_date": "2026-08-26",
        "comments": "Activating for production"
    }

    Response:
    {
        "success": true,
        "rule_id": "...",
        "status": "active",
        "suggestion_id": "..." (if linked)
    }
    """
    try:
        from app.services.suggestion_lifecycle_service import SuggestionLifecycleService
        from app.db.models.rule import Rule
        from app.db.models.rule_suggestion import RuleSuggestion

        # Get rule
        rule = db.query(Rule).filter_by(rule_id=rule_id).first()
        if not rule:
            return {"success": False, "error": f"Rule {rule_id} not found"}

        # Activate rule
        rule.status = "active"
        rule.activated_by = payload.get("activated_by", "system")
        rule.activated_at = datetime.now(timezone.utc)
        db.commit()

        # Find linked suggestion and transition to RULE_ACTIVATED
        suggestion = db.query(RuleSuggestion).filter_by(suggestion_id=rule.suggestion_id).first()
        suggestion_id = None
        if suggestion:
            suggestion_id = suggestion.suggestion_id
            lifecycle_service = SuggestionLifecycleService()
            lifecycle_service.transition_status(
                suggestion_id=suggestion_id,
                from_status=suggestion.review_status,
                to_status="rule_activated",
                transitioned_by=payload.get("activated_by", "system"),
                reason="Rule activated in production",
                metadata={"rule_id": rule_id, "comments": payload.get("comments")},
                db=db,
            )

        return {
            "success": True,
            "rule_id": rule_id,
            "status": "active",
            "suggestion_id": suggestion_id,
            "activated_by": rule.activated_by,
            "activated_at": rule.activated_at.isoformat(),
        }

    except Exception as e:
        print(f"Error activating rule: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.get("/v1/suggestions/{suggestion_id}/lifecycle")
def get_suggestion_lifecycle(
    suggestion_id: str,
    db=Depends(get_db),
):
    """
    Get complete lifecycle and audit history for a suggestion.

    Response:
    {
        "success": true,
        "suggestion_id": "...",
        "current_status": "approved",
        "valid_next_statuses": ["rule_created"],
        "history": [
            {
                "from_status": "pending_review",
                "to_status": "approved",
                "transitioned_by": "reviewer@example.com",
                "created_at": "2026-08-26T06:00:00Z"
            }
        ]
    }
    """
    try:
        from app.services.suggestion_lifecycle_service import SuggestionLifecycleService

        lifecycle_service = SuggestionLifecycleService()

        # Get current status
        status_result = lifecycle_service.get_current_status(suggestion_id, db)
        if not status_result["success"]:
            return status_result

        # Get audit history
        history_result = lifecycle_service.get_audit_history(suggestion_id, db)
        if not history_result["success"]:
            return history_result

        return {
            "success": True,
            "suggestion_id": suggestion_id,
            "current_status": status_result["current_status"],
            "valid_next_statuses": status_result["valid_next_statuses"],
            "history": history_result["history"],
            "total_transitions": history_result["total_transitions"],
        }

    except Exception as e:
        print(f"Error getting lifecycle: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def create_rule_from_suggestion(suggestion_id: str, created_by: str, db) -> Dict[str, Any]:
    """Helper function to create a rule from an approved suggestion."""
    try:
        from app.db.models.rule_suggestion import RuleSuggestion
        from app.db.models.rule import Rule

        suggestion = db.query(RuleSuggestion).filter_by(suggestion_id=suggestion_id).first()
        if not suggestion:
            return {"success": False, "error": f"Suggestion {suggestion_id} not found"}

        # Create rule from suggestion
        rule_id = f"RULE_{str(uuid4())[:8].upper()}"
        suggested_rule = suggestion.suggested_rule or {}

        rule = Rule(
            rule_id=rule_id,
            workspace_id=suggestion.workspace_id,
            domain_id="ecommerce",  # TODO: Get from suggestion
            suggestion_id=suggestion_id,
            business_term=suggested_rule.get("business_term", ""),
            rule_category=suggestion.rule_category or "unknown",
            operation=suggested_rule.get("operation", ""),
            conditions=suggested_rule.get("conditions", []),
            scope=suggested_rule.get("scope", "global"),
            affected_entities=suggested_rule.get("affected_entities", {}),
            status="draft",
            created_at=datetime.now(timezone.utc),
        )

        db.add(rule)
        db.commit()

        return {
            "success": True,
            "rule_id": rule_id,
            "suggestion_id": suggestion_id,
            "status": "draft",
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}

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
    from app.db.models.workspace import Workspace

    # AUTO-CREATE WORKSPACE if it doesn't exist in THIS session
    existing_workspace = db.query(Workspace).filter_by(workspace_id=payload.workspace_id).first()
    if not existing_workspace:
        workspace = Workspace(
            workspace_id=payload.workspace_id,
            name=f"Workspace {payload.workspace_id[:8]}",
            description="Auto-created workspace on first feedback submission",
            status="active",
        )
        db.add(workspace)
        db.flush()

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
        domain_id=domain_pack_id,
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
            is_duplicate=duplicate_check.get("is_duplicate", False),
            matching_rule_id=duplicate_check.get("matching_rule_id"),
            confidence=duplicate_check.get("confidence", 0.0),
            semantic_similarity=duplicate_check.get("semantic_similarity", 0.0),
            retrieval_stage=duplicate_check.get("retrieval_stage", 0),
            similar_rules=duplicate_check.get("similar_rules", []),
            details=duplicate_check.get("details", {}),
        ),
        conflict_detection=ConflictDetectionResponse(
            status=conflict_check.get("status", "no_conflict"),
            relationship=conflict_check.get("relationship", "compatible"),
            has_conflict=conflict_check.get("has_conflict", False),
            conflict_type=conflict_check.get("conflict_type"),
            confidence=conflict_check.get("confidence", 0.0),
            semantic_similarity=conflict_check.get("semantic_similarity", 0.0),
            retrieval_stage=conflict_check.get("retrieval_stage", 0),
            conflicting_rule_ids=conflict_check.get("conflicting_rule_ids", []),
            related_compatible_rule_ids=conflict_check.get("related_compatible_rule_ids", []),
            conflicting_rules=conflict_check.get("conflicting_rules", []),
            details=conflict_check.get("details", {}),
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
    from app.services.suggestion_service import SuggestionService
    service = SuggestionService()
    s_obj = service.create_suggestion(
        db=db,
        workspace_id=payload.workspace_id,
        feedback_id=payload.feedback_id,
        suggested_rule=payload.suggested_rule,
        confidence=payload.confidence,
    )
    return SuggestionResponse(
        suggestion_id=s_obj.suggestion_id,
        workspace_id=s_obj.workspace_id,
        feedback_id=s_obj.feedback_id,
        suggested_rule=s_obj.suggested_rule,
        status=s_obj.review_status,
        confidence_score=payload.confidence,
        created_at=s_obj.created_at,
        reviewed_by=None,
        reviewed_at=None,
    )


@app.get("/v1/suggestions/{suggestion_id}", response_model=SuggestionResponse)
def get_suggestion_route(
    suggestion_id: str,
    db=Depends(get_db),
):
    from app.services.suggestion_service import SuggestionService
    service = SuggestionService()
    s_obj = service.get_suggestion(db, suggestion_id)
    if not s_obj:
        raise HTTPException(status_code=404, detail="Suggestion not found")
        
    return SuggestionResponse(
        suggestion_id=s_obj.suggestion_id,
        workspace_id=s_obj.workspace_id,
        feedback_id=s_obj.feedback_id,
        suggested_rule=s_obj.suggested_rule,
        status=s_obj.review_status,
        confidence_score=0.0,
        created_at=s_obj.created_at,
        reviewed_by=None,
        reviewed_at=None,
    )


@app.post("/v1/suggestions/{suggestion_id}/approve", response_model=SuggestionResponse)
def approve_suggestion_route(
    suggestion_id: str,
    payload: SuggestionApproveRequest,
    db=Depends(get_db),
):
    from app.services.suggestion_lifecycle_service import SuggestionLifecycleService
    service = SuggestionLifecycleService()
    s_obj = service.transition_status(db, suggestion_id, "approved", payload.reviewer_id, payload.notes)
    
    return SuggestionResponse(
        suggestion_id=s_obj.suggestion_id,
        workspace_id=s_obj.workspace_id,
        feedback_id=s_obj.feedback_id,
        suggested_rule=s_obj.suggested_rule,
        status=s_obj.review_status,
        confidence_score=0.0,
        created_at=s_obj.created_at,
        reviewed_by=None,
        reviewed_at=None,
    )

@app.post("/v1/suggestions/{suggestion_id}/reject", response_model=SuggestionResponse)
def reject_suggestion_route(
    suggestion_id: str,
    payload: SuggestionRejectRequest,
    db=Depends(get_db),
):
    from app.services.suggestion_lifecycle_service import SuggestionLifecycleService
    service = SuggestionLifecycleService()
    s_obj = service.transition_status(db, suggestion_id, "rejected", payload.reviewer_id, payload.notes)
    
    return SuggestionResponse(
        suggestion_id=s_obj.suggestion_id,
        workspace_id=s_obj.workspace_id,
        feedback_id=s_obj.feedback_id,
        suggested_rule=s_obj.suggested_rule,
        status=s_obj.review_status,
        confidence_score=0.0,
        created_at=s_obj.created_at,
        reviewed_by=None,
        reviewed_at=None,
    )


@app.get("/v1/suggestions", response_model=List[SuggestionResponse])
def list_suggestions_route(
    db=Depends(get_db),
    workspace_id: Optional[str] = None,
    status: Optional[str] = None,
):
    from app.db.models.rule_suggestion import RuleSuggestion
    
    query = db.query(RuleSuggestion)
    if workspace_id:
        query = query.filter(RuleSuggestion.workspace_id == workspace_id)
    if status:
        query = query.filter(RuleSuggestion.review_status == status)
        
    results = query.all()
    
    return [
        SuggestionResponse(
            suggestion_id=s.suggestion_id,
            workspace_id=s.workspace_id,
            feedback_id=s.feedback_id,
            suggested_rule=s.suggested_rule,
            status=s.review_status,
            confidence_score=0.0,
            created_at=s.created_at,
            reviewed_by=s.reviewed_by,
            reviewed_at=s.reviewed_at,
        ) for s in results
    ]


# --- Clarification APIs ---

@app.post("/v1/clarifications", response_model=ClarificationResponse)
def create_clarification_route(
    payload: ClarificationCreateRequest,
    db=Depends(get_db),
):
    from app.services.clarification_service import RealClarificationService
    from app.db.models.feedback import Feedback
    
    feedback = db.query(Feedback).filter_by(feedback_id=payload.feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    service = RealClarificationService()
    res = service.generate_clarification(
        feedback_id=payload.feedback_id,
        feedback_text=feedback.feedback_text,
        classification=payload.classification,
        extraction=payload.extraction,
        workspace_id=feedback.workspace_id,
        db=db
    )
    db.commit()
    
    from datetime import datetime
    return ClarificationResponse(
        clarification_id=res.get("clarification_id") or "not-needed",
        feedback_id=payload.feedback_id,
        questions=res.get("questions", []),
        reason=res.get("reason", ""),
        status=res.get("status", "pending"),
        response=None,
        created_at=datetime.utcnow(),
        responded_at=None,
    )


@app.get("/v1/clarifications/{clarification_id}", response_model=ClarificationResponse)
def get_clarification_route(
    clarification_id: str,
    db=Depends(get_db),
):
    from app.db.models.clarification import Clarification
    clar = db.query(Clarification).filter_by(clarification_id=clarification_id).first()
    if not clar:
        raise HTTPException(status_code=404, detail="Clarification not found")
        
    return ClarificationResponse(
        clarification_id=clar.clarification_id,
        feedback_id=clar.feedback_id,
        questions=clar.questions or [],
        reason=clar.reason or "",
        status=clar.processing_status or "pending",
        response=clar.clarification_response,
        created_at=clar.created_at,
        responded_at=clar.responded_at,
    )


@app.post("/v1/clarifications/{clarification_id}/respond", response_model=ClarificationResponse)
def respond_to_clarification_route(
    clarification_id: str,
    payload: ClarificationRespondRequest,
    db=Depends(get_db),
):
    from app.services.clarification_service import RealClarificationService
    from app.db.models.clarification import Clarification
    
    service = RealClarificationService()
    res = service.respond_to_clarification(clarification_id, payload.response, db=db)
    
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error") or "Failed")
        
    clar = db.query(Clarification).filter_by(clarification_id=clarification_id).first()
    return ClarificationResponse(
        clarification_id=clar.clarification_id,
        feedback_id=clar.feedback_id,
        questions=clar.questions or [],
        reason=clar.reason or "",
        status=clar.processing_status,
        response=clar.clarification_response,
        created_at=clar.created_at,
        responded_at=clar.responded_at,
    )


# --- Review APIs ---

@app.post("/v1/reviews", response_model=ReviewResponse)
def create_review_route(
    payload: ReviewCreateRequest,
    db=Depends(get_db),
):
    from app.db.models.review import Review
    from datetime import datetime
    from uuid import uuid4
    
    review_id = str(uuid4())
    review = Review(
        review_id=review_id,
        suggestion_id=payload.suggestion_id,
        workspace_id="default",  # Usually decoupled to workspace of suggestion
        reviewer_id=payload.reviewer_id or "auto",
        status="assigned",
        priority=payload.priority or "normal",
        decision=None,
        notes=None,
        assigned_at=datetime.utcnow(),
        completed_at=None,
        created_at=datetime.utcnow()
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    
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


@app.get("/v1/reviews/{review_id}", response_model=ReviewResponse)
def get_review_route(
    review_id: str,
    db=Depends(get_db),
):
    from app.db.models.review import Review
    
    review = db.query(Review).filter_by(review_id=review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
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


@app.post("/v1/reviews/{review_id}/complete", response_model=ReviewResponse)
def complete_review_route(
    review_id: str,
    payload: ReviewCompleteRequest,
    db=Depends(get_db),
):
    from app.db.models.review import Review
    from datetime import datetime
    
    review = db.query(Review).filter_by(review_id=review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
    review.status = "completed"
    review.decision = payload.decision
    review.notes = payload.notes
    review.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(review)
    
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
):
    from app.db.models.review import Review
    
    review = db.query(Review).filter_by(review_id=review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
    review.reviewer_id = payload.reviewer_id
    review.status = "assigned"
    db.commit()
    db.refresh(review)
    
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


# --- Evaluation APIs ---

@app.post("/v1/evaluations", response_model=EvaluationResponse)
def create_evaluation_route(
    payload: EvaluationCreateRequest,
    db=Depends(get_db),
):
    from app.services.evaluation_service import EvaluationService
    service = EvaluationService()
    try:
        run = service.create_evaluation_run(
            db=db,
            model_version_id=payload.model_version_id,
            dataset_version_id=payload.dataset_version_id
        )
        return EvaluationResponse(
            evaluation_run_id=run.evaluation_run_id,
            model_version_id=run.model_version_id,
            dataset_version_id=run.dataset_version_id,
            status=run.status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            metrics=[]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/evaluations/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation_route(
    evaluation_id: str,
    db=Depends(get_db),
):
    from app.services.evaluation_service import EvaluationService
    service = EvaluationService()
    try:
        res = service.get_evaluation_run(db, evaluation_id)
        return EvaluationResponse(
            evaluation_run_id=res["evaluation_run_id"],
            model_version_id=res["model_version_id"],
            dataset_version_id=res["dataset_version_id"],
            status=res["status"],
            started_at=res["started_at"],
            completed_at=res["completed_at"],
            metrics=res["metrics"]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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

# Restore Phase 4 Services
from app.schemas.analysis_run import AnalysisRunResponse
from app.services.analysis_run_service import AnalysisRunService
from fastapi import HTTPException
import app.schemas.model_version as mv_schemas
from app.services.model_version_service import ModelVersionService
import app.schemas.dataset as dataset_schemas
from app.services.dataset_version_service import DatasetVersionService
from app.services.background_job_service import BackgroundJobService
from app.schemas.jobs import JobResponse

@app.get("/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db=Depends(get_db)):
    service = BackgroundJobService()
    try:
        job = service.get_job(db, job_id)
        return JobResponse(
            job_id=job.job_id,
            status=job.status,
            result=job.result,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/v1/dataset-versions", response_model=dataset_schemas.DatasetVersionResponse)
def create_dataset_version(payload: dataset_schemas.DatasetVersionCreateRequest, db=Depends(get_db)):
    service = DatasetVersionService()
    try:
        # pass dummy workspace id since CreateRequest doesn't have it
        job = service.create_version(db, payload.dataset_name, payload.version, "default", None, "system")
        return dataset_schemas.DatasetVersionResponse(
            dataset_version_id=job.dataset_version_id,
            dataset_name=job.dataset_name,
            version=job.version,
            domain_pack_version=payload.domain_pack_version,
            annotation_version=payload.annotation_version,
            source=payload.source,
            path=payload.path,
            status=job.status
        )
    except Exception as e:
        raise HTTPException(status_code=409 if "Conflict" in str(e) else 400, detail=str(e))

@app.get("/v1/dataset-versions", response_model=list[dataset_schemas.DatasetVersionResponse])
def list_dataset_versions(db=Depends(get_db)):
    service = DatasetVersionService()
    return service.list_versions(db)

@app.get("/v1/dataset-versions/{dataset_id}", response_model=dataset_schemas.DatasetVersionResponse)
def get_dataset_version(dataset_id: str, db=Depends(get_db)):
    service = DatasetVersionService()
    try:
        return service.get_version(db, dataset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/v1/model-versions", response_model=mv_schemas.ModelVersionResponse)
def create_model_version(payload: mv_schemas.ModelVersionCreateRequest, db=Depends(get_db)):
    service = ModelVersionService()
    try:
        model = service.create_model_version(db, payload.model_name, payload.version, payload.workspace_id, "s3://mock")
        return mv_schemas.ModelVersionResponse(
            model_version_id=model.model_version_id,
            model_name=model.model_name,
            version=model.version,
            status=model.status,
            artifact_path=model.artifact_path
        )
    except Exception as e:
        raise HTTPException(status_code=409 if "Conflict" in str(e) else 400, detail=str(e))

@app.get("/v1/model-versions", response_model=list[mv_schemas.ModelVersionResponse])
def list_model_versions(db=Depends(get_db)):
    service = ModelVersionService()
    return service.list_model_versions(db)

@app.get("/v1/model-versions/{model_id}", response_model=mv_schemas.ModelVersionResponse)
def get_model_version(model_id: str, db=Depends(get_db)):
    service = ModelVersionService()
    try:
        model = service.get_model_version(db, model_id)
        return mv_schemas.ModelVersionResponse(
            model_version_id=model.model_version_id,
            model_name=model.model_name,
            version=model.version,
            status=model.status,
            artifact_path=model.artifact_path
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/v1/analysis-runs/{run_id}", response_model=AnalysisRunResponse)
def get_analysis_run(run_id: str, db=Depends(get_db)):
    service = AnalysisRunService()
    try:
        run = service.get_analysis_run(db, run_id)
        return AnalysisRunResponse(
            analysis_run_id=run.analysis_run_id,
            feedback_id=run.feedback_id,
            workspace_id=run.workspace_id,
            processing_mode=run.processing_mode,
            status=run.status,
            created_at=run.created_at,
            threshold_configuration=run.threshold_configuration
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.on_event("startup")
def list_routes():
    import inspect
    routes = [(route.path, route.methods) for route in app.routes if hasattr(route, 'methods')]
    print(f"Registered {len(routes)} API routes")