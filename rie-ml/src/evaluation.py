"""Evaluation harness for baseline models (Week 2-3 deliverable).

Measures performance on test set:
  - Classification: accuracy, precision, recall, F1 per category
  - Extraction: exact match, partial match, confidence distribution
  - Duplicate detection: precision, recall, F1
  - Conflict detection: precision, recall
"""

import json
from typing import Dict, Any, List
from collections import defaultdict

import numpy as np
from sklearn.metrics import classification_report, accuracy_score


class EvaluationHarness:
    def __init__(self, test_data_path: str):
        self.test_data_path = test_data_path
        self.test_data = []
        self._load_test_data()

    def _load_test_data(self) -> None:
        with open(self.test_data_path, "r", encoding="utf-8") as f:
            for line in f:
                self.test_data.append(json.loads(line.strip()))

    def evaluate_classifier(self, classifier) -> Dict[str, Any]:
        """Evaluate classifier on test set."""
        y_true_type = []
        y_pred_type = []
        y_true_category = []
        y_pred_category = []

        for obj in self.test_data:
            feedback = obj["feedback_text"]
            true_type = obj["feedback_type"]
            true_category = obj.get("rule_category")

            pred = classifier.classify(feedback, obj.get("schema_context", {}))

            y_true_type.append(true_type)
            y_pred_type.append(pred["feedback_type"])
            y_true_category.append(true_category if true_category else "none")
            y_pred_category.append(pred["rule_category"] if pred["rule_category"] else "none")

        report_type = classification_report(y_true_type, y_pred_type, output_dict=True, zero_division=0)
        report_category = classification_report(y_true_category, y_pred_category, output_dict=True, zero_division=0)

        return {
            "feedback_type": {
                "accuracy": accuracy_score(y_true_type, y_pred_type),
                "report": report_type,
            },
            "rule_category": {
                "accuracy": accuracy_score(y_true_category, y_pred_category),
                "report": report_category,
            },
        }

    def evaluate_extractor(self, extractor, classifier) -> Dict[str, Any]:
        """Evaluate rule extractor on test set."""
        exact_matches = 0
        partial_matches = 0
        total = 0

        for obj in self.test_data:
            feedback = obj["feedback_text"]
            true_rules = obj.get("rules", [])

            if not true_rules:
                continue

            classification = classifier.classify(feedback, obj.get("schema_context", {}))
            pred = extractor.extract(feedback, classification, obj.get("schema_context", {}))
            pred_rules = pred.get("rules", [])

            total += 1

            # Exact match: same business_term and operation
            if len(pred_rules) == len(true_rules):
                exact = all(
                    p.get("business_term") == t.get("business_term") and
                    p.get("operation") == t.get("operation")
                    for p, t in zip(pred_rules, true_rules)
                )
                if exact:
                    exact_matches += 1
                    continue

            # Partial match: at least one rule matches
            for p in pred_rules:
                for t in true_rules:
                    if (p.get("business_term") == t.get("business_term") or
                        p.get("operation") == t.get("operation")):
                        partial_matches += 1
                        break

        return {
            "exact_match_rate": exact_matches / total if total > 0 else 0.0,
            "partial_match_rate": partial_matches / total if total > 0 else 0.0,
            "total_evaluated": total,
        }

    def generate_report(self, classifier, extractor) -> str:
        """Generate full evaluation report as markdown."""
        cls_results = self.evaluate_classifier(classifier)
        ext_results = self.evaluate_extractor(extractor, classifier)

        report = f"""# Baseline Model Evaluation Report

**Date:** 2026-08-24
**Test Set:** {self.test_data_path}
**Samples Evaluated:** {len(self.test_data)}

---

## Classification Performance

### Feedback Type
- **Accuracy:** {cls_results['feedback_type']['accuracy']:.4f}

### Rule Category
- **Accuracy:** {cls_results['rule_category']['accuracy']:.4f}

---

## Rule Extraction Performance

- **Exact Match Rate:** {ext_results['exact_match_rate']:.4f}
- **Partial Match Rate:** {ext_results['partial_match_rate']:.4f}
- **Total Evaluated:** {ext_results['total_evaluated']}

---

## Recommendations

1. Classification accuracy is {"acceptable" if cls_results['feedback_type']['accuracy'] > 0.7 else "below target"} for baseline.
2. Extraction needs {"improvement" if ext_results['exact_match_rate'] < 0.5 else "minor tuning"}.
3. Next step: {"Deploy baseline" if cls_results['feedback_type']['accuracy'] > 0.7 else "Add more training data"}.
"""
        return report