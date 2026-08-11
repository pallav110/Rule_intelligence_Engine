# RIE Data Implementation Status

## Overall

- [x] Taxonomy established
- [x] E-Commerce domain pack validated
- [x] Customer Support domain pack complete
- [ ] SaaS Subscription domain pack complete
- [ ] Synthetic dataset generation
- [ ] Train/validation/test splitting
- [ ] Frozen evaluation set
 - [x] SaaS Subscription domain pack complete
 - [x] Synthetic dataset generation (pipeline implemented, small test run)
 - [ ] Train/validation/test splitting (full-size)
 - [ ] Frozen evaluation set
 - [x] Train/validation/test splitting (small/full generated; leakage-controlled by `rule_family_id` grouping)
 - [x] Frozen evaluation set (created as `test.jsonl`, to remain frozen)

## Generated dataset (v1)

- total examples: 937
- per-domain: saas_subscription=310, ecommerce=312, customer_support=315
- rule families: 31
- duplicate pairs: 31 (generated; target 150 — limited by available families with 2+ examples)
- conflict pairs: 13 (from packs' conflicting_rules.json)
- clarifications: 100

Notes: counts differ slightly from original targets due to the number of rule families and per-family allocations; duplicates and conflict pair counts are lower than targets because not enough distinct families had multiple generated paraphrases or explicit conflicting rules. These can be expanded by increasing per-family generation or adding more paraphrase templates.

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
