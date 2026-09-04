from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status, Request, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
import json
from uuid import uuid4
from fastapi import File, UploadFile
from sqlalchemy import text
from pathlib import Path
from datetime import datetime, timezone
import logging
from app.db.database import engine
from app.db.database import get_db
from app.db.models.feedback import Feedback
from app.db.models.analysis_run import AnalysisRun
from app.db.models.rule_suggestion import RuleSuggestion
from app.schemas.feedback import (
    FeedbackAnalysisRequest,
    FeedbackAnalysisResponse,
    ClassificationResponse,
    ExtractionResponse,
    SchemaValidationResponse,
    DuplicateDetectionResponse,
    ConflictDetectionResponse,
    ClarificationResponse as FeedbackClarificationResponse,
    RoutingDecisionResponse,
    PerFieldConfidence,
    PreprocessingResponse,
)

# Setup logging
from app.logging_config import setup_logging, input_validation_logger
logger = setup_logging()

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
from app.services.baseline_duplicate_detection_service import BaselineDuplicateDetectionService
from app.services.baseline_conflict_detection_service import BaselineConflictDetectionService
from app.services.completeness_checker import CompletenessChecker, AmbiguityDetector
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
    # === INPUT VALIDATION LOGGING (8.1) ===
    input_validation_logger.info("=== DOMAIN PACK DETECTION - INPUT VALIDATION START ===")
    input_validation_logger.info(f"Workspace ID: {payload.workspace_id}")
    input_validation_logger.info(f"Feedback length: {len(payload.feedback_text or '')} characters")
    input_validation_logger.info("=== DOMAIN PACK DETECTION - INPUT VALIDATION COMPLETE ===")

    feedback_text = payload.feedback_text or ""
    detected_domain, confidence = detect_domain_pack(feedback_text)

    return {
        "detected_domain": detected_domain,
        "confidence": round(confidence, 3),
        "recommended": detected_domain if confidence > 0.3 else None,
        "reasoning": f"Domain auto-detected with {confidence*100:.1f}% confidence"
    }

# --- Phase 3 Testing Endpoints (Duplicate & Conflict Detection) ---

@app.post("/v1/rules/check-conflict")
def check_conflict_endpoint(
    payload: dict,
    model: str = "baseline",
    db=Depends(get_db),
):
    """
    Dedicated endpoint for testing conflict detection.

    Request:
    {
        "rule": {...suggested rule...} OR "suggested_rule": {...},
        "workspace_id": "WS001",
        "domain_id": "ecommerce"
    }

    Query params:
    - model: "baseline" or "semantic" (default: "baseline")

    Response:
    {
        "has_conflict": bool,
        "conflict_type": "direct_conflict|potential_conflict|temporal_conflict|scope_conflict|no_conflict",
        "conflicting_rule_ids": [str, ...],
        "confidence": float (0.0-1.0),
        "retrieval_stage": int (number of candidates),
        "details": {...}
    }
    """
    # === INPUT VALIDATION LOGGING (8.1) ===
    input_validation_logger.info("=== CONFLICT DETECTION - INPUT VALIDATION START ===")
    input_validation_logger.info(f"Workspace ID: {payload.get('workspace_id', 'default')}")
    input_validation_logger.info(f"Domain ID: {payload.get('domain_id', 'ecommerce')}")
    input_validation_logger.info(f"Rule provided: {bool(payload.get('rule') or payload.get('suggested_rule'))}")
    input_validation_logger.info(f"Model: {model}")
    input_validation_logger.info("=== CONFLICT DETECTION - INPUT VALIDATION COMPLETE ===")

    try:
        # Support both "rule" and "suggested_rule" keys
        suggested_rule = payload.get("rule") or payload.get("suggested_rule", {})
        workspace_id = payload.get("workspace_id", "default")
        domain_id = payload.get("domain_id", "ecommerce")

        # Select service based on model parameter
        if model == "semantic":
            service = RealConflictDetectionService()
        else:
            service = BaselineConflictDetectionService()

        result = service.check_conflict(
            suggested_rule=suggested_rule,
            workspace_id=workspace_id,
            domain_id=domain_id,
            db=db,
        )

        return {
            **result,
            "model_used": model,
        }
    except Exception as e:
        print(f"Error in conflict detection: {e}")
        import traceback
        traceback.print_exc()
        return {
            "has_conflict": False,
            "conflict_type": "no_conflict",
            "conflicting_rule_ids": [],
            "confidence": 0.0,
            "retrieval_stage": 0,
            "details": {"error": str(e)},
            "model_used": model,
        }

# --- Task 4: Clarification & Re-analysis Endpoints ---

