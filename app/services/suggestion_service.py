"""Suggestion service for managing rule suggestions lifecycle.

Handles creation, approval, rejection, and listing of rule suggestions.
Integrates with rule extraction to process feedback into suggestions.
"""

from datetime import datetime
from uuid import uuid4
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.db.models.rule_suggestion import RuleSuggestion
from app.db.models.feedback import Feedback
from app.services.rule_extractor import RealRuleExtractor
from app.services.classifier import RealClassifier


class SuggestionService:
    """Service for managing rule suggestions."""

    def __init__(self):
        """Initialize suggestion service with extractors."""
        self.classifier = RealClassifier()
        self.extractor = RealRuleExtractor()

    def extract(
        self,
        feedback: str,
        domain_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extract rules from feedback text using classification and extraction pipeline.

        Parameters
        ----------
        feedback: str
            Raw feedback text to process
        domain_context: dict | None
            Optional context with available_tables, available_columns, etc.

        Returns
        -------
        dict
            Contains:
            - suggested_rule: extracted rule structure
            - confidence: overall confidence score
            - classification: classification result
            - extraction: extraction result
        """
        # Prepare schema context
        schema_context = domain_context or {
            "available_tables": [],
            "available_columns": [],
        }

        # Classify the feedback
        classification_result = self.classifier.classify(feedback, schema_context)

        # Extract rules from feedback
        extraction_result = self.extractor.extract(
            feedback,
            classification_result,
            schema_context
        )

        # Build suggested rule from extraction
        suggested_rule = None
        confidence = extraction_result.confidence

        if extraction_result.rules:
            rule = extraction_result.rules[0]  # Take first rule
            suggested_rule = {
                "business_term": rule.get("business_term"),
                "operation": rule.get("operation"),
                "conditions": rule.get("conditions", []),
                "scope": rule.get("scope", "global"),
                "time_window": rule.get("time_window"),
                "threshold": rule.get("threshold"),
                "affected_entities": rule.get("affected_entities", {}),
                "feedback_type": classification_result.feedback_type,
                "rule_category": classification_result.rule_category,
            }

        return {
            "suggested_rule": suggested_rule,
            "confidence": confidence,
            "classification": {
                "feedback_type": classification_result.feedback_type,
                "rule_category": classification_result.rule_category,
                "is_actionable": classification_result.is_actionable,
                "requires_clarification": classification_result.requires_clarification,
                "confidence": classification_result.confidence,
            },
            "extraction": {
                "rules": extraction_result.rules,
                "confidence": extraction_result.confidence,
            }
        }

    def create_suggestion(
        self,
        db: Session,
        workspace_id: str,
        feedback_id: str,
        suggested_rule: dict,
        confidence: float,
    ) -> RuleSuggestion:
        """Create a new rule suggestion."""
        suggestion_id = str(uuid4())

        suggestion = RuleSuggestion(
            suggestion_id=suggestion_id,
            workspace_id=workspace_id,
            feedback_id=feedback_id,
            suggested_rule=suggested_rule,
            status="pending_review",
            confidence_score=confidence,
            created_at=datetime.utcnow(),
        )

        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)

        return suggestion

    def get_suggestion(
        self,
        db: Session,
        suggestion_id: str,
    ) -> Optional[RuleSuggestion]:
        """Get a suggestion by ID."""
        return db.query(RuleSuggestion).filter(
            RuleSuggestion.suggestion_id == suggestion_id
        ).first()

    def approve_suggestion(
        self,
        db: Session,
        suggestion_id: str,
        reviewer_id: Optional[str] = None,
    ) -> RuleSuggestion:
        """Approve a suggestion."""
        suggestion = self.get_suggestion(db, suggestion_id)

        if suggestion is None:
            raise ValueError(f"Suggestion not found: {suggestion_id}")

        if suggestion.status != "pending_review":
            raise ValueError(f"Cannot approve suggestion with status: {suggestion.status}")

        suggestion.status = "approved"
        suggestion.reviewed_by = reviewer_id
        suggestion.reviewed_at = datetime.utcnow()

        db.commit()
        db.refresh(suggestion)

        return suggestion

    def reject_suggestion(
        self,
        db: Session,
        suggestion_id: str,
        reviewer_id: Optional[str] = None,
        rejection_reason: Optional[str] = None,
    ) -> RuleSuggestion:
        """Reject a suggestion."""
        suggestion = self.get_suggestion(db, suggestion_id)

        if suggestion is None:
            raise ValueError(f"Suggestion not found: {suggestion_id}")

        if suggestion.status != "pending_review":
            raise ValueError(f"Cannot reject suggestion with status: {suggestion.status}")

        suggestion.status = "rejected"
        suggestion.reviewed_by = reviewer_id
        suggestion.reviewed_at = datetime.utcnow()
        suggestion.rejection_reason = rejection_reason

        db.commit()
        db.refresh(suggestion)

        return suggestion

    def list_suggestions(
        self,
        db: Session,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[RuleSuggestion]:
        """List suggestions with optional filters."""
        query = db.query(RuleSuggestion)

        if workspace_id:
            query = query.filter(RuleSuggestion.workspace_id == workspace_id)

        if status:
            query = query.filter(RuleSuggestion.status == status)

        return query.order_by(RuleSuggestion.created_at.desc()).all()