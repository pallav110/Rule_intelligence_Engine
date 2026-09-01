from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.models.dataset_version import DatasetVersion
from app.schemas.dataset import DatasetVersionCreateRequest

class DatasetVersionService:
    def create_dataset(self, db: Session, payload: DatasetVersionCreateRequest) -> DatasetVersion:
        """Create a new dataset version record."""
        import uuid
        
        dataset_id = f"ds-{uuid.uuid4().hex[:8]}"
        
        dataset = DatasetVersion(
            dataset_version_id=dataset_id,
            dataset_name=payload.dataset_name,
            version=payload.version,
            domain_pack_version=payload.domain_pack_version,
            annotation_version=payload.annotation_version,
            source=payload.source,
            path=payload.path,
            status="active"
        )
        
        db.add(dataset)
        try:
            db.commit()
            db.refresh(dataset)
        except IntegrityError:
            db.rollback()
            raise ValueError(f"Dataset version {payload.version} already exists for {payload.dataset_name}")
            
        return dataset

    def get_dataset(self, db: Session, dataset_id: str) -> DatasetVersion:
        """Fetch a dataset by ID."""
        dataset = db.query(DatasetVersion).filter(DatasetVersion.dataset_version_id == dataset_id).first()
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")
        return dataset

    def list_datasets(self, db: Session) -> List[DatasetVersion]:
        """List all datasets."""
        # Could add pagination or filtering by name in a real implementation
        return db.query(DatasetVersion).order_by(DatasetVersion.created_at.desc()).all()
