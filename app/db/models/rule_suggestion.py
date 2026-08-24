from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class RuleSuggestion(Base):
    __tablename__ = "rule_suggestions"

    suggestion_id: Mapped[str] = mapped_column(
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

    feedback_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    rule_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    classification_result: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    extraction_result: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    schema_validation_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    duplicate_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    conflict_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    clarification_required: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    review_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    suggested_rule: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )