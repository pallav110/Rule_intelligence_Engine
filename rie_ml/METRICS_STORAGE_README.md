# Baseline Evaluation Metrics Storage System

Complete persistent storage and reporting system for Rule Intelligence Engine baseline model evaluation results.

## Overview

This system captures all baseline evaluation metrics according to the Phase 3/4 specification and stores them persistently on disk, allowing you to:

- ✅ **Store all evaluation results** — Classification, extraction, duplicate detection, conflict detection, clarification metrics
- ✅ **Compare baseline vs candidate models** — Track improvements and regressions
- ✅ **Query evaluation history** — Filter by model type, date range, or acceptance status
- ✅ **Generate reports** — HTML dashboards, JSON exports, text summaries
- ✅ **Track acceptance criteria** — Automatic validation against specification targets

## Directory Structure

```
rie_ml/
├── src/evaluation/
│   ├── __init__.py
│   └── metrics_storage.py         # Core storage and dataclass definitions
├── scripts/
│   ├── evaluate_baseline_with_storage.py    # Main evaluation script (stores results)
│   ├── view_metrics.py                       # Query and view stored metrics
│   └── generate_metrics_dashboard.py         # Generate HTML reports
└── datasets/evaluation/
    └── metrics/                   # Persistent storage directory
        ├── results/               # JSON evaluation results
        ├── summaries/             # Text summary reports
        ├── comparisons/           # Comparison analysis files
        └── dashboards/            # Generated HTML reports
```

## Usage

### 1. Run Baseline Evaluation (with automatic storage)

```bash
cd /home/spxlpt133/Desktop/Rule-intelligence-Engine/rie_ml

# Run evaluation on frozen dataset
python scripts/evaluate_baseline_with_storage.py

# Run with custom dataset split
python scripts/evaluate_baseline_with_storage.py --dataset validation

# Add notes to this evaluation
python scripts/evaluate_baseline_with_storage.py --notes "Testing after glossary improvements"
```

**Output:**
- JSON result file → `datasets/evaluation/metrics/results/baseline_<timestamp>_<id>.json`
- Text summary → `datasets/evaluation/metrics/summaries/baseline_<timestamp>_<id>_summary.txt`
- Console report with all metrics displayed

### 2. View Stored Metrics

```bash
# List all evaluations (latest 20)
python scripts/view_metrics.py

# View specific evaluation
python scripts/view_metrics.py --id baseline_1693543792_a1b2c3d4

# Filter by model type
python scripts/view_metrics.py --model baseline_deterministic

# Show recent evaluations summary
python scripts/view_metrics.py --summary

# Compare two evaluations
python scripts/view_metrics.py --compare baseline_1693543792_a1b2c3d4 baseline_1693543800_b2c3d4e5
```

### 3. Generate HTML Reports

```bash
# Generate report for specific evaluation
python scripts/generate_metrics_dashboard.py --id baseline_1693543792_a1b2c3d4

# Generate comparison dashboard
python scripts/generate_metrics_dashboard.py --compare baseline_1693543792_a1b2c3d4 baseline_1693543800_b2c3d4e5

# Generate historical dashboard
python scripts/generate_metrics_dashboard.py --history

# Include all historical data
python scripts/generate_metrics_dashboard.py --history --all
```

**Output:** HTML files saved to `datasets/evaluation/metrics/dashboards/`

## Metrics Captured

### Classification Metrics
- **Accuracy** — Overall classification accuracy
- **Precision** — Per-category precision scores
- **Recall** — Per-category recall scores
- **F1 Score** — Per-category F1 scores (≥ 0.85 target)
- **Calibration Error** — Confidence calibration error (≤ 0.05 target)
- **Confusion Matrix** — Per-category classification breakdown

### Rule Extraction Metrics
- **Business Term** — Precision, Recall, F1 (target: ≥ 0.80)
- **Operation** — Precision, Recall, F1
- **Conditions** — Precision, Recall, F1
- **Scope** — Precision, Recall, F1
- **Time Window** — Precision, Recall, F1
- **Affected Entities** — Precision, Recall, F1
- **Threshold** — Precision, Recall, F1
- **Exact Rule Match Rate** — % of completely correct extractions
- **Schema Validation Pass Rate** — % of schema-valid extractions

### Duplicate Detection Metrics
- **Precision** — (target: ≥ 90%)
- **Recall** — (target: ≥ 90%)
- **F1 Score**
- **Recall@K** — (target: ≥ 95%)
- **False Positive Rate** — FP / (FP + TN)
- **False Negative Rate** — FN / (FN + TP)
- **Exact Duplicates** — Separate precision/recall
- **Semantic Duplicates** — Separate precision/recall

### Conflict Detection Metrics
- **Precision** — (target: ≥ 85%)
- **Recall** — (target: ≥ 85%)
- **F1 Score**
- **Accuracy**
- **False Conflict Rate** — % false positives (target: ≤ 5%)
- **Missed Conflict Rate** — % false negatives (target: ≤ 5%)
- **Per-Conflict-Type Metrics:**
  - Logical contradictions
  - Threshold conflicts
  - Scope conflicts
  - Time-window conflicts
  - Permission conflicts

### Clarification Metrics
- **Detection Precision** — Correct clarification requests
- **Detection Recall** — % of actual ambiguous cases caught
- **Detection F1 Score**
- **Missed Clarification Cases** — Count
- **Incorrect Clarification Requests** — False positives
- **Average Resolution Time** — Seconds

### Performance Metrics
- **Average Processing Time** — < 2 seconds target

