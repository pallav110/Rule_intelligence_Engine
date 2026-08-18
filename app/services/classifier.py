from dataclasses import dataclass


@dataclass
class ClassificationResult:
    feedback_type: str
    rule_category: str | None
    is_actionable: bool
    requires_clarification: bool
    confidence: float


class Classifier:
    def classify(
        self,
        feedback: str,
        domain_context: dict,
    ) -> ClassificationResult:
        raise NotImplementedError


class MockClassifier(Classifier):
    def classify(
        self,
        feedback: str,
        domain_context: dict,
    ) -> ClassificationResult:
        return ClassificationResult(
            feedback_type="business_rule_correction",
            rule_category="filter_rule",
            is_actionable=True,
            requires_clarification=False,
            confidence=0.0,
        )