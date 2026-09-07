"""Real duplicate detection service using semantic and structural matching."""

from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher
from pathlib import Path
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

        # 4. Compare conditions (including candidate conditions for semantic matching)
        new_conditions = new_rule.get("conditions", [])
        existing_conditions = existing_rule.get("conditions", [])
        new_candidate_conditions = new_rule.get("candidate_conditions", [])
        condition_similarity = self._compare_conditions(
            new_conditions, existing_conditions, new_rule, existing_rule,
            candidate_conditions=new_candidate_conditions,
        )
        details["condition_similarity"] = round(condition_similarity, 3)

        # 5. Compare affected entities (tables and columns) — merge both key styles
        new_entities = self._get_effective_entities(new_rule)
        existing_entities = self._get_effective_entities(existing_rule)
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

    def _compare_conditions(
        self, new_conditions: List[Dict], existing_conditions: List[Dict],
        new_rule: Dict = None, existing_rule: Dict = None,
        candidate_conditions: List[Dict] = None,
    ) -> float:
        """
        Compare condition lists.
        Returns similarity score 0.0-1.0.

        Strategy:
        - If BOTH are empty: perfect match (1.0)
        - If ONE is empty, check if entities/fuzzy match gives partial credit (0.5)
        - If candidate conditions present, boost similarity via fuzzy token overlap
        - If BOTH have conditions: compare field-by-field with fuzzy matching
        """
        if not new_conditions and not existing_conditions:
            return 1.0

        # If new rule has no conditions but HAS candidate conditions, boost similarity
        if not new_conditions and candidate_conditions and existing_conditions:
            candidate_texts = [c.get("text", "").lower() for c in candidate_conditions]
            candidate_text = " ".join(candidate_texts)
            for cond in existing_conditions if existing_conditions else []:
                field = (cond.get("field") or "").lower()
                for token in self._field_tokens(field):
                    if token in candidate_text or self._singularize(token) in candidate_text:
                        return 0.65  # Good semantic match via candidate conditions

        if not new_conditions or not existing_conditions:
            if new_conditions and not existing_conditions:
                # New rule has conditions, existing doesn't — check effective entities
                existing_ent = self._get_effective_entities(existing_rule) if existing_rule else {}
                existing_fields = set(f.lower() for f in existing_ent.get("columns", []))
                new_fields = set((cond.get("field") or "").lower() for cond in new_conditions if cond)
                for nf in new_fields:
                    nf_tokens = {self._singularize(t) for t in self._field_tokens(nf)}
                    for ef in existing_fields:
                        ef_tokens = {self._singularize(t) for t in self._field_tokens(ef)}
                        if nf_tokens & ef_tokens:
                            return 0.5
            elif existing_conditions and not new_conditions:
                new_ent = self._get_effective_entities(new_rule) if new_rule else {}
                new_fields = set(f.lower() for f in new_ent.get("columns", []))
                existing_fields = set((cond.get("field") or "").lower() for cond in existing_conditions if cond)
                for nf in new_fields:
                    nf_tokens = {self._singularize(t) for t in self._field_tokens(nf)}
                    for ef in existing_fields:
                        ef_tokens = {self._singularize(t) for t in self._field_tokens(ef)}
                        if nf_tokens & ef_tokens:
                            return 0.5
            return 0.5

        # Normalize conditions for comparison
        new_normalized = self._normalize_conditions(new_conditions)
        existing_normalized = self._normalize_conditions(existing_conditions)

        # Count matching conditions using fuzzy field comparison
        matching = 0
        for new_cond in new_normalized:
            for existing_cond in existing_normalized:
                if self._conditions_equal(new_cond, existing_cond):
                    matching += 1
                    break

        total = max(len(new_normalized), len(existing_normalized))
        return matching / total if total > 0 else 0.0

    def _normalize_conditions(self, conditions) -> List[Dict]:
        """Normalize condition representation for comparison."""
        if not conditions:
            return []
        normalized = []
        for cond in conditions:
            if not cond or not isinstance(cond, dict):
                continue
            normalized.append(
                {
                    "field": (cond.get("field") or "").lower(),
                    "operator": (cond.get("operator") or "").lower(),
                    "value": str(cond.get("value", "")).lower() if cond.get("value") is not None else None,
                }
            )
        return normalized

    @staticmethod
    def _get_effective_entities(rule: Dict[str, Any]) -> Dict[str, Any]:
        """Build effective entities dict from affected_entities or affected_tables/affected_columns."""
        entities = rule.get("affected_entities") or {}
        tables = entities.get("tables") or rule.get("affected_tables") or []
        columns = entities.get("columns") or rule.get("affected_columns") or []
        return {"tables": tables, "columns": columns}

    @staticmethod
    def _field_tokens(field_name: str) -> set:
        """Split a field name into lowercase tokens (e.g. 'orders.status' -> {'orders','status'})."""
        return set(f.strip().lower() for f in field_name.split(".") if f.strip())

    @staticmethod
    def _singularize(token: str) -> str:
        """Very simple singularization: remove trailing 's' for plural forms."""
        t = token.lower().strip()
        return t[:-1] if t.endswith("s") and len(t) > 3 else t

    def _fields_related(self, f1: str, f2: str) -> bool:
        """Check if two field names are related via fuzzy comparison."""
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

    def _conditions_equal(self, cond1: Dict, cond2: Dict) -> bool:
        """Check if two conditions are equivalent (fuzzy field matching)."""
        field_match = self._fields_related(cond1.get("field") or "", cond2.get("field") or "")
        operator_match = (cond1.get("operator") or "").lower() == (cond2.get("operator") or "").lower()

        # Special handling for value comparison
        val1 = cond1.get("value")
        val2 = cond2.get("value")

        # For null checks, treat None and "None" as equivalent
        if (cond1.get("operator") or "").lower() in ["is_not_null", "is_null"]:
            value_match = True
        else:
            value_match = str(val1).lower() == str(val2).lower() if val1 is not None and val2 is not None else val1 == val2

        return field_match and operator_match and value_match

    def _compare_entities(self, new_entities: Dict, existing_entities: Dict) -> float:
        """
        Compare affected entities (tables and columns).
        Returns similarity score 0.0-1.0 (fuzzy matching for tables/columns).
        """
        new_tables = set(new_entities.get("tables", []))
        existing_tables = set(existing_entities.get("tables", []))
        new_columns = list(new_entities.get("columns", []))
        existing_columns = list(existing_entities.get("columns", []))

        # Fuzzy Jaccard for tables (singularized tokens)
        if new_tables or existing_tables:
            new_tok = {self._singularize(t) for t in new_tables}
            exist_tok = {self._singularize(t) for t in existing_tables}
            table_similarity = len(new_tok & exist_tok) / len(new_tok | exist_tok) if (new_tok | exist_tok) else 0.0
        else:
            table_similarity = 1.0

        # Fuzzy Jaccard for columns (singularized tokens)
        if new_columns or existing_columns:
            new_tok2 = {self._singularize(t) for t in new_columns}
            exist_tok2 = {self._singularize(t) for t in existing_columns}
            col_similarity = len(new_tok2 & exist_tok2) / len(new_tok2 | exist_tok2) if (new_tok2 | exist_tok2) else 0.0
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

        new_has_conditions = len(new_rule.get("conditions", [])) > 0
        existing_has_conditions = len(existing_rule.get("conditions", [])) > 0
        new_has_candidates = len(new_rule.get("candidate_conditions", [])) > 0

        # Check if entities are "unknown" (not extracted)
        new_entities = self._get_effective_entities(new_rule)
        existing_entities = self._get_effective_entities(existing_rule)
        both_entities_unknown = (
            (new_entities.get("columns", []) == ["unknown.unknown"] or not new_entities.get("columns")) and
            (existing_entities.get("columns", []) == ["unknown.unknown"] or not existing_entities.get("columns"))
        )

        # EXACT DUPLICATE: everything matches perfectly
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
            and operation_match
            and scope_match
            and (
                (condition_sim > 0.85 and entities_sim > 0.8) or
                # One rule has conditions, other doesn't, but same intent
                (new_has_conditions != existing_has_conditions and entities_sim > 0.6)
            )
        ):
            confidence = min(0.95, (condition_sim + entities_sim) / 2 + 0.1)
            return self.SEMANTIC_DUPLICATE, confidence

        # MODIFICATION: same business term, same operation, different conditions
        if (
            business_term_match
            and operation_match
            and (condition_sim > 0.5 and condition_sim < 0.9)
        ):
            confidence = min(0.85, (condition_sim + 0.7) / 2)
            return self.MODIFICATION, confidence

        # EXTENSION: candidate conditions matching existing rule's intent
        if (
            new_has_candidates
            and not new_has_conditions
            and existing_has_conditions
            and business_term_match
            and operation_match
        ):
            if both_entities_unknown or entities_sim > 0.3:
                confidence = 0.70
                return self.EXTENSION, confidence

        # EXTENSION: same operation/scope but more conditions or entities
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
        if business_term_match and condition_sim > 0.3 and len(new_rule.get("conditions", [])) < len(existing_rule.get("conditions", [])):
            confidence = condition_sim * 0.8
            return self.SUBSET, confidence

        # SUPERSET: new rule is superset of existing (same business term)
        if business_term_match and condition_sim > 0.3 and len(new_rule.get("conditions", [])) > len(existing_rule.get("conditions", [])):
            confidence = condition_sim * 0.75
            return self.SUPERSET, confidence

        # RELATED COMPATIBLE: same business term and operation but different scope
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
                    "retrieval_stage": 0,
                    "details": {"reason": "No semantically similar rules found"},
                }

            # STAGE 2: Structural Comparison on Candidates
            result = self.detector.detect(suggested_rule, candidates)

            # Enhance result with pgvector data
            result["is_duplicate"] = result["confidence"] > 0.7 and result["relationship"] in [
                "exact_duplicate",
                "semantic_duplicate",
                "extension",
                "modification",
            ]
            # semantic_similarity removed in V4 - using deterministic baseline
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
        STAGE 1: Retrieve Top-K semantically similar candidates.

        Strategy:
        1. ALWAYS load active_rules.json from domain pack (canonical rules)
        2. Query pgvector for semantically similar rules from database
        3. Merge and deduplicate, prioritizing domain pack rules

        Returns:
            List of candidate rules (domain_pack rules + pgvector results)
        """
        candidates = []

        # FIRST: Load active domain pack rules (PRIMARY - canonical source)
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
                                "source": "domain_pack",
                                "similarity_score": 1.0  # Domain rules are always relevant
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
                        # Query pgvector for user workspace rules
                        user_candidates = self.pgvector_service.retrieve_similar_rules(
                            embedding=embedding,
                            workspace_id=workspace_id,
                            domain_id=domain_id,
                            top_k=self.CANDIDATE_K,
                            similarity_threshold=self.SEMANTIC_SIMILARITY_THRESHOLD,
                            db=db,
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

        return candidates

    def _fallback_retrieve_all_rules(
        self,
        workspace_id: str,
        domain_id: str,
        db,
    ) -> List[Dict[str, Any]]:
        """
        Fallback: Retrieve all rules when pgvector is not available.

        Strategy:
        1. Load active_rules.json from domain pack (canonical rules)
        2. Supplement with database rules if they exist
        """
        existing_rules = []

        # FIRST: Load active domain pack rules (PRIMARY)
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
                                "source": "domain_pack"
                            }
                            existing_rules.append(rule)
        except Exception as pack_e:
            print(f"Warning: Could not load active rules from {domain_id}/rules/active_rules.json: {pack_e}")

        # SECOND: Supplement with database rules
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

            for row in result:
                db_rule = {
                    "rule_id": row[0],
                    "business_term": row[1],
                    "operation": row[2],
                    "conditions": json.loads(row[3]) if isinstance(row[3], str) else row[3] or [],
                    "scope": row[4],
                    "affected_entities": json.loads(row[5]) if isinstance(row[5], str) else row[5] or {},
                    "threshold": row[6],
                    "time_window": row[7],
                    "source": "database"
                }
                # Avoid duplicates - don't add if rule_id already exists
                if not any(er.get("rule_id") == db_rule.get("rule_id") for er in existing_rules):
                    existing_rules.append(db_rule)

            return existing_rules

        except Exception as e:
            print(f"Error in fallback retrieval: {e}")
            return existing_rules
