from app.db.database import SessionLocal
from app.db.models.background_job import BackgroundJob
from app.worker import celery_app


@celery_app.task(
    name="jobs.process_background_job"
)
def process_background_job(job_id: str):
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
        job = db.get(BackgroundJob, job_id)

        if job is not None:
            job.status = "failed"
            db.commit()

        raise

    finally:
        db.close()
