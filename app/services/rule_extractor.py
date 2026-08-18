from dataclasses import dataclass
from typing import Any


@dataclass
class RuleExtractionResult:
    rules: list[dict[str, Any]]
    confidence: float


class RuleExtractor:
    def extract(
        self,
        feedback: str,
        classification: Any,
        schema_context: dict,
    ) -> RuleExtractionResult:
        raise NotImplementedError


class MockRuleExtractor(RuleExtractor):
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