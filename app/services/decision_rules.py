"""Explicit decision rules mapping per spec (8.9.7 / 8.10).

Each condition is evaluated independently and may request an overriding
system action (clarification request, manual review, senior review,
reviewer verification). This module centralizes the table-to-action mapping
so the routing policy is deterministic and easy to test.
"""
from typing import Dict, Any, Optional


def evaluate_decision_table(
    classification: Dict[str, Any],
    extraction: Dict[str, Any],
    schema_validation: Dict[str, Any],
    duplicate_check: Dict[str, Any],
    conflict_check: Dict[str, Any],
    sensitivity: Dict[str, Any],
    clarification_required: bool,
) -> Optional[Dict[str, Any]]:
    """Return an overriding action dict or None.

    Action dict samples:
      {"action": "manual_review", "reason": "schema_validation_failed"}
      {"action": "clarification", "reason": "missing_mandatory_fields"}
      {"action": "reviewer_verification", "reason": "duplicate_detected"}
      {"action": "senior_review", "reason": "conflict_detected"}

    Rules are evaluated independently and priority is:
      schema validation failure -> mandatory manual review (highest)
      missing mandatory fields -> clarification
      low classification / extraction -> manual review
      duplicate -> reviewer verification
      conflict -> senior reviewer
      sensitivity -> senior reviewer
    """

    # 1. Schema validation failed
    if schema_validation and schema_validation.get("status") == "FAIL":
        return {"action": "manual_review", "reason": "schema_validation_failed"}

    # 2. Missing mandatory fields (clarification)
    if schema_validation and not schema_validation.get("mandatory_fields_valid", True):
        return {"action": "clarification", "reason": "missing_mandatory_fields"}

    # 3. Clarification required from completeness/ambiguity
    if clarification_required:
        return {"action": "clarification", "reason": "clarification_required"}

    # 4. Low classification probability (use calibrated if present)
    cls_conf = None
    if classification:
        cls_conf = classification.get("calibrated_confidence") or classification.get("confidence")
    try:
        if cls_conf is not None and float(cls_conf) < 0.6:
            return {"action": "manual_review", "reason": "low_classification_probability"}
    except Exception:
        pass

    # 5. Low extraction probability: compute average per-field if available
    try:
        extr_conf = extraction.get("confidence") if isinstance(extraction, dict) else None
        avg = None
        if isinstance(extr_conf, dict):
            vals = [float(v) for v in extr_conf.values() if isinstance(v, (int, float))]
            if vals:
                avg = sum(vals) / len(vals)
        elif isinstance(extr_conf, (int, float)):
            avg = float(extr_conf)
        if avg is not None and avg < 0.5:
            return {"action": "manual_review", "reason": "low_extraction_probability"}
    except Exception:
        pass

    # 6. Duplicate detected -> reviewer verification
    if duplicate_check and duplicate_check.get("is_duplicate"):
        return {"action": "reviewer_verification", "reason": "duplicate_detected"}

    # 7. Conflict detected -> senior reviewer
    if conflict_check and conflict_check.get("has_conflict"):
        return {"action": "senior_review", "reason": "conflict_detected"}

    # 8. Sensitive business rule -> senior reviewer
    if sensitivity and sensitivity.get("sensitive"):
        return {"action": "senior_review", "reason": "sensitive_business_rule"}

    return None
