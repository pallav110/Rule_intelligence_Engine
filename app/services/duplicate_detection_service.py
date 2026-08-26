"""Real duplicate detection service using semantic and structural matching."""

from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher
import json
import re


class DuplicateDetector:
    """Detect duplicate and related rules using semantic and structural matching."""

    # Relationship types
    EXACT_DUPLICATE = "exact_duplicate"
    SEMANTIC_DUPLICATE = "semantic_duplicate"
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
        Detect if new_rule duplicates or relates to existing rules.

        Returns:
            {
                "relationship": str,  # One of the relationship types above
                "matching_rule_id": str or None,
                "confidence": float,
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
                "details": {},
            }

        best_match = None
        best_relationship = self.UNRELATED
        best_confidence = 0.0

        for existing_rule in existing_rules:
            relationship, confidence, details = self._compare_rules(new_rule, existing_rule)

            if confidence > best_confidence:
                best_confidence = confidence
                best_relationship = relationship
                best_match = existing_rule

        return {
            "relationship": best_relationship,
            "matching_rule_id": best_match.get("rule_id") if best_match else None,
            "confidence": round(best_confidence, 3),
            "details": self._extract_match_details(new_rule, best_match) if best_match else {},
        }

    def _compare_rules(self, new_rule: Dict[str, Any], existing_rule: Dict[str, Any]) -> Tuple[str, float, Dict]:
        """Compare two rules and return relationship type, confidence, and details."""
        details = {
            "business_term_match": False,
            "condition_similarity": 0.0,
            "operation_match": False,
            "scope_match": False,
            "affected_entities_match": 0.0,
            "threshold_match": False,
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

        # 4. Compare conditions
        new_conditions = new_rule.get("conditions", [])
        existing_conditions = existing_rule.get("conditions", [])
        condition_similarity = self._compare_conditions(new_conditions, existing_conditions)
        details["condition_similarity"] = round(condition_similarity, 3)

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

    def _compare_conditions(self, new_conditions: List[Dict], existing_conditions: List[Dict]) -> float:
        """
        Compare condition lists.
        Returns similarity score 0.0-1.0
        """
        if not new_conditions and not existing_conditions:
            return 1.0
        if not new_conditions or not existing_conditions:
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
        if (
            business_term_match
            and condition_sim > 0.85
            and entities_sim > 0.8
        ):
            confidence = min(0.95, (condition_sim + entities_sim) / 2 + 0.1)
            return self.SEMANTIC_DUPLICATE, confidence

        # MODIFICATION: same business term, same operation, different conditions
        if (
            business_term_match
            and operation_match
            and condition_sim > 0.5
            and condition_sim < 0.9
        ):
            confidence = min(0.85, (condition_sim + 0.7) / 2)
            return self.MODIFICATION, confidence

        # EXTENSION: same business term, same operation, more conditions or entities
        if (
            business_term_match
            and operation_match
            and scope_match
            and len(new_rule.get("conditions", [])) >= len(existing_rule.get("conditions", []))
            and condition_sim > 0.4
        ):
            confidence = min(0.8, condition_sim + 0.3)
            return self.EXTENSION, confidence

        # SUBSET: existing rule is superset of new rule (same business term)
        if business_term_match and condition_sim > 0.6 and len(new_rule.get("conditions", [])) < len(existing_rule.get("conditions", [])):
            confidence = condition_sim * 0.8
            return self.SUBSET, confidence

        # SUPERSET: new rule is superset of existing (same business term)
        if business_term_match and condition_sim > 0.6 and len(new_rule.get("conditions", [])) > len(existing_rule.get("conditions", [])):
            confidence = condition_sim * 0.75
            return self.SUPERSET, confidence

        # RELATED COMPATIBLE: same business term and operation but different conditions
        if business_term_match and operation_match and not scope_match:
            confidence = min(0.65, condition_sim * 0.7 + 0.2)
            return "related_compatible", confidence

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


class RealDuplicateDetectionService:
    """Production duplicate detection service with pgvector semantic retrieval."""

    # Top-K candidates to retrieve for detailed comparison
    CANDIDATE_K = 10

    # Similarity threshold for pgvector retrieval
    SEMANTIC_SIMILARITY_THRESHOLD = 0.40

    def __init__(self):
        """Initialize service."""
        self.detector = DuplicateDetector()
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

    def check_duplicate(
        self,
        suggested_rule: Dict[str, Any],
        workspace_id: str,
        domain_id: str,
        db=None,
    ) -> Dict[str, Any]:
        """
        Check if suggested rule duplicates existing rules using two-stage pipeline.

        Stage 1 (NEW): Semantic retrieval via pgvector
        - Generate embedding for suggested rule
        - Query pgvector for Top-K semantically similar rules
        - Filters from 100+ rules to ~10 candidates

        Stage 2 (EXISTING): Structural comparison
        - Detailed comparison of candidate rules only
        - Determines exact duplicate vs semantic duplicate vs modification

        Returns:
            {
                "relationship": "exact_duplicate|semantic_duplicate|modification|extension|unrelated",
                "is_duplicate": bool,
                "matching_rule_id": str or None,
                "confidence": float (0.0-1.0),
                "semantic_similarity": float (from pgvector),
                "retrieval_stage": int (number of candidates retrieved),
                "details": {...}
            }
        """
        if not db:
            return {
                "is_duplicate": False,
                "relationship": "unrelated",
                "matching_rule_id": None,
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

            # If no candidates found, not a duplicate
            if not candidates:
                return {
                    "is_duplicate": False,
                    "relationship": "unrelated",
                    "matching_rule_id": None,
                    "confidence": 0.0,
                    "semantic_similarity": 0.0,
                    "retrieval_stage": 0,
                    "details": {"reason": "No semantically similar rules found"},
                }

            # STAGE 2: Structural Comparison on Candidates
            result = self.detector.detect(suggested_rule, candidates)

            # Enhance result with pgvector data
            result["is_duplicate"] = result["confidence"] > 0.7 and result["relationship"] in [
                "exact_duplicate",
                "semantic_duplicate",
            ]
            result["semantic_similarity"] = round(
                candidates[0].get("similarity_score", 0.0) if candidates else 0.0,
                3
            )
            result["retrieval_stage"] = len(candidates)

            return result

        except Exception as e:
            print(f"Error in duplicate detection: {e}")
            import traceback
            traceback.print_exc()
            return {
                "is_duplicate": False,
                "relationship": "unrelated",
                "matching_rule_id": None,
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
        we pre-filter to ~10 most similar rules.

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
