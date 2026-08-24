from uuid import uuid4

from sqlalchemy.orm import sessionmaker

from app.db.database import engine
from app.services.dataset_version_service import DatasetVersionService


TestingSession = sessionmaker(bind=engine)


def unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def test_dataset_version_lifecycle():
    db = TestingSession()
    service = DatasetVersionService()

    dataset_name = unique_name("feedback-evaluation")

    dataset = service.create(
        db=db,
        dataset_name=dataset_name,
        version="1.0",
        domain_pack_version="ecommerce-2.0",
        annotation_version="1.0",
        source="annotated_csv",
        path="/datasets/feedback-evaluation/1.0.csv",
    )

    assert dataset.dataset_version_id
    assert dataset.status == "PENDING"
    assert dataset.path == "/datasets/feedback-evaluation/1.0.csv"

    fetched = service.get(
        db=db,
        dataset_version_id=dataset.dataset_version_id,
    )

    assert fetched is not None
    assert fetched.dataset_version_id == dataset.dataset_version_id
    assert fetched.dataset_name == dataset_name
    assert fetched.version == "1.0"

    db.close()


def test_duplicate_dataset_version_is_rejected():
    db = TestingSession()
    service = DatasetVersionService()

    dataset_name = unique_name("duplicate-dataset")

    service.create(
        db=db,
        dataset_name=dataset_name,
        version="1.0",
        domain_pack_version="ecommerce-2.0",
        annotation_version="1.0",
        source="annotated_csv",
        path="/datasets/duplicate/1.0.csv",
    )

    try:
        service.create(
            db=db,
            dataset_name=dataset_name,
            version="1.0",
            domain_pack_version="ecommerce-2.0",
            annotation_version="1.0",
            source="annotated_csv",
            path="/datasets/duplicate/1.0.csv",
        )
        assert False, "Expected duplicate dataset version to fail"
    except ValueError as exc:
        assert str(exc) == (
            f"Dataset version already exists: "
            f"{dataset_name}/1.0"
        )

    db.close()


def test_list_dataset_versions():
    db = TestingSession()
    service = DatasetVersionService()

    dataset_name = unique_name("list-dataset")

    first = service.create(
        db=db,
        dataset_name=dataset_name,
        version="1.0",
        domain_pack_version="ecommerce-2.0",
        annotation_version="1.0",
        source="annotated_csv",
        path="/datasets/list/1.0.csv",
    )

    second = service.create(
        db=db,
        dataset_name=dataset_name,
        version="2.0",
        domain_pack_version="ecommerce-2.0",
        annotation_version="1.0",
        source="annotated_csv",
        path="/datasets/list/2.0.csv",
    )

    results = service.list(
        db=db,
        dataset_name=dataset_name,
    )

    assert len(results) == 2
    assert results[0].dataset_version_id == first.dataset_version_id
    assert results[1].dataset_version_id == second.dataset_version_id

    db.close()
