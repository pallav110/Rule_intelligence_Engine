#!/usr/bin/env python3
"""Evaluate baseline model performance on frozen test dataset.

This script runs the complete baseline pipeline (classification, extraction, validation)
on the frozen evaluation dataset and generates a performance report.

Usage:
    python evaluate_baseline.py [domain]

Output:
    - Evaluation report (JSON)
    - Acceptance criteria validation
    - Performance metrics
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from baseline.classifier import BaselineClassifier
from baseline.extractor import BaselineExtractor
from baseline.validator import BaselineValidator
from baseline.extractor import load_glossary, load_schema

# Add evaluation to path
sys.path.insert(0, str(Path(__file__).parent.parent / "evaluation"))
from evaluator import BaselineEvaluator, load_acceptance_criteria


def load_test_dataset(domain: str = "ecommerce") -> List[Dict[str, Any]]:
    """Load test dataset."""
    dataset_path = Path(__file__).parent.parent / "datasets" / "evaluation" / "baseline_test.json"

    if dataset_path.exists():
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("test_cases", [])

    return []


def run_baseline_evaluation(domain: str = "ecommerce"):
    """Run complete baseline evaluation."""
    print(f"🔍 Loading unified baseline model")

    # Load glossary and schema
    glossary = load_glossary(domain)
    schema = load_schema(domain)

    if not glossary or not schema:
        print("❌ Error: Glossary or schema not found")
        return None

    # Initialize models - use unified classifier
    model_path = Path(__file__).parent.parent / "models" / "baseline_classifier_unified.pkl"
    classifier = BaselineClassifier(str(model_path))
    extractor = BaselineExtractor(glossary, schema)
    validator = BaselineValidator(schema, glossary)

    # Load test dataset
    print("📊 Loading test dataset...")
    test_data = load_test_dataset(domain)

    if not test_data:
        print("❌ Error: Test dataset not found")
        return None

    print(f"📋 Found {len(test_data)} test cases")

    # Generate predictions
    print("🔄 Running baseline pipeline...")

    classification_preds = []
    extraction_preds = []
    validation_preds = []

    for i, item in enumerate(test_data, 1):
        print(f"  Processing test case {i}/{len(test_data)}...", end="\r")

        # Classification
        classification = classifier.classify(item["feedback_text"])
        classification_preds.append({
            "feedback_id": item["feedback_id"],
            "predicted": classification,
            "expected": item["expected_classification"]
        })

        # Extraction
        extraction = extractor.extract(item["feedback_text"], classification)
        extraction_preds.append({
            "feedback_id": item["feedback_id"],
            "predicted": extraction,
            "expected": item["expected_extraction"]
        })

        # Validation
        validation = validator.validate(extraction)
        validation_preds.append({
            "feedback_id": item["feedback_id"],
            "predicted": validation,
            "expected": item["expected_validation"]
        })

    print("\n✅ Pipeline execution complete")

    # Evaluate performance
    print("📈 Evaluating performance...")

    evaluator = BaselineEvaluator(test_data)
    evaluator.evaluate_classification(classification_preds)
    evaluator.evaluate_extraction(extraction_preds)
    evaluator.evaluate_validation(validation_preds)
    evaluator.calculate_overall_performance()

    # Validate against criteria
    print("📋 Validating against acceptance criteria...")
    criteria = load_acceptance_criteria()
    validation_result = evaluator.validate_acceptance_criteria(criteria)

    # Generate report
    report = evaluator.generate_report()

    return {
        "report": report,
        "validation": validation_result,
        "criteria": criteria
    }


def print_report(results: Dict[str, Any]):
    """Print evaluation report."""
    report = results["report"]
    validation = results["validation"]
    criteria = results["criteria"]

    print("\n" + "="*80)
    print("BASELINE EVALUATION REPORT")
    print("="*80)

    print(f"\n📊 Dataset: {report['metrics']['classification']['sample_size']} test cases")
    print(f"📅 Timestamp: {report['timestamp']}")

    print("\n" + "-"*80)
    print("CLASSIFICATION PERFORMANCE")
    print("-"*80)

    class_metrics = report["metrics"]["classification"]
    print(f"Feedback Type:")
    print(f"  Precision: {class_metrics['feedback_type']['precision']:.4f}")
    print(f"  Recall:    {class_metrics['feedback_type']['recall']:.4f}")
    print(f"  F1:        {class_metrics['feedback_type']['f1']:.4f}")

    print(f"\nRule Category:")
    print(f"  Precision: {class_metrics['rule_category']['precision']:.4f}")
    print(f"  Recall:    {class_metrics['rule_category']['recall']:.4f}")
    print(f"  F1:        {class_metrics['rule_category']['f1']:.4f}")

    print(f"\nOverall Accuracy: {class_metrics['overall_accuracy']:.4f}")

    print("\n" + "-"*80)
    print("EXTRACTION PERFORMANCE")
    print("-"*80)

    ext_metrics = report["metrics"]["extraction"]
    print(f"Field Accuracy:")
    for field, acc in ext_metrics["field_accuracy"].items():
        print(f"  {field}: {acc:.4f}")

    print(f"\nComplete Rule Accuracy: {ext_metrics['complete_rule_accuracy']:.4f}")

    print("\n" + "-"*80)
    print("VALIDATION PERFORMANCE")
    print("-"*80)

    val_metrics = report["metrics"]["validation"]
    print(f"Status Accuracy:        {val_metrics['status_accuracy']:.4f}")
    print(f"Coverage Correlation:   {val_metrics['coverage_correlation']:.4f}")

    print("\n" + "-"*80)
    print("OVERALL PERFORMANCE")
    print("-"*80)

    overall = report["metrics"]["overall"]
    print(f"Overall Score: {overall['score']:.4f}")
    print(f"Grade:         {overall['grade']}")

    print("\n" + "="*80)
    print("ACCEPTANCE CRITERIA VALIDATION")
    print("="*80)

    print(f"\nOverall Status: {'✅ PASSED' if validation['passed'] else '❌ FAILED'}")

    for component, result in validation["details"].items():
        print(f"\n{component.upper()}:")
        print(f"  Status: {'✅ Passed' if result['passed'] else '❌ Failed'}")

        if not result["passed"]:
            for metric, values in result["details"].items():
                print(f"    {metric}:")
                print(f"      Actual:   {values['actual']}")
                print(f"      Expected: {values['expected']}")

    print("\n" + "="*80)


def save_report(results: Dict[str, Any], domain: str = "ecommerce"):
    """Save evaluation report to file."""
    report_dir = Path(__file__).parent.parent / "evaluation" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    timestamp = results["report"]["timestamp"].replace(":", "-").replace(".", "-")
    report_path = report_dir / f"baseline_evaluation_{domain}_{timestamp}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n💾 Report saved to: {report_path}")


def main():
    """Main evaluation function."""
    domain = sys.argv[1] if len(sys.argv) > 1 else "ecommerce"

    print("🚀 Starting Baseline Evaluation")
    print(f"📁 Domain: {domain}")

    results = run_baseline_evaluation(domain)

    if results:
        print_report(results)
        save_report(results, domain)

        # Exit with appropriate code
        if results["validation"]["passed"]:
            print("\n🎉 Baseline evaluation PASSED!")
            sys.exit(0)
        else:
            print("\n⚠️  Baseline evaluation FAILED!")
            sys.exit(1)
    else:
        print("\n❌ Evaluation failed to run")
        sys.exit(1)


if __name__ == "__main__":
    main()
