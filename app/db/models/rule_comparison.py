from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class RuleComparison(Base):
    __tablename__ = "rule_comparisons"

    comparison_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.workspace_id"),
        nullable=False,
    )

    suggestion_id: Mapped[str | None] = mapped_column(
        ForeignKey("rule_suggestions.suggestion_id"),
        nullable=True,
    )

    comparison_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    relationship: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    matching_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("rules.rule_id"),
        nullable=True,
    )

    conflicting_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("rules.rule_id"),
        nullable=True,
    )

    confidence: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
