from dataclasses import dataclass
from typing import Any


@dataclass
class DuplicateCheckResult:
    relationship: str
    confidence: float
    matching_rule_id: str | None = None


class RuleComparisonService:
    def check_duplicate(
        self,
        rule: dict[str, Any],
        existing_rules: list[dict[str, Any]],
    ) -> DuplicateCheckResult:
        raise NotImplementedError

@dataclass
class ConflictCheckResult:
    relationship: str
    confidence: float
    conflicting_rule_id: str | None = None


class RuleConflictService:
    def check_conflict(
        self,
        rule: dict[str, Any],
        existing_rules: list[dict[str, Any]],
    ) -> ConflictCheckResult:
        raise NotImplementedError

@dataclass
class RuleComparisonResult:
    relationship: str
    confidence: float
    details: dict[str, Any]


class RuleComparator:
    def compare(
        self,
        rule_a: dict[str, Any],
        rule_b: dict[str, Any],
    ) -> RuleComparisonResult:
        raise NotImplementedError

class MockRuleComparisonService(RuleComparisonService):
    def check_duplicate(
        self,
        rule: dict[str, Any],
        existing_rules: list[dict[str, Any]],
    ) -> DuplicateCheckResult:
        return DuplicateCheckResult(
            relationship="unrelated",
            confidence=0.0,
        )


class MockRuleConflictService(RuleConflictService):
    def check_conflict(
        self,
        rule: dict[str, Any],
        existing_rules: list[dict[str, Any]],
    ) -> ConflictCheckResult:
        return ConflictCheckResult(
            relationship="no_conflict",
            confidence=0.0,
        )


class MockRuleComparator(RuleComparator):
    def compare(
        self,
        rule_a: dict[str, Any],
        rule_b: dict[str, Any],
    ) -> RuleComparisonResult:
        return RuleComparisonResult(
            relationship="unrelated",
            confidence=0.0,
            details={},
        )