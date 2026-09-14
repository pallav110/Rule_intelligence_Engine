"""Classification service for business feedback.

Uses trained baseline classifier (TF-IDF + Logistic Regression) for deterministic
classification with fallback to regex patterns if model unavailable.
"""

import re
import os
from typing import Dict, Any, Optional
from pathlib import Path


# ---------------------------------------------------------------------------
# Rare-class pre-gates (Spec v0.2.0)
# ---------------------------------------------------------------------------
# Both classification engines saturate on the majority business_rule class:
# the DistilBERT head was trained on starved rare-class seeds, and the regex
# fallback assigns business_rule to almost every rule-shaped sentence.
# issue_report / feature_request / question are non-actionable intents (their
# seeds all carry is_actionable=False), so asserting them deterministically —
# like the irrelevant_spam pre-filter — stops them leaking into business_rule
# and then toward review routing. These frames are deliberately narrow: they
# only fire on unambiguous lexical signals the annotated seeds actually use.
# A rule-signal (exclude/include/should + a schema noun) yields to the model
# ("trusted middle") so a real rule is never stolen. The rule-signal guard
# does NOT apply to the question gate: an interrogative "should we exclude…?"
# about rule semantics is exactly what the taxonomy calls a question
# (requires_clarification), so gating it is the desired behavior.

_RULE_SIGNAL_RE = re.compile(
    r"\b(exclude|include|should|must|filter|count|sum|calculate)\b.{0,60}"
    r"\b(order|record|transaction|invoice|revenue|subscription|ticket|report|"
    r"refund|metric|column|table)\b",
    re.IGNORECASE,
)

_FR_FRAMES = (
    r"\bplease\s+(add|give|assign|create|notify|alert|show)\b",
    r"\bkindly\s+(add|give)\b",
    r"\bcan\s+we\s+get\b",
    r"\bcould\s+(you|we)\s+(add|get|provide)\b",
    r"\b(it|that)\s+would\s+be\s+(nice|helpful|great|good)\s+to\b",
    r"\bwould\s+help\s+to\b",
    r"\bplease\s+give\b.{0,40}\baccess\b",
)

_IR_FRAMES = (
    r"\b(is|are|reads|shows|returns|counts?|renders?|loads?|opens?|landed\s+on)\s+"
    r"\w{0,4}\s*(wrong|broken|overlapping|missing|stuck|slow|incorrect|off|blank)\b",
    r"\b(seems?|looks?|appears?)\s+(to\s+be\s+)?(wrong|broken|missing|incorrect|stuck|slow|off)\b",
    r"\bkeeps?\s+\w+ing\b",
    r"\b\w+ing\s+to\s+the\s+wrong\b",
    r"\b\w+ing\s+(very\s+)?slow(ly)?\b",
    r"\bis\s+the\s+\w+\s+(count|value|number|metric)\s+(wrong|off|incorrect)\b",
)

# An issue report must name the thing that is broken (button/dashboard/email/
# report/timer/count/…). This keeps "Orders that are missing" — which is rule
# wording, not a UI bug — from being gated on "are missing" alone.
_IR_ARTIFACT_RE = re.compile(
    r"\b(button|dashboard|email|report|timer|invoice|count|metric|page|screen|"
    r"table|filter|banner|chart|notification|backlog|sla|csat|tab|widget|"
    r"checkbox|window|spinner|panel|console)\b",
    re.IGNORECASE,
)

# Question gate requires a literal terminal "?" AND one of these interrogative
# frames. Not subject to _RULE_SIGNAL_RE (see header comment).
_Q_FRAMES = (
    r"\bhow\s+(should|do|does|would|is|are)\b",
    r"\bwhat\s+(does|counts\s+as|qualifies\s+as|is|defines|should)\b",
    r"\bwhy\s+(is|does|do|are|would|should)\b",
    r"\bclarify\s+whether\b",
    r"\bwhether\b",
    r"\bdoes\s+(?:[\w.]+\s+){0,4}(include|exclude|represent|count|mean|signify|track)\b",
    r"\b(is|are)\s+(?:[\w.]+\s+){0,4}(inclusive|exclusive|counted|included|billed|part\s+of|subject\s+to)\b",
    r"\bshould\s+we\s+(treat|exclude|include|count|filter|use)\b",
    r"\bwhich\s+(applies|counts|should|one|rule)\b",
    r"\bwhat\s+should\s+we\b",
)

