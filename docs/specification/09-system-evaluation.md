# Section 9: System Evaluation and Performance Measurement

## 9.1 Evaluation Dataset

The Rule Intelligence Engine (RIE) is evaluated using a manually reviewed benchmark dataset containing synthetic feedback generated across multiple business domains. Evaluation is performed independently for each processing module to identify strengths and weaknesses rather than relying on a single overall accuracy value.

The evaluation process compares the deterministic baseline with candidate machine learning models using identical frozen evaluation datasets. Candidate models are promoted only after demonstrating measurable improvements over the deterministic baseline according to the predefined acceptance criteria.

| Dataset | Size | Purpose |
|---------|------|---------|
| Training | ~600 | Model Training |
| Validation | ~150 | Hyperparameter tuning and confidence calibration |
| Frozen Evaluation | ~200 | Final evaluation |
| Duplicate Pairs | ~150 | Duplicate detection evaluation |
| Conflict Pairs | ~150 | Conflict detection evaluation |
| Ambiguous Feedback | ~100 | Clarification evaluation |

The frozen evaluation dataset is never used during model training, validation, or hyperparameter tuning to ensure unbiased performance measurement. All expected outputs are manually verified to establish a reliable ground truth for performance comparison.

## 9.2 Classification Evaluation

The classification module is evaluated independently using:
- Accuracy
- Precision
- Recall
- F1 Score
- Calibration Error
- Confusion Matrix

Performance is measured separately for each supported feedback category rather than reporting only an overall accuracy.

Example categories include:
- Metric Definition
- Filter Rule
- Mapping Rule
- Join Rule
- Access Rule
- Data Quality Issue
- General Product Feedback

## 9.3 Rule Extraction Evaluation

Rule extraction quality is evaluated independently for each component of the structured rule representation. Instead of measuring only whether an entire rule was extracted correctly, the system measures the accuracy of each individual field.

The following fields are evaluated separately:
- Business Term
- Operation
- Normalized Conditions (Field, Operator, Value)
- Scope
- Time Window
- Affected Tables and Columns
- Threshold Values

The following evaluation metrics are recorded:
- Field-level Precision
- Field-level Recall
- Field-level F1 Score
- Exact Rule Match Rate
- Schema Validation Pass Rate

Each extracted field is compared against the manually annotated ground truth to identify which parts of the extraction pipeline require improvement.

## 9.4 Duplicate Detection Evaluation

Duplicate detection performance is evaluated using labelled duplicate pairs.

Evaluation metrics include:
- Precision
- Recall
- F1 Score
- Recall@K
- False Positive Rate
- False Negative Rate

Performance is measured separately for:
- Exact duplicates
- Semantic duplicates

## 9.5 Conflict Detection Evaluation

Conflict detection is evaluated using manually labelled conflicting business rules.

Evaluation metrics include:
- Precision
- Recall
- F1 Score
- Conflict Detection Accuracy
- False Conflict Rate
- Missed Conflict Rate
- Conflict Classification Accuracy
- Missed Conflict Rate (note: duplicated in source, but we keep as is)

Performance is measured separately for different conflict categories, including:
- Logical contradictions
- Threshold conflicts
- Scope conflicts
- Time-window conflicts
- Permission conflicts

The False Conflict Rate measures the percentage of valid business rules that are incorrectly identified as conflicts. A lower False Conflict Rate reduces unnecessary manual review effort.

## 9.6 Clarification Evaluation

Since the system never infers missing business information, clarification generation is evaluated as an independent task.

The evaluation measures:
- Clarification Detection Precision
- Clarification Detection Recall
- Clarification Detection F1 Score
- Missed Clarification Cases
- Incorrect Clarification Requests
- Average Clarification Resolution Time

A clarification request is considered correct only when the submitted feedback genuinely lacks sufficient information for rule generation. False clarification requests are also tracked to minimize unnecessary reviewer intervention.

## 9.7 Baseline vs Machine Learning Comparison

Both the deterministic baseline and the machine learning pipeline are evaluated using identical datasets.

| Metric | Deterministic Baseline | Candidate ML Model |
|--------|------------------------|--------------------|
| Classification Accuracy | Measured | Measured |
| Per-category F1 Score | Measured | Measured |
| Complete Rule Accuracy | Measured | Measured |
| Duplicate Precision | Measured | Measured |
| Duplicate Recall | Measured | Measured |
| Recall@K | Measured | Measured |
| Conflict Precision | Measured | Measured |
| Conflict Recall | Measured | Measured |
| Calibration Error | Measured | Measured |
| Average Processing Time | Measured | Measured |

Both approaches are evaluated using the same frozen evaluation dataset. Candidate machine learning models are promoted only if they demonstrate measurable improvements over the deterministic baseline while satisfying the predefined acceptance criteria. Thresholds for semantic candidate retrieval, structured duplicate detection, and structured conflict detection are finalized through empirical evaluation using the validation dataset.

## 9.8 Acceptance Criteria

The initial project will be considered successful if it satisfies the following measurable goals:

| Component | Target |
|-----------|--------|
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
| Workspace Isolation Tests | 100% Pass |
| Idempotency Tests | 100% Pass |
| Background Job Retry Tests | 100% Pass |
| Baseline vs Candidate Model Promotion | Candidate model must outperform the deterministic baseline |
| Average API Response Time | < 2 seconds* |
| Docker Deployment | Successful |
| Manual Review Workflow | Functional |

*The response time target is measured using CPU-based inference on an Intel Core i7-class processor with 16 GB RAM, using the distilbert-base-uncased checkpoint, a maximum feedback length of 256 tokens, single-request processing, and a concurrency level of 10 simultaneous requests.