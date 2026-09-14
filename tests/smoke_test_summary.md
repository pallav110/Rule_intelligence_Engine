# Smoke Test — 45 Cases (2026-09-14 10:59:43)

## Validation (Production)
  PASS: 36 | PARTIAL: 0 | FAIL: 0 | ERR: 1

## Validation (Baseline)
  PASS: 27 | PARTIAL: 3 | FAIL: 3 | ERR: 1

## Routing (Production)
  {'senior_review_required': 30, 'auto_approved': 5, 'clarification_required': 1, 'mandatory_manual_review': 8, '?': 1}

## Duplicate Detection
  Prod: {'Exact Duplicate': 10, 'Unique Rule': 32, 'Modification': 1, 'Semantic Duplicate': 1, None: 1}
  Base: {'Exact Duplicate': 6, 'Unique Rule': 30, 'Semantic Duplicate': 4, 'Modification': 4, None: 1}

## Conflicts
  Prod: 15 | Base: 13

## Clarification Required
  Prod: 10 | Base: 19

## Performance
  Prod avg: 0.347s | Base avg: 0.041s
  Errors: 1

