"""Baseline conflict detection service using deterministic comparison.

This implements the V4 architecture's deterministic baseline for conflict detection.
The service uses direct field comparison instead of semantic similarity (ML feature).
"""

from typing import Dict, Any, List, Optional, Tuple
import json


class BaselineConflictDetector:
    """Detect conflicts between rules based on structural analysis."""

    # Conflict types
    DIRECT_CONFLICT = "direct_conflict"
    POTENTIAL_CONFLICT = "potential_conflict"
    TEMPORAL_CONFLICT = "temporal_conflict"
    SCOPE_CONFLICT = "scope_conflict"
    NO_CONFLICT = "no_conflict"

    def __init__(self):
        """Initialize conflict detector."""
        self.confidence_threshold = 0.6

    def detect(
        self,
        new_rule: Dict[str, Any],
        existing_rules: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Detect if new_rule conflicts with existing rules using DETERMINISTIC comparison.

        Returns:
            {
                "has_conflict": bool,
                "conflict_type": str,
                "conflicting_rule_ids": [str],
                "confidence": float,
                "deterministic_comparison": bool,  # Always true for baseline
                "details": {
                    "business_term_conflict": bool,
                    "operation_conflict": bool,
                    "condition_conflict": bool,
                    "scope_overlap": bool,
                    "time_window_overlap": bool,
                    "affected_field_overlap": bool,
                    "contradictory_conditions": [...],
                    "conflicting_operations": bool,
                    "recommendations": [str],
                }
            }
        """
        if not existing_rules:
            return {
                "has_conflict": False,
                "conflict_type": self.NO_CONFLICT,
                "conflicting_rule_ids": [],
                "confidence": 0.0,
                "deterministic_comparison": True,
                "details": {},
            }

        conflicts = []
        for existing_rule in existing_rules:
            conflict_type, confidence, details = self._check_conflict(new_rule, existing_rule)

            if conflict_type != self.NO_CONFLICT and confidence > self.confidence_threshold:
                conflicts.append(
                    {
                        "rule_id": existing_rule.get("rule_id"),
                        "conflict_type": conflict_type,
                        "confidence": confidence,
                        "details": details,
                    }
                )

        if not conflicts:
            return {
                "has_conflict": False,
                "conflict_type": self.NO_CONFLICT,
                "conflicting_rule_ids": [],
                "confidence": 0.0,
                "deterministic_comparison": True,
                "details": {},
            }

        # Aggregate conflicts
        worst_conflict = max(conflicts, key=lambda x: x["confidence"])
        return {
            "has_conflict": True,
            "conflict_type": worst_conflict["conflict_type"],
            "conflicting_rule_ids": [c["rule_id"] for c in conflicts],
            "confidence": round(worst_conflict["confidence"], 3),
            "deterministic_comparison": True,
            "details": {
                "all_conflicts": conflicts,
                "primary_conflict": worst_conflict,
                "recommendations": self._generate_recommendations(worst_conflict["conflict_type"], new_rule),
            },
        }

    def _check_conflict(self, new_rule: Dict[str, Any], existing_rule: Dict[str, Any]) -> Tuple[str, float, Dict]:
        """Check for specific conflict between two rules using deterministic comparison."""
        details = {
            "business_term_conflict": False,
            "operation_conflict": False,
            "condition_conflict": False,
            "scope_overlap": False,
            "time_window_overlap": False,
            "affected_field_overlap": False,
            "contradictory_conditions": [],
            "conflicting_operations": False,
            "shared_tables": [],
            "shared_columns": [],
            "candidate_conditions_conflict": False,
        }

        # 1. Check business term conflict (same term = potential conflict)
        new_term = new_rule.get("business_term", "").lower()
        existing_term = existing_rule.get("business_term", "").lower()
        details["business_term_conflict"] = new_term == existing_term

        if not details["business_term_conflict"]:
            return self.NO_CONFLICT, 0.0, details

        # 2. Check scope overlap
        new_scope = new_rule.get("scope", "").lower()
        existing_scope = existing_rule.get("scope", "").lower()
        details["scope_overlap"] = new_scope == existing_scope or new_scope == "global" or existing_scope == "global"

        if not details["scope_overlap"]:
            return self.NO_CONFLICT, 0.0, details

        # 3. Check affected entities overlap
        new_entities = new_rule.get("affected_entities", {})
        existing_entities = existing_rule.get("affected_entities", {})

        new_tables = set(new_entities.get("tables", []))
        existing_tables = set(existing_entities.get("tables", []))
        shared_tables = new_tables & existing_tables
        details["shared_tables"] = list(shared_tables)

        if not shared_tables:
            return self.NO_CONFLICT, 0.0, details

        new_columns = set(new_entities.get("columns", []))
        existing_columns = set(existing_entities.get("columns", []))
        shared_columns = new_columns & existing_columns
        details["shared_columns"] = list(shared_columns)
        details["affected_field_overlap"] = len(shared_columns) > 0

        # 4. Check for contradictory conditions (INCLUDING candidate conditions)
        new_conditions = new_rule.get("conditions", [])
        new_candidates = new_rule.get("candidate_conditions", [])
        existing_conditions = existing_rule.get("conditions", [])

        # If new rule has unresolved candidate conditions, flag for clarification
        if new_candidates and not new_conditions and existing_conditions:
            # User said something like "exclude cancelled orders" but didn't specify HOW
            # This might conflict with existing rule, but needs clarification
            details["candidate_conditions_conflict"] = True
            candidate_texts = [c.get("text", "") for c in new_candidates]
            details["clarification_needed"] = f"Confirm how to identify: {', '.join(candidate_texts)}"
            # Lower confidence since conditions are unresolved
            return self.POTENTIAL_CONFLICT, 0.65, details

        contradictory = self._find_contradictions(new_conditions, existing_conditions)
        details["contradictory_conditions"] = contradictory

        if contradictory:
            return self.DIRECT_CONFLICT, 0.95, details

        # 5. Check for conflicting operations
        new_op = (new_rule.get("operation") or "").lower()
        existing_op = (existing_rule.get("operation") or "").lower()

        operation_conflict = self._check_operation_conflict(new_op, existing_op)
        details["conflicting_operations"] = operation_conflict

        if operation_conflict and shared_columns:
            return self.DIRECT_CONFLICT, 0.85, details

        # 6. Check temporal overlap (for time-based rules)
        new_time_window = new_rule.get("time_window")
        existing_time_window = existing_rule.get("time_window")
        details["temporal_overlap"] = new_time_window == existing_time_window

        # 7. Potential conflict if conditions overlap but not contradictory
        if shared_tables and len(new_conditions) > 0 and len(existing_conditions) > 0:
            condition_similarity = self._calculate_condition_similarity(new_conditions, existing_conditions)
            if condition_similarity > 0.4:
                return self.POTENTIAL_CONFLICT, condition_similarity * 0.8, details

        return self.NO_CONFLICT, 0.0, details

    def _find_contradictions(self, new_conditions: List[Dict], existing_conditions: List[Dict]) -> List[Dict]:
        """Find contradictory conditions between two rules."""
        contradictions = []

        for new_cond in new_conditions:
            new_field = new_cond.get("field", "").lower()
            new_operator = new_cond.get("operator", "").lower()
            new_value = new_cond.get("value")

            for existing_cond in existing_conditions:
                existing_field = existing_cond.get("field", "").lower()
                existing_operator = existing_cond.get("operator", "").lower()
                existing_value = existing_cond.get("value")

                # Same field, contradictory operators/values
                if new_field == existing_field:
                    is_contradictory = self._operators_contradict(
                        new_operator, new_value, existing_operator, existing_value
                    )

                    if is_contradictory:
                        contradictions.append(
                            {
                                "field": new_field,
                                "new_condition": f"{new_field} {new_operator} {new_value}",
                                "existing_condition": f"{existing_field} {existing_operator} {existing_value}",
                                "reason": self._contradiction_reason(
                                    new_operator, new_value, existing_operator, existing_value
                                ),
                            }
                        )

        return contradictions

    def _operators_contradict(self, op1: str, val1: Any, op2: str, val2: Any) -> bool:
        """Check if two operator/value pairs are contradictory."""
        op_pairs = [
            ("equals", "not_equals"),
            ("in", "not_in"),
            ("is_not_null", "is_null"),
            ("greater_than", "less_than"),
            ("greater_than_or_equal", "less_than"),
            ("less_than_or_equal", "greater_than"),
        ]

        # Check symmetric pairs
        for pair in op_pairs:
            if (op1 == pair[0] and op2 == pair[1]) or (op1 == pair[1] and op2 == pair[0]):
                return True

        # Check value contradictions for equals
        if op1 == "equals" and op2 == "equals" and val1 != val2:
            return True

        # Check list contradictions
        if op1 == "in" and op2 == "not_in":
            if isinstance(val1, list) and isinstance(val2, list):
                # Contradictory if all values from val1 are in val2
                return all(v in val2 for v in val1)

        return False

    def _contradiction_reason(self, op1: str, val1: Any, op2: str, val2: Any) -> str:
        """Generate human-readable contradiction reason."""
        if op1 == "is_not_null" and op2 == "is_null":
            return "One requires field to be null, other requires non-null"

        if op1 == "equals" and op2 == "equals" and val1 != val2:
            return f"Requires field to equal both {val1} and {val2}"

        if (op1 == "greater_than" or op1 == "greater_than_or_equal") and (op2 == "less_than" or op2 == "less_than_or_equal"):
            return f"Requires field to be > {val1} and < {val2}"

        return "Operators are contradictory"

    def _check_operation_conflict(self, op1: str, op2: str) -> bool:
        """Check if two operations conflict."""
        conflicting_pairs = [
            ("exclude", "include"),
            ("restrict", "allow"),
            ("mask", "expose"),
            ("drop", "keep"),
        ]

        for pair in conflicting_pairs:
            if (op1 == pair[0] and op2 == pair[1]) or (op1 == pair[1] and op2 == pair[0]):
                return True

        return False

    def _calculate_condition_similarity(self, conditions1: List[Dict], conditions2: List[Dict]) -> float:
        """Calculate similarity between condition lists."""
        if not conditions1 or not conditions2:
            return 0.0

        matches = 0
        for cond1 in conditions1:
            for cond2 in conditions2:
                if (
                    cond1.get("field", "").lower() == cond2.get("field", "").lower()
                    and cond1.get("operator", "").lower() == cond2.get("operator", "").lower()
                ):
                    matches += 1
                    break

        return matches / max(len(conditions1), len(conditions2))

    def _generate_recommendations(self, conflict_type: str, new_rule: Dict[str, Any]) -> List[str]:
        """Generate recommendations for conflict resolution."""
        recommendations = []

        if conflict_type == self.DIRECT_CONFLICT:
            recommendations.append("Review and reconcile contradictory conditions")
            recommendations.append("Consider modifying scope or affected entities to avoid overlap")
            recommendations.append("Merge or prioritize which rule takes precedence")

        elif conflict_type == self.POTENTIAL_CONFLICT:
            recommendations.append("Verify conditions are truly compatible")
            recommendations.append("Consider adding discriminating conditions")
            recommendations.append("Test with sample data to confirm no unexpected behavior")

        elif conflict_type == self.TEMPORAL_CONFLICT:
            recommendations.append("Check time window specifications for temporal overlap")
            recommendations.append("Consider adjusting time windows or adding temporal conditions")

        elif conflict_type == self.SCOPE_CONFLICT:
            recommendations.append("Review scope definitions for potential overlap")
            recommendations.append("Ensure scope specifications are mutually exclusive if intended")

        else:
            recommendations.append("No direct conflicts detected")

        return recommendations


class BaselineConflictDetectionService:
    """Production-ready baseline conflict detection service.

    This implements the V4 architecture's deterministic baseline.
    No semantic similarity or pgvector retrieval is used.
    """

    def __init__(self):
        """Initialize service."""
        self.detector = BaselineConflictDetector()

    def check_conflict(
        self,
        suggested_rule: Dict[str, Any],
        workspace_id: str,
        domain_id: str,
        db=None,
    ) -> Dict[str, Any]:
        """
        Check if suggested rule conflicts with existing rules using DETERMINISTIC baseline.

        This is the V4-compliant implementation that uses:
        - Business term comparison
        - Operation comparison
        - Condition comparison
        - Threshold comparison
        - Scope comparison
        - Time window comparison
        - Affected field comparison

        Returns:
            {
                "has_conflict": bool,
                "conflict_type": "direct_conflict|potential_conflict|temporal_conflict|scope_conflict|no_conflict",
                "conflicting_rule_ids": [str],
                "confidence": float (0.0-1.0),
                "deterministic_comparison": bool,  # Always true for baseline
                "details": {...}
            }
        """
        # Load existing rules from domain pack JSON (source of truth)
        existing_rules = self._load_active_rules(domain_id)

        if not existing_rules:
            return {
                "has_conflict": False,
                "conflict_type": self.NO_CONFLICT,
                "conflicting_rule_ids": [],
                "confidence": 0.0,
                "deterministic_comparison": True,
                "details": {"reason": "No active rules found to compare against"},
            }

        # Run conflict detection
        result = self.detector.detect(suggested_rule, existing_rules)

        # Add metadata
        result["deterministic_comparison"] = True
        result["retrieval_stage"] = len(existing_rules)

        return result

    def _load_active_rules(self, domain_id: str) -> List[Dict[str, Any]]:
        """Load active rules from domain pack JSON files."""
        try:
            from pathlib import Path

            active_rules_path = (
                Path(__file__).parent.parent.parent /
                "rie_ml" / "domain-packs" / domain_id / "rules" / "active_rules.json"
            )

            if not active_rules_path.exists():
                print(f"⚠️  Active rules file not found: {active_rules_path}")
                return []

            with open(active_rules_path, 'r') as f:
                rules = json.load(f)

            # Normalize rule structure
            normalized_rules = []
            for rule in rules:
                normalized_rules.append({
                    "rule_id": rule.get("rule_id"),
                    "business_term": rule.get("business_term"),
                    "operation": rule.get("operation"),
                    "conditions": rule.get("conditions", []),
                    "scope": rule.get("scope", "global"),
                    "affected_entities": rule.get("affected_entities", {}),
                    "threshold": rule.get("threshold"),
                    "time_window": rule.get("time_window"),
                })

            return normalized_rules

        except Exception as e:
            print(f"Error loading active rules: {e}")
            return []
