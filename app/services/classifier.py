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

    def __init__(self, domain: str = None):
        """Initialize classifier with optional trained baseline model."""
        self.domain = domain or "ecommerce"
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
        # Gibberish / spam / noise is detected FIRST, before any model runs.
        # A trained model can otherwise assign high confidence to a random class
        # for nonsense input (e.g. a strong "business_rule_correction" prediction
        # for "asdf qwerty"). The deterministic heuristic wins over both model and regex.
        if self._is_gibberish(feedback):
            return {
                "feedback_type": "irrelevant_spam",
                "rule_category": "unknown",
                "is_actionable": False,
                "confidence": 0.95,
            }

        if self.is_trained and self.model and not self._fallback_to_regex:
            result = self._classify_with_model(feedback)
            # Fall back to regex if model confidence is low (< 0.6)
            # This helps catch non-actionable inputs that the model wasn't trained on
            if result["confidence"] < 0.6:
                return self._classify_with_regex(feedback)
            return result
        else:
            return self._classify_with_regex(feedback)

    def _is_gibberish(self, feedback: str) -> bool:
        """Heuristics to detect spam / gibberish / irrelevant input.

        Any of these conditions flags the input as noise:
        1. Very short feedback
        2. Common non-actionable single-word responses
        3. No alphabetic characters at all
        4. High non-alphanumeric ratio (lots of brackets, symbols, numbers)
        5. No recognizable English words (dictionary check)
        6. Keyboard-mash runs (e.g. "asdf qwerty zxcv") - real words are
           essentially never contiguous substrings of a single QWERTY home row,
           so this is precise with little false-positive risk.
        """
        feedback = feedback or ""
        feedback_lower = feedback.lower().strip()
        words = feedback_lower.split()
        alnum_count = sum(1 for c in feedback if c.isalnum())
        total_chars = len(feedback)
        non_alnum_ratio = (total_chars - alnum_count) / max(total_chars, 1)
        has_real_word = any(len(w) >= 3 and w.isalpha() and not self._is_keyboard_mash(w) for w in words)

        return (
            total_chars < 10
            or feedback_lower in ["ok", "yes", "no", "thanks", "thank you", "hi", "hello"]
            or not any(c.isalpha() for c in feedback)
            or non_alnum_ratio > 0.5  # More than 50% special chars = likely gibberish
            or (len(words) > 0 and not has_real_word and total_chars > 20)  # Long but no real words
            or self._is_keyboard_mash_run(words)
        )

    # QWERTY home rows. Real English words are rarely contiguous substrings of a
    # single row, so a word matching one is almost always keyboard-mashing.
    _QWERTY_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")

    @staticmethod
    def _is_keyboard_mash(word: str) -> bool:
        """True if a lowercased word is a contiguous substring of one QWERTY row."""
        if len(word) < 3 or not word.isalpha():
            return False
        return any(word in row for row in RealClassifier._QWERTY_ROWS)

    @staticmethod
    def _is_keyboard_mash_run(words) -> bool:
        """True if the input is dominated by keyboard-mash words.

        Requires at least two mash words to avoid flagging a single incidental
        match, and mash words must form at least half of the token stream so a
        mash alongside real signal (e.g. "asdf refund") is not mistaken for noise.
        """
        if len(words) < 2:
            return False
        mash_count = sum(1 for w in words if RealClassifier._is_keyboard_mash(w))
        return mash_count >= 2 and mash_count >= len(words) / 2

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
        feedback_lower = feedback.lower().strip()

        # Rule classification patterns
        rule_patterns = [
            (r"\b(revenue|metric|sum|total|count|average|amount)\b", "metric_definition", 0.90),
            (r"\b(exclude|include|restrict|should|must|contribute|not contribute)\b.*\b(revenue|metric|sum|total|count|average|amount)\b", "metric_definition", 0.90),
            (r"\b(should|must|only).*\b(access|view|edit|delete)\b", "access_scope_rule", 0.85),
            (r"\b(status|state|phase)\b.*\b(map|equals|is)\b", "status_mapping", 0.88),
            (r"\b(time|date|period|quarter|month|week)\b.*\b(rule|condition|apply)\b", "time_rule", 0.82),
            (r"\b(exclude|filter|remove|should not|must not).*\b(order|record|transaction)\b", "filter_rule", 0.92),
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

        # Check for non-actionable patterns (questions, unclear feedback)
        question_words = ["what", "how", "why", "explain", "describe", "who", "when", "where"]
        if any(word in feedback_lower.split() for word in question_words):
            # Check if it's a question about rules (should still be actionable)
            if "should" not in feedback_lower and "must" not in feedback_lower:
                feedback_type = "unclear_feedback"
                is_actionable = False
                confidence = 0.3  # Lower confidence for questions

        # Spam/irrelevant/gibberish handled by shared heuristic (already applied at
        # the top of classify()); kept here as a defensive re-check for direct callers.
        if self._is_gibberish(feedback):
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
