# RIE ML Module — Phase 1 Foundation

**Project:** Rule Intelligence Engine (RIE)  
**Component:** ML / Data / Rule Intelligence  
**Owner:** Person 2  
**Phase:** 1 (Foundation & Dataset Preparation)  
**Status:** ✅ E-Commerce Domain Pack Complete

---

## Project Structure

```
rie-ml/
├── domain-packs/                   # Synthetic business domain environments
│   └── ecommerce/                  # Phase 1: E-Commerce
│       ├── README.md               # Domain pack handoff documentation
│       ├── domain_config.json      # Pack metadata and references
│       ├── schema/
│       │   ├── schema.json         # 7 entity schema with column definitions
│       │   └── relationships.json  # Foreign key graph and join paths
│       ├── rules/
│       │   ├── active_rules.json   # 10+ approved business rules
│       │   └── conflicting_rules.json  # 4–6 conflicting rules (test DCD)
│       ├── feedback/
│       │   └── seed.jsonl          # 30 manually reviewed feedback examples
│       ├── documentation/
│       │   ├── business_glossary.md    # Business terms → schema mapping
│       │   └── annotation_guide.md     # Annotation SOP and taxonomy
│       └── taxonomy/
│           └── labels.json        # Frozen snake_case enums
├── data/                            # Datasets (per V4 §4)
│   ├── raw/
│   │   └── feedback_seed.jsonl    # Legacy raw input (deprecated, see note below)
│   ├── processed/                  # Generated train/val/test datasets (future)
│   └── splits/                      # Dataset split metadata (future)
├── scripts/
│   └── validate_domain_pack.py      # Validate schema refs + taxonomy + IDs
├── src/                             # ML pipeline modules (Phase 2+)
│   ├── calibration/
│   ├── classification/
│   ├── common/
│   ├── duplicate_conflict/
│   └── extraction/
├── models/                          # Model artifacts (Phase 2+)
│   ├── classification_model_v0/
│   ├── extraction_model_v0/
│   └── baseline/
├── evaluation/                      # Evaluation results (Phase 2+)
├── tests/                           # Unit tests
├── requirements.txt                 # Python dependencies
└── README.md                        # This file
```

## Phase 1 Objectives (COMPLETE) ✅

- [x] **FastAPI project setup** — Person 1 owns this
- [x] **PostgreSQL database setup** — Person 1 owns this
- [x] **Docker environment configuration** — Person 1 owns this
- [x] **Domain Pack design** — ✅ E-Commerce domain pack complete
- [x] **Synthetic dataset preparation** — ✅ 30 seed examples with balanced coverage
- [x] **Annotation guideline definition** — ✅ `annotation_guide.md` complete

## Person 2 Deliverables (Phase 1)

### 1. E-Commerce Domain Pack ✅

**Location:** `domain-packs/ecommerce/`

**Includes:**
- 7-entity e-commerce schema (customers, orders, order_items, products, payments, refunds, regions)
- 8+ FK relationships with join paths
- 10+ active business rules (metric, filter, status, time, join, access, entity definitions)
- 4+ conflicting rules (for duplicate/conflict detection testing)
- 30 manually reviewed seed feedback examples
- 15+ business glossary terms mapped to schema
- Complete annotation guidelines (SOP for labeling)
- Frozen taxonomy with snake_case labels

**Acceptance:** See [domain-packs/ecommerce/README.md](domain-packs/ecommerce/README.md)

### 2. Synthetic Dataset (Seed Phase) ✅

**Location:** `domain-packs/ecommerce/feedback/seed.jsonl`

**Stats:**
- 30 manually reviewed examples
- Covers all 14 rule categories
- Includes Hinglish and conversational phrasing
- Balanced mix of actionable, clarification, and non-rule feedback
- 2 examples with invalid schema references (for validation testing)
- Examples grouped by `rule_family_id` to preserve paraphrase integrity