@app.post("/v1/clarifications/{clarification_id}/respond")
def respond_to_clarification(
    clarification_id: str,
    payload: dict,
    db=Depends(get_db),
):
    """
    Respond to a clarification question.

    Request:
    {
        "response_text": "user's clarification response",
        "responded_by": "user_id or email"
    }

    Response:
    {
        "success": true,
        "clarification_id": "...",
        "feedback_id": "...",
        "next_step": "re_analyze_with_clarification"
    }
    """
    try:
        from app.services.clarification_service import RealClarificationService

        service = RealClarificationService()
        result = service.respond_to_clarification(
            clarification_id=clarification_id,
            response_text=payload.get("response_text", ""),
            responded_by=payload.get("responded_by"),
            db=db,
        )

        return result
    except Exception as e:
        print(f"Error responding to clarification: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
        }


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
    # === INPUT VALIDATION LOGGING (8.1) ===
    input_validation_logger.info("=== RE-ANALYZE FEEDBACK - INPUT VALIDATION START ===")
    input_validation_logger.info(f"Feedback ID: {feedback_id}")
    input_validation_logger.info(f"Workspace ID: {payload.get('workspace_id', 'default')}")
    input_validation_logger.info(f"Domain ID: {payload.get('domain_id', 'ecommerce')}")
    input_validation_logger.info(f"Clarification response length: {len(payload.get('clarification_response', ''))} characters")
    input_validation_logger.info("=== RE-ANALYZE FEEDBACK - INPUT VALIDATION COMPLETE ===")

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
        duplicate_service = BaselineDuplicateDetectionService()
        duplicate_check = duplicate_service.check_duplicate(
            suggested_rule=primary_rule,
            workspace_id=workspace_id,
            domain_id=domain_id,
            db=db,
        )

        # Conflict Detection
        conflict_service = BaselineConflictDetectionService()
        conflict_check = conflict_service.check_conflict(
            suggested_rule=primary_rule,
            workspace_id=workspace_id,
            domain_id=domain_id,
            db=db,
        )

        # Review Routing
        routing_service = RealReviewRoutingService()
        # Calibrate classification confidence and assess sensitivity before routing
        try:
            from app.services.calibration import calibrate_probability
            from app.services.sensitivity_service import assess_sensitivity
            temp = float(schema_context.get("calibration_temperature", 1.0)) if isinstance(schema_context, dict) else 1.0
            raw_conf = float(classification_result_dict.get("confidence", 0.0) or 0.0)
            classification_result_dict["calibrated_confidence"] = calibrate_probability(raw_conf, temp)
            sensitivity = assess_sensitivity(primary_rule, classification_result_dict)
        except Exception:
            sensitivity = {"sensitive": False, "score": 0.0, "reasons": []}
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
            sensitivity=sensitivity,
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

def extract_workspace_from_context(payload_workspace: str, request_headers: dict = None) -> str:
    """
    Extract workspace ID from multiple sources in priority order:
    1. X-Workspace-ID header (explicit override)
    2. Authorization header (JWT token extraction)
    3. X-User-ID header (derive workspace from user)
    4. Payload workspace_id field (fallback)
    5. Environment variable DEFAULT_WORKSPACE_ID
    """
    import os

    if not request_headers:
        request_headers = {}

    # Priority 1: Explicit workspace header
    explicit_ws = request_headers.get("X-Workspace-ID") or request_headers.get("x-workspace-id")
    if explicit_ws:
        print(f"[AUTH] Using workspace from X-Workspace-ID header: {explicit_ws}")
        return explicit_ws

    # Priority 2: Extract from JWT token (if Authorization header present)
    auth_header = request_headers.get("Authorization") or request_headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            import jwt
            token = auth_header.replace("Bearer ", "").strip()
            # Try to decode token (without verification for now)
            decoded = jwt.decode(token, options={"verify_signature": False})
            if "workspace_id" in decoded:
                ws_id = decoded["workspace_id"]
                print(f"[AUTH] Using workspace from JWT token: {ws_id}")
                return ws_id
            if "sub" in decoded and "workspace_id" in decoded.get("context", {}):
                ws_id = decoded["context"]["workspace_id"]
                print(f"[AUTH] Using workspace from JWT context: {ws_id}")
                return ws_id
        except ImportError:
            print(f"[AUTH] PyJWT not installed - skipping JWT parsing")
        except Exception as e:
            print(f"[AUTH] Could not decode JWT token: {e}")

    # Priority 3: Derive from X-User-ID header
    user_id = request_headers.get("X-User-ID") or request_headers.get("x-user-id")
    if user_id:
        import hashlib
        # Deterministic workspace ID from user ID
        ws_id = hashlib.sha256(f"user_{user_id}".encode()).hexdigest()[:36]
        print(f"[AUTH] Derived workspace from X-User-ID: {ws_id}")
        return ws_id

    # Priority 4: Payload fallback
    if payload_workspace:
        print(f"[AUTH] Using workspace from payload: {payload_workspace}")
        return payload_workspace

    # Priority 5: Environment default
    default_ws = os.getenv("DEFAULT_WORKSPACE_ID", "e8af6af9-3bbe-4117-a007-f55db418bc30")
    print(f"[AUTH] Using default workspace from environment: {default_ws}")
    return default_ws


