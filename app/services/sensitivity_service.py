"""Simple business-sensitivity detection service.

Provides a lightweight rule-based detector to flag suggestions that touch
on sensitive business domains (revenue, payment, compliance, PII) so routing
can escalate to senior reviewers.
"""
from typing import Dict, Any

SENSITIVE_KEYWORDS = {
    "revenue",
    "payment",
    "refund",
    "credit",
    "charge",
    "fraud",
    "pci",
    "pii",
    "ssn",
    "tax",
    "compliance",
}


def assess_sensitivity(rule: Dict[str, Any], classification: Dict[str, Any]) -> Dict[str, Any]:
    """Return sensitivity assessment dict: {sensitive: bool, score: float, reasons: []}.

    Simple heuristic: check business_term, rule_category, and condition field names
    for tokens in the sensitive keywords set.
    """
    reasons = []
    score = 0.0

    term = str((rule or {}).get("business_term") or "").lower()
    if any(k in term for k in SENSITIVE_KEYWORDS):
        reasons.append(f"business_term matched sensitive keyword: {term}")
        score += 0.6

    category = str((classification or {}).get("rule_category") or "").lower()
    if any(k in category for k in SENSITIVE_KEYWORDS):
        reasons.append(f"rule_category matched sensitive keyword: {category}")
        score += 0.3

    # Check conditions for sensitive field names
    for cond in (rule or {}).get("conditions", []) or []:
        fld = str(cond.get("field") or "").lower()
        if any(k in fld for k in SENSITIVE_KEYWORDS):
            reasons.append(f"condition field matched sensitive keyword: {fld}")
            score += 0.2
            break

    sensitive = score >= 0.5
    return {"sensitive": bool(sensitive), "score": min(1.0, score), "reasons": reasons}
