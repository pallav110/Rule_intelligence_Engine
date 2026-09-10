# Section 8: Core ML Modules

## 8.1 Input Validation
Before any machine learning model is executed, the API validates the incoming request.

The validation stage verifies:
- Authentication token
- Workspace membership authorization
- JSON schema
- Required request fields
- Maximum feedback length
- Supported content type
- Duplicate request identifier (Idempotency Key)

Requests failing validation immediately return an appropriate HTTP error response without entering the processing pipeline.

Authorization verifies that the authenticated user is permitted to access the requested workspace before analysis begins.

---

## 8.2 Feedback Preprocessing
The preprocessing module normalizes the submitted feedback while preserving its business meaning.

Operations performed include:
- Unicode normalization
- Whitespace normalization
- Sentence segmentation
- Tokenization
- Removal of unnecessary punctuation
- Business keyword preservation
- Detection of schema references
- Basic spelling correction (optional)
- Language normalization for conversational English and Hinglish

**Example:**
```
Input : Revenue shouldnt include cancelld orders...
Output: Revenue should not include cancelled orders.
```

No business information is added or inferred during preprocessing.

---

## 8.3 Feedback Classification

The objective of the classification module is to determine whether the submitted feedback contains actionable business logic and how it should be routed.

The classification module generates calibrated predictions for **four independent classification tasks**:

| Prediction | Description |
|------------|-------------|
| **Feedback Type** | Identifies whether the feedback represents a business rule, issue report, feature request, question, or general feedback |
| **Rule Category** | Categorizes actionable feedback (Metric Rule, Filter Rule, Mapping Rule, Access Rule, Join Rule, etc.) |
| **Actionable** | Determines whether rule extraction should continue |
| **Clarification Requirement** | Predicts whether additional information is likely to be required before rule extraction |

> Raw model probabilities are calibrated before downstream decision making. Classification outputs are recorded independently from extraction and other pipeline stages.

### 8.3.1 Baseline Approach
The baseline classifier provides the deterministic reference implementation used for benchmarking candidate machine learning models.

**Components:**
- Regular Expressions
- Business Keyword Dictionaries
- TF-IDF Vectorization
- Logistic Regression Classifier

**Pipeline:**
```
Feedback → Text Cleaning → TF-IDF Vectorization → Logistic Regression → Predicted Category
```

The TF-IDF vectorizer converts feedback into sparse numerical vectors representing word importance. A Logistic Regression classifier is trained on these vectors to predict category labels.

**Advantages:**
- Fast inference
- Explainable predictions
- Easy debugging
- Provides a reproducible performance baseline

> This deterministic approach serves as the evaluation baseline for model comparison and as the fallback mechanism if no candidate model is approved.

### 8.3.2 Machine Learning Implementation

The initial candidate machine learning classifier uses the Hugging Face checkpoint `distilbert-base-uncased`, fine-tuned for the four independent classification tasks.

The candidate model is selected because it:
- Understands semantic meaning
- Handles conversational language
- Works well with short business feedback
- Is approximately 40% smaller than BERT
- Provides faster inference

The candidate model predicts the following independent outputs **simultaneously**:
- Feedback Type
- Rule Category
- Actionable
- Clarification Required

#### Training and Annotation Dataset

Training data consists of:
- Manually annotated classification dataset
- Synthetic business feedback
- Reviewer-approved business feedback
- Public datasets (where applicable)

Data split:
| Split | Percentage |
|-------|-----------|
| Training | 70% |
| Validation | 15% |
| Frozen Evaluation | 15% |

> The frozen evaluation dataset is never used during model training, validation, or hyperparameter tuning. No feedback from the testing dataset is used during training.

#### Model Input
```json
{
  "workspace": "Finance",
  "feedback": "Revenue should exclude cancelled orders."
}
```

Before inference:
```
Lowercase → Tokenization → Attention Mask → Tokenizer Encoding → DistilBERT
```

#### Model Output
```json
{
  "feedback_type": "Business Rule",
  "rule_category": "Metric Definition",
  "actionable": true,
  "clarification_required": false,
  "classification_probability": 0.96
}
```

