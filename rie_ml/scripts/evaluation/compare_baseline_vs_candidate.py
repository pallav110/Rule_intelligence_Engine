#!/usr/bin/env python3
"""
Baseline vs Candidate Model Comparison Script

Compares the deterministic baseline against the DistilBERT candidate model
on the frozen test dataset to determine if the candidate should be promoted.

Per specification Section 8.3.2:
"The candidate model is promoted only if it demonstrates measurable improvement
over the deterministic baseline according to the predefined acceptance criteria."

Usage:
    python compare_baseline_vs_candidate.py
"""

import json
from pathlib import Path
from typing import Dict, Any
import sys
from dataclasses import asdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from evaluation.metrics_storage import MetricsStorage


def print_header(text: str):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(text)
    print("=" * 80 + "\n")


def compare_metrics(
    baseline: Dict[str, Any],
    candidate: Dict[str, Any],
    metric_name: str,
    threshold: float = None
) -> Dict[str, Any]:
    """Compare a single metric between baseline and candidate"""
    baseline_val = baseline.get(metric_name, 0)
    candidate_val = candidate.get(metric_name, 0)

    improvement = candidate_val - baseline_val
    improvement_pct = (improvement / baseline_val * 100) if baseline_val > 0 else 0

    passes_threshold = True
    if threshold is not None:
        passes_threshold = candidate_val >= threshold

    result = {
        'baseline': baseline_val,
        'candidate': candidate_val,
        'improvement': improvement,
        'improvement_pct': improvement_pct,
        'passes_threshold': passes_threshold,
        'threshold': threshold
    }

    return result


def generate_promotion_decision(comparison: Dict[str, Any]) -> Dict[str, Any]:
    """Generate promotion decision based on comparison results"""

    # Acceptance criteria from specification Section 9.8
    acceptance_criteria = {
        'classification_accuracy': 0.85,
        'per_category_f1': 0.85,
        'calibration_error': 0.05,
    }

    passes = []
    failures = []

    # Check classification accuracy
    if comparison['classification']['accuracy']['passes_threshold']:
        passes.append("Classification Accuracy ≥ 85%")
    else:
        failures.append(f"Classification Accuracy {comparison['classification']['accuracy']['candidate']:.2%} < 85%")

    # Check if candidate outperforms baseline
    if comparison['classification']['accuracy']['improvement'] > 0:
        passes.append("Candidate outperforms baseline on accuracy")
    elif comparison['classification']['accuracy']['improvement'] < 0:
        failures.append("Candidate performs worse than baseline on accuracy")
    else:
        passes.append("Candidate matches baseline accuracy")

    # Promotion decision
    promote = len(failures) == 0

    return {
        'promote': promote,
        'status': 'APPROVED' if promote else 'REJECTED',
        'passes': passes,
        'failures': failures,
        'recommendation': (
            "✅ PROMOTE: Candidate meets acceptance criteria and demonstrates improvement"
            if promote else
            "❌ REJECT: Candidate does not meet all acceptance criteria"
        )
    }


