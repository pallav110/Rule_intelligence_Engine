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

    reviewer_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="assigned",
    )

    priority: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="normal",
    )

    decision: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
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

    @property
    def comment(self) -> str | None:
        return self.notes

    @comment.setter
    def comment(self, value: str | None) -> None:
        self.notes = value

    @property
    def reviewed_at(self) -> datetime | None:
        return self.completed_at

    @reviewed_at.setter
    def reviewed_at(self, value: datetime | None) -> None:
        self.completed_at = value
