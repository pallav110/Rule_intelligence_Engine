# E-Commerce Domain Pack — Person 2 Handoff

**Version:** `ecommerce_v0.1.0`  
**Created:** 2026-08-10  
**Owner:** Person 2 (ML / Data / Rule Intelligence)  
**Annotation Version:** `ann_v0.1.0`

---

## Overview

This domain pack contains a complete synthetic e-commerce business environment for Phase 1 of the Rule Intelligence Engine (RIE). It is designed to be:

- **Domain-independent**: Portable structure serves as a template for other business domains
- **Schema-validated**: All feedback field references validated against `schema/schema.json`
- **ML-ready**: Supports independent training of classification, extraction, and duplicate/conflict detection models
- **Reproducible**: All examples are manually reviewed and version-controlled

## Directory Structure

```
rie-ml/domain-packs/ecommerce/
├── domain_config.json              # Pack metadata and version
├── schema/
│   ├── schema.json                 # 7-entity database schema
│   └── relationships.json          # Foreign key graph + join paths
├── rules/
│   ├── active_rules.json           # 10+ approved business rules
│   └── conflicting_rules.json      # 4–6 deliberately conflicting rules
├── feedback/
│   └── seed.jsonl                  # 30 manually reviewed examples
├── documentation/
│   ├── business_glossary.md        # 15+ business terms → schema mapping
│   └── annotation_guide.md         # Annotation SOP and field definitions
├── taxonomy/
│   └── labels.json                 # Frozen snake_case enum lists
└── README.md                       # This file
```

## Contents Checklist

| Artifact | Type | Count | Status | Notes |
|----------|------|-------|--------|-------|
| **Schema** | JSON | 7 tables | ✅ Complete | customers, orders, order_items, products, payments, refunds, regions |
| **Relationships** | JSON | 8 FKs | ✅ Complete | Cardinality + join paths |
| **Active Rules** | JSON | 10 rules | ✅ Complete | Covers metric, filter, status, time, join, access, entity rules |
| **Conflicting Rules** | JSON | 4 rules | ✅ Complete | Direct conflicts with active set |
| **Seed Feedback** | JSONL | 30 examples | ✅ Complete | Balanced across categories, includes Hinglish, ambiguous, clarification cases |
| **Glossary** | Markdown | 15+ terms | ✅ Complete | Revenue, orders, customers, active metrics |
| **Annotation Guide** | Markdown | Complete | ✅ Complete | Field definitions, BIO NER reference, paraphrase grouping |
| **Taxonomy** | JSON | 4 enums | ✅ Complete | feedback_types, rule_categories, operations, operators |

## Entities & Schema

The e-commerce schema includes **7 core entities**:

| Entity | Purpose | Key Filter Columns |
|--------|---------|-------------------|
| `customers` | Buyer profiles | `is_internal`, `last_purchase_at` |
| `orders` | Transactions | `status`, `is_test`, `order_date`, `discount_pct` |
| `order_items` | Line items | `product_id`, `quantity`, `unit_price` |
| `products` | Catalog | `name`, `category`, `is_active` |
| `payments` | Payment records | `status`, `amount`, `transaction_id` |
| `refunds` | Refund transactions | `status`, `amount`, `payment_id` |
| `regions` | Geographic scope | `name`, `country_code` |

**All feedback field references use `table.column` notation and are validated by `scripts/validate_domain_pack.py`.**

## Seed Feedback Dataset

**30 annotated examples covering:**

- **Metric definition** (5 ex): revenue, gross sales, net revenue
- **Filter rule** (5 ex): exclude cancelled/test/internal
- **Status mapping** (2 ex): order status equivalences
- **Join correction** (2 ex): payment join fixes
- **Access scope** (2 ex): region-restricted access
- **Data quality** (2 ex): duplicate customer IDs
- **Clarification** (3 ex): missing metric or threshold
- **Non-rule feedback** (2 ex): dashboard performance complaint
- **Multi-rule** (2 ex): 2+ rules in one message
- **Hinglish** (2 ex): conversational/Hinglish phrasing
- **Invalid schema ref** (1 ex): references non-existent column (validation test)

