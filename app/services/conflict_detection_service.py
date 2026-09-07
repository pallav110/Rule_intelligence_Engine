"""Real conflict detection service for identifying contradicting rules."""

from typing import Dict, Any, List, Optional, Tuple
import json


class ConflictDetector:
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
        Detect if new_rule conflicts with existing rules.

        Returns:
            {
                "has_conflict": bool,
                "conflict_type": str,
                "conflicting_rule_ids": [str],
                "confidence": float,
                "details": {
                    "contradictory_conditions": [...],
                    "conflicting_operations": bool,
                    "scope_overlap": bool,
                    "temporal_overlap": bool,
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
                "details": {},
            }

        # Aggregate conflicts and related rules
        worst_conflict = max(conflicts, key=lambda x: x["confidence"])
        related_rules = [c for c in conflicts if c["conflict_type"] == "related_compatible"]
        actual_conflicts = [c for c in conflicts if c["conflict_type"] != "related_compatible"]

        return {
            "has_conflict": len(actual_conflicts) > 0,
            "conflict_type": worst_conflict["conflict_type"] if actual_conflicts else "no_conflict",
            "conflicting_rule_ids": [c["rule_id"] for c in actual_conflicts],
            "related_compatible_rule_ids": [c["rule_id"] for c in related_rules],
            "confidence": round(worst_conflict["confidence"], 3),
            "details": {
                "all_conflicts": conflicts,
                "primary_conflict": worst_conflict if actual_conflicts else None,
                "related_compatible_rules": related_rules,
                "recommendations": self._generate_recommendations(worst_conflict["conflict_type"] if actual_conflicts else "no_conflict", new_rule),
            },
        }

    # ── helpers: same _get_effective_entities / _singularize / _field_tokens / _fields_related as baseline
    @staticmethod
    def _get_effective_entities(rule: Dict[str, Any]) -> Dict[str, Any]:
        entities = rule.get("affected_entities") or {}
        tables = entities.get("tables") or rule.get("affected_tables") or []
        columns = entities.get("columns") or rule.get("affected_columns") or []
        return {"tables": tables, "columns": columns}

    @staticmethod
    def _singularize(token: str) -> str:
        t = token.lower().strip()
        return t[:-1] if t.endswith("s") and len(t) > 3 else t

    def _field_tokens(self, field_name: str) -> set:
        return set(f.strip().lower() for f in field_name.split(".") if f.strip())

    def _fields_related(self, f1: str, f2: str) -> bool:
        if not f1 or not f2:
            return False
        f1l, f2l = f1.lower(), f2.lower()
        if f1l == f2l:
            return True
        tok1 = {self._singularize(t) for t in self._field_tokens(f1l)}
        tok2 = {self._singularize(t) for t in self._field_tokens(f2l)}
        if tok1 & tok2:
            return True
        if self._string_similarity(f1l, f2l) > 0.6:
            return True
        leaf1 = f1l.rsplit(".", 1)[-1]
        leaf2 = f2l.rsplit(".", 1)[-1]
        return leaf1 == leaf2

    def _check_conflict(self, new_rule: Dict[str, Any], existing_rule: Dict[str, Any]) -> Tuple[str, float, Dict]:
        """Check for specific conflict between two rules."""
        details = {
            "contradictory_conditions": [],
            "conflicting_operations": False,
            "scope_overlap": False,
            "temporal_overlap": False,
            "shared_tables": [],
            "shared_columns": [],
            "business_term_match": False,
            "business_term_similarity": 0.0,
            "subject_overlap": False,
            "subject_similarity": 0.0,
        }

        # 1. Check business term compatibility
        new_term = (new_rule.get("business_term") or "").lower()
        existing_term = (existing_rule.get("business_term") or "").lower()
        term_similarity = self._string_similarity(new_term, existing_term)
        details["business_term_similarity"] = round(term_similarity, 3)
        details["business_term_match"] = term_similarity > 0.85

        # 2. Check scope overlap
        new_scope = new_rule.get("scope", "").lower()
        existing_scope = existing_rule.get("scope", "").lower()
        details["scope_overlap"] = new_scope == existing_scope or new_scope == "global" or existing_scope == "global"

        if not details["scope_overlap"]:
            return self.NO_CONFLICT, 0.0, details

        # 3. Check affected entities overlap (use effective entities + fuzzy table match)
        new_entities = self._get_effective_entities(new_rule)
        existing_entities = self._get_effective_entities(existing_rule)

        new_tables = set(new_entities.get("tables", []))
        existing_tables = set(existing_entities.get("tables", []))

        new_tables_norm = {self._singularize(t) for t in new_tables} if new_tables else set()
        existing_tables_norm = {self._singularize(t) for t in existing_tables} if existing_tables else set()
        shared_tables = (new_tables & existing_tables) | (new_tables_norm & existing_tables_norm)
        details["shared_tables"] = list(shared_tables)

        if not shared_tables:
            # If new rule has NO resolved tables/columns but has conditions and same term+scope,
            # allow fall-through to condition-level conflict checks.
            new_cols_eff = set(self._get_effective_entities(new_rule).get("columns", []))
            has_any_entity = bool(new_tables or existing_tables or new_cols_eff)
            # Let candidate_conditions / condition overlap checks decide; don't short-circuit here
            if new_rule.get("conditions") or new_rule.get("candidate_conditions"):
                details["shared_tables"] = []
            else:
                return self.NO_CONFLICT, 0.0, details

        # Use fuzzy column overlap for shared_columns
        new_columns = set(new_entities.get("columns", []))
        existing_columns = set(existing_entities.get("columns", []))
        shared_columns = new_columns & existing_columns
        if not shared_columns:
            for nc in list(new_columns):
                nc_tokens = {self._singularize(t) for t in self._field_tokens(nc)}
                for ec in list(existing_columns):
                    ec_tokens = {self._singularize(t) for t in self._field_tokens(ec)}
                    if nc_tokens & ec_tokens:
                        shared_columns = {nc, ec}
                        break
                if shared_columns and shared_columns != (new_columns & existing_columns):
                    break
        details["shared_columns"] = list(shared_columns)

        # 4. Check subject overlap (semantic concept overlap)
        subject_similarity = self._calculate_subject_similarity(new_rule, existing_rule)
        details["subject_similarity"] = round(subject_similarity, 3)
        details["subject_overlap"] = subject_similarity > 0.6

        # 5. Check for contradictory conditions
        new_conditions = new_rule.get("conditions", [])
        existing_conditions = existing_rule.get("conditions", [])

        contradictory = self._find_contradictions(new_conditions, existing_conditions)
        details["contradictory_conditions"] = contradictory

        if contradictory:
            return self.DIRECT_CONFLICT, 0.95, details

        # 6. Check for conflicting operations with sufficient subject overlap
        new_op = (new_rule.get("operation") or "").lower()
        existing_op = (existing_rule.get("operation") or "").lower()

        operation_conflict = self._check_operation_conflict(new_op, existing_op)
        details["conflicting_operations"] = operation_conflict

        # Operation conflict detected — also allow condition-overlap as surrogate for column overlap
        condition_overlap = False
        if len(new_conditions) > 0 and len(existing_conditions) > 0:
            condition_overlap = self._calculate_condition_similarity(new_conditions, existing_conditions) > 0.4
        if operation_conflict and (shared_columns or condition_overlap):
            # Business term already required (NO_CONFLICT above if not), so this is a direct conflict
            return self.DIRECT_CONFLICT, 0.85, details

        # 7. Check temporal overlap (for time-based rules)
        new_time_window = new_rule.get("time_window")
        existing_time_window = existing_rule.get("time_window")
        details["temporal_overlap"] = new_time_window == existing_time_window

        # 8. Potential conflict if conditions overlap but not contradictory
        # Allow when tables unknown (new rule from extractor with no resolved entities) but conditions exist
        has_entity_basis = bool(shared_tables) or (not set(self._get_effective_entities(new_rule).get("tables", [])) and not set(self._get_effective_entities(new_rule).get("columns", [])) and bool(new_conditions))
        if (shared_tables or has_entity_basis) and len(new_conditions) > 0 and len(existing_conditions) > 0:
            condition_similarity = self._calculate_condition_similarity(new_conditions, existing_conditions)
            if condition_similarity > 0.4:
                return self.POTENTIAL_CONFLICT, condition_similarity * 0.8, details

        # 9. Related/compatible if same business term and operation but different conditions
        if details["business_term_match"] and new_op == existing_op and not contradictory:
            condition_similarity = self._calculate_condition_similarity(new_conditions, existing_conditions)
            if condition_similarity > 0.3 and condition_similarity < 0.9:
                return "related_compatible", 0.6 + condition_similarity * 0.3, details

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

                # Fuzzy field match for contradictions
                if self._fields_related(new_field, existing_field):
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
        """Calculate similarity between condition lists (fuzzy field matching)."""
        if not conditions1 or not conditions2:
            return 0.0

        matches = 0
        for cond1 in conditions1:
            for cond2 in conditions2:
                if (
                    self._fields_related(cond1.get("field", ""), cond2.get("field", ""))
                    and (cond1.get("operator") or "").lower() == (cond2.get("operator") or "").lower()
                ):
                    matches += 1
                    break

        return matches / max(len(conditions1), len(conditions2))

    def _calculate_subject_similarity(self, rule1: Dict[str, Any], rule2: Dict[str, Any]) -> float:
        """Calculate semantic similarity of rule subjects based on conditions and affected entities."""
        # Extract subject-related fields from conditions
        subjects1 = set()
        for cond in rule1.get("conditions", []):
            field = cond.get("field", "")
            if field:
                subjects1.add(field.lower())

        subjects2 = set()
        for cond in rule2.get("conditions", []):
            field = cond.get("field", "")
            if field:
                subjects2.add(field.lower())

        # Add affected columns as potential subjects
        entities1 = rule1.get("affected_entities", {})
        entities2 = rule2.get("affected_entities", {})
        for col in entities1.get("columns", []):
            subjects1.add(col.lower())
        for col in entities2.get("columns", []):
            subjects2.add(col.lower())

        if not subjects1 or not subjects2:
            return 0.0

        intersection = subjects1 & subjects2
        union = subjects1 | subjects2
        return len(intersection) / len(union) if union else 0.0

    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity using SequenceMatcher."""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, s1, s2).ratio()

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

        elif conflict_type == "related_compatible":
            recommendations.append("These rules are related but compatible - consider whether to merge or keep separate")
            recommendations.append("Verify that the conditions do not create unintended gaps or overlaps")
            recommendations.append("Document the relationship between these rules for future reference")

        else:
            recommendations.append("No direct conflicts detected")

        return recommendations


class RealConflictDetectionService:
    """Production conflict detection service with pgvector semantic retrieval."""

    # Top-K candidates to retrieve for detailed comparison
    CANDIDATE_K = 10

    # Similarity threshold for pgvector retrieval
    SEMANTIC_SIMILARITY_THRESHOLD = 0.40

    def __init__(self):
        """Initialize service."""
        self.detector = ConflictDetector()
        self.embedding_service = None
        self.pgvector_service = None
        self._init_services()

    def _init_services(self):
        """Initialize embedding and pgvector services."""
        try:
            from app.services.embedding_service import get_embedding_service
            from app.services.pgvector_service import get_pgvector_service

            self.embedding_service = get_embedding_service()
            self.pgvector_service = get_pgvector_service()
        except Exception as e:
            print(f"Warning: Could not initialize embedding services: {e}")

    def check_conflict(
        self,
        suggested_rule: Dict[str, Any],
        workspace_id: str,
        domain_id: str,
        db=None,
    ) -> Dict[str, Any]:
        """
        Check if suggested rule conflicts with existing rules using TWO-STAGE pipeline per spec 8.7.2.

        Stage 1: Retrieve candidate rules using pgvector or fallback to domain-packs JSON
        Stage 2: Structured rule comparison (business term, operation, conditions, scope, time window, thresholds, affected fields)

        Per spec 8.7.2: "Final conflict decisions are based on structured rule comparison rather than semantic similarity scores."

        Returns:
            {
                "has_conflict": bool,
                "conflict_type": "direct_conflict|potential_conflict|no_conflict",
                "conflicting_rule_ids": [str],
                "confidence": float (0.0-1.0),
                "details": {...}
            }
        """
        try:
            # Debug: show incoming suggested_rule for troubleshooting
            try:
                print("DEBUG: check_conflict - suggested_rule:", json.dumps(suggested_rule, default=str))
            except Exception:
                print("DEBUG: check_conflict - suggested_rule (repr):", repr(suggested_rule))
            # STAGE 1: Retrieve candidate rules using pgvector, then fallback to domain-packs JSON
            candidate_rules = self._retrieve_candidate_rules_pgvector(suggested_rule, domain_id) or self._fallback_load_domain_pack_rules(domain_id)

            if not candidate_rules:
                return {
                    "has_conflict": False,
                    "conflict_type": "no_conflict",
                    "conflicting_rule_ids": [],
                    "confidence": 0.0,
                    "retrieval_stage": 0,
                    "details": {},
                }

            # STAGE 2: Structured rule comparison for each candidate
            conflicting_ids = []
            conflicts_found = []
            # Debug: log candidate rules count and ids
            if candidate_rules:
                try:
                    ids = [r.get("rule_id") for r in candidate_rules]
                    print(f"DEBUG: Retrieved {len(candidate_rules)} candidate_rules, ids={ids}")
                except Exception:
                    print("DEBUG: Retrieved candidate_rules (could not extract ids)")

            for active_rule in candidate_rules:
                # Compare suggested_rule with active_rule using structured logic
                conflict_result = self._structured_rule_comparison(suggested_rule, active_rule)

                # Debug: log per-candidate comparison result
                try:
                    print(f"DEBUG: comparing suggested_rule -> active_rule={active_rule.get('rule_id')}, conflict_result={json.dumps(conflict_result, default=str)}")
                except Exception:
                    print(f"DEBUG: comparing suggested_rule -> active_rule={active_rule.get('rule_id')}, conflict_result(repr)={repr(conflict_result)}")

                if conflict_result["has_conflict"]:
                    conflicting_ids.append(active_rule.get("rule_id"))
                    conflicts_found.append({
                        "rule_id": active_rule.get("rule_id"),
                        "conflict_type": conflict_result["conflict_type"],
                        "confidence": conflict_result["confidence"],
                        "comparison_details": conflict_result["details"],
                    })

            if not conflicting_ids:
                return {
                    "has_conflict": False,
                    "conflict_type": "no_conflict",
                    "conflicting_rule_ids": [],
                    "confidence": 0.0,
                    "retrieval_stage": len(candidate_rules),
                    "details": {},
                }

            # Aggregate results
            worst_conflict = max(conflicts_found, key=lambda x: x["confidence"])

            return {
                "has_conflict": True,
                "conflict_type": worst_conflict["conflict_type"],
                "conflicting_rule_ids": conflicting_ids,
                "confidence": round(worst_conflict["confidence"], 2),
                "retrieval_stage": len(candidate_rules),
                "details": {
                    "all_conflicts": conflicts_found,
                    "primary_conflict": worst_conflict,
                },
            }

        except Exception as e:
            print(f"Error in conflict detection: {e}")
            import traceback
            traceback.print_exc()
            return {
                "has_conflict": False,
                "conflict_type": "no_conflict",
                "conflicting_rule_ids": [],
                "confidence": 0.0,
                "retrieval_stage": 0,
                "details": {"error": str(e)},
            }

    def _structured_rule_comparison(self, new_rule: Dict[str, Any], existing_rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stage 2: Structured rule comparison per spec 8.7.2.

        Compares rule components:
        - Business Term: Same or Different
        - Operation: Compatible or Contradictory
        - Conditions: Equivalent, Broader, Narrower, or Different
        - Scope: Same, Overlapping, or Independent
        - Time Window: Same or Overlapping
        - Threshold Values: Equal, Increased, Decreased, or Conflicting
        - Affected Fields: Same, Partial, or Different
        """
        details = {}

        # Normalize affected entities using the same merge logic as baseline:
        # accept either `affected_entities` or top-level `affected_tables` / `affected_columns` fields.
        new_entities = self.detector._get_effective_entities(new_rule)
        exist_entities = self.detector._get_effective_entities(existing_rule)
        # Write back so downstream code sees the merged form
        new_rule["affected_entities"] = new_entities
        existing_rule["affected_entities"] = exist_entities

        # 1. Business Term Comparison
        new_term = (new_rule.get("business_term") or "").lower()
        exist_term = (existing_rule.get("business_term") or "").lower()
        term_similarity = self.detector._string_similarity(new_term, exist_term)
        details["business_term"] = {
            "new": new_term,
            "existing": exist_term,
            "similarity": round(term_similarity, 3),
            "match": term_similarity > 0.85
        }

        # Debug: log incoming terms and similarity
        print(f"DEBUG: _structured_rule_comparison - new_term='{new_term}', exist_term='{exist_term}', similarity={details['business_term']['similarity']}")

        # If business terms don't match, no conflict possible
        if term_similarity < 0.85:
            return {
                "has_conflict": False,
                "conflict_type": "no_conflict",
                "confidence": 0.0,
                "details": details,
            }

        # 2. Scope Comparison
        new_scope = (new_rule.get("scope") or "global").lower()
        exist_scope = (existing_rule.get("scope") or "global").lower()
        scope_overlap = new_scope == exist_scope or new_scope == "global" or exist_scope == "global"
        details["scope"] = {
            "new": new_scope,
            "existing": exist_scope,
            "overlap": scope_overlap
        }

        # If scopes don't overlap, no conflict
        if not scope_overlap:
            return {
                "has_conflict": False,
                "conflict_type": "no_conflict",
                "confidence": 0.0,
                "details": details,
            }

        # 3. Affected Fields Comparison
        new_entities = new_rule.get("affected_entities", {})
        exist_entities = existing_rule.get("affected_entities", {})
        new_tables = set(new_entities.get("tables", []))
        exist_tables = set(exist_entities.get("tables", []))

        # Fuzzy table match: singularized intersection
        new_tables_norm = {self.detector._singularize(t) for t in new_tables} if new_tables else set()
        exist_tables_norm = {self.detector._singularize(t) for t in exist_tables} if exist_tables else set()
        shared_tables = (new_tables & exist_tables) | (new_tables_norm & exist_tables_norm)

        # Get columns from affected_entities, or derive from conditions if empty
        new_columns = set(new_entities.get("columns", []))
        if not new_columns:
            # Infer columns from conditions
            for cond in new_rule.get("conditions", []):
                field = cond.get("field", "")
                if field:
                    new_columns.add(field)

        exist_columns = set(exist_entities.get("columns", []))
        if not exist_columns:
            # Infer columns from conditions
            for cond in existing_rule.get("conditions", []):
                field = cond.get("field", "")
                if field:
                    exist_columns.add(field)

        shared_columns = new_columns & exist_columns
        # Fuzzy column match (singularized tokens)
        if not shared_columns:
            for nc in list(new_columns):
                nc_tokens = {self.detector._singularize(t) for t in self.detector._field_tokens(nc)}
                for ec in list(exist_columns):
                    ec_tokens = {self.detector._singularize(t) for t in self.detector._field_tokens(ec)}
                    if nc_tokens & ec_tokens:
                        shared_columns = {nc, ec}
                        break
                if shared_columns and shared_columns != (new_columns & exist_columns):
                    break

        details["affected_fields"] = {
            "new_tables": list(new_tables),
            "existing_tables": list(exist_tables),
            "shared_tables": list(shared_tables),
            "new_columns": list(new_columns),
            "existing_columns": list(exist_columns),
            "shared_columns": list(shared_columns),
        }

        # Debug: log shared tables/columns
        print(f"DEBUG: affected_fields shared_tables={details['affected_fields']['shared_tables']}, shared_columns={details['affected_fields']['shared_columns']}")

        # If no shared fields, allow fall-through for entity-less rules with conditions
        if not shared_tables or not shared_columns:
            # When new rule has no resolved entities but has conditions, allow condition-level check
            new_has_any = bool(new_tables or new_columns)
            if not new_has_any and (new_rule.get("conditions") or new_rule.get("candidate_conditions")):
                pass  # Allow fall-through to condition comparison below
            else:
                return {
                    "has_conflict": False,
                    "conflict_type": "no_conflict",
                    "confidence": 0.0,
                    "details": details,
                }

        # 4. Operation Comparison (Contradictory or Compatible)
        new_op = (new_rule.get("operation") or "").lower()
        exist_op = (existing_rule.get("operation") or "").lower()

        contradictory_pairs = [
            ("exclude", "include"),
            ("restrict", "allow"),
            ("mask", "expose"),
            ("drop", "keep"),
            ("subtract", "include"),
            ("add", "exclude"),
        ]

        operation_conflict = False
        for pair in contradictory_pairs:
            if (new_op == pair[0] and exist_op == pair[1]) or (new_op == pair[1] and exist_op == pair[0]):
                operation_conflict = True
                break

        details["operation"] = {
            "new": new_op,
            "existing": exist_op,
            "contradictory": operation_conflict
        }

        # 5. Conditions Comparison
        new_conds = new_rule.get("conditions", [])
        exist_conds = existing_rule.get("conditions", [])
        cond_similarity = self.detector._calculate_condition_similarity(new_conds, exist_conds)

        details["conditions"] = {
            "new_count": len(new_conds),
            "existing_count": len(exist_conds),
            "similarity": round(cond_similarity, 3),
        }

        # 6. Time Window Comparison
        new_time = new_rule.get("time_window")
        exist_time = existing_rule.get("time_window")
        time_overlap = new_time == exist_time or (new_time is None and exist_time is None)

        details["time_window"] = {
            "new": new_time,
            "existing": exist_time,
            "overlap": time_overlap
        }

        # 7. Threshold Comparison
        new_thresh = new_rule.get("threshold")
        exist_thresh = existing_rule.get("threshold")

        details["threshold"] = {
            "new": new_thresh,
            "existing": exist_thresh,
            "conflict": new_thresh is not None and exist_thresh is not None and new_thresh != exist_thresh and operation_conflict
        }

        # DECISION LOGIC per spec:
        # - Direct Conflict: Contradictory operations on shared fields with same business term and overlapping scope
        #   Also fires when operation conflicts and conditions overlap (even without explicit shared columns)
        condition_overlap = cond_similarity > 0.4
        if operation_conflict and (shared_columns or shared_tables or condition_overlap):
            return {
                "has_conflict": True,
                "conflict_type": "direct_conflict",
                "confidence": 0.9,
                "details": details,
            }

        # - Potential Conflict: Similar conditions but not exact contradictory operations
        if cond_similarity > 0.5:
            return {
                "has_conflict": True,
                "conflict_type": "potential_conflict",
                "confidence": round(0.5 + (cond_similarity * 0.4), 2),
                "details": details,
            }

        # - No Conflict
        return {
            "has_conflict": False,
            "conflict_type": "no_conflict",
            "confidence": 0.0,
            "details": details,
        }

    def _retrieve_candidates(
        self,
        suggested_rule: Dict[str, Any],
        workspace_id: str,
        domain_id: str,
        db,
    ) -> List[Dict[str, Any]]:
        """
        STAGE 1: Retrieve Top-K semantically similar candidates using pgvector.

        This is the optimization: instead of comparing against all 100+ rules,
        we pre-filter to ~10 most similar rules for conflict checking.

        Falls back to loading all rules from domain pack JSON if pgvector unavailable.

        Args:
            suggested_rule: The new rule to check
            workspace_id: Workspace to search in
            domain_id: Domain to filter by
            db: SQLAlchemy session

        Returns:
            List of candidate rules with similarity_score, or empty list if none found
        """
        # Try pgvector first if available
        candidates_from_pgvector = None
        if self.embedding_service and self.pgvector_service:
            try:
                # Generate embedding text from rule
                rule_text = self._generate_rule_embedding_text(suggested_rule)
                if rule_text:
                    # Generate embedding
                    embedding = self.embedding_service.generate_embedding(rule_text)
                    if embedding:
                        # Query pgvector for Top-K similar rules
                        try:
                            candidates_from_pgvector = self.pgvector_service.retrieve_similar_rules(
                                embedding=embedding,
                                workspace_id=workspace_id,
                                domain_id=domain_id,
                                top_k=self.CANDIDATE_K,
                                similarity_threshold=self.SEMANTIC_SIMILARITY_THRESHOLD,
                                db=db,
                            )
                        except Exception as pgv_error:
                            print(f"pgvector query failed (extension may not be installed): {pgv_error}")
                            candidates_from_pgvector = None

                        # If pgvector succeeded, return those candidates
                        if candidates_from_pgvector:
                            return candidates_from_pgvector

            except Exception as e:
                print(f"Warning: pgvector embedding generation failed: {e}")

        # Fallback: Load all rules from domain pack JSON
        fallback_candidates = self._fallback_load_domain_pack_rules(domain_id)
        return fallback_candidates

    def _generate_rule_embedding_text(self, rule: Dict[str, Any]) -> str:
        """Generate text representation of a rule for embedding."""
        parts = []

        if rule.get("business_term"):
            parts.append(f"Business term: {rule['business_term']}")

        if rule.get("operation"):
            parts.append(f"Operation: {rule['operation']}")

        if rule.get("conditions"):
            conditions_text = ", ".join([
                f"{c.get('field')} {c.get('operator')} {c.get('value')}"
                for c in rule.get("conditions", [])
            ])
            if conditions_text:
                parts.append(f"Conditions: {conditions_text}")

        if rule.get("scope"):
            parts.append(f"Scope: {rule['scope']}")

        if rule.get("time_window"):
            parts.append(f"Time window: {rule['time_window']}")

        if rule.get("threshold"):
            parts.append(f"Threshold: {rule['threshold']}")

        if rule.get("affected_entities"):
            ae = rule.get("affected_entities", {})
            if ae.get("tables"):
                parts.append(f"Tables: {', '.join(ae['tables'])}")
            if ae.get("columns"):
                parts.append(f"Columns: {', '.join(ae['columns'])}")

        return " | ".join(parts) if parts else "rule"

    def _rules_conflict(self, rule1: Dict[str, Any], rule2: Dict[str, Any]) -> bool:
        """Check if two rules have conflicting characteristics."""
        # Same business term
        bt1 = (rule1.get("business_term") or "").lower()
        bt2 = (rule2.get("business_term") or "").lower()

        if not bt1 or not bt2 or bt1 != bt2:
            return False

        # Shared affected entities
        entities1 = rule1.get("affected_entities", {})
        entities2 = rule2.get("affected_entities", {})

        tables1 = set(entities1.get("tables", []))
        tables2 = set(entities2.get("tables", []))

        if not (tables1 & tables2):
            return False

        # Conflicting operations
        op1 = (rule1.get("operation") or "").lower()
        op2 = (rule2.get("operation") or "").lower()

        conflicting_ops = [
            ("exclude", "include"),
            ("restrict", "allow"),
            ("mask", "expose"),
            ("drop", "keep"),
        ]

        for pair in conflicting_ops:
            if (op1 == pair[0] and op2 == pair[1]) or (op1 == pair[1] and op2 == pair[0]):
                return True

        return False

    def _retrieve_candidate_rules_pgvector(self, suggested_rule: Dict[str, Any], domain_id: str) -> List[Dict[str, Any]]:
        """
        STAGE 1: Retrieve candidate rules using pgvector semantic retrieval.

        Strategy:
        1. ALWAYS load active_rules.json from domain pack (canonical rules)
        2. Query pgvector for semantically similar rules from database
        3. Merge and deduplicate, prioritizing domain pack rules

        Returns:
            List of candidate rules or None if pgvector not available
        """
        candidates = []

        # FIRST: Load active domain pack rules (PRIMARY - canonical source)
        try:
            from pathlib import Path
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
                                "source": "domain_pack",
                                "similarity_score": 1.0
                            }
                            candidates.append(rule)
        except Exception as pack_e:
            print(f"Warning: Could not load active rules from {domain_id}/rules/active_rules.json: {pack_e}")

        # SECOND: Supplement with pgvector-retrieved database rules (if available)
        if self.embedding_service and self.pgvector_service:
            try:
                rule_text = self.embedding_service.generate_rule_embedding_text(suggested_rule)
                if rule_text:
                    embedding = self.embedding_service.generate_embedding(rule_text)
                    if embedding:
                        # Query pgvector for similar rules
                        user_candidates = self.pgvector_service.retrieve_similar_rules(
                            embedding=embedding,
                            domain_id=domain_id,
                            top_k=self.CANDIDATE_K,
                            similarity_threshold=self.SEMANTIC_SIMILARITY_THRESHOLD,
                        )

                        # Merge: avoid duplicates by rule_id
                        candidates_dict = {c.get("rule_id"): c for c in candidates}
                        for c in user_candidates:
                            rule_id = c.get("rule_id")
                            # Only add if not already present (domain pack takes precedence)
                            if rule_id not in candidates_dict:
                                c["source"] = "database"
                                candidates_dict[rule_id] = c

                        candidates = list(candidates_dict.values())
            except Exception as pg_e:
                print(f"Warning: pgvector retrieval failed: {pg_e}")

        # Sort by similarity descending and limit to top-K
        candidates.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        candidates = candidates[:self.CANDIDATE_K]

        return candidates if candidates else None

    def _fallback_load_domain_pack_rules(self, domain_id: str) -> List[Dict[str, Any]]:
        """Fallback: Load all active rules from domain pack JSON files."""
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

            # Normalize and return all rules
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
            print(f"Error loading domain pack rules: {e}")
            return []

    def _load_conflicting_rules_ground_truth(self, domain_id: str) -> Dict[str, List[str]]:
        """Load pre-defined conflicting rules from domain pack JSON files.

        Returns a mapping of rule_id -> list of rule_ids it conflicts with.
        """
        try:
            from pathlib import Path

            conflicting_rules_path = (
                Path(__file__).parent.parent.parent /
                "rie_ml" / "domain-packs" / domain_id / "rules" / "conflicting_rules.json"
            )

            if not conflicting_rules_path.exists():
                return {}

            with open(conflicting_rules_path, 'r') as f:
                conflicts_list = json.load(f)

            # Build bidirectional mapping
            conflicts_map = {}
            for conflict_rule in conflicts_list:
                rule_id = conflict_rule.get("rule_id")
                conflicts_with = conflict_rule.get("conflicts_with")
                conflict_type = conflict_rule.get("conflict_type", "direct_conflict")

                if rule_id and conflicts_with:
                    if rule_id not in conflicts_map:
                        conflicts_map[rule_id] = []
                    conflicts_map[rule_id].append({
                        "rule_id": conflicts_with,
                        "conflict_type": conflict_type,
                    })

                    # Add reverse mapping
                    if conflicts_with not in conflicts_map:
                        conflicts_map[conflicts_with] = []
                    conflicts_map[conflicts_with].append({
                        "rule_id": rule_id,
                        "conflict_type": conflict_type,
                    })

            return conflicts_map

        except Exception as e:
            print(f"Error loading conflicting rules ground truth: {e}")
            return {}

