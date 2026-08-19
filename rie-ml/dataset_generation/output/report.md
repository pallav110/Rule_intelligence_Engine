# Dataset Generation Report

**Generated at:** 2026-08-19T11:34:22.874657Z

## Summary

- Seed records: 25
- Total generated: 240
- Approved generated: 240
- Rejected generated: 0
- **Total for splitting**: 265 (seed + approved generated)
- Validation errors: 0
- Validation warnings: 24

## Generation Breakdown

- paraphrases: 47
- conversational: 38
- hinglish: 16
- multi_rule: 5
- ambiguous: 100
- conflicts: 10
- non_rule: 10
- spam: 10
- invalid_schema: 4

## Dataset Split

**Target sizes:** Train=600, Val=150, Test=200

**Actual sizes:**
- Train: 185 records (69.8%) - 102 rule families
- Validation: 39 records (14.7%) - 28 rule families
- Test: 41 records (15.5%) - 28 rule families
- Total rule families: 158

**⚠️ Insufficient data for target split:** Available 265 records vs target 950. Split sizes are limited by available rule families and records. Add more seed data or increase generation multipliers to reach targets.

## Task-Specific Datasets

- Classification: 265 records
- Extraction: 139 records
- Clarification: 104 records
- Duplicate pairs: 496 pairs
- Conflict pairs: 9 pairs

**⚠️ Conflict pairs:** Generated 9 vs target 150. Limited by seeds with numeric thresholds that can create conflicts. Add more threshold-based rules to seed.

## Rule Family Analysis

- Total rule families: 158
- Business rule families: 32 (139 records)
- Non-business families: 126 (126 records)

Non-business breakdown:
- ambiguous: 100 records
- non_rule: 11 records
- other: 4 records
- spam: 11 records

## Validation Warnings

- EC_GEN0108: EC_GEN0108.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0108: EC_GEN0108.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0109: EC_GEN0109.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0109: EC_GEN0109.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0110: EC_GEN0110.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0110: EC_GEN0110.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0111: EC_GEN0111.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0111: EC_GEN0111.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0112: EC_GEN0112.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0112: EC_GEN0112.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0113: EC_GEN0113.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0113: EC_GEN0113.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0118: EC_GEN0118.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0118: EC_GEN0118.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0227: EC_GEN0227.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0227: EC_GEN0227.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0389: EC_GEN0389.rules[0]: unknown schema field 'payments.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0389: EC_GEN0389.rules[0]: unknown affected column 'payments.nonexistent_field'
- EC_GEN0390: EC_GEN0390.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0390: EC_GEN0390.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0392: EC_GEN0392.rules[0]: unknown schema field 'products.missing_attr' (allowed: schema_validation_expected=fail)
- EC_GEN0392: EC_GEN0392.rules[0]: unknown affected column 'products.missing_attr'
- EC_GEN0393: EC_GEN0393.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0393: EC_GEN0393.rules[0]: unknown affected column 'orders.unknown_field'

## Configuration

```json
{
  "domain_pack_id": "ecommerce",
  "domain_pack_version": "ecommerce_v0.1.0",
  "domain_pack_path": "/home/spxlpt133/Desktop/Rule-intelligence-Engine/rie-ml/domain-packs/ecommerce",
  "seed_path": "/home/spxlpt133/Desktop/Rule-intelligence-Engine/rie-ml/domain-packs/ecommerce/feedback/seed.jsonl",
  "output_dir": "/home/spxlpt133/Desktop/Rule-intelligence-Engine/rie-ml/dataset_generation/output",
  "dataset_version": "dataset_v0.1.0",
  "annotation_version": "ann_v0.1.0",
  "random_seed": 42,
  "target_train_size": 600,
  "target_val_size": 150,
  "target_test_size": 200,
  "target_duplicate_pairs": 150,
  "target_conflict_pairs": 150,
  "target_ambiguous": 100,
  "paraphrase_multiplier": 3,
  "conversational_multiplier": 2,
  "hinglish_multiplier": 1,
  "multi_rule_multiplier": 1,
  "strict_validation": true,
  "allow_invalid_schema_refs": false
}
```