**Schema Validation:**
- All field references validated with `scripts/validate_domain_pack.py`
- Invalid example (`EC_FB028`) marked with `schema_validation_expected: "fail"` for testing

### 3. Taxonomy Standardization ✅

**Location:** `domain-packs/ecommerce/taxonomy/labels.json`

**Enforces:**
- Snake_case feedback types: `business_rule_correction`, `unclear_feedback`, etc.
- 14 rule categories matching OVERVIEW.txt
- Normalized operations: `exclude`, `include`, `restrict`, `map`, `replace`, ...
- Standard operators: `equals`, `greater_than`, `in`, `is_not_null`, ...
- Duplicate/conflict relationship types

**Migration:** All existing feedback must convert to this taxonomy before use.

### 4. Validation Script ✅

**Location:** `scripts/validate_domain_pack.py`

**Validates:**
- Schema field existence (table.column notation)
- Taxonomy label membership
- Unique feedback_id, rule_id, rule_family_id
- Required fields in feedback records
- Condition field references
- Special handling for invalid examples (`schema_validation_expected=fail`)

**Usage:**
```bash
python scripts/validate_domain_pack.py
# Output: ✅ ecommerce domain pack is valid
```

## Dependencies

**Python 3.9+**

```txt
jsonschema>=4.21.0
pyyaml>=6.0
```

Install:
```bash
pip install -r requirements.txt
```

## Data Governance

### Datasets Used
- ✅ Synthetic (manually created)
- ✅ Manually reviewed (100% QA before inclusion)
- ✅ No production data
- ✅ Reproducible
- ✅ Version-controlled

### Dataset Versioning
Every dataset references:
- `domain_pack_version`: e.g. `ecommerce_v0.1.0`
- `annotation_version`: e.g. `ann_v0.1.0`
- `source`: `manual`, `programmatic`, or `llm_assisted`

Updates create new versions; old versions remain for reproducibility.

### Future Incorporation
If production feedback is included in Phase 2+:
1. **Anonymize** all sensitive data (customer IDs, emails, etc.)
2. **Manual review** by data governance team
3. **Version update** in domain pack
4. **Approval** before inclusion in any training/eval dataset

## Legacy Data Migration

**Old file:** `rie-ml/data/raw/feedback_seed.jsonl`

**Status:** ⚠️ **Deprecated**

The original 5 examples had incorrect labels:
- ❌ `feedback_type: "Filter Rule"` → ✅ `feedback_type: "business_rule_correction"` + `rule_category: "filter_rule"`
- ❌ `domain: "finance"` → ✅ `domain: "ecommerce"`
- ❌ `operation: "EXCLUDE"` → ✅ `operation: "exclude"` (snake_case)
- ❌ `clarification_required` → ✅ `requires_clarification`

**New source:** All seed data is now in `domain-packs/ecommerce/feedback/seed.jsonl`

To deprecate old file:
```bash
# Option 1: Move to archive
mv rie-ml/data/raw/feedback_seed.jsonl rie-ml/data/raw/feedback_seed.DEPRECATED.jsonl

# Option 2: Add deprecation note in rie-ml/README.md
```

## Next Phase (Phase 2)

### Person 2 Tasks
1. **LLM-Assisted Data Generation**
   - Use seed examples to generate ~950 more feedback samples
   - Maintain rule family grouping
   - Create 3 splits: train (70%), validation (15%), evaluation (15%)
   - Manual review of all generated examples
   - Output: `rie-ml/data/processed/{classification,extraction}_{train,val,eval}_*.jsonl`

2. **ML Model Development**
   - Implement classification baseline (deterministic rules)
   - Implement rule extraction baseline
   - Train DistilBERT classification model
   - Train DistilBERT extraction model
   - Compare against baseline using frozen eval dataset
   - Output: `rie-ml/models/{classification,extraction}_model_v0/`

