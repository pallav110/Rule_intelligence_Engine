"""Real conflict detection service integrating rie_ml conflict detector.

Replaces Mock conflict detection with structured rule conflict detection.
"""

from typing import List, Dict, Any
import sys
from pathlib import Path

# Add rie_ml to path
rie_ml_path = Path(__file__).parent.parent.parent / "rie_ml"
sys.path.insert(0, str(rie_ml_path))

from src.conflict_detection import ConflictDetector


class RealConflictDetectionService:
    """Production conflict detection backed by rie_ml."""

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
                    'conflicting_rule_id': conflict.get('rule_id'),
                    'conflict_type': conflict.get('conflict_type', 'unknown'),
                }

        return {
            'relationship': 'compatible',
            'confidence': 1.0,
        }


class ConflictDetector:
    """Detects conflicts between business rules."""

    def __init__(self):
        self.rules = []  # List of rule dicts

    def load_rules(self, extraction_path: str) -> None:
        """Load rules from a JSONL file."""
        import json

        with open(extraction_path, 'r') as f:
            for line in f:
                data = json.loads(line)
                if 'rules' in data:
                    self.rules.extend(data['rules'])
                elif 'rule_id' in data:
                    self.rules.append(data)

    def find_conflicts(self) -> List[Dict[str, Any]]:
        """Find all conflicts among loaded rules."""
        conflicts = []

        for i, rule1 in enumerate(self.rules):
            for j, rule2 in enumerate(self.rules):
                if i >= j:
                    continue

                conflict = self._check_rule_conflict(rule1, rule2)
                if conflict:
                    conflict['rule_id'] = rule2.get('rule_id', '')
                    conflicts.append(conflict)

        return conflicts

    def _check_rule_conflict(self, rule1: Dict[str, Any], rule2: Dict[str, Any]) -> Dict[str, Any]:
        """Check if two rules conflict with each other."""
        if rule1.get('business_term') != rule2.get('business_term'):
            return None

        op1 = rule1.get('operation')
        op2 = rule2.get('operation')

        # Check for contradictory operations (e.g., include vs exclude)
        if (op1 == 'include' and op2 == 'exclude') or \
           (op1 == 'exclude' and op2 == 'include'):
            return {
                'business_term': rule1.get('business_term'),
                'conflict_type': 'operation_contradiction',
                'rule1_id': rule1.get('rule_id'),
                'rule2_id': rule2.get('rule_id'),
            }

        # Check for conflicting conditions
        cond1 = rule1.get('conditions', {})
        cond2 = rule2.get('conditions', {})

        if cond1 and cond2 and self._conditions_conflict(cond1, cond2):
            return {
                'business_term': rule1.get('business_term'),
                'conflict_type': 'condition_conflict',
                'rule1_id': rule1.get('rule_id'),
                'rule2_id': rule2.get('rule_id'),
            }

        return None

    def _conditions_conflict(self, cond1: Dict[str, Any], cond2: Dict[str, Any]) -> bool:
        """Check if two conditions conflict."""
        # Simple conflict check: same field, different values with opposing operations
        field1 = cond1.get('field')
        field2 = cond2.get('field')

        if field1 == field2:
            value1 = cond1.get('value')
            value2 = cond2.get('value')

            if value1 and value2 and value1 != value2:
                return True

        return False
