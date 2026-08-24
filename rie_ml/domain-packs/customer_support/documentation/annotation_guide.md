# Customer Support Domain Pack — Annotation Guide

**Version:** `ann_v0.1.0`  
**Domain:** `customer_support`  
**Taxonomy:** [`taxonomy/labels.json`](../taxonomy/labels.json)

This guide defines how to annotate seed and evaluation feedback for the Customer Support domain pack. Annotations support independent training and evaluation of **classification** and **structured rule extraction** tasks.

---

## 1. Annotation Principles

1. Use **snake_case** labels from `taxonomy/labels.json` only.
2. Never invent schema fields - all `field` values must exist in `schema/schema.json` or be explicitly marked invalid for validation-test examples.
3. Paraphrases of the same underlying rule share a **`rule_family_id`** and must stay in the same dataset split when splits are created.
4. Different rules extracted from the same feedback share **`feedback_id`** but should use different `rule_family_id` values unless they are equivalent logic.
5. The system must not guess missing business information - use `requires_clarification: true` when intent is incomplete.

---

## 2. Required Fields (Feedback Record)

| Field | Required | Description |
|-------|----------|-------------|
| `feedback_id` | Yes | Unique ID, format `CS_FB###` |
| `domain` | Yes | Always `customer_support` for this pack |
| `domain_pack_version` | Yes | e.g. `customer_support_v0.1.0` |
| `rule_family_id` | Yes | Groups paraphrases, format `RF###` |
| `feedback_text` | Yes | Raw user feedback (verbatim) |
| `feedback_type` | Yes | From taxonomy `feedback_types` |
| `rule_category` | Yes* | Primary category; `null` for non-rule/unclear |
| `is_actionable` | Yes | `true` if a rule can be extracted or inferred |
| `requires_clarification` | Yes | `true` if mandatory info is missing |
| `schema_context` | Recommended | Tables/columns available to the user |
| `rules` | Yes | Array of structured rules (empty if not actionable) |
| `annotation_version` | Yes | e.g. `ann_v0.1.0` |
| `source` | Yes | `manual`, `programmatic`, or `llm_assisted` |

\*For `non_rule_feedback`, `unclear_feedback`, and `irrelevant_spam`, set `rule_category` to `null`.

---

## 3. Structured Rule Fields (each item in `rules[]`)

| Field | Required | Description |
|-------|----------|-------------|
| `business_term` | Yes* | Normalized term from glossary (snake_case) |
| `operation` | Yes* | From taxonomy `operations` |
| `conditions` | Yes* | Array of `{field, operator, value}` |
| `scope` | Optional | e.g. `global`, `department:billing` |
| `time_window` | Optional | e.g. `from_opened_at`, `24_hours` |
| `threshold` | Optional | Numeric threshold when applicable |
| `affected_entities` | Recommended | `{tables: [], columns: []}` |

\*Omit or leave empty when `requires_clarification: true`.

### Condition object

```json
{
  "field": "tickets.status",
  "operator": "equals",
  "value": "resolved"
}
```

- **`field`:** Must use `table.column` notation.
- **`operator`:** From taxonomy `operators`.
- **`value`:** Literal, array (for `in`/`not_in`), or `null` for unary operators.

---

## 4. Feedback Type vs Rule Category

| feedback_type | When to use | rule_category |
|---------------|-------------|---------------|
| `business_rule_correction` | User proposes or corrects a business rule | One of 11 rule categories |
| `non_rule_feedback` | Product/UI complaint, no data rule | `null` |
| `unclear_feedback` | Intent ambiguous, cannot extract rule | `null` |
| `irrelevant_spam` | Unrelated content | `null` |

### Rule categories (customer support)

