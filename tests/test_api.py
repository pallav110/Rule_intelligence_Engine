from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_feedback_analyze_valid_request():
    response = client.post(
        "/v1/feedback/analyze",
        json={
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
                    "feedback": "Refund orders should not count as revenue.",
                    "domain": "ecommerce",
                },
                {
                    "feedback": "Cancelled orders should be excluded.",
                    "domain": "ecommerce",
                },
            ]
        },
    )

    assert response.status_code == 200
    assert len(response.json()["results"]) == 2