Each record includes:
- `feedback_text`: Raw user input (verbatim, diverse writing styles)
- `rule_category`: Classification label
- `rules[]`: Extracted structured rules (empty if clarification needed)
- `schema_context`: Available tables/columns for this example
- `rule_family_id`: Groups paraphrases for split integrity
- `annotation_version`: `ann_v0.1.0`

**Location:** `feedback/seed.jsonl`

## Active Rules

**10 canonical approved rules** from `rules/active_rules.json`:

| Rule ID | Category | Business Term | Operation | Scope |
|---------|----------|---------------|-----------|-------|
| EC_R001 | metric_definition | revenue | exclude | cancelled orders |
| EC_R002 | filter_rule | revenue | exclude | test transactions |
| EC_R003 | metric_definition | net_revenue | subtract | successful refunds |
| EC_R004 | metric_definition | gross_sales | include | successful payments |
| EC_R005 | filter_rule | free_shipping | include | orders > ₹999 |
| EC_R006 | access_scope_rule | regional_orders | restrict | North region |
| EC_R007 | status_mapping | completed_order | map | shipped/delivered → completed |
| EC_R008 | join_correction | payment_reconciliation | replace | use transaction_id |
| EC_R009 | entity_definition | active_customer | include | 90-day purchase window |
| EC_R010 | filter_rule | customer_count | exclude | internal users |

## Conflicting Rules

**4 deliberately conflicting rules** from `rules/conflicting_rules.json`:

| Rule ID | Conflicts With | Business Term | Conflict Type |
|---------|----------------|---------------|---------------|
| EC_CR001 | EC_R003 | revenue | Include refunds (vs. subtract) |
| EC_CR002 | EC_R001 | revenue | Include cancelled (vs. exclude) |
| EC_CR003 | EC_R005 | free_shipping | Threshold ₹500 (vs. ₹999) |
| EC_CR004 | EC_R006 | regional_orders | No region filter (vs. North only) |

**These test the conflict detection module and ensure the system correctly identifies rule opposition.**

## Taxonomy (Frozen)

All labels are defined in `taxonomy/labels.json` and use **snake_case** as the authoritative convention (per OVERVIEW.txt §3):

**Feedback Types:**
- `business_rule_correction`
- `non_rule_feedback`
- `unclear_feedback`
- `irrelevant_spam`

**Rule Categories:**
- metric_definition, filter_rule, status_mapping, time_rule, join_correction
- column_meaning, entity_definition, data_quality_issue, calculation_correction
- expected_result_correction, access_scope_rule, threshold_rule, aggregation_rule, computation_rule

**Operations:**
- exclude, include, restrict, map, replace, add, subtract, multiply, divide, aggregate, filter, transform

**Operators:**
- equals, not_equals, greater_than, less_than, greater_than_or_equals, less_than_or_equals
- in, not_in, contains, not_contains, is_null, is_not_null, regex_match

## Validation

**Run the domain pack validator:**

```bash
python rie-ml/scripts/validate_domain_pack.py
```

Checks:
- ✅ Schema field references exist in `schema/schema.json`
- ✅ Taxonomy labels match frozen enums
- ✅ Unique `rule_id`, `feedback_id`, `rule_family_id`
- ✅ No duplicate `feedback_id` in seed dataset
- ✅ Conditions reference valid schema fields
- ✅ Feedback record structure (required fields, type consistency)
- ✅ Special case: `schema_validation_expected=fail` for intentionally invalid examples

## Person 1 Integration Handoff

### Expected Backend Loader Interface

Person 1 (Backend / System Architecture) should implement a `DomainPackLoader` that reads this domain pack structure:

```python
# Pseudo-code
loader = DomainPackLoader("rie-ml/domain-packs/ecommerce")
pack = loader.load()

# Expected attributes:
pack.schema              # dict of tables, columns, types
pack.relationships      # FK graph
pack.active_rules       # list of canonical rules
pack.conflicting_rules  # list of conflicting rules
pack.seed_feedback      # JSONL feedback records
pack.glossary           # business term definitions
pack.taxonomy           # frozen enum lists
```

