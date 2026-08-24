from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def unique_model_name(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"

def test_model_version_lifecycle_api():
    model_name = unique_model_name("api-feedback-classifier")

    create_response = client.post(
        "/v1/models",
        json={
            "model_name": model_name,
            "version": "1.0",
        },
    )

    assert create_response.status_code == 200

    model = create_response.json()

    assert model["model_version_id"]
    assert model["model_name"] == model_name
    assert model["version"] == "1.0"
    assert model["status"] == "CANDIDATE"
    assert model["artifact_path"] == (
        f"/models/{model_name}/1.0/"
    )

    model_id = model["model_version_id"]

    approve_response = client.post(
        f"/v1/models/{model_id}/approve"
    )

    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "APPROVED"

    activate_response = client.post(
        f"/v1/models/{model_id}/activate"
    )

    assert activate_response.status_code == 200
    assert activate_response.json()["status"] == "ACTIVE"

def test_model_version_api_auto_switches_active_version():
    model_name = unique_model_name("api-switch-test")

    first = client.post(
        "/v1/models",
        json={
            "model_name": model_name,
            "version": "1.0",
        },
    ).json()

    client.post(
        f"/v1/models/{first['model_version_id']}/approve"
    )

    client.post(
        f"/v1/models/{first['model_version_id']}/activate"
    )

    second = client.post(
        "/v1/models",
        json={
            "model_name": model_name,
            "version": "2.0",
        },
    ).json()

    client.post(
        f"/v1/models/{second['model_version_id']}/approve"
    )

    second_activation = client.post(
        f"/v1/models/{second['model_version_id']}/activate"
    )

    assert second_activation.status_code == 200
    assert second_activation.json()["status"] == "ACTIVE"

    first_response = client.get(
        f"/v1/models/{first['model_version_id']}"
    )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "APPROVED"

def test_model_version_api_rejects_invalid_activation():
    model_name = unique_model_name("api-invalid-test")

    response = client.post(
        "/v1/models",
        json={
            "model_name": model_name,
            "version": "1.0",
        },
    )

    assert response.status_code == 200

    model_id = response.json()["model_version_id"]

    activate_response = client.post(
        f"/v1/models/{model_id}/activate"
    )

    assert activate_response.status_code == 409
    assert activate_response.json()["detail"] == (
        "Only APPROVED models can be activated"
    )

def test_model_version_api_rejects_duplicate_version():
    model_name = unique_model_name("api-duplicate-test")

    payload = {
        "model_name": model_name,
        "version": "1.0",
    }

    first = client.post("/v1/models", json=payload)
    second = client.post("/v1/models", json=payload)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == (
        f"Model version already exists: "
        f"{model_name}/1.0"
    )

def test_get_missing_model_version():
    response = client.get(
        "/v1/models/does-not-exist"
    )

    assert response.status_code == 404