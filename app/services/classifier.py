"""Real classifier service integrating rie_ml baseline classifier.

Replaces MockClassifier with actual ML-powered classification.
"""

from dataclasses import dataclass
from pathlib import Path

from rie_ml.src.baseline.classifier import BaselineClassifier as MLClassifier


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


class RealClassifier(Classifier):
    """Production classifier backed by rie_ml baseline."""

    def __init__(self, model_path: str | None = None):
        if model_path is None:
            # Default to rie_ml/models/baseline_classifier.pkl
            model_path = str(Path(__file__).parent.parent.parent / "rie_ml" / "models" / "baseline_classifier.pkl")

        self._model = MLClassifier(model_path=model_path)

    def classify(
        self,
        feedback: str,
        domain_context: dict,
    ) -> ClassificationResult:
        result = self._model.classify(feedback, domain_context)

        return ClassificationResult(
            feedback_type=result["feedback_type"],
            rule_category=result.get("rule_category"),
            is_actionable=result["is_actionable"],
            requires_clarification=result["requires_clarification"],
            confidence=result["confidence"],
        )


class MockClassifier(Classifier):
    """Mock for testing - returns hardcoded values."""

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