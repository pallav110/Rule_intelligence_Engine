"""Suggestion lifecycle management service with full status transitions and audit history."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from uuid import uuid4
from enum import Enum


class SuggestionStatus(str, Enum):
    """Suggestion lifecycle statuses."""
    RECEIVED = "received"
    VALIDATED = "validated"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    ANALYZED = "analyzed"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    RULE_CREATED = "rule_created"
    RULE_ACTIVATED = "rule_activated"
    ARCHIVED = "archived"


class SuggestionLifecycleService:
    """Manages suggestion lifecycle with status transitions and audit history."""

    # Valid status transitions
    VALID_TRANSITIONS = {
        SuggestionStatus.RECEIVED: [SuggestionStatus.VALIDATED, SuggestionStatus.REJECTED],
        SuggestionStatus.VALIDATED: [SuggestionStatus.CLASSIFIED, SuggestionStatus.REJECTED],
        SuggestionStatus.CLASSIFIED: [SuggestionStatus.EXTRACTED, SuggestionStatus.REJECTED],
        SuggestionStatus.EXTRACTED: [SuggestionStatus.ANALYZED, SuggestionStatus.REJECTED],
        SuggestionStatus.ANALYZED: [SuggestionStatus.PENDING_REVIEW, SuggestionStatus.REJECTED],
        SuggestionStatus.PENDING_REVIEW: [SuggestionStatus.APPROVED, SuggestionStatus.REJECTED],
        SuggestionStatus.APPROVED: [SuggestionStatus.RULE_CREATED],
        SuggestionStatus.REJECTED: [SuggestionStatus.ARCHIVED],
        SuggestionStatus.RULE_CREATED: [SuggestionStatus.RULE_ACTIVATED],
        SuggestionStatus.RULE_ACTIVATED: [SuggestionStatus.ARCHIVED],
    }

    def __init__(self):
        """Initialize lifecycle service."""
        pass

    def transition_status(
        self,
        suggestion_id: str,
        from_status: str,
        to_status: str,
        transitioned_by: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db=None,
    ) -> Dict[str, Any]:
        """
        Transition suggestion status with validation and audit trail.

        Args:
            suggestion_id: Suggestion identifier
            from_status: Current status
            to_status: Target status
            transitioned_by: User/system performing transition
            reason: Optional reason for transition
            metadata: Optional metadata (e.g., reviewer comments, rule_id)
            db: Database session

        Returns:
            {success: bool, suggestion_id: str, from_status: str, to_status: str, audit_entry_id: str}
        """
        try:
            # Validate transition
            if not self._is_valid_transition(from_status, to_status):
                return {
                    "success": False,
                    "error": f"Invalid transition from {from_status} to {to_status}",
                    "valid_transitions": self.VALID_TRANSITIONS.get(from_status, []),
                }

            if not db:
                return {
                    "success": False,
                    "error": "Database connection required",
                }

            from app.db.models.rule_suggestion import RuleSuggestion
            from app.db.models.suggestion_audit import SuggestionAudit

            # Get suggestion
            suggestion = db.query(RuleSuggestion).filter_by(suggestion_id=suggestion_id).first()
            if not suggestion:
                return {
                    "success": False,
                    "error": f"Suggestion {suggestion_id} not found",
                }

            # Verify current status matches
            if suggestion.review_status != from_status:
                return {
                    "success": False,
                    "error": f"Status mismatch: expected {from_status}, actual {suggestion.review_status}",
                }

            # Create audit entry
            audit_entry_id = str(uuid4())
            audit = SuggestionAudit(
                audit_id=audit_entry_id,
                suggestion_id=suggestion_id,
                from_status=from_status,
                to_status=to_status,
                transitioned_by=transitioned_by,
                transition_reason=reason,
                audit_metadata=metadata or {},
                created_at=datetime.now(timezone.utc),
            )
            db.add(audit)

            # Update suggestion status
            suggestion.review_status = to_status
            suggestion.updated_at = datetime.now(timezone.utc)

            # Update reviewer info if approved/rejected
            if to_status in [SuggestionStatus.APPROVED, SuggestionStatus.REJECTED]:
                suggestion.reviewed_by = transitioned_by
                suggestion.reviewed_at = datetime.now(timezone.utc)

            db.commit()

            return {
                "success": True,
                "suggestion_id": suggestion_id,
                "from_status": from_status,
                "to_status": to_status,
                "audit_entry_id": audit_entry_id,
                "transitioned_by": transitioned_by,
                "transitioned_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            if db:
                db.rollback()
            return {
                "success": False,
                "error": str(e),
            }

    def get_audit_history(
        self,
        suggestion_id: str,
        db=None,
    ) -> Dict[str, Any]:
        """
        Get complete audit history for a suggestion.

        Returns:
            {suggestion_id: str, history: List[audit_entry], total_transitions: int}
        """
        if not db:
            return {
                "success": False,
                "error": "Database connection required",
            }

        try:
            from app.db.models.suggestion_audit import SuggestionAudit

            audits = (
                db.query(SuggestionAudit)
                .filter_by(suggestion_id=suggestion_id)
                .order_by(SuggestionAudit.created_at.asc())
                .all()
            )

            history = [
                {
                    "audit_id": audit.audit_id,
                    "from_status": audit.from_status,
                    "to_status": audit.to_status,
                    "transitioned_by": audit.transitioned_by,
                    "transition_reason": audit.transition_reason,
                    "metadata": audit.metadata,
                    "created_at": audit.created_at.isoformat(),
                }
                for audit in audits
            ]

            return {
                "success": True,
                "suggestion_id": suggestion_id,
                "history": history,
                "total_transitions": len(history),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _is_valid_transition(self, from_status: str, to_status: str) -> bool:
        """Check if status transition is valid."""
        try:
            from_enum = SuggestionStatus(from_status)
            to_enum = SuggestionStatus(to_status)
            return to_enum in self.VALID_TRANSITIONS.get(from_enum, [])
        except ValueError:
            return False

    def get_current_status(
        self,
        suggestion_id: str,
        db=None,
    ) -> Dict[str, Any]:
        """Get current status and lifecycle position."""
        if not db:
            return {
                "success": False,
                "error": "Database connection required",
            }

        try:
            from app.db.models.rule_suggestion import RuleSuggestion

            suggestion = db.query(RuleSuggestion).filter_by(suggestion_id=suggestion_id).first()
            if not suggestion:
                return {
                    "success": False,
                    "error": f"Suggestion {suggestion_id} not found",
                }

            current_status = suggestion.review_status
            valid_next_statuses = self.VALID_TRANSITIONS.get(SuggestionStatus(current_status), [])

            return {
                "success": True,
                "suggestion_id": suggestion_id,
                "current_status": current_status,
                "valid_next_statuses": [status.value for status in valid_next_statuses],
                "created_at": suggestion.created_at.isoformat() if suggestion.created_at else None,
                "updated_at": suggestion.updated_at.isoformat() if suggestion.updated_at else None,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
