"""Data retention and deletion service for Spec §10.7.

Implements configurable data retention policies for:
- Feedback
- Suggestions
- Background Jobs
- Evaluation Results (handled via version control, not deletion)
- Audit History (long-term retention, not deleted)

Expired records may be archived or permanently deleted according to organizational policies.
Deletion operations are recorded within the Audit History repository.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.db.database import SessionLocal
from app.db.models.feedback import Feedback
from app.db.models.rule_suggestion import RuleSuggestion
from app.db.models.background_job import BackgroundJob
from app.db.models.audit_history import AuditHistory
from app.config import settings
from app.logging_config import get_logger

logger = get_logger('retention_service')


class RetentionService:
    """Service for managing data retention and deletion policies."""

    def __init__(self):
        """Initialize retention service with configuration."""
        self.feedback_retention_days = settings.RETENTION_FEEDBACK_DAYS
        self.suggestions_retention_days = settings.RETENTION_SUGGESTIONS_DAYS
        self.background_jobs_retention_days = settings.RETENTION_BACKGROUND_JOBS_DAYS
        self.audit_history_long_term = settings.RETENTION_AUDIT_HISTORY_LONG_TERM
        self.evaluation_results_version_controlled = settings.RETENTION_EVALUATION_RESULTS_VERSION_CONTROLLED

    def cleanup_expired_feedback(self, db=None) -> Dict[str, Any]:
        """
        Delete feedback older than the retention period.

        Args:
            db: Database session (optional, will create one if not provided)

        Returns:
            Dict with count of deleted feedback and any errors
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.feedback_retention_days)

            # Query for expired feedback
            expired_feedback = db.query(Feedback).filter(
                Feedback.created_at < cutoff_date
            ).all()

            count = len(expired_feedback)

            # Record deletion in audit history before deleting
            for feedback in expired_feedback:
                self._record_deletion_audit(
                    db=db,
                    entity_type="feedback",
                    entity_id=feedback.feedback_id,
                    action="delete_expired",
                    details={"retention_days": self.feedback_retention_days}
                )
                db.delete(feedback)

            db.commit()

            logger.info(f"Deleted {count} expired feedback records older than {self.feedback_retention_days} days")

            return {
                "success": True,
                "deleted_count": count,
                "entity_type": "feedback",
                "retention_days": self.feedback_retention_days
            }

        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"Error deleting expired feedback: {e}")
            return {
                "success": False,
                "error": str(e),
                "entity_type": "feedback"
            }
        finally:
            if close_db:
                db.close()

    def cleanup_expired_suggestions(self, db=None) -> Dict[str, Any]:
        """
        Delete suggestions older than the retention period.
        Only suggestions in terminal states (approved, rejected, archived) are eligible for deletion.

        Args:
            db: Database session (optional, will create one if not provided)

        Returns:
            Dict with count of deleted suggestions and any errors
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.suggestions_retention_days)

            # Query for expired suggestions in terminal states
            terminal_states = ['approved', 'rejected', 'archived', 'rule_activated']
            expired_suggestions = db.query(RuleSuggestion).filter(
                RuleSuggestion.created_at < cutoff_date,
                RuleSuggestion.review_status.in_(terminal_states)
            ).all()

            count = len(expired_suggestions)

            # Record deletion in audit history before deleting
            for suggestion in expired_suggestions:
                self._record_deletion_audit(
                    db=db,
                    entity_type="rule_suggestion",
                    entity_id=suggestion.suggestion_id,
                    action="delete_expired",
                    details={
                        "retention_days": self.suggestions_retention_days,
                        "final_status": suggestion.review_status
                    }
                )
                db.delete(suggestion)

            db.commit()

            logger.info(f"Deleted {count} expired suggestions older than {self.suggestions_retention_days} days")

            return {
                "success": True,
                "deleted_count": count,
                "entity_type": "rule_suggestion",
                "retention_days": self.suggestions_retention_days
            }

        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"Error deleting expired suggestions: {e}")
            return {
                "success": False,
                "error": str(e),
                "entity_type": "rule_suggestion"
            }
        finally:
            if close_db:
                db.close()

    def cleanup_expired_background_jobs(self, db=None) -> Dict[str, Any]:
        """
        Delete background job records older than the retention period.

        Args:
            db: Database session (optional, will create one if not provided)

        Returns:
            Dict with count of deleted background jobs and any errors
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.background_jobs_retention_days)

            # Query for expired background jobs
            expired_jobs = db.query(BackgroundJob).filter(
                BackgroundJob.created_at < cutoff_date
            ).all()

            count = len(expired_jobs)

            # Record deletion in audit history before deleting
            for job in expired_jobs:
                self._record_deletion_audit(
                    db=db,
                    entity_type="background_job",
                    entity_id=job.job_id,
                    action="delete_expired",
                    details={"retention_days": self.background_jobs_retention_days}
                )
                db.delete(job)

            db.commit()

            logger.info(f"Deleted {count} expired background jobs older than {self.background_jobs_retention_days} days")

            return {
                "success": True,
                "deleted_count": count,
                "entity_type": "background_job",
                "retention_days": self.background_jobs_retention_days
            }

        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"Error deleting expired background jobs: {e}")
            return {
                "success": False,
                "error": str(e),
                "entity_type": "background_job"
            }
        finally:
            if close_db:
                db.close()

    def run_retention_cleanup(self) -> Dict[str, Any]:
        """
        Run all retention cleanup policies.

        Returns:
            Dict with results of all cleanup operations
        """
        logger.info("Starting retention cleanup process")

        results = {
            "feedback": self.cleanup_expired_feedback(),
            "suggestions": self.cleanup_expired_suggestions(),
            "background_jobs": self.cleanup_expired_background_jobs()
        }

        # Log summary
        total_deleted = sum(
            result.get("deleted_count", 0)
            for result in results.values()
            if result.get("success")
        )

        logger.info(f"Retention cleanup completed. Total deleted: {total_deleted}")

        return {
            "success": True,
            "results": results,
            "total_deleted": total_deleted
        }

    def _record_deletion_audit(
        self,
        db,
        entity_type: str,
        entity_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a deletion operation in the audit history.

        Args:
            db: Database session
            entity_type: Type of entity being deleted
            entity_id: ID of the entity being deleted
            action: Action being performed (e.g., 'delete_expired')
            details: Additional details about the deletion
        """
        try:
            audit_entry = AuditHistory(
                audit_id=str(uuid4()),
                workspace_id=None,  # System-level operation
                actor_id="retention_service",
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details or {},
                created_at=datetime.now(timezone.utc)
            )
            db.add(audit_entry)
            # Note: We don't commit here; the caller is responsible for committing
        except Exception as e:
            logger.error(f"Failed to record deletion audit for {entity_type} {entity_id}: {e}")
            # Don't raise here as we don't want audit failures to prevent deletion