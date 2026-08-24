# Section 7: Suggestion Lifecycle - Feedback Lifecycle

## 7.1 Feedback Lifecycle

```
Feedback Submitted
│
▼
RECEIVED
│
▼
VALIDATED
│
▼
ANALYSIS RUN CREATED
│
▼
PROCESSING
│
▼
PROCESSED
│
▼
ARCHIVED
```

## Feedback States

| State | Description |
|-------|-------------|
| RECEIVED | Feedback accepted by the API |
| VALIDATED | Authentication, workspace and request schema verified |
| PROCESSING | Classification and rule extraction pipeline executing |
| PROCESSED | One or more suggestions generated successfully |
| ARCHIVED | Feedback retained for audit and traceability |
| ANALYSIS RUN CREATED | Analysis Run initialized for automated processing |

## Key Characteristics
- Each feedback record remains immutable after submission to preserve traceability
- The Feedback lifecycle ends once the generated suggestions are successfully stored
- All subsequent operations occur within the Suggestion lifecycle
- Feedback is retained for audit and traceability purposes