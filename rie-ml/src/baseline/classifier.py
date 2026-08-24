"""Baseline classifier for RIE-ML (tf-idf + logistic regression).

This implements the deterministic baseline that the backend expects
(see ``app/services/classifier.py`` MockClassifier / actual service).

Training data format (from ``dataset_generation/output/classification.jsonl``):
  {
    "feedback_id": "...",
    "feedback_text": "...",
    "feedback_type": "business_rule_correction" | ...,
    "rule_category": "metric_definition" | ...,
    "is_actionable": true | false,
    "requires_clarification": true | false,
    ...
  }

The classifier produces a single dict with those keys — ready for
``rie_ml.baseline.classifier.FeedbackClassificationContract.classify()``
to validate against.
"""

import json
import os
from typing import Dict, Any, List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multioutput import MultiOutputClassifier


class BaselineClassifier:
    """Deterministic TF-IDF + LR classifier for feedback."""

    def __init__(self, model_path: str | None = None):
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            lowercase=True,
            stop_words="english",
        )
        self.model = MultiOutputClassifier(
            LogisticRegression(max_iter=1000, class_weight="balanced")
        )
        self._fitted = False

        if model_path and os.path.exists(model_path):
            self.load(model_path)

    # ------------------------------------------------------------------
    #  Public API required by the backend contract
    # ------------------------------------------------------------------

    def train(self, data_path: str) -> None:
        """Train on a JSONL file that matches the dataset output format."""
        texts: List[str] = []
        labels: List[List[str]] = []  # each entry = [feedback_type, rule_category]

        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line.strip())
                texts.append(obj["feedback_text"])
                # We have two multi-label targets; collect both.
                labels.append([
                    obj.get("feedback_type", ""),
                    obj.get("rule_category", ""),
                ])

        X = self.vectorizer.fit_transform(texts)
        y = np.array(labels)  # shape (n_samples, 2)

        self.model.fit(X, y)
        self._fitted = True

    def classify(self, feedback: str, domain_context: dict | None = None) -> Dict[str, Any]:
        """Classify a single feedback text.

        Parameters
        ----------
        feedback: str
            Raw feedback text.
        domain_context: dict | None
            Ignored by the baseline but kept for contract compatibility.

        Returns
        -------
        dict
            ``feedback_type``, ``rule_category``, ``is_actionable``,
            ``requires_clarification``, ``confidence``.
        """
        if not self._fitted:
            raise RuntimeError("Classifier not trained. Call .train() first.")

        X = self.vectorizer.transform([feedback])
        preds = self.model.predict(X)[0]  # shape (2,)

        # Map numeric predictions back to strings via our fixed vocabulary
        type_map = {
            0: "business_rule_correction",
            1: "data_quality_issue",
            2: "access_rule",
            3: "filter_rule",
            4: "calculation_correction",
        }
        category_map = {
            0: "metric_definition",
            1: "filter_rule",
            2: "access_scope_rule",
            3: "calculation_correction",
            4: "column_meaning",
        }

        feedback_type = type_map.get(int(preds[0]), str(preds[0]))
        rule_category = category_map.get(int(preds[1]), str(preds[1]))

        # Simple heuristic for the remaining booleans
        is_actionable = feedback_type in {
            "business_rule_correction",
            "data_quality_issue",
        }
        requires_clarification = "unclear" in feedback.lower() or "?" in feedback

        confidence = float(np.max(np.abs(preds)))

        return {
            "feedback_type": feedback_type,
            "rule_category": rule_category,
            "is_actionable": is_actionable,
            "requires_clarification": requires_clarification,
            "confidence": round(confidence, 4),
        }

    # ------------------------------------------------------------------
    #  Persistence helpers
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Serialize vectorizer + model to ``path`` (simple JSON wrapper)."""
        import joblib  # type: ignore
        bundle = {
            "vectorizer": self.vectorizer,
            "model": self.model,
        }
        joblib.dump(bundle, path)

    def load(self, path: str) -> None:
        """Load a previously saved bundle."""
        import joblib  # type: ignore
        bundle = joblib.load(path)
        self.vectorizer = bundle["vectorizer"]
        self.model = bundle["model"]
        self._fitted = True