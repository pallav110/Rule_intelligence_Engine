#!/usr/bin/env python3
"""Train and save baseline classifier for each domain pack.

This script trains the deterministic TF-IDF + Logistic Regression baseline
classifier using generated training data from each domain pack.

Usage:
    python train_baseline.py

Output:
    Models saved to: rie_ml/models/baseline_classifier_{domain}.pkl
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from baseline.classifier import BaselineClassifier


def combine_domain_training_data(domain: str, output_path: Path) -> int:
    """Combine and prepare training data for a domain."""
    dataset_dir = Path(__file__).parent.parent / "dataset_generation" / "output" / domain
    train_file = dataset_dir / "train.jsonl"

    if not train_file.exists():
        print(f"⚠️  No training data found for {domain} at {train_file}")
        return 0

    # Validate and count records
    count = 0
    with open(train_file, "r") as f:
        for line in f:
            try:
                obj = json.loads(line.strip())
                if obj.get("feedback_text") and obj.get("feedback_type"):
                    count += 1
            except json.JSONDecodeError:
                pass

    return count


def train_baseline_classifier(domain: str, output_dir: Path):
    """Train baseline classifier for a specific domain."""
    dataset_dir = Path(__file__).parent.parent / "dataset_generation" / "output" / domain
    train_file = dataset_dir / "train.jsonl"

    if not train_file.exists():
        print(f"❌ No training data found for domain '{domain}'")
        return False

    # Count records
    print(f"\n📊 Training baseline classifier for domain: {domain}")
    print(f"   Data source: {train_file}")

    record_count = combine_domain_training_data(domain, output_dir)
    if record_count == 0:
        print(f"❌ No valid training records found")
        return False

    print(f"   Records: {record_count}")

    # Train classifier
    print(f"   Training TF-IDF + Logistic Regression model...")
    classifier = BaselineClassifier()

    try:
        classifier.train(str(train_file))
        print(f"   ✅ Model trained successfully")
    except Exception as e:
        print(f"   ❌ Training failed: {e}")
        return False

    # Save model
    output_path = output_dir / f"baseline_classifier_{domain}.pkl"
    print(f"   Saving model to: {output_path}")

    try:
        classifier.save(str(output_path))
        print(f"   ✅ Model saved: {output_path}")
        return True
    except Exception as e:
        print(f"   ❌ Save failed: {e}")
        return False


def main():
    """Train baseline classifiers for all domains."""
    output_dir = Path(__file__).parent.parent / "models"
    output_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("BASELINE CLASSIFIER TRAINING")
    print("=" * 60)
    print(f"Output directory: {output_dir}")

    # Domains to train
    domains = ["ecommerce", "customer_support", "saas_subscription"]
    results = {}

    for domain in domains:
        success = train_baseline_classifier(domain, output_dir)
        results[domain] = "✅ SUCCESS" if success else "❌ FAILED"

    # Summary
    print("\n" + "=" * 60)
    print("TRAINING SUMMARY")
    print("=" * 60)

    for domain, status in results.items():
        print(f"{domain:20s} {status}")

    success_count = sum(1 for s in results.values() if "SUCCESS" in s)
    print(f"\nTotal: {success_count}/{len(domains)} domains trained successfully")

    if success_count == len(domains):
        print("\n✅ All baseline classifiers trained and saved!")
        print("\nNext steps:")
        print("1. Replace mock classifier with trained baseline in app/services/classifier.py")
        print("2. Load baseline models on API startup")
        print("3. Run Phase 2 tests to verify improvements")
        return 0
    else:
        print(f"\n⚠️  {len(domains) - success_count} domains failed training")
        return 1


if __name__ == "__main__":
    sys.exit(main())
