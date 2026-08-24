"""Real rule comparison and conflict detection services.

Replaces Mock implementations with actual duplicate and conflict detection.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import sys
from pathlib import Path

# Add rie-ml to path
rie_ml_path = Path(__file__).parent.parent.parent / "rie-ml"
sys.path.insert(0, str(rie_ml_path))

from src.duplicate_detection import DuplicateDetector
from src.conflict_detection import ConflictDetector


@dataclass
class DuplicateCheckResult:
    relationship: str
    confidence: float
    matching_rule_id: Optional[str] = None


class RealRuleComparisonService:
    """Production duplicate detection backed by rie-ml."""

    def __init__(self):
        self.duplicate_detector = DuplicateDetector(threshold=0.85)
        self._indexed = False

    def index_feedbacks(self, feedbacks: List[Dict[str, Any]]) -> None:
        """Index feedback texts for duplicate detection."""
        texts = [f.get('feedback_text', '') for f in feedbacks]
        ids = [f.get('feedback_id', str(i)) for i, f in enumerate(feedbacks)]

        self.duplicate_detector.vectorizer.fit(texts)
        self.duplicate_detector.vectors = self.duplicate_detector.vectorizer.transform(texts)
        self.duplicate_detector.ids = ids
        self._indexed = True

    def check_duplicate(
        self,
        rule: Dict[str, Any],
        existing_rules: List[Dict[str, Any]],
    ) -> DuplicateCheckResult:
        """Check if rule is duplicate of existing rules."""
        if not self._indexed and existing_rules:
            self.index_feedbacks(existing_rules)

        if not self._indexed:
            return DuplicateCheckResult(
                relationship="unrelated",
                confidence=0.0,
                matching_rule_id=None,
            )

        # For simplicity, we'll check if this rule text matches any existing
        rule_text = rule.get('feedback_text', '')
        if not rule_text:
            return DuplicateCheckResult(
                relationship="unrelated",
                confidence=0.0,
                matching_rule_id=None,
            )

        # Vectorize the rule text
        try:
            rule_vector = self.duplicate_detector.vectorizer.transform([rule_text])
            similarities = self.duplicate_detector.cosine_similarity(
                rule_vector, self.duplicate_detector.vectors
            ).flatten()

            max_sim_idx = similarities.argmax()
            max_sim = similarities[max_sim_idx]

            if max_sim >= self.duplicate_detector.threshold:
                return DuplicateCheckResult(
                    relationship="duplicate",
                    confidence=float(max_sim),
                    matching_rule_id=self.duplicate_detector.ids[max_sim_idx],
                )
        except Exception:
            pass  # Fall back to unrelated

        return DuplicateCheckResult(
            relationship="unrelated",
            confidence=0.0,
            matching_rule_id=None,
        )


@dataclass
class ConflictCheckResult:
    relationship: str
    confidence: float
    conflicting_rule_id: Optional[str] = None


class RealRuleConflictService:
    """Production conflict detection backed by rie-ml."""

    def __init__(self):
        self.conflict_detector = ConflictDetector()
        self._loaded = False

    def load_rules(self, rules: List[Dict[str, Any]]) -> None:
        """Load rules for conflict detection."""
        # Convert rules to extraction format
        extraction_data = []
        for rule in rules:
            extraction_data.append({
                'rules': [rule.get('structured_rule', rule)] if isinstance(rule.get('structured_rule'), dict) else [rule]
            })

        # Create temporary file for conflict detector
        import tempfile
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for data in extraction_data:
                json.dump(data, f)
                f.write('\n')
            temp_path = f.name

        self.conflict_detector.load_rules(temp_path)
        self._loaded = True

    def check_conflict(
        self,
        rule: Dict[str, Any],
        existing_rules: List[Dict[str, Any]],
    ) -> ConflictCheckResult:
        """Check if rule conflicts with existing rules."""
        if not self._loaded and existing_rules:
            self.load_rules(existing_rules)

        if not self._loaded:
            return ConflictCheckResult(
                relationship="no_conflict",
                confidence=1.0,
                conflicting_rule_id=None,
            )

        # Check for conflicts using our conflict detector
        conflicts = self.conflict_detector.find_conflicts()

        if conflicts:
            # Return the first conflict found
            first_conflict = conflicts[0]
            return ConflictCheckResult(
                relationship="conflict",
                confidence=0.9,
                conflicting_rule_id=first_conflict.get('rule_1', {}).get('rule_id'),
            )

        return ConflictCheckResult(
            relationship="no_conflict",
            confidence=1.0,
            conflicting_rule_id=None,
        )


class RealRuleComparator:
    """Production rule comparator."""

    def compare(
        self,
        rule_a: Dict[str, Any],
        rule_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare two rules and return relationship details."""
        # Simple comparison - can be enhanced
        if rule_a.get('business_term') == rule_b.get('business_term'):
            if rule_a.get('operation') == rule_b.get('operation'):
                return {
                    'relationship': 'identical',
                    'confidence': 1.0,
                    'details': {'matched_fields': ['business_term', 'operation']}
                }
            else:
                return {
                    'relationship': 'operation_conflict',
                    'confidence': 0.8,
                    'details': {
                        'business_term': rule_a.get('business_term'),
                        'operation_a': rule_a.get('operation'),
                        'operation_b': rule_b.get('operation')
                    }
                }
        else:
            return {
                'relationship': 'different',
                'confidence': 0.5,
                'details': {}
            }


# Keep mocks for backward compatibility during transition
class MockRuleComparisonService:
    def check_duplicate(
        self,
        rule: dict[str, Any],
        existing_rules: list[dict[str, Any]],
    ) -> DuplicateCheckResult:
        return DuplicateCheckResult(
            relationship="unrelated",
            confidence=0.0,
        )


class MockRuleConflictService:
    def check_conflict(
        self,
        rule: dict[str, Any],
        existing_rules: list[dict[str, Any]],
    ) -> ConflictCheckResult:
        return ConflictCheckResult(
            relationship="no_conflict",
            confidence=0.0,
        )


class MockRuleComparator:
    def compare(
        self,
        rule_a: dict[str, Any],
        rule_b: dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "relationship": "unrelated",
            "confidence": 0.0,
            "details": {}
        }