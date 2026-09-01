# AI/ML Implementation Compliance Checklist
**Date:** 2026-09-01  
**Status:** Pre-Training Verification

---

## Section 8.3.2: Classification Model Requirements

### ✅ What We've Implemented Correctly

| Requirement | Specification | Our Implementation | Status |
|-------------|--------------|-------------------|--------|
| Model Checkpoint | `distilbert-base-uncased` | ✅ `distilbert-base-uncased` | **PASS** |
| Task Type | Multi-task classification | ✅ 4 independent heads | **PASS** |
| Outputs | Feedback Type, Rule Category, Actionable, Clarification | ✅ All 4 outputs | **PASS** |
| Max Sequence Length | 256 tokens | ✅ 256 tokens | **PASS** |
| Batch Size | 16 | ✅ 16 | **PASS** |
| Optimizer | AdamW | ✅ AdamW | **PASS** |
| Learning Rate | 2e-5 | ✅ 2e-5 | **PASS** |
| Training Split | 70% train, 15% val, 15% test | ✅ 922 train (~70%), 196 val (~15%), 201 test (~15%) | **PASS** |
| Frozen Test Set | Never used in training | ✅ Separate test.jsonl per domain | **PASS** |
| Label Independence | Not combined into single score | ✅ 4 independent losses | **PASS** |

### ❌ What's Missing - CRITICAL

