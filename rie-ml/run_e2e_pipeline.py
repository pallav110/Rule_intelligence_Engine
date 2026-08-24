#!/usr/bin/env python3
"""End-to-end pipeline runner for Week 1-3 integration test.

Tests the complete flow:
  feedback → classify → extract → detect duplicates/conflicts → clarify

Usage:
  python run_e2e_pipeline.py --train --evaluate
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from baseline.classifier import BaselineClassifier
from baseline.extractor import BaselineRuleExtractor
from duplicate_detection import DuplicateDetector
from conflict_detection import ConflictDetector
from clarification import ClarificationGenerator
from evaluation import EvaluationHarness


def main():
    parser = argparse.ArgumentParser(description="RIE-ML End-to-End Pipeline")
    parser.add_argument("--train", action="store_true", help="Train classifier on train.jsonl")
    parser.add_argument("--evaluate", action="store_true", help="Run evaluation on test.jsonl")
    parser.add_argument("--test-feedback", type=str, help="Test single feedback text")
    parser.add_argument("--data-dir", type=str, default="dataset_generation/output",
                        help="Path to dataset output directory")
    args = parser.parse_args()

    data_dir = Path(__file__).parent / args.data_dir
    train_path = data_dir / "train.jsonl"
    test_path = data_dir / "test.jsonl"
    extraction_path = data_dir / "extraction.jsonl"
    model_path = Path(__file__).parent / "models" / "baseline_classifier.pkl"
    model_path.parent.mkdir(exist_ok=True)

    # Initialize components
    print("=== Initializing RIE-ML Pipeline ===")
    classifier = BaselineClassifier()
    extractor = BaselineRuleExtractor()
    dup_detector = DuplicateDetector(threshold=0.85)
    conflict_detector = ConflictDetector()
    clarifier = ClarificationGenerator(confidence_threshold=0.6)

    # Train if requested
    if args.train:
        print(f"\n[1/6] Training classifier on {train_path}...")
        if not train_path.exists():
            print(f"ERROR: {train_path} not found. Run dataset generation first.")
            return 1
        classifier.train(str(train_path))
        classifier.save(str(model_path))
        print(f"✓ Classifier trained and saved to {model_path}")
    else:
        if model_path.exists():
            print(f"\n[1/6] Loading classifier from {model_path}...")
            classifier.load(str(model_path))
            print("✓ Classifier loaded")
        else:
            print(f"ERROR: No trained model found at {model_path}. Run with --train first.")
            return 1

    # Index duplicates
    print(f"\n[2/6] Indexing for duplicate detection...")
    if train_path.exists():
        dup_detector.index(str(train_path))
        print(f"✓ Indexed {len(dup_detector.ids)} feedback entries")
    else:
        print("⚠ Skipping duplicate detection (no train data)")

    # Load rules for conflict detection
    print(f"\n[3/6] Loading rules for conflict detection...")
    if extraction_path.exists():
        conflict_detector.load_rules(str(extraction_path))
        print(f"✓ Loaded rules for {len(conflict_detector.rules_by_term)} business terms")
    else:
        print("⚠ Skipping conflict detection (no extraction data)")

    # Test single feedback if provided
    if args.test_feedback:
        print(f"\n[4/6] Testing single feedback...")
        print(f"Input: {args.test_feedback}")

        # Classify
        cls_result = classifier.classify(args.test_feedback, {})
        print(f"\nClassification Result:")
        print(json.dumps(cls_result, indent=2))

        # Extract
        ext_result = extractor.extract(args.test_feedback, cls_result, {"available_tables": [], "available_columns": []})
        print(f"\nExtraction Result:")
        print(json.dumps(ext_result, indent=2))

        # Clarify
        clar_result = clarifier.generate(args.test_feedback, cls_result, ext_result)
        print(f"\nClarification Result:")
        print(json.dumps(clar_result, indent=2))

    # Evaluate if requested
    if args.evaluate:
        print(f"\n[5/6] Running evaluation on {test_path}...")
        if not test_path.exists():
            print(f"ERROR: {test_path} not found.")
            return 1

        harness = EvaluationHarness(str(test_path))
        report = harness.generate_report(classifier, extractor)

        report_path = Path(__file__).parent / "evaluation_report.md"
        with open(report_path, "w") as f:
            f.write(report)
        print(f"✓ Evaluation complete. Report saved to {report_path}")
        print("\n" + report)

    # Find duplicates and conflicts
    print(f"\n[6/6] Finding duplicates and conflicts...")
    if dup_detector.vectors is not None:
        dup_pairs = dup_detector.find_all_pairs()
        print(f"✓ Found {len(dup_pairs)} duplicate pairs")
        if len(dup_pairs) > 0:
            print(f"  Example: {dup_pairs[0]}")

    if conflict_detector.rules_by_term:
        conflicts = conflict_detector.find_conflicts()
        print(f"✓ Found {len(conflicts)} conflicts")
        if len(conflicts) > 0:
            print(f"  Example: {conflicts[0]['description']}")

    print("\n=== Pipeline Execution Complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
