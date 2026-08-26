"""Suggestion audit trail model for tracking lifecycle transitions."""

from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models.workspace import Base


class SuggestionAudit(Base):
    """Tracks all status transitions for suggestions with full audit trail."""

    __tablename__ = "suggestion_audit"

    audit_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    suggestion_id: Mapped[str] = mapped_column(
        ForeignKey("rule_suggestions.suggestion_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    from_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    to_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    transitioned_by: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    transition_reason: Mapped[str] = mapped_column(
        String(500),
        nullable=True,
    )

    audit_metadata: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