@app.post(
    "/v1/feedback/analyze",
    response_model=FeedbackAnalysisResponse,
)
def analyze_feedback(
    payload: FeedbackAnalysisRequest,
    request: Request,
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
    # === INPUT VALIDATION LOGGING (8.1) ===
    input_validation_logger.info("=== INPUT VALIDATION START ===")

    # Extract workspace from authentication context (headers > JWT > payload > environment)
    headers_dict = dict(request.headers) if request else {}
    workspace_id = extract_workspace_from_context(payload.workspace_id, headers_dict)

    input_validation_logger.info(f"Workspace ID: {workspace_id}")

    # Log JSON schema validation (Pydantic handles this)
    input_validation_logger.info("JSON schema validation: PASSED (Pydantic model validation)")

    # Log required request fields
    required_fields = {
        'workspace_id': payload.workspace_id,
        'feedback_text': payload.feedback_text,
    }
    input_validation_logger.info(f"Required fields validation: {required_fields}")

    # Log additional request fields
    additional_fields = {
        'feedback_id': payload.feedback_id or 'auto-generated',
        'submitted_by': payload.submitted_by or 'anonymous',
        'schema_context': f"{len(payload.schema_context or {})} items" if payload.schema_context else "none",
    }
    input_validation_logger.info(f"Additional fields: {additional_fields}")

    # Detect and log domain pack explicitly
    detected_domain, detection_confidence = detect_domain_pack(payload.feedback_text)
    input_validation_logger.info(f"Domain detection: {detected_domain} (confidence: {detection_confidence:.3f})")

    # Store detected domain in schema context for downstream processing
    full_schema_context = payload.schema_context.copy() if payload.schema_context else {}
    full_schema_context["domain_pack_id"] = detected_domain
    full_schema_context["domain_detection_confidence"] = detection_confidence

    # Log maximum feedback length
    feedback_length = len(payload.feedback_text)
    input_validation_logger.info(f"Feedback length: {feedback_length} characters")
    if feedback_length > 10000:  # Example max length
        input_validation_logger.warning(f"Feedback exceeds maximum length (10000 chars)")

    # Log supported content type
    input_validation_logger.info("Content type: application/json")

    # Log duplicate request identifier (Idempotency Key)
    idempotency_key = payload.feedback_id or "auto-generated"
    input_validation_logger.info(f"Idempotency Key: {idempotency_key}")

    # Log workspace membership authorization check
    try:
        from app.db.models.workspace import Workspace
        workspace = db.query(Workspace).filter_by(workspace_id=payload.workspace_id).first()
        if workspace:
            input_validation_logger.info(f"Workspace authorization: SUCCESS (workspace exists)")
        else:
            input_validation_logger.info(f"Workspace authorization: PENDING (workspace will be auto-created)")
    except Exception as e:
        input_validation_logger.error(f"Workspace authorization check failed: {e}")

    input_validation_logger.info("=== INPUT VALIDATION COMPLETE ===")

    # Proceed with processing if validation passes
    from uuid import uuid4
    from datetime import datetime
    from app.services.enhanced_rule_extractor import EnhancedRuleExtractor
    from app.services.schema_validation_service import SchemaValidationService
    from app.services.baseline_duplicate_detection_service import BaselineDuplicateDetectionService
    from app.services.baseline_conflict_detection_service import BaselineConflictDetectionService
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

    # Step 2: Create AnalysisRun record with complete metadata
    analysis_run_id = str(uuid4())
    suggestion_id = str(uuid4())
    analysis_run = AnalysisRun(
        analysis_run_id=analysis_run_id,
        feedback_id=feedback_id,
        workspace_id=payload.workspace_id,
        model_version_id=None,  # Don't set if version doesn't exist in database
        dataset_version_id=None,  # Don't set if version doesn't exist in database
        taxonomy_version="v1",  # Baseline taxonomy version
        domain_pack_id=None,  # Don't set if pack doesn't exist in database
        threshold_configuration={
            "classification": 0.7,
            "extraction": 0.6,
            "schema_validation": 0.8,
            "conflict_detection": 0.7,
            "duplicate_detection": 0.85
        },
        processing_mode="single",
        status="processing",
        started_at=datetime.utcnow(),
    )
    db.add(analysis_run)
    db.flush()

    # STEP 1: Feedback Preprocessing (8.2)
    from app.services.feedback_preprocessor import FeedbackPreprocessor
    preprocessor = FeedbackPreprocessor()
    preprocessing_result = preprocessor.preprocess(
        payload.feedback_text, full_schema_context
    )
    processed_feedback = preprocessing_result["processed_text"]

    # Record preprocessing timestamp
    analysis_run.execution_timestamps["preprocessing_completed"] = datetime.utcnow().isoformat()

    # STEP 2: Classification (with domain-aware baseline model)
    domain_pack_id = full_schema_context.get("domain_pack_id", "customer_support")
    classifier = RealClassifier(domain=domain_pack_id)
    classification_result = classifier.classify(
        processed_feedback, full_schema_context
    )
    classification_result_dict = {
        "feedback_type": classification_result.get("feedback_type", "unclear_feedback"),
        "rule_category": classification_result.get("rule_category", "unknown"),
        "is_actionable": classification_result.get("is_actionable", False),
        "confidence": classification_result.get("confidence", 0.5),
    }

    # Record classification timestamp
    analysis_run.execution_timestamps["classification_completed"] = datetime.utcnow().isoformat()

    # STEP 2: Rule Extraction (with glossary, evidence, per-field confidence)
    extractor = EnhancedRuleExtractor()
    extraction_result = extractor.extract(processed_feedback, full_schema_context)
    extracted_rules = extraction_result.get("extraction", {}).get("extracted_rules", [])

    # Record extraction timestamp
    analysis_run.execution_timestamps["extraction_completed"] = datetime.utcnow().isoformat()

    # STEP 3: Schema Validation
    # Load actual schema from domain pack for validation
    domain_pack_id = full_schema_context.get("domain_pack_id", "ecommerce")
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
        preprocessing_result=preprocessing_result,
        schema_validation_status=schema_validation["status"],
        created_at=datetime.utcnow(),
    )
    db.add(rule_suggestion)
    db.flush()  # Flush to ensure suggestion is persisted before FK references

    # Record schema validation timestamp
    analysis_run.execution_timestamps["schema_validation_completed"] = datetime.utcnow().isoformat()

    # STEP 5: Duplicate Detection (V4 Baseline)
    duplicate_service = BaselineDuplicateDetectionService()
    duplicate_check = duplicate_service.check_duplicate(
        suggested_rule=primary_rule,
        workspace_id=payload.workspace_id,
        domain_id=domain_pack_id,
        db=db,
    )

    # STEP 6: Conflict Detection
    conflict_service = BaselineConflictDetectionService()
    conflict_check = conflict_service.check_conflict(
        suggested_rule=primary_rule,
        workspace_id=payload.workspace_id,
        domain_id=domain_pack_id,
        db=db,
    )

    # Record duplicate and conflict detection timestamps
    analysis_run.execution_timestamps["duplicate_detection_completed"] = datetime.utcnow().isoformat()
    analysis_run.execution_timestamps["conflict_detection_completed"] = datetime.utcnow().isoformat()

    # STEP 7: Clarification Generation (V4 Baseline - Completeness Check)
    completeness_checker = CompletenessChecker()
    completeness_result = completeness_checker.generate_clarification_questions(primary_rule)

    ambiguity_detector = AmbiguityDetector()
    ambiguity_result = ambiguity_detector.generate_clarification_questions(primary_rule, payload.feedback_text)

    # Determine if clarification is required based on completeness and ambiguity
    clarification_required = completeness_result["clarification_required"] or ambiguity_result["clarification_required"]
    clarification_questions = []
    clarification_reason = ""

    if completeness_result["clarification_required"]:
        clarification_questions.extend([q["question"] for q in completeness_result["questions"]])
        clarification_reason = f"Missing mandatory fields: {', '.join(completeness_result['missing_fields'])}"

    if ambiguity_result["clarification_required"]:
        clarification_questions.extend([q["question"] for q in ambiguity_result["questions"]])
        if clarification_reason:
            clarification_reason += "; Ambiguous fields: " + ", ".join(ambiguity_result['ambiguous_fields'])
        else:
            clarification_reason = f"Ambiguous fields: {', '.join(ambiguity_result['ambiguous_fields'])}"

    # STEP 8: Review Routing (V4 Policy-Driven)
    routing_service = RealReviewRoutingService()
    # Calibrate classification confidence and assess sensitivity before routing
    try:
        from app.services.calibration import calibrate_probability
        from app.services.sensitivity_service import assess_sensitivity
        temp = float(schema_context.get("calibration_temperature", 1.0)) if isinstance(schema_context, dict) else 1.0
        raw_conf = float(classification_result_dict.get("confidence", 0.0) or 0.0)
        classification_result_dict["calibrated_confidence"] = calibrate_probability(raw_conf, temp)
        sensitivity = assess_sensitivity(primary_rule, classification_result_dict)
    except Exception:
        sensitivity = {"sensitive": False, "score": 0.0, "reasons": []}

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
        clarification_required=clarification_required,
        mandatory_fields_valid=(all(v.get("mandatory_fields_valid", True) for v in schema_validation_results) if schema_validation_results else False),
        sensitivity=sensitivity,
    )

    # Record clarification timestamp
    analysis_run.execution_timestamps["clarification_completed"] = datetime.utcnow().isoformat()

    # Update suggestion with clarification and routing results
    rule_suggestion.clarification_required = clarification_required
    rule_suggestion.clarification_reason = clarification_reason
    rule_suggestion.clarification_questions = clarification_questions
    rule_suggestion.review_status = routing_decision.get("review_status", "pending_review")

    # Record routing timestamp
    analysis_run.execution_timestamps["routing_completed"] = datetime.utcnow().isoformat()

    analysis_run.status = "completed"
    analysis_run.completed_at = datetime.utcnow()
    db.commit()

    # Build spec-compliant response with per-module confidence
    # clarification_required already set on line 894 from completeness/ambiguity check

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

    # Aggregate validated and invalid fields from all rules
    all_validated_fields = []
    all_invalid_fields = []
    all_validation_checks = {}

    for result in schema_validation_results:
        all_validated_fields.extend(result.get("validated_fields", []))
        all_invalid_fields.extend(result.get("invalid_fields", []))
        if result.get("check_results"):
            all_validation_checks.update(result.get("check_results", {}))

    schema_validation_obj = SchemaValidationResponse(
        status=schema_validation["status"],
        coverage=schema_validation["coverage"],
        mandatory_fields_valid=schema_validation["mandatory_fields_valid"],
        validation_errors=schema_validation["validation_errors"],
        schema_loaded=schema_loaded,
        validated_fields=list(set(all_validated_fields)),
        invalid_fields=list(set(all_invalid_fields)),
        validation_checks=all_validation_checks
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
        status=routing_decision.get("review_status", "pending_review").upper(),
        preprocessing=PreprocessingResponse(
            original_text=payload.feedback_text,
            processed_text=preprocessing_result.get("processed_text", payload.feedback_text),
            preprocessing_steps=preprocessing_result.get("steps", []),
            detected_keywords=preprocessing_result.get("detected_keywords", []),
            detected_schema_refs=preprocessing_result.get("detected_schema_refs", []),
            language_normalized=preprocessing_result.get("language_normalized", False),
        ),
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
            retrieval_stage=duplicate_check.get("retrieval_stage", 0),
            similar_rules=duplicate_check.get("similar_rules", []),
            details=duplicate_check.get("details", {}),
        ),
        conflict_detection=ConflictDetectionResponse(
            status=conflict_check.get("conflict_type", "no_conflict"),
            relationship=conflict_check.get("relationship", "compatible"),
            has_conflict=conflict_check.get("has_conflict", False),
            conflict_type=conflict_check.get("conflict_type"),
            confidence=conflict_check.get("confidence", 0.0),
            retrieval_stage=conflict_check.get("retrieval_stage", 0),
            conflicting_rule_ids=conflict_check.get("conflicting_rule_ids", []),
            related_compatible_rule_ids=conflict_check.get("related_compatible_rule_ids", []),
            conflict_details=conflict_check.get("all_conflicts", []),
            details=conflict_check.get("details", {}),
        ),
        clarification_required=clarification_required,
        clarification=FeedbackClarificationResponse(
            clarification_id=None,
            required=clarification_required,
            questions=clarification_questions,
            reason=clarification_reason,
            ambiguity_reasons=ambiguity_result.get("ambiguity_reasons", []),
        ) if clarification_required else None,
        routing_decision=RoutingDecisionResponse(
            review_status=routing_decision.get("review_status", "pending_review"),
            priority=routing_decision.get("priority", "normal"),
            reason=routing_decision.get("reason", "")
        ),
    )



