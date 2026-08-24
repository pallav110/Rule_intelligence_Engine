from uuid import uuid4

from app.db.database import SessionLocal
from app.db.models.workspace import Workspace
from app.services.classifier import MockClassifier
from app.services.canonical_rule_service import CanonicalRuleService
from app.services.domain_pack_loader import DomainPackLoader
from app.services.feedback_preprocessor import FeedbackPreprocessor
from app.services.feedback_service import FeedbackService
from app.services.rule_extractor import MockRuleExtractor
from app.services.schema_validator import SchemaValidator


def test_batch_feedback_service_processes_multiple_items():
    service = FeedbackService(
        preprocessor=FeedbackPreprocessor(),
        domain_loader=DomainPackLoader(),
        classifier=MockClassifier(),
        extractor=MockRuleExtractor(),
        validator=SchemaValidator(),
        canonical_rule_service=CanonicalRuleService(),
    )

    db = SessionLocal()

    workspace_id = str(uuid4())

    workspace = Workspace(
        workspace_id=workspace_id,
        name="Batch Feedback Test Workspace",
    )

    db.add(workspace)
    db.commit()

    try:
        first = service.analyze(
            db=db,
            workspace_id=workspace_id,
            feedback="Refund orders should not count as revenue.",
            domain="ecommerce",
        )

        second = service.analyze(
            db=db,
            workspace_id=workspace_id,
            feedback="Cancelled orders should be excluded.",
            domain="ecommerce",
        )
    finally:
        db.close()

    assert first.feedback_id != second.feedback_id
    assert first.classification.is_actionable is True
    assert second.classification.is_actionable is True
    assert first.validation.valid is True
    assert second.validation.valid is True