### API Contract

When Person 1 builds the FastAPI routes, these values should be used:

**`GET /v1/taxonomy`** → contents of `taxonomy/labels.json`

**`GET /v1/domain-pack/ecommerce/schema`** → contents of `schema/schema.json`

**`POST /v1/feedback/classify`** request → should include:
```json
{
  "schema_context": {
    "available_tables": [...],
    "available_columns": [...]
  }
}
```

These come from feedback records' `schema_context` field.

**Rules validation** → all `rules[].conditions[].field` must exist in `schema/schema.json`

### Database Model (PostgreSQL)

Person 1 should create a `DomainPack` entity (per V4 §6.8):

| Column | Type | Source |
|--------|------|--------|
| `pack_id` | string | `domain_config.domain_pack_id` |
| `version` | string | `domain_config.version` |
| `schema_json` | text | contents of `schema/schema.json` |
| `relationships_json` | text | contents of `schema/relationships.json` |
| `taxonomy_json` | text | contents of `taxonomy/labels.json` |
| `active_rules_json` | text | contents of `rules/active_rules.json` |
| `conflicting_rules_json` | text | contents of `rules/conflicting_rules.json` |
| `glossary_md` | text | contents of `documentation/business_glossary.md` |
| `created_at` | timestamp | pack creation date |

Then expose via `GET /v1/domain-pack/{pack_id}` returning all above fields.

### Migration Path

**Data flow for future ML pipeline:**

```
feedback/seed.jsonl
  ↓
  (validate with scripts/validate_domain_pack.py)
  ↓
  (person 2: generate ~950 more examples with LLM-assisted pipeline)
  ↓
  rie-ml/data/processed/
    ├── classification_train_*.jsonl
    ├── classification_val_*.jsonl
    ├── extraction_train_*.jsonl
    ├── extraction_eval_*.jsonl (manually reviewed, frozen)
    └── splits_report.json (paraphrase split integrity)
  ↓
  (person 2: train DistilBERT classification + extraction models)
  ↓
  rie-ml/models/
    ├── classification_model_v1/
    ├── extraction_model_v1/
    └── model_metadata.json
```

**Person 1 responsibility:** Ensure domain pack files are loaded into PostgreSQL once, then referenced by model training pipeline.

## Quick Start for Person 2

### Validate the pack:
```bash
cd rie-ml
python scripts/validate_domain_pack.py
# Expected: "✅ ecommerce domain pack is valid"
```

### Use seed feedback for next phase:
```bash
# Read seed examples
jq '.rules | length' feedback/seed.jsonl  # Count total rules extracted
jq '.feedback_type' feedback/seed.jsonl | sort | uniq -c  # Distribution
```

### Extend the pack:
1. Add more feedback examples to `feedback/seed.jsonl` (keep paraphrase grouping via `rule_family_id`)
2. Update `documentation/business_glossary.md` if new business terms emerge
3. Add new rules to `rules/active_rules.json` or `conflicting_rules.json`
4. Re-run validation before committing

## Acceptance Criteria Met ✅

- [x] E-Commerce domain pack directory exists with all 8 artifact groups
- [x] Schema covers all 7 entities with realistic columns
- [x] 10+ active rules + 4+ conflicting rules defined
- [x] Glossary maps 15+ business terms to schema columns
- [x] Annotation guide is complete enough for second reviewer
- [x] 30 seed feedback examples pass validation script
- [x] All labels use OVERVIEW snake_case taxonomy
- [x] Person 1 handoff note documents pack location and loading contract

---

**Next Steps (Phase 1 → Phase 2):**
1. Person 1: Implement DomainPackLoader + FastAPI routes + PostgreSQL schema
2. Person 2: Run LLM-assisted data generation pipeline to create ~950 examples
3. Person 1 + Person 2: Review generated examples and build balanced train/val/test splits
4. Person 2: Train classification and extraction models
5. Evaluate against frozen evaluation dataset using deterministic baseline as comparison
