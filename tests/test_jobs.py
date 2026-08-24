from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_and_get_job():
    workspace = client.post(
        "/v1/workspaces",
        json={"name": "Test Workspace"},
    )

    assert workspace.status_code == 200

    workspace_id = workspace.json()["workspace_id"]

    response = client.post(
        "/v1/jobs",
        json={
            "workspace_id": workspace_id,
            "job_type": "feedback_analysis",
            "idempotency_key": "test-job-001",
        },
    )

    assert response.status_code == 200

    job = response.json()

    assert job["job_id"]
    assert job["workspace_id"] == workspace_id
    assert job["job_type"] == "feedback_analysis"
    assert job["status"] == "pending"

    job_response = client.get(
        f"/v1/jobs/{job['job_id']}"
    )

    assert job_response.status_code == 200

    fetched_job = job_response.json()

    assert fetched_job["job_id"] == job["job_id"]
    assert fetched_job["workspace_id"] == workspace_id


def test_job_idempotency():
    workspace = client.post(
        "/v1/workspaces",
        json={"name": "Idempotency Test"},
    )

    assert workspace.status_code == 200

    workspace_id = workspace.json()["workspace_id"]

    payload = {
        "workspace_id": workspace_id,
        "job_type": "feedback_analysis",
        "idempotency_key": "same-key-001",
    }

    first = client.post("/v1/jobs", json=payload)
    second = client.post("/v1/jobs", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json()["job_id"] == second.json()["job_id"]
