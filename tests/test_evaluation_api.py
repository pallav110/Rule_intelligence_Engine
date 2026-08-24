from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.database import engine
from app.db.models.dataset_version import DatasetVersion
from app.db.models.model_version import ModelVersion
from app.main import app
from sqlalchemy.orm import sessionmaker


TestingSession = sessionmaker(bind=engine)
client = TestClient(app)


def create_model_and_dataset():
    db = TestingSession()

    model = ModelVersion(
        model_version_id=str(uuid4()),
        model_name=f"api-evaluation-model-{uuid4().hex[:8]}",
        version="1.0",
        status="ACTIVE",
        artifact_path="/models/test/",
    )

    dataset = DatasetVersion(
        dataset_version_id=str(uuid4()),
        dataset_name=f"api-evaluation-dataset-{uuid4().hex[:8]}",
        version="1.0",
        domain_pack_version="ecommerce-2.0",
        annotation_version="gen_v1",
        source="synthetic_jsonl",
        path="rie_ml/datasets/generated/v1/test.jsonl",
        status="READY",
    )

    db.add(model)
    db.add(dataset)
    db.commit()

    model_id = model.model_version_id
    dataset_id = dataset.dataset_version_id

    db.close()

    return model_id, dataset_id


def test_create_evaluation_api():
    model_id, dataset_id = create_model_and_dataset()

    response = client.post(
        "/v1/evaluations",
        json={
            "model_version_id": model_id,
            "dataset_version_id": dataset_id,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["evaluation_run_id"]
    assert data["model_version_id"] == model_id
    assert data["dataset_version_id"] == dataset_id
    assert data["status"] == "COMPLETED"

    assert len(data["metrics"]) == 4

    metric_names = {
        metric["metric_name"]
        for metric in data["metrics"]
    }

    assert metric_names == {
        "feedback_type_accuracy",
        "rule_category_accuracy",
        "is_actionable_accuracy",
        "requires_clarification_accuracy",
    }


def test_get_evaluation_api():
    model_id, dataset_id = create_model_and_dataset()

    create_response = client.post(
        "/v1/evaluations",
        json={
            "model_version_id": model_id,
            "dataset_version_id": dataset_id,
        },
    )

    assert create_response.status_code == 200

    evaluation_id = create_response.json()["evaluation_run_id"]

    response = client.get(
        f"/v1/evaluations/{evaluation_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["evaluation_run_id"] == evaluation_id
    assert data["model_version_id"] == model_id
    assert data["dataset_version_id"] == dataset_id
    assert data["status"] == "COMPLETED"
    assert len(data["metrics"]) == 4


def test_get_missing_evaluation_api():
    missing_id = str(uuid4())

    response = client.get(
        f"/v1/evaluations/{missing_id}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        f"Evaluation run not found: {missing_id}"
    )
