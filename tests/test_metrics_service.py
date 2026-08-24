from uuid import uuid4

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.database import engine
from app.db.models.dataset_version import DatasetVersion
from app.db.models.evaluation_metric import EvaluationMetric
from app.db.models.evaluation_run import EvaluationRun
from app.db.models.model_version import ModelVersion
from app.services.metrics_service import MetricsService


TestingSession = sessionmaker(bind=engine)


def test_get_metrics_for_evaluation_run():
    db = TestingSession()

    model = ModelVersion(
        model_version_id=str(uuid4()),
        model_name=f"metrics-model-{uuid4().hex[:8]}",
        version="1.0",
        status="ACTIVE",
        artifact_path="/models/test/",
    )

    dataset = DatasetVersion(
        dataset_version_id=str(uuid4()),
        dataset_name=f"metrics-dataset-{uuid4().hex[:8]}",
        version="1.0",
        domain_pack_version="ecommerce-2.0",
        annotation_version="gen_v1",
        source="synthetic_jsonl",
        path="rie-ml/datasets/generated/v1/test.jsonl",
        status="READY",
    )

    db.add(model)
    db.add(dataset)
    db.commit()

    run = EvaluationRun(
        evaluation_run_id=str(uuid4()),
        model_version_id=model.model_version_id,
        dataset_version_id=dataset.dataset_version_id,
        status="COMPLETED",
    )

    db.add(run)
    db.commit()

    metric = EvaluationMetric(
        metric_id=str(uuid4()),
        evaluation_run_id=run.evaluation_run_id,
        metric_name="feedback_type_accuracy",
        metric_value=0.95,
    )

    db.add(metric)
    db.commit()

    result = MetricsService().get_metrics(
        db=db,
        evaluation_run_id=run.evaluation_run_id,
    )

    assert result["evaluation_run_id"] == run.evaluation_run_id
    assert result["model_version_id"] == model.model_version_id
    assert result["dataset_version_id"] == dataset.dataset_version_id
    assert result["status"] == "COMPLETED"

    assert len(result["metrics"]) == 1
    assert result["metrics"][0]["metric_name"] == (
        "feedback_type_accuracy"
    )
    assert result["metrics"][0]["metric_value"] == 0.95

    db.close()


def test_get_metrics_rejects_missing_evaluation_run():
    db = TestingSession()

    with pytest.raises(
        ValueError,
        match="Evaluation run not found",
    ):
        MetricsService().get_metrics(
            db=db,
            evaluation_run_id=str(uuid4()),
        )

    db.close()
