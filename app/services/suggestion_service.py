"""Suggestion service for managing rule suggestions lifecycle.

Handles creation, approval, rejection, and listing of rule suggestions.
"""

from datetime import datetime
from uuid import uuid4
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models.rule_suggestion import RuleSuggestion
from app.db.models.feedback import Feedback


class SuggestionService:
    """Service for managing rule suggestions."""

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