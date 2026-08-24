"""Review routing service for assigning suggestions to reviewers.

Manages the review workflow and assignment logic.
"""

from datetime import datetime
from uuid import uuid4
from typing import Optional, List
from sqlalchemy.orm import Session

from app.db.models.review import Review
from app.db.models.rule_suggestion import RuleSuggestion


class ReviewRoutingService:
    """Service for managing review routing and assignments."""

    def create_review(
        self,
        db: Session,
        suggestion_id: str,
        reviewer_id: Optional[str] = None,
        priority: str = "normal",
    ) -> Review:
        """Create a review assignment for a suggestion."""
        # Verify suggestion exists
        suggestion = db.query(RuleSuggestion).filter(
            RuleSuggestion.suggestion_id == suggestion_id
        ).first()

        if suggestion is None:
            raise ValueError(f"Suggestion not found: {suggestion_id}")

        if suggestion.status != "pending_review":
            raise ValueError(f"Cannot create review for suggestion with status: {suggestion.status}")

        review_id = str(uuid4())

        review = Review(
            review_id=review_id,
            suggestion_id=suggestion_id,
            reviewer_id=reviewer_id,
            status="pending",
            priority=priority,
            assigned_at=datetime.utcnow(),
        )

        db.add(review)
        db.commit()
        db.refresh(review)

        return review

    def get_review(
        self,
        db: Session,
        review_id: str,
    ) -> Optional[Review]:
        """Get a review by ID."""
        return db.query(Review).filter(
            Review.review_id == review_id
        ).first()

    def complete_review(
        self,
        db: Session,
        review_id: str,
        decision: str,
        notes: Optional[str] = None,
    ) -> Review:
        """Complete a review with a decision."""
        review = self.get_review(db, review_id)

        if review is None:
            raise ValueError(f"Review not found: {review_id}")

        if review.status != "pending":
            raise ValueError(f"Cannot complete review with status: {review.status}")

        if decision not in ["approved", "rejected"]:
            raise ValueError(f"Invalid decision: {decision}")

        review.status = "completed"
        review.decision = decision
        review.notes = notes
        review.completed_at = datetime.utcnow()

        # Update suggestion status
        suggestion = db.query(RuleSuggestion).filter(
            RuleSuggestion.suggestion_id == review.suggestion_id
        ).first()

        if suggestion:
            suggestion.status = decision
            if decision == "rejected":
                suggestion.rejection_reason = notes

        db.commit()
        db.refresh(review)

        return review

    def list_reviews(
        self,
        db: Session,
        reviewer_id: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[Review]:
        """List reviews with optional filters."""
        query = db.query(Review)

        if reviewer_id:
            query = query.filter(Review.reviewer_id == reviewer_id)

        if status:
            query = query.filter(Review.status == status)

        if priority:
            query = query.filter(Review.priority == priority)

        return query.order_by(Review.assigned_at.desc()).all()

    def assign_reviewer(
        self,
        db: Session,
        review_id: str,
        reviewer_id: str,
    ) -> Review:
        """Assign or reassign a reviewer to a review."""
        review = self.get_review(db, review_id)

        if review is None:
            raise ValueError(f"Review not found: {review_id}")

        if review.status != "pending":
            raise ValueError(f"Cannot reassign review with status: {review.status}")

        review.reviewer_id = reviewer_id

        db.commit()
        db.refresh(review)

        return review