"""Classification service for business feedback.

Uses trained baseline classifier (TF-IDF + Logistic Regression) for deterministic
classification with fallback to regex patterns if model unavailable.
"""

import re
import os
from typing import Dict, Any
from pathlib import Path


class RealClassifier:
    """Classify business feedback into types and categories."""

    def __init__(self, domain: str = "ecommerce"):
        """Initialize classifier with optional trained baseline model."""
        self.domain = domain
        self.is_trained = False
        self.model = None
        self.vectorizer = None
        self._fallback_to_regex = False

        # Try to load trained baseline model
        self._load_baseline_model()

    def _load_baseline_model(self):
        """Load trained unified baseline classifier."""
        try:
            import joblib

            # Use unified model (new approach - works for all domains)
            model_path = Path(__file__).parent.parent.parent / "rie_ml" / "models" / "baseline_classifier_unified.pkl"

            if model_path.exists():
                bundle = joblib.load(str(model_path))
                self.vectorizer = bundle.get("vectorizer")
                self.model = bundle.get("model")
                self.is_trained = True
                print(f"✅ Loaded unified baseline classifier (cross-domain)")
            else:
                print(f"⚠️  No unified model found at {model_path}, using regex fallback")
                self._fallback_to_regex = True
        except Exception as e:
            print(f"⚠️  Failed to load unified model: {e}, using regex fallback")
            self._fallback_to_regex = True

    def classify(
        self, feedback: str, domain_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Classify feedback text using baseline model or regex patterns.

        Returns:
            {
                "feedback_type": "business_rule_correction|unclear_feedback|...",
                "rule_category": "metric_definition|filter_rule|...",
                "is_actionable": bool,
                "confidence": 0.0-1.0
            }
        """
        if self.is_trained and self.model and not self._fallback_to_regex:
            return self._classify_with_model(feedback)
        else:
            return self._classify_with_regex(feedback)

    def _classify_with_model(self, feedback: str) -> Dict[str, Any]:
        """Classify using trained baseline model."""
        try:
            import numpy as np

            # Transform and predict
            X = self.vectorizer.transform([feedback])
            preds = self.model.predict(X)[0]

            # Map predictions to labels
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

            # Handle both string and numeric predictions
            try:
                pred_type = int(preds[0])
                feedback_type = type_map.get(pred_type, str(preds[0]))
            except (ValueError, TypeError):
                feedback_type = str(preds[0])

            try:
                pred_cat = int(preds[1])
                rule_category = category_map.get(pred_cat, str(preds[1]))
            except (ValueError, TypeError):
                rule_category = str(preds[1])

            # Compute confidence from probabilities
            try:
                proba = self.model.predict_proba(X)
                confidence = float(np.mean([np.max(p) for p in proba]))
            except AttributeError:
                confidence = 0.75 if len(feedback) > 20 else 0.5

            is_actionable = feedback_type in {
                "business_rule_correction",
                "data_quality_issue",
                "access_rule",
                "filter_rule",
                "calculation_correction",
            }

            return {
                "feedback_type": feedback_type,
                "rule_category": rule_category,
                "is_actionable": is_actionable,
                "confidence": round(confidence, 4),
            }
        except Exception as e:
            print(f"⚠️  Model prediction failed: {e}, falling back to regex")
            return self._classify_with_regex(feedback)

    def _classify_with_regex(self, feedback: str) -> Dict[str, Any]:
        """Classify using regex patterns (fallback)."""
        feedback_lower = feedback.lower()

        # Rule classification patterns
        rule_patterns = [
            (r"\b(revenue|metric|sum|total|count|average|amount)\b.*\b(exclude|include|restrict)\b", "metric_definition", 0.90),
            (r"\b(should|must|only).*\b(access|view|edit|delete)\b", "access_scope_rule", 0.85),
            (r"\b(status|state|phase)\b.*\b(map|equals|is)\b", "status_mapping", 0.88),
            (r"\b(time|date|period|quarter|month|week)\b.*\b(rule|condition|apply)\b", "time_rule", 0.82),
            (r"\b(exclude|filter|remove).*\b(order|record|transaction)\b", "filter_rule", 0.92),
            (r"\b(calculate|compute|derive)\b.*\b(from|by|using)\b", "calculation_correction", 0.85),
        ]

        feedback_type = "business_rule_correction"
        rule_category = "metric_definition"
        confidence = 0.5
        is_actionable = False

        # Check for rule patterns
        for pattern, category, conf in rule_patterns:
            if re.search(pattern, feedback_lower):
                rule_category = category
                confidence = conf
                is_actionable = True
                feedback_type = "business_rule_correction"
                break

        # Check for non-actionable patterns
        if any(word in feedback_lower for word in ["what", "how", "why", "explain", "describe"]):
            if "should" not in feedback_lower and "must" not in feedback_lower:
                feedback_type = "unclear_feedback"
                is_actionable = False
                confidence = 0.4

        # Check for spam/irrelevant
        if len(feedback) < 10 or feedback_lower in ["ok", "yes", "no", "thanks"]:
            feedback_type = "irrelevant_spam"
            is_actionable = False
            confidence = 0.95

        return {
            "feedback_type": feedback_type,
            "rule_category": rule_category,
            "is_actionable": is_actionable,
            "confidence": confidence,
        }

    def train(self, training_data, labels):
        """Train classifier (not used with baseline model)."""
        self.is_trained = True
        return {"status": "using_baseline_model"}
