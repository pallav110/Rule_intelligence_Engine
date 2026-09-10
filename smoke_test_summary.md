# Smoke Test 45-Case Regression Summary

## v3 → v4 (2026-09-10)

### Validation Scorecard
| Metric | v3 | v4 | Δ |
|--------|----|----|---|
| PASS   | 28 | 34 | +6 |
| PARTIAL| 8  | 2  | -6 |
| N/A    | 7  | 7  |  0 |
| FAIL   | 1  | 1  |  0 |
| ERR    | 1  | 1  |  0 |

### Hallucinated tables/columns: **0** (was present in v3)

### Cases Improved (PARTIAL → PASS)
| Case | v3 issue | v4 fix |
|------|----------|--------|
| 7  | term=Returned (adjective) → Products | Business term validation |
| 11 | term=computing (verb) → Orders | Schema table noun lookup |
| 16 | `created_at` hallucinated column | Date-column resolution + pruning |
| 17 | "completed" hallucinated table | Non-schema table pruning |
| 26 | term=Cancelled → Orders | Business term validation |
| 30 | term=Cancelled → Orders | Business term validation |

### Remaining Issues
| Case | Status | Issue |
|------|--------|-------|
| 10, 22 | PARTIAL | "Purchases" not in domain glossary (extractor correct, glossary gap) |
| 40 | FAIL | Gibberish input "xj29 revenue zzz" — correctly unclassifiable |
| 41 | ERR | Empty feedback — Pydantic min_length=1 (expected) |

### Root Cause Fixed This Session
Schema was loaded **after** extraction in both analyze + re-analyze endpoints, so
the extractor's business-term validation and table-lookup ran with empty schema.
Fixed by loading `domain_schema` before STEP 3 and injecting into context.
