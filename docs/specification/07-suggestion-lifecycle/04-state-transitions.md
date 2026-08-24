# Section 7: Suggestion Lifecycle - State Transitions

## 7.4 Lifecycle State Transitions

Not every state can transition directly to another state. The Rule Intelligence Engine enforces controlled state transitions to preserve consistency and auditability.

### Allowed Transitions

| Current State | Allowed Next State(s) |
|---------------|----------------------|
| RECEIVED | VALIDATED |
| VALIDATED | ANALYSIS RUN CREATED |
| ANALYSIS RUN CREATED | PROCESSING |
| PROCESSING | PROCESSED |
| DUPLICATE & CONFLICT ANALYSIS | CLARIFICATION CHECK |
| CLARIFICATION CHECK | SUGGESTION GENERATED, CLARIFICATION REQUESTED |
| SUGGESTION GENERATED | PENDING REVIEW |
| PENDING REVIEW | APPROVED, REJECTED, CLARIFICATION REQUESTED |
| APPROVED | READY FOR RULE CREATION |
| READY FOR RULE CREATION | RULE CREATED |
| RULE CREATED (DRAFT) | ACTIVE |

### Enforcement
- Any invalid state transition is rejected by the system
- All state transitions are recorded in the audit history
- This ensures traceability and prevents inconsistent states