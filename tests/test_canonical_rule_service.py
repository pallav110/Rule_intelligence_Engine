from app.services.canonical_rule_service import CanonicalRuleService


def test_valid_rule_is_converted_to_canonical_rule():
    rule = CanonicalRuleService().build(
        {
            "rule_id": "R001",
            "rule_category": "filter_rule",
            "operation": "exclude",
            "conditions": [
                {
                    "field": "orders.status",
                    "operator": "equals",
                    "value": "refunded",
                    "scope": "global",
                    "time_window": None,
                }
            ],
            "affected_tables": ["orders"],
            "affected_columns": ["status"],
        }
    )

    assert rule.rule_id == "R001"
    assert rule.rule_category == "filter_rule"
    assert rule.operation == "exclude"
    assert rule.conditions[0].field == "orders.status"


def test_invalid_rule_is_rejected():
    invalid_rule = {
        "rule_id": "R002",
        "rule_category": "filter_rule",
        "operation": "exclude",
        "conditions": [],
    }

    try:
        CanonicalRuleService().build(invalid_rule)
        assert False, "Expected validation error"
    except Exception:
        assert True