3. **Dataset Splits & Versioning**
   - Document split strategy
   - Ensure paraphrase grouping is preserved across splits
   - Create `rie-ml/data/splits/manifest_v0.json`

### Person 1 Tasks
1. **FastAPI Backend**
   - Implement DomainPackLoader
   - Create `/v1/domain-pack/{pack_id}` endpoint
   - Create `/v1/taxonomy` endpoint
   - Create `/v1/feedback/{feedback_id}/classify` endpoint
   - Create `/v1/feedback/{feedback_id}/extract-rules` endpoint

2. **PostgreSQL Schema**
   - Create `domain_packs` table
   - Create `feedback` table
   - Create `rules` table (approved)
   - Create `rule_suggestions` table (ML output)

3. **Docker & CI/CD**
   - Build Docker image for development environment
   - Set up testing pipeline
   - Set up deployment pipeline

## Running Validation

Before committing any changes:

```bash
# From project root
python rie-ml/scripts/validate_domain_pack.py

# Expected output:
# ✅ Loading ecommerce domain pack from rie-ml/domain-packs/ecommerce
# ✅ Validating schema.json
# ✅ Validating taxonomy.json
# ✅ Validating active_rules.json (10 rules)
# ✅ Validating conflicting_rules.json (4 rules)
# ✅ Validating seed.jsonl (30 examples)
# ✅ ecommerce domain pack is valid
```

## Common Workflows

### Add a new feedback example
1. Create a record in `domain-packs/ecommerce/feedback/seed.jsonl`
2. Use existing `rule_family_id` if it's a paraphrase, or create new one
3. Ensure all schema field references exist
4. Run validation: `python scripts/validate_domain_pack.py`

### Add a new active rule
1. Add to `domain-packs/ecommerce/rules/active_rules.json`
2. Increment rule ID (e.g. EC_R011 → EC_R012)
3. Update business glossary if new term
4. Consider adding feedback example that uses this rule
5. Run validation

### Update schema
1. Edit `domain-packs/ecommerce/schema/schema.json`
2. Add/remove columns or tables
3. Update `schema/relationships.json` if FKs change
4. Update any rules that reference affected columns
5. Update glossary terms
6. Run validation to find broken references

## Quick Reference

| Artifact | Location | Audience | Purpose |
|----------|----------|----------|---------|
| Schema | `schema/schema.json` | ML, Backend | Defines valid table.column references |
| Taxonomy | `taxonomy/labels.json` | ML, Backend | Enum constraints for labels |
| Active Rules | `rules/active_rules.json` | ML, Backend | Ground truth for duplicate/conflict detection |
| Conflicting Rules | `rules/conflicting_rules.json` | ML | Test cases for conflict detection |
| Seed Feedback | `feedback/seed.jsonl` | ML | Training seed for data generation |
| Glossary | `documentation/business_glossary.md` | ML, Data Analyst | Business term definitions |
| Annotation Guide | `documentation/annotation_guide.md` | ML (data annotators) | SOP for feedback labeling |
| Domain Config | `domain_config.json` | Backend | Pack metadata and file refs |
| Relationships | `schema/relationships.json` | ML, Backend | Join paths and FK cardinality |

## Troubleshooting

### Validation fails: "unknown schema field 'X.Y'"
- Check `schema/schema.json` for typos in table or column names
- Ensure all rules and feedback reference fields that exist
- Use `scripts/validate_domain_pack.py` to find all occurrences

### Validation fails: "invalid operation 'foo'"
- Check `taxonomy/labels.json` for allowed operations
- Update feedback or rules to use standardized operations
- If new operation is needed, add to taxonomy first

### Paraphrases split across splits
- Ensure same `rule_family_id` is used for paraphrases
- When creating train/val/test splits, group by `rule_family_id` first
- Check split report after generation

---

**Contact:** Person 2 (ML / Data / Rule Intelligence)  
**Last Updated:** 2026-08-10
