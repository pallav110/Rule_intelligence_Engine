from app.db.database import SessionLocal
from app.db.models.background_job import BackgroundJob
from app.worker import celery_app
from app.services.feedback_service import FeedbackService


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

        feedback_service = FeedbackService()

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

@celery_app.task(
    name="evaluations.run_evaluation_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def run_evaluation_task(self, evaluation_run_id: str):
    import time, uuid, json
    from datetime import datetime
    from app.db.database import SessionLocal
    from app.db.models.evaluation_run import EvaluationRun
    from app.db.models.evaluation_metric import EvaluationMetric

    db = SessionLocal()
    try:
        run = db.get(EvaluationRun, evaluation_run_id)
        if not run:
            return {"status": "failed", "error": "Not found"}

        run.status = "running"
        run.started_at = datetime.utcnow()
        db.commit()

        # Mock long-running evaluation ML
        time.sleep(2)

        # Emit mock metrics
        db.add(EvaluationMetric(
            metric_id=str(uuid.uuid4()),
            evaluation_run_id=evaluation_run_id,
            metric_name="accuracy",
            metric_value=0.92,
            metric_details={}
        ))

        db.add(EvaluationMetric(
            metric_id=str(uuid.uuid4()),
            evaluation_run_id=evaluation_run_id,
            metric_name="f1_score",
            metric_value=0.88,
            metric_details={"precision": 0.89, "recall": 0.87}
        ))

        run.status = "completed"
        run.completed_at = datetime.utcnow()
        db.commit()

        return {"status": "completed", "evaluation_run_id": evaluation_run_id}

    except Exception as e:
        db.rollback()
        run = db.get(EvaluationRun, evaluation_run_id)
        if run:
            run.status = "failed"
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(
    name="retention.cleanup",
    bind=True,
)
def retention_cleanup_task(self):
    """
    Periodic task to run data retention cleanup.
    """
    from app.services.retention_service import RetentionService

    service = RetentionService()
    result = service.run_retention_cleanup()

    if not result.get("success"):
        # Log the error but don't retry automatically for retention cleanup
        # as it might be a configuration issue
        logger = self.get_logger()
        logger.error(f"Retention cleanup failed: {result.get('error')}")

    return result
