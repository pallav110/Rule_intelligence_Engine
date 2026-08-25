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

    extracted_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("extracted_rules.extracted_rule_id"),
        nullable=True,
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

    compared_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("rules.rule_id"),
        nullable=True,
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

    @property
    def relationship_type(self) -> str:
        return self.relationship

    @relationship_type.setter
    def relationship_type(self, value: str) -> None:
        self.relationship = value

    @property
    def similarity_score(self) -> float | None:
        return self.confidence

    @similarity_score.setter
    def similarity_score(self, value: float | None) -> None:
        self.confidence = value

    @property
    def comparison_summary(self) -> dict | None:
        return self.details

    @comparison_summary.setter
    def comparison_summary(self, value: dict | None) -> None:
        self.details = value
