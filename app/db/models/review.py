from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class Review(Base):
    __tablename__ = "reviews"

    review_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.workspace_id"),
        nullable=False,
    )

    suggestion_id: Mapped[str] = mapped_column(
        ForeignKey("rule_suggestions.suggestion_id"),
        nullable=False,
    )

    reviewer_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
