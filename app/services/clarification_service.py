"""Clarification service for managing unclear feedback.

Generates clarification questions and manages clarification lifecycle.
"""

from datetime import datetime
from uuid import uuid4
from typing import Optional, List
from sqlalchemy.orm import Session

from app.db.models.clarification import Clarification
import sys
from pathlib import Path

# Add rie_ml to path
rie_ml_path = Path(__file__).parent.parent.parent / "rie_ml"
sys.path.insert(0, str(rie_ml_path))

from src.clarification import ClarificationGenerator


class ClarificationService:
    """Service for managing clarifications."""

    def __init__(self):
        self.generator = ClarificationGenerator(confidence_threshold=0.6)

    def create_clarification(
        self,
        db: Session,
        feedback_id: str,
        classification: dict,
        extraction: dict,
    ) -> Optional[Clarification]:
        """Create a clarification request if needed."""
        result = self.generator.generate("", classification, extraction)

        if not result["needs_clarification"]:
            return None

        clarification_id = str(uuid4())

        clarification = Clarification(
            clarification_id=clarification_id,
            feedback_id=feedback_id,
            questions=result["questions"],
            reason=result["reason"],
            status="pending",
            created_at=datetime.utcnow(),
        )

        db.add(clarification)
        db.commit()
        db.refresh(clarification)

        return clarification

    def get_clarification(
        self,
        db: Session,
        clarification_id: str,
    ) -> Optional[Clarification]:
        """Get a clarification by ID."""
        return db.query(Clarification).filter(
            Clarification.clarification_id == clarification_id
        ).first()

    def respond_to_clarification(
        self,
        db: Session,
        clarification_id: str,
        response: str,
    ) -> Clarification:
        """Respond to a clarification request."""
        clarification = self.get_clarification(db, clarification_id)

        if clarification is None:
            raise ValueError(f"Clarification not found: {clarification_id}")

        if clarification.status != "pending":
            raise ValueError(f"Cannot respond to clarification with status: {clarification.status}")

        clarification.response = response
        clarification.status = "responded"
        clarification.responded_at = datetime.utcnow()

        db.commit()
        db.refresh(clarification)

        return clarification

    def list_clarifications(
        self,
        db: Session,
        feedback_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Clarification]:
        """List clarifications with optional filters."""
        query = db.query(Clarification)

        if feedback_id:
            query = query.filter(Clarification.feedback_id == feedback_id)

        if status:
            query = query.filter(Clarification.status == status)

        return query.order_by(Clarification.created_at.desc()).all()