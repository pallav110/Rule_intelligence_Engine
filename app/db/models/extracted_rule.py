from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class ExtractedRule(Base):
    __tablename__ = "extracted_rules"

    extracted_rule_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.workspace_id"),
        nullable=False,
    )

    feedback_id: Mapped[str] = mapped_column(
        ForeignKey("feedback.feedback_id"),
        nullable=False,
    )

    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.analysis_run_id"),
        nullable=False,
    )

    suggestion_id: Mapped[str | None] = mapped_column(
        ForeignKey("rule_suggestions.suggestion_id"),
        nullable=True,
    )

    rule_family_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    business_term: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    operation: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    conditions: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    scope: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    time_window: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    affected_tables: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    affected_columns: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    extraction_confidence: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    schema_validation_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    rule_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )