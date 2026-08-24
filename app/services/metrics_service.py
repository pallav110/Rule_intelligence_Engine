from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.evaluation_metric import EvaluationMetric
from app.db.models.evaluation_run import EvaluationRun


class MetricsService:
    def get_metrics(
        self,
        db: Session,
        evaluation_run_id: str,
    ) -> dict[str, Any]:
        evaluation_run = db.get(
            EvaluationRun,
            evaluation_run_id,
        )

        if evaluation_run is None:
            raise ValueError(
                f"Evaluation run not found: {evaluation_run_id}"
            )

        metrics = db.scalars(
            select(EvaluationMetric)
            .where(
                EvaluationMetric.evaluation_run_id
                == evaluation_run_id
            )
            .order_by(EvaluationMetric.metric_name)
        ).all()

        return {
            "evaluation_run_id": evaluation_run.evaluation_run_id,
            "model_version_id": evaluation_run.model_version_id,
            "dataset_version_id": evaluation_run.dataset_version_id,
            "status": evaluation_run.status,
            "metrics": [
                {
                    "metric_name": metric.metric_name,
                    "metric_value": metric.metric_value,
                    "metric_details": metric.metric_details,
                }
                for metric in metrics
            ],
        }
