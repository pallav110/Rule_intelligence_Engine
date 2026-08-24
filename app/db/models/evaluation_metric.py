from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.workspace import Base


class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"

    metric_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.evaluation_run_id"),
        nullable=False,
    )

    metric_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    metric_value: Mapped[float] = mapped_column(
        nullable=False,
    )

    metric_details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
