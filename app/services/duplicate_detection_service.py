"""Real duplicate detection service integrating rie_ml duplicate detector.

Replaces Mock duplicate detection with semantic similarity-based detection.
"""

from typing import List, Dict, Any
import sys
from pathlib import Path

# Add rie_ml to path
rie_ml_path = Path(__file__).parent.parent.parent / "rie_ml"
sys.path.insert(0, str(rie_ml_path))

from src.duplicate_detection import DuplicateDetector


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
            'relationship': 'unrelated',
            'confidence': 0.0,
            'matching_rule_id': None,
        }