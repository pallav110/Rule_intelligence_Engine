# SaaS Subscription Domain — Annotation Guide

**Version:** `ann_v0.2.0`  
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

---

## Feedback Type vs Rule Category (per §8.3.2 authoritative taxonomy)

| feedback_type | When to use | rule_category |
|---------------|-------------|---------------|
| `business_rule` | User proposes or corrects a business rule | One of 6 rule categories |
| `issue_report` | Something is broken/wrong (data issue, bug) | `null` |
| `feature_request` | Request for new functionality | `null` |
| `question` | Clarification needed, ambiguous intent | `null` |
| `general_feedback` | General comment, no specific rule or issue | `null` |
| `irrelevant_spam` | Unrelated/spam content (pre-filter class) | `null` |

### Rule categories (SaaS subscription) — per §8.3.2

- `metric_definition` — how a metric is calculated (compositions over fields)
- `filter_rule` — include/exclude records (include/exclude operations)
- `mapping_rule` — map or replace raw values into canonical statuses (map/replace)
- `access_rule` — define permissions or access scope for roles/users (restrict)
- `join_rule` — define how tables relate or join conditions for derived metrics
- `data_quality_rule` — flag or validate records; validation/exclusion/flagging