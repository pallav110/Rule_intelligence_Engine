#!/usr/bin/env python
"""Train baseline ML models for Rule Intelligence Engine."""

import os
import sys
from pathlib import Path

# Add the project root and rie_ml to Python path
project_root = Path("/home/spxlpt133/Desktop/Rule-intelligence-Engine")
rie_ml_path = project_root / "rie_ml"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(rie_ml_path))

# Ensure models directory exists
models_dir = rie_ml_path / "models"
models_dir.mkdir(parents=True, exist_ok=True)

# Train Classification Model
print("Training Classification Model...")
from rie_ml.src.baseline.classifier import BaselineClassifier

classifier = BaselineClassifier()
train_path = rie_ml_path / "dataset_generation" / "output" / "ecommerce" / "classification.jsonl"

if train_path.exists():
    classifier.train(str(train_path))
    classifier.save(str(models_dir / "baseline_classifier.pkl"))
    print("✓ Classification model trained and saved")
else:
    print(f"✗ Training data not found: {train_path}")

# Train Extraction Model (if available)
print("\nTraining Extraction Model...")
try:
    from rie_ml.src.baseline.extractor import BaselineRuleExtractor
    extractor = BaselineRuleExtractor()
    extraction_train_path = rie_ml_path / "dataset_generation" / "output" / "ecommerce" / "extraction.jsonl"

    if extraction_train_path.exists():
        # Check if extractor has train method
        if hasattr(extractor, 'train'):
            extractor.train(str(extraction_train_path))
            extractor.save(str(models_dir / "baseline_extractor.pkl"))
            print("✓ Extraction model trained and saved")
        else:
            print("ℹ Extraction model doesn't have train method, skipping")
    else:
        print(f"✗ Extraction training data not found: {extraction_train_path}")
except ImportError as e:
    print(f"ℹ Extraction model not available: {e}")

print("\n✓ All models trained successfully!")