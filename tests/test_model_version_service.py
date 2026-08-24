from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models.model_version import ModelVersion
from app.db.models.workspace import Base
from app.services.model_version_service import ModelVersionService


engine = create_engine("sqlite:///:memory:")
TestingSession = sessionmaker(bind=engine)

Base.metadata.create_all(engine)


def test_model_version_lifecycle():
    db = TestingSession()
    service = ModelVersionService()

    model = service.create(
        db=db,
        model_name="feedback-classifier",
        version="1.0",
    )

    assert model.status == "CANDIDATE"
    assert model.artifact_path == "/models/feedback-classifier/1.0/"

    approved = service.approve(
        db=db,
        model_version_id=model.model_version_id,
    )

    assert approved.status == "APPROVED"

    active = service.activate(
        db=db,
        model_version_id=model.model_version_id,
    )

    assert active.status == "ACTIVE"

    db.close()


def test_new_active_version_replaces_previous_active_version():
    db = TestingSession()
    service = ModelVersionService()

    first = service.create(
        db=db,
        model_name="replacement-test",
        version="1.0",
    )
    service.approve(db, first.model_version_id)
    service.activate(db, first.model_version_id)

    second = service.create(
        db=db,
        model_name="replacement-test",
        version="2.0",
    )
    service.approve(db, second.model_version_id)
    service.activate(db, second.model_version_id)

    db.refresh(first)

    assert first.status == "APPROVED"
    assert second.status == "ACTIVE"

    db.close()


def test_invalid_activation_is_rejected():
    db = TestingSession()
    service = ModelVersionService()

    model = service.create(
        db=db,
        model_name="activation-test",
        version="1.0",
    )

    try:
        service.activate(db, model.model_version_id)
        assert False, "Expected activation to fail"
    except ValueError as exc:
        assert str(exc) == "Only APPROVED models can be activated"

    db.close()


def test_duplicate_model_version_is_rejected():
    db = TestingSession()
    service = ModelVersionService()

    service.create(
        db=db,
        model_name="duplicate-test",
        version="1.0",
    )

    try:
        service.create(
            db=db,
            model_name="duplicate-test",
            version="1.0",
        )
        assert False, "Expected duplicate model version to fail"
    except ValueError as exc:
        assert str(exc) == (
            "Model version already exists: "
            "duplicate-test/1.0"
        )

    db.close()