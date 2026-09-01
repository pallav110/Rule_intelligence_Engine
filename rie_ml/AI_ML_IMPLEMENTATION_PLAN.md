# AI/ML Implementation Plan - DistilBERT Fine-tuning

**Status:** Planning Phase
**Date:** 2026-09-01
**Goal:** Train and evaluate DistilBERT candidate model vs deterministic baseline

---

## Phase Overview

According to specification Section 8.3.2 and 11.1, we need to:
1. Fine-tune `distilbert-base-uncased` for multi-task classification
2. Evaluate on frozen evaluation dataset
3. Compare against deterministic baseline
4. Promote only if candidate outperforms baseline

---

## Current State

### ✅ What We Have

**Datasets (Specification-Compliant):**
- Training: 922 examples (301 CS + 319 EC + 302 SAAS)
- Validation: 196 examples (64 CS + 68 EC + 64 SAAS)
- Test/Frozen Eval: test.jsonl files per domain
- Specialized: classification.jsonl, extraction.jsonl, duplicate_pairs.jsonl

**Baseline:**
- TF-IDF + Logistic Regression: 100% accuracy on frozen eval
- Model: `rie_ml/models/baseline_classifier_unified.pkl`
- Metrics storage system operational

**Evaluation Infrastructure:**
- Metrics storage: `rie_ml/src/evaluation/metrics_storage.py`
- Evaluation script: `rie_ml/scripts/evaluate_baseline_with_storage.py`
- All 8 acceptance criteria tracked

### ❌ What We Need

**AI/ML Components:**
1. DistilBERT fine-tuning script
2. Multi-task classification head
3. Training pipeline (transformers + PyTorch)
4. Model checkpointing and versioning
5. Candidate model evaluation
6. Baseline vs candidate comparison

---

## Implementation Tasks

### Task 1: Prepare Combined Training Dataset
**Location:** `rie_ml/scripts/prepare_ml_training_data.py`

**Actions:**
- Combine train.jsonl from all 3 domains
- Extract labels: feedback_type, rule_category, is_actionable, requires_clarification
- Create balanced splits (if needed)
- Save to: `rie_ml/datasets/ml_training/train_combined.jsonl`

**Output Format:**
```json
{
  "text": "Revenue should exclude cancelled orders",
  "labels": {
    "feedback_type": "business_rule_correction",
    "rule_category": "calculation_correction",
    "is_actionable": true,
    "requires_clarification": false
  },
  "domain": "ecommerce"
}
```

### Task 2: Create Multi-Task DistilBERT Classifier
**Location:** `rie_ml/src/ml_models/distilbert_classifier.py`

**Architecture:**
```
DistilBERT (distilbert-base-uncased)
    ↓
Pooled Output [CLS token]
    ↓
├─ Feedback Type Head (Softmax)
├─ Rule Category Head (Softmax)
├─ Is Actionable Head (Sigmoid)
└─ Requires Clarification Head (Sigmoid)
```

**Specifications (from docs):**
- Model: `distilbert-base-uncased`
- Tokenizer: `DistilBertTokenizerFast`
- Max sequence length: 256 tokens
- Batch size: 16
- Optimizer: AdamW
- Learning rate: 2e-5
- Hardware: CPU inference, optional GPU training

**Key Classes:**
```python
class MultiTaskDistilBERTClassifier(nn.Module):
    def __init__(self, num_feedback_types, num_rule_categories):
        self.distilbert = DistilBertModel.from_pretrained('distilbert-base-uncased')
        self.feedback_type_head = nn.Linear(768, num_feedback_types)
        self.rule_category_head = nn.Linear(768, num_rule_categories)
        self.is_actionable_head = nn.Linear(768, 1)
        self.requires_clarification_head = nn.Linear(768, 1)
```

### Task 3: Training Script
**Location:** `rie_ml/scripts/train_distilbert_classifier.py`

**Training Pipeline:**
1. Load combined training data
2. Initialize DistilBERT with multi-task heads
3. Define multi-task loss (weighted combination):
   - Feedback type: CrossEntropyLoss
   - Rule category: CrossEntropyLoss
   - Is actionable: BCEWithLogitsLoss
   - Requires clarification: BCEWithLogitsLoss
4. Train with early stopping (validation loss)
5. Save checkpoints every epoch
6. Log training metrics (loss per task, accuracy)

**Key Parameters:**
```python
config = {
    "model_name": "distilbert-base-uncased",
    "max_length": 256,
    "batch_size": 16,
    "learning_rate": 2e-5,
    "num_epochs": 10,
    "early_stopping_patience": 3,
    "weight_decay": 0.01,
    "warmup_steps": 100,
}
```

**Output:**
- Trained model: `rie_ml/models/distilbert_classifier_candidate.pt`
- Training log: `rie_ml/models/training_log.json`
- Checkpoints: `rie_ml/models/checkpoints/epoch_*.pt`

### Task 4: Candidate Model Evaluation Script
**Location:** `rie_ml/scripts/evaluate_distilbert_candidate.py`

**Actions:**
1. Load trained DistilBERT model
2. Load frozen evaluation dataset (test.jsonl from all domains)
3. Run predictions on each example
4. Compute metrics:
   - Overall accuracy
   - Per-category precision/recall/F1
   - Calibration error
   - Confusion matrix
5. Store results using existing `metrics_storage.py`

**Integration with Existing System:**
```python
from rie_ml.src.evaluation.metrics_storage import (
    MetricsStorage,
    BaselineEvaluationResult,
    ClassificationMetrics
)

# Evaluate candidate
result = evaluate_distilbert_on_frozen_eval()

# Store with metrics storage
storage = MetricsStorage()
storage.save_result(result)
```

### Task 5: Baseline vs Candidate Comparison
**Location:** `rie_ml/scripts/compare_baseline_vs_candidate.py`

**Actions:**
1. Load baseline evaluation results
2. Load candidate evaluation results
3. Compare metrics side-by-side
4. Generate comparison report
5. Determine if candidate should be promoted

**Promotion Criteria (from Section 9.8):**
- Classification Accuracy: ≥ 85%
- Per-category F1 Score: ≥ 0.85
- Candidate must **outperform** baseline
- Calibration Error: ≤ 0.05

**Output:**
- Comparison JSON: `rie_ml/datasets/evaluation/metrics/comparisons/baseline_vs_candidate.json`
- Promotion decision: `rie_ml/models/promotion_decision.json`

### Task 6: Model Registry and Versioning
**Location:** `rie_ml/src/ml_models/model_registry.py`

**Track:**
- Model name and version
- Training dataset version
- Hyperparameters
- Evaluation metrics
- Training timestamp
- Status: CANDIDATE / APPROVED / ACTIVE

**Schema:**
```python
{
    "model_id": "distilbert_v1.0",
    "model_type": "ml_candidate",
    "checkpoint_path": "models/distilbert_classifier_candidate.pt",
    "training_dataset_version": "v1.0",
    "hyperparameters": {...},
    "evaluation_metrics": {...},
    "status": "CANDIDATE",
    "trained_at": "2026-09-01T07:00:00Z"
}
```

---

## Acceptance Criteria

From specification Section 9.8:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Classification Accuracy | ≥ 85% | Overall correct predictions / total |
| Per-category F1 | ≥ 0.85 | F1 for each feedback type and rule category |
| Calibration Error | ≤ 0.05 | Temperature scaling validation |
| Baseline Comparison | Must outperform | Candidate metrics > Baseline metrics |

---

## Implementation Order

1. ✅ **Prepare combined training dataset** (30 min)
2. ✅ **Create multi-task DistilBERT classifier** (2 hours)
3. ✅ **Implement training script** (2 hours)
4. ✅ **Train model** (1-2 hours depending on hardware)
5. ✅ **Evaluate candidate on frozen eval** (30 min)
6. ✅ **Compare baseline vs candidate** (30 min)
7. ✅ **Model registry and versioning** (1 hour)

**Total estimated time:** 8-9 hours

---

## Dependencies

**Python Packages (add to requirements.txt):**
```
transformers==4.35.0
torch==2.1.0
datasets==2.14.0
scikit-learn==1.3.0
accelerate==0.24.0
```

**Hardware:**
- Training: GPU recommended (CUDA), fallback to CPU
- Inference: CPU (per specification)

---

## Success Criteria

✅ DistilBERT model trained successfully
✅ Evaluation metrics stored in metrics storage system
✅ Comparison report generated
✅ Candidate achieves ≥85% accuracy
✅ Candidate outperforms baseline (if applicable)
✅ Model registry tracks all versions

---

## Next Steps

1. Start with Task 1: Prepare combined training dataset
2. Validate dataset format and label distribution
3. Proceed to Task 2: Implement multi-task DistilBERT classifier
4. Continue sequentially through tasks

**Ready to begin?** Start with `prepare_ml_training_data.py`
