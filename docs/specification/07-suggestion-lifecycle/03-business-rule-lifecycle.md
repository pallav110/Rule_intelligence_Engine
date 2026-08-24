# Section 7: Suggestion Lifecycle - Business Rule Lifecycle

## 7.3 Business Rule Lifecycle

```
RULE CREATED (DRAFT)
│
▼
DRAFT
│
▼
ACTIVE
│
├──────────────┐
▼              ▼
MODIFIED    RETIRED
```

## Rule States

| State | Description |
|-------|-------------|
| RULE CREATED | Rule generated from an approved suggestion |
| DRAFT | Available for administrative verification |
| ACTIVE | Business rule currently enforced |
| MODIFIED | Updated after business changes |
| RETIRED | Rule removed from production while retained for audit history |

## Key Characteristics
- Only authorized administrators may activate, modify or retire business rules
- This separation ensures that reviewer approval does not automatically create or activate production business rules
- Business rule creation and rule activation remain independent administrative actions