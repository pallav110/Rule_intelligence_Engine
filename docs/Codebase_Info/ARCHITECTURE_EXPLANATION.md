# Architecture Explanation - 4-File Design Pattern

## 🏗️ Overview

The Rule Intelligence Engine uses a **two-layer architecture** with **separation of concerns**:

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                          │
│  (Production Services - FastAPI Integration)                  │
├─────────────────────────────────────────────────────────────┤
│ app/services/extractor.py    app/services/validator.py        │
│ (RealExtractor)              (RealValidator)                  │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ uses
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    CORE LAYER                                 │
│  (Domain-Agnostic Algorithms - No Dependencies)               │
├─────────────────────────────────────────────────────────────┤
│ rie_ml/src/baseline/extractor.py  rie_ml/src/baseline/validator.py │
│ (BaselineExtractor)            (BaselineValidator)             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 Detailed Breakdown

### 1. `rie_ml/src/baseline/extractor.py` (Core Extractor)

**Purpose**: Pure algorithm for rule extraction

**Characteristics**:
- ✅ **Domain-agnostic**: Works with any glossary/schema
- ✅ **No dependencies**: Pure Python, no web framework
- ✅ **Reusable**: Used in scripts, tests, batch jobs, services
- ✅ **Deterministic**: Pattern-based, no ML required
- ✅ **Fast**: ~5ms per extraction

**What it does**:
```python
# Input: text + glossary + schema
text = "orders above ₹1500 should qualify for free express shipping"
glossary = load_glossary('ecommerce')
schema = load_schema('ecommerce')

# Output: structured rule
extractor = BaselineExtractor(glossary, schema)
result = extractor.extract(text)
# {
#   "business_term": "free_express_shipping",
#   "operation": "include",
#   "conditions": [{"field": "orders.total", "operator": "greater_than", "value": 1500}],
#   "scope": "global",
#   "confidence": {"business_term": 0.95, "operation": 0.90, ...}
# }
```

**Used by**:
- `app/services/extractor.py` (production service)
- `rie_ml/scripts/evaluate_baseline.py` (evaluation)
- `tests/` (unit tests)
- Batch processing scripts

---

### 2. `app/services/extractor.py` (Service Extractor)

**Purpose**: Production-ready wrapper for FastAPI

**Characteristics**:
- ✅ **Domain-aware**: Switches domains dynamically
- ✅ **Error handling**: Graceful fallback on failure
- ✅ **FastAPI integration**: Ready for HTTP requests
- ✅ **Logging**: Production monitoring
- ✅ **Configuration**: Environment-aware

**What it does**:
```python
# Initialize with domain
extractor = RealExtractor(domain='ecommerce')

# Extract with fallback
result = extractor.extract(text)
# - Tries BaselineExtractor first
# - Falls back to simple patterns if BaselineExtractor fails
# - Returns consistent format either way
```

**Key features**:
1. **Automatic loading**: Loads correct domain glossary/schema
2. **Fallback mode**: If baseline extractor fails, uses simple patterns
3. **Status tracking**: `is_ready` flag for health checks
4. **Domain switching**: Can change domains at runtime

---

### 3. `rie_ml/src/baseline/validator.py` (Core Validator)

**Purpose**: Pure algorithm for rule validation

**Characteristics**:
- ✅ **Schema-based**: Validates against domain schema
- ✅ **No dependencies**: Pure Python
- ✅ **Reusable**: Used everywhere validation is needed
- ✅ **Deterministic**: Rule-based validation
- ✅ **Fast**: ~2ms per validation

**What it does**:
```python
# Input: extracted rule + schema + glossary
rule = {
  "business_term": "free_express_shipping",
  "operation": "include",
  "conditions": [{"field": "orders.total", "operator": "greater_than", "value": 1500}]
}

schema = load_schema('ecommerce')
glossary = load_glossary('ecommerce')

validator = BaselineValidator(schema, glossary)
result = validator.validate(rule)
# {
#   "status": "PASS",
#   "coverage": 1.0,
#   "validated_fields": ["business_term", "operation", "conditions"],
#   "invalid_fields": [],
#   "validation_errors": []
# }
```

**Validation checks**:
1. Business term (against glossary)
2. Operation (against valid operations list)
3. Conditions (field, operator, value against schema)
4. Scope (against valid scopes)
5. Threshold (if applicable)

---

### 4. `app/services/validator.py` (Service Validator)

**Purpose**: Production-ready wrapper for FastAPI

**Characteristics**:
- ✅ **Domain-aware**: Switches domains dynamically
- ✅ **Error handling**: Graceful fallback on failure
- ✅ **FastAPI integration**: Ready for HTTP requests
- ✅ **Logging**: Production monitoring
- ✅ **Configuration**: Environment-aware