## Acceptance Criteria

Each evaluation is automatically checked against acceptance criteria:

| Component | Target | Stored As |
|-----------|--------|-----------|
| Classification Accuracy | ≥ 85% | `result.classification.accuracy` |
| Per-category F1 Score | ≥ 0.85 | `result.classification.f1_score[category]` |
| Complete Rule Accuracy | ≥ 80% | `result.extraction.exact_rule_match_rate` |
| Duplicate Precision | ≥ 90% | `result.duplicate_detection.precision` |
| Duplicate Recall | ≥ 90% | `result.duplicate_detection.recall` |
| Recall@K | ≥ 95% | `result.duplicate_detection.recall_at_k` |
| Conflict Precision | ≥ 85% | `result.conflict_detection.precision` |
| Conflict Recall | ≥ 85% | `result.conflict_detection.recall` |
| Missed Conflict Rate | ≤ 5% | `result.conflict_detection.missed_conflict_rate` |
| Calibration Error | ≤ 0.05 | `result.classification.calibration_error` |
| API Response Time | < 2s | `result.average_processing_time_seconds` |

## Data Structures

### BaselineEvaluationResult

```python
@dataclass
class BaselineEvaluationResult:
    evaluation_id: str                          # Unique ID
    timestamp: str                              # ISO format timestamp
    model_type: str                             # "baseline_deterministic", "ml_candidate", etc.
    model_version: str                          # Semantic version
    dataset_split: str                          # "frozen_evaluation", "validation"
    dataset_size: int                           # Number of samples evaluated
    classification: ClassificationMetrics       # See below
    extraction: ExtractionMetrics                # See below
    duplicate_detection: DuplicateDetectionMetrics
    conflict_detection: ConflictDetectionMetrics
    clarification: ClarificationMetrics
    average_processing_time_seconds: float
    notes: str                                  # Optional user notes
    acceptance_criteria_passed: bool            # Automatic pass/fail
```

### Stored JSON Format

Results are stored as JSON with full metric details:

```json
{
  "evaluation_id": "baseline_1693543792_a1b2c3d4",
  "timestamp": "2026-09-01T06:42:06Z",
  "model_type": "baseline_deterministic",
  "model_version": "1.0",
  "dataset_split": "frozen_evaluation",
  "dataset_size": 200,
  "classification": {
    "accuracy": 0.875,
    "precision": { "metric_definition": 0.92, "filter_rule": 0.85 },
    "recall": { "metric_definition": 0.88, "filter_rule": 0.82 },
    "f1_score": { "metric_definition": 0.90, "filter_rule": 0.835 },
    "calibration_error": 0.0234,
    "total_samples": 200,
    "correct_predictions": 175
  },
  "extraction": {
    "business_term_precision": 0.92,
    "business_term_recall": 0.90,
    "business_term_f1": 0.91,
    "operation_precision": 0.95,
    "operation_recall": 0.93,
    "operation_f1": 0.94,
    ...
  },
  "duplicate_detection": { ... },
  "conflict_detection": { ... },
  "clarification": { ... },
  "average_processing_time_seconds": 0.0234,
  "notes": "",
  "acceptance_criteria_passed": true
}
```

## Comparison & Analysis

### Compare Two Evaluations

```python
from rie_ml.src.evaluation.metrics_storage import MetricsStorage

storage = MetricsStorage()
comparison = storage.compare_results("baseline_id_1", "baseline_id_2")

# Returns dict with:
# - improvements: metrics that got better
# - regressions: metrics that got worse
# - overall_improvement: boolean
```

### Query Interface

```python
# List all results
results = storage.list_results(limit=20)
results = storage.list_results(model_type="baseline_deterministic", limit=50)

# Load specific result
result = storage.load_result("baseline_1693543792_a1b2c3d4")

# Save summary report
report_file = storage.save_summary_report(result)

# Save comparison
comparison_file = storage.save_comparison(comparison)
```

## Integration with Training Pipeline

### Training Script Integration

Update `rie_ml/scripts/train_baseline_unified.py` to track model metrics:

```python
from rie_ml.src.evaluation.metrics_storage import MetricsStorage

# After training
storage = MetricsStorage()

# Run evaluation on training results
result = run_evaluation()  # Your evaluation function

# Store automatically
storage.save_result(result)
storage.save_summary_report(result)
```

## Files Created

- ✅ `rie_ml/src/evaluation/__init__.py` — Empty init
- ✅ `rie_ml/src/evaluation/metrics_storage.py` — Core storage system
- ✅ `rie_ml/scripts/evaluate_baseline_with_storage.py` — Main evaluation script
- ✅ `rie_ml/scripts/view_metrics.py` — Query and view metrics
- ✅ `rie_ml/scripts/generate_metrics_dashboard.py` — HTML report generation

## Next Steps

1. **Run baseline evaluation:** `python scripts/evaluate_baseline_with_storage.py`
2. **View stored results:** `python scripts/view_metrics.py --summary`
3. **Generate HTML report:** `python scripts/generate_metrics_dashboard.py --history`
4. **Compare models:** Train ML model, evaluate, then compare with baseline
5. **Track improvements:** Each evaluation is automatically validated against acceptance criteria

## Notes

- All results are stored persistently in `datasets/evaluation/metrics/`
- Evaluation IDs include timestamp for uniqueness and sorting
- Acceptance criteria checking is automatic
- HTML dashboards are self-contained (single file, no external dependencies)
- Results can be loaded back into Python for custom analysis
