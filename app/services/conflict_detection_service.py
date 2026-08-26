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

        # Only consider operation conflict if business terms and subjects are similar
        if operation_conflict and shared_columns and details["business_term_similarity"] > 0.7 and details["subject_similarity"] > 0.5:
            return self.DIRECT_CONFLICT, 0.85, details

        # 7. Check temporal overlap (for time-based rules)
        new_time_window = new_rule.get("time_window")
        existing_time_window = existing_rule.get("time_window")
        details["temporal_overlap"] = new_time_window == existing_time_window

        # 8. Potential conflict if conditions overlap but not contradictory
        if shared_tables and len(new_conditions) > 0 and len(existing_conditions) > 0:
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
        Check if suggested rule conflicts with existing rules using two-stage pipeline.

        Stage 1 (NEW): Semantic retrieval via pgvector
        - Generate embedding for suggested rule
        - Query pgvector for Top-K semantically similar rules
        - Filters from 100+ rules to ~10 candidates

        Stage 2 (EXISTING): Conflict analysis on candidates
        - Detailed conflict analysis of candidate rules only
        - Determines direct conflict vs potential vs no conflict

        Returns:
            {
                "has_conflict": bool,
                "conflict_type": "direct_conflict|potential_conflict|temporal_conflict|scope_conflict|no_conflict",
                "conflicting_rule_ids": [str],
                "confidence": float (0.0-1.0),
                "semantic_similarity": float (from pgvector),
                "retrieval_stage": int (number of candidates retrieved),
                "details": {...}
            }
        """
        if not db:
            return {
                "has_conflict": False,
                "conflict_type": "no_conflict",
                "conflicting_rule_ids": [],
                "confidence": 0.0,
                "semantic_similarity": 0.0,
                "retrieval_stage": 0,
                "details": {"reason": "No database connection"},
            }

        try:
            # STAGE 1: Semantic Retrieval via pgvector
            candidates = self._retrieve_candidates(
                suggested_rule,
                workspace_id,
                domain_id,
                db,
            )

            # If no candidates found, no conflict
            if not candidates:
                return {
                    "has_conflict": False,
                    "conflict_type": "no_conflict",
                    "conflicting_rule_ids": [],
                    "confidence": 0.0,
                    "semantic_similarity": 0.0,
                    "retrieval_stage": 0,
                    "details": {"reason": "No semantically similar rules found"},
                }

            # STAGE 2: Conflict Analysis on Candidates
            result = self.detector.detect(suggested_rule, candidates)

            # Enhance result with pgvector data
            result["semantic_similarity"] = round(
                candidates[0].get("similarity_score", 0.0) if candidates else 0.0,
                3
            )
            result["retrieval_stage"] = len(candidates)

            return result

        except Exception as e:
            print(f"Error in conflict detection: {e}")
            import traceback
            traceback.print_exc()
            return {
                "has_conflict": False,
                "conflict_type": "no_conflict",
                "conflicting_rule_ids": [],
                "confidence": 0.0,
                "semantic_similarity": 0.0,
                "retrieval_stage": 0,
                "details": {"error": str(e)},
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

        Args:
            suggested_rule: The new rule to check
            workspace_id: Workspace to search in
            domain_id: Domain to filter by
            db: SQLAlchemy session

        Returns:
            List of candidate rules with similarity_score, or empty list if none found
        """
        # If no embedding service, fall back to fetching all rules
        if not self.embedding_service or not self.pgvector_service:
            return self._fallback_retrieve_all_rules(workspace_id, domain_id, db)

        try:
            # Generate embedding for the suggested rule
            rule_text = self.embedding_service.generate_rule_embedding_text(suggested_rule)
            if not rule_text:
                return self._fallback_retrieve_all_rules(workspace_id, domain_id, db)

            embedding = self.embedding_service.generate_embedding(rule_text)
            if not embedding:
                return self._fallback_retrieve_all_rules(workspace_id, domain_id, db)

            # Query pgvector for Top-K similar rules
            # Search in BOTH user workspace AND domain pack workspace (reference rules)
            user_candidates = self.pgvector_service.retrieve_similar_rules(
                embedding=embedding,
                workspace_id=workspace_id,
                domain_id=domain_id,
                top_k=self.CANDIDATE_K,
                similarity_threshold=self.SEMANTIC_SIMILARITY_THRESHOLD,
                db=db,
            )

            # Also search domain pack workspace for reference rules
            domain_pack_candidates = self.pgvector_service.retrieve_similar_rules(
                embedding=embedding,
                workspace_id="domain_pack_workspace",
                domain_id=domain_id,
                top_k=self.CANDIDATE_K,
                similarity_threshold=self.SEMANTIC_SIMILARITY_THRESHOLD,
                db=db,
            )

            # Merge and deduplicate candidates (domain pack + user workspace)
            candidates_dict = {}
            for c in user_candidates + domain_pack_candidates:
                rule_id = c.get("rule_id")
                if rule_id not in candidates_dict or c.get("similarity_score", 0) > candidates_dict[rule_id].get("similarity_score", 0):
                    candidates_dict[rule_id] = c

            candidates = list(candidates_dict.values())
            # Sort by similarity descending and take top K
            candidates.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
            candidates = candidates[:self.CANDIDATE_K]

            return candidates

        except Exception as e:
            print(f"Warning: pgvector retrieval failed, falling back to all rules: {e}")
            return self._fallback_retrieve_all_rules(workspace_id, domain_id, db)

    def _fallback_retrieve_all_rules(
        self,
        workspace_id: str,
        domain_id: str,
        db,
    ) -> List[Dict[str, Any]]:
        """
        Fallback: Retrieve all rules when pgvector is not available.

        Used if embedding service fails or pgvector extension not installed.
        """
        try:
            from sqlalchemy import text

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
            existing_rules = []

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
                    "similarity_score": 0.0,  # No semantic score in fallback
                }
                existing_rules.append(rule)

            return existing_rules

        except Exception as e:
            print(f"Error in fallback retrieval: {e}")
            return []
