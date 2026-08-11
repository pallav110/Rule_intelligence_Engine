# SaaS Subscription Domain — Annotation Guide

**Version:** `ann_v0.1.0`  
**Domain:** `saas_subscription`  
**Taxonomy:** [`taxonomy/labels.json`](../taxonomy/labels.json)

Follow the pack-wide annotation rules (snake_case, taxonomy labels, table.column fields) as in other domain packs.

Key points specific to SaaS:
- Use `subscriptions`, `invoices`, `payments`, `subscription_plans`, `users`, and `organizations` table.column names exactly as in `schema/schema.json`.
- `rule_family_id` values start with `RF` and are shared across paraphrases.
- For clarification examples set `requires_clarification: true`, `is_actionable: false`, and `rules: []`.
- For validation-test examples reference a nonexistent field (e.g. `subscriptions.nonexistent_field`) and set `schema_validation_expected: "fail"`.

Structured rule snippets must use `field` values in `table.column` format and operators from `taxonomy/labels.json`.

Example structured rule for a failed payment:

```json
{
  "business_term": "failed_payment",
  "operation": "include",
  "conditions": [{"field": "payments.status", "operator": "equals", "value": "failed"}],
  "scope": "global"
}
```

When a feedback message contains multiple distinct rules, include multiple objects in `rules[]` and use multiple `rule_family_id` values.

Preserve `feedback_text` verbatim, including Hinglish or conversational forms.