- `metric_definition` - how a support metric is calculated
- `filter_rule` - include/exclude records
- `status_mapping` - equivalence of ticket states
- `time_rule` - response or resolution windows
- `join_correction` - how support tables should be joined
- `column_meaning` - clarify what a column represents
- `entity_definition` - define a business entity or queue
- `data_quality_issue` - data integrity problems
- `calculation_correction` - fix aggregation logic
- `expected_result_correction` - user states expected result or count
- `access_scope_rule` - who can see what data

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
Optionally add `missing_information` and `suggested_questions` in extended annotations.

### Invalid schema reference (validation test)
- Annotate the intended rule but set `schema_validation_expected: "fail"` in metadata extension, or use a deliberately invalid field like `tickets.unknown_column` in conditions for pipeline testing.
- Do not map invalid fields to real columns.

### Hinglish / conversational English
- Preserve original `feedback_text` verbatim.
- Annotate using the same schema; normalized values in `rules[]` remain in English/snake_case.

---

## 6. Rule Family ID Grouping

**Same `rule_family_id`** - linguistic paraphrases of one rule:
- "Exclude internal tickets from backlog counts."
- "Internal tickets should not count in the support backlog."

**Different `rule_family_id`** - distinct rules in one message:
- "Exclude internal tickets and restrict agent access to department tickets." -> two rules, two families.

When creating train/val/test splits later, all records with the same `rule_family_id` must remain in the **same split**.

---

## 7. NER Labels (Future Extraction Training)

For token-level BIO annotation (Phase 2+), use labels from `taxonomy/labels.json`:

| Label | Description | Example span |
|-------|-------------|--------------|
| BUSINESS_TERM | Metric or concept | CSAT |
| OPERATION | Action | exclude |
| FIELD | Schema field | tickets.status |
| VALUE | Condition value | resolved |
| SCOPE | Application scope | department:billing |
| TIME_WINDOW | Temporal constraint | 24 hours |
| THRESHOLD | Numeric cutoff | 30 |
| TABLE | Table name | tickets |
| COLUMN | Column name | status |

Conditions are **not** stored as a single text span - the Rule Builder constructs `{field, operator, value}` from separate spans.

---

## 8. Review Process

1. Annotator labels record independently.
2. Second reviewer validates labels and schema references.
3. Disagreements escalated to senior review before inclusion in frozen evaluation set.
4. Run `python3 rie_ml/scripts/validate_domain_pack.py` before committing new examples.

---

## 9. Seed Target Distribution

For the initial 20-30 seed examples, aim for approximate coverage:

| Bucket | Count |
|--------|-------|
| metric_definition | 4 |
| filter_rule | 5 |
| status_mapping | 2 |
| time_rule | 2 |
| join_correction | 2 |
| access_scope_rule | 2 |
| data_quality_issue | 2 |
| clarification / ambiguous | 3 |
| non_rule_feedback | 2 |
| multi_rule | 2 |
| hinglish | 2 |
| invalid_schema_ref | 1 |

---

## 10. Example (Complete Record)

```json
{
  "feedback_id": "CS_FB001",
  "domain": "customer_support",
  "domain_pack_version": "customer_support_v0.1.0",
  "rule_family_id": "RF001",
  "feedback_text": "Internal sandbox tickets should be excluded from backlog counts.",
  "feedback_type": "business_rule_correction",
  "rule_category": "filter_rule",
  "is_actionable": true,
  "requires_clarification": false,
  "schema_context": {
    "available_tables": ["tickets"],
    "available_columns": ["tickets.is_internal", "tickets.status"]
  },
  "rules": [
    {
      "business_term": "ticket_backlog",
      "operation": "exclude",
      "conditions": [
        {"field": "tickets.is_internal", "operator": "equals", "value": true}
      ],
      "scope": "global",
      "time_window": null,
      "threshold": null,
      "affected_entities": {
        "tables": ["tickets"],
        "columns": ["tickets.is_internal", "tickets.status"]
      }
    }
  ],
  "annotation_version": "ann_v0.1.0",
  "source": "manual"
}
```
