from app.services.classifier import Classifier
from app.services.domain_pack_loader import DomainPackLoader
from app.services.feedback_preprocessor import FeedbackPreprocessor
from app.services.rule_extractor import RuleExtractor
from app.services.schema_validator import SchemaValidator
from app.services.canonical_rule_service import CanonicalRuleService

from app.schemas.feedback import (
    ClassificationResponse,
    FeedbackAnalysisResponse,
    ValidationErrorResponse,
    ValidationResponse,
)


class FeedbackService:
    def __init__(
        self,
        preprocessor: FeedbackPreprocessor,
        domain_loader: DomainPackLoader,
        classifier: Classifier,
        extractor: RuleExtractor,
        validator: SchemaValidator,
        canonical_rule_service: CanonicalRuleService,
    ):
        self.preprocessor = preprocessor
        self.domain_loader = domain_loader
        self.classifier = classifier
        self.extractor = extractor
        self.validator = validator
        self.canonical_rule_service = canonical_rule_service

    def analyze(self, feedback: str, domain: str):
        available_domains = {
            pack["domain_pack_id"]
            for pack in self.domain_loader.list_available_packs()
        }

        processed = self.preprocessor.preprocess(
            feedback,
            domain,
            available_domains,
        )

        schema = self.domain_loader.load_schema(processed.domain)

        classification = self.classifier.classify(
            processed.normalized_text,
            {
                "domain": processed.domain,
            },
        )

        extraction = self.extractor.extract(
            processed.normalized_text,
            classification,
            schema,
        )

        canonical_rules = [
            self.canonical_rule_service.build(rule)
            for rule in extraction.rules
        ]

        validation = self.validator.validate(
            [
                condition.field
                for rule in canonical_rules
                for condition in rule.conditions
            ],
            schema,
        )

        return FeedbackAnalysisResponse(
            feedback_id=str(processed.feedback_id),
            classification=ClassificationResponse(
                feedback_type=classification.feedback_type,
                rule_category=classification.rule_category,
                is_actionable=classification.is_actionable,
                requires_clarification=classification.requires_clarification,
                confidence=classification.confidence,
            ),
            rules=[
                rule.model_dump()
                for rule in canonical_rules
            ],
            validation=ValidationResponse(
                valid=validation.valid,
                errors=[
                    ValidationErrorResponse(
                        field=error.field,
                        reason=error.reason,
                    )
                    for error in validation.errors
                ],
            ),
        )