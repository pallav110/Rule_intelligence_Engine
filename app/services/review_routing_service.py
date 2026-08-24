# app/services/review_routing_service.py

"""Review routing service for managing suggestion reviews and routing decisions.

This service handles the routing of suggestions to appropriate reviewers based on
criteria such as classification result, schema validation status, duplicate
detection, conflict detection, and business sensitivity.
"""

from typing import List, Dict, Any, Optional
from uuid import uuid4
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.db.models.review import Review
from app.db.models.feedback import Feedback
from app.db.models.rule_suggestion import RuleSuggestion
from app.services.classifier import RealClassifier
from app.services.schema_validator import SchemaValidator
from app.services.duplicate_detection_service import RealDuplicateDetectionService
from app.services.conflict_detection_service import RealConflictDetectionService
from app.services.feedback_service import FeedbackService


class ReviewRoutingService:
    """Service for routing suggestions to appropriate reviewers."""

    def __init__(self):
        self.classifier = RealClassifier()
        self.schema_validator = SchemaValidator()
        self.duplicate_detector = RealDuplicateDetectionService()
        self.conflict_detector = RealConflictDetectionService()
        self.feedback_service = FeedbackService()
        self.logger = logging.getLogger(__name__)

    def route_suggestion(self, db: Session, feedback: Feedback,
                        classification_result: dict,
                        extracted_rules: dict,
                        schema_validation_status: str,
                        suggestion: Optional[RuleSuggestion] = None) -> str:
        """
        Route a suggestion to the appropriate reviewer.

        Args:
            db: Database session
            feedback: Feedback object
            classification_result: Classification result from classifier
            extracted_rules: Extracted rule information
            schema_validation_status: Status of schema validation
            suggestion: Optional suggestion object

        Returns:
            Suggested reviewer role or category
        """
        # 1. Check if clarification is required
        if classification_result.get('requires_clarification', False):
            return "CLARIFICATION_REQUIRED"

        # 2. Check schema validation status
        if schema_validation_status == "FAIL":
            return "MANDATORY_MANUAL_REVIEW"

        # 3. Check for duplicate detection
        if suggestion:
            duplicate_result = self.duplicate_detector.check_duplicate(
                suggested_rule=suggestion.suggested_rule,
                existing_rules=self._get_existing_rules(db, suggestion.feedback_id)
            )
            if duplicates['relationship'] == 'duplicate':
                return "REVIEWER_VERIFICATION"

        # 4. Check for conflict detection
        if suggestion:
            conflict_result = self.conflict_detector.check_conflict(
                rule=suggestion.suggested_rule,
                existing_rules=self._get_existing_rules(db, suggestion.feedback_id)
            )
            if conflict_result['relationship'] == 'conflict':
                return "SENIOR_REVIEWER"

        # 5. Check classification result
        if classification_result['classification'] == 'high_confidence':
            return "STANDARD_REVIEWER"
        elif classification_result['classification'] in ['low_confidence', 'uncertain']:
            return "MANUAL_REVIEW"

        # 6. Default routing based on business sensitivity
        if self._is_sensitive_business_rule(extracted_rules):
            return "SENIOR_REVIEWER"
        else:
            return "STANDARD_REVIEWER"

    def _get_existing_rules(self, db: Session, feedback_id: str) -> List[Dict[str, Any]]:
        """Get existing rules for a feedback ID."""
        # This would typically query the database for active rules
        # For now, we'll return empty list as placeholder
        return []

    def _is_sensitive_business_rule(self, extracted_rules: dict) -> bool:
        """Determine if a rule is sensitive business logic."""
        business_term = extracted_rules.get('business_term', '').lower()
        sensitive_terms = ['revenue', 'margin', 'pricing', 'pricing_strategy', 'discount']
        return any(term in business_term for term in sensitive_terms)