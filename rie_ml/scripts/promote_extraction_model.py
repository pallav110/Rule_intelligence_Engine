#!/usr/bin/env python3
"""
Promotion Decision for Rule Extraction Model

Determines whether to promote DistilBERT candidate or stick with baseline.
Follows the same model lifecycle as classification: CANDIDATE → APPROVED → ACTIVE
"""

import json
from pathlib import Path
from datetime import datetime


def make_promotion_decision(evaluation_results, threshold_metrics=None):
    """
    Decide whether to promote DistilBERT candidate to APPROVED status.

    Args:
        evaluation_results: Results from evaluate_extraction_model.py
        threshold_metrics: Custom thresholds for promotion

    Returns:
        Decision with rationale
    """
    if threshold_metrics is None:
        threshold_metrics = {
            'min_macro_f1': 0.75,  # 75% macro F1
            'min_token_accuracy': 0.90,  # 90% token accuracy
            'prefer_candidate_if_f1_above': 0.85  # Auto-approve if macro F1 > 85%
        }

    # Extract metrics
    token_accuracy = evaluation_results.get('overall_accuracy', 0)
    macro_f1 = evaluation_results.get('macro_f1', 0)

    decision = {
        'timestamp': datetime.now().isoformat(),
        'model_type': 'distilbert_token_extractor',
        'status': 'PENDING',
        'rationale': '',
        'metrics': {
            'token_accuracy': token_accuracy,
            'macro_f1': macro_f1,
        },
        'thresholds': threshold_metrics
    }

    # Decision logic
    if macro_f1 >= threshold_metrics['prefer_candidate_if_f1_above']:
        decision['status'] = 'APPROVED'
        decision['rationale'] = (
            f"DistilBERT candidate achieves {macro_f1:.1%} macro F1, "
            f"exceeding auto-approval threshold of {threshold_metrics['prefer_candidate_if_f1_above']:.0%}. "
            f"Token accuracy: {token_accuracy:.1%}. Promotes to APPROVED status."
        )
    elif macro_f1 >= threshold_metrics['min_macro_f1'] and token_accuracy >= threshold_metrics['min_token_accuracy']:
        decision['status'] = 'APPROVED'
        decision['rationale'] = (
            f"DistilBERT candidate achieves {macro_f1:.1%} macro F1 and {token_accuracy:.1%} token accuracy, "
            f"meeting minimum thresholds (F1≥{threshold_metrics['min_macro_f1']:.0%}, Accuracy≥{threshold_metrics['min_token_accuracy']:.0%}). "
            f"Candidate demonstrates strong performance for promotion to APPROVED."
        )
    else:
        decision['status'] = 'REJECTED'
        decision['rationale'] = (
            f"DistilBERT candidate achieves {macro_f1:.1%} macro F1 and {token_accuracy:.1%} token accuracy. "
            f"Does not meet promotion criteria (F1≥{threshold_metrics['min_macro_f1']:.0%}, Accuracy≥{threshold_metrics['min_token_accuracy']:.0%}). "
            f"Baseline remains active."
        )

    decision['recommendation'] = (
        'PROMOTE_TO_APPROVED' if decision['status'] == 'APPROVED' else 'KEEP_BASELINE_ACTIVE'
    )

    return decision


def save_promotion_decision(decision, output_dir):
    """Save promotion decision to file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    decision_file = output_dir / 'PROMOTION_DECISION_EXTRACTION.json'
    with open(decision_file, 'w') as f:
        json.dump(decision, f, indent=2)

    # Also save as text for readability
    text_file = output_dir / 'PROMOTION_DECISION_EXTRACTION.txt'
    with open(text_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("RULE EXTRACTION MODEL PROMOTION DECISION\n")
        f.write("="*80 + "\n\n")
        f.write(f"Decision Date: {decision['timestamp']}\n")
        f.write(f"Model: {decision['model_type']}\n")
        f.write(f"Status: {decision['status']}\n")
        f.write(f"Recommendation: {decision['recommendation']}\n\n")
        f.write("METRICS:\n")
        f.write(f"  Token Accuracy: {decision['metrics'].get('token_accuracy', 0):.1%}\n")
        f.write(f"  Macro F1: {decision['metrics'].get('macro_f1', 0):.4f}\n\n")
        f.write("RATIONALE:\n")
        f.write(f"  {decision['rationale']}\n\n")
        f.write("="*80 + "\n")

    print(f"\n✅ Promotion decision saved to {decision_file}")
    print(f"✅ Text version saved to {text_file}")

    return decision_file, text_file


def print_promotion_decision(decision):
    """Print promotion decision to console."""
    print("\n" + "="*80)
    print("RULE EXTRACTION MODEL PROMOTION DECISION")
    print("="*80)
    print(f"\nDecision: {decision['status']}")
    print(f"Recommendation: {decision['recommendation']}")
    print(f"\nMetrics:")
    print(f"  Token Accuracy: {decision['metrics'].get('token_accuracy', 0):.1%}")
    print(f"  Macro F1: {decision['metrics'].get('macro_f1', 0):.4f}")
    print(f"\nRationale:")
    print(f"  {decision['rationale']}")
    print("\n" + "="*80)


def main():
    """Load evaluation results and make promotion decision."""
    eval_results_file = Path(__file__).parent.parent / "models" / "distilbert_token_extractor" / "token_evaluation_results.json"

    if not eval_results_file.exists():
        print(f"❌ Evaluation results not found: {eval_results_file}")
        print("   Run evaluate_extraction_model.py first")
        return

    with open(eval_results_file, 'r') as f:
        evaluation_results = json.load(f)

    decision = make_promotion_decision(evaluation_results)
    print_promotion_decision(decision)

    output_dir = Path(__file__).parent.parent / "models" / "distilbert_token_extractor"
    save_promotion_decision(decision, output_dir)

    return decision


if __name__ == "__main__":
    main()
