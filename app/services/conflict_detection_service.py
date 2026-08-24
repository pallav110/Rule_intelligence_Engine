"""Real conflict detection service integrating rie-ml conflict detector.

Replaces Mock conflict detection with structured rule conflict detection.
"""

from typing import List, Dict, Any
import sys
from pathlib import Path

# Add rie-ml to path
rie_ml_path = Path(__file__).parent.parent.parent / "rie-ml"
sys.path.insert(0, str(rie_ml_path))

from src.conflict_detection import ConflictDetector


class RealConflictDetectionService:
    """Production conflict detection backed by rie-ml."""

    def __init__(self):
        self.detector = ConflictDetector()
        self._loaded = False

    def load_rules(self, extraction_path: str) -> None:
        """Load structured rules for conflict detection."""
        self.detector.load_rules(extraction_path)
        self._loaded = True

    def check_conflict(
        self,
        rule: Dict[str, Any],
        existing_rules: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check if rule conflicts with existing rules."""
        if not self._loaded:
            # Load existing rules on-the-fly
            import tempfile
            import json

            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                for r in existing_rules:
                    json.dump({'rules': [r]}, f)
                    f.write('\n')
                temp_path = f.name

            self.detector.load_rules(temp_path)
            self._loaded = True

        # Find conflicts
        conflicts = self.detector.find_conflicts()

        # Check if current rule conflicts with any existing rule
        for conflict in conflicts:
            if conflict['business_term'] == rule.get('business_term'):
                return {
                    'relationship': 'conflict',
                    'confidence': 0.9,
                    'conflicting_rule_id': conflict['rule_1'].get('rule_id'),
                }

        return {
            'relationship': 'no_conflict',
            'confidence': 1.0,
            'conflicting_rule_id': None,
        }