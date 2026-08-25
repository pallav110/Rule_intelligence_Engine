from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models.analysis_run import AnalysisRun
from app.db.models.feedback import Feedback
from app.schemas.feedback import FeedbackAnalysisResponse
from app.services.domain_pack_loader import DomainPackLoader, DomainPackNotFoundError
from app.services.suggestion_service import SuggestionService


class FeedbackService:
    def __init__(self):
        self.domain_loader = DomainPackLoader()
        self.suggestion_service = SuggestionService()

    def analyze(
        self,
        db: Session,
        workspace_id: str,
        feedback: str,
        domain: str | None = None,
        processing_mode: str = "single",
        feedback_id: str | None = None,
        submitted_by: str | None = None,
        schema_context: dict | None = None,
    ) -> FeedbackAnalysisResponse:
        """Deprecated: Use app/main.py analyze_feedback endpoint instead."""
        feedback_id = feedback_id or str(uuid4())
        analysis_run_id = str(uuid4())
        schema_context = schema_context or {}
        domain_pack_id = domain or schema_context.get("domain_pack_id", "customer_support")

        feedback_record = Feedback(
            feedback_id=feedback_id,
            workspace_id=workspace_id,
            feedback_text=feedback,
            submitted_by=submitted_by,
            processing_status="processing",
        )
        db.add(feedback_record)
        db.flush()

        analysis_run = AnalysisRun(
            analysis_run_id=analysis_run_id,
            feedback_id=feedback_id,
            workspace_id=workspace_id,
            domain_pack_id=domain_pack_id,
            processing_mode=processing_mode,
            status="processing",
            started_at=datetime.utcnow(),
        )
        db.add(analysis_run)
        db.flush()

        try:
            domain_pack = self.domain_loader.load(domain_pack_id)
        except DomainPackNotFoundError:
            domain_pack = {}

        extract_result = self.suggestion_service.extract(
            feedback=feedback,
            domain_context=schema_context,
        )
        classification = extract_result["classification"]
        extraction = extract_result.get("extraction", {})
        extracted_rules = extraction.get("rules", []) if isinstance(extraction, dict) else []

        feedback_record.processing_status = "processed"
        analysis_run.status = "completed"
        analysis_run.completed_at = datetime.utcnow()
        db.commit()

        return FeedbackAnalysisResponse(
            feedback_id=feedback_id,
            suggestion_id=str(uuid4()),
            status="PENDING_REVIEW",
            classification={
                "feedback_type": classification.get("feedback_type", "unknown"),
                "rule_category": classification.get("rule_category"),
                "actionability": classification.get("is_actionable", False),
                "confidence": classification.get("confidence", 0.0),
            },
            extraction={
                "rules": extracted_rules,
                "confidence": extraction.get("extraction_confidence", 0.0),
                "evidence": extraction.get("evidence", ""),
            },
            schema_validation={
                "status": "PASS",
                "coverage": 1.0,
                "mandatory_fields_valid": True,
                "validation_errors": [],
            },
            duplicate_detection={
                "status": "none",
                "relationship": "unrelated",
                "similar_rules": [],
            },
            conflict_detection={
                "status": "no_conflict",
                "relationship": "compatible",
                "conflicting_rules": [],
            },
            routing_decision={
                "review_status": "pending_review",
                "priority": "normal",
                "reason": "",
            },
        )
