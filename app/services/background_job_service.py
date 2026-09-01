from sqlalchemy.orm import Session
from app.db.models.background_job import BackgroundJob

class BackgroundJobService:
    def get_job(self, db: Session, workspace_id: str, job_id: str) -> BackgroundJob:
        """Fetch a background job by ID, ensuring it belongs to the specified workspace."""
        job = db.query(BackgroundJob).filter(
            BackgroundJob.job_id == job_id,
            BackgroundJob.workspace_id == workspace_id
        ).first()

        if not job:
            raise ValueError(f"Job not found: {job_id}")

        return job
