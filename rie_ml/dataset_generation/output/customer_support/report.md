# Dataset Generation Report

**Generated at:** 2026-08-24T06:25:30.243750Z

## Summary

- Seed records: 51
- Total generated: 380
- Approved generated: 380
- Rejected generated: 0
- **Total for splitting**: 431 (seed + approved generated)
- Validation errors: 0
- Validation warnings: 24

## Generation Breakdown

- paraphrases: 111
- conversational: 82
- hinglish: 39
- multi_rule: 5
- ambiguous: 100
- conflicts: 18
- non_rule: 10
- spam: 10
- invalid_schema: 5

## Dataset Split

**Target sizes:** Train=600, Val=150, Test=200

**Actual sizes:**
- Train: 301 records (69.8%) - 126 rule families
- Validation: 64 records (14.8%) - 37 rule families
- Test: 66 records (15.3%) - 34 rule families
- Total rule families: 197

**⚠️ Insufficient data for target split:** Available 431 records vs target 950. Split sizes are limited by available rule families and records. Add more seed data or increase generation multipliers to reach targets.

## Task-Specific Datasets

- Classification: 431 records
- Extraction: 301 records
- Clarification: 108 records
- Duplicate pairs: 856 pairs
- Conflict pairs: 18 pairs

**⚠️ Conflict pairs:** Generated 18 vs target 150. Limited by seeds with numeric thresholds that can create conflicts. Add more threshold-based rules to seed.

## Rule Family Analysis

- Total rule families: 197
- Business rule families: 67 (301 records)
- Non-business families: 130 (130 records)

Non-business breakdown:
- ambiguous: 100 records
- non_rule: 10 records
- other: 10 records
- spam: 10 records

## Validation Warnings

- EC_GEN0109: EC_GEN0109.rules[0]: unknown schema field 'tickets.unknown_column' (allowed: schema_validation_expected=fail)
- EC_GEN0109: EC_GEN0109.rules[0]: unknown affected column 'tickets.unknown_column'
- EC_GEN0110: EC_GEN0110.rules[0]: unknown schema field 'tickets.unknown_column' (allowed: schema_validation_expected=fail)
- EC_GEN0110: EC_GEN0110.rules[0]: unknown affected column 'tickets.unknown_column'
- EC_GEN0111: EC_GEN0111.rules[0]: unknown schema field 'tickets.unknown_column' (allowed: schema_validation_expected=fail)
- EC_GEN0111: EC_GEN0111.rules[0]: unknown affected column 'tickets.unknown_column'
- EC_GEN0112: EC_GEN0112.rules[0]: unknown schema field 'tickets.unknown_column' (allowed: schema_validation_expected=fail)
- EC_GEN0112: EC_GEN0112.rules[0]: unknown affected column 'tickets.unknown_column'
- EC_GEN0113: EC_GEN0113.rules[0]: unknown schema field 'tickets.unknown_column' (allowed: schema_validation_expected=fail)
- EC_GEN0113: EC_GEN0113.rules[0]: unknown affected column 'tickets.unknown_column'
- EC_GEN0114: EC_GEN0114.rules[0]: unknown schema field 'tickets.unknown_column' (allowed: schema_validation_expected=fail)
- EC_GEN0114: EC_GEN0114.rules[0]: unknown affected column 'tickets.unknown_column'
- EC_GEN0372: EC_GEN0372.rules[0]: unknown schema field 'tickets.unknown_column' (allowed: schema_validation_expected=fail)
- EC_GEN0372: EC_GEN0372.rules[0]: unknown affected column 'tickets.unknown_column'
- EC_GEN0522: EC_GEN0522.rules[0]: unknown schema field 'payments.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0522: EC_GEN0522.rules[0]: unknown affected column 'payments.nonexistent_field'
- EC_GEN0523: EC_GEN0523.rules[0]: unknown schema field 'payments.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0523: EC_GEN0523.rules[0]: unknown affected column 'payments.nonexistent_field'
- EC_GEN0524: EC_GEN0524.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0524: EC_GEN0524.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0525: EC_GEN0525.rules[0]: unknown schema field 'products.missing_attr' (allowed: schema_validation_expected=fail)
- EC_GEN0525: EC_GEN0525.rules[0]: unknown affected column 'products.missing_attr'
- EC_GEN0526: EC_GEN0526.rules[0]: unknown schema field 'products.missing_attr' (allowed: schema_validation_expected=fail)
- EC_GEN0526: EC_GEN0526.rules[0]: unknown affected column 'products.missing_attr'

## Configuration

```json
{
  "domain_pack_id": "ecommerce",
  "domain_pack_version": "ecommerce_v0.1.0",
  "domain_pack_path": "domain-packs/customer_support",
  "seed_path": "domain-packs/customer_support/feedback/seed.jsonl",
  "output_dir": "dataset_generation/output/customer_support_v2",
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
