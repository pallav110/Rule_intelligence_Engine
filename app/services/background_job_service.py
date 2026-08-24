from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.background_job import BackgroundJob
from app.db.models.workspace import Workspace


class BackgroundJobService:
    def create_workspace(
        self,
        db: Session,
        name: str,
    ) -> Workspace:
        workspace = Workspace(
            workspace_id=str(uuid4()),
            name=name,
        )

        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        return workspace

    def create_job(
        self,
        db: Session,
        workspace_id: str,
        job_type: str,
        idempotency_key: str,
    ) -> BackgroundJob:
        workspace = db.get(Workspace, workspace_id)

        if workspace is None:
            raise ValueError(
                f"Workspace not found: {workspace_id}"
            )

        existing_job = db.scalar(
            select(BackgroundJob).where(
                BackgroundJob.workspace_id == workspace_id,
                BackgroundJob.idempotency_key == idempotency_key,
            )
        )

        if existing_job is not None:
            return existing_job

        job = BackgroundJob(
            job_id=str(uuid4()),
            workspace_id=workspace_id,
            job_type=job_type,
            status="pending",
            idempotency_key=idempotency_key,
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        return job

    def get_job(
        self,
        db: Session,
        job_id: str,
    ) -> BackgroundJob | None:
        return db.get(BackgroundJob, job_id)
