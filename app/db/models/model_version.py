from datetime import datetime
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class ModelVersionStatus(PyEnum):
    """Model lifecycle status per spec 8.11."""
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ModelType(PyEnum):
    """Model type categories per spec 8.11 storage layout."""
    CLASSIFICATION = "classification"
    RULE_EXTRACTION = "rule-extraction"
    DUPLICATE_DETECTION = "duplicate-detection"
    CONFLICT_DETECTION = "conflict-detection"
    CLARIFICATION = "clarification"
    SCHEMA_VALIDATION = "schema-validation"
    OTHER = "other"


class ModelVersion(Base):
    __tablename__ = "model_versions"

    __table_args__ = (
        UniqueConstraint(
            "model_name",
            "version",
            "model_type",
            name="uq_model_versions_name_version_type",
        ),
    )

    model_version_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    model_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="other",
    )

    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Checkpoint/artifact path per spec storage layout
    checkpoint_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # Legacy column: NOT NULL in existing DB — mirror checkpoint_path on write
    artifact_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Dataset linkage per spec 8.11
    training_dataset_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("dataset_versions.dataset_version_id"),
        nullable=True,
    )
    validation_dataset_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("dataset_versions.dataset_version_id"),
        nullable=True,
    )

    # Annotation scheme version per spec 8.11
    annotation_scheme_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Hyperparameters per spec 8.11
    hyperparameters: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Training timestamp per spec 8.11
    training_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Evaluation metrics per spec 8.11
    evaluation_metrics: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Status per spec 8.11
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ModelVersionStatus.CANDIDATE.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