def main():
    print_header("BASELINE VS CANDIDATE MODEL COMPARISON")

    # Initialize metrics storage
    storage = MetricsStorage()

    # Find baseline result
    print("📊 Loading evaluation results...")
    all_results = storage.list_results(limit=100)

    baseline_result = None
    candidate_result = None

    for result in all_results:
        if result['model_type'] == 'baseline_deterministic':
            baseline_result = storage.load_result(result['evaluation_id'])
            print(f"✅ Found baseline: {result['evaluation_id']}")
        elif result['model_type'] == 'ml_candidate_distilbert':
            candidate_result = storage.load_result(result['evaluation_id'])
            print(f"✅ Found candidate: {result['evaluation_id']}")

    if not baseline_result:
        print("❌ No baseline evaluation found")
        print("Run: python scripts/evaluate_baseline_with_storage.py --dataset test")
        sys.exit(1)

    if not candidate_result:
        print("❌ No candidate evaluation found")
        print("Run: python scripts/evaluate_distilbert_comprehensive.py --split test --save-to-storage")
        sys.exit(1)

    print()

    # Compare classification metrics
    print_header("CLASSIFICATION COMPARISON")

    baseline_clf = baseline_result.classification if hasattr(baseline_result, 'classification') else baseline_result['classification']
    candidate_clf = candidate_result.classification if hasattr(candidate_result, 'classification') else candidate_result['classification']

    # Convert to dicts if they're dataclass objects
    if hasattr(baseline_clf, '__dataclass_fields__'):
        from dataclasses import asdict
        baseline_clf = asdict(baseline_clf)
        candidate_clf = asdict(candidate_clf)

    accuracy_comp = compare_metrics(
        baseline_clf,
        candidate_clf,
        'accuracy',
        threshold=0.85
    )

    print(f"Accuracy:")
    print(f"  Baseline:   {accuracy_comp['baseline']:.2%}")
    print(f"  Candidate:  {accuracy_comp['candidate']:.2%}")
    print(f"  Improvement: {accuracy_comp['improvement']:+.2%}")
    print(f"  Threshold (≥85%): {'✅ PASS' if accuracy_comp['passes_threshold'] else '❌ FAIL'}")

    # Per-category F1 scores
    print(f"\nPer-Category F1 Scores:")
    baseline_f1 = baseline_clf.get('f1_score', {})
    candidate_f1 = candidate_clf.get('f1_score', {})

    for category in baseline_f1.keys():
        baseline_val = baseline_f1.get(category, 0)
        candidate_val = candidate_f1.get(category, 0)
        improvement = candidate_val - baseline_val

        print(f"  {category}:")
        print(f"    Baseline: {baseline_val:.4f}, Candidate: {candidate_val:.4f}, "
              f"Improvement: {improvement:+.4f}")

    # Other metrics
    print_header("OTHER METRICS COMPARISON")

    # Duplicate Detection
    print("Duplicate Detection:")
    baseline_dup = baseline_result.duplicate_detection if hasattr(baseline_result, 'duplicate_detection') else baseline_result['duplicate_detection']
    candidate_dup = candidate_result.duplicate_detection if hasattr(candidate_result, 'duplicate_detection') else candidate_result['duplicate_detection']

    if hasattr(baseline_dup, '__dataclass_fields__'):
        baseline_dup = asdict(baseline_dup)
        candidate_dup = asdict(candidate_dup)

    dup_precision = compare_metrics(
        baseline_dup,
        candidate_dup,
        'precision',
        threshold=0.90
    )
    dup_recall = compare_metrics(
        baseline_dup,
        candidate_dup,
        'recall',
        threshold=0.90
    )

    print(f"  Precision: Baseline {dup_precision['baseline']:.2%}, "
          f"Candidate {dup_precision['candidate']:.2%}, "
          f"Improvement {dup_precision['improvement']:+.2%}")
    print(f"  Recall: Baseline {dup_recall['baseline']:.2%}, "
          f"Candidate {dup_recall['candidate']:.2%}, "
          f"Improvement {dup_recall['improvement']:+.2%}")

    # Conflict Detection
    print("\nConflict Detection:")
    baseline_conf = baseline_result.conflict_detection if hasattr(baseline_result, 'conflict_detection') else baseline_result['conflict_detection']
    candidate_conf = candidate_result.conflict_detection if hasattr(candidate_result, 'conflict_detection') else candidate_result['conflict_detection']

    if hasattr(baseline_conf, '__dataclass_fields__'):
        baseline_conf = asdict(baseline_conf)
        candidate_conf = asdict(candidate_conf)

    conf_precision = compare_metrics(
        baseline_conf,
        candidate_conf,
        'precision',
        threshold=0.85
    )
    conf_recall = compare_metrics(
        baseline_conf,
        candidate_conf,
        'recall',
        threshold=0.85
    )

    print(f"  Precision: Baseline {conf_precision['baseline']:.2%}, "
          f"Candidate {conf_precision['candidate']:.2%}, "
          f"Improvement {conf_precision['improvement']:+.2%}")
    print(f"  Recall: Baseline {conf_recall['baseline']:.2%}, "
          f"Candidate {conf_recall['candidate']:.2%}, "
          f"Improvement {conf_recall['improvement']:+.2%}")

    # Processing Time
    print("\nProcessing Time:")
    baseline_time = baseline_result.average_processing_time_seconds if hasattr(baseline_result, 'average_processing_time_seconds') else baseline_result['average_processing_time_seconds']
    candidate_time = candidate_result.average_processing_time_seconds if hasattr(candidate_result, 'average_processing_time_seconds') else candidate_result['average_processing_time_seconds']
    time_diff = candidate_time - baseline_time

    print(f"  Baseline: {baseline_time:.4f}s per sample")
    print(f"  Candidate: {candidate_time:.4f}s per sample")
    print(f"  Difference: {time_diff:+.4f}s")

    # Generate promotion decision
    comparison = {
        'classification': {
            'accuracy': accuracy_comp
        }
    }

    decision = generate_promotion_decision(comparison)

    print_header("PROMOTION DECISION")

    print(f"Status: {decision['status']}")
    print(f"\n{decision['recommendation']}")

    if decision['passes']:
        print("\n✅ Acceptance Criteria Passed:")
        for criterion in decision['passes']:
            print(f"   • {criterion}")

    if decision['failures']:
        print("\n❌ Acceptance Criteria Failed:")
        for criterion in decision['failures']:
            print(f"   • {criterion}")

    # Save comparison report
    output_path = Path(__file__).parent.parent.parent / "models" / "distilbert_candidate" / "promotion_decision.json"
    baseline_eval_id = baseline_result.evaluation_id if hasattr(baseline_result, 'evaluation_id') else baseline_result['evaluation_id']
    candidate_eval_id = candidate_result.evaluation_id if hasattr(candidate_result, 'evaluation_id') else candidate_result['evaluation_id']

    with open(output_path, 'w') as f:
        json.dump({
            'decision': decision,
            'comparison': {
                'accuracy': accuracy_comp,
                'duplicate_precision': dup_precision,
                'duplicate_recall': dup_recall,
                'conflict_precision': conf_precision,
                'conflict_recall': conf_recall,
            },
            'baseline_evaluation_id': baseline_eval_id,
            'candidate_evaluation_id': candidate_eval_id,
            'timestamp': '2026-09-01T09:11:00Z',
        }, f, indent=2)

    print(f"\n💾 Promotion decision saved to {output_path}")

    print("\n" + "=" * 80)

    return 0 if decision['promote'] else 1


if __name__ == "__main__":
    sys.exit(main())