> Classification probabilities are calibrated before downstream decision making and are recorded independently from extraction confidence.

#### Implementation Details

**Python Libraries:** `transformers`, `torch`, `scikit-learn`, `datasets`

**Training Pipeline:**
```
Dataset → Tokenizer → DistilBERT → Fine Tuning → Validation → Model Registry
```

**Inference:**
```
FastAPI → Load DistilBERT → Predict → JSON
```

**Evaluation:**
Classification performance is measured using:
- Accuracy
- Precision
- Recall
- Macro F1
- Weighted F1
- Per-category F1
- Confusion Matrix

The deterministic baseline and the candidate DistilBERT model are evaluated on the same frozen evaluation dataset. The candidate must demonstrate measurable improvement over the baseline.

#### Model Comparison Table

| Model | Role |
|-------|------|
| TF-IDF + Logistic Regression | Deterministic baseline |
| DistilBERT (`distilbert-base-uncased`) | Initial candidate model |
| BERT | Alternative candidate |
| RoBERTa | Alternative candidate |

#### Configuration Table

| Configuration | Value |
|--------------|-------|
| Model Checkpoint | `distilbert-base-uncased` |
| Tokenizer | `DistilBertTokenizerFast` |
| Maximum Sequence Length | 256 tokens |
| Batch Size | 16 |
| Optimizer | AdamW |
| Learning Rate | 2e-5 |
| Execution Hardware | CPU-based inference with optional GPU support during training |

#### Classification Task Labels

| Classification Task | Labels |
|--------------------|--------|
| **Feedback Type** | `Business Rule`, `Issue Report`, `Feature Request`, `Question`, `General Feedback` |
| **Rule Category** | `Metric Definition`, `Filter Rule`, `Mapping Rule`, `Access Rule`, `Join Rule`, `Data Quality Rule` |
| **Actionable** | `true`, `false` (sigmoid) |
| **Clarification Required** | `true`, `false` (sigmoid) |

> **Source of truth:** These labels are defined in the authoritative Word document (§8.3.2). The `rule_category` labels also serve as sub-categories under `Business Rule` feedback type. Non-rule feedback types (`Issue Report`, `Feature Request`, `Question`, `General Feedback`) do not undergo rule extraction.

---

## 8.4 Rule Extraction

### Overview
The Rule Extraction module converts actionable business feedback into one or more structured business rules. The module identifies business entities and rule components from natural-language feedback and then transforms these components into the canonical Rule JSON structure defined for the Rule Intelligence Engine.

### Two-Stage Process
1. **Entity/Span Extraction** – identifies relevant business terms, operations, fields, values, scopes and temporal expressions from the feedback
2. **Rule Construction** – converts the extracted entities into one or more structured rules containing explicit field, operator, and value conditions

### Input Requirements
- Original feedback text
- Workspace/domain identifier
- Domain glossary
- Schema metadata
- Available tables and columns
- Previous clarification response (if applicable)

### Output Structure
The module produces one or more structured rules containing:
- `business_term` – Business metric or concept (e.g., "Revenue")
- `operation` – Rule operation (e.g., EXCLUDE)
- `conditions` – Normalized field/operator/value tuples
- `scope` – Scope of application
- `time_window` – Temporal constraint
- `affected_tables` – Database tables
- `affected_columns` – Column references
- `rule_family_id` – Groups equivalent rule representations
- `extraction_evidence` – Supporting rationale
- `per-field_confidence` – Confidence per extracted component

### Annotation Scheme
The training dataset uses the BIO (Begin-Inside-Outside) annotation format for token-level entity extraction:

| Label | Description | Example |
|-------|-------------|---------|
| BUSINESS_TERM | Business metric or concept | Revenue |
| OPERATION | Business operation | exclude |
| FIELD | Database field referenced by a rule | orders.status |
| VALUE | Value used by a condition | Cancelled |
| SCOPE | Scope of application | Finance region |
| TIME_WINDOW | Temporal constraint | current quarter |
| THRESHOLD | Numeric comparison value | 50000 |
| TABLE | Referenced database table | orders |
| COLUMN | Referenced database column | status |

**Condition Transformation Example:**
```
Natural Language: "Order Status is cancelled"
Extracted Spans: [FIELD: "orders.status"] [OPERATION: "equals"] [VALUE: "Cancelled"]
Normalized Rule: {"field": "orders.status", "operator": "EQUALS", "value": "Cancelled"}
```

### Deterministic Baseline
Before implementing ML models, a deterministic baseline is established using:
- Regular expressions
- Business dictionaries
- Domain glossary
- Schema metadata
- Predefined operation mappings
- Rule templates
- Linguistic patterns

### Operation Mappings
| Input Phrase | Normalized Operation |
|--------------|----------------------|
| exclude | EXCLUDE |
| do not include | EXCLUDE |
| include | INCLUDE |
| only | RESTRICT |
| greater than | GREATER_THAN |
| less than | LESS_THAN |
| equal to | EQUALS |

### Machine Learning Approach
**Model Candidate**: distilbert-base-uncased (treated as candidate, not production)

**Model Selection Process:**
```
Deterministic Baseline
        │
        ├──────────────┐
        ▼              ▼
   TF-IDF/Statistical  Transformer Candidate
        │              │
        └──────┬───────┘
               ▼
        Frozen Evaluation
               │
               ▼
       Model Promotion Gate
               │
       ┌───────┴────────┐
       ▼                ▼
   Candidate Pass    Candidate Fails
       │                │
       ▼                ▼
 APPROVED MODEL    Retain Baseline
```

**Model Lifecycle**: CANDIDATE → APPROVED → ACTIVE (only ACTIVE used for inference)

---

## 8.5 Schema Validation

### Validation Checks
The module verifies whether extracted entities and fields are valid within the active Domain Pack and workspace schema:

1. Business term existence
2. Table existence
3. Column existence
4. Field-to-table relationship
5. Valid operation for the identified field
6. Valid operator for the field type
7. Valid value type for the operator
8. Valid scope
9. Valid time window
10. Required rule components are present

### Validation Examples

**PASS Example:**
```json
{
  "business_term": "Revenue",
  "operation": "EXCLUDE",
  "condition": {"field": "orders.status", "operator": "EQUALS", "value": "Cancelled"}
}
// All schema elements valid → Status: PASS, Coverage: 1.0
```

**PARTIAL Example:**
```json
{
  "validated_fields": ["orders.status", "orders.customer_id"],
  "invalid_fields": ["orders.unknown_field"]
}
// Status: PARTIAL, Coverage: 0.75
```

**FAIL Example:**
```json
{
  "business_term": "Revenue",
  "condition": {"field": "orders.status", "operator": "EQUALS", "value": "Cancelled"}
}
// If orders.status doesn't exist in schema → Status: FAIL, Review: REQUIRED
```

### Mandatory Validation Failure
When a mandatory field cannot be validated:
- **Do NOT** attempt to automatically repair or invent missing schema information
- System marks the rule as requiring manual review or clarification
- Appropriate clarification generated if applicable

### Hard Manual-Review Conditions
Manual review is **mandatory** (cannot be overridden) when:
- Schema validation is FAIL
- Schema validation is PARTIAL for a mandatory component
- A mandatory rule field is missing
- Extraction confidence is below configured threshold
- Classification confidence is below configured threshold
- A rule is identified as sensitive
- A potential conflict is detected
- Duplicate modification relationships require reviewer verification
- System cannot reliably determine intended business operation

**Example:**
- Classification Confidence = 0.96
- Extraction Confidence = 0.94
- Schema Status = FAIL
- **Result**: Still routed to manual review (schema fail overrides high confidence)

### Schema Validation Output Format
```json
{
  "status": "PASS",
  "coverage": 1.0,
  "mandatory_fields_valid": true,
  "invalid_fields": [],
  "validation_errors": []
}
```

---

## 8.6 Duplicate Detection

### Two-Stage Process

**Stage 1 – Candidate Retrieval**
- Convert extracted rule to dense vector using Sentence-BERT (SBERT) embeddings
- Compare against previously extracted rules in the same workspace
- **Cosine Similarity IS used only to retrieve Top-K candidates**
- Similarity scores are NOT used for duplicate/final decision

**Stage 2 – Structured Rule Comparison**
Compare each candidate using standardized rule representation:

| Attribute | Comparison Logic |
|-----------|-----------------|
| Business Term | Exact / Semantic Match |
| Operation | Match / Mismatch |
| Conditions | Equivalent / Different |
| Scope | Same / Different |
| Time Window | Same / Different |
| Affected Fields | Match / Partial / Different |

### Relationship Types

| Relationship | Description |
|--------------|-------------|
| Exact Duplicate | Identical business meaning and structure |
| Semantic Duplicate | Different wording but equivalent business rule |
| Modification | Existing rule with changed values or conditions |
| Unique Rule | No matching rule identified |

### Implementation Stack
- **Sentence Embedding**: Sentence-BERT embeddings stored using pgvector
- **Vector Similarity**: Cosine Similarity
- **Vector Index**: PostgreSQL pgvector
- **Rule Comparator**: Custom Python Comparison Engine
- **API Framework**: FastAPI

### Evaluation Metrics
- Precision, Recall, F1 Score
- False Positive Rate, False Negative Rate
- Candidate Retrieval Recall (Top-K)

---

## 8.7 Conflict Detection

### Two-Stage Process

**Stage 1 – Candidate Rule Retrieval**
- Convert extracted rule to semantic embedding using SBERT
- Retrieve Top-K most semantically related active rules in same workspace
- Used ONLY for candidate identification, not for conflict decision

**Stage 2 – Structured Rule Comparison**

| Rule Component | Comparison Logic |
|----------------|-----------------|
| Business Term | Same or Different |
| Operation | Compatible or Contradictory |
| Conditions | Equivalent / Broader / Narrower / Different |
| Scope | Same / Overlapping / Independent |
| Time Window | Same / Overlapping |
| Threshold Values | Equal / Increased / Decreased / Conflicting |
| Affected Fields | Same / Partial / Different |

### Relationship Types
- **Compatible**: Rule can coexist with existing rule
- **Extension**: Adds additional conditions without contradiction
- **Modification**: Updates existing rule while preserving intent
- **Conflict**: Contradicts existing business logic

### Conflict Resolution Strategy
When potential conflict detected:
1. Store the extracted suggestion
2. Record conflicting rule identifiers
3. Generate structured comparison report
4. Route suggestion to manual review
5. Wait for reviewer approval before any further action

**Business rules are NEVER modified automatically.**

### Implementation Stack
- **Sentence Embeddings**: Sentence-BERT (SBERT)
- **Vector Search**: PostgreSQL pgvector
- **Rule Comparison Engine**: Custom Python Module
- **API Framework**: FastAPI
- **Data Store**: PostgreSQL

### Evaluation Metrics
- Precision, Recall, F1 Score
- Conflict Detection Accuracy
- False Conflict Rate, Missed Conflict Rate
- Conflict Classification Accuracy
- Scoped by: logical contradictions, threshold conflicts, scope conflicts, time-window conflicts, permission conflicts

### Key Design Principle
Semantic similarity is used **only** for retrieving candidate rules. Final conflict classification is based on structured comparison of business rule attributes, ensuring explainable and deterministic conflict decisions.

---

## 8.8 Completeness Check & Clarification Generation

### Never Infer Missing Business Information
Before generating the final suggestion, every required rule component is verified.

### Missing Information Handling

| Missing Information | System Action |
|---------------------|---------------|
| Table | Request clarification |
| Column | Request clarification |
| Metric | Request clarification |
| Threshold | Request clarification |
| Date Range | Request clarification |

### Example
```
Feedback: "Increase the threshold."

Generated clarification: 
"Which metric should be updated, and what should the new threshold value be?"

Clarified Feedback: "For Revenue metric, increase the threshold to $50,000"
```

### Clarification Storage
- Clarification requests and responses stored SEPARATELY
- Original feedback remains immutable
- New Analysis Run created after clarification response

---

## 8.9 Prediction Calibration and Decision Routing

### Independent Module Confidence
Each module produces its own confidence score (no weighted aggregation):

| Module | Confidence Produced |
|--------|---------------------|
| Classification | Classification Probability (Softmax) |
| Rule Extraction | Average token/entity confidence from NER |
| Schema Validation | Percentage of entities successfully validated |
| Duplicate Detection | Structured comparison confidence after retrieval |
| Conflict Detection | Confidence from rule comparison engine |

### Calibration Process
- Classification probabilities calibrated using validation dataset
- Temperature scaling evaluated for classification outputs
- Entity confidence aggregation calibrated for NER
- Final extraction confidence used for routing decisions

### Decision Rules for Review Routing

| Condition | System Action |
|-----------|---------------|
| Schema Validation Failed | **Mandatory** Manual Review |
| Mandatory Information Missing | Clarification Required |
| Low Classification Probability | Manual Review |
| Low Extraction Probability | Manual Review |
| Duplicate Detected | Reviewer Verification |
| Conflict Detected | Senior Reviewer |
| Sensitive Business Rule | Senior Reviewer |

### Routing Policy

| Condition | Queue |
|-----------|-------|
| Schema validation failed | Mandatory Manual Review |
| Missing mandatory fields | Clarification Required |
| Conflict detected | Senior Reviewer |
| Sensitive business rule | Senior Reviewer |
| Duplicate detected | Reviewer Verification |
| Normal validated suggestion | Standard Review |

---

## 8.10 Review Routing

### Basis for Reviewer Assignment
- Classification result
- Schema validation status
- Duplicate detection result
- Conflict detection result
- Clarification requirement
- Business sensitivity
- Duplicate status
- Conflict severity
- Clarification requirement (duplicate)
- Rule category
- Business sensitivity (duplicate)

### Output
Once routing is complete, the suggestion is persisted in the Suggestion Repository and a suggestion_id with the current processing status is returned to the client. Human review continues asynchronously through the separate review workflow.

---

## 8.11 Model Artifact and Version Management

### Storage Layout
```
/models/
    rule-extraction/
        v0.1/
        v0.2/
        v1.0/
    classification/
        v0.1/
        v0.2/
    duplicate-detection/
        v0.1/
```

### Model Version Metadata
Each model version records:
- Model name
- Model checkpoint
- Training dataset version
- Validation dataset version
- Annotation scheme version
- Hyperparameters
- Training timestamp
- Evaluation metrics
- Model status (CANDIDATE/APPROVED/ACTIVE)

---

## 8.12 Extraction Dataset Requirements

- Maintained separately from classification dataset
- Each example contains:
  - Original feedback text
  - BIO/BILOU token labels
  - Structured rule target
  - Business domain
  - Rule family ID
  - Expected conditions
  - Expected affected tables/columns
  - Multiple-rule indicator

- Split: Training (~600) / Validation (~150) / Frozen Evaluation (~200)
- Same rule_family_id examples kept within the same split
- Frozen test set NEVER used for training/tuning/selection

---

## 8.13 Evaluation Criteria

| Requirement | Target |
|-------------|--------|
| Classification Accuracy | ≥ 85% |
| Per-category F1 Score | ≥ 0.85 |
| Complete Rule Accuracy | ≥ 80% |
| Duplicate Precision | ≥ 90% |
| Duplicate Recall | ≥ 90% |
| Recall@K | ≥ 95% |
| Conflict Precision | ≥ 85% |
| Conflict Recall | ≥ 85% |
| Missed Conflict Rate | ≤ 5% |
| Calibration Error | ≤ 0.05 |

### Hard Requirements
- Workspace isolation tests: 100% Pass
- Idempotency tests: 100% Pass
- Background job retry tests: 100% Pass
- Baseline vs Candidate Model: Candidate must outperform baseline
- API Response Time: < 2 seconds (measured with specific hardware)
- Docker Deployment: Successful
- Manual Review Workflow: Functional