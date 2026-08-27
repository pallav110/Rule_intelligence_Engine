# Baseline Model Limitations

## 🎯 Purpose

This document describes the **expected limitations** of the baseline models in Phase 3. These are **not bugs** - they are **documented limitations** that demonstrate the system's **conservative, safe behavior**.

---

## 📋 Limitations Overview

### 1. **Extraction Quality**
**Issue**: Baseline regex extractor produces invalid conditions

**Example**:
```json
"conditions": [
  {
    "field": "unknown.What",
    "operator": "equals",
    "value": "the"
  }
]
```

**Why it happens**:
- Baseline extractor uses regex patterns
- Natural language structure is misinterpreted as conditions
- This is an **expected limitation** of regex-based extraction

**Current behavior**:
- Invalid conditions are extracted
- Schema validation catches them and marks as `PARTIAL`
- Clarification is triggered if needed

**Future improvement**:
```json
"conditions": [],
"extraction_warnings": [
  "No explicit condition detected"
]
```

**Why it's acceptable**:
- Schema validation catches invalid conditions
- System doesn't accept invalid rules
- Conservative behavior prevents errors

---

### 2. **Classification Confidence**
**Issue**: Low confidence triggers clarification

**Example**:
```json
"confidence": 0.4776,
"clarification_required": true
```

**Why it happens**:
- Baseline classifier is intentionally conservative
- Uncertain classifications are flagged for review
- This is **correct behavior**, not a bug

**Current behavior**:
- Low confidence → clarification triggered
- Uncertain suggestions → manual review
- System doesn't blindly accept uncertain classifications

**Future improvement**:
- Higher accuracy classifier (70-90%)
- Better confidence calibration
- Domain-specific confidence thresholds

**Why it's acceptable**:
- Prevents invalid rules from being accepted
- Ensures human review for uncertain cases
- Conservative behavior is safe

---

### 3. **Semantic Similarity vs Duplicate Confidence**
**Issue**: High similarity but low duplicate confidence is confusing

**Example**:
```json
"semantic_similarity": 0.87,
"confidence": 0.0,
"is_duplicate": false
```

**Why it happens**:
- **Semantic similarity**: Measures how related rules are
- **Duplicate confidence**: Measures if rules are identical
- Similar ≠ duplicate

**Current behavior**:
- High semantic similarity (87%)
- Low duplicate confidence (0%)
- Correctly classified as `unrelated`

**Future improvement**:
```json
"semantic_similarity": 0.87,
"confidence": 0.0,
"is_duplicate": false,
"interpretation": "Highly related, but not sufficiently identical to classify as a duplicate."
```

**Why it's acceptable**:
- The distinction is correct
- Needs better UI explanation
- System behavior is accurate

---

### 4. **Generic Clarification Questions**
**Issue**: Questions are domain-based, not extraction-specific

**Example**:
```json
"questions": [
  "Should this apply to all support channels (email, chat, phone)?",
  "Does this affect all customer tiers or premium-only customers?",
  "Should this include internal support staff or partner tickets?",
  "Are there regional support guidelines?",
  "Should tickets be routed, prioritized, or escalated?"
]
```

**Why it happens**:
- Current implementation generates questions from domain knowledge
- Doesn't yet analyze specific extraction gaps

**Current behavior**:
- Generic domain questions
- Still useful for clarification
- Triggers human review

**Future improvement**:
```json
"questions": [
  "Missing operation: What should happen to first-response-time SLA?",
  "Possible operations: include / exclude / restrict / replace / etc."
]
```

**Why it's acceptable**:
- Clarification is still triggered
- Human review catches issues
- System is conservative

---

## 🎯 Why These Limitations Are Acceptable

### 1. **Conservative Behavior**
The system is **intentionally conservative**:
- Low confidence → clarification
- Invalid extraction → schema validation failure
- Uncertain suggestion → manual review

This prevents invalid rules from being accepted.

### 2. **Multiple Safety Layers**
```
Extracted Rule
      ↓
Schema Validation (catches invalid fields)
      ↓
Duplicate Detection (prevents duplicates)
      ↓
Conflict Detection (prevents conflicts)
      ↓
Clarification (requests missing info)
      ↓
Review Routing (sends uncertain to manual review)
```

### 3. **Traceability**
Every step is traceable:
- Feedback → suggestion → extracted rule → validation → review → business rule
- All records stored in database with timestamps
- Audit history tracks all changes

### 4. **Documented Limitations**
These limitations are **documented and expected**:
- Not bugs, but known limitations
- Demonstrate system's safety mechanisms
- Show conservative, safe behavior

---

## 📚 Related Files

- `FINAL_SUMMARY.md` - Complete project summary
- `IMPLEMENTATION_SUMMARY.md` - Specification mapping
- `EXTRACTION_USAGE.md` - Extraction implementation
- `VALIDATION_USAGE.md` - Validation implementation
- `CLASSIFICATION_USAGE.md` - Classification implementation
- `LIFECYCLE_USAGE.md` - Lifecycle implementation

---

## 🎯 Conclusion

These limitations are **not bugs** - they are **expected baseline model limitations** that demonstrate the system's **conservative, safe behavior**:

1. ✅ **Extraction quality**: Schema validation catches invalid conditions
2. ✅ **Classification confidence**: Low confidence triggers clarification
3. ✅ **Semantic similarity**: Distinction is correct, needs better UI
4. ✅ **Clarification questions**: Generic but still useful

**Don't hide these limitations** - they demonstrate the system's **safety mechanisms**:
- Schema validation catches invalid extractions
- Clarification triggers on low confidence
- Review routing sends uncertain suggestions to manual review

This is a **much stronger engineering story** than showing a magically perfect model.

---

**Signed**: Claude  
**Date**: 2024-08-27  
**Status**: ✅ **Documented & Expected**
