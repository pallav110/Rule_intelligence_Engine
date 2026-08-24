# Section 3: System Workflow and Data Flow (cont.)

## 3.2 Human Review Flow

The Human Review Flow operates independently after automated analysis has completed.

Authorized reviewers access the review dashboard and retrieve suggestions that are currently awaiting review.

### For each suggestion, reviewers can examine:
- Original business feedback
- Structured rule suggestion
- Classification results
- Extracted business entities
- Duplicate detection results
- Conflict detection results
- Classification results
- Extraction results
- Schema validation results
- Supporting evidence
- Clarification requests (if applicable)

### Reviewer Actions
After evaluating the generated suggestion, reviewers may perform one of the following actions:

- **Approve the suggestion** – changes status to APPROVED
- **Reject the suggestion** – changes status to REJECTED
- **Request Clarification** – additional business information required
- **Archive the suggestion** – no longer relevant

### Audit Trail
Each review action is recorded in the audit history together with:
- Reviewer identifier
- Decision
- Timestamp
- Review comments

### Clarification Handling
If clarification is requested, the original feedback remains unchanged. The clarification request and user response are stored separately, after which a new Analysis Run is created using the original feedback together with the clarification response while preserving the original submission as an immutable record.

### Approval Limitations
Human approval changes only the suggestion review status. It does not create, activate, modify, or deploy a business rule.

### Eligibility
Approved suggestions become eligible for draft business rule creation through a separate workflow. Rule activation requires an explicit administrative action and is performed independently of the review process.