#!/usr/bin/env python3
"""Train and save a unified baseline classifier across all domains.

This script trains a single deterministic TF-IDF + Logistic Regression baseline
classifier using combined training data from all domain packs.

Usage:
    python train_baseline_unified.py

Output:
    Model saved to: rie_ml/models/baseline_classifier_unified.pkl
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from baseline.classifier import BaselineClassifier


def combine_all_domain_data(output_dir: Path) -> List[Dict[str, Any]]:
    """Combine training data from all domains into a single dataset."""
    all_data = []
    domains = ["ecommerce", "customer_support", "saas_subscription"]

    for domain in domains:
        dataset_dir = Path(__file__).parent.parent / "dataset_generation" / "output" / domain
        train_file = dataset_dir / "train.jsonl"

        if not train_file.exists():
            print(f"⚠️  No training data found for {domain} at {train_file}")
            continue

        print(f"📊 Loading {domain} data from {train_file}")

        # Load and validate records
        count = 0
        with open(train_file, "r") as f:
            for line in f:
                try:
                    obj = json.loads(line.strip())
                    if obj.get("feedback_text") and obj.get("feedback_type"):
                        # Add domain information to each record
                        obj["domain"] = domain
                        all_data.append(obj)
                        count += 1
                except json.JSONDecodeError:
                    pass

        print(f"   Loaded {count} valid records from {domain}")

    return all_data


def create_combined_dataset_file(all_data: List[Dict[str, Any]], output_dir: Path) -> Path:
    """Create a combined training file."""
    # Use a temporary location for the combined file
    temp_dir = Path(__file__).parent.parent / "datasets" / "evaluation"
    temp_dir.mkdir(exist_ok=True)
    combined_file = temp_dir / "train_combined.jsonl"

    print(f"\n🔗 Creating combined training dataset: {combined_file}")

    with open(combined_file, "w") as f:
        for record in all_data:
            f.write(json.dumps(record) + "\n")

    print(f"   ✅ Saved {len(all_data)} combined training records")

    return combined_file


def train_unified_classifier(train_file: Path, output_dir: Path) -> bool:
    """Train a unified baseline classifier across all domains."""
    print(f"\n🎯 Training unified baseline classifier")
    print(f"   Data source: {train_file}")

    # Count records
    record_count = 0
    with open(train_file, "r") as f:
        for line in f:
            record_count += 1

    print(f"   Records: {record_count}")

    # Train classifier
    print(f"   Training TF-IDF + Logistic Regression model...")
    classifier = BaselineClassifier()

    try:
        classifier.train(str(train_file))
        print(f"   ✅ Model trained successfully")
    except Exception as e:
        print(f"   ❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Save model to a writable location
    models_dir = Path(__file__).parent.parent / "datasets" / "evaluation"
    models_dir.mkdir(exist_ok=True)
    output_path = models_dir / "baseline_classifier_unified.pkl"
    print(f"   Saving model to: {output_path}")

    try:
        classifier.save(str(output_path))
        print(f"   ✅ Model saved: {output_path}")
        return True
    except Exception as e:
        print(f"   ❌ Save failed: {e}")
        return False


def main():
    """Train unified baseline classifier."""
    output_dir = Path(__file__).parent.parent / "models"
    output_dir.mkdir(exist_ok=True)

    print("=" * 70)
    print("BASELINE CLASSIFIER TRAINING - UNIFIED MODEL")
    print("=" * 70)
    print(f"Output directory: {output_dir}")

    # Combine all domain data
    all_data = combine_all_domain_data(output_dir)

    if not all_data:
        print("\n❌ No training data found in any domain")
        return 1

    # Create combined dataset
    combined_file = create_combined_dataset_file(all_data, output_dir)

    # Train unified model
    success = train_unified_classifier(combined_file, output_dir)

    # Summary
    print("\n" + "=" * 70)
    print("TRAINING SUMMARY")
    print("=" * 70)

    if success:
        print("✅ Unified baseline classifier trained and saved!")
        print(f"   Model: {models_dir / 'baseline_classifier_unified.pkl'}")
        print(f"   Training data: {len(all_data)} records from all domains")
        print("\nNext steps:")
        print("1. Update evaluation script to use unified model")
        print("2. Update backend to load unified model")
        print("3. Run evaluation to validate performance")
        return 0
    else:
        print("⚠️  Training failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
