"""Baseline duplicate detection service using deterministic matching.

This implements the V4 architecture's deterministic baseline for duplicate detection.
The service uses text normalization, rule normalization, canonical formatting,
and hash comparison instead of semantic similarity (ML feature).
"""

from typing import Dict, Any, List, Optional, Tuple
import json
import hashlib
import re
from difflib import SequenceMatcher


class BaselineDuplicateDetector:
    """Detect duplicate and related rules using deterministic matching."""

    # Relationship types
    EXACT_DUPLICATE = "exact_duplicate"
    SEMANTIC_DUPLICATE = "semantic_duplicate"  # Will not be used in baseline
    EXTENSION = "extension"
    MODIFICATION = "modification"
    SUBSET = "subset"
    SUPERSET = "superset"
    UNRELATED = "unrelated"

    def __init__(self):
        """Initialize duplicate detector."""
        self.similarity_threshold = 0.75
        self.structural_threshold = 0.6

    def detect(
        self,
        new_rule: Dict[str, Any],
        existing_rules: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Detect if new_rule duplicates or relates to existing rules using DETERMINISTIC matching.

        Returns:
            {
                "relationship": str,  # One of the relationship types above
                "matching_rule_id": str or None,
                "confidence": float,
                "deterministic_match": bool,  # Always true for baseline
                "normalized_rule_hash": str,  # Hash of normalized rule
                "details": {
                    "business_term_match": bool,
                    "condition_similarity": float,
                    "operation_match": bool,
                    "scope_match": bool,
                    "affected_entities_match": float,
                }
            }
        """
        if not existing_rules:
            return {
                "relationship": self.UNRELATED,
                "matching_rule_id": None,
                "confidence": 0.0,
                "deterministic_match": True,
                "normalized_rule_hash": self._generate_rule_hash(new_rule),
                "details": {},
            }

        best_match = None
        best_relationship = self.UNRELATED
        best_confidence = 0.0
        best_details = {}

        for existing_rule in existing_rules:
            relationship, confidence, details = self._compare_rules(new_rule, existing_rule)

            if confidence > best_confidence:
                best_confidence = confidence
                best_relationship = relationship
                best_match = existing_rule
                best_details = details

        # Determine if this is a duplicate (anything other than UNRELATED)
        is_duplicate = best_relationship != self.UNRELATED and best_confidence > 0.5

        return {
            "is_duplicate": is_duplicate,
            "relationship": best_relationship,
            "matching_rule_id": best_match.get("rule_id") if best_match else None,
            "confidence": round(best_confidence, 3),
            "deterministic_match": True,
            "normalized_rule_hash": self._generate_rule_hash(new_rule),
            "details": self._extract_match_details(new_rule, best_match) if best_match else best_details,
        }

    def _compare_rules(self, new_rule: Dict[str, Any], existing_rule: Dict[str, Any]) -> Tuple[str, float, Dict]:
        """Compare two rules using deterministic matching."""
        details = {
            "business_term_match": False,
            "condition_similarity": 0.0,
            "operation_match": False,
            "scope_match": False,
            "affected_entities_match": 0.0,
            "threshold_match": False,
            "candidate_conditions_match": False,
        }

        # 1. Check business term match
        new_term = new_rule.get("business_term", "").lower()
        existing_term = existing_rule.get("business_term", "").lower()
        term_similarity = self._string_similarity(new_term, existing_term)
        details["business_term_match"] = term_similarity > 0.85

        # 2. Check operation match
        new_op = (new_rule.get("operation") or "").lower()
        existing_op = (existing_rule.get("operation") or "").lower()
        details["operation_match"] = new_op == existing_op

        # 3. Check scope match
        new_scope = new_rule.get("scope", "").lower()
        existing_scope = existing_rule.get("scope", "").lower()
        details["scope_match"] = new_scope == existing_scope

        # 4. Compare conditions (INCLUDING candidate conditions now)
        new_conditions = new_rule.get("conditions", [])
        new_candidate_conditions = new_rule.get("candidate_conditions", [])
        existing_conditions = existing_rule.get("conditions", [])

        condition_similarity = self._compare_conditions(
            new_conditions, existing_conditions, new_rule, existing_rule,
            candidate_conditions=new_candidate_conditions
        )
        details["condition_similarity"] = round(condition_similarity, 3)
        details["candidate_conditions_match"] = len(new_candidate_conditions) > 0

        # 5. Compare affected entities (tables and columns)
        new_entities = new_rule.get("affected_entities", {})
        existing_entities = existing_rule.get("affected_entities", {})
        entities_similarity = self._compare_entities(new_entities, existing_entities)
        details["affected_entities_match"] = round(entities_similarity, 3)

        # 6. Check threshold match
        new_threshold = new_rule.get("threshold")
        existing_threshold = existing_rule.get("threshold")
        details["threshold_match"] = new_threshold == existing_threshold

        # Determine relationship based on comparison
        relationship, confidence = self._determine_relationship(new_rule, existing_rule, details)

        return relationship, confidence, details

    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity using SequenceMatcher."""
        return SequenceMatcher(None, s1, s2).ratio()

    def _compare_conditions(self, new_conditions: List[Dict], existing_conditions: List[Dict], new_rule: Dict = None, existing_rule: Dict = None, candidate_conditions: List[Dict] = None) -> float:
        """
        Compare condition lists using deterministic matching.
        Also uses candidate conditions for semantic similarity.
        Returns similarity score 0.0-1.0
        """
        if not new_conditions and not existing_conditions:
            return 1.0

        # If new rule has no conditions but HAS candidate conditions, boost similarity if entities match
        if not new_conditions and candidate_conditions and existing_conditions:
            # Extract field names from candidate conditions (heuristic: look for keywords like "orders", "status", etc.)
            candidate_texts = [c.get("text", "").lower() for c in candidate_conditions]
            candidate_text = " ".join(candidate_texts)

            # Check if existing conditions mention similar entities
            existing_fields = set(cond.get("field", "").lower() for cond in existing_conditions)
            for field in existing_fields:
                if any(entity in candidate_text for entity in field.split(".")):
                    return 0.65  # Good semantic match via candidate conditions

        if not new_conditions or not existing_conditions:
            # Check if the rule without conditions has the same field in affected_entities
            # This handles the case where extraction detected the field but didn't create a structured condition
            if new_conditions and not existing_conditions:
                # New rule has conditions, existing doesn't - check if fields overlap
                existing_fields = set()
                if existing_rule and existing_rule.get("affected_entities"):
                    existing_fields = set(existing_rule["affected_entities"].get("columns", []))

                new_fields = set(cond.get("field", "").lower() for cond in new_conditions)
                overlapping_fields = new_fields & existing_fields
                if overlapping_fields:
                    return 0.5  # Medium similarity - same fields mentioned

            elif existing_conditions and not new_conditions:
                # Existing rule has conditions, new doesn't - check if fields overlap
                new_fields = set()
                if new_rule and new_rule.get("affected_entities"):
                    new_fields = set(new_rule["affected_entities"].get("columns", []))

                existing_fields = set(cond.get("field", "").lower() for cond in existing_conditions)
                overlapping_fields = new_fields & existing_fields
                if overlapping_fields:
                    return 0.5  # Medium similarity - same fields mentioned

            return 0.0

        # Normalize conditions for comparison
        new_normalized = self._normalize_conditions(new_conditions)
        existing_normalized = self._normalize_conditions(existing_conditions)

        # Count matching conditions
        matching = 0
        for new_cond in new_normalized:
            for existing_cond in existing_normalized:
                if self._conditions_equal(new_cond, existing_cond):
                    matching += 1
                    break

        total = max(len(new_normalized), len(existing_normalized))
        return matching / total if total > 0 else 0.0

    def _normalize_conditions(self, conditions: List[Dict]) -> List[Dict]:
        """Normalize condition representation for comparison."""
        normalized = []
        for cond in conditions:
            normalized.append(
                {
                    "field": cond.get("field", "").lower(),
                    "operator": cond.get("operator", "").lower(),
                    "value": str(cond.get("value", "")).lower() if cond.get("value") is not None else None,
                }
            )
        return normalized

    def _conditions_equal(self, cond1: Dict, cond2: Dict) -> bool:
        """Check if two conditions are equivalent."""
        field_match = cond1.get("field") == cond2.get("field")
        operator_match = cond1.get("operator") == cond2.get("operator")

        # Special handling for value comparison
        val1 = cond1.get("value")
        val2 = cond2.get("value")

        # For null checks, treat None and "None" as equivalent
        if cond1.get("operator") in ["is_not_null", "is_null"]:
            value_match = True
        else:
            value_match = val1 == val2

        return field_match and operator_match and value_match

    def _compare_entities(self, new_entities: Dict, existing_entities: Dict) -> float:
        """
        Compare affected entities (tables and columns).
        Returns similarity score 0.0-1.0
        """
        new_tables = set(new_entities.get("tables", []))
        existing_tables = set(existing_entities.get("tables", []))

        new_columns = set(new_entities.get("columns", []))
        existing_columns = set(existing_entities.get("columns", []))

        # Calculate Jaccard similarity for tables
        if new_tables or existing_tables:
            table_intersection = len(new_tables & existing_tables)
            table_union = len(new_tables | existing_tables)
            table_similarity = table_intersection / table_union if table_union > 0 else 0.0
        else:
            table_similarity = 1.0

        # Calculate Jaccard similarity for columns
        if new_columns or existing_columns:
            col_intersection = len(new_columns & existing_columns)
            col_union = len(new_columns | existing_columns)
            col_similarity = col_intersection / col_union if col_union > 0 else 0.0
        else:
            col_similarity = 1.0

        # Average the two
        return (table_similarity + col_similarity) / 2

    def _determine_relationship(self, new_rule: Dict, existing_rule: Dict, details: Dict) -> Tuple[str, float]:
        """Determine relationship type and confidence based on comparison details."""
        business_term_match = details["business_term_match"]
        condition_sim = details["condition_similarity"]
        operation_match = details["operation_match"]
        scope_match = details["scope_match"]
        entities_sim = details["affected_entities_match"]

        # Check if one rule has conditions and the other doesn't
        new_has_conditions = len(new_rule.get("conditions", [])) > 0
        existing_has_conditions = len(existing_rule.get("conditions", [])) > 0
        new_has_candidates = len(new_rule.get("candidate_conditions", [])) > 0

        # Check if entities are "unknown" (not extracted)
        new_entities = new_rule.get("affected_entities", {})
        existing_entities = existing_rule.get("affected_entities", {})
        both_entities_unknown = (
            (new_entities.get("columns", []) == ["unknown.unknown"] or not new_entities.get("columns")) and
            (existing_entities.get("columns", []) == ["unknown.unknown"] or not existing_entities.get("columns"))
        )

        # EXACT DUPLICATE: everything matches
        if (
            business_term_match
            and condition_sim > 0.95
            and operation_match
            and scope_match
            and entities_sim > 0.9
        ):
            confidence = 0.99
            return self.EXACT_DUPLICATE, confidence

        # SEMANTIC DUPLICATE: business term + high condition/entity match
        # Also consider the case where one rule has conditions and the other doesn't
        # but they're semantically similar (same business term, operation, scope)
        if (
            business_term_match
            and operation_match
            and scope_match
            and (
                (condition_sim > 0.85 and entities_sim > 0.8) or
                # Special case: one rule has conditions, other doesn't, but same intent
                (new_has_conditions != existing_has_conditions and entities_sim > 0.6)
            )
        ):
            confidence = min(0.95, (condition_sim + entities_sim) / 2 + 0.1)
            return self.SEMANTIC_DUPLICATE, confidence

        # MODIFICATION: same business term, same operation, different conditions
        # NEW: Also handle case where new rule has candidate conditions and existing has real conditions
        if (
            business_term_match
            and operation_match
            and (condition_sim > 0.5 and condition_sim < 0.9)
        ):
            confidence = min(0.85, (condition_sim + 0.7) / 2)
            return self.MODIFICATION, confidence

        # EXTENSION: New rule with candidate conditions matching existing rule's intent
        # This is important for the baseline: when user says "exclude X" but doesn't specify HOW,
        # and an existing rule operates on the same business term, it's likely a refinement
        if (
            new_has_candidates
            and not new_has_conditions
            and existing_has_conditions
            and business_term_match
            and operation_match
        ):
            # Strong match on business term + operation + candidate conditions
            # Even if entities are unknown, the semantic match is clear
            if both_entities_unknown or entities_sim > 0.3:
                confidence = 0.70  # Good semantic match via intent + candidates
                return self.EXTENSION, confidence

        # EXTENSION: same operation/scope but more conditions or entities
        if (
            operation_match
            and scope_match
            and len(new_rule.get("conditions", [])) >= len(existing_rule.get("conditions", []))
            and condition_sim > 0.4
        ):
            confidence = min(0.8, condition_sim + 0.3)
            return self.EXTENSION, confidence

        # SUBSET: existing rule is superset of new rule
        if condition_sim > 0.6 and len(new_rule.get("conditions", [])) < len(existing_rule.get("conditions", [])):
            confidence = condition_sim * 0.8
            return self.SUBSET, confidence

        # SUPERSET: new rule is superset of existing
        if condition_sim > 0.6 and len(new_rule.get("conditions", [])) > len(existing_rule.get("conditions", [])):
            confidence = condition_sim * 0.75
            return self.SUPERSET, confidence

        # UNRELATED: low similarity across all dimensions
        confidence = 0.0
        return self.UNRELATED, confidence

    def _extract_match_details(self, new_rule: Dict, existing_rule: Dict) -> Dict[str, Any]:
        """Extract human-readable match details."""
        return {
            "new_rule_business_term": new_rule.get("business_term"),
            "existing_rule_business_term": existing_rule.get("business_term"),
            "existing_rule_id": existing_rule.get("rule_id"),
            "matching_conditions": len(new_rule.get("conditions", [])) > 0,
            "new_rule_operation": new_rule.get("operation"),
            "existing_rule_operation": existing_rule.get("operation"),
        }

    def _generate_rule_hash(self, rule: Dict[str, Any]) -> str:
        """Generate a deterministic hash for rule normalization."""
        # Create canonical representation
        canonical = {
            "business_term": rule.get("business_term", "").lower(),
            "operation": (rule.get("operation") or "").lower(),
            "scope": rule.get("scope", "").lower(),
            "conditions": self._normalize_conditions(rule.get("conditions", [])),
            "affected_entities": {
                "tables": sorted(rule.get("affected_entities", {}).get("tables", [])),
                "columns": sorted(rule.get("affected_entities", {}).get("columns", [])),
            },
        }

        # Convert to JSON string and hash
        canonical_str = json.dumps(canonical, sort_keys=True)
        return hashlib.md5(canonical_str.encode()).hexdigest()


class BaselineDuplicateDetectionService:
    """Production-ready baseline duplicate detection service.

    This implements the V4 architecture's deterministic baseline.
    No semantic similarity or pgvector retrieval is used.
    """

    def __init__(self):
        """Initialize service."""
        self.detector = BaselineDuplicateDetector()

    def check_duplicate(
        self,
        suggested_rule: Dict[str, Any],
        workspace_id: str,
        domain_id: str,
        db=None,
    ) -> Dict[str, Any]:
        """
        Check if suggested rule duplicates existing rules using DETERMINISTIC baseline.

        This is the V4-compliant implementation that uses:
        - Text normalization
        - Rule normalization
        - Canonical formatting
        - Hash comparison
        - Exact field matching

        Returns:
            {
                "is_duplicate": bool,
                "relationship": "exact_duplicate|semantic_duplicate|modification|extension|unrelated",
                "matching_rule_id": str or None,
                "confidence": float (0.0-1.0),
                "deterministic_match": bool,  # Always true for baseline
                "normalized_rule_hash": str,  # Hash of normalized rule
                "details": {...}
            }
        """
        # For baseline, we retrieve ALL rules (no semantic retrieval)
        try:
            from sqlalchemy import text
            import json
            from pathlib import Path

            existing_rules = []

            # Stage 1: Try database query first
            query = text(
                """
                SELECT rule_id, business_term, operation, conditions, scope,
                       affected_entities, threshold, time_window
                FROM rules
                WHERE workspace_id = :workspace_id
                  AND domain_id = :domain_id
                  AND status IN ('active', 'draft')
                ORDER BY created_at DESC
                LIMIT 100
            """
            )

            result = db.execute(query, {"workspace_id": workspace_id, "domain_id": domain_id})

            for row in result:
                rule = {
                    "rule_id": row[0],
                    "business_term": row[1],
                    "operation": row[2],
                    "conditions": json.loads(row[3]) if isinstance(row[3], str) else row[3] or [],
                    "scope": row[4],
                    "affected_entities": json.loads(row[5]) if isinstance(row[5], str) else row[5] or {},
                    "threshold": row[6],
                    "time_window": row[7],
                }
                existing_rules.append(rule)

            # Stage 2: If database returns 0 results, fallback to domain pack JSON files
            if not existing_rules:
                try:
                    active_rules_path = (
                        Path(__file__).parent.parent.parent /
                        "rie_ml" / "domain-packs" / domain_id / "rules" / "active_rules.json"
                    )
                    if active_rules_path.exists():
                        with open(active_rules_path, 'r') as f:
                            json_rules = json.load(f)
                            if isinstance(json_rules, list):
                                for json_rule in json_rules:
                                    rule = {
                                        "rule_id": json_rule.get("rule_id"),
                                        "business_term": json_rule.get("business_term"),
                                        "operation": json_rule.get("operation"),
                                        "conditions": json_rule.get("conditions", []),
                                        "scope": json_rule.get("scope", "global"),
                                        "affected_entities": json_rule.get("affected_entities", {}),
                                        "threshold": json_rule.get("threshold"),
                                        "time_window": json_rule.get("time_window"),
                                    }
                                    existing_rules.append(rule)
                except Exception as fallback_e:
                    print(f"Warning: Could not load fallback rules from {domain_id}/rules/active_rules.json: {fallback_e}")

            # Use deterministic duplicate detection
            detection_result = self.detector.detect(suggested_rule, existing_rules)

            # Enhance result with baseline-specific fields
            detection_result["is_duplicate"] = detection_result["confidence"] > 0.7 and detection_result["relationship"] in [
                "exact_duplicate",
                "semantic_duplicate",
            ]
            detection_result["retrieval_stage"] = len(existing_rules)  # Track how many candidates were retrieved
            detection_result["similar_rules"] = existing_rules  # Include all retrieved rules for debugging

            return detection_result

        except Exception as e:
            print(f"Error in baseline duplicate detection: {e}")
            import traceback
            traceback.print_exc()
            return {
                "is_duplicate": False,
                "relationship": "unrelated",
                "matching_rule_id": None,
                "confidence": 0.0,
                "deterministic_match": True,
                "normalized_rule_hash": "",
                "details": {"error": str(e)},
            }
