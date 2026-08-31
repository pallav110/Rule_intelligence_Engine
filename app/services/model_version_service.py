from typing import List
import os
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.models.model_version import ModelVersion
from app.schemas.model_version import ModelVersionCreateRequest

class ModelVersionService:
    def create_model_version(self, db: Session, payload: ModelVersionCreateRequest) -> ModelVersion:
        """Create a new model version record."""
        import uuid
        
        model_id = f"mv-{uuid.uuid4().hex[:8]}"
        artifact_path = f"/models/{payload.model_name}/{payload.version}.pkl"
        
        model_version = ModelVersion(
            model_version_id=model_id,
            model_name=payload.model_name,
            version=payload.version,
            artifact_path=artifact_path,
            status="CANDIDATE"
        )
        
        db.add(model_version)
        try:
            db.commit()
            db.refresh(model_version)
        except IntegrityError:
            db.rollback()
            raise ValueError(f"Model version {payload.version} already exists for {payload.model_name}")
            
        return model_version

    def get_model_version(self, db: Session, model_version_id: str) -> ModelVersion:
        """Fetch a model version by ID."""
        model_version = db.query(ModelVersion).filter(ModelVersion.model_version_id == model_version_id).first()
        if not model_version:
            raise ValueError(f"Model version not found: {model_version_id}")
        return model_version

    def list_model_versions(self, db: Session) -> List[ModelVersion]:
        """List all model versions."""
        return db.query(ModelVersion).order_by(ModelVersion.created_at.desc()).all()
