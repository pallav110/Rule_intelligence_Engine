from io import BytesIO
from uuid import uuid4

from app.db.database import SessionLocal
from app.db.models.workspace import Workspace
from app.main import app
from fastapi.testclient import TestClient


client = TestClient(app)


def test_batch_csv_feedback():
    db = SessionLocal()
    workspace_id = str(uuid4())

    workspace = Workspace(
        workspace_id=workspace_id,
        name="CSV Batch Test Workspace",
    )

    db.add(workspace)
    db.commit()
    db.close()

    csv_content = (
        "feedback\n"
        "Refund orders should not count as revenue.\n"
        "Cancelled orders should be excluded.\n"
    )

    response = client.post(
        "/v1/feedback/batch-csv",
        data={
            "workspace_id": workspace_id,
            "domain_pack_id": "ecommerce",
        },
        files={
            "file": (
                "test.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "job_id" in body
    assert body["workspace_id"] == workspace_id
    assert body["job_type"] == "batch_feedback_csv"
    assert body["status"] == "pending"
    assert body["idempotency_key"]

def test_batch_csv_rejects_missing_feedback_column():
    response = client.post(
        "/v1/feedback/batch-csv",
        data={
            "workspace_id": str(uuid4()),
            "domain_pack_id": "ecommerce",
        },
        files={
            "file": (
                "test.csv",
                BytesIO(b"text\nhello\n"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "CSV must contain a 'feedback' column"


def test_batch_csv_rejects_empty_csv():
    response = client.post(
        "/v1/feedback/batch-csv",
        data={
            "workspace_id": str(uuid4()),
            "domain_pack_id": "ecommerce",
        },
        files={
            "file": (
                "test.csv",
                BytesIO(b"feedback\n"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "CSV contains no valid feedback rows"


def test_batch_csv_rejects_non_csv_file():
    response = client.post(
        "/v1/feedback/batch-csv",
        data={
            "workspace_id": str(uuid4()),
            "domain_pack_id": "ecommerce",
        },
        files={
            "file": (
                "test.txt",
                BytesIO(b"feedback\nhello\n"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "File must be a CSV"


def test_batch_csv_rejects_unknown_domain_pack():
    db = SessionLocal()
    workspace_id = str(uuid4())

    workspace = Workspace(
        workspace_id=workspace_id,
        name="CSV Unknown Domain Test Workspace",
    )

    db.add(workspace)
    db.commit()
    db.close()

    response = client.post(
        "/v1/feedback/batch-csv",
        data={
            "workspace_id": workspace_id,
            "domain_pack_id": "does_not_exist",
        },
        files={
            "file": (
                "test.csv",
                BytesIO(b"feedback\nhello world\n"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown domain: does_not_exist"
