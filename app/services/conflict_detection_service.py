"""Unified conflict detection service.

Consolidates baseline (deterministic, all-rules retrieval) and ML/semantic
(pgvector Top-K retrieval) engines into a single file with a shared detector
class and a parametrised service facade.

Usage:
    # Semantic engine (pgvector + domain pack) — default for production
    svc = ConflictDetectionService(engine="semantic")

    # Baseline engine (domain pack + raw SQL) — deterministic fallback
    svc = ConflictDetectionService(engine="baseline")

    result = svc.check_conflict(suggested_rule, workspace_id, domain_id, db=db)

Backward-compatible aliases:
    RealConflictDetectionService     = ConflictDetectionService  (engine="semantic")
    BaselineConflictDetectionService = ConflictDetectionService  (engine="baseline")
"""

from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher
from pathlib import Path
import json
import hashlib
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Spec §8.7 conflict_type mapping: internal value -> spec-compliant value
# ---------------------------------------------------------------------------

CONFLICT_TYPE_SPEC_MAP = {
    "direct_conflict": "Conflict",
    "potential_conflict": "Conflict",
    "temporal_conflict": "Conflict",
    "scope_conflict": "Conflict",
    "related_compatible": "Compatible",
    "no_conflict": "No Conflict",
}


def to_spec_conflict_type(internal_value: str) -> str:
    """Map an internal conflict_type value to the spec §8.7 enum."""
    return CONFLICT_TYPE_SPEC_MAP.get(internal_value, internal_value)


# ---------------------------------------------------------------------------
# Unified conflict detector (deterministic structural comparison)
# ---------------------------------------------------------------------------

