from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.workspace_id"),
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )