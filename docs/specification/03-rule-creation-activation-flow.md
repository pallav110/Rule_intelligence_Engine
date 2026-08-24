# Section 3: System Workflow and Data Flow (cont.)

## 3.3 Rule Activation Flow

Business rule creation and activation are intentionally separated from the review workflow to ensure complete human control over production rule management.

### Rule Creation and Activation Workflow

**1. Draft Business Rule Creation**
- Only suggestions with an APPROVED status are eligible for draft business rule creation.
- An approved suggestion is selected for draft rule creation.
- One or more structured extracted rules are converted into formal business rules.
- Each generated rule is validated against the active rule repository using structured rule comparison.
- The validated rule is stored in the Rule Repository with a status of DRAFT.

**2. Rule Activation**
- An authorized administrator reviews the draft rule and explicitly invokes the Rule Activation API.
- The rule status is updated to ACTIVE and becomes available for downstream systems.

### Separation Principles
- Reviewer approval does not automatically create or activate production business rules
- Business rule creation and rule activation remain independent administrative actions
- This separation ensures that AI-generated suggestions never directly modify production business rules
- Production rules remain under complete human control

## 3.4 Suggestion Lifecycle

Every submitted feedback progresses through a predefined lifecycle that ensures traceability and controlled rule management.

| Status | Description |
|--------|-------------|
| RECEIVED | Feedback successfully received by the API |
| VALIDATED | Authentication, request validation, and schema validation completed |
| CLASSIFIED | Feedback type, rule category, and actionability identified |
| EXTRACTED | Structured rule information extracted from the feedback |
| ANALYZED | Duplicate detection, conflict detection, schema validation, clarification analysis, and evidence generation completed |
| PENDING_REVIEW | Suggestion stored and waiting for human review |
| CLARIFICATION_REQUIRED | Additional business information is required |
| APPROVED | Suggestion approved by an authorized reviewer |
| REJECTED | Suggestion rejected after manual review |
| READY_FOR_RULE_CREATION | Approved suggestion is eligible for draft business rule creation |
| RULE_CREATED | Formal business rule generated, validated, and stored in the Rule Repository with a status of DRAFT |
| RULE_ACTIVATED | An authorized administrator activates the draft business rule, making it available for operational use |

### Key Design Principles
- Feedback, suggestions, extracted rules, draft business rules, and active business rules remain separate entities throughout the system
- This separation preserves complete traceability, supports independent review and analysis, and prevents unintended modification of production business logic