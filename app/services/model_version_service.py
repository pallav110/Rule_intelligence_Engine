from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.models.model_version import ModelVersion, ModelVersionStatus, ModelType
from app.schemas.model_version import ModelVersionCreateRequest, ModelVersionUpdateRequest

class ModelVersionService:
    def create_model_version(self, db: Session, payload: ModelVersionCreateRequest) -> ModelVersion:
        """Create a new model version record per spec 8.11."""
        import uuid

        model_id = f"mv-{uuid.uuid4().hex[:8]}"

        model_type_str = payload.model_type.value if isinstance(payload.model_type, ModelType) else str(payload.model_type)
        # Strip enum repr prefix if present (e.g. "ModelType.CLASSIFICATION" -> "classification")
        if "." in model_type_str:
            model_type_str = model_type_str.split(".")[-1].lower()
        # Normalize to canonical spec 8.11 values (underscores -> dashes)
        model_type_str = model_type_str.replace("_", "-")

        model_version = ModelVersion(
            model_version_id=model_id,
            model_name=payload.model_name,
            model_type=model_type_str,
            version=payload.version,
            description=payload.description,
            checkpoint_path=payload.checkpoint_path,
            # artifact_path is legacy NOT NULL column — mirror checkpoint_path
            artifact_path=payload.checkpoint_path,
            training_dataset_version_id=payload.training_dataset_version_id,
            validation_dataset_version_id=payload.validation_dataset_version_id,
            annotation_scheme_version=payload.annotation_scheme_version,
            hyperparameters=payload.hyperparameters,
            training_timestamp=payload.training_timestamp,
            evaluation_metrics=payload.evaluation_metrics,
            status=ModelVersionStatus.CANDIDATE.value,
        )

        db.add(model_version)
        try:
            db.commit()
            db.refresh(model_version)
        except IntegrityError:
            db.rollback()
            raise ValueError(f"Model version {payload.version} already exists for {payload.model_name} ({payload.model_type})")

        return model_version

    def get_model_version(self, db: Session, model_version_id: str) -> ModelVersion:
        """Fetch a model version by ID."""
        model_version = db.query(ModelVersion).filter(ModelVersion.model_version_id == model_version_id).first()
        if not model_version:
            raise ValueError(f"Model version not found: {model_version_id}")
        return model_version

    def list_model_versions(self, db: Session, model_type: Optional[str] = None, status: Optional[str] = None) -> List[ModelVersion]:
        """List all model versions with optional filters."""
        query = db.query(ModelVersion)
        if model_type:
            query = query.filter(ModelVersion.model_type == model_type)
        if status:
            query = query.filter(ModelVersion.status == status)
        return query.order_by(ModelVersion.created_at.desc()).all()

    def update_model_version(self, db: Session, model_version_id: str, payload: ModelVersionUpdateRequest) -> ModelVersion:
        """Update a model version (e.g., promote CANDIDATE -> APPROVED -> ACTIVE)."""
        model_version = self.get_model_version(db, model_version_id)

        if payload.status is not None:
            current = model_version.status
            # Normalize both old & new to plain strings (handle either enum class)
            new_status = payload.status.value if hasattr(payload.status, "value") else str(payload.status).split(".")[-1]
            valid_transitions = {
                ModelVersionStatus.CANDIDATE.value: [ModelVersionStatus.APPROVED.value, ModelVersionStatus.ARCHIVED.value],
                ModelVersionStatus.APPROVED.value: [ModelVersionStatus.ACTIVE.value, ModelVersionStatus.ARCHIVED.value],
                ModelVersionStatus.ACTIVE.value: [ModelVersionStatus.ARCHIVED.value],
                ModelVersionStatus.ARCHIVED.value: [],
            }
            if new_status not in valid_transitions.get(current, []):
                raise ValueError(f"Invalid status transition: {current} -> {new_status}")
            model_version.status = new_status

            # Spec 8.11: only ONE model may be ACTIVE per model_type at a time.
            # Promoting a challenger to ACTIVE automatically ARCHIVEs the prior
            # ACTIVE of the same type, so get_active_model()/inference always
            # resolve to a single, unambiguous champion. Without this, a promote
            # can leave two ACTIVE rows and which one serves is undefined.
            if new_status == ModelVersionStatus.ACTIVE.value:
                prior_active = (
                    db.query(ModelVersion)
                    .filter(
                        ModelVersion.model_type == model_version.model_type,
                        ModelVersion.model_version_id != model_version_id,
                        ModelVersion.status == ModelVersionStatus.ACTIVE.value,
                    )
                    .all()
                )
                for prior in prior_active:
                    prior.status = ModelVersionStatus.ARCHIVED.value

        if payload.description is not None:
            model_version.description = payload.description

        if payload.evaluation_metrics is not None:
            model_version.evaluation_metrics = payload.evaluation_metrics

        model_version.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(model_version)
        return model_version

    def promote_model(self, db: Session, model_version_id: str, target_status) -> ModelVersion:
        """Convenience method to promote model through lifecycle: CANDIDATE -> APPROVED -> ACTIVE."""
        # Normalize: accept ModelVersionStatus enum or string, route via string to avoid enum repr issues
        if hasattr(target_status, "value"):
            target_status = target_status.value
        else:
            target_status = str(target_status).split(".")[-1]
        # Map to schema enum for validation
        from app.schemas.model_version import ModelVersionStatus as SchemaStatus
        try:
            schema_status = SchemaStatus(target_status)
        except ValueError:
            raise ValueError(f"Invalid target status: {target_status}")
        return self.update_model_version(db, model_version_id, ModelVersionUpdateRequest(status=schema_status))

    def get_active_model(self, db: Session, model_type: str) -> Optional[ModelVersion]:
        """Get the currently ACTIVE model for a given type (used for inference)."""
        return db.query(ModelVersion).filter(
            ModelVersion.model_type == model_type,
            ModelVersion.status == ModelVersionStatus.ACTIVE.value
        ).first()

    def get_candidate_models(self, db: Session, model_type: str) -> List[ModelVersion]:
        """Get all CANDIDATE models for a type (for evaluation)."""
        return db.query(ModelVersion).filter(
            ModelVersion.model_type == model_type,
            ModelVersion.status == ModelVersionStatus.CANDIDATE.value
        ).order_by(ModelVersion.created_at.desc()).all()
