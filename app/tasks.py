from app.db.database import SessionLocal
from app.db.models.background_job import BackgroundJob
from app.worker import celery_app
from app.services.feedback_service import FeedbackService
from app.services.feedback_preprocessor import FeedbackPreprocessor
from app.services.domain_pack_loader import DomainPackLoader
from app.services.classifier import MockClassifier
from app.services.rule_extractor import MockRuleExtractor
from app.services.schema_validator import SchemaValidator
from app.services.canonical_rule_service import CanonicalRuleService


@celery_app.task(
    name="jobs.process_background_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_background_job(
    self,
    job_id: str,
    feedback_rows: list[str] | None = None,
    domain_pack_id: str | None = None,
):
    db = SessionLocal()

    try:
        job = db.get(BackgroundJob, job_id)

        if job is None:
            return {
                "job_id": job_id,
                "status": "failed",
                "error": "Job not found",
            }

        job.status = "running"
        db.commit()

        # Existing generic background job.
        if feedback_rows is None:
            job.status = "completed"
            db.commit()

            return {
                "job_id": job_id,
                "status": "completed",
            }

        feedback_service = FeedbackService(
            preprocessor=FeedbackPreprocessor(),
            domain_loader=DomainPackLoader(),
            classifier=MockClassifier(),
            extractor=MockRuleExtractor(),
            validator=SchemaValidator(),
            canonical_rule_service=CanonicalRuleService(),
        )

        for feedback in feedback_rows:
            feedback_service.analyze(
                db=db,
                workspace_id=job.workspace_id,
                feedback=feedback,
                domain=domain_pack_id,
                processing_mode="batch",
            )

        job.status = "completed"
        db.commit()

        return {
            "job_id": job_id,
            "status": "completed",
            "total_rows": len(feedback_rows),
        }

    except Exception:
        db.rollback()

        job = db.get(BackgroundJob, job_id)

        if job is not None:
            job.status = "failed"
            db.commit()

        raise

    finally:
        db.close()