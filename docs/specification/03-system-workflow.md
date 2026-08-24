# Section 3: System Workflow and Data Flow

## 3.1 Feedback Analysis Flow

The Feedback Analysis Flow begins when a client submits business feedback through the POST /v1/feedback/analyze endpoint. Each request includes the business feedback, authentication credentials, the requested workspace identifier, and optional schema context required for validation.

### Step 1 – Feedback Classification
The Classification Module analyzes the submitted feedback and predicts:
- Feedback type
- Rule category
- Business domain
- Actionability
- Whether clarification is required
- Initial review priority

The classification result provides structured context for all subsequent processing stages.

### Step 2 – Rule Extraction
The Rule Extraction Module converts the unstructured feedback into one or more structured canonical business rules by identifying and extracting:
- Business term
- Operation
- Structured conditions (field, operator, value)
- Scope
- Time window
- Threshold values
- Affected tables and columns
- Schema references

Every extracted rule component is validated against the provided schema metadata. Unknown tables, columns, business terms, or invalid operations are flagged rather than accepted automatically. A single feedback submission may generate multiple structured rules, each stored independently while maintaining traceability to the originating feedback and suggestion.

### Step 3 – Duplicate Detection
The Duplicate Detection Module compares the generated suggestion against previously approved business rules and existing suggestions to determine whether it represents:
- Exact Duplicate
- Semantic Duplicate
- Extension of an existing rule
- Modification of an existing rule
- Unrelated suggestion

Semantic similarity search using pgvector is first used to retrieve candidate rules. Final duplicate classification is then performed using structured rule comparison based on business term, operation, conditions, scope, time window, threshold values, and affected schema elements. The duplicate relationship is recorded for each extracted rule.

### Step 4 – Conflict Detection
The Conflict Detection Module evaluates whether the proposed rule logically conflicts with existing active business rules.

Possible outcomes include:
- Direct Conflict
- Potential Conflict
- No Conflict

Conflict detection follows the same two-stage approach. Candidate rules are retrieved using semantic similarity, while final conflict determination is performed using structured rule comparison based on business term, operation, conditions, scope, time window, threshold values, and affected schema elements. Conflict results are recorded independently and later used during review routing.

### Step 5 – Clarification Handling
If mandatory business information is missing or ambiguous, the Clarification Module identifies the missing information and generates structured clarification requests.

The system never assumes or invents missing business information. Clarification requests and user responses are stored separately from the original feedback. When a clarification response is received, a new Analysis Run is created using the original feedback together with the clarification response while preserving the original submission as an immutable record.

### Step 6 – Confidence & Evidence Generation
Each stage of the analysis produces independent outputs, including calibrated classification probabilities, extraction probabilities, schema validation results, duplicate detection results, conflict detection results, and supporting evidence.

Schema validation is represented using pass/fail status together with validation coverage rather than as a confidence score. These outputs are recorded separately to support explainability and human review.

### Step 7 – Review Routing
Based on validation results, duplicate detection, conflict detection, clarification requirements, and classification results, the Review Routing Module determines the appropriate review path.

Possible routing outcomes include:
- Normal Review
- High-Priority Review
- Clarification Required
- Validation Failure
- Mandatory Manual Review

Suggestions are automatically routed to mandatory manual review whenever schema validation fails, mandatory business fields are missing, sensitive business rules are detected, duplicate or conflict analysis identifies potential issues, or calibrated model outputs fall below configured thresholds.

The API immediately returns a response containing:
- Suggestion ID
- Current processing status
- Classification results
- Extraction results
- Schema validation status
- Duplicate indicators
- Conflict indicators
- Clarification requirement (if applicable)

The feedback analysis work-flow ends at this point. No business rule is created, modified, or activated during automated analysis.