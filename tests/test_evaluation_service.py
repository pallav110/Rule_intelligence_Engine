import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.database import engine
from app.db.models.dataset_version import DatasetVersion
from app.db.models.evaluation_metric import EvaluationMetric
from app.db.models.evaluation_run import EvaluationRun
from app.db.models.model_version import ModelVersion
from app.services.evaluation_service import EvaluationService
from app.services.classifier import Classifier, ClassificationResult


TestingSession = sessionmaker(bind=engine)


class TestClassifier(Classifier):
    def classify(self, feedback, domain_context):
        return ClassificationResult(
            feedback_type="business_rule_correction",
            rule_category="data_quality_issue",
            is_actionable=True,
            requires_clarification=False,
            confidence=0.9,
        )


def unique_name(prefix):
    return f"{prefix}-{uuid4().hex[:8]}"


def create_model(db):
    model = ModelVersion(
        model_version_id=str(uuid4()),
        model_name=unique_name("evaluation-model"),
        version="1.0",
        status="ACTIVE",
        artifact_path="/models/test/",
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def create_dataset(db):
    dataset = DatasetVersion(
        dataset_version_id=str(uuid4()),
        dataset_name=unique_name("evaluation-dataset"),
        version="1.0",
        domain_pack_version="ecommerce-2.0",
        annotation_version="gen_v1",
        source="synthetic_jsonl",
        path="rie_ml/datasets/generated/v1/test.jsonl",
        status="READY",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


def test_evaluation_run_lifecycle():
    db = TestingSession()

    model = create_model(db)
    dataset = create_dataset(db)

    service = EvaluationService(
        classifier=TestClassifier(),
    )

    result = service.evaluate(
        db=db,
        model_version_id=model.model_version_id,
        dataset_version_id=dataset.dataset_version_id,
    )

    assert result.status == "COMPLETED"
    assert result.model_version_id == model.model_version_id
    assert result.dataset_version_id == dataset.dataset_version_id
    assert result.started_at is not None
    assert result.completed_at is not None

    metrics = list(
        db.scalars(
            select(EvaluationMetric).where(
                EvaluationMetric.evaluation_run_id
                == result.evaluation_run_id
            )
        ).all()
    )

    assert len(metrics) > 0

    db.close()


def test_evaluation_requires_existing_model():
    db = TestingSession()

    dataset = create_dataset(db)

    service = EvaluationService(
        classifier=TestClassifier(),
    )

    with pytest.raises(ValueError, match="Model version not found"):
        service.evaluate(
            db=db,
            model_version_id=str(uuid4()),
            dataset_version_id=dataset.dataset_version_id,
        )

    db.close()


def test_evaluation_requires_existing_dataset():
    db = TestingSession()

    model = create_model(db)

    service = EvaluationService(
        classifier=TestClassifier(),
    )

    with pytest.raises(ValueError, match="Dataset version not found"):
        service.evaluate(
            db=db,
            model_version_id=model.model_version_id,
            dataset_version_id=str(uuid4()),
        )

    db.close()
