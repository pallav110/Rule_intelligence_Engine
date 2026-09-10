# E-Commerce Domain Pack — Annotation Guide

**Version:** `ann_v0.2.0`  
**Domain:** `ecommerce`  
**Taxonomy:** [`taxonomy/labels.json`](../taxonomy/labels.json)

This guide defines how to annotate seed and evaluation feedback for the E-Commerce domain pack. Annotations support independent training and evaluation of **classification** and **structured rule extraction** tasks.

---

## 1. Annotation Principles

1. Use **snake_case** labels from `taxonomy/labels.json` only.
2. Never invent schema fields — all `field` values must exist in `schema/schema.json` or be explicitly marked invalid for validation-test examples.
3. Paraphrases of the same underlying rule share a **`rule_family_id`** and must stay in the same dataset split when splits are created.
4. Different rules extracted from the same feedback share **`feedback_id`** but use **different `rule_family_id`** values unless they represent equivalent logic.
5. The system must not guess missing business information — use `requires_clarification: true` when intent is incomplete.

---

## 2. Required Fields (Feedback Record)

| Field | Required | Description |
|-------|----------|-------------|
| `feedback_id` | Yes | Unique ID, format `EC_FB###` |
| `domain` | Yes | Always `ecommerce` for this pack |
| `domain_pack_version` | Yes | e.g. `ecommerce_v0.1.0` |
| `rule_family_id` | Yes | Groups paraphrases, format `RF###` |
| `feedback_text` | Yes | Raw user feedback (verbatim) |
| `feedback_type` | Yes | From taxonomy `feedback_types` |
| `rule_category` | Yes* | Primary category; `null` for non-rule/unclear |
| `is_actionable` | Yes | `true` if a rule can be extracted or inferred |
| `requires_clarification` | Yes | `true` if mandatory info is missing |
| `schema_context` | Recommended | Tables/columns available to the user |
| `rules` | Yes | Array of structured rules (empty if not actionable) |
| `annotation_version` | Yes | e.g. `ann_v0.2.0` |
| `source` | Yes | `manual`, `programmatic`, or `llm_assisted` |

\*For `issue_report`, `feature_request`, `question`, `general_feedback`, and `irrelevant_spam`, set `rule_category` to `null`.

---

## 3. Structured Rule Fields (each item in `rules[]`)

| Field | Required | Description |
|-------|----------|-------------|
| `business_term` | Yes* | Normalized term from glossary (snake_case) |
| `operation` | Yes* | From taxonomy `operations` |
| `conditions` | Yes* | Array of `{field, operator, value}` |
| `scope` | Optional | e.g. `global`, `region:north` |
| `time_window` | Optional | e.g. `calendar_month`, `90_days` |
| `threshold` | Optional | Numeric threshold when applicable |
| `affected_entities` | Recommended | `{tables: [], columns: []}` |

\*Omit or leave empty when `requires_clarification: true`.

### Condition object

```json
{
  "field": "orders.status",
  "operator": "equals",
  "value": "cancelled"
}
```

- **`field`:** Must use `table.column` notation.
- **`operator`:** From taxonomy `operators`.
- **`value`:** Literal, array (for `in`/`not_in`), or `null` for unary operators.

---

## 4. Feedback Type vs Rule Category

| feedback_type | When to use | rule_category |
|---------------|-------------|---------------|
| `business_rule` | User proposes or corrects a business rule | One of 6 rule categories |
| `issue_report` | Something is broken/wrong (data issue, bug) | `null` |
| `feature_request` | Request for new functionality | `null` |
| `question` | Clarification needed, ambiguous intent | `null` |
| `general_feedback` | General comment, no specific rule or issue | `null` |
| `irrelevant_spam` | Unrelated/spam content (pre-filter class) | `null` |

### Rule categories (e-commerce) — per §8.3.2 authoritative taxonomy

- `metric_definition` — how a metric is calculated (compositions over fields)
- `filter_rule` — include/exclude records (include/exclude operations)
- `mapping_rule` — map or replace raw values into canonical statuses (map/replace)
- `access_rule` — define permissions or access scope for roles/users (restrict)
- `join_rule` — define how tables relate or join conditions for derived metrics
- `data_quality_rule` — flag or validate records; validation/exclusion/flagging

---

## 5. Special Cases

