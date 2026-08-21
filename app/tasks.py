from app.db.database import SessionLocal
from app.db.models.background_job import BackgroundJob
from app.worker import celery_app


@celery_app.task(
    name="jobs.process_background_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_background_job(self, job_id: str):
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

        # Placeholder for the actual background workload.
        # This will later call the real analysis pipeline.

        job.status = "completed"
        db.commit()

        return {
            "job_id": job_id,
            "status": "completed",
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()