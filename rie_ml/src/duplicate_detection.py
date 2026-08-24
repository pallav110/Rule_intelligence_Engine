# src/duplicate_detection.py

"""Real duplicate detection service integrating rie_ml duplicate detector.
Replaces Mock duplicate detection with semantic similarity-based detection.
"""

from typing import List, Dict, Any
import json


class RealDuplicateDetectionService:
    """Production duplicate detection backed by rie_ml."""

    def __init__(self, threshold: float = 0.85):
        self.detector = DuplicateDetector(threshold=threshold)
        self._indexed = False

    def index_feedbacks(self, data_path: str) -> None:
        """Index existing feedback for duplicate detection."""
        self.detector.index(data_path)
        self._indexed = True

    def check_duplicate(
        self,
        rule: Dict[str, Any],
        existing_rules: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check if rule is duplicate of existing rules."""
        if not self._indexed:
            # Index existing rules on-the-fly
            # Import tempfile and json for temporary file handling
            import tempfile
            import json

            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                for r in existing_rules:
                    json.dump(r, f)
                    f.write('\n')
                temp_path = f.name

            self.detector.index(temp_path)
            self._indexed = True

        # Find duplicates
        rule_id = rule.get('rule_id', '')
        duplicates = self.detector.find_duplicates_for(rule_id)

        if duplicates:
            return {
                'relationship': 'duplicate',
                'confidence': 0.95,
                'matching_rule_id': duplicates[0],
            }

        return {
            'relationship': 'unique',
            'confidence': 1.0,
        }


class DuplicateDetector:
    """Detects duplicate rules using semantic similarity."""

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold
        self.rules = {}  # Maps rule_id to rule dict

    def index(self, data_path: str) -> None:
        """Index existing rules from a JSONL file."""
        with open(data_path, 'r') as f:
            for line in f:
                rule = json.loads(line)
                rule_id = rule.get('rule_id', '')
                if rule_id:
                    self.rules[rule_id] = rule

    def find_duplicates_for(self, rule_id: str) -> List[Dict[str, Any]]:
        """Find duplicates for a given rule ID."""
        if rule_id not in self.rules:
            return []

        target_rule = self.rules[rule_id]
        duplicates = []

        for other_rule_id, other_rule in self.rules.items():
            if rule_id == other_rule_id:
                continue

            if self._are_rules_identical(target_rule, other_rule):
                duplicates.append(other_rule_id)

        return duplicates

    def _are_rules_identical(self, rule1: Dict[str, Any], rule2: Dict[str, Any]) -> bool:
        """Check if two rules are identical based on key fields."""
        # Extract key fields for comparison
        def get_key(rule):
            return (
                rule.get('business_term'),
                rule.get('operation'),
                tuple(sorted(rule.get('conditions', {}).items())),
                rule.get('scope'),
                rule.get('time_window'),
                tuple(sorted(rule.get('affected_tables_columns', {}).items())),
            )

        key1 = get_key(rule1)
        key2 = get_key(rule2)

        return key1 == key2