### Multi-rule feedback
- One `feedback_id`, multiple objects in `rules[]`.
- Each rule gets its own `rule_family_id` unless paraphrasing the same logic.
- Set `rule_category` to the **primary** category; note secondary categories in review comments if needed.

### Clarification required
```json
{
  "is_actionable": false,
  "requires_clarification": true,
  "rules": []
}
```
Optionally add `missing_information` and `suggested_questions` in extended annotations (future schema).

### Invalid schema reference (validation test)
- Annotate the intended rule but set `schema_validation_expected: "fail"` in metadata extension, or use a deliberately invalid field like `orders.unknown_field` in conditions for pipeline testing.
- Do not map invalid fields to real columns.

### Hinglish / conversational English
- Preserve original `feedback_text` verbatim.
- Annotate using the same schema; normalized values in `rules[]` remain in English/snake_case.

---

## 6. Rule Family ID Grouping

**Same `rule_family_id`** — linguistic paraphrases of one rule:
- "Revenue should exclude cancelled orders."
- "Cancelled orders must not contribute to revenue."

**Different `rule_family_id`** — distinct rules in one message:
- "Exclude cancelled orders and exclude test transactions." → two rules, two family IDs.

When creating train/val/test splits later, all records with the same `rule_family_id` must remain in the **same split**.

---

## 7. NER Labels (Future Extraction Training)

For token-level BIO annotation (Phase 2+), use labels from `taxonomy/labels.json`:

| Label | Description | Example span |
|-------|-------------|--------------|
| BUSINESS_TERM | Metric or concept | Revenue |
| OPERATION | Action | exclude |
| FIELD | Schema field | orders.status |
| VALUE | Condition value | cancelled |
| SCOPE | Application scope | North region |
| TIME_WINDOW | Temporal constraint | current quarter |
| THRESHOLD | Numeric cutoff | 50000 |
| TABLE | Table name | orders |
| COLUMN | Column name | status |

Conditions are **not** stored as a single text span — the Rule Builder constructs `{field, operator, value}` from separate spans.

---

## 8. Review Process

1. Annotator labels record independently.
2. Second reviewer validates labels and schema references.
3. Disagreements escalated to senior review before inclusion in frozen evaluation set.
4. Run `python3 rie_ml/scripts/validate_domain_pack.py` before committing new examples.

---

## 9. Category Distribution (Seed Target)

For the initial 20–30 seed examples, aim for approximate coverage:

| Bucket | Count |
|--------|-------|
| metric_definition | 5 |
| filter_rule | 5 |
| mapping_rule | 2 |
| join_rule | 2 |
| access_rule | 2 |
| data_quality_rule | 2 |
| clarification / ambiguous (question) | 3 |
| issue_report | 2 |
| feature_request | 2 |
| multi_rule | 2 |
| hinglish | 2 |
| invalid_schema_ref | 1 |
| irrelevant_spam (pre-filter) | 1 |

---

## 10. Example (Complete Record)

```json
{
  "feedback_id": "EC_FB001",
  "domain": "ecommerce",
  "domain_pack_version": "ecommerce_v0.1.0",
  "rule_family_id": "RF001",
  "feedback_text": "Revenue should exclude cancelled orders and test transactions.",
  "feedback_type": "business_rule",
  "rule_category": "filter_rule",
  "is_actionable": true,
  "requires_clarification": false,
  "schema_context": {
    "available_tables": ["orders"],
    "available_columns": ["orders.status", "orders.is_test"]
  },
  "rules": [
    {
      "business_term": "revenue",
      "operation": "exclude",
      "conditions": [
        {"field": "orders.status", "operator": "equals", "value": "cancelled"}
      ],
      "scope": "global",
      "time_window": null,
      "threshold": null,
      "affected_entities": {
        "tables": ["orders"],
        "columns": ["orders.status"]
      }
    },
    {
      "business_term": "revenue",
      "operation": "exclude",
      "conditions": [
        {"field": "orders.is_test", "operator": "equals", "value": true}
      ],
      "scope": "global",
      "time_window": null,
      "threshold": null,
      "affected_entities": {
        "tables": ["orders"],
        "columns": ["orders.is_test"]
      }
    }
  ],
  "annotation_version": "ann_v0.2.0",
  "source": "manual"
}
```