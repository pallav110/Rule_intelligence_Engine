from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.dataset_version import DatasetVersion


class DatasetVersionService:
    def create(
        self,
        db: Session,
        dataset_name: str,
        version: str,
        domain_pack_version: str,
        annotation_version: str,
        source: str,
        path: str,
    ) -> DatasetVersion:
        existing = db.scalar(
            select(DatasetVersion).where(
                DatasetVersion.dataset_name == dataset_name,
                DatasetVersion.version == version,
            )
        )

        if existing is not None:
            raise ValueError(
                f"Dataset version already exists: "
                f"{dataset_name}/{version}"
            )

        dataset_version = DatasetVersion(
            dataset_version_id=str(uuid4()),
            dataset_name=dataset_name,
            version=version,
            domain_pack_version=domain_pack_version,
            annotation_version=annotation_version,
            source=source,
            path=path,
            status="PENDING",
        )

        db.add(dataset_version)
        db.commit()
        db.refresh(dataset_version)

        return dataset_version

    def get(
        self,
        db: Session,
        dataset_version_id: str,
    ) -> DatasetVersion | None:
        return db.get(DatasetVersion, dataset_version_id)

    def list(
        self,
        db: Session,
        dataset_name: str | None = None,
    ) -> list[DatasetVersion]:
        query = select(DatasetVersion).order_by(
            DatasetVersion.dataset_name,
            DatasetVersion.version,
        )

        if dataset_name is not None:
            query = query.where(
                DatasetVersion.dataset_name == dataset_name
            )

        return list(db.scalars(query).all())
