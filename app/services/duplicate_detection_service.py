"""Unified duplicate detection service.

Consolidates baseline (deterministic, all-rules retrieval) and ML/semantic
(pgvector Top-K retrieval) engines into a single file with a shared detector
class and a parametrised service facade.

Usage:
    # Semantic engine (pgvector + domain pack) — default for production
    svc = DuplicateDetectionService(engine="semantic")

    # Baseline engine (domain pack + raw SQL) — deterministic fallback
    svc = DuplicateDetectionService(engine="baseline")

    result = svc.check_duplicate(suggested_rule, workspace_id, domain_id, db=db)

Backward-compatible aliases:
    RealDuplicateDetectionService     = DuplicateDetectionService  (engine="semantic")
    BaselineDuplicateDetectionService = DuplicateDetectionService  (engine="baseline")
"""

from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher
from pathlib import Path
import json
import re
import hashlib
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Spec §8.6 relationship_type mapping: internal value -> spec-compliant value
# ---------------------------------------------------------------------------

RELATIONSHIP_TYPE_SPEC_MAP = {
    "exact_duplicate": "Exact Duplicate",
    "semantic_duplicate": "Semantic Duplicate",
    "modification": "Modification",
    "subset": "Modification",
    "superset": "Modification",
    "extension": "Semantic Duplicate",
    "related_compatible": "Semantic Duplicate",
    "unrelated": "Unique Rule",
    "no_duplicate": "Unique Rule",
}


def to_spec_relationship_type(internal_value: str) -> str:
    """Map an internal relationship_type value to the spec §8.6 enum."""
    return RELATIONSHIP_TYPE_SPEC_MAP.get(internal_value, internal_value)


# ---------------------------------------------------------------------------
# Unified duplicate detector (deterministic structural comparison)
# ---------------------------------------------------------------------------

