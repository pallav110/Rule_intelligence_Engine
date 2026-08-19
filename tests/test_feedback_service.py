from app.services.classifier import MockClassifier
from app.services.canonical_rule_service import CanonicalRuleService
from app.services.domain_pack_loader import DomainPackLoader
from app.services.feedback_preprocessor import FeedbackPreprocessor
from app.services.feedback_service import FeedbackService
from app.services.rule_extractor import MockRuleExtractor
from app.services.schema_validator import SchemaValidator


def test_feedback_service_pipeline():
    service = FeedbackService(
        preprocessor=FeedbackPreprocessor(),
        domain_loader=DomainPackLoader(),
        classifier=MockClassifier(),
        extractor=MockRuleExtractor(),
        validator=SchemaValidator(),
        canonical_rule_service=CanonicalRuleService(),
    )

    result = service.analyze(
        "Refund orders should not count as revenue.",
        "ecommerce",
    )

    assert result.feedback_id
    assert result.classification.feedback_type == "business_rule_correction"
    assert result.classification.rule_category == "filter_rule"
    assert result.rules == []
    assert result.validation.valid is True