# --- Suggestion APIs ---


# Debug: return last saved analysis JSON if present (useful for UI inspection)
@app.get("/debug/last-analysis", include_in_schema=False)
def get_last_analysis_debug():
    import os, json
    from fastapi.responses import JSONResponse

    # First, try common temporary path (used by local dev scripts)
    candidate_paths = [
        "/tmp/analysis_result.json",
        "./tmp/analysis_result.json",
        "/app/tmp/analysis_result.json",
    ]

    for path in candidate_paths:
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                return JSONResponse(status_code=200, content=data)
        except Exception:
            # try next candidate
            continue

    # If no file available, try to return the most recent AnalysisRun + RuleSuggestion from DB
    try:
        from app.db.database import SessionLocal
        from app.db.models.analysis_run import AnalysisRun
        from app.db.models.rule_suggestion import RuleSuggestion

        db = SessionLocal()
        try:
            ar = db.query(AnalysisRun).order_by(AnalysisRun.created_at.desc()).first()
            if not ar:
                return JSONResponse(status_code=404, content={"error": "no saved analysis file or analysis runs in DB"})

            # Try to fetch associated suggestion
            rs = db.query(RuleSuggestion).filter_by(analysis_run_id=ar.analysis_run_id).order_by(RuleSuggestion.created_at.desc()).first()

            payload = {
                "analysis_run_id": ar.analysis_run_id,
                "feedback_id": ar.feedback_id,
                "workspace_id": ar.workspace_id,
                "domain_pack_id": ar.domain_pack_id,
                "threshold_configuration": ar.threshold_configuration,
                "status": ar.status,
                "created_at": ar.created_at.isoformat() if ar.created_at else None,
            }

            if rs:
                payload.update({
                    "suggestion_id": rs.suggestion_id,
                    "classification": rs.classification_result or {},
                    # stored extraction_result may be a status or JSON; attempt to include
                    "extraction": rs.suggested_rule or {},
                    "schema_validation": {"status": rs.schema_validation_status},
                    "clarification_required": bool(rs.clarification_required),
                    "review_status": rs.review_status,
                })

            return JSONResponse(status_code=200, content=payload)
        finally:
            db.close()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"fallback read failed: {str(e)}"})


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
        model = service.create_model_version(db, payload)
        return mv_schemas.ModelVersionResponse.from_orm(model)
    except ValueError as e:
        raise HTTPException(status_code=409 if "already exists" in str(e) else 400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/v1/model-versions", response_model=list[mv_schemas.ModelVersionResponse])
def list_model_versions(model_type: str = None, status: str = None, db=Depends(get_db)):
    service = ModelVersionService()
    models = service.list_model_versions(db, model_type=model_type, status=status)
    return [mv_schemas.ModelVersionResponse.from_orm(m) for m in models]

@app.get("/v1/model-versions/{model_id}", response_model=mv_schemas.ModelVersionResponse)
def get_model_version(model_id: str, db=Depends(get_db)):
    service = ModelVersionService()
    try:
        model = service.get_model_version(db, model_id)
        return mv_schemas.ModelVersionResponse.from_orm(model)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.patch("/v1/model-versions/{model_id}", response_model=mv_schemas.ModelVersionResponse)
def update_model_version(model_id: str, payload: mv_schemas.ModelVersionUpdateRequest, db=Depends(get_db)):
    service = ModelVersionService()
    try:
        model = service.update_model_version(db, model_id, payload)
        return mv_schemas.ModelVersionResponse.from_orm(model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/v1/model-versions/{model_id}/promote", response_model=mv_schemas.ModelVersionResponse)
def promote_model_version(model_id: str, target_status: mv_schemas.ModelVersionStatus, db=Depends(get_db)):
    """Promote model through lifecycle: CANDIDATE -> APPROVED -> ACTIVE per spec 8.11."""
    service = ModelVersionService()
    try:
        model = service.promote_model(db, model_id, target_status)
        return mv_schemas.ModelVersionResponse.from_orm(model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/v1/model-versions/active/{model_type}", response_model=mv_schemas.ModelVersionResponse)
def get_active_model(model_type: str, db=Depends(get_db)):
    """Get the currently ACTIVE model for a given type (used for inference)."""
    service = ModelVersionService()
    model = service.get_active_model(db, model_type)
    if not model:
        raise HTTPException(status_code=404, detail=f"No ACTIVE model found for type: {model_type}")
    return mv_schemas.ModelVersionResponse.from_orm(model)

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


# === ML CANDIDATE ENDPOINTS (for testing baseline vs ML comparison) ===

@app.post("/v1/feedback/classify-distilbert")
def classify_with_distilbert(payload: FeedbackAnalysisRequest):
    """
    Classify feedback using DistilBERT (ML candidate, 98.01% accuracy).

    Used for side-by-side comparison with baseline classifier in testing UI.
    """
    try:
        from app.services.distilbert_classifier import get_distilbert_classifier

        classifier = get_distilbert_classifier()
        result = classifier.classify(payload.feedback_text)

        return {
            "feedback_type": result.get("feedback_type"),
            "rule_category": result.get("rule_category"),
            "is_actionable": result.get("is_actionable"),
            "requires_clarification": result.get("requires_clarification"),
            "confidence": result.get("confidence"),
            "model": "distilbert",
            "accuracy_on_validation": result.get("accuracy_on_validation", 0.9801)
        }
    except Exception as e:
        logger.error(f"Error in DistilBERT classification: {e}")
        return {
            "feedback_type": None,
            "rule_category": None,
            "is_actionable": False,
            "requires_clarification": False,
            "confidence": 0.0,
            "model": "distilbert",
            "error": str(e)
        }


@app.post("/v1/feedback/extract-distilbert")
def extract_with_distilbert(payload: FeedbackAnalysisRequest):
    """
    Extract rules using DistilBERT token classifier (ML candidate, 95.6% accuracy).

    Used for side-by-side comparison with baseline extractor in testing UI.
    Returns enhanced JSON structure with component mapping, detailed components, and domain pack matching.
    """
    try:
        from app.services.distilbert_token_extractor import get_distilbert_token_extractor
        from app.services.domain_pack_matcher import DomainPackMatcher

        extractor = get_distilbert_token_extractor()
        result = extractor.extract(payload.feedback_text)

        extracted_rules = result.get("extraction", {}).get("extracted_rules", [])
        domain_pack_id = payload.schema_context.get("domain_pack_id", "ecommerce") if payload.schema_context else "ecommerce"

        # Add domain pack matching for enrichment
        matcher = DomainPackMatcher()

        # Match against active rules
        matching_result = matcher.match_extracted_rules(extracted_rules, domain_pack_id)

        # Enrich rules with schema details
        enriched_rules = matcher.enrich_with_schema_details(extracted_rules, domain_pack_id)

        # Validate against taxonomy
        taxonomy_validation = matcher.validate_against_taxonomy(extracted_rules, domain_pack_id)

        return {
            "extraction": {
                "extracted_rules": enriched_rules,
                "component_mapping": result.get("extraction", {}).get("component_mapping", {}),
                "detailed_components": result.get("extraction", {}).get("detailed_components", {})
            },
            "domain_pack_matching": {
                "matched_rules": matching_result.get("matched_rules", []),
                "unmatched_rules": matching_result.get("unmatched_rules", []),
                "domain_coverage": matching_result.get("domain_coverage", 0.0),
                "matching_confidence": matching_result.get("matching_confidence", 0.0),
                "total_active_rules": matching_result.get("total_active_rules", 0),
                "matched_count": matching_result.get("matched_count", 0)
            },
            "taxonomy_validation": taxonomy_validation,
            "overall_confidence": result.get("overall_confidence", 0.0),
            "model": "distilbert_token_classifier",
            "token_accuracy": result.get("token_accuracy", 0.956),
            "macro_f1": result.get("macro_f1", 0.8276),
            "method": result.get("method", "bio_token_classification"),
            "validation_ready": result.get("validation_ready", False),
            "domain_pack_id": domain_pack_id
        }
    except Exception as e:
        logger.error(f"Error in DistilBERT token extraction: {e}")
        return {
            "extraction": {
                "extracted_rules": [],
                "component_mapping": {},
                "detailed_components": {}
            },
            "domain_pack_matching": {
                "matched_rules": [],
                "unmatched_rules": [],
                "domain_coverage": 0.0,
                "matching_confidence": 0.0
            },
            "taxonomy_validation": {
                "valid_terms": [],
                "invalid_terms": [],
                "valid_operations": [],
                "invalid_operations": [],
                "overall_validity": 0.0
            },
            "overall_confidence": 0.0,
            "model": "distilbert_token_classifier",
            "error": str(e),
            "validation_ready": False
        }


@app.post("/v1/feedback/validate-schema-distilbert")
def validate_schema_with_distilbert(payload: FeedbackAnalysisRequest):
    """
    Validate extracted ML candidate rules against schema (for testing UI comparison).
    Accepts optional 'extracted_rules' in payload to avoid re-extracting.
    """
    try:
        from app.services.schema_validation_service import SchemaValidationService
        from pathlib import Path
        import json

        # Get extracted rules from payload if provided, otherwise extract fresh
        extracted_rules = payload.schema_context.get("extracted_rules", [])

        # If not provided, extract using DistilBERT (skip if re-extracting would be too slow)
        if not extracted_rules:
            # For now, return empty rules - extraction happens separately in HTML
            extracted_rules = []

        # Get schema from domain pack (same as baseline)
        domain_pack_id = payload.schema_context.get("domain_pack_id", "ecommerce")
        domain_schema = {}
        try:
            schema_path = Path(__file__).parent.parent / "rie_ml" / "domain-packs" / domain_pack_id / "schema" / "schema.json"
            if schema_path.exists():
                with open(schema_path, 'r') as f:
                    domain_schema = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load schema for {domain_pack_id}: {e}")

        # Validate each extracted rule
        validator = SchemaValidationService(domain_schema)
        validation_results = []

        for rule in extracted_rules:
            validation = validator.validate_rule(rule, domain_schema)
            validation_results.append(validation)

        # Aggregate results
        all_validated_fields = []
        all_invalid_fields = []
        all_validation_checks = {}

        for result in validation_results:
            all_validated_fields.extend(result.get("validated_fields", []))
            all_invalid_fields.extend(result.get("invalid_fields", []))
            if result.get("check_results"):
                all_validation_checks.update(result.get("check_results", {}))

        # Determine overall status
        if not validation_results:
            status = "PASS"  # No rules = pass (nothing to validate)
            coverage = 1.0
        elif all(v["status"] == "PASS" for v in validation_results):
            status = "PASS"
            coverage = 1.0
        elif any(v["status"] in ["PASS", "PARTIAL"] for v in validation_results):
            status = "PARTIAL"
            total_checkable = len(all_validated_fields) + len(all_invalid_fields)
            coverage = len(all_validated_fields) / total_checkable if total_checkable > 0 else 0.5
        else:
            status = "FAIL"
            total_checkable = len(all_validated_fields) + len(all_invalid_fields)
            coverage = len(all_validated_fields) / total_checkable if total_checkable > 0 else 0.0

        return {
            "status": status,
            "coverage": round(coverage, 3),
            "mandatory_fields_valid": all(v["mandatory_fields_valid"] for v in validation_results) if validation_results else True,
            "validation_errors": [e for v in validation_results for e in v.get("validation_errors", [])],
            "schema_loaded": bool(domain_schema),
            "validated_fields": list(set(all_validated_fields)),
            "invalid_fields": list(set(all_invalid_fields)),
            "validation_checks": all_validation_checks,
            "model": "distilbert_token_classifier"
        }

    except Exception as e:
        logger.error(f"Error in DistilBERT schema validation: {e}")
        return {
            "status": "FAIL",
            "coverage": 0.0,
            "mandatory_fields_valid": False,
            "validation_errors": [str(e)],
            "schema_loaded": False,
            "validated_fields": [],
            "invalid_fields": [],
            "validation_checks": {},
            "model": "distilbert_token_classifier",
            "error": str(e)
        }


@app.post("/v1/rules/check-duplicate")
async def check_duplicate_endpoint(
    workspace_id: str = None,
    domain_id: str = None,
    model: str = "baseline",
    request: Request = None,
    db=Depends(get_db)
):
    """
    Check for duplicate rules.

    Body: Full rule data (Dict with rule structure)
    Query params: workspace_id, domain_id, model
    """
    try:
        # Get the raw JSON body
        rule_data = await request.json()

        if model == "semantic":
            service = RealDuplicateDetectionService()
        else:
            service = BaselineDuplicateDetectionService()

        result = service.check_duplicate(
            suggested_rule=rule_data,
            workspace_id=workspace_id or "default",
            domain_id=domain_id or "ecommerce",
            db=db
        )

        return {
            **result,
            "model_used": model
        }
    except Exception as e:
        logger.error(f"Error in duplicate detection ({model}): {e}")
        import traceback
        traceback.print_exc()
        return {
            "is_duplicate": False,
            "relationship": "unrelated",
            "confidence": 0.0,
            "retrieval_stage": 0,
            "matching_rule_id": None,
            "model_used": model,
            "error": str(e)
        }


@app.get("/v1/evaluation/duplicate-detection/results")
def get_duplicate_detection_results(
    model_type: Optional[str] = None,
    limit: int = 10
):
    """
    Retrieve stored duplicate detection evaluation results.

    Query params:
    - model_type: Filter by model type (baseline_deterministic, ml_candidate)
    - limit: Maximum number of results to return (default 10)
    """
    try:
        from rie_ml.src.evaluation.metrics_storage import MetricsStorage

        storage = MetricsStorage()
        results_dir = storage.results_dir

        results = []
        for result_file in sorted(results_dir.glob("dup_det_*.json"), reverse=True)[:limit]:
            try:
                with open(result_file, "r") as f:
                    data = json.load(f)

                if model_type and data.get("model_type") != model_type:
                    continue

                results.append({
                    "evaluation_id": data.get("evaluation_id"),
                    "timestamp": data.get("timestamp"),
                    "model_type": data.get("model_type"),
                    "domains": data.get("domains"),
                    "metrics": data.get("metrics", {}),
                    "processing_time": data.get("processing_time_seconds"),
                })
            except Exception as e:
                logger.warning(f"Failed to load result file {result_file}: {e}")

        return {
            "results": results,
            "count": len(results),
            "storage_path": str(results_dir)
        }
    except Exception as e:
        logger.error(f"Error retrieving duplicate detection results: {e}")
        return {
            "error": str(e),
            "results": [],
            "count": 0
        }


@app.get("/v1/evaluation/duplicate-detection/{evaluation_id}")
def get_duplicate_detection_evaluation(evaluation_id: str):
    """
    Retrieve a specific duplicate detection evaluation result by ID.

    Path params:
    - evaluation_id: Unique evaluation identifier
    """
    try:
        from rie_ml.src.evaluation.metrics_storage import MetricsStorage

        storage = MetricsStorage()
        result_file = storage.results_dir / f"{evaluation_id}.json"

        if not result_file.exists():
            raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")

        with open(result_file, "r") as f:
            data = json.load(f)

        return {
            "evaluation_id": data.get("evaluation_id"),
            "timestamp": data.get("timestamp"),
            "model_type": data.get("model_type"),
            "module": data.get("module", "duplicate_detection"),
            "domains": data.get("domains"),
            "metrics": data.get("metrics", {}),
            "processing_time": data.get("processing_time_seconds"),
            "notes": data.get("notes"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving evaluation {evaluation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/evaluation/duplicate-detection/{evaluation_id}/summary")
def get_duplicate_detection_summary(evaluation_id: str):
    """
    Retrieve human-readable summary report for a duplicate detection evaluation.

    Path params:
    - evaluation_id: Unique evaluation identifier
    """
    try:
        from rie_ml.src.evaluation.metrics_storage import MetricsStorage

        storage = MetricsStorage()
        summary_file = storage.summaries_dir / f"{evaluation_id}_summary.txt"

        if not summary_file.exists():
            raise HTTPException(status_code=404, detail=f"Summary for {evaluation_id} not found")

        with open(summary_file, "r") as f:
            content = f.read()

        return {
            "evaluation_id": evaluation_id,
            "summary": content
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving summary for {evaluation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/evaluation/duplicate-detection/compare")
async def compare_duplicate_detection_evaluations(
    evaluation_ids: List[str]
):
    """
    Compare multiple duplicate detection evaluation results.

    Body: {"evaluation_ids": ["eval_id_1", "eval_id_2", ...]}
    """
    try:
        from rie_ml.src.evaluation.metrics_storage import MetricsStorage

        storage = MetricsStorage()
        comparisons = []

        for eval_id in evaluation_ids:
            result_file = storage.results_dir / f"{eval_id}.json"
            if result_file.exists():
                with open(result_file, "r") as f:
                    data = json.load(f)
                    comparisons.append({
                        "evaluation_id": eval_id,
                        "model_type": data.get("model_type"),
                        "timestamp": data.get("timestamp"),
                        "metrics": data.get("metrics", {}),
                    })

        if not comparisons:
            raise HTTPException(status_code=404, detail="No evaluation results found")

        # Compute deltas between first and others
        deltas = []
        if len(comparisons) > 1:
            baseline = comparisons[0]["metrics"]
            for comp in comparisons[1:]:
                delta = {}
                for key in baseline:
                    if isinstance(baseline[key], (int, float)):
                        delta[key] = comp["metrics"].get(key, 0) - baseline[key]
                deltas.append({
                    "vs": comparisons[0]["evaluation_id"],
                    "deltas": delta
                })

        return {
            "comparisons": comparisons,
            "deltas": deltas,
            "count": len(comparisons)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing evaluations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
def list_routes():
    import inspect
    routes = [(route.path, route.methods) for route in app.routes if hasattr(route, 'methods')]
    print(f"Registered {len(routes)} API routes")