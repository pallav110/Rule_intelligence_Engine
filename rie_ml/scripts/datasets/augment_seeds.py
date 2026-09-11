#!/usr/bin/env python3
"""Draft corrected seed records: balance rule_category toward spec 4.8, close
missing feedback_type gaps (general_feedback, feature_request), add scope /
time_window / column-bearing rules with ALL annotation fields populated.

Outputs new records to rie_ml/scripts/datasets/seed_augment.jsonl (validation
copy) and, after validation, patches each domain seed.jsonl by appending.

Run from repo root:  python3 rie_ml/scripts/datasets/augment_seeds.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent  # repo root
DOMAIN_VER = {
    "ecommerce": "ecommerce_v0.1.0",
    "customer_support": "customer_support_v0.1.0",
    "saas_subscription": "saas_subscription_v0.1.0",
}


def rec(domain, fid, rfid, text, ftype, category=None, actionable=True,
        clarif=False, schema_tables=(), schema_columns=(), rules=(), **extra):
    r = {
        "feedback_id": fid,
        "domain": domain,
        "domain_pack_version": DOMAIN_VER[domain],
        "rule_family_id": rfid,
        "feedback_text": text,
        "feedback_type": ftype,
        "rule_category": category,
        "is_actionable": actionable,
        "requires_clarification": clarif,
        "schema_context": {
            "available_tables": list(schema_tables),
            "available_columns": list(schema_columns),
        },
        "rules": list(rules),
        "annotation_version": "ann_v0.2.0",
        "source": "manual",
    }
    r.update(extra)
    return r


def rule(business_term, operation, conds, scope="global", time_window=None,
         threshold=None, tables=(), columns=()):
    return {
        "business_term": business_term,
        "operation": operation,
        "conditions": [dict(field=f, operator=op, value=v) for (f, op, v) in conds],
        "scope": scope,
        "time_window": time_window,
        "threshold": threshold,
        "affected_entities": {
            "tables": list(tables),
            "columns": list(columns),
        },
    }


# ---------------------------------------------------------------------------
# ECOMMERCE
# ---------------------------------------------------------------------------
EC = []
# metric_definition (balance metric share, add scope/time)
EC.append(rec(
    "ecommerce", "EC_FB100", "ecommerce_R0100",
    "Gross merchandise value should include only payments that successfully settled in each region.",
    "business_rule", "metric_definition",
    schema_tables=["payments", "regions"], schema_columns=["payments.status", "payments.amount", "regions.name"],
    rules=[rule(
        "gross merchandise value", "include",
        [("payments.status", "equals", "settled")],
        scope="each region", tables=["payments", "regions"], columns=["payments.status", "payments.amount"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB101", "ecommerce_R0101",
    "Order value for the monthly report must exclude test orders in North America.",
    "business_rule", "metric_definition",
    schema_tables=["orders", "customers"], schema_columns=["orders.total_amount", "orders.is_test", "customers.region_id"],
    rules=[rule(
        "order value", "exclude",
        [("orders.is_test", "equals", "true")],
        scope="North America", time_window={"type": "fixed", "value": "month", "unit": "month"},
        tables=["orders"], columns=["orders.total_amount", "orders.is_test"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB102", "ecommerce_R0102",
    "Average order size should be computed only over completed orders for the last 30 days.",
    "business_rule", "metric_definition",
    schema_tables=["orders"], schema_columns=["orders.status", "orders.completed_at", "orders.total_amount"],
    rules=[rule(
        "average order size", "include",
        [("orders.status", "equals", "completed")],
        scope="storefront", time_window={"type": "rolling", "value": 30, "unit": "days"},
        tables=["orders"], columns=["orders.status", "orders.total_amount"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB103", "ecommerce_R0103",
    "Net revenue should subtract refunded amounts for the current quarter.",
    "business_rule", "metric_definition",
    schema_tables=["orders", "refunds"], schema_columns=["orders.total_amount", "refunds.status", "refunds.amount"],
    rules=[rule(
        "net revenue", "subtract",
        [("refunds.status", "equals", "completed")],
        scope="all regions", time_window={"type": "fixed", "value": "quarter", "unit": "month"},
        tables=["orders", "refunds"], columns=["orders.total_amount", "refunds.amount"]),
    ]))
# filter_rule (4)  -- scope/time_window heavy
EC.append(rec(
    "ecommerce", "EC_FB104", "ecommerce_R0104",
    "Show only product categories that are still active to every customer.",
    "business_rule", "filter_rule",
    schema_tables=["products"], schema_columns=["products.is_active", "products.category"],
    rules=[rule(
        "product catalog", "restrict",
        [("products.is_active", "equals", "true")],
        scope="every customer", tables=["products"], columns=["products.is_active"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB105", "ecommerce_R0105",
    "Internal customer orders must not appear in regional sales reports.",
    "business_rule", "filter_rule",
    schema_tables=["orders", "customers"], schema_columns=["customers.is_internal", "orders.status"],
    rules=[rule(
        "regional sales", "exclude",
        [("customers.is_internal", "equals", "true")],
        scope="regional", tables=["orders", "customers"], columns=["customers.is_internal"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB106", "ecommerce_R0106",
    "Discount should not apply to orders placed more than a year ago.",
    "business_rule", "filter_rule",
    schema_tables=["orders"], schema_columns=["orders.order_date", "orders.discount_pct"],
    rules=[rule(
        "discount eligibility", "restrict",
        [("orders.order_date", "greater_than", "2025-09-01")],
        scope="retail", tables=["orders"], columns=["orders.order_date"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB107", "ecommerce_R0107",
    "Backend reports should include products that have a listing price above zero.",
    "business_rule", "filter_rule",
    schema_tables=["products"], schema_columns=["products.list_price", "products.name"],
    rules=[rule(
        "product reports", "include",
        [("products.list_price", "greater_than", 0)],
        scope="backend reports", tables=["products"], columns=["products.list_price"]),
    ]))
# mapping_rule (3)
EC.append(rec(
    "ecommerce", "EC_FB108", "ecommerce_R0108",
    "Map order status shipped and delivered to fulfilled for the analytics dashboard.",
    "business_rule", "mapping_rule",
    schema_tables=["orders"], schema_columns=["orders.status"],
    rules=[rule(
        "order fulfillment status", "map",
        [("orders.status", "in", ["shipped", "delivered"])],
        scope="analytics", tables=["orders"], columns=["orders.status"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB109", "ecommerce_R0109",
    "Map payment method netbanking and upi to digital for the settlement report.",
    "business_rule", "mapping_rule",
    schema_tables=["payments"], schema_columns=["payments.payment_method"],
    rules=[rule(
        "payment method", "map",
        [("payments.payment_method", "in", ["netbanking", "upi"])],
        scope="settlement", tables=["payments"], columns=["payments.payment_method"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB110", "ecommerce_R0110",
    "Map inter customer segment to business segment for reporting by region.",
    "business_rule", "mapping_rule",
    schema_tables=["customers"], schema_columns=["customers.region_id"],
    rules=[rule(
        "customer segment", "map",
        [("customers.region_id", "is_not_null", "true")],
        scope="by region", tables=["customers"], columns=["customers.region_id"]),
    ]))
# access_rule (4)
EC.append(rec(
    "ecommerce", "EC_FB111", "ecommerce_R0111",
    "Only the finance role may view refund details of any order.",
    "business_rule", "access_rule",
    schema_tables=["refunds", "orders"], schema_columns=["refunds.status", "refunds.amount", "orders.order_id"],
    rules=[rule(
        "refund visibility", "restrict",
        [("refunds.status", "equals", "completed")],
        scope="finance role", tables=["refunds", "orders"], columns=["refunds.amount"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB112", "ecommerce_R0112",
    "Customer support agents should not access order payment transaction ids.",
    "business_rule", "access_rule",
    schema_tables=["payments", "orders"], schema_columns=["payments.transaction_id", "payments.payment_method"],
    rules=[rule(
        "transaction id access", "exclude",
        [("payments.payment_method", "is_not_null", "true")],
        scope="support agents", tables=["payments", "orders"], columns=["payments.transaction_id"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB113", "ecommerce_R0113",
    "Catalog editors are restricted to modifying products within their region only.",
    "business_rule", "access_rule",
    schema_tables=["products", "regions"], schema_columns=["products.name", "regions.name", "products.is_active"],
    rules=[rule(
        "catalog edit", "restrict",
        [("products.is_active", "equals", "true")],
        scope="their region", tables=["products", "regions"], columns=["products.is_active"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB114", "ecommerce_R0114",
    "Analysts should be limited to reading aggregated refund totals, not individual orders.",
    "business_rule", "access_rule",
    schema_tables=["refunds", "orders"], schema_columns=["refunds.amount", "orders.order_id", "refunds.status"],
    rules=[rule(
        "refund analytics", "restrict",
        [("refunds.status", "is_not_null", "true")],
        scope="analysts", tables=["refunds", "orders"], columns=["refunds.amount"]),
    ]))
# data_quality_rule (3)
EC.append(rec(
    "ecommerce", "EC_FB115", "ecommerce_R0115",
    "Reject product records where the listing price is negative.",
    "business_rule", "data_quality_rule",
    schema_tables=["products"], schema_columns=["products.list_price"],
    rules=[rule(
        "product data quality", "exclude",
        [("products.list_price", "less_than", 0)],
        scope="catalog", tables=["products"], columns=["products.list_price"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB116", "ecommerce_R0116",
    "Drop order items that have a null quantity before computing inventory.",
    "business_rule", "data_quality_rule",
    schema_tables=["order_items"], schema_columns=["order_items.quantity"],
    rules=[rule(
        "inventory quantity", "exclude",
        [("order_items.quantity", "is_null", "true")],
        scope="inventory", tables=["order_items", "products"], columns=["order_items.quantity"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB117", "ecommerce_R0117",
    "Orders with an empty customer id must be excluded from the customer report.",
    "business_rule", "data_quality_rule",
    schema_tables=["orders", "customers"], schema_columns=["orders.customer_id"],
    rules=[rule(
        "customer order report", "exclude",
        [("orders.customer_id", "is_null", "true")],
        scope="customer report", tables=["orders", "customers"], columns=["orders.customer_id"]),
    ]))
# join_rule (2)
EC.append(rec(
    "ecommerce", "EC_FB118", "ecommerce_R0118",
    "Revenue joins orders to payments on order_id for each completed payment.",
    "business_rule", "join_rule",
    schema_tables=["orders", "payments"], schema_columns=["orders.order_id", "payments.order_id", "payments.status"],
    rules=[rule(
        "revenue join", "add",
        [("payments.status", "equals", "completed")],
        scope="payments join", tables=["orders", "payments"], columns=["orders.order_id", "payments.order_id"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB119", "ecommerce_R0119",
    "Attach customer region to each order by matching region id across tables.",
    "business_rule", "join_rule",
    schema_tables=["customers", "orders", "regions"], schema_columns=["customers.region_id", "regions.region_id", "orders.customer_id"],
    rules=[rule(
        "customer region lookup", "add",
        [("customers.region_id", "equals", "regions.region_id")],
        scope="regional reporting", tables=["customers", "orders", "regions"], columns=["customers.region_id"]),
    ]))

# non-rule feedback_types -- close gaps
EC.append(rec(
    "ecommerce", "EC_FB120", "ecommerce_nonrule_020",
    "The reports are downloading really fast now, thank you.",
    "general_feedback", None, actionable=False,
    schema_tables=[], schema_columns=[]))
EC.append(rec(
    "ecommerce", "EC_FB121", "ecommerce_nonrule_021",
    "Love the new dashboard colors, nice work by the team.",
    "general_feedback", None, actionable=False,
    schema_tables=[], schema_columns=[]))
EC.append(rec(
    "ecommerce", "EC_FB122", "ecommerce_nonrule_022",
    "Great tool, no complaints so far.",
    "general_feedback", None, actionable=False,
    schema_tables=[], schema_columns=[]))
EC.append(rec(
    "ecommerce", "EC_FB123", "ecommerce_nonrule_023",
    "We appreciate the quick support on the last query.",
    "general_feedback", None, actionable=False,
    schema_tables=[], schema_columns=[]))
EC.append(rec(
    "ecommerce", "EC_FB124", "ecommerce_nonrule_024",
    "Can we get a bulk export button for the order report?",
    "feature_request", None, actionable=False,
    schema_tables=["orders"], schema_columns=["orders.order_id"]))
EC.append(rec(
    "ecommerce", "EC_FB125", "ecommerce_nonrule_025",
    "Please add a dark mode for the admin panel.",
    "feature_request", None, actionable=False,
    schema_tables=[], schema_columns=[]))
EC.append(rec(
    "ecommerce", "EC_FB126", "ecommerce_nonrule_026",
    "It would be nice to notify the warehouse when stock runs low.",
    "feature_request", None, actionable=False,
    schema_tables=["products"], schema_columns=["products.name"]))
EC.append(rec(
    "ecommerce", "EC_FB127", "ecommerce_nonrule_027",
    "Kindly add timezone support to the order date filters.",
    "feature_request", None, actionable=False,
    schema_tables=["orders"], schema_columns=["orders.order_date"]))
EC.append(rec(
    "ecommerce", "EC_FB128", "ecommerce_nonrule_028",
    "should we count orders that get refunded in the same week?",
    "question", None, actionable=False, clarif=True,
    schema_tables=["orders", "refunds"], schema_columns=["orders.status", "refunds.status"]))
EC.append(rec(
    "ecommerce", "EC_FB129", "ecommerce_nonrule_029",
    "What counts as an active product for the catalog store?",
    "question", None, actionable=False, clarif=True,
    schema_tables=["products"], schema_columns=["products.is_active"]))
EC.append(rec(
    "ecommerce", "EC_FB130", "ecommerce_nonrule_030",
    "The monthly sales email is going to the wrong recipients.",
    "issue_report", None, actionable=False,
    schema_tables=[], schema_columns=[]))

# ---------------------------------------------------------------------------
# CUSTOMER SUPPORT
# ---------------------------------------------------------------------------
CS = []
CS.append(rec(
    "customer_support", "CS_FB100", "CS_R0100",
    "First response time metric should only include tickets opened in the last 30 days.",
    "business_rule", "metric_definition",
    schema_tables=["tickets"], schema_columns=["tickets.opened_at", "tickets.first_response_at"],
    rules=[rule(
        "first response time", "include",
        [("tickets.first_response_at", "is_not_null", "true")],
        scope="support", time_window={"type": "rolling", "value": 30, "unit": "days"},
        tables=["tickets"], columns=["tickets.opened_at", "tickets.first_response_at"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB101", "CS_R0101",
    "Backlog count must exclude internal test tickets for every department.",
    "business_rule", "metric_definition",
    schema_tables=["tickets", "departments"], schema_columns=["tickets.is_internal", "tickets.status", "departments.name"],
    rules=[rule(
        "backlog count", "exclude",
        [("tickets.is_internal", "equals", "true")],
        scope="every department", tables=["tickets", "departments"], columns=["tickets.is_internal"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB102", "CS_R0102",
    "Satisfaction score should be counted only from surveys that were actually responded on.",
    "business_rule", "metric_definition",
    schema_tables=["satisfaction_scores"], schema_columns=["satisfaction_scores.score", "satisfaction_scores.response_status"],
    rules=[rule(
        "satisfaction score", "include",
        [("satisfaction_scores.response_status", "equals", "responded")],
        scope="all regions", tables=["satisfaction_scores"], columns=["satisfaction_scores.score"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB103", "CS_R0103",
    "Resolved in time metric should subtract tickets reopened after resolution.",
    "business_rule", "metric_definition",
    schema_tables=["tickets"], schema_columns=["tickets.reopen_count", "tickets.status"],
    rules=[rule(
        "resolved in time", "subtract",
        [("tickets.reopen_count", "greater_than", 0)],
        scope="quarterly", tables=["tickets"], columns=["tickets.reopen_count"]),
    ]))
# filter
CS.append(rec(
    "customer_support", "CS_FB104", "CS_R0104",
    "Si only tickets assigned to the priority queue should surface in the dashboard.",
    "business_rule", "filter_rule",
    schema_tables=["tickets", "departments"], schema_columns=["tickets.priority", "departments.queue_name"],
    rules=[rule(
        "priority dashboard", "restrict",
        [("tickets.priority", "equals", "high")],
        scope="priority queue", tables=["tickets", "departments"], columns=["tickets.priority"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB105", "CS_R0105",
    "Do not include tickets flagged as duplicates in the resolution report.",
    "business_rule", "filter_rule",
    schema_tables=["tickets"], schema_columns=["tickets.is_duplicate", "tickets.status"],
    rules=[rule(
        "resolution report", "exclude",
        [("tickets.is_duplicate", "equals", "true")],
        scope="by channel", tables=["tickets"], columns=["tickets.is_duplicate"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB106", "CS_R0106",
    "Show only tickets that breached SLA for the weekly review.",
    "business_rule", "filter_rule",
    schema_tables=["tickets"], schema_columns=["tickets.sla_breach", "tickets.closed_at"],
    rules=[rule(
        "sla review", "include",
        [("tickets.sla_breach", "equals", "true")],
        scope="weekly review", time_window={"type": "fixed", "value": "week", "unit": "week"},
        tables=["tickets"], columns=["tickets.sla_breach"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB107", "CS_R0107",
    "Satisfaction reports should exclude surveys from internal customers.",
    "business_rule", "filter_rule",
    schema_tables=["satisfaction_scores", "customers"], schema_columns=["satisfaction_scores.score", "customers.is_internal"],
    rules=[rule(
        "satisfaction report", "exclude",
        [("customers.is_internal", "equals", "true")],
        scope="external only", tables=["satisfaction_scores", "customers"], columns=["customers.is_internal"]),
    ]))
# mapping
CS.append(rec(
    "customer_support", "CS_FB108", "CS_R0108",
    "Map ticket priority high and urgent to critical for the escalation board.",
    "business_rule", "mapping_rule",
    schema_tables=["tickets"], schema_columns=["tickets.priority"],
    rules=[rule(
        "ticket priority", "map",
        [("tickets.priority", "in", ["high", "urgent"])],
        scope="escalation", tables=["tickets"], columns=["tickets.priority"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB109", "CS_R0109",
    "Map received statuses closed and solved to done in the report.",
    "business_rule", "mapping_rule",
    schema_tables=["tickets"], schema_columns=["tickets.status"],
    rules=[rule(
        "ticket status", "map",
        [("tickets.status", "in", ["closed", "solved"])],
        scope="reporting", tables=["tickets"], columns=["tickets.status"]),
    ]))
# access
CS.append(rec(
    "customer_support", "CS_FB110", "CS_R0110",
    "Only managers may view satisfaction comment text of individual tickets.",
    "business_rule", "access_rule",
    schema_tables=["satisfaction_scores"], schema_columns=["satisfaction_scores.comment", "satisfaction_scores.is_positive"],
    rules=[rule(
        "satisfaction comment access", "restrict",
        [("satisfaction_scores.is_positive", "is_not_null", "true")],
        scope="managers", tables=["satisfaction_scores"], columns=["satisfaction_scores.comment"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB111", "CS_R0111",
    "Agents are restricted to tickets within their own department.",
    "business_rule", "access_rule",
    schema_tables=["tickets", "departments"], schema_columns=["tickets.department_id", "departments.department_id"],
    rules=[rule(
        "agent visibility", "restrict",
        [("tickets.department_id", "equals", "departments.department_id")],
        scope="own department", tables=["tickets", "departments"], columns=["tickets.department_id"]),
    ]))
# data quality
CS.append(rec(
    "customer_support", "CS_FB112", "CS_R0112",
    "Drop tickets that have no subject before computing the funnel.",
    "business_rule", "data_quality_rule",
    schema_tables=["tickets"], schema_columns=["tickets.subject"],
    rules=[rule(
        "ticket funnel", "exclude",
        [("tickets.subject", "is_null", "true")],
        scope="funnel", tables=["tickets"], columns=["tickets.subject"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB113", "CS_R0113",
    "Exclude duplicated tickets where the duplicate flag is missing from the stats.",
    "business_rule", "data_quality_rule",
    schema_tables=["tickets"], schema_columns=["tickets.is_duplicate", "tickets.duplicate_of_ticket_id"],
    rules=[rule(
        "duplicate stats", "exclude",
        [("tickets.is_duplicate", "is_null", "true")],
        scope="stats", tables=["tickets"], columns=["tickets.is_duplicate"]),
    ]))
# join
CS.append(rec(
    "customer_support", "CS_FB114", "CS_R0114",
    "Join tickets to satisfaction scores on ticket_id for the support score by agent.",
    "business_rule", "join_rule",
    schema_tables=["tickets", "satisfaction_scores", "agents"], schema_columns=["tickets.ticket_id", "satisfaction_scores.ticket_id", "tickets.assigned_agent_id"],
    rules=[rule(
        "support score", "add",
        [("satisfaction_scores.ticket_id", "equals", "tickets.ticket_id")],
        scope="by agent", tables=["tickets", "satisfaction_scores", "agents"], columns=["tickets.assigned_agent_id"]),
    ]))

# non-rule gaps
CS.append(rec(
    "customer_support", "CS_FB120", "CS_nonrule_020",
    "The team resolved my issue super fast, genuinely impressed.",
    "general_feedback", None, actionable=False,
    schema_tables=[], schema_columns=[]))
CS.append(rec(
    "customer_support", "CS_FB121", "CS_nonrule_021",
    "Support is very helpful, keep it up.",
    "general_feedback", None, actionable=False,
    schema_tables=[], schema_columns=[]))
CS.append(rec(
    "customer_support", "CS_FB122", "CS_nonrule_022",
    "No issues so far, dashboard looks clean.",
    "general_feedback", None, actionable=False,
    schema_tables=[], schema_columns=[]))
CS.append(rec(
    "customer_support", "CS_FB123", "CS_nonrule_023",
    "Terrific experience with the knowledge base articles.",
    "general_feedback", None, actionable=False,
    schema_tables=[], schema_columns=[]))
CS.append(rec(
    "customer_support", "CS_FB124", "CS_nonrule_024",
    "Please add a bulk reassign option for tickets.",
    "feature_request", None, actionable=False,
    schema_tables=["tickets"], schema_columns=["tickets.assigned_agent_id"]))
CS.append(rec(
    "customer_support", "CS_FB125", "CS_nonrule_025",
    "Could you add a downloadable CSV for the CSAT report?",
    "feature_request", None, actionable=False,
    schema_tables=["satisfaction_scores"], schema_columns=["satisfaction_scores.score"]))
CS.append(rec(
    "customer_support", "CS_FB126", "CS_nonrule_026",
    "Can we get SLA breach notifications in Slack?",
    "feature_request", None, actionable=False,
    schema_tables=["tickets"], schema_columns=["tickets.sla_breach"]))
CS.append(rec(
    "customer_support", "CS_FB127", "CS_nonrule_027",
    "It would help to auto-merge duplicate tickets.",
    "feature_request", None, actionable=False,
    schema_tables=["tickets"], schema_columns=["tickets.is_duplicate"]))
CS.append(rec(
    "customer_support", "CS_FB128", "CS_nonrule_028",
    "Should we count reopened tickets inside first response time?",
    "question", None, actionable=False, clarif=True,
    schema_tables=["tickets"], schema_columns=["tickets.reopen_count", "tickets.first_response_at"]))
CS.append(rec(
    "customer_support", "CS_FB129", "CS_nonrule_029",
    "what does escalated priority mean exactly?",
    "question", None, actionable=False, clarif=True,
    schema_tables=["tickets"], schema_columns=["tickets.priority"]))
CS.append(rec(
    "customer_support", "CS_FB130", "CS_nonrule_030",
    "The SLA timer keeps resetting on some tickets.",
    "issue_report", None, actionable=False,
    schema_tables=["tickets"], schema_columns=["tickets.sla_breach"]))

# ---------------------------------------------------------------------------
# SAAS SUBSCRIPTION
# ---------------------------------------------------------------------------
SAAS = []
SAAS.append(rec(
    "saas_subscription", "SAAS_FB100", "SAAS_R0100",
    "Monthly recurring revenue should include subscriptions active at period end.",
    "business_rule", "metric_definition",
    schema_tables=["subscriptions"], schema_columns=["subscriptions.status", "subscriptions.plan_id"],
    rules=[rule(
        "monthly recurring revenue", "include",
        [("subscriptions.status", "equals", "active")],
        scope="period end", time_window={"type": "fixed", "value": "month", "unit": "month"},
        tables=["subscriptions", "subscription_plans"], columns=["subscriptions.status"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB101", "SAAS_R0101",
    "Annual contract value must exclude free plan subscriptions.",
    "business_rule", "metric_definition",
    schema_tables=["subscriptions", "subscription_plans"], schema_columns=["subscriptions.plan_id", "subscription_plans.price_cents"],
    rules=[rule(
        "annual contract value", "exclude",
        [("subscription_plans.price_cents", "equals", 0)],
        scope="all products", tables=["subscriptions", "subscription_plans"], columns=["subscription_plans.price_cents"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB102", "SAAS_R0102",
    "Active users count should only include users with an active enrollment.",
    "business_rule", "metric_definition",
    schema_tables=["users"], schema_columns=["users.is_active", "users.role"],
    rules=[rule(
        "active users", "include",
        [("users.is_active", "equals", "true")],
        scope="organization wide", tables=["users"], columns=["users.is_active"]),
    ]))
# filter
SAAS.append(rec(
    "saas_subscription", "SAAS_FB103", "SAAS_R0103",
    "Revenue dashboards should show only non-trial subscriptions in each industry.",
    "business_rule", "filter_rule",
    schema_tables=["subscriptions", "subscription_plans"], schema_columns=["subscriptions.status", "subscription_plans.trial_days", "organizations.industry"],
    rules=[rule(
        "subscription revenue", "exclude",
        [("subscriptions.status", "equals", "trialing")],
        scope="each industry", tables=["subscriptions", "subscription_plans", "organizations"], columns=["subscriptions.status"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB104", "SAAS_R0104",
    "Do not count invoices that are still open in the overdue report.",
    "business_rule", "filter_rule",
    schema_tables=["invoices"], schema_columns=["invoices.status", "invoices.due_date"],
    rules=[rule(
        "overdue report", "exclude",
        [("invoices.status", "equals", "open")],
        scope="billing", tables=["invoices"], columns=["invoices.status"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB105", "SAAS_R0105",
    "Only include payments marked succeeded in the cash report.",
    "business_rule", "filter_rule",
    schema_tables=["payments", "invoices"], schema_columns=["payments.status", "payments.amount_cents"],
    rules=[rule(
        "cash report", "include",
        [("payments.status", "equals", "succeeded")],
        scope="cash basis", tables=["payments", "invoices"], columns=["payments.status"]),
    ]))
# mapping
SAAS.append(rec(
    "saas_subscription", "SAAS_FB106", "SAAS_R0106",
    "Map plan billing intervals monthly and yearly for the churn report.",
    "business_rule", "mapping_rule",
    schema_tables=["subscription_plans"], schema_columns=["subscription_plans.billing_interval"],
    rules=[rule(
        "billing interval", "map",
        [("subscription_plans.billing_interval", "in", ["monthly", "yearly"])],
        scope="churn report", tables=["subscription_plans"], columns=["subscription_plans.billing_interval"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB107", "SAAS_R0107",
    "Map currency usd to usd in the consolidated statement.",
    "business_rule", "mapping_rule",
    schema_tables=["subscription_plans", "invoices"], schema_columns=["subscription_plans.currency", "invoices.currency"],
    rules=[rule(
        "currency mapping", "map",
        [("invoices.currency", "equals", "usd")],
        scope="consolidated", tables=["subscription_plans", "invoices"], columns=["invoices.currency"]),
    ]))
# access
SAAS.append(rec(
    "saas_subscription", "SAAS_FB108", "SAAS_R0108",
    "Only finance can view payment failure codes for an organization.",
    "business_rule", "access_rule",
    schema_tables=["payments"], schema_columns=["payments.failure_code", "payments.status"],
    rules=[rule(
        "payment failure access", "restrict",
        [("payments.failure_code", "is_not_null", "true")],
        scope="finance", tables=["payments", "invoices"], columns=["payments.failure_code"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB109", "SAAS_R0109",
    "Sales should be restricted to viewing only their own organization accounts.",
    "business_rule", "access_rule",
    schema_tables=["organizations"], schema_columns=["organizations.industry", "organizations.name", "organizations.is_active"],
    rules=[rule(
        "sales visibility", "restrict",
        [("organizations.is_active", "equals", "true")],
        scope="sales accounts", tables=["organizations", "users"], columns=["organizations.name"]),
    ]))
# data quality
SAAS.append(rec(
    "saas_subscription", "SAAS_FB110", "SAAS_R0110",
    "Drop invoices with a negative amount from the aging report.",
    "business_rule", "data_quality_rule",
    schema_tables=["invoices"], schema_columns=["invoices.amount_cents"],
    rules=[rule(
        "invoice aging", "exclude",
        [("invoices.amount_cents", "less_than", 0)],
        scope="aging", tables=["invoices"], columns=["invoices.amount_cents"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB111", "SAAS_R0111",
    "Exclude organizations that have no active status flag from reports.",
    "business_rule", "data_quality_rule",
    schema_tables=["organizations"], schema_columns=["organizations.is_active"],
    rules=[rule(
        "org report quality", "exclude",
        [("organizations.is_active", "is_null", "true")],
        scope="reports", tables=["organizations", "users"], columns=["organizations.is_active"]),
    ]))
# join
SAAS.append(rec(
    "saas_subscription", "SAAS_FB112", "SAAS_R0112",
    "Attach the plan name to each subscription by matching plan id.",
    "business_rule", "join_rule",
    schema_tables=["subscriptions", "subscription_plans"], schema_columns=["subscriptions.plan_id", "subscription_plans.plan_id"],
    rules=[rule(
        "plan lookup", "add",
        [("subscriptions.plan_id", "equals", "subscription_plans.plan_id")],
        scope="billing reports", tables=["subscriptions", "subscription_plans"], columns=["subscriptions.plan_id"]),
    ]))

# non-rule gaps
SAAS.append(rec(
    "saas_subscription", "SAAS_FB120", "SAAS_nonrule_020",
    "Billing team is doing a great job this quarter.",
    "general_feedback", None, actionable=False,
    schema_tables=[], schema_columns=[]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB121", "SAAS_nonrule_021",
    "The new subscription page looks amazing.",
    "general_feedback", None, actionable=False,
    schema_tables=[], schema_columns=[]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB122", "SAAS_nonrule_022",
    "App is working well so far, thanks.",
    "general_feedback", None, actionable=False,
    schema_tables=[], schema_columns=[]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB123", "SAAS_nonrule_023",
    "Great onboarding experience for new users.",
    "general_feedback", None, actionable=False,
    schema_tables=["users"], schema_columns=["users.role"]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB124", "SAAS_nonrule_024",
    "Please add a dunning email preview to the billing screen.",
    "feature_request", None, actionable=False,
    schema_tables=["payments"], schema_columns=["payments.failure_code"]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB125", "SAAS_nonrule_025",
    "Can we get a bulk seat increase for our team?",
    "feature_request", None, actionable=False,
    schema_tables=["users"], schema_columns=["users.role"]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB126", "SAAS_nonrule_026",
    "It would help to show proration in the invoice line items.",
    "feature_request", None, actionable=False,
    schema_tables=["invoices"], schema_columns=["invoices.amount_cents"]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB127", "SAAS_nonrule_027",
    "Kindly add a CSV export for MRR by plan.",
    "feature_request", None, actionable=False,
    schema_tables=["subscriptions", "subscription_plans"], schema_columns=["subscriptions.plan_id"]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB128", "SAAS_nonrule_028",
    "Should prorated amounts count toward the current subscription period?",
    "question", None, actionable=False, clarif=True,
    schema_tables=["subscriptions"], schema_columns=["subscriptions.prorated", "subscriptions.current_period_end"]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB129", "SAAS_nonrule_029",
    "what happens to a trial when it converts to paid?",
    "question", None, actionable=False, clarif=True,
    schema_tables=["subscriptions", "subscription_plans"], schema_columns=["subscriptions.status", "subscription_plans.trial_days"]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB130", "SAAS_nonrule_030",
    "The renewal email shows wrong due date.",
    "issue_report", None, actionable=False,
    schema_tables=["invoices"], schema_columns=["invoices.due_date"]))

# ---- second wave: push access_rule / data_quality / join toward spec 4.8 ----
EC.append(rec(
    "ecommerce", "EC_FB131", "ecommerce_R0131",
    "Only warehouse staff may edit product listing prices.",
    "business_rule", "access_rule",
    schema_tables=["products"], schema_columns=["products.list_price", "products.name"],
    rules=[rule(
        "price edit", "restrict",
        [("products.list_price", "is_not_null", "true")],
        scope="warehouse staff", tables=["products"], columns=["products.list_price"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB132", "ecommerce_R0132",
    "Marketing must not see payment transaction ids of any customer.",
    "business_rule", "access_rule",
    schema_tables=["payments"], schema_columns=["payments.transaction_id", "payments.payment_method"],
    rules=[rule(
        "transaction access", "exclude",
        [("payments.payment_method", "is_not_null", "true")],
        scope="marketing excluded", tables=["payments", "orders"], columns=["payments.transaction_id"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB133", "ecommerce_R0133",
    "Regional managers are limited to orders in their own region only.",
    "business_rule", "access_rule",
    schema_tables=["orders", "customers"], schema_columns=["orders.region_id", "customers.region_id", "orders.status"],
    rules=[rule(
        "regional manager scope", "restrict",
        [("orders.region_id", "equals", "customers.region_id")],
        scope="own region", tables=["orders", "customers"], columns=["orders.region_id"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB134", "ecommerce_R0134",
    "Only the ops role can view internal test order data.",
    "business_rule", "access_rule",
    schema_tables=["orders"], schema_columns=["orders.is_test", "orders.status"],
    rules=[rule(
        "internal order access", "restrict",
        [("orders.is_test", "equals", "true")],
        scope="ops role", tables=["orders"], columns=["orders.is_test"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB135", "ecommerce_R0135",
    "Finance can access refund records for any region.",
    "business_rule", "access_rule",
    schema_tables=["refunds", "regions"], schema_columns=["refunds.status", "refunds.amount"],
    rules=[rule(
        "refund finance access", "include",
        [("refunds.status", "in", ["completed", "pending"])],
        scope="all regions", tables=["refunds"], columns=["refunds.amount"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB136", "ecommerce_R0136",
    "Rows with a missing product name should be dropped before catalog sync.",
    "business_rule", "data_quality_rule",
    schema_tables=["products"], schema_columns=["products.name", "products.category"],
    rules=[rule(
        "catalog sync", "exclude",
        [("products.name", "is_null", "true")],
        scope="catalog sync", tables=["products"], columns=["products.name"]),
    ]))
EC.append(rec(
    "ecommerce", "EC_FB137", "ecommerce_R0137",
    "Join order items to products on product id for the category report.",
    "business_rule", "join_rule",
    schema_tables=["order_items", "products"], schema_columns=["order_items.product_id", "products.product_id"],
    rules=[rule(
        "product join", "add",
        [("order_items.product_id", "equals", "products.product_id")],
        scope="category report", tables=["order_items", "products"], columns=["order_items.product_id"]),
    ]))

CS.append(rec(
    "customer_support", "CS_FB131", "CS_R0131",
    "Only the ops role can see ticket event payloads.",
    "business_rule", "access_rule",
    schema_tables=["ticket_events"], schema_columns=["ticket_events.event_payload", "ticket_events.event_type"],
    rules=[rule(
        "event payload access", "restrict",
        [("ticket_events.event_type", "is_not_null", "true")],
        scope="ops role", tables=["ticket_events"], columns=["ticket_events.event_payload"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB132", "CS_R0132",
    "Agents should not see a customer's support tier when internal.",
    "business_rule", "access_rule",
    schema_tables=["customers"], schema_columns=["customers.support_tier", "customers.is_internal"],
    rules=[rule(
        "support tier access", "exclude",
        [("customers.is_internal", "equals", "true")],
        scope="agents excluded", tables=["customers"], columns=["customers.support_tier"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB133", "CS_R0133",
    "Managers may view satisfaction scores across all departments.",
    "business_rule", "access_rule",
    schema_tables=["satisfaction_scores", "departments"], schema_columns=["satisfaction_scores.score", "departments.name", "satisfaction_scores.response_status"],
    rules=[rule(
        "score visibility", "include",
        [("satisfaction_scores.response_status", "equals", "responded")],
        scope="all departments", tables=["satisfaction_scores", "departments"], columns=["satisfaction_scores.score"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB134", "CS_R0134",
    "Only admins can reassign a ticket to another department.",
    "business_rule", "access_rule",
    schema_tables=["tickets", "departments"], schema_columns=["tickets.department_id", "departments.department_id"],
    rules=[rule(
        "reassign access", "restrict",
        [("tickets.department_id", "is_not_null", "true")],
        scope="admins", tables=["tickets", "departments"], columns=["tickets.department_id"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB135", "CS_R0135",
    "Finance can view refund only ticket payment activity.",
    "business_rule", "access_rule",
    schema_tables=["tickets", "customers"], schema_columns=["tickets.status", "customers.customer_segment"],
    rules=[rule(
        "ticket finance access", "include",
        [("tickets.status", "in", ["closed", "solved"])],
        scope="finance", tables=["tickets", "customers"], columns=["tickets.status"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB136", "CS_R0136",
    "Discard survey rows that have no score value before aggregating.",
    "business_rule", "data_quality_rule",
    schema_tables=["satisfaction_scores"], schema_columns=["satisfaction_scores.score", "satisfaction_scores.nps_score"],
    rules=[rule(
        "survey aggregate", "exclude",
        [("satisfaction_scores.score", "is_null", "true")],
        scope="survey data", tables=["satisfaction_scores"], columns=["satisfaction_scores.score"]),
    ]))
CS.append(rec(
    "customer_support", "CS_FB137", "CS_R0137",
    "Join agents to tickets on assigned agent id for the utilization report.",
    "business_rule", "join_rule",
    schema_tables=["agents", "tickets"], schema_columns=["agents.agent_id", "tickets.assigned_agent_id"],
    rules=[rule(
        "agent join", "add",
        [("tickets.assigned_agent_id", "equals", "agents.agent_id")],
        scope="utilization", tables=["agents", "tickets"], columns=["tickets.assigned_agent_id"]),
    ]))

SAAS.append(rec(
    "saas_subscription", "SAAS_FB131", "SAAS_R0131",
    "Only account admins can change subscription plan billing interval.",
    "business_rule", "access_rule",
    schema_tables=["subscriptions", "subscription_plans"], schema_columns=["subscriptions.plan_id", "subscription_plans.billing_interval"],
    rules=[rule(
        "plan change access", "restrict",
        [("subscription_plans.billing_interval", "is_not_null", "true")],
        scope="account admins", tables=["subscriptions", "subscription_plans"], columns=["subscriptions.plan_id"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB132", "SAAS_R0132",
    "Finance must not see individual user emails in the export.",
    "business_rule", "access_rule",
    schema_tables=["users"], schema_columns=["users.email", "users.role", "users.is_active"],
    rules=[rule(
        "email access", "exclude",
        [("users.is_active", "equals", "true")],
        scope="finance excluded", tables=["users"], columns=["users.email"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB133", "SAAS_R0133",
    "Support agents can only view subscriptions of organizations they own.",
    "business_rule", "access_rule",
    schema_tables=["subscriptions", "organizations"], schema_columns=["subscriptions.organization_id", "organizations.organization_id"],
    rules=[rule(
        "org subscription scope", "restrict",
        [("subscriptions.organization_id", "equals", "organizations.organization_id")],
        scope="owned orgs", tables=["subscriptions", "organizations"], columns=["subscriptions.organization_id"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB134", "SAAS_R0134",
    "Only billing can view failed payment reasons.",
    "business_rule", "access_rule",
    schema_tables=["payments"], schema_columns=["payments.failure_code", "payments.status"],
    rules=[rule(
        "billing failure access", "restrict",
        [("payments.failure_code", "is_not_null", "true")],
        scope="billing", tables=["payments", "invoices"], columns=["payments.failure_code"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB135", "SAAS_R0135",
    "Sales can see invoice totals for their own customer organizations.",
    "business_rule", "access_rule",
    schema_tables=["invoices", "organizations"], schema_columns=["invoices.amount_cents", "invoices.organization_id", "organizations.organization_id"],
    rules=[rule(
        "invoice sales scope", "include",
        [("invoices.organization_id", "equals", "organizations.organization_id")],
        scope="sales orgs", tables=["invoices", "organizations"], columns=["invoices.amount_cents"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB136", "SAAS_R0136",
    "Remove product events that have no user id before analytics.",
    "business_rule", "data_quality_rule",
    schema_tables=["product_events"], schema_columns=["product_events.user_id", "product_events.event_type"],
    rules=[rule(
        "event analytics", "exclude",
        [("product_events.user_id", "is_null", "true")],
        scope="analytics", tables=["product_events"], columns=["product_events.user_id"]),
    ]))
SAAS.append(rec(
    "saas_subscription", "SAAS_FB137", "SAAS_R0137",
    "Join payments to invoices on invoice id for the collection report.",
    "business_rule", "join_rule",
    schema_tables=["payments", "invoices"], schema_columns=["payments.invoice_id", "invoices.invoice_id"],
    rules=[rule(
        "invoice join", "add",
        [("payments.invoice_id", "equals", "invoices.invoice_id")],
        scope="collection", tables=["payments", "invoices"], columns=["payments.invoice_id"]),
    ]))

# ---------------------------------------------------------------------------
# Merge + validate + write
# ---------------------------------------------------------------------------
AUG = {"ecommerce": EC, "customer_support": CS, "saas_subscription": SAAS}

def merge_into_seeds(aug: dict[str, list[dict]]):
    """Append augment records into each domain seed.jsonl, skipping existing IDs."""
    merged = {}
    for domain, recs in aug.items():
        seed = REPO / "rie_ml" / "domain-packs" / domain / "feedback" / "seed.jsonl"
        existing: dict[str, dict] = {}
        with seed.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    existing[r["feedback_id"]] = r
        added = 0
        for r in recs:
            if r["feedback_id"] not in existing:
                existing[r["feedback_id"]] = r
                added += 1
        # preserve original line order, appending new records at the end
        ordered = list(existing.values())
        with seed.open("w", encoding="utf-8") as f:
            for r in ordered:
                f.write(json.dumps(r) + "\n")
        merged[domain] = len(ordered)
        print(f"  {domain}: appended {added} new -> {len(ordered)} total")
    return merged


def validate_merged():
    """Full-file validation of each merged seed.jsonl via SeedValidator."""
    sys.path.insert(0, str(REPO / "rie_ml"))
    from dataset_generation.seed_validator import SeedValidator
    for domain in AUG:
        val = SeedValidator(Path(REPO / "rie_ml" / "domain-packs" / domain))
        result = val.validate_seed_file(REPO / "rie_ml" / "domain-packs" / domain / "feedback" / "seed.jsonl")
        print(f"  {domain}: is_valid={result['is_valid']} valid={result['valid_records']} "
              f"invalid={result['invalid_records']} dup_ids={result['duplicate_feedback_ids']}")
        if result["errors"]:
            for e in result["errors"][:20]:
                print("    ERR", e)


if __name__ == "__main__":
    out = Path(__file__).parent / "seed_augment.jsonl"
    with out.open("w") as f:
        for domain, recs in AUG.items():
            for r in recs:
                f.write(json.dumps(r) + "\n")
    print("drafted:", sum(len(v) for v in AUG.values()), "records ->", out)
    print("merging into seed.jsonl...")
    merge_into_seeds(AUG)
    print("validating merged seed files...")
    validate_merged()