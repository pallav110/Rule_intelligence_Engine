# Dataset Generation Report

**Generated at:** 2026-08-17T11:06:46.415454Z

## Summary

- Total records generated: 0
- Valid records: 0
- Rejected records: 0
- Validation errors: 0
- Validation warnings: 0

## Generation Breakdown

- paraphrases: 57
- conversational: 38
- hinglish: 19
- multi_rule: 5
- ambiguous: 100
- conflicts: 150
- non_rule: 10
- spam: 10
- invalid_schema: 5

## Dataset Split

- Train: 63 records (15.3%)
- Validation: 150 records (36.3%)
- Test: 200 records (48.4%)
- Rule families: 152

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
