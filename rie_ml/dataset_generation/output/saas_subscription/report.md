# Dataset Generation Report

**Generated at:** 2026-08-24T06:25:38.836538Z

## Summary

- Seed records: 49
- Total generated: 383
- Approved generated: 383
- Rejected generated: 0
- **Total for splitting**: 432 (seed + approved generated)
- Validation errors: 0
- Validation warnings: 24

## Generation Breakdown

- paraphrases: 115
- conversational: 78
- hinglish: 39
- multi_rule: 5
- ambiguous: 100
- conflicts: 21
- non_rule: 10
- spam: 10
- invalid_schema: 5

## Dataset Split

**Target sizes:** Train=600, Val=150, Test=200

**Actual sizes:**
- Train: 302 records (69.9%) - 128 rule families
- Validation: 64 records (14.8%) - 40 rule families
- Test: 66 records (15.3%) - 32 rule families
- Total rule families: 200

**⚠️ Insufficient data for target split:** Available 432 records vs target 950. Split sizes are limited by available rule families and records. Add more seed data or increase generation multipliers to reach targets.

## Task-Specific Datasets

- Classification: 432 records
- Extraction: 302 records
- Clarification: 107 records
- Duplicate pairs: 808 pairs
- Conflict pairs: 21 pairs

**⚠️ Conflict pairs:** Generated 21 vs target 150. Limited by seeds with numeric thresholds that can create conflicts. Add more threshold-based rules to seed.

## Rule Family Analysis

- Total rule families: 200
- Business rule families: 70 (302 records)
- Non-business families: 130 (130 records)

Non-business breakdown:
- ambiguous: 100 records
- non_rule: 10 records
- other: 10 records
- spam: 10 records

## Validation Warnings

- EC_GEN0121: EC_GEN0121.rules[0]: unknown schema field 'subscriptions.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0121: EC_GEN0121.rules[0]: unknown affected column 'subscriptions.nonexistent_field'
- EC_GEN0122: EC_GEN0122.rules[0]: unknown schema field 'subscriptions.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0122: EC_GEN0122.rules[0]: unknown affected column 'subscriptions.nonexistent_field'
- EC_GEN0123: EC_GEN0123.rules[0]: unknown schema field 'subscriptions.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0123: EC_GEN0123.rules[0]: unknown affected column 'subscriptions.nonexistent_field'
- EC_GEN0124: EC_GEN0124.rules[0]: unknown schema field 'subscriptions.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0124: EC_GEN0124.rules[0]: unknown affected column 'subscriptions.nonexistent_field'
- EC_GEN0125: EC_GEN0125.rules[0]: unknown schema field 'subscriptions.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0125: EC_GEN0125.rules[0]: unknown affected column 'subscriptions.nonexistent_field'
- EC_GEN0126: EC_GEN0126.rules[0]: unknown schema field 'subscriptions.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0126: EC_GEN0126.rules[0]: unknown affected column 'subscriptions.nonexistent_field'
- EC_GEN0401: EC_GEN0401.rules[0]: unknown schema field 'subscriptions.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0401: EC_GEN0401.rules[0]: unknown affected column 'subscriptions.nonexistent_field'
- EC_GEN0510: EC_GEN0510.rules[0]: unknown schema field 'products.missing_attr' (allowed: schema_validation_expected=fail)
- EC_GEN0510: EC_GEN0510.rules[0]: unknown affected column 'products.missing_attr'
- EC_GEN0511: EC_GEN0511.rules[0]: unknown schema field 'payments.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0511: EC_GEN0511.rules[0]: unknown affected column 'payments.nonexistent_field'
- EC_GEN0512: EC_GEN0512.rules[0]: unknown schema field 'payments.nonexistent_field' (allowed: schema_validation_expected=fail)
- EC_GEN0512: EC_GEN0512.rules[0]: unknown affected column 'payments.nonexistent_field'
- EC_GEN0513: EC_GEN0513.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0513: EC_GEN0513.rules[0]: unknown affected column 'orders.unknown_field'
- EC_GEN0514: EC_GEN0514.rules[0]: unknown schema field 'orders.unknown_field' (allowed: schema_validation_expected=fail)
- EC_GEN0514: EC_GEN0514.rules[0]: unknown affected column 'orders.unknown_field'

## Configuration

```json
{
  "domain_pack_id": "ecommerce",
  "domain_pack_version": "ecommerce_v0.1.0",
  "domain_pack_path": "domain-packs/saas_subscription",
  "seed_path": "domain-packs/saas_subscription/feedback/seed.jsonl",
  "output_dir": "dataset_generation/output/saas_subscription_v2",
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
