"""Real rule extractor service integrating rie-ml baseline extractor.

Replaces MockRuleExtractor with actual ML-powered rule extraction.
"""

from dataclasses import dataclass
from typing import Any, List, Dict

from rie_ml.baseline.extractor import BaselineRuleExtractor as MLExtractor


@dataclass
class RuleExtractionResult:
    rules: List[Dict[str, Any]]
    confidence: float


class RuleExtractor:
    def extract(
        self,
        feedback: str,
        classification: Any,
        schema_context: dict,
    ) -> RuleExtractionResult:
        raise NotImplementedError


class RealRuleExtractor(RuleExtractor):
    """Production rule extractor backed by rie-ml baseline."""

    def __init__(self):
        self._model = MLExtractor()

    def extract(
        self,
        feedback: str,
        classification: Any,
        schema_context: dict,
    ) -> RuleExtractionResult:
        result = self._model.extract(feedback, classification, schema_context)

        return RuleExtractionResult(
            rules=result["rules"],
            confidence=result["confidence"],
        )


class MockRuleExtractor(RuleExtractor):
    """Mock for testing - returns empty rules."""

    def extract(
        self,
        feedback: str,
        classification: Any,
        schema_context: dict,
    ) -> RuleExtractionResult:
        return RuleExtractionResult(
            rules=[],
            confidence=0.0,
        )