class DuplicateDetector:
    """Detect duplicate and related rules using structural comparison.

    This is the single comparison engine shared by both the semantic
    (pgvector-retrieved candidates) and baseline (all-rules) pipelines.
    It handles:
      - Business-term fuzzy matching
      - Operation / scope equality
      - Condition list comparison with candidate-condition awareness
      - Affected-entity (tables/columns) comparison with leaf-based matching
      - Relationship classification per spec §8.6
    """

    # Relationship types (spec §8.6 internal names)
    EXACT_DUPLICATE = "exact_duplicate"
    SEMANTIC_DUPLICATE = "semantic_duplicate"
    EXTENSION = "extension"
    MODIFICATION = "modification"
    SUBSET = "subset"
    SUPERSET = "superset"
    RELATED_COMPATIBLE = "related_compatible"
    UNRELATED = "unrelated"

    def __init__(self):
        self.similarity_threshold = 0.75
        self.structural_threshold = 0.6

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        new_rule: Dict[str, Any],
        existing_rules: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Detect if *new_rule* duplicates or relates to any of *existing_rules*.

        Returns the best (highest confidence) match across all candidates.
        """
        if not existing_rules:
            return {
                "relationship": self.UNRELATED,
                "matching_rule_id": None,
                "confidence": 0.0,
                "is_duplicate": False,
                "deterministic_match": True,
                "normalized_rule_hash": self._generate_rule_hash(new_rule),
                "details": {},
            }

        best_match = None
        best_relationship = self.UNRELATED
        best_confidence = 0.0
        best_details: Dict[str, Any] = {}

        for existing_rule in existing_rules:
            relationship, confidence, details = self._compare_rules(new_rule, existing_rule)
            if confidence > best_confidence:
                best_confidence = confidence
                best_relationship = relationship
                best_match = existing_rule
                best_details = details

        is_duplicate = (
            best_relationship != self.UNRELATED and best_confidence > 0.7
            and best_relationship in (
                self.EXACT_DUPLICATE, self.SEMANTIC_DUPLICATE,
                self.EXTENSION, self.MODIFICATION,
            )
        )

        return {
            "relationship": best_relationship,
            "matching_rule_id": best_match.get("rule_id") if best_match else None,
            "confidence": round(best_confidence, 3),
            "is_duplicate": is_duplicate,
            "deterministic_match": True,
            "normalized_rule_hash": self._generate_rule_hash(new_rule),
            "details": self._extract_match_details(new_rule, best_match) if best_match else best_details,
        }

    # ------------------------------------------------------------------
    # Core comparison
    # ------------------------------------------------------------------

    def _compare_rules(self, new_rule: Dict[str, Any], existing_rule: Dict[str, Any]) -> Tuple[str, float, Dict]:
        details: Dict[str, Any] = {
            "business_term_match": False,
            "condition_similarity": 0.0,
            "operation_match": False,
            "scope_match": False,
            "affected_entities_match": 0.0,
            "threshold_match": False,
        }

        # 1. Business term
        new_term = (new_rule.get("business_term") or "").lower()
        existing_term = (existing_rule.get("business_term") or "").lower()
        details["business_term_match"] = self._string_similarity(new_term, existing_term) > 0.85

        # 2. Operation
        new_op = (new_rule.get("operation") or "").lower()
        existing_op = (existing_rule.get("operation") or "").lower()
        details["operation_match"] = new_op == existing_op

        # 3. Scope
        new_scope = (new_rule.get("scope") or "").lower()
        existing_scope = (existing_rule.get("scope") or "").lower()
        details["scope_match"] = new_scope == existing_scope

        # 4. Conditions (including candidate conditions for semantic matching)
        new_conditions = new_rule.get("conditions", [])
        existing_conditions = existing_rule.get("conditions", [])
        new_candidate_conditions = new_rule.get("candidate_conditions", [])
        details["condition_similarity"] = round(
            self._compare_conditions(
                new_conditions, existing_conditions,
                new_rule, existing_rule,
                candidate_conditions=new_candidate_conditions,
            ),
            3,
        )

        # 5. Affected entities (leaf-based column matching)
        new_entities = self._get_effective_entities(new_rule)
        existing_entities = self._get_effective_entities(existing_rule)
        details["affected_entities_match"] = round(
            self._compare_entities(new_entities, existing_entities), 3,
        )

        # 6. Threshold
        details["threshold_match"] = new_rule.get("threshold") == existing_rule.get("threshold")

        relationship, confidence = self._determine_relationship(new_rule, existing_rule, details)
        return relationship, confidence, details

    # ------------------------------------------------------------------
    # Condition comparison
    # ------------------------------------------------------------------

    def _compare_conditions(
        self,
        new_conditions: List[Dict],
        existing_conditions: List[Dict],
        new_rule: Dict = None,
        existing_rule: Dict = None,
        candidate_conditions: List[Dict] = None,
    ) -> float:
        """Compare two condition lists.  Returns similarity 0.0–1.0."""
        if not new_conditions and not existing_conditions:
            return 1.0

        # Candidate conditions boost: new rule has candidates, existing has real conditions
        if not new_conditions and candidate_conditions and existing_conditions:
            candidate_text = " ".join(c.get("text", "").lower() for c in candidate_conditions)
            for cond in existing_conditions:
                field = (cond.get("field") or "").lower()
                for token in self._field_tokens(field):
                    if token in candidate_text or self._singularize(token) in candidate_text:
                        return 0.65

        if not new_conditions or not existing_conditions:
            # One side has conditions, the other doesn't — check entity overlap
            if new_conditions and not existing_conditions:
                existing_fields = set(
                    f.lower() for f in (self._get_effective_entities(existing_rule or {}).get("columns", []))
                )
                new_fields = {(cond.get("field") or "").lower() for cond in new_conditions if cond}
                for nf in new_fields:
                    nf_tok = {self._singularize(t) for t in self._field_tokens(nf)}
                    for ef in existing_fields:
                        ef_tok = {self._singularize(t) for t in self._field_tokens(ef)}
                        if nf_tok & ef_tok:
                            return 0.5
            elif existing_conditions and not new_conditions:
                new_fields = set(
                    f.lower() for f in (self._get_effective_entities(new_rule or {}).get("columns", []))
                )
                existing_fields = {(cond.get("field") or "").lower() for cond in existing_conditions if cond}
                for nf in new_fields:
                    nf_tok = {self._singularize(t) for t in self._field_tokens(nf)}
                    for ef in existing_fields:
                        ef_tok = {self._singularize(t) for t in self._field_tokens(ef)}
                        if nf_tok & ef_tok:
                            return 0.5
            return 0.5

        new_normalized = self._normalize_conditions(new_conditions)
        existing_normalized = self._normalize_conditions(existing_conditions)

        matching = 0
        for nc in new_normalized:
            for ec in existing_normalized:
                if self._conditions_equal(nc, ec):
                    matching += 1
                    break

        total = max(len(new_normalized), len(existing_normalized))
        return matching / total if total > 0 else 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_conditions(conditions) -> List[Dict]:
        if not conditions:
            return []
        normalized = []
        for cond in conditions:
            if not cond or not isinstance(cond, dict):
                continue
            normalized.append({
                "field": (cond.get("field") or "").lower(),
                "operator": (cond.get("operator") or "").lower(),
                "value": str(cond.get("value", "")).lower() if cond.get("value") is not None else None,
            })
        return normalized

    @staticmethod
    def _get_effective_entities(rule: Dict[str, Any]) -> Dict[str, Any]:
        """Build effective entities dict from *affected_entities* or top-level keys."""
        entities = rule.get("affected_entities") or {}
        tables = entities.get("tables") or rule.get("affected_tables") or []
        columns = entities.get("columns") or rule.get("affected_columns") or []
        return {"tables": tables, "columns": columns}

    @staticmethod
    def _field_tokens(field_name: str) -> set:
        return set(f.strip().lower() for f in field_name.split(".") if f.strip())

    @staticmethod
    def _singularize(token: str) -> str:
        t = token.lower().strip()
        if len(t) <= 4 or not t.endswith("s"):
            return t
        if t.endswith("ss") or t.endswith("us") or t.endswith("is") or t.endswith("ness"):
            return t
        return t[:-1]

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

    def _conditions_equal(self, cond1: Dict, cond2: Dict) -> bool:
        field_match = self._fields_related(cond1.get("field") or "", cond2.get("field") or "")
        operator_match = (cond1.get("operator") or "").lower() == (cond2.get("operator") or "").lower()
        val1, val2 = cond1.get("value"), cond2.get("value")
        if (cond1.get("operator") or "").lower() in ("is_not_null", "is_null"):
            value_match = True
        else:
            value_match = (
                str(val1).lower() == str(val2).lower()
                if val1 is not None and val2 is not None
                else val1 == val2
            )
        return field_match and operator_match and value_match

    @staticmethod
    def _leaf_set(columns) -> set:
        cols = columns if isinstance(columns, (set, list)) else []
        return {c.split(".")[-1].lower() for c in cols if c}

    def _compare_entities(self, new_entities: Dict, existing_entities: Dict) -> float:
        """Leaf-based Jaccard similarity for tables + columns."""
        new_tables = set(new_entities.get("tables", []))
        existing_tables = set(existing_entities.get("tables", []))

        if new_tables or existing_tables:
            new_tok = {self._singularize(t) for t in new_tables}
            exist_tok = {self._singularize(t) for t in existing_tables}
            table_sim = len(new_tok & exist_tok) / len(new_tok | exist_tok) if (new_tok | exist_tok) else 0.0
        else:
            table_sim = 1.0

        new_leaves = self._leaf_set(list(new_entities.get("columns", [])))
        exist_leaves = self._leaf_set(list(existing_entities.get("columns", [])))
        if new_leaves or exist_leaves:
            col_sim = len(new_leaves & exist_leaves) / len(new_leaves | exist_leaves) if (new_leaves | exist_leaves) else 0.0
        else:
            col_sim = 1.0

        return (table_sim + col_sim) / 2

    def _string_similarity(self, s1: str, s2: str) -> float:
        return SequenceMatcher(None, s1, s2).ratio()

    # ------------------------------------------------------------------
    # Relationship classification (spec §8.6)
    # ------------------------------------------------------------------

    def _determine_relationship(self, new_rule: Dict, existing_rule: Dict, details: Dict) -> Tuple[str, float]:
        bt = details["business_term_match"]
        cs = details["condition_similarity"]
        op = details["operation_match"]
        sc = details["scope_match"]
        en = details["affected_entities_match"]

        new_has_conds = len(new_rule.get("conditions", [])) > 0
        exist_has_conds = len(existing_rule.get("conditions", [])) > 0
        new_has_cands = len(new_rule.get("candidate_conditions", [])) > 0

        new_ent = self._get_effective_entities(new_rule)
        exist_ent = self._get_effective_entities(existing_rule)
        both_unknown = (
            (new_ent.get("columns", []) == ["unknown.unknown"] or not new_ent.get("columns"))
            and (exist_ent.get("columns", []) == ["unknown.unknown"] or not exist_ent.get("columns"))
        )

        # EXACT DUPLICATE
        if bt and cs > 0.95 and op and sc and en > 0.9:
            return self.EXACT_DUPLICATE, 0.99

        # SEMANTIC DUPLICATE
        if bt and op and sc and (
            (cs > 0.85 and en > 0.8)
            or (new_has_conds != exist_has_conds and en > 0.6)
        ):
            return self.SEMANTIC_DUPLICATE, min(0.95, (cs + en) / 2 + 0.1)

        # MODIFICATION
        if bt and op and 0.5 < cs < 0.9:
            return self.MODIFICATION, min(0.85, (cs + 0.7) / 2)

        # EXTENSION — candidate conditions
        if new_has_cands and not new_has_conds and exist_has_conds and bt and op:
            if both_unknown or en > 0.3:
                return self.EXTENSION, 0.70

        # EXTENSION — new rule narrower than existing
        if bt and op and sc and len(new_rule.get("conditions", [])) < len(existing_rule.get("conditions", [])) and 0.4 < cs < 0.95:
            return self.EXTENSION, min(0.8, cs + 0.3)

        # SUBSET
        if bt and cs > 0.3 and len(new_rule.get("conditions", [])) < len(existing_rule.get("conditions", [])):
            return self.SUBSET, cs * 0.8

        # SUPERSET
        if bt and cs > 0.3 and len(new_rule.get("conditions", [])) > len(existing_rule.get("conditions", [])):
            return self.SUPERSET, cs * 0.75

        # RELATED COMPATIBLE
        if bt and op and not sc:
            return self.RELATED_COMPATIBLE, min(0.65, cs * 0.7 + 0.2)

        return self.UNRELATED, 0.0

    # ------------------------------------------------------------------
    # Details / hash
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_match_details(new_rule: Dict, existing_rule: Dict) -> Dict[str, Any]:
        return {
            "new_rule_business_term": new_rule.get("business_term"),
            "existing_rule_business_term": existing_rule.get("business_term"),
            "existing_rule_id": existing_rule.get("rule_id"),
            "matching_conditions": len(new_rule.get("conditions", [])) > 0,
            "new_rule_operation": new_rule.get("operation"),
            "existing_rule_operation": existing_rule.get("operation"),
        }

    def _generate_rule_hash(self, rule: Dict[str, Any]) -> str:
        canonical = {
            "business_term": (rule.get("business_term") or "").lower(),
            "operation": (rule.get("operation") or "").lower(),
            "scope": (rule.get("scope") or "").lower(),
            "conditions": self._normalize_conditions(rule.get("conditions", [])),
            "affected_entities": {
                "tables": sorted(rule.get("affected_entities", {}).get("tables", [])),
                "columns": sorted(rule.get("affected_entities", {}).get("columns", [])),
            },
        }
        return hashlib.md5(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Unified service facade — parametrised by engine
# ---------------------------------------------------------------------------

_DOMAIN_PACK_RULE_KEYS = (
    "rule_id", "business_term", "operation", "conditions", "scope",
    "affected_entities", "threshold", "time_window",
)


class DuplicateDetectionService:
    """Unified duplicate detection service with engine selection.

    Args:
        engine: ``"semantic"`` (default) — pgvector Top-K retrieval
                (with domain-pack + DB fallback).  ``"baseline"`` —
                deterministic domain-pack + raw-SQL retrieval only.
    """

    CANDIDATE_K = 10
    SEMANTIC_SIMILARITY_THRESHOLD = 0.40

    def __init__(self, engine: str = "semantic"):
        if engine not in ("semantic", "baseline"):
            raise ValueError(f"engine must be 'semantic' or 'baseline', got {engine!r}")
        self.engine = engine
        self.detector = DuplicateDetector()

        # Lazy-init semantic-only services
        self._embedding_service = None
        self._pgvector_service = None
        if engine == "semantic":
            self._init_semantic_services()

    def _init_semantic_services(self):
        try:
            from app.services.embedding_service import get_embedding_service
            from app.services.pgvector_service import get_pgvector_service
            self._embedding_service = get_embedding_service()
            self._pgvector_service = get_pgvector_service()
        except Exception as exc:
            logger.warning("Could not initialize semantic retrieval services: %s", exc)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def check_duplicate(
        self,
        suggested_rule: Dict[str, Any],
        workspace_id: str,
        domain_id: str = None,
        db=None,
    ) -> Dict[str, Any]:
        if not db:
            return {
                "is_duplicate": False,
                "relationship": "unrelated",
                "matching_rule_id": None,
                "confidence": 0.0,
                "retrieval_stage": 0,
                "details": {"reason": "No database connection"},
            }

        if not domain_id:
            return {
                "is_duplicate": False,
                "relationship": "unrelated",
                "matching_rule_id": None,
                "confidence": 0.0,
                "retrieval_stage": 0,
                "details": {"reason": "No domain detected — skipping duplicate detection"},
            }

        try:
            if self.engine == "semantic":
                candidates = self._retrieve_candidates_semantic(suggested_rule, workspace_id, domain_id, db)
            else:
                candidates = self._retrieve_candidates_baseline(workspace_id, domain_id, db)

            if not candidates:
                return {
                    "is_duplicate": False,
                    "relationship": "unrelated",
                    "matching_rule_id": None,
                    "confidence": 0.0,
                    "retrieval_stage": 0,
                    "details": {"reason": "No semantically similar rules found"},
                }

            result = self.detector.detect(suggested_rule, candidates)
            result["retrieval_stage"] = len(candidates)

            # Include retrieved rules for debugging / downstream use
            result["similar_rules"] = candidates

            return result

        except Exception as exc:
            logger.error("Error in duplicate detection (%s): %s", self.engine, exc)
            import traceback
            traceback.print_exc()
            return {
                "is_duplicate": False,
                "relationship": "unrelated",
                "matching_rule_id": None,
                "confidence": 0.0,
                "retrieval_stage": 0,
                "details": {"error": str(exc)},
            }

    # ------------------------------------------------------------------
    # Retrieval — shared domain-pack loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_domain_pack_rules(domain_id: str) -> List[Dict[str, Any]]:
        rules: List[Dict[str, Any]] = []
        try:
            active_rules_path = (
                Path(__file__).parent.parent.parent
                / "rie_ml" / "domain-packs" / domain_id / "rules" / "active_rules.json"
            )
            if active_rules_path.exists():
                with open(active_rules_path, "r") as fh:
                    json_rules = json.load(fh)
                    if isinstance(json_rules, list):
                        for jr in json_rules:
                            rules.append({
                                "rule_id": jr.get("rule_id"),
                                "business_term": jr.get("business_term"),
                                "operation": jr.get("operation"),
                                "conditions": jr.get("conditions", []),
                                "scope": jr.get("scope", "global"),
                                "affected_entities": jr.get("affected_entities", {}),
                                "threshold": jr.get("threshold"),
                                "time_window": jr.get("time_window"),
                                "source": "domain_pack",
                                "similarity_score": 1.0,
                            })
        except Exception as exc:
            logger.warning("Could not load active rules from %s: %s", domain_id, exc)
        return rules

    @staticmethod
    def _load_db_rules_sql(workspace_id: str, domain_id: str, db) -> List[Dict[str, Any]]:
        rules: List[Dict[str, Any]] = []
        try:
            from sqlalchemy import text
            result = db.execute(
                text(
                    """
                    SELECT rule_id, business_term, operation, conditions, scope,
                           affected_entities, threshold, time_window
                    FROM rules
                    WHERE workspace_id = :ws AND domain_id = :dom
                      AND status IN ('active', 'draft')
                    ORDER BY created_at DESC
                    LIMIT 100
                    """
                ),
                {"ws": workspace_id, "dom": domain_id},
            )
            for row in result:
                rules.append({
                    "rule_id": row[0],
                    "business_term": row[1],
                    "operation": row[2],
                    "conditions": json.loads(row[3]) if isinstance(row[3], str) else row[3] or [],
                    "scope": row[4],
                    "affected_entities": json.loads(row[5]) if isinstance(row[5], str) else row[5] or {},
                    "threshold": row[6],
                    "time_window": row[7],
                    "source": "database",
                })
        except Exception as exc:
            logger.warning("Could not load DB rules for %s/%s: %s", workspace_id, domain_id, exc)
        return rules

    # ------------------------------------------------------------------
    # Retrieval — baseline engine
    # ------------------------------------------------------------------

    def _retrieve_candidates_baseline(
        self, workspace_id: str, domain_id: str, db,
    ) -> List[Dict[str, Any]]:
        """Load ALL rules from domain pack + DB (no semantic retrieval)."""
        candidates = self._load_domain_pack_rules(domain_id)
        db_rules = self._load_db_rules_sql(workspace_id, domain_id, db)
        existing_ids = {c.get("rule_id") for c in candidates}
        for r in db_rules:
            if r.get("rule_id") not in existing_ids:
                candidates.append(r)
        return candidates

    # ------------------------------------------------------------------
    # Retrieval — semantic engine (pgvector + domain pack)
    # ------------------------------------------------------------------

    def _retrieve_candidates_semantic(
        self,
        suggested_rule: Dict[str, Any],
        workspace_id: str,
        domain_id: str,
        db,
    ) -> List[Dict[str, Any]]:
        """Top-K semantic retrieval via pgvector, merged with domain-pack rules."""
        candidates = self._load_domain_pack_rules(domain_id)

        if self._embedding_service and self._pgvector_service:
            try:
                rule_text = self._embedding_service.generate_rule_embedding_text(suggested_rule)
                if rule_text:
                    embedding = self._embedding_service.generate_embedding(rule_text)
                    if embedding:
                        user_candidates = self._pgvector_service.retrieve_similar_rules(
                            embedding=embedding,
                            workspace_id=workspace_id,
                            domain_id=domain_id,
                            top_k=self.CANDIDATE_K,
                            similarity_threshold=self.SEMANTIC_SIMILARITY_THRESHOLD,
                            db=db,
                        )
                        existing_ids = {c.get("rule_id") for c in candidates}
                        for c in user_candidates:
                            rid = c.get("rule_id")
                            if rid not in existing_ids:
                                c["source"] = "database"
                                candidates.append(c)
                                existing_ids.add(rid)
            except Exception as exc:
                logger.warning("pgvector retrieval failed: %s", exc)

        candidates.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        return candidates[: self.CANDIDATE_K]


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------

# Old code: `from app.services.duplicate_detection_service import RealDuplicateDetectionService`
RealDuplicateDetectionService = DuplicateDetectionService  # engine="semantic" default


class BaselineDuplicateDetectionService(DuplicateDetectionService):
    """Convenience alias that forces engine='baseline'."""

    def __init__(self):
        super().__init__(engine="baseline")