_FR_RE = tuple(re.compile(p, re.IGNORECASE) for p in _FR_FRAMES)
_IR_RE = tuple(re.compile(p, re.IGNORECASE) for p in _IR_FRAMES)
_Q_RE = tuple(re.compile(p, re.IGNORECASE) for p in _Q_FRAMES)


def rare_class_gate(feedback) -> Optional[dict]:
    """Deterministically route an unambiguous non-actionable intent.

    Returns a classification dict for feature_request / issue_report / question,
    or None when the input is not clearly one of those (the model arbitrates).

    Runs AFTER the spam/gibberish pre-filter and BEFORE any model — same
    philosophy as the irrelevant_spam gate. Each returned dict carries
    is_actionable=False so the pipeline routes it to N/A / clarification, never
    to review as a rule.
    """
    if not feedback or not isinstance(feedback, str):
        return None
    text = feedback.lower().strip()
    has_rule_signal = bool(_RULE_SIGNAL_RE.search(text))
    if has_rule_signal and not any(p.search(text) for p in _FR_RE):
        # Genuine rule wording with no feature-request frame -> leave to the
        # model rather than risk stealing a real rule.
        return None
    if any(p.search(text) for p in _FR_RE):
        return {"feedback_type": "feature_request", "rule_category": "none",
                "is_actionable": False, "confidence": 0.9}
    if _IR_ARTIFACT_RE.search(text) and any(p.search(text) for p in _IR_RE):
        return {"feedback_type": "issue_report", "rule_category": "none",
                "is_actionable": False, "confidence": 0.9}
    # Question frame fires on an interrogative + terminal "?". The one
    # exception: "clarify whether X is …" is unambiguous on its own and the
    # annotated seeds for it (CS/SAAS colmean_002) don't end in a question mark,
    # so that frame gates without requiring "?".
    strong_q = bool(re.search(r"\bclarify\s+whether\b", text))
    if strong_q or (text.endswith("?") and any(p.search(text) for p in _Q_RE)):
        return {"feedback_type": "question", "rule_category": "none",
                "is_actionable": False, "confidence": 0.9,
                "requires_clarification": True}
    return None


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

            # Use unified model (new approach — works for all domains)
            # New location (dataset regen); fall back to legacy flat path
            model_path = Path(__file__).parent.parent.parent / "rie_ml" / "models" / "baseline" / "baseline_classifier_unified.pkl"
            if not model_path.exists():
                model_path = Path(__file__).parent.parent.parent / "rie_ml" / "models" / "baseline_classifier_unified.pkl"

            if model_path.exists():
                bundle = joblib.load(str(model_path))
                self.vectorizer = bundle.get("vectorizer")
                self.model = bundle.get("model")
                self.is_trained = True
                print(f"✅ Loaded unified baseline classifier (cross-domain) from {model_path}")
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

        # Rare-class pre-gate (after spam, before model): assert an unambiguous
        # feature_request / issue_report / question deterministically. Without
        # this, the starved-rare-class model and regex both collapse them into
        # business_rule, and non-actionable intents leak toward rule routing.
        gate = rare_class_gate(feedback)
        if gate:
            return gate

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
            # Noise-token dominance: catches gibberish that smuggles real words
            # ("xj29 revenue zzz qqq cancelled blahhh 9281 asdfgh") past the
            # no-real-word and mash-run checks above.
            or (len(words) >= 3 and sum(1 for w in words if self._noise_token(w)) >= len(words) / 2)
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

    @staticmethod
    def _noise_token(word: str) -> bool:
        """True if a token reads as gibberish on its own: keyboard-mash, a run of
        3+ identical characters ("zzz", "qqq", "blahhh"), a letter+digit jumble
        ("xj29"), or a standalone number of 3+ digits ("9281"). Real rule
        phrasing rarely trips these — "30"/"90"/"US"/"order_id" are classed clean."""
        w = word.strip(".,;:!?\"'()[]{}%$@#/\\|*^~=+-_")
        return (
            (not w)
            or RealClassifier._is_keyboard_mash(w)
            or bool(re.search(r"([a-zA-Z0-9])\1{2,}", w))
            or (bool(re.search(r"[a-zA-Z]", w)) and bool(re.search(r"\d", w)))
            or (w.isdigit() and len(w) >= 3)
        )

    def _classify_with_model(self, feedback: str) -> Dict[str, Any]:
        """Classify using trained baseline model."""
        try:
            import numpy as np

            # Transform and predict
            X = self.vectorizer.transform([feedback])
            preds = self.model.predict(X)[0]

            # NEW TAXONOMY v0.2.0 (5-class feedback_type, 6-class rule_category)
            # NOTE: the baseline model was trained with string labels directly,
            # so most predictions arrive as strings. The int->label maps below are
            # only for the degenerate numeric-encoding case and must match the
            # training label order exactly.
            type_map = {
                0: "business_rule",
                1: "issue_report",
                2: "feature_request",
                3: "question",
                4: "general_feedback",
            }
            category_map = {
                0: "metric_definition",
                1: "filter_rule",
                2: "mapping_rule",
                3: "access_rule",
                4: "join_rule",
                5: "data_quality_rule",
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

            # NEW TAXONOMY v0.2.0: only business_rule is actionable (matches
            # src/baseline/classifier.py). issue_report / feature_request /
            # question / general_feedback are not rule-carriers.
            is_actionable = feedback_type == "business_rule"

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
        """Classify using regex patterns (fallback).

        NEW TAXONOMY v0.2.0 — every label emitted here matches the authoritative
        5-class feedback_type / 6-class rule_category. (Older names like
        access_scope_rule / status_mapping / calculation_correction are removed.)
        """
        feedback_lower = feedback.lower().strip()

        # Rule classification patterns -> NEW 6-class rule_category
        rule_patterns = [
            (r"\b(revenue|metric|sum|total|count|average|amount)\b", "metric_definition", 0.90),
            (r"\b(exclude|include|restrict|should|must|contribute|not contribute)\b.*\b(revenue|metric|sum|total|count|average|amount)\b", "metric_definition", 0.90),
            (r"\b(should|must|only).*\b(access|view|edit|delete)\b", "access_rule", 0.85),
            (r"\b(status|state|phase)\b.*\b(map|equals|is)\b", "mapping_rule", 0.88),
            (r"\b(exclude|filter|remove|should not|must not).*\b(order|record|transaction)\b", "filter_rule", 0.92),
            (r"\b(duplicate|missing|incomplete|null|empty|invalid)\b", "data_quality_rule", 0.85),
            (r"\b(join|link|combine|merge)\b.*\b(table|record|id)\b", "join_rule", 0.82),
            (r"\b(calculate|compute|derive)\b.*\b(from|by|using)\b", "metric_definition", 0.85),
        ]

        feedback_type = "business_rule"
        rule_category = "metric_definition"
        confidence = 0.5
        is_actionable = False

        # Check for rule patterns
        for pattern, category, conf in rule_patterns:
            if re.search(pattern, feedback_lower):
                rule_category = category
                confidence = conf
                is_actionable = True
                feedback_type = "business_rule"
                break

        # Check for non-actionable patterns (questions, unclear feedback)
        question_words = ["what", "how", "why", "explain", "describe", "who", "when"]
        # "where" is often used as a condition indicator in SQL-like feedback ("where status = cancelled")
        # so we exclude it from question detection
        if any(word in feedback_lower.split() for word in question_words):
            # Check if it's a question about rules (should still be actionable)
            if "should" not in feedback_lower and "must" not in feedback_lower:
                # NEW TAXONOMY v0.2.0: unclear_feedback -> question
                feedback_type = "question"
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
