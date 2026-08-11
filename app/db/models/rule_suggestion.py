from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class RuleSuggestion(Base):
    __tablename__ = "rule_suggestions"

    suggestion_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.workspace_id"),
        nullable=False
    )

    feedback_id: Mapped[str] = mapped_column(
        ForeignKey("feedback.feedback_id"),
        nullable=False
    )

    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.analysis_run_id"),
        nullable=False
    )

    suggested_rule: Mapped[dict] = mapped_column(
        JSON,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
