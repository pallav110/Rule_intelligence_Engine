from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class Rule(Base):
    __tablename__ = "rules"

    rule_id: Mapped[str] = mapped_column(
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

    rule_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    rule_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    operation: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    conditions: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
    )

    affected_tables: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
    )

    affected_columns: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
    )

    rule_definition: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
    )

    activated_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )