# RIE Data Implementation Status

## Overall

- [x] Taxonomy established
- [x] E-Commerce domain pack validated
- [x] Customer Support domain pack complete
- [x] SaaS Subscription domain pack complete
- [x] Synthetic dataset generation (v1)
- [x] Train/validation/test splitting (v1)
- [x] Frozen evaluation set (v1 `test.jsonl`)

Notes: The v1 dataset generation, splitting, pair generation, and validation are complete and documented below.

## Generated dataset (v1)
 - total examples: 937
 - per-domain: saas_subscription=310, ecommerce=312, customer_support=315
 - rule families: 31
 - duplicate pairs: 150
 - conflict pairs: 150
 - clarifications: 100

Status: Synthetic dataset generation, pair generation, splitting, and basic+pairs validation are COMPLETE for v1. The dataset is reproducible from `rie-ml/dataset_pipeline/config.json` (seed=42, version=v1).

Canonical artifacts (location: `rie-ml/datasets/generated/v1`):

 - generated_all.jsonl — 937 examples
 - train.jsonl — 600 examples
 - validation.jsonl — 153 examples
 - test.jsonl (FROZEN) — 184 examples
 - duplicate_pairs.jsonl — 150 pairs
 - conflict_pairs.jsonl — 150 pairs
 - clarifications.jsonl — 100 examples
 - metadata.json — generation metadata + checksums

SHA-256 checksums (selected):

 - generated_all.jsonl: 927a2cfaee1165d402c47e93cd11a47d19b4b44e56609623a7fb37ba06ba9d10
 - train.jsonl: cee9f7363ec5ae791da0d913f40749e2502c4bb6b1094418006e48b1aa0c4344
 - validation.jsonl: 893450e5d0599e6ee4ff0e8571027f2b76245e300666416be42b7919d5acb5d8
 - test.jsonl: abe11df856965b98127def72f14cb4c96d2bcd556cea4fa5b941a3d0ef3ef368
 - duplicate_pairs.jsonl: 90eee7a2cda40029197fa120f5d32fa9d147cbf78e6e4038bd2ab9a52dac507f
 - conflict_pairs.jsonl: 7268e5d98ef03228c1cb972de8c7d99108e6ea9d24288979193d1b5db95c4053

Reproducibility & freeze notes:

 - The `test.jsonl` file is the frozen evaluation set for v1 — do not modify it.
 - To reproduce exactly, run:

	 python3 -m rie-ml.dataset_pipeline.make_dataset

	 (Ensure `rie-ml/domain-packs` and `rie-ml/dataset_pipeline/config.json` are unchanged.)

Cleanup:

 - I scanned the repository for other copies of the generated artifacts and found no duplicate generated files outside `rie-ml/datasets/generated/v1`.
 - If you have specific files or folders you consider extraneous, tell me which ones and I'll remove them; I did not delete any non-obvious files without confirmation.

## E-Commerce

- [x] schema
- [x] relationships
- [x] glossary
- [x] canonical rules
- [x] annotation guide
- [x] seed examples
- [x] schema validation
- [x] dataset validation
- [x] version metadata

## Customer Support

- [x] domain_config.json
- [x] taxonomy/labels.json
- [x] schema/schema.json
- [x] schema/relationships.json
- [x] rules/active_rules.json
- [x] rules/conflicting_rules.json
- [x] documentation/annotation_guide.md
- [x] documentation/business_glossary.md
- [x] feedback/seed.jsonl
- [x] pack validation

- [x] one intentional invalid-schema validation example (CS_FB024)

## Notes

- The Customer Support pack is being built incrementally.
- The global taxonomy is not being modified.
- E-Commerce remains unchanged.
