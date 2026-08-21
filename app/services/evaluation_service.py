from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models.evaluation_metric import EvaluationMetric
from app.db.models.evaluation_run import EvaluationRun
from app.db.models.model_version import ModelVersion
from app.db.models.dataset_version import DatasetVersion
from app.services.classifier import Classifier


class EvaluationService:
    def __init__(self, classifier: Classifier):
        self.classifier = classifier

    def evaluate(
        self,
        db: Session,
        model_version_id: str,
        dataset_version_id: str,
    ) -> EvaluationRun:
        model_version = db.get(
            ModelVersion,
            model_version_id,
        )

        if model_version is None:
            raise ValueError(
                f"Model version not found: {model_version_id}"
            )

        dataset_version = db.get(
            DatasetVersion,
            dataset_version_id,
        )

        if dataset_version is None:
            raise ValueError(
                f"Dataset version not found: {dataset_version_id}"
            )

        evaluation_run = EvaluationRun(
            evaluation_run_id=str(uuid4()),
            model_version_id=model_version_id,
            dataset_version_id=dataset_version_id,
            status="RUNNING",
            started_at=datetime.utcnow(),
        )

        db.add(evaluation_run)
        db.commit()
        db.refresh(evaluation_run)

        try:
            dataset_path = Path(dataset_version.path)

            if not dataset_path.is_absolute():
                dataset_path = Path.cwd() / dataset_path

            with dataset_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                records = [
                    __import__("json").loads(line)
                    for line in file
                    if line.strip()
                ]

            total = len(records)

            if total == 0:
                raise ValueError("Evaluation dataset is empty")

            feedback_type_correct = 0
            rule_category_correct = 0
            actionable_correct = 0
            clarification_correct = 0

            for record in records:
                prediction = self.classifier.classify(
                    record["feedback_text"],
                    {"domain": record["domain"]},
                )

                feedback_type_correct += (
                    prediction.feedback_type
                    == record["feedback_type"]
                )

                rule_category_correct += (
                    prediction.rule_category
                    == record["rule_category"]
                )

                actionable_correct += (
                    prediction.is_actionable
                    == record["is_actionable"]
                )

                clarification_correct += (
                    prediction.requires_clarification
                    == record["requires_clarification"]
                )

            metrics = {
                "feedback_type_accuracy": (
                    feedback_type_correct / total
                ),
                "rule_category_accuracy": (
                    rule_category_correct / total
                ),
                "is_actionable_accuracy": (
                    actionable_correct / total
                ),
                "requires_clarification_accuracy": (
                    clarification_correct / total
                ),
            }

            for metric_name, metric_value in metrics.items():
                metric = EvaluationMetric(
                    metric_id=str(uuid4()),
                    evaluation_run_id=evaluation_run.evaluation_run_id,
                    metric_name=metric_name,
                    metric_value=metric_value,
                )
                db.add(metric)

            evaluation_run.status = "COMPLETED"
            evaluation_run.completed_at = datetime.utcnow()

            db.commit()
            db.refresh(evaluation_run)

            return evaluation_run

        except Exception:
            evaluation_run.status = "FAILED"
            db.commit()
            raise
