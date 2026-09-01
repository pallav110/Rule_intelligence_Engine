#!/usr/bin/env python3
"""View and query stored baseline evaluation metrics.

Usage:
    python view_metrics.py                          # List all evaluations
    python view_metrics.py --id baseline_xyz        # View specific evaluation
    python view_metrics.py --model baseline_deterministic  # Filter by model type
    python view_metrics.py --compare id1 id2        # Compare two evaluations
    python view_metrics.py --summary                # Show latest 5 evaluations summary
"""

import sys
import json
from pathlib import Path
from typing import Optional
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.metrics_storage import MetricsStorage


class MetricsViewer:
    """View and query evaluation metrics."""

    def __init__(self):
        self.storage = MetricsStorage()

    def list_all(self, limit: int = 20):
        """List all stored evaluations."""
        results = self.storage.list_results(limit=limit)

        if not results:
            print("No evaluations found.")
            return

        print(f"\n{'Evaluation ID':<40} {'Timestamp':<25} {'Model Type':<25} {'Status':<10}")
        print("=" * 100)

        for result in results:
            status = "✅ PASS" if result["acceptance_criteria_passed"] else "❌ FAIL"
            print(
                f"{result['evaluation_id']:<40} {result['timestamp']:<25} "
                f"{result['model_type']:<25} {status:<10}"
            )

        print(f"\nTotal: {len(results)} evaluations")

    def view_evaluation(self, evaluation_id: str):
        """View details of a specific evaluation."""
        result = self.storage.load_result(evaluation_id)

        if not result:
            print(f"❌ Evaluation not found: {evaluation_id}")
            return

        print("\n" + "=" * 80)
        print("EVALUATION DETAILS")
        print("=" * 80)
        print(f"ID: {result.evaluation_id}")
        print(f"Timestamp: {result.timestamp}")
        print(f"Model: {result.model_type} v{result.model_version}")
        print(f"Dataset: {result.dataset_split} ({result.dataset_size} samples)")
        print()

        # Classification
        print("CLASSIFICATION METRICS")
        print("-" * 80)
        print(f"  Accuracy: {result.classification.accuracy * 100:.2f}%")
        print(f"  Calibration Error: {result.classification.calibration_error:.4f}")
        print(f"  Per-Category F1 Scores:")
        for cat, score in result.classification.f1_score.items():
            print(f"    {cat}: {score:.4f}")
        print()

        # Extraction
        print("RULE EXTRACTION METRICS")
        print("-" * 80)
        extraction = result.extraction
        extraction_fields = [
            ("Business Term F1", extraction.business_term_f1),
            ("Operation F1", extraction.operation_f1),
            ("Conditions F1", extraction.conditions_f1),
            ("Scope F1", extraction.scope_f1),
            ("Time Window F1", extraction.time_window_f1),
            ("Affected Entities F1", extraction.affected_entities_f1),
            ("Threshold F1", extraction.threshold_f1),
            ("Exact Rule Match Rate", extraction.exact_rule_match_rate * 100),
            ("Schema Validation Pass Rate", extraction.schema_validation_pass_rate * 100),
        ]
        for name, value in extraction_fields:
            print(f"  {name}: {value:.2f}")
        print()

        # Duplicate Detection
        print("DUPLICATE DETECTION METRICS")
        print("-" * 80)
        dup = result.duplicate_detection
        dup_fields = [
            ("Precision", dup.precision),
            ("Recall", dup.recall),
            ("F1 Score", dup.f1_score),
            ("Recall@K", dup.recall_at_k),
            ("False Positive Rate", dup.false_positive_rate),
            ("False Negative Rate", dup.false_negative_rate),
        ]
        for name, value in dup_fields:
            print(f"  {name}: {value:.4f}")
        print()

        # Conflict Detection
        print("CONFLICT DETECTION METRICS")
        print("-" * 80)
        conf = result.conflict_detection
        conf_fields = [
            ("Precision", conf.precision),
            ("Recall", conf.recall),
            ("F1 Score", conf.f1_score),
            ("Accuracy", conf.accuracy),
            ("False Conflict Rate", conf.false_conflict_rate),
            ("Missed Conflict Rate", conf.missed_conflict_rate),
        ]
        for name, value in conf_fields:
            print(f"  {name}: {value:.4f}")
        print()

        # Clarification
        print("CLARIFICATION METRICS")
        print("-" * 80)
        clar = result.clarification
        clar_fields = [
            ("Detection Precision", clar.detection_precision),
            ("Detection Recall", clar.detection_recall),
            ("Detection F1", clar.detection_f1_score),
            ("Avg Resolution Time (s)", clar.average_resolution_time_seconds),
        ]
        for name, value in clar_fields:
            print(f"  {name}: {value:.4f}")
        print()

        # Performance
        print("PERFORMANCE")
        print("-" * 80)
        print(f"  Avg Processing Time: {result.average_processing_time_seconds:.4f}s per sample")
        print()

        # Acceptance
        status = "✅ PASSED" if result.acceptance_criteria_passed else "❌ FAILED"
        print("ACCEPTANCE CRITERIA")
        print("-" * 80)
        print(f"  {status}")
        print()

        if result.notes:
            print("NOTES")
            print("-" * 80)
            print(f"  {result.notes}")
            print()

        print("=" * 80)

    def compare_evaluations(self, eval_id_1: str, eval_id_2: str):
        """Compare two evaluations."""
        comparison = self.storage.compare_results(eval_id_1, eval_id_2)

        if "error" in comparison:
            print(f"❌ {comparison['error']}")
            return

        print("\n" + "=" * 80)
        print("EVALUATION COMPARISON")
        print("=" * 80)
        print(f"Baseline: {eval_id_1}")
        print(f"  Timestamp: {comparison['baseline_timestamp']}")
        print()
        print(f"Candidate: {eval_id_2}")
        print(f"  Timestamp: {comparison['candidate_timestamp']}")
        print()

        if comparison["improvements"]:
            print("📈 IMPROVEMENTS")
            print("-" * 80)
            for metric, details in comparison["improvements"].items():
                improvement = details["improvement"]
                print(f"  {metric}")
                print(f"    Baseline: {details['baseline']:.4f}")
                print(f"    Candidate: {details['candidate']:.4f}")
                print(f"    Improvement: +{improvement:.4f}")
            print()

        if comparison["regressions"]:
            print("📉 REGRESSIONS")
            print("-" * 80)
            for metric, details in comparison["regressions"].items():
                regression = details["regression"]
                print(f"  {metric}")
                print(f"    Baseline: {details['baseline']:.4f}")
                print(f"    Candidate: {details['candidate']:.4f}")
                print(f"    Regression: -{regression:.4f}")
            print()

        print("DUPLICATE DETECTION COMPARISON")
        print("-" * 80)
        dup = comparison["duplicate_detection"]
        print(f"  Precision: {dup['baseline_precision']:.4f} → {dup['candidate_precision']:.4f}")
        print(f"  Recall: {dup['baseline_recall']:.4f} → {dup['candidate_recall']:.4f}")
        print()

        print("CONFLICT DETECTION COMPARISON")
        print("-" * 80)
        conf = comparison["conflict_detection"]
        print(f"  Precision: {conf['baseline_precision']:.4f} → {conf['candidate_precision']:.4f}")
        print(f"  Recall: {conf['baseline_recall']:.4f} → {conf['candidate_recall']:.4f}")
        print()

        overall = "✅ OVERALL IMPROVEMENT" if comparison["overall_improvement"] else "⚠️  MIXED RESULTS"
        print(f"{overall}")
        print("=" * 80)

        # Save comparison
        comparison_file = self.storage.save_comparison(comparison)
        print(f"\nComparison saved to: {comparison_file}")

    def summary(self, limit: int = 5):
        """Show summary of recent evaluations."""
        results = self.storage.list_results(limit=limit)

        if not results:
            print("No evaluations found.")
            return

        print("\n" + "=" * 80)
        print(f"RECENT EVALUATIONS (Latest {len(results)})")
        print("=" * 80)

        for i, result in enumerate(results, 1):
            status = "✅ PASS" if result["acceptance_criteria_passed"] else "❌ FAIL"
            print(f"\n{i}. {result['evaluation_id']}")
            print(f"   Model: {result['model_type']} v{result['model_version']}")
            print(f"   Timestamp: {result['timestamp']}")
            print(f"   Acceptance: {status}")

        print("\n" + "=" * 80)

    def filter_by_model(self, model_type: str):
        """Filter evaluations by model type."""
        results = self.storage.list_results(model_type=model_type)

        if not results:
            print(f"No evaluations found for model type: {model_type}")
            return

        print(f"\n{'Evaluation ID':<40} {'Timestamp':<25} {'Status':<10}")
        print("=" * 75)

        for result in results:
            status = "✅ PASS" if result["acceptance_criteria_passed"] else "❌ FAIL"
            print(f"{result['evaluation_id']:<40} {result['timestamp']:<25} {status:<10}")

        print(f"\nTotal: {len(results)} evaluations for {model_type}")


def main():
    parser = argparse.ArgumentParser(description="View and query baseline evaluation metrics")
    parser.add_argument("--id", help="View specific evaluation by ID")
    parser.add_argument("--model", help="Filter by model type")
    parser.add_argument("--compare", nargs=2, metavar=("ID1", "ID2"), help="Compare two evaluations")
    parser.add_argument("--summary", action="store_true", help="Show recent evaluations summary")
    parser.add_argument("--limit", type=int, default=20, help="Limit number of results (default: 20)")

    args = parser.parse_args()

    viewer = MetricsViewer()

    if args.id:
        viewer.view_evaluation(args.id)
    elif args.compare:
        viewer.compare_evaluations(args.compare[0], args.compare[1])
    elif args.model:
        viewer.filter_by_model(args.model)
    elif args.summary:
        viewer.summary(limit=5)
    else:
        viewer.list_all(limit=args.limit)


if __name__ == "__main__":
    main()
