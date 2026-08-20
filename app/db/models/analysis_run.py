from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    analysis_run_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    feedback_id: Mapped[str] = mapped_column(
        ForeignKey("feedback.feedback_id"),
        nullable=False,
    )

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.workspace_id"),
        nullable=False,
    )

    model_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_versions.model_version_id"),
        nullable=True,
    )

    dataset_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("dataset_versions.dataset_version_id"),
        nullable=True,
    )

    taxonomy_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    domain_pack_id: Mapped[str | None] = mapped_column(
        ForeignKey("domain_packs.pack_id"),
        nullable=True,
    )

    threshold_configuration: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    processing_mode: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="single",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )