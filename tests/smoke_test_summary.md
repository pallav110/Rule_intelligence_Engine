# Smoke Test 45-Case Regression Summary

## v4 (latest — 2026-09-10, post-glossary fix)

### Validation Scorecard
| Metric | prev v4 | now v4 | Δ |
|--------|---------|--------|---|
| PASS   | 34      | 36     | +2 |
| PARTIAL| 2       | 0      | −2 |
| N/A    | 7       | 7      |  0 |
| FAIL   | 1       | 1      |  0 |
| ERR    | 1       | 1      |  0 |

### Hallucinated tables/columns: **0**

### Cases Improved (PARTIAL → PASS)
| Case | v4 issue | fix |
|------|----------|-----|
| 10 | "Cancelled purchases shouldn't contribute to revenue." — `Business term 'Purchases' not found in glossary` | orders table synonyms + glossary extraction updated |
| 22 | "Average order value should include completed purchases only." — same glossary gap | same fix |

### Fix Details
**Root cause:** Schema validation's glossary was built only from table/column names
and `business_meaning` fields — "purchases" (a natural synonym for orders) was
never in the derived glossary.

**Changes applied:**
1. `schema.json` — added `synonyms: ["purchases", "purchase", "sale", "sales"]`
   to orders table (and synonyms to all other tables for consistency)
2. `schema_validation_service.py` — `_extract_glossary_from_schema` now also reads
   table `description` and `synonyms[]` fields into the glossary
3. `business_glossary.md` — synonyms table updated with full alias lists

### Remaining (non-fixable via code/data only)
| Case | Status | Issue |
|------|--------|-------|
| 40 | FAIL | Gibberish input — correctly unclassifiable |
| 41 | ERR | Empty feedback — Pydantic min_length=1 (expected) |
