"""Unit test for the rare-class pre-gate (app/services/classifier.py).

The gate deterministically routes unambiguous feature_request / issue_report /
question inputs — classes the starved-seed model and regex fallback collapse
into business_rule. It must NEVER fire on genuine rule wording, spam, or
gibberish (those are handled upstream / passed to the model).

Run:  python tests/unit_rare_gate.py   (no server, no DB)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.classifier import rare_class_gate

# ---- Negatives: the full 45-case production smoke list. ----------------------
# These must NOT be gated to a non-actionable rare class. Index 43 is the one
# genuine question in the set ("Why is revenue excluding cancelled orders?") —
# gating that one to `question` is correct (it already classifies as question).
NEG = [
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
    "",                                                              # empty,
    "Revenue",                                                       # bare word
    "Why is revenue excluding cancelled orders?",                    # question (43)
    "Revenue should include cancelled orders and exclude cancelled orders.",  # contradiction
    "I read an article about revenue and cancelled orders yesterday.",  # article
]
# Index 43 (0-based 42) is a question — expect the gate to fire on it.
NEG_EXPECT_QUESTION = 42  # "Why is revenue excluding cancelled orders?"

# ---- Positives: real rare-class seeds from the domain packs. -----------------
POS = [
    # feature_request
    ("Can we get a bulk export button for the order report?", "feature_request"),
    ("Please add a dark mode for the admin panel.", "feature_request"),
    ("It would be nice to notify the warehouse when stock runs low.", "feature_request"),
    ("Kindly add timezone support to the order date filters.", "feature_request"),
    ("Please add dark mode to the agent console.", "feature_request"),
    ("Please add a bulk reassign option for tickets.", "feature_request"),
    ("It would help to show proration in the invoice line items.", "feature_request"),
    ("Please add a dunning email preview to the billing screen.", "feature_request"),
    ("Can we get SLA breach notifications in Slack?", "feature_request"),
    ("Customer requests: I can't see the payment history, please give billing role access.",
     "feature_request"),
    ("Could you add a downloadable CSV for the CSAT report?", "feature_request"),
    # issue_report
    ("The checkout button is overlapping the footer on mobile.", "issue_report"),
    ("The monthly sales email is going to the wrong recipients.", "issue_report"),
    ("The CSAT count seems wrong.", "issue_report"),
    ("The support dashboard is loading very slowly today.", "issue_report"),
    ("The SLA timer keeps resetting on some tickets.", "issue_report"),
    ("The renewal email shows wrong due date.", "issue_report"),
    ("The invoice keeps showing as open even after payment.", "issue_report"),
    # question
    ("How should we treat orders with a status of shipped or delivered when calculating completed orders?",
     "question"),
    ("Does the completed date represent the fulfillment date or the revenue recognition date?",
     "question"),
    ("Clarify whether subscriptions.current_period_end is inclusive or exclusive for billing.",
     "question"),
    ("Does tickets.first_response_at include automated email responses or only human agent replies?",
     "question"),
    ("Is the CSAT metric counted from received surveys or closed tickets?", "question"),
    ("Why is revenue excluding cancelled orders?", "question"),
]

failures = []

# Negatives
for i, fb in enumerate(NEG):
    r = rare_class_gate(fb)
    if i == NEG_EXPECT_QUESTION:
        if (r or {}).get("feedback_type") != "question":
            failures.append(f"NEG[43] expected question, got {r!r}: {fb!r}")
        continue
    if r is not None:
        failures.append(f"NEG[{i+1}] gate fired {r.get('feedback_type')!r}: {fb!r}")

# Positives
for fb, want in POS:
    r = rare_class_gate(fb)
    if (r or {}).get("feedback_type") != want:
        failures.append(f"POS expected {want!r}, got {r!r}: {fb!r}")

# Ordering: feature_request frame inside a question must win as feature_request
# (frame checked first), but only when unambiguous.
r = rare_class_gate("Can we get a bulk export button for the order report?")
if (r or {}).get("feedback_type") != "feature_request":
    failures.append(f"ordering check: {r!r}")

if failures:
    print(f"FAIL: {len(failures)} gate mismatches")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print(f"OK: {len(NEG)} negatives + {len(POS)} positives all passed")