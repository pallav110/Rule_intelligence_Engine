"""Phase 3 — Structured conflict detection engine.

Detects conflicts between rules:
  1. Threshold conflicts (e.g., > 10 vs > 20)
  2. Operation conflicts (include vs exclude)
  3. Scope conflicts (different time windows for same metric)
"""

import json
from typing import Dict, List, Any


class ConflictDetector:
    def __init__(self):
        self.rules_by_term: Dict[str, List[Dict]] = {}

    def load_rules(self, extraction_path: str) -> None:
        """Load structured rules from extraction.jsonl."""
        self.rules_by_term.clear()
        with open(extraction_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line.strip())
                for rule in obj.get("rules", []):
                    term = rule.get("business_term")
                    if term:
                        self.rules_by_term.setdefault(term, []).append(rule)

    def find_conflicts(self) -> List[Dict[str, Any]]:
        """Find all conflicting rule pairs."""
        conflicts = []

        for term, rules in self.rules_by_term.items():
            if len(rules) < 2:
                continue

            for i in range(len(rules)):
                for j in range(i + 1, len(rules)):
                    r1, r2 = rules[i], rules[j]

                    # Check operation conflicts
                    if r1["operation"] != r2["operation"]:
                        conflicts.append({
                            "business_term": term,
                            "conflict_type": "operation",
                            "rule_1": r1,
                            "rule_2": r2,
                            "description": f"Operation conflict: {r1['operation']} vs {r2['operation']}",
                        })

                    # Check threshold conflicts
                    t1, t2 = r1.get("threshold"), r2.get("threshold")
                    if t1 is not None and t2 is not None and t1 != t2:
                        conflicts.append({
                            "business_term": term,
                            "conflict_type": "threshold",
                            "rule_1": r1,
                            "rule_2": r2,
                            "description": f"Threshold conflict: {t1} vs {t2}",
                        })

                    # Check scope conflicts
                    if r1.get("scope") != r2.get("scope"):
                        conflicts.append({
                            "business_term": term,
                            "conflict_type": "scope",
                            "rule_1": r1,
                            "rule_2": r2,
                            "description": f"Scope conflict: {r1.get('scope')} vs {r2.get('scope')}",
                        })

        return conflicts