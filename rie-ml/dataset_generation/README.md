# RIE Dataset Generation Pipeline

Synthetic feedback dataset generation pipeline for the Rule Intelligence Engine (RIE). This pipeline generates validated synthetic training data from manually annotated seed examples and domain pack specifications.

## Overview

The pipeline takes:
- **Seed data** (`seed.jsonl`) - Manually annotated reference examples
- **Domain Pack** - Schema, taxonomy, and business rules

And produces:
- **Synthetic feedback datasets** for classification, extraction, clarification, duplicate detection, and conflict detection
- **Train/val/test splits** with rule-family-aware splitting to prevent data leakage
- **Validation reports** with detailed error/warning information

## Features

- **Seed Validation**: Validates seed data against domain pack schema and taxonomy before generation
- **Multiple Generation Types**:
  - Paraphrases (linguistically different, semantically equivalent)
  - Conversational feedback (natural business language)
  - Hinglish (Hindi-English mixed examples)
  - Multi-rule feedback (multiple independent rules in one message)
  - Ambiguous/clarification cases (requires human clarification)
  - Conflict cases (contradictory business rules)
  - Non-rule feedback (UI/UX complaints)
  - Spam/irrelevant examples
  - Invalid schema references (for validation testing)
- **Post-Generation Validation**: Automatic validation of all generated records
- **Rule-Family-Aware Splitting**: Prevents data leakage by keeping paraphrases together
- **Reproducibility**: Fixed random seeds and configuration files
- **Traceability**: Every generated record tracks its source seed and generation method

## Installation

No additional dependencies beyond Python 3.8+. The pipeline uses only standard library modules.

```bash
cd rie-ml
```

## Usage

### Basic Usage

Run the pipeline with default configuration:

```bash
python3 scripts/generate_dataset.py
```

Or using the direct script:

```bash
python3 rie-ml/dataset_generation/run_pipeline.py
```

### Advanced Usage

Specify custom configuration:

```bash
python3 scripts/generate_dataset.py \
  --domain-pack /path/to/domain-pack \
  --seed /path/to/seed.jsonl \
  --output /path/to/output \
  --random-seed 42 \
  --strict
```

### Using Configuration File

Create a configuration file:

```python
from dataset_generation.config import GenerationConfig
from pathlib import Path

config = GenerationConfig(
    domain_pack_path=Path("domain-packs/ecommerce"),
    seed_path=Path("domain-packs/ecommerce/feedback/seed.jsonl"),
    output_dir=Path("dataset_generation/output"),
    random_seed=42,
    target_train_size=600,
    target_val_size=150,
    target_test_size=200,
)

config.save(Path("my_config.json"))
```

Then run with the config:

```bash
python3 scripts/generate_dataset.py --config my_config.json
```

## Configuration

The `GenerationConfig` class controls all aspects of generation:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `domain_pack_id` | `"ecommerce"` | Domain pack identifier |
| `domain_pack_version` | `"ecommerce_v0.1.0"` | Domain pack version |
| `domain_pack_path` | Path to ecommerce pack | Path to domain pack directory |
| `seed_path` | Path to seed.jsonl | Path to seed data file |
| `output_dir` | `dataset_generation/output` | Output directory |
| `dataset_version` | `"dataset_v0.1.0"` | Dataset version identifier |
| `annotation_version` | `"ann_v0.1.0"` | Annotation schema version |
| `random_seed` | `42` | Random seed for reproducibility |
| `target_train_size` | `600` | Target training set size |
| `target_val_size` | `150` | Target validation set size |
| `target_test_size` | `200` | Target test set size |
| `target_duplicate_pairs` | `150` | Target duplicate pairs |
| `target_conflict_pairs` | `150` | Target conflict pairs |
| `target_ambiguous` | `100` | Target ambiguous examples |  
| `paraphrase_multiplier` | `3` | Paraphrases per seed |
| `conversational_multiplier` | `2` | Conversational versions per seed |
| `hinglish_multiplier` | `1` | Hinglish versions per seed |
| `multi_rule_multiplier` | `1` | Multi-rule combinations |
| `strict_validation` | `True` | Fail on validation errors |
| `allow_invalid_schema_refs` | `False` | Allow invalid schema fields |

