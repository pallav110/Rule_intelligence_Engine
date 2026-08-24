# Section 7: Suggestion Lifecycle - Suggestion Lifecycle

## 7.2 Suggestion Lifecycle

```
Suggestion Generated
│
▼
PENDING REVIEW
├──────────────┬──────────────┬──────────────┐
▼              ▼              ▼              ▼
APPROVED    REJECTED    CLARIFICATION REQUIRED    ARCHIVED
│
▼
READY FOR RULE CREATION
│
▼
RULE CREATED (DRAFT)
```

## Suggestion States

| State | Description |
|-------|-------------|
| GENERATED | Structured suggestion stored after processing |
| PENDING REVIEW | Waiting for reviewer evaluation |
| APPROVED | Business logic accepted by reviewer |
| REJECTED | Suggestion rejected |
| CLARIFICATION REQUESTED | Awaiting additional information |
| READY FOR RULE CREATION | Eligible for conversion into a business rule |
| RULE CREATED (DRAFT) | Draft business rule created from the approved suggestion |

## Critical Design Principles

**Suggestion approval confirms only that the proposed business logic is acceptable.** The generated business rule remains inactive until explicitly activated through the Business Rule lifecycle.

**If clarification is requested, the original feedback remains unchanged.** The clarification response is stored separately and a new Analysis Run is created before the updated suggestion re-enters the review lifecycle.