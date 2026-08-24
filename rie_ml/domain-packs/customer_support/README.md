# Customer Support Domain Pack

**Version:** `customer_support_v0.1.0`  
**Created:** 2026-08-11  
**Annotation Version:** `ann_v0.1.0`

This pack is the structural template for the Customer Support domain in RIE. It will mirror the E-Commerce pack layout while using customer-support-specific business semantics, schema fields, glossary terms, and seed examples.

## Structure

- `domain_config.json`
- `taxonomy/labels.json`
- `schema/schema.json`
- `schema/relationships.json`
- `rules/active_rules.json`
- `rules/conflicting_rules.json`
- `documentation/business_glossary.md`
- `documentation/annotation_guide.md`
- `feedback/seed.jsonl`

## Notes

- Uses the repository-wide frozen taxonomy from `taxonomy_v0.1.0`.
- Does not reuse E-Commerce business terms or schema fields.
- Seed examples and annotation guide are included after schema and rule validation.
- Validation passes with one intentional invalid-schema test example (`CS_FB024`).
