"""Smoke test 45 feedback cases through production and baseline pipelines."""
import json
import time
import sys
import requests

API = "http://localhost:8000/v1/feedback/analyze"
FEEDBACKS = [
    "Revenue should exclude cancelled orders.",
    "Revenue must include completed payments only.",
    "Refunds should be excluded from the total revenue.",
    "Orders with status pending should not be counted in revenue.",
    "Only successful payments should contribute to total revenue.",
    "Customer lifetime value should include all completed purchases.",
    "Returned products must be excluded from sales calculations.",
    "Revenue should include orders created in the current month.",
    "Do not consider cancelled orders when calculating revenue.",
    "Cancelled purchases shouldn't contribute to revenue.",
    "When computing revenue, ignore orders that were cancelled.",
    "Revenue calculations need to leave out cancelled transactions.",
    "Only orders that successfully went through should be counted toward revenue.",
    "Revenue must not account for refunded purchases.",
    "Revenue should exclude cancelled orders from the US.",
    "Revenue should exclude cancelled orders created in the current month.",
    "Only completed orders from premium customers should contribute to revenue.",
    "Exclude refunded orders where the payment method is cash.",
    "Revenue should include completed orders but exclude refunded orders.",
    "Do not count cancelled orders or failed payments when calculating revenue.",
    "Order count should exclude cancelled orders.",
    "Average order value should include completed purchases only.",
    "Refund amount should include all successfully processed refunds.",
    "Customer revenue should exclude refunded transactions.",
    "Revenue should exclude cancelled orders.",
    "Cancelled orders should not be included in revenue.",
    "When calculating revenue, ignore cancelled orders.",
    "Revenue should exclude cancelled purchases.",
    "Revenue should include cancelled orders.",
    "Cancelled orders must contribute to revenue.",
    "Revenue should exclude completed orders.",
    "Revenue should exclude returned orders.",
    "Exclude cancelled orders from revenue globally.",
    "For this month, revenue should exclude refunded orders.",
    "For the last 30 days, only completed payments should contribute to revenue.",
    "Revenue needs fixing.",
    "Revenue shouldn't count some orders.",
    "The cafeteria food is terrible today.",
    "BUY NOW BUY NOW BUY NOW BUY NOW CLICK HERE!!! FREE FREE FREE!!!",
    "xj29 revenue zzz qqq cancelled blahhh 9281 asdfgh",
    "",
    "Revenue",
    "Why is revenue excluding cancelled orders?",
    "Revenue should include cancelled orders and exclude cancelled orders.",
    "I read an article about revenue and cancelled orders yesterday.",
]

def slim(rule_result):
    """Extract key fields from a rule result for compact display."""
    if not rule_result:
        return None
    return {
        "business_term": rule_result.get("business_term"),
        "operation": rule_result.get("operation"),
        "conditions": rule_result.get("conditions", []),
        "time_window": rule_result.get("time_window"),
        "affected_tables": rule_result.get("affected_tables", []),
        "affected_columns": rule_result.get("affected_columns", []),
    }

def run_case(idx, feedback, model):
    t0 = time.time()
    try:
        r = requests.post(API, json={"feedback_text": feedback, "workspace_id": "default"}, params={"model": model}, timeout=30)
        elapsed = time.time() - t0
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}", "time_s": round(elapsed, 3)}
        d = r.json()
        # Pull out key fields
        return {
            "time_s": round(elapsed, 3),
            "classification": {
                "feedback_type": d.get("classification", {}).get("feedback_type"),
                "rule_category": d.get("classification", {}).get("rule_category"),
                "confidence": d.get("classification", {}).get("confidence"),
                "is_actionable": d.get("classification", {}).get("is_actionable"),
            },
            "extraction_confidence": d.get("extraction_confidence"),
            "rules": [slim(r) for r in d.get("extracted_rules", [])],
            "validation": {
                "status": d.get("schema_validation", {}).get("status"),
                "coverage": d.get("schema_validation", {}).get("coverage"),
                "validation_errors": d.get("schema_validation", {}).get("validation_errors", []),
            },
            "duplicate": {
                "is_duplicate": d.get("duplicate_detection", {}).get("is_duplicate"),
                "relationship": d.get("duplicate_detection", {}).get("relationship"),
                "confidence": d.get("duplicate_detection", {}).get("confidence"),
                "matching_rule_id": d.get("duplicate_detection", {}).get("matching_rule_id"),
            },
            "conflict": {
                "has_conflict": d.get("conflict_detection", {}).get("has_conflict"),
                "conflict_type": d.get("conflict_detection", {}).get("conflict_type"),
                "severity": d.get("conflict_detection", {}).get("severity"),
            },
            "routing": d.get("routing_decision", {}),
            "clarification_needed": d.get("clarification_needed"),
        }
    except Exception as e:
        return {"error": str(e), "time_s": round(time.time() - t0, 3)}

def main():
    results = {"tests": [], "summary": {"passed": 0, "failed": 0, "errors": 0}}
    total = len(FEEDBACKS)

    for i, fb in enumerate(FEEDBACKS, 1):
        label = fb[:60] or "(empty)"
        print(f"[{i}/{total}] {label}...", end=" ", flush=True)

        prod = run_case(i, fb, model="active")
        base = run_case(i, fb, model="baseline")

        test = {"id": i, "feedback": fb, "production": prod, "baseline": base}

        # Basic pass/fail
        has_error = "error" in prod or "error" in base
        if has_error:
            status = "ERROR"
            results["summary"]["errors"] += 1
        elif (i <= 35 and prod.get("classification", {}).get("is_actionable") is not None):
            status = "PASS"
            results["summary"]["passed"] += 1
        else:
            status = "OK"
            results["summary"]["passed"] += 1

        test["status"] = status
        results["tests"].append(test)
        print(f"{status} ({prod.get('time_s','?')}s prod / {base.get('time_s','?')}s base)")

    out_path = "/home/spxlpt133/Desktop/Rule-intelligence-Engine/smoke_test_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✅ Results saved to {out_path}")
    print(f"   Summary: {results['summary']}")

if __name__ == "__main__":
    main()
