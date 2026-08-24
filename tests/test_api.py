from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

WORKSPACE_ID = "52bb3fbd-16cf-4ee3-b5a5-e66dca62d811"


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness():
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_fails_when_dependency_unavailable():
    with patch(
        "app.main.engine.connect",
        side_effect=Exception("database unavailable"),
    ):
        response = client.get("/ready")

    assert response.status_code == 503
    assert "Readiness check failed" in response.json()["detail"]


def test_feedback_analyze_valid_request():
    response = client.post(
        "/v1/feedback/analyze",
        json={
            "workspace_id": WORKSPACE_ID,
            "feedback": "Refund orders should not count as revenue.",
            "domain": "ecommerce",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["feedback_id"]
    assert data["classification"]["feedback_type"] == "business_rule_correction"
    assert data["validation"]["valid"] is True


def test_feedback_analyze_unknown_domain():
    response = client.post(
        "/v1/feedback/analyze",
        json={
            "workspace_id": WORKSPACE_ID,
            "feedback": "Refund orders should not count as revenue.",
            "domain": "unknown_domain",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown domain: unknown_domain"


def test_batch_feedback():
    response = client.post(
        "/v1/feedback/batch-analyze",
        json={
            "items": [
                {
                    "workspace_id": WORKSPACE_ID,
                    "feedback": "Refund orders should not count as revenue.",
                    "domain": "ecommerce",
                },
                {
                    "workspace_id": WORKSPACE_ID,
                    "feedback": "Cancelled orders should be excluded.",
                    "domain": "ecommerce",
                },
            ]
        },
    )

    assert response.status_code == 200
    assert len(response.json()["results"]) == 2