| Requirement | Specification | Our Implementation | Action Needed |
|-------------|--------------|-------------------|---------------|
| **Input Preprocessing** | "Lowercase → Tokenization → Attention Mask → Tokenizer Encoding" | ❌ We skip lowercase (DistilBERT handles it) | **VERIFY: Is this okay?** |
| **Output Format** | Must include `classification_probability` field (0.96 in example) | ❌ We return logits/probs but not single classification_probability | **FIX: Add max probability extraction** |
| **Calibration** | "Classification probabilities are calibrated before downstream decision making" | ❌ Not implemented yet (Task #42) | **BLOCK: Must calibrate before eval** |
| **Evaluation Metrics** | Accuracy, Precision, Recall, Macro F1, Weighted F1, Per-category F1, Confusion Matrix | ❌ Only basic metrics in training loop | **FIX: Add comprehensive eval** |
| **Model Registry** | Status: CANDIDATE → APPROVED → ACTIVE | ❌ Not implemented (Task #45) | **REQUIRED** |
| **Workspace Context** | Input includes `{"workspace":"Finance", "feedback":"..."}` | ❌ We don't use workspace_id during training | **VERIFY: Needed for training?** |

---

## Section 8.4: Rule Extraction (Future - NOT NOW)

### ✅ Correctly Separated

| What We're NOT Doing (Correctly) | Why | Status |
|----------------------------------|-----|--------|
| Rule Extraction | Section 8.4 is a **separate model** (BIO token classification) | ✅ **CORRECT** - We're only doing classification now |
| NER Model | distilbert-base-uncased with token classification head | ✅ **NOT IMPLEMENTED** - Future phase |
| Rule Builder | Converts extracted entities to canonical JSON | ✅ **NOT IMPLEMENTED** - Future phase |

**IMPORTANT:** Section 8.4 describes a **completely different model** for extraction. We are correctly implementing ONLY the classification model (8.3.2) first.

---

## Section 8.5-8.10: Downstream Modules (Not Training-Related)

These sections describe inference-time modules:
- ✅ Schema Validation (already exists as baseline)
- ✅ Duplicate Detection (already exists as baseline with SBERT)
- ✅ Conflict Detection (already exists as baseline with SBERT)
- ✅ Clarification Generation (already exists)
- ✅ Review Routing (already exists)

**NOT PART OF TRAINING.** These are used during inference after the classifier is trained.

---

## CRITICAL GAPS - Must Fix Before Training

### 1. ❌ Calibration (HIGH PRIORITY)

**Specification:**
> "Classification probabilities are calibrated before downstream decision making"

**Current State:** Not implemented

**Action:** We MUST implement calibration (Task #42) and re-run evaluation with calibrated probabilities

**Fix:**
```python
# After training, calibrate on validation set
from sklearn.calibration import CalibratedClassifierCV
# Implement temperature scaling or Platt scaling
```

---

### 2. ❌ Comprehensive Evaluation Metrics (HIGH PRIORITY)

**Specification Requires:**
- Accuracy ✅ (we have this)
- Precision (per-category) ❌
- Recall (per-category) ❌
- Macro F1 ❌
- Weighted F1 ❌
- Per-category F1 ❌
- Confusion Matrix ❌

**Current State:** We only track loss during training

**Fix:** Create comprehensive evaluation script with all metrics

---

### 3. ❌ Output Format (MEDIUM PRIORITY)

**Specification Example:**
```json
{
  "feedback_type": "Business Rule",
  "rule_category": "Metric Definition",
  "actionable": true,
  "clarification_required": false,
  "classification_probability": 0.96
}
```

**Current State:** We return separate probabilities per task, not a single `classification_probability`

**Question:** What should `classification_probability` be?
- Average of all 4 task confidences?
- Minimum of all 4 task confidences?
- Feedback type confidence only?

**Action:** Clarify specification interpretation

---

### 4. ❌ Model Lifecycle (MEDIUM PRIORITY)

**Specification:**
> Model lifecycle: CANDIDATE → APPROVED → ACTIVE

**Current State:** No model registry

**Fix:** Implement Task #45 (Model Registry)

---

## Pre-Training Checklist

### ✅ Ready to Train

- [x] Dataset validated (922 train, 196 val, 201 test)
- [x] Multi-task DistilBERT model implemented
- [x] 4 independent prediction heads
- [x] Training pipeline with early stopping
- [x] Checkpoint saving
- [x] Label mappings defined
- [x] No rule_family leakage

### ❌ Must Fix BEFORE Frozen Evaluation

- [ ] Implement calibration on validation set
- [ ] Add comprehensive evaluation metrics (precision, recall, F1 per-category, confusion matrix)
- [ ] Define `classification_probability` output format
- [ ] Implement model registry with CANDIDATE/APPROVED/ACTIVE status

### ⚠️ Clarifications Needed

1. **Preprocessing:** Spec shows "Lowercase" as first step, but distilbert-base-uncased handles lowercasing internally. Should we manually lowercase input text?

2. **classification_probability:** Spec shows single probability (0.96) in output. Should this be:
   - Max probability across all 4 tasks?
   - Feedback type probability only?
   - Geometric mean of all 4 probabilities?

3. **Workspace Context:** Spec shows `{"workspace":"Finance", ...}` in input. Should workspace_id be:
   - Encoded as additional input feature during training?
   - Only used during inference for routing?
   - Ignored for classification model?

---

## Decision: Can We Train Now?

### YES, We Can Start Training Now ✅

**Reasons:**
1. Core model architecture is specification-compliant
2. Dataset is validated and ready
3. Training pipeline implements all required hyperparameters
4. Missing items (calibration, comprehensive metrics) can be added POST-training

### But We CANNOT Evaluate on Frozen Test Yet ❌

**Blockers:**
1. Must implement calibration first (Task #42)
2. Must implement comprehensive metrics (precision, recall, F1, confusion matrix)
3. Must clarify `classification_probability` output format

---

## Proposed Workflow

### Phase 1: Train Model (NOW)
```bash
python scripts/train_distilbert_classifier.py
```
**Output:** Best model checkpoint saved

### Phase 2: Post-Training Setup (AFTER TRAINING)
1. Implement calibration on validation set
2. Implement comprehensive evaluation script
3. Clarify specification questions

### Phase 3: Frozen Evaluation (ONLY AFTER PHASE 2)
1. Run comprehensive evaluation on test.jsonl
2. Compare vs baseline
3. Generate promotion decision

---

## Summary

**What We Have:** ✅ Specification-compliant training setup
**What We're Missing:** ❌ Post-training calibration & comprehensive evaluation
**Can We Train Now:** ✅ YES
**Can We Evaluate on Frozen Test:** ❌ NO (must implement calibration first)

**Recommendation:** 
1. START TRAINING NOW
2. While training runs, implement calibration & evaluation scripts
3. After training completes, calibrate then evaluate

---

## Questions for User

1. Should we **start training now** and fix calibration/metrics after?
2. Or should we **implement calibration first** before training?
3. How should we define `classification_probability` (single output value)?

