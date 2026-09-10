#!/usr/bin/env python3
"""Register baseline deterministic model in the registry

Registers all baseline models that were evaluated, creating a complete
registry with both baseline and ML candidate models for comparison.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from model_registry import ModelRegistry, ModelType, ModelStatus
from evaluation.metrics_storage import MetricsStorage


def register_baseline_models():
    """Register all baseline deterministic models"""

    registry = ModelRegistry()
    storage = MetricsStorage()

    print("📋 Loading baseline evaluation results...")
    all_results = storage.list_results(limit=100)

    baseline_results = [
        (result['evaluation_id'], storage.load_result(result['evaluation_id']))
        for result in all_results
        if result['model_type'] == 'baseline_deterministic'
    ]

    if not baseline_results:
        print("⚠️  No baseline evaluations found")
        return []

    registered_models = []

    for eval_id, baseline_result in baseline_results:
        print(f"\n📝 Registering baseline: {eval_id}")

        # Extract evaluation metrics
        evaluation_metrics = {
            "feedback_type_accuracy": baseline_result.classification.accuracy,
            "feedback_type_precision": sum(
                baseline_result.classification.precision.values()
            ) / len(baseline_result.classification.precision),
            "feedback_type_recall": sum(
                baseline_result.classification.recall.values()
            ) / len(baseline_result.classification.recall),
            "evaluation_id": baseline_result.evaluation_id,
            "dataset_size": baseline_result.dataset_size,
            "dataset_split": baseline_result.dataset_split
        }

        # Register the baseline model
        metadata = registry.register_model(
            model_name="baseline-deterministic-classifier",
            model_type=ModelType.BASELINE_DETERMINISTIC,
            version="1.0.0",  # All baselines are same version
            model_path="N/A - Deterministic Rules",
            created_by="baseline_pipeline",
            description="Deterministic baseline classifier using rule-based extraction",
            tags=["baseline", "deterministic", "rules", "reference"],
            training_config={
                "approach": "rule_based",
                "feedback_type_rules": 8,
                "classification_method": "pattern_matching",
                "extraction_method": "regex_and_nlp"
            },
            evaluation_metrics=evaluation_metrics,
            acceptance_criteria_passed=False,  # Baseline is reference, not accepted
            notes=f"Baseline deterministic model for comparison. "
                  f"Accuracy: {evaluation_metrics['feedback_type_accuracy']:.2%}. "
                  f"Serves as reference point for ML candidate evaluation."
        )

        print(f"✅ Registered baseline model")
        print(f"   Model ID: {metadata.model_id}")
        print(f"   Accuracy: {evaluation_metrics['feedback_type_accuracy']:.2%}")

        registered_models.append(metadata)

    return registered_models


def show_registry_comparison():
    """Display comparison of registered models"""
    registry = ModelRegistry()

    print("\n" + "="*80)
    print("MODEL REGISTRY - BASELINE vs CANDIDATE COMPARISON")
    print("="*80)

    for model_name, versions in registry._index.items():
        print(f"\n📦 {model_name}")
        print("-" * 80)

        # Sort by creation date, newest first
        sorted_versions = sorted(versions, key=lambda v: v.created_at, reverse=True)

        for v in sorted_versions:
            status_icon = {
                "production": "🟢",
                "staging": "🟡",
                "experimental": "⚪",
                "deprecated": "🔴",
                "archived": "⚫"
            }.get(v.status.value, "❓")

            accuracy = v.evaluation_metrics.get('feedback_type_accuracy', 'N/A')
            acc_str = f"{accuracy:.2%}" if isinstance(accuracy, float) else str(accuracy)

            print(f"\n  {status_icon} v{v.version} - {v.model_type.value}")
            print(f"     Status: {v.status.value}")
            print(f"     ID: {v.model_id}")
            print(f"     Accuracy: {acc_str}")
            print(f"     Created: {v.created_at}")
            print(f"     Type: {v.model_type.value}")

    print("\n" + "="*80)


def generate_registry_report():
    """Generate comprehensive registry report"""
    registry = ModelRegistry()

    report = {
        "timestamp": "2026-09-01T09:30:00Z",
        "registry_summary": {
            "total_models": len(registry._index),
            "total_versions": sum(len(v) for v in registry._index.values())
        },
        "models": {}
    }

    for model_name, versions in registry._index.items():
        model_data = []
        for v in versions:
            model_data.append({
                "id": v.model_id,
                "version": v.version,
                "status": v.status.value,
                "type": v.model_type.value,
                "created_at": v.created_at,
                "updated_at": v.updated_at,
                "accuracy": v.evaluation_metrics.get('feedback_type_accuracy', 'N/A'),
                "acceptance_criteria_passed": v.acceptance_criteria_passed
            })
        report["models"][model_name] = model_data

    # Save report
    report_path = Path(__file__).parent.parent.parent / "models" / "registry" / "registry_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n💾 Registry report saved to {report_path}")
    return report


def main():
    print("="*80)
    print("BASELINE MODEL REGISTRATION")
    print("="*80)

    baseline_models = register_baseline_models()

    if baseline_models:
        print(f"\n✅ Registered {len(baseline_models)} baseline model(s)")
    else:
        print("\n⚠️  No baseline models to register")

    # Show comparison
    show_registry_comparison()

    # Generate report
    report = generate_registry_report()

    print("\n" + "="*80)
    print("✅ BASELINE REGISTRATION COMPLETE")
    print("="*80)

    return 0 if baseline_models else 1


if __name__ == "__main__":
    sys.exit(main())
