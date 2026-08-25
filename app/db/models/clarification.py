from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class Clarification(Base):
    __tablename__ = "clarifications"

    clarification_id: Mapped[str] = mapped_column(
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

    feedback_id: Mapped[str | None] = mapped_column(
        ForeignKey("feedback.feedback_id"),
        nullable=True,
    )

    analysis_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.analysis_run_id"),
        nullable=True,
    )

    clarification_question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    questions: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    clarification_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    responded_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    processing_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    @property
    def question(self) -> str:
        return self.clarification_question

    @question.setter
    def question(self, value: str) -> None:
        self.clarification_question = value

    @property
    def response(self) -> str | None:
        return self.clarification_response

    @response.setter
    def response(self, value: str | None) -> None:
        self.clarification_response = value

    @property
    def status(self) -> str:
        return self.processing_status

    @status.setter
    def status(self, value: str) -> None:
        self.processing_status = value
