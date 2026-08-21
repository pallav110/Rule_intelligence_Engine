from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.model_version import ModelVersion
from app.schemas.model_version import ModelVersionStatus


class ModelVersionService:
    def create(
        self,
        db: Session,
        model_name: str,
        version: str,
    ) -> ModelVersion:
        existing = db.scalar(
            select(ModelVersion).where(
                ModelVersion.model_name == model_name,
                ModelVersion.version == version,
            )
        )

        if existing is not None:
            raise ValueError(
                f"Model version already exists: {model_name}/{version}"
            )

        model_version = ModelVersion(
            model_version_id=str(uuid4()),
            model_name=model_name,
            version=version,
            status=ModelVersionStatus.CANDIDATE.value,
            artifact_path=f"/models/{model_name}/{version}/",
        )

        db.add(model_version)
        db.commit()
        db.refresh(model_version)

        return model_version

    def approve(
        self,
        db: Session,
        model_version_id: str,
    ) -> ModelVersion:
        model_version = db.get(ModelVersion, model_version_id)

        if model_version is None:
            raise ValueError(
                f"Model version not found: {model_version_id}"
            )

        if model_version.status != ModelVersionStatus.CANDIDATE.value:
            raise ValueError(
                "Only CANDIDATE models can be approved"
            )

        model_version.status = ModelVersionStatus.APPROVED.value

        db.commit()
        db.refresh(model_version)

        return model_version

    def activate(
        self,
        db: Session,
        model_version_id: str,
    ) -> ModelVersion:
        model_version = db.get(ModelVersion, model_version_id)

        if model_version is None:
            raise ValueError(
                f"Model version not found: {model_version_id}"
            )

        if model_version.status != ModelVersionStatus.APPROVED.value:
            raise ValueError(
                "Only APPROVED models can be activated"
            )

        active_versions = db.scalars(
            select(ModelVersion).where(
                ModelVersion.model_name == model_version.model_name,
                ModelVersion.status == ModelVersionStatus.ACTIVE.value,
            )
        ).all()

        for active_version in active_versions:
            active_version.status = ModelVersionStatus.APPROVED.value

        model_version.status = ModelVersionStatus.ACTIVE.value

        db.commit()
        db.refresh(model_version)

        return model_version

    def get(
        self,
        db: Session,
        model_version_id: str,
    ) -> ModelVersion | None:
        return db.get(ModelVersion, model_version_id)

    def list(
        self,
        db: Session,
        model_name: str | None = None,
    ) -> list[ModelVersion]:
        query = select(ModelVersion).order_by(
            ModelVersion.model_name,
            ModelVersion.version,
        )

        if model_name is not None:
            query = query.where(
                ModelVersion.model_name == model_name
            )

        return list(db.scalars(query).all())