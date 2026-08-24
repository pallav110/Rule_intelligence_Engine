from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class ModelVersion(Base):
    __tablename__ = "model_versions"

    __table_args__ = (
        UniqueConstraint(
            "model_name",
            "version",
            name="uq_model_versions_name_version",
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

    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="CANDIDATE",
    )

    artifact_path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )