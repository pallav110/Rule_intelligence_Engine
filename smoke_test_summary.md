# Smoke Test — 45 Cases (2026-09-09 17:49:19)

## Validation (Production)
  PASS: 28 | PARTIAL: 8 | FAIL: 1 | ERR: 1

## Validation (Baseline)
  PASS: 15 | PARTIAL: 10 | FAIL: 7 | ERR: 1

## Routing (Production)
  {'senior_review_required': 25, 'clarification_required': 9, 'auto_approved': 2, 'mandatory_manual_review': 8, '?': 1}

## Duplicate Detection
  Prod: {'Exact Duplicate': 8, 'Unique Rule': 31, 'Modification': 3, 'Semantic Duplicate': 2, None: 1}
  Base: {'Exact Duplicate': 4, 'Unique Rule': 27, 'Semantic Duplicate': 3, 'Modification': 10, None: 1}

## Conflicts
  Prod: 10 | Base: 10

## Clarification Required
  Prod: 22 | Base: 22

## Performance
  Prod avg: 0.799s | Base avg: 0.037s
  Errors: 1

