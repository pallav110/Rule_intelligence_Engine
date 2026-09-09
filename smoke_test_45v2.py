"""Smoke test 45 feedback cases — production vs baseline, full 8-step pipeline."""
import json, time, sys
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
    "Revenue needs fixing.",                                        # vague
    "Revenue shouldn't count some orders.",                          # vague
    "The cafeteria food is terrible today.",                         # off-topic
    "BUY NOW BUY NOW BUY NOW BUY NOW CLICK HERE!!! FREE FREE FREE!!!",  # spam
    "xj29 revenue zzz qqq cancelled blahhh 9281 asdfgh",            # gibberish
    "",
    "Revenue",
    "Why is revenue excluding cancelled orders?",
    "Revenue should include cancelled orders and exclude cancelled orders.",
    "I read an article about revenue and cancelled orders yesterday.",
]

def slim_rule(r):
    if not r:
        return None
    return {
        "business_term": r.get("business_term"),
        "operation": r.get("operation"),
        "conditions": r.get("conditions"),
        "time_window": r.get("time_window"),
        "affected_tables": r.get("affected_tables"),
        "affected_columns": r.get("affected_columns"),
    }

def run(i, feedback, model):
    t0 = time.time()
    try:
        r = requests.post(API,
            json={"feedback_text": feedback, "workspace_id": "default"},
            params={"model": model}, timeout=60)
        elapsed = round(time.time() - t0, 3)
        if r.status_code != 200:
            return {"time_s": elapsed, "error": f"HTTP {r.status_code}: {r.text[:300]}"}
        d = r.json()
        ex = d.get("extraction") or {}
        return {
            "time_s": elapsed,
            "classification": {
                "feedback_type": d.get("classification", {}).get("feedback_type"),
                "rule_category": d.get("classification", {}).get("rule_category"),
                "confidence": round(d.get("classification", {}).get("confidence", 0), 3) if d.get("classification", {}).get("confidence") is not None else None,
                "is_actionable": d.get("classification", {}).get("is_actionable"),
            },
            "extraction_confidence": round(ex.get("confidence", 0), 3) if isinstance(ex.get("confidence"), (int, float)) else ex.get("confidence"),
            "rules": [slim_rule(r) for r in ex.get("rules", [])],
            "validation": {
                "status": d.get("schema_validation", {}).get("status"),
                "coverage": d.get("schema_validation", {}).get("coverage"),
                "errors": d.get("schema_validation", {}).get("validation_errors", []),
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
            "clarification_required": d.get("clarification_required"),
            "routing": d.get("routing_decision", {}),
            "_routing_status": d.get("routing_decision", {}).get("review_status") or d.get("routing_decision", {}).get("status"),
        }
    except Exception as e:
        return {"time_s": round(time.time() - t0, 3), "error": str(e)}

results = {"meta": {"total": len(FEEDBACKS), "time": time.strftime("%Y-%m-%d %H:%M:%S")}}
cases = []
for i, fb in enumerate(FEEDBACKS, 1):
    label = (fb[:50] + "...") if len(fb) > 50 else (fb or "(empty)")
    print(f"[{i:02d}] {label:<54} ", end="", flush=True)
    prod = run(i, fb, "active")
    base = run(i, fb, "baseline")
    tag = "ERROR" if ("error" in prod or "error" in base) else "ok"
    print(f"{tag}  prod={prod.get('time_s','?')}s  base={base.get('time_s','?')}s")
    cases.append({"id": i, "feedback": fb, "production": prod, "baseline": base})

results["cases"] = cases
# Summaries
from collections import Counter
def cnt(path):
    return Counter(c.get("production", {}).get(path.split(".")[0], {}).get(path.split(".")[1]) for c in cases)
results["summary"] = {
    "validation": dict(Counter(c.get("production", {}).get("validation", {}).get("status") for c in cases)),
    "routing": dict(Counter(c.get("production", {}).get("_routing_status", "?") for c in cases)),
    "has_errors": sum(1 for c in cases if "error" in c.get("production", {})),
    "avg_time_prod": round(sum(c["production"].get("time_s",0) for c in cases if "error" not in c.get("production", {}))/max(1,len([c for c in cases if "error" not in c.get("production", {})])), 3),
    "avg_time_base": round(sum(c["baseline"].get("time_s",0) for c in cases if "error" not in c.get("baseline", {}))/max(1,len([c for c in cases if "error" not in c.get("baseline", {})])), 3),
}

out = "/home/spxlpt133/Desktop/Rule-intelligence-Engine/smoke_test_results.json"
with open(out, "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\n✅ Saved to {out}")
print(f"   {results['summary']}")

# Build a quick markdown summary
prod_dup_cnt = Counter(c.get("production", {}).get("duplicate", {}).get("relationship") for c in cases)
base_dup_cnt = Counter(c.get("baseline", {}).get("duplicate", {}).get("relationship") for c in cases)
prod_conflict = sum(1 for c in cases if c.get("production", {}).get("conflict", {}).get("has_conflict"))
base_conflict = sum(1 for c in cases if c.get("baseline", {}).get("conflict", {}).get("has_conflict"))
prod_clarif = sum(1 for c in cases if c.get("production", {}).get("clarification_required"))
base_clarif = sum(1 for c in cases if c.get("baseline", {}).get("clarification_required"))

md = f"# Smoke Test — 45 Cases ({results['meta']['time']})\n\n"
md += "## Validation (Production)\n"
md += f"  PASS: {results['summary']['validation'].get('PASS',0)} | "
md += f"PARTIAL: {results['summary']['validation'].get('PARTIAL',0)} | "
md += f"FAIL: {results['summary']['validation'].get('FAIL',0)} | "
md += f"ERR: {results['summary']['validation'].get(None,0)}\n\n"
md += "## Validation (Baseline)\n"
bval = dict(Counter(c.get("baseline", {}).get("validation", {}).get("status") for c in cases))
md += f"  PASS: {bval.get('PASS',0)} | PARTIAL: {bval.get('PARTIAL',0)} | "
md += f"FAIL: {bval.get('FAIL',0)} | ERR: {bval.get(None,0)}\n\n"
md += f"## Routing (Production)\n  {results['summary']['routing']}\n\n"
md += f"## Duplicate Detection\n"
md += f"  Prod: {dict(prod_dup_cnt)}\n"
md += f"  Base: {dict(base_dup_cnt)}\n\n"
md += f"## Conflicts\n  Prod: {prod_conflict} | Base: {base_conflict}\n\n"
md += f"## Clarification Required\n  Prod: {prod_clarif} | Base: {base_clarif}\n\n"
md += f"## Performance\n"
md += f"  Prod avg: {results['summary']['avg_time_prod']}s | Base avg: {results['summary']['avg_time_base']}s\n"
md += f"  Errors: {results['summary']['has_errors']}\n\n"
with open("/home/spxlpt133/Desktop/Rule-intelligence-Engine/smoke_test_summary.md","w") as f:
    f.write(md)
