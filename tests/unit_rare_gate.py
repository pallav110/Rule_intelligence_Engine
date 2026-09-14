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
    # --- new #152 feature_request seeds (must be gated by FR frames) ---
    # ecommerce
    ("Please add an order export button for the reports page.", "feature_request"),
    ("Can we get a restock alert for low inventory products?", "feature_request"),
    ("It would be helpful to show order delivery dates on the summary page.", "feature_request"),
    ("Please create a download link for the returns report.", "feature_request"),
    ("Could you provide a monthly summary email for refunds?", "feature_request"),
    ("Kindly add a currency selector to the checkout page.", "feature_request"),
    # customer_support
    ("Please add a bulk close option for tickets.", "feature_request"),
    ("Can we get a priority flag on the ticket list page?", "feature_request"),
    ("It would be helpful to show agent names on the dashboard.", "feature_request"),
    ("Please create a reassign button for the agent queue view.", "feature_request"),
    ("Could you provide an SLA breach export for managers?", "feature_request"),
    # saas_subscription
    ("Please add a usage report for active subscriptions.", "feature_request"),
    ("Can we get a plan comparison view on the billing page?", "feature_request"),
    ("It would be helpful to show invoice due dates on the dashboard.", "feature_request"),
    ("Please create a proration preview for the invoice screen.", "feature_request"),
    ("Could you provide a dunning email preview for trial expiries?", "feature_request"),
    # --- new #152 issue_report seeds (must be gated by IR frames) ---
    # ecommerce
    ("The orders page is stuck on the loading spinner today.", "issue_report"),
    ("The refund report shows the wrong amount for returned items.", "issue_report"),
    ("The product image is missing on the checkout page.", "issue_report"),
    ("The dashboard is loading very slowly for the sales report.", "issue_report"),
    ("The discount banner keeps overlapping the add-to-cart button.", "issue_report"),
    ("The payment confirmation email is going to the wrong address.", "issue_report"),
    ("The refund figure seems off on the order report.", "issue_report"),
    ("The order page shows the wrong phone number for shipped orders.", "issue_report"),
    # customer_support
    ("The agent console is stuck on a blank screen after login.", "issue_report"),
    ("The CSAT dashboard shows the wrong score today.", "issue_report"),
    ("The support email is going to the wrong queue.", "issue_report"),
    ("The ticket page keeps loading slowly for large accounts.", "issue_report"),
    ("The SLA timer seems to be stuck at zero for some tickets.", "issue_report"),
    ("The notification banner is overlapping the reply box.", "issue_report"),
    ("The satisfaction survey page is missing the comment field.", "issue_report"),
    # saas_subscription
    ("The subscription page is stuck on the payment spinner.", "issue_report"),
    ("The invoice PDF shows the wrong amount after currency conversion.", "issue_report"),
    ("The billing email is going to the wrong contact for the account.", "issue_report"),
    ("The MRR dashboard keeps loading slowly on month-end.", "issue_report"),
    ("The dunning banner is missing the upcoming renewal notice.", "issue_report"),
    ("The trial count seems off for the current plan tier.", "issue_report"),
    ("The payment page shows the wrong currency symbol.", "issue_report"),
    # --- new #152 question seeds (must be gated by Q frames) ---
    ("Does tickets.first_response_at include weekends in the SLA timing?", "question"),
    ("Does invoices.status include voided drafts when computing outstanding balance?", "question"),
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

# General feedback has no gate — it must NEVER be stolen by an FR/IR/Q frame.
# These are the new #152 general_feedback seeds, which are deliberately phrased
# to avoid every gate frame.
GF_NO_GATE = [
    "Checkout speed has improved a lot this week, nice work.",
    "The mobile shopping experience has gotten much better lately.",
    "I really appreciate how quickly support resolved my issue.",
    "The new product inventory feature looks clean overall.",
    "Support agents have been really responsive this quarter.",
    "The new ticket layout feels more organized overall.",
    "Thanks for the quick turnaround on my last report.",
    "The agent experience with this tool has improved noticeably.",
    "Billing seems more straightforward with the new dashboard.",
    "The self-serve portal has made renewals much easier for us.",
    "Great to see proration details now shown on invoices.",
    "Thanks for fixing the invoice errors we reported last week.",
]
for fb in GF_NO_GATE:
    r = rare_class_gate(fb)
    if r is not None:
        failures.append(f"GF_NO_GATE gate fired {r.get('feedback_type')!r}: {fb!r}")

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