from app.services.rule_comparison_service import (
    MockRuleComparator,
    MockRuleComparisonService,
    MockRuleConflictService,
)


def test_duplicate_check_interface():
    result = MockRuleComparisonService().check_duplicate(
        {"rule_id": "R001"},
        [],
    )

    assert result.relationship == "unrelated"
    assert result.confidence == 0.0
    assert result.matching_rule_id is None


def test_conflict_check_interface():
    result = MockRuleConflictService().check_conflict(
        {"rule_id": "R001"},
        [],
    )

    assert result.relationship == "no_conflict"
    assert result.confidence == 0.0
    assert result.conflicting_rule_id is None


def test_rule_comparison_interface():
    result = MockRuleComparator().compare(
        {"rule_id": "R001"},
        {"rule_id": "R002"},
    )

    assert result.relationship == "unrelated"
    assert result.confidence == 0.0
    assert result.details == {}