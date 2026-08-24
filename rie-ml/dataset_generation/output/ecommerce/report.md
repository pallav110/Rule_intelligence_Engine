# Dataset Generation Report

**Generated at:** 2026-08-24T06:25:21.381247Z

## Summary

- Seed records: 60
- Total generated: 396
- Approved generated: 396
- Rejected generated: 0
- **Total for splitting**: 456 (seed + approved generated)
- Validation errors: 0
- Validation warnings: 24

## Generation Breakdown

- paraphrases: 122
- conversational: 88
- hinglish: 41
- multi_rule: 5
- ambiguous: 100
- conflicts: 15
- non_rule: 10
- spam: 10
- invalid_schema: 5

## Dataset Split

**Target sizes:** Train=600, Val=150, Test=200

**Actual sizes:**
- Train: 319 records (70.0%) - 144 rule families
- Validation: 68 records (14.9%) - 20 rule families
- Test: 69 records (15.1%) - 36 rule families
- Total rule families: 200

**⚠️ Insufficient data for target split:** Available 456 records vs target 950. Split sizes are limited by available rule families and records. Add more seed data or increase generation multipliers to reach targets.

## Task-Specific Datasets

- Classification: 456 records
- Extraction: 320 records
- Clarification: 114 records
- Duplicate pairs: 1020 pairs
- Conflict pairs: 9 pairs

**⚠️ Conflict pairs:** Generated 9 vs target 150. Limited by seeds with numeric thresholds that can create conflicts. Add more threshold-based rules to seed.

## Rule Family Analysis

- Total rule families: 200
- Business rule families: 64 (320 records)
- Non-business families: 136 (136 records)

Non-business breakdown:
- ambiguous: 100 records
- non_rule: 11 records
- other: 14 records
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
- EC_GEN0382: EC_GEN0382.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0382: EC_GEN0382.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0539: EC_GEN0539.rules[0]: unknown schema field 'customers.fake_column' (allowed: schema_validation_expected=fail)
- EC_GEN0539: EC_GEN0539.rules[0]: unknown affected column 'customers.fake_column'
- EC_GEN0540: EC_GEN0540.rules[0]: unknown schema field 'payments.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0540: EC_GEN0540.rules[0]: unknown affected column 'payments.nonexistent_field'
- EC_GEN0541: EC_GEN0541.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0541: EC_GEN0541.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0542: EC_GEN0542.rules[0]: unknown schema field 'customers.fake_column' (allowed: schema_validation_expected=fail)
- EC_GEN0542: EC_GEN0542.rules[0]: unknown affected column 'customers.fake_column'
- EC_GEN0543: EC_GEN0543.rules[0]: unknown schema field 'payments.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0543: EC_GEN0543.rules[0]: unknown affected column 'payments.nonexistent_field'

## Configuration

```json
{
  "domain_pack_id": "ecommerce",
  "domain_pack_version": "ecommerce_v0.1.0",
  "domain_pack_path": "domain-packs/ecommerce",
  "seed_path": "domain-packs/ecommerce/feedback/seed.jsonl",
  "output_dir": "dataset_generation/output/ecommerce_v2",
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