## Output Files

The pipeline generates the following files in the output directory:

### Core Datasets

- **`candidates.jsonl`** - All generated records before validation
- **`approved.jsonl`** - Records that passed validation
- **`rejected.jsonl`** - Records that failed validation (with rejection reasons)

### Dataset Splits

- **`train.jsonl`** - Training set (seed + generated)
- **`val.jsonl`** - Validation set
- **`test.jsonl`** - Frozen test set

### Task-Specific Datasets

- **`classification.jsonl`** - For feedback classification task
  - Fields: `feedback_id`, `feedback_text`, `feedback_type`, `rule_category`, `is_actionable`, `requires_clarification`
  
- **`extraction.jsonl`** - For structured rule extraction task
  - Fields: `feedback_id`, `feedback_text`, `rules`, `rule_family_id
- **`clarification.jsonl`** - For clarification detection task
  - Fields: `feedback_id`, `feedback_text`, `requires_clarification`, `reason`

### Relationship Datasets

- **`duplicate_pairs.jsonl`** - Pairs of semantically equivalent feedback
- **`conflict_pairs.jsonl`** - Pairs of contradictory business rules

### Reports

- **`config.json`** - Configuration used for generation
- **`validation_report.json`** - Detailed validation results (JSON)
- **`report.md`** - Human-readable generation report (Markdown)

## Pipeline Stages

### 1. Seed Validation

Validates seed data against:
- Domain pack schema (table/column existence)
- Taxonomy labels (feedback types, rule categories, operations, operators)
- Required field presence
- Annotation consistency (is_actionable, requires_clarification, rules)
- Schema context consistency

Invalid seed records are reported but do not stop generation (unless `strict_validation=True`).

### 2. Generation

Generates synthetic data using multiple generators:

- **ParaphraseGenerator**: Creates linguistically different versions preserving semantics
- **ConversationalGenerator**: Converts to natural business language
- **HinglishGenerator**: Creates Hindi-English mixed examples
- **MultiRuleGenerator**: Combines multiple rules from different seeds
- **AmbiguousGenerator**: Creates feedback requiring clarification
- **ConflictGenerator**: Creates contradictory rule pairs
- **NonRuleGenerator**: Creates UI/UX complaints
- **SpamGenerator**: Creates irrelevant/spam examples
- **InvalidSchemaGenerator**: Creates invalid schema references for testing

All generated records include:
- `source_seed_id` - Traceability to originating seed
- `rule_family_id` - Groups semantically equivalent rules
- `generation_method` - Type of generation used
- `dataset_version` - Dataset version identifier
- `annotation_version` - Annotation schema version

### 3. Post-Generation Validation

Validates all generated records against:
- Schema validity (field references)
- Domain validity (taxonomy labels)
- Rule structure consistency
- Required field presence
- Annotation consistency
- Duplicate feedback IDs
- Rule-family consistency

Invalid records go to `rejected.jsonl` with rejection reasons.

### 4. Dataset Splitting

Splits data into train/val/test with:
- **Rule-family-aware splitting**: All records with same `rule_family_id` stay in same split
- **Target sizes**: Attempts to reach configured target sizes
- **Reproducibility**: Uses fixed random seed

### 5. Task-Specific Dataset Creation

Creates specialized datasets for:
- Classification (all records)
- Extraction (actionable records with rules)
- Clarification (records requiring clarification)
- Duplicate pairs (from same rule families)
- Conflict pairs (from conflicting rule families)

## Rule Family IDs

Rule family IDs group semantically equivalent business rules:

```
ecommerce_EC_R001
├── Revenue should exclude cancelled orders.
├── Cancelled orders must not contribute to revenue.
├── Exclude cancelled orders from revenue.
└── Don't count cancelled orders in revenue.
```

**Important**: Different business rules must have different rule family IDs. The pipeline preserves this by:
- Copying `rule_family_id` from seed for paraphrases
- Creating new IDs for multi-rule combinations
- Creating new IDs for conflicts (with `_conflict` suffix)
- Creating new IDs for ambiguous/non-rule/spam examples

## Validation Reports

### Seed Validation

Checks seed data before generation:
- JSONL validity
- Required fields
- Taxonomy compliance
- Schema references
- Annotation consistency

### Generation Validation

Checks generated data:
- Schema validity
- Domain validity
- Rule structure
- Annotation consistency
- Duplicate detection
- Rule-family consistency

### Consistency Checking

Verifies that records with same `rule_family_id` have:
- Same `feedback_type`
- Same `rule_category`
- Semantically similar rule structures

## Example Output

### Classification Dataset Entry

```json
{
  "feedback_id": "EC_FB001",
  "feedback_text": "Revenue should exclude cancelled orders.",
  "feedback_type": "business_rule_correction",
  "rule_category": "metric_definition",
  "is_actionable": true,
  "requires_clarification": false
}
```

### Extraction Dataset Entry

```json
{
  "feedback_id": "EC_FB001",
  "feedback_text": "Revenue should exclude cancelled orders.",
  "rules": [
    {
      "business_term": "revenue",
      "operation": "exclude",
      "conditions": [
        {
          "field": "orders.status",
          "operator": "equals",
          "value": "cancelled"
        }
      ],
      "scope": "global",
      "time_window": null,
      "threshold": null,
      "affected_entities": {
        "tables": ["orders"],
        "columns": ["orders.status"]
      }
    }
  ],
  "rule_family_id": "ecommerce_EC_R001"
}
```

### Duplicate Pair Entry

```json
{
  "pair_id": "DP0001",
  "feedback_id_1": "EC_FB001",
  "feedback_id_2": "EC_GEN0001",
  "rule_family_id": "ecommerce_EC_R001",
  "relationship": "semantic_duplicate"
}
```

## Extending to Other Domains

The pipeline is domain-agnostic. To use with a different domain:

1. Create a new domain pack with:
   - `domain_config.json`
   - `schema/schema.json`
   - `taxonomy/labels.json`
   - `feedback/seed.jsonl`

2. Update configuration:
```python
config = GenerationConfig(
    domain_pack_id="customer_support",
    domain_pack_version="customer_support_v0.1.0",
    domain_pack_path=Path("domain-packs/customer_support"),
    seed_path=Path("domain-packs/customer_support/feedback/seed.jsonl"),
)
```

3. Run the pipeline with the new config.

## Module Structure

```
dataset_generation/
├── __init__.py           # Package initialization
├── config.py             # Configuration management
├── seed_validator.py     # Seed data validation
├── generators.py         # Synthetic data generators
├── post_validator.py     # Post-generation validation
├── dataset_splitter.py   # Dataset splitting logic
├── output_writer.py      # Output file writing
├── pipeline.py           # Main pipeline orchestration
└── run_pipeline.py       # CLI entry point
```

## Troubleshooting

### Seed Validation Fails

If seed validation fails in strict mode:
1. Check the error messages in the output
2. Fix invalid seed records
2. Or run with `--strict` flag removed to proceed with warnings

### Low Generation Count

If fewer records are generated than expected:
1. Check that seed records have `is_actionable=true` and contain rules
2. Increase multipliers in configuration
3. Add more seed records to cover more rule families

### Split Ratios Not Met

If train/val/test sizes don't match targets:
1. Rule-family-aware splitting may prevent exact ratios
2. Adjust target sizes based on available rule families
3. Add more seed data to increase rule family diversity

### Validation Errors

If many records fail validation:
1. Check `rejected.jsonl` for rejection reasons
2. Review schema references in domain pack
3. Ensure taxonomy labels match domain pack
4. Run with `strict_validation=False` to proceed with warnings

## Best Practices

1. **Always validate seed data** before generation
2. **Review rejected records** to understand generation quality
3. **Keep rule families consistent** - same rule = same family ID
4. **Use frozen test sets** - don't regenerate after initial creation
5. **Track dataset versions** - update `dataset_version` when regenerating
6. **Review validation reports** - check for consistency issues
7. **Manual review required** - LLM-generated data is not automatically correct

## License

Part of the Rule Intelligence Engine project.

## Contact

For questions or issues, refer to the main RIE documentation.
