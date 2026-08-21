from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def test_create_dataset_version_api():
    dataset_name = unique_name("api-dataset")

    response = client.post(
        "/v1/datasets",
        json={
            "dataset_name": dataset_name,
            "version": "1.0",
            "domain_pack_version": "ecommerce-2.0",
            "annotation_version": "1.0",
            "source": "annotated_csv",
            "path": "/datasets/api-dataset/1.0.csv",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["dataset_version_id"]
    assert data["dataset_name"] == dataset_name
    assert data["version"] == "1.0"
    assert data["path"] == "/datasets/api-dataset/1.0.csv"
    assert data["status"] == "PENDING"


def test_create_dataset_version_api_rejects_duplicate():
    dataset_name = unique_name("api-duplicate")

    payload = {
        "dataset_name": dataset_name,
        "version": "1.0",
        "domain_pack_version": "ecommerce-2.0",
        "annotation_version": "1.0",
        "source": "annotated_csv",
        "path": "/datasets/api-duplicate/1.0.csv",
    }

    first = client.post("/v1/datasets", json=payload)
    second = client.post("/v1/datasets", json=payload)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == (
        f"Dataset version already exists: {dataset_name}/1.0"
    )


def test_get_dataset_version_api():
    dataset_name = unique_name("api-get")

    create_response = client.post(
        "/v1/datasets",
        json={
            "dataset_name": dataset_name,
            "version": "1.0",
            "domain_pack_version": "ecommerce-2.0",
            "annotation_version": "1.0",
            "source": "annotated_csv",
            "path": "/datasets/api-get/1.0.csv",
        },
    )

    assert create_response.status_code == 200

    created = create_response.json()

    response = client.get(
        f"/v1/datasets/{created['dataset_version_id']}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["dataset_version_id"] == created["dataset_version_id"]
    assert data["dataset_name"] == dataset_name
    assert data["version"] == "1.0"
    assert data["path"] == "/datasets/api-get/1.0.csv"
    assert data["status"] == "PENDING"


def test_get_missing_dataset_version_api():
    missing_id = str(uuid4())

    response = client.get(
        f"/v1/datasets/{missing_id}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        f"Dataset version not found: {missing_id}"
    )


def test_list_dataset_versions_api():
    dataset_name = unique_name("api-list")

    first = client.post(
        "/v1/datasets",
        json={
            "dataset_name": dataset_name,
            "version": "1.0",
            "domain_pack_version": "ecommerce-2.0",
            "annotation_version": "1.0",
            "source": "annotated_csv",
            "path": "/datasets/api-list/1.0.csv",
        },
    )

    second = client.post(
        "/v1/datasets",
        json={
            "dataset_name": dataset_name,
            "version": "2.0",
            "domain_pack_version": "ecommerce-2.0",
            "annotation_version": "1.0",
            "source": "annotated_csv",
            "path": "/datasets/api-list/2.0.csv",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200

    response = client.get(
        f"/v1/datasets?dataset_name={dataset_name}"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["datasets"]) == 2
    assert data["datasets"][0]["version"] == "1.0"
    assert data["datasets"][1]["version"] == "2.0"
