# Model Registry System - Implementation Guide

## Overview

The Model Registry is a comprehensive system for managing ML model versions, tracking lifecycle, and facilitating deployment decisions. It provides centralized management of all models across their lifecycle from training to production.

## Architecture

### Core Components

1. **ModelRegistry** (`registry.py`)
   - Central registry for model management
   - Persistent storage on disk
   - Version tracking and lifecycle management
   - Lineage tracking for fine-tuned models

2. **ModelMetadata** 
   - Complete metadata for each model version
   - Evaluation metrics and performance indicators
   - Training configuration and parameters
   - Creation and modification timestamps

3. **ModelLoader** (`loader.py`)
   - Production model loading with automatic version resolution
   - Caching for performance
   - Integration with calibration parameters
   - Easy access to current production models

## Model Lifecycle

```
EXPERIMENTAL → STAGING → PRODUCTION
      ↓           ↓          ↓
   (testing)  (validation) (live)
      
      DEPRECATED ← ARCHIVED
   (old models)  (history)
```

### Status Definitions

- **EXPERIMENTAL**: New model under development/testing
- **STAGING**: Validated and ready for deployment testing
- **PRODUCTION**: Live model serving real traffic
- **DEPRECATED**: Older version retained for reference
- **ARCHIVED**: Historical record

## Usage

### 1. Register a Model

```bash
python rie_ml/scripts/register_distilbert_model.py
```

This script:
- Loads the trained DistilBERT model
- Retrieves evaluation metrics from storage
- Registers the model with metadata
- Saves registration summary

### 2. Check Model Status

```bash
python rie_ml/scripts/promote_model.py status --model-id <model_id>
```

Output includes:
- Version and status
- Evaluation metrics
- Training configuration
- Creation and modification timestamps

### 3. Promote Model Through Lifecycle

**To Staging:**
```bash
python rie_ml/scripts/promote_model.py promote-staging \
  --model-id a6680da5-4ab6-41c8-a88e-fc395e94a804 \
  --reason "Passed evaluation with 98% accuracy"
```

**To Production:**
```bash
python rie_ml/scripts/promote_model.py promote-prod \
  --model-id a6680da5-4ab6-41c8-a88e-fc395e94a804 \
  --reason "Approved for production deployment"
```

### 4. Load Production Model

```python
from rie_ml.src.model_registry.loader import ModelLoader

loader = ModelLoader(device='cpu')
result = loader.load_production_model('distilbert-feedback-classifier')

model = result['model']
metadata = result['metadata']
calibration_params = result['calibration_params']

# Use model for inference
```

### 5. List Available Models

```bash
python -c "
from rie_ml.src.model_registry.loader import ModelLoader
loader = ModelLoader()
import json
print(json.dumps(loader.list_available_models(), indent=2))
"
```

## File Structure

```
rie_ml/
├── src/
│   └── model_registry/
│       ├── __init__.py           # Public API
│       ├── registry.py           # Core registry implementation
│       └── loader.py             # Model loading utilities
├── scripts/
│   ├── register_distilbert_model.py    # Registration script
│   └── promote_model.py                # Promotion script
└── models/
    └── registry/
        ├── index.json            # Model index
        ├── lineage.json          # Model lineage/relationships
        ├── promotion_history.json # Promotion records
        └── metadata/             # Individual model metadata files
            └── <model_id>.json
```

## DistilBERT Model Status

### Current Registration

**Model Name**: `distilbert-feedback-classifier`
**Current Status**: 🟢 PRODUCTION
**Version**: 1.0.0
**Model ID**: `a6680da5-4ab6-41c8-a88e-fc395e94a804`

### Performance Metrics

| Task | Accuracy | Macro F1 | Precision | Recall |
|------|----------|----------|-----------|--------|
| Feedback Type | **98.01%** | 0.9879 | 0.9860 | 0.9901 |
| Rule Category | 82.59% | 0.7300 | 0.7436 | 0.7617 |
| Is Actionable | 97.51% | 0.9796 | 0.9917 | 0.9677 |
| Requires Clarification | 98.51% | 0.9774 | 0.9701 | 0.9848 |

### Evaluation Details

- **Dataset**: Frozen test set (201 samples)
- **Domains**: ecommerce, customer_support, saas_subscription
- **Calibration**: Temperature scaling applied
- **Evaluation ID**: `7528045b-c2b5-4f8d-9dbe-a10fea033976`

## Programmatic API

### Register Model

```python
from rie_ml.src.model_registry import ModelRegistry, ModelType

registry = ModelRegistry()

metadata = registry.register_model(
    model_name="my-classifier",
    model_type=ModelType.ML_DISTILBERT,
    version="1.0.0",
    model_path="/path/to/model.pt",
    created_by="ml_pipeline",
    description="My classifier description",
    tags=["production", "classifier"],
    evaluation_metrics={"accuracy": 0.95},
    acceptance_criteria_passed=True
)
```

### Promote Model

```python
from rie_ml.src.model_registry import ModelStatus

model = registry.promote_model(
    model_id=metadata.model_id,
    target_status=ModelStatus.PRODUCTION,
    promotion_reason="Ready for production"
)
```

### Get Models

```python
# Get latest production version
prod_model = registry.get_latest_version(
    "distilbert-feedback-classifier",
    status=ModelStatus.PRODUCTION
)

# Get all versions
all_versions = registry.get_model_versions("distilbert-feedback-classifier")

# Get by ID
specific = registry.get_model("a6680da5-4ab6-41c8-a88e-fc395e94a804")
```

### Compare Models

```python
comparison = registry.compare_models(model_id_1, model_id_2)
```

### Get Lineage

```python
lineage = registry.get_model_lineage(model_id, depth=3)
```

## Key Features

✅ **Version Management**: Track all model versions with metadata
✅ **Lifecycle Tracking**: Explicit status transitions with validation
✅ **Lineage Tracking**: Track parent-child relationships for fine-tuned models
✅ **Persistent Storage**: All data saved to disk for durability
✅ **Metrics Integration**: Direct integration with evaluation metrics storage
✅ **Easy Deployment**: Simple API for loading production models
✅ **Audit Trail**: Complete history of all model operations
✅ **Status Validation**: Prevents invalid status transitions

## Next Steps

1. **Integration with API**: Expose model loading through REST API
2. **Model A/B Testing**: Support canary deployments with multiple models
3. **Automated Promotion**: CI/CD integration for automatic promotions
4. **Model Monitoring**: Track performance metrics over time
5. **Rollback Support**: Easy rollback to previous versions