**What it does**:
```python
# Initialize with domain
validator = RealValidator(domain='ecommerce')

# Validate with fallback
result = validator.validate(extracted_rule)
# - Tries BaselineValidator first
# - Falls back to simple checks if BaselineValidator fails
# - Returns consistent format either way
```

**Key features**:
1. **Automatic loading**: Loads correct domain schema/glossary
2. **Fallback mode**: If baseline validator fails, uses simple checks
3. **Status tracking**: `is_ready` flag for health checks
4. **Domain switching**: Can change domains at runtime

---

## 🔄 Relationship Between Files

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ app/services/extractor.py (RealExtractor)                                │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ __init__(domain)                                                  │  │
│  │   ├─ tries to load BaselineExtractor                            │  │
│  │   ├─ loads glossary/schema for domain                            │  │
│  │   └─ sets is_ready=True if successful                            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ extract(text)                                                     │  │
│  │   ├─ if is_ready: uses BaselineExtractor.extract()               │  │
│  │   └─ else: uses simple fallback patterns                         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                            ▲
                            │ uses
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ rie_ml/src/baseline/extractor.py (BaselineExtractor)                   │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ __init__(glossary, schema)                                        │  │
│  │   └─ initializes extraction patterns                             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ extract(text)                                                     │  │
│  │   ├─ extracts business term (pattern matching)                    │  │
│  │   ├─ extracts operation (regex patterns)                          │  │
│  │   ├─ extracts conditions (field-operator-value)                   │  │
│  │   ├─ extracts scope (default: global)                             │  │
│  │   └─ calculates confidence scores                                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ✅ Why This Design?

### Benefits

1. **Separation of Concerns**
   - Core: Pure algorithm (easy to test, reuse, maintain)
   - Service: Production wrapper (handles real-world issues)

2. **Reusability**
   - Core extractor/validator used in multiple contexts
   - Service layer only used in FastAPI

3. **Testability**
   - Core can be unit tested without FastAPI
   - Service can be integration tested with FastAPI

4. **Maintainability**
   - Changes to algorithm don't affect API
   - Changes to API don't affect algorithm

5. **Fallback Strategy**
   - Service layer provides graceful degradation
   - If core fails, service still works (reduced functionality)

---

## 📊 Code Statistics

| File | Lines | Purpose | Layer |
|------|-------|---------|-------|
| `rie_ml/src/baseline/extractor.py` | 400+ | Core extraction algorithm | Core |
| `app/services/extractor.py` | 150+ | Production service wrapper | Service |
| `rie_ml/src/baseline/validator.py` | 200+ | Core validation algorithm | Core |
| `app/services/validator.py` | 150+ | Production service wrapper | Service |

---

## 🎯 Usage Examples

### Core Layer (Testing/Scripts)
```python
# Direct use of core extractor
from rie_ml.src.baseline.extractor import BaselineExtractor, load_glossary, load_schema

glossary = load_glossary('ecommerce')
schema = load_schema('ecommerce')
extractor = BaselineExtractor(glossary, schema)

result = extractor.extract("orders above ₹1500 should qualify for free express shipping")
print(result)
```

### Service Layer (Production)
```python
# Use via FastAPI service
from app.services.extractor import RealExtractor

extractor = RealExtractor(domain='ecommerce')
result = extractor.extract("orders above ₹1500 should qualify for free express shipping")
print(result)
```

### Full Pipeline
```python
# Complete extraction + validation
from app.services.extractor import RealExtractor
from app.services.validator import RealValidator

extractor = RealExtractor(domain='ecommerce')
validator = RealValidator(domain='ecommerce')

text = "orders above ₹1500 should qualify for free express shipping"

# Step 1: Extract
rule = extractor.extract(text)

# Step 2: Validate
validation = validator.validate(rule)

print(f"Extracted: {rule}")
print(f"Validation: {validation}")
```

---

## 🔍 Key Differences

### Core Layer
- **No domain awareness**: Requires explicit glossary/schema
- **No error handling**: Assumes valid inputs
- **No logging**: Silent operation
- **No fallback**: Fails on error
- **Fast**: Minimal overhead

### Service Layer
- **Domain-aware**: Loads correct domain automatically
- **Error handling**: Graceful degradation
- **Logging**: Production monitoring
- **Fallback**: Works even if core fails
- **Slightly slower**: Extra safety checks

---

## ✅ Conclusion

**4 files are intentional and follow best practices**:

1. **Core Extractor**: Pure algorithm (reusable, testable)
2. **Service Extractor**: Production wrapper (safe, reliable)
3. **Core Validator**: Pure algorithm (reusable, testable)
4. **Service Validator**: Production wrapper (safe, reliable)

**This design enables**:
- ✅ Clean separation of concerns
- ✅ High reusability
- ✅ Easy testing
- ✅ Graceful degradation
- ✅ Production readiness

**All files are necessary and serve distinct purposes** ✅