class ConflictDetector:
    """Detect conflicts between rules based on structural analysis.

    This is the single comparison engine shared by both the semantic
    (pgvector-retrieved candidates) and baseline (all-rules) pipelines.

    Per spec 8.7.2: "Final conflict decisions are based on structured rule
    comparison rather than semantic similarity scores."
    """

    # Conflict types
    DIRECT_CONFLICT = "direct_conflict"
    POTENTIAL_CONFLICT = "potential_conflict"
    TEMPORAL_CONFLICT = "temporal_conflict"
    SCOPE_CONFLICT = "scope_conflict"
    NO_CONFLICT = "no_conflict"

    def __init__(self):
        self.confidence_threshold = 0.6

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        new_rule: Dict[str, Any],
        existing_rules: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Detect if *new_rule* conflicts with any of *existing_rules*."""
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
                conflicts.append({
                    "rule_id": existing_rule.get("rule_id"),
                    "conflict_type": conflict_type,
                    "confidence": confidence,
                    "details": details,
                })

        if not conflicts:
            return {
                "has_conflict": False,
                "conflict_type": self.NO_CONFLICT,
                "conflicting_rule_ids": [],
                "confidence": 0.0,
                "deterministic_comparison": True,
                "details": {},
            }

        worst_conflict = max(conflicts, key=lambda x: x["confidence"])
        related_rules = [c for c in conflicts if c["conflict_type"] == "related_compatible"]
        actual_conflicts = [c for c in conflicts if c["conflict_type"] != "related_compatible"]

        return {
            "has_conflict": len(actual_conflicts) > 0,
            "conflict_type": worst_conflict["conflict_type"] if actual_conflicts else "no_conflict",
            "conflicting_rule_ids": [c["rule_id"] for c in actual_conflicts],
            "related_compatible_rule_ids": [c["rule_id"] for c in related_rules],
            "confidence": round(worst_conflict["confidence"], 3),
            "deterministic_comparison": True,
            "details": {
                "all_conflicts": conflicts,
                "primary_conflict": worst_conflict if actual_conflicts else None,
                "related_compatible_rules": related_rules,
                "recommendations": self._generate_recommendations(
                    worst_conflict["conflict_type"] if actual_conflicts else "no_conflict",
                    new_rule,
                ),
            },
        }

    # ------------------------------------------------------------------
    # Core comparison
    # ------------------------------------------------------------------

    def _check_conflict(self, new_rule: Dict[str, Any], existing_rule: Dict[str, Any]) -> Tuple[str, float, Dict]:
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

        # 1. Business term
        new_term = (new_rule.get("business_term") or "").lower()
        existing_term = (existing_rule.get("business_term") or "").lower()
        term_similarity = self._string_similarity(new_term, existing_term)
        details["business_term_similarity"] = round(term_similarity, 3)
        details["business_term_match"] = term_similarity > 0.85

        if not details["business_term_match"]:
            return self.NO_CONFLICT, 0.0, details

        # 2. Scope overlap
        # `.get("scope", "")` returns None when the key exists with a null
        # value (extraction sometimes emits scope: null), so coerce with
        # `or ""` to keep .lower() from crashing on None.
        new_scope = (new_rule.get("scope") or "").lower()
        existing_scope = (existing_rule.get("scope") or "").lower()
        details["scope_overlap"] = (
            new_scope == existing_scope or new_scope == "global" or existing_scope == "global"
        )

        if not details["scope_overlap"]:
            return self.NO_CONFLICT, 0.0, details

        # 3. Affected entities overlap
        new_entities = self._get_effective_entities(new_rule)
        existing_entities = self._get_effective_entities(existing_rule)

        new_tables = set(new_entities.get("tables", []))
        existing_tables = set(existing_entities.get("tables", []))
        new_tables_norm = {self._singularize(t) for t in new_tables} if new_tables else set()
        existing_tables_norm = {self._singularize(t) for t in existing_tables} if existing_tables else set()
        shared_tables = (new_tables & existing_tables) | (new_tables_norm & existing_tables_norm)
        details["shared_tables"] = list(shared_tables)

        if not shared_tables:
            if new_rule.get("conditions") or new_rule.get("candidate_conditions"):
                details["shared_tables"] = []
            else:
                return self.NO_CONFLICT, 0.0, details

        # Columns — exact then fuzzy
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

        # 4. Subject overlap
        subject_similarity = self._calculate_subject_similarity(new_rule, existing_rule)
        details["subject_similarity"] = round(subject_similarity, 3)
        details["subject_overlap"] = subject_similarity > 0.6

        # 5. Contradictory conditions
        new_conditions = new_rule.get("conditions", [])
        existing_conditions = existing_rule.get("conditions", [])
        contradictory = self._find_contradictions(new_conditions, existing_conditions)
        details["contradictory_conditions"] = contradictory

        if contradictory:
            return self.DIRECT_CONFLICT, 0.95, details

        # 6. Conflicting operations
        new_op = (new_rule.get("operation") or "").lower()
        existing_op = (existing_rule.get("operation") or "").lower()
        operation_conflict = self._check_operation_conflict(new_op, existing_op)
        details["conflicting_operations"] = operation_conflict

        condition_overlap = False
        if len(new_conditions) > 0 and len(existing_conditions) > 0:
            condition_overlap = self._calculate_condition_similarity(new_conditions, existing_conditions) > 0.4
        if operation_conflict and (shared_columns or condition_overlap):
            return self.DIRECT_CONFLICT, 0.85, details

        # 7. Temporal overlap
        new_time_window = new_rule.get("time_window")
        existing_time_window = existing_rule.get("time_window")
        details["temporal_overlap"] = new_time_window == existing_time_window

        # 8. Potential conflict — overlapping conditions but not contradictory
        has_entity_basis = bool(shared_tables) or (
            not set(self._get_effective_entities(new_rule).get("tables", []))
            and not set(self._get_effective_entities(new_rule).get("columns", []))
            and bool(new_conditions)
        )
        if (shared_tables or has_entity_basis) and len(new_conditions) > 0 and len(existing_conditions) > 0:
            condition_similarity = self._calculate_condition_similarity(new_conditions, existing_conditions)
            if condition_similarity > 0.85 and new_op == existing_op and details["business_term_match"]:
                return self.NO_CONFLICT, 0.0, details
            if condition_similarity > 0.4:
                return self.POTENTIAL_CONFLICT, condition_similarity * 0.8, details

        # 9. Related / compatible
        if details["business_term_match"] and new_op == existing_op and not contradictory:
            condition_similarity = self._calculate_condition_similarity(new_conditions, existing_conditions)
            if condition_similarity > 0.3 and condition_similarity < 0.9:
                return "related_compatible", 0.6 + condition_similarity * 0.3, details

        return self.NO_CONFLICT, 0.0, details

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_effective_entities(rule: Dict[str, Any]) -> Dict[str, Any]:
        entities = rule.get("affected_entities") or {}
        tables = entities.get("tables") or rule.get("affected_tables") or []
        columns = entities.get("columns") or rule.get("affected_columns") or []
        return {"tables": tables, "columns": columns}

    @staticmethod
    def _singularize(token: str) -> str:
        t = token.lower().strip()
        if len(t) <= 4 or not t.endswith("s"):
            return t
        if t.endswith("ss") or t.endswith("us") or t.endswith("is") or t.endswith("ness"):
            return t
        return t[:-1]

    def _field_tokens(self, field_name: str) -> set:
        return set(f.strip().lower() for f in field_name.split(".") if f.strip())

    def _fields_related(self, f1: str, f2: str) -> bool:
        """Leaf-name matching only — different columns on the same table are NOT related."""
        if not f1 or not f2:
            return False
        f1l, f2l = f1.lower(), f2.lower()
        if f1l == f2l:
            return True
        leaf1 = f1l.rsplit(".", 1)[-1]
        leaf2 = f2l.rsplit(".", 1)[-1]
        return leaf1 == leaf2

    def _string_similarity(self, s1: str, s2: str) -> float:
        return SequenceMatcher(None, s1, s2).ratio()

    def _find_contradictions(self, new_conditions: List[Dict], existing_conditions: List[Dict]) -> List[Dict]:
        contradictions = []
        for new_cond in new_conditions:
            if not isinstance(new_cond, dict):
                continue
            # field/operator can be None (ML value-only conditions, and
            # post-extraction cross-validation nulls unresolvable fields).
            # `.get("field", "")` returns None when the key exists as null,
            # so coerce with `or ""` to avoid a NoneType .lower() crash.
            new_field = (new_cond.get("field") or "").lower()
            new_operator = (new_cond.get("operator") or "").lower()
            new_value = new_cond.get("value")
            for existing_cond in existing_conditions:
                if not isinstance(existing_cond, dict):
                    continue
                existing_field = (existing_cond.get("field") or "").lower()
                existing_operator = (existing_cond.get("operator") or "").lower()
                existing_value = existing_cond.get("value")
                if self._fields_related(new_field, existing_field):
                    if self._operators_contradict(new_operator, new_value, existing_operator, existing_value):
                        contradictions.append({
                            "field": new_field,
                            "new_condition": f"{new_field} {new_operator} {new_value}",
                            "existing_condition": f"{existing_field} {existing_operator} {existing_value}",
                            "reason": self._contradiction_reason(
                                new_operator, new_value, existing_operator, existing_value,
                            ),
                        })
        return contradictions

    @staticmethod
    def _operators_contradict(op1: str, val1: Any, op2: str, val2: Any) -> bool:
        op_pairs = [
            ("equals", "not_equals"),
            ("in", "not_in"),
            ("is_not_null", "is_null"),
            ("greater_than", "less_than"),
            ("greater_than_or_equal", "less_than"),
            ("less_than_or_equal", "greater_than"),
        ]
        for pair in op_pairs:
            if (op1 == pair[0] and op2 == pair[1]) or (op1 == pair[1] and op2 == pair[0]):
                return True
        # equals == equals is only a contradiction when the two values are
        # DEFINITELY different. A value that is a phrase-superset of the other
        # ("cancelled orders across all stores" vs "cancelled") is not proven
        # contradictory — flagging it yields false conflicts — so treat it as
        # equivalent rather than assume the extractor emitted pristine atoms.
        if op1 == "equals" and op2 == "equals" and not ConflictDetector._values_equal(val1, val2):
            return True
        if op1 == "in" and op2 == "not_in":
            if isinstance(val1, list) and isinstance(val2, list):
                return all(ConflictDetector._values_equal(v, val2) for v in val1)
        return False

    @staticmethod
    def _values_equal(val1: Any, val2: Any) -> bool:
        """Robust value equivalence used before declaring a contradiction.

        Handles the common shapes that reach conflict detection:
        * scalars (str/int/float/bool) — compared case-insensitively for text
        * a multi-word string whose token set contains the other value, i.e.
          phrase-superset values ("cancelled orders across all stores for the
          last 30 days" ⊇ "cancelled") — treated as equivalent, not opposite
        * equal-length lists (e.g. `in` values) compared element-wise
        """
        if val1 is None or val2 is None:
            return val1 is val2  # only both-None counts as equal
        if isinstance(val1, list) and isinstance(val2, list):
            if len(val1) != len(val2):
                return False
            return all(ConflictDetector._values_equal(a, b) for a, b in zip(val1, val2))
        if isinstance(val1, bool) and isinstance(val2, bool):
            return val1 == val2
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            return val1 == val2
        if isinstance(val1, str) and isinstance(val2, str):
            a_tokens = [t for t in val1.strip().lower().split() if t]
            b_tokens = [t for t in val2.strip().lower().split() if t]
            if a_tokens == b_tokens:
                return True
            # Phrase-superset: a multi-word value whose token set contains the
            # other SINGLE-token value — "cancelled orders across all stores for
            # the last 30 days" ⊇ "cancelled". A single token must match a whole
            # token (not a substring) so "active" ⊉ "inactive".
            if len(a_tokens) > 1 and len(b_tokens) == 1 and b_tokens[0] in a_tokens:
                return True
            if len(b_tokens) > 1 and len(a_tokens) == 1 and a_tokens[0] in b_tokens:
                return True
            return False
        return val1 == val2

    @staticmethod
    def _contradiction_reason(op1: str, val1: Any, op2: str, val2: Any) -> str:
        if op1 == "is_not_null" and op2 == "is_null":
            return "One requires field to be null, other requires non-null"
        if op1 == "equals" and op2 == "equals" and not ConflictDetector._values_equal(val1, val2):
            return f"Requires field to equal both {val1} and {val2}"
        if (op1 in ("greater_than", "greater_than_or_equal")) and (op2 in ("less_than", "less_than_or_equal")):
            return f"Requires field to be > {val1} and < {val2}"
        return "Operators are contradictory"

    @staticmethod
    def _check_operation_conflict(op1: str, op2: str) -> bool:
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
        subjects1: set = set()
        for cond in rule1.get("conditions", []):
            field = cond.get("field", "")
            if field:
                subjects1.add(field.lower())
        subjects2: set = set()
        for cond in rule2.get("conditions", []):
            field = cond.get("field", "")
            if field:
                subjects2.add(field.lower())
        for col in rule1.get("affected_entities", {}).get("columns", []):
            subjects1.add(col.lower())
        for col in rule2.get("affected_entities", {}).get("columns", []):
            subjects2.add(col.lower())
        if not subjects1 or not subjects2:
            return 0.0
        intersection = subjects1 & subjects2
        union = subjects1 | subjects2
        return len(intersection) / len(union) if union else 0.0

    def _generate_recommendations(self, conflict_type: str, new_rule: Dict[str, Any]) -> List[str]:
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


# ---------------------------------------------------------------------------
# Unified service facade — parametrised by engine
# ---------------------------------------------------------------------------

class ConflictDetectionService:
    """Unified conflict detection service with engine selection.

    Args:
        engine: ``"semantic"`` (default) — pgvector Top-K retrieval
                (with domain-pack fallback).  ``"baseline"`` —
                deterministic domain-pack + DB rules retrieval only.
    """

    CANDIDATE_K = 10
    SEMANTIC_SIMILARITY_THRESHOLD = 0.40

    def __init__(self, engine: str = "semantic"):
        if engine not in ("semantic", "baseline"):
            raise ValueError(f"engine must be 'semantic' or 'baseline', got {engine!r}")
        self.engine = engine
        self.detector = ConflictDetector()

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

    def check_conflict(
        self,
        suggested_rule: Dict[str, Any],
        workspace_id: str,
        domain_id: str,
        db=None,
    ) -> Dict[str, Any]:
        if not db:
            return {
                "has_conflict": False,
                "conflict_type": "no_conflict",
                "conflicting_rule_ids": [],
                "confidence": 0.0,
                "retrieval_stage": 0,
                "details": {"reason": "No database connection"},
            }

        try:
            if self.engine == "semantic":
                candidates = self._retrieve_candidates_semantic(suggested_rule, workspace_id, domain_id)
            else:
                candidates = self._retrieve_candidates_baseline(workspace_id, domain_id, db)

            if not candidates:
                return {
                    "has_conflict": False,
                    "conflict_type": "no_conflict",
                    "conflicting_rule_ids": [],
                    "confidence": 0.0,
                    "retrieval_stage": 0,
                    "details": {"reason": "No active rules found to compare against"},
                }

            # Run structured comparison per candidate
            conflicting_ids: List[str] = []
            conflicts_found: List[Dict[str, Any]] = []

            for active_rule in candidates:
                conflict_result = self.detector._check_conflict(suggested_rule, active_rule)
                conflict_type, confidence, details = conflict_result

                if conflict_type != ConflictDetector.NO_CONFLICT and confidence > self.detector.confidence_threshold:
                    conflicting_ids.append(active_rule.get("rule_id"))
                    conflicts_found.append({
                        "rule_id": active_rule.get("rule_id"),
                        "conflict_type": conflict_type,
                        "confidence": confidence,
                        "comparison_details": details,
                    })

            if not conflicting_ids:
                return {
                    "has_conflict": False,
                    "conflict_type": "no_conflict",
                    "conflicting_rule_ids": [],
                    "confidence": 0.0,
                    "retrieval_stage": len(candidates),
                    "details": {},
                }

            worst_conflict = max(conflicts_found, key=lambda x: x["confidence"])

            return {
                "has_conflict": True,
                "conflict_type": worst_conflict["conflict_type"],
                "conflicting_rule_ids": conflicting_ids,
                "confidence": round(worst_conflict["confidence"], 2),
                "retrieval_stage": len(candidates),
                "details": {
                    "all_conflicts": conflicts_found,
                    "primary_conflict": worst_conflict,
                },
            }

        except Exception as exc:
            logger.error("Error in conflict detection (%s): %s", self.engine, exc)
            import traceback
            traceback.print_exc()
            return {
                "has_conflict": False,
                "conflict_type": "no_conflict",
                "conflicting_rule_ids": [],
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
        """Load ALL rules from domain pack + DB."""
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
        self, suggested_rule: Dict[str, Any], workspace_id: str, domain_id: str,
    ) -> List[Dict[str, Any]]:
        """Top-K semantic retrieval via pgvector, merged with domain-pack rules."""
        candidates = self._load_domain_pack_rules(domain_id)

        if self._embedding_service and self._pgvector_service:
            try:
                rule_text = self._generate_rule_embedding_text(suggested_rule)
                if rule_text:
                    embedding = self._embedding_service.generate_embedding(rule_text)
                    if embedding:
                        user_candidates = self._pgvector_service.retrieve_similar_rules(
                            embedding=embedding,
                            workspace_id=workspace_id,
                            domain_id=domain_id,
                            top_k=self.CANDIDATE_K,
                            similarity_threshold=self.SEMANTIC_SIMILARITY_THRESHOLD,
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

    def _generate_rule_embedding_text(self, rule: Dict[str, Any]) -> str:
        parts: List[str] = []
        if rule.get("business_term"):
            parts.append(f"Business term: {rule['business_term']}")
        if rule.get("operation"):
            parts.append(f"Operation: {rule['operation']}")
        if rule.get("conditions"):
            conditions_text = ", ".join(
                f"{c.get('field')} {c.get('operator')} {c.get('value')}"
                for c in rule.get("conditions", [])
            )
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


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------

# Old code: `from app.services.conflict_detection_service import RealConflictDetectionService`
RealConflictDetectionService = ConflictDetectionService  # engine="semantic" default

# Baseline class (thin subclass that forces engine="baseline")
# Imported here so callers can import everything from the consolidated file.


class BaselineConflictDetectionService(ConflictDetectionService):
    """Convenience alias that forces engine='baseline'."""

    def __init__(self):
        super().__init__(engine="baseline")
