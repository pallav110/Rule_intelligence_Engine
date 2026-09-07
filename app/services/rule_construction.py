"""Rule Construction Layer - Spec 8.4 Two-Stage Process Stage 2.

Converts extracted BIO entities into complete structured rules using:
- Domain schema/glossary for TABLE+VALUE → FIELD resolution
- Operation mappings for surface word → canonical operation
- Deterministic logic (no inference beyond schema/glossary)
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# Canonical operation mapping (Spec 8.4 Table)
OPERATION_CANONICAL = {
    "exclude": "EXCLUDE",
    "do not include": "EXCLUDE",
    "must not include": "EXCLUDE",
    "does not count": "EXCLUDE",
    "don't count": "EXCLUDE",
    "not contribute": "EXCLUDE",
    "excluded from": "EXCLUDE",
    "remove": "EXCLUDE",
    "removed from": "EXCLUDE",
    "include": "INCLUDE",
    "must include": "INCLUDE",
    "should be part of": "INCLUDE",
    "accounts for": "INCLUDE",
    "part of": "INCLUDE",
    "count toward": "INCLUDE",
    "counts toward": "INCLUDE",
    "restricted to": "RESTRICT",
    "access should be limited to": "RESTRICT",
    "limited to": "RESTRICT",
    "only show": "RESTRICT",
    "restrict": "RESTRICT",
    "replace": "REPLACE",
    "instead of": "REPLACE",
    "rely on": "REPLACE",
    "switch": "REPLACE",
    "use": "REPLACE",
    "instead": "REPLACE",
    "subtract": "SUBTRACT",
    "net out": "SUBTRACT",
    "deduct": "SUBTRACT",
    "add": "ADD",
    "also account for": "ADD",
    "add to": "ADD",
}


# Condition operator mapping (Spec 8.4 Condition Transformation Example)
COND_OPERATOR_CANONICAL = {
    "equal to": "EQUALS",
    "equals": "EQUALS",
    "greater than": "GREATER_THAN",
    "more than": "GREATER_THAN",
    "exceeds": "GREATER_THAN",
    "above": "GREATER_THAN",
    "over": "GREATER_THAN",
    "less than": "LESS_THAN",
    "below": "LESS_THAN",
    "under": "LESS_THAN",
    "does not equal": "NOT_EQUALS",
    "doesn't equal": "NOT_EQUALS",
    "not equal": "NOT_EQUALS",
    "is present": "IS_NOT_NULL",
    "has a value": "IS_NOT_NULL",
    "non-empty": "IS_NOT_NULL",
}


class DomainSchemaResolver:
    """Resolves extracted entities to canonical rules using domain pack schema."""

    def __init__(self, domain_pack_id: str):
        self.domain_pack_id = domain_pack_id
        self.schema = {}
        self.glossary = {}
        self.table_columns = {}
        self.table_to_status_column = {}
        self._load_domain_pack()

    def _load_domain_pack(self):
        """Load domain pack schema and glossary."""
        pack_path = Path(__file__).parent.parent.parent / "rie_ml" / "domain-packs" / self.domain_pack_id

        # Load schema
        schema_file = pack_path / "schema" / "schema.json"
        if schema_file.exists():
            import json
            with open(schema_file) as f:
                self.schema = json.load(f)

            # Build table → columns map and find status-like columns
            for table, meta in self.schema.get("tables", {}).items():
                cols = list(meta.get("columns", {}).keys())
                self.table_columns[table] = cols
                # Heuristic: find status column for this table
                for col in cols:
                    col_lower = col.lower()
                    if col_lower in ("status", "state", "type", "category", "priority"):
                        self.table_to_status_column[table] = col
                        break

        # Load glossary for business term → tables/columns
        glossary_file = pack_path / "documentation" / "business_glossary.md"
        if glossary_file.exists():
            import re
            with open(glossary_file) as f:
                content = f.read()
            # Parse markdown glossary
            terms = re.findall(r'###\s+(\w+)\n(.*?)(?=\n###|\n---|\n## |$)', content, re.DOTALL)
            for term_name, term_content in terms:
                def_match = re.search(r'\*\*Definition:\*\*\s*(.*?)\n', term_content)
                definition = def_match.group(1).strip() if def_match else ""
                tables_match = re.search(r'\*\*Tables/columns:\*\*\s*(.*?)\n', term_content)
                tables_cols = tables_match.group(1).strip() if tables_match else ""
                self.glossary[term_name.lower()] = {
                    "definition": definition,
                    "tables_columns": tables_cols,
                }

    def resolve_field(self, table: str, value: str, context: Dict[str, Any] = None) -> Optional[str]:
        """Resolve TABLE + VALUE → canonical field using schema/glossary.

        Returns:
            field string like "orders.status" or None if cannot resolve
        """
        # 1. Check if table has a known status column
        if table in self.table_to_status_column:
            return f"{table}.{self.table_to_status_column[table]}"

        # 2. Check if value matches any column name in table (e.g., value="high" -> column=priority)
        cols = self.table_columns.get(table, [])
        for col in cols:
            col_lower = col.lower()
            val_lower = value.lower()
            if col_lower in val_lower or val_lower in col_lower:
                return f"{table}.{col}"

        # 3. Check glossary for business_term → table/column hints
        business_term = (context or {}).get("business_term", "").lower()
        if business_term in self.glossary:
            gloss = self.glossary[business_term]
            tcols = gloss.get("tables_columns", "")
            if tcols:
                # Parse "table.column" or "table: column" from glossary
                import re
                for match in re.finditer(r'(\w+)\.(\w+)', tcols):
                    t, c = match.groups()
                    if t == table or t.lower() in table.lower():
                        return f"{t}.{c}"

        return None


class RuleConstructor:
    """Constructs complete structured rules from BIO extraction + domain context."""

    def __init__(self, domain_pack_id: str):
        self.domain_pack_id = domain_pack_id
        self.resolver = DomainSchemaResolver(domain_pack_id)

    def _canonicalize_operation(self, op_surface: str) -> str:
        """Map surface operation word/phrase to canonical operation."""
        if not op_surface:
            return "EXCLUDE"
        op_lower = op_surface.lower().strip()

        # Direct mapping
        if op_lower in OPERATION_CANONICAL:
            return OPERATION_CANONICAL[op_lower]

        # Fuzzy: longest match first
        for phrase, canonical in sorted(OPERATION_CANONICAL.items(), key=lambda x: -len(x[0])):
            if phrase in op_lower:
                return canonical

        return "EXCLUDE"

    def _canonicalize_condition_operator(self, op_surface: str) -> str:
        """Map condition operator word to canonical operator."""
        if not op_surface:
            return "EQUALS"
        op_lower = op_surface.lower().strip()
        for phrase, canonical in sorted(COND_OPERATOR_CANONICAL.items(), key=lambda x: -len(x[0])):
            if phrase in op_lower:
                return canonical
        return "EQUALS"

    def construct_rule(
        self,
        extracted_rule: Dict[str, Any],
        component_mapping: Dict[str, Any],
        detailed_components: Dict[str, Any],
        confidence_per_field: Dict[str, float] = None,
    ) -> Dict[str, Any]:
        """Construct complete rule from raw BIO extraction.

        Args:
            extracted_rule: Raw rule from _extract_entities_from_tags
            component_mapping: Component mapping from extractor
            detailed_components: Detailed per-component from extractor
            confidence_per_field: Optional per-field confidence scores

        Returns:
            Complete rule matching Spec 8.4 output structure
        """
        rule = {
            "business_term": extracted_rule.get("business_term"),
            "operation": self._canonicalize_operation(extracted_rule.get("operation")),
            "conditions": [],
            "scope": extracted_rule.get("scope", "global"),
            "time_window": extracted_rule.get("time_window"),
            "threshold": extracted_rule.get("threshold"),
            "affected_tables": extracted_rule.get("affected_tables", []),
            "affected_columns": extracted_rule.get("affected_columns", []),
            "rule_family_id": component_mapping.get("rule_family_id"),
            "extraction_evidence": component_mapping.get("extraction_evidence", ""),
        }

        # Get context for resolution
        context = {
            "business_term": rule["business_term"],
            "operation": rule["operation"],
        }

        # ---- Resolve conditions ----
        # Priority: explicit conditions from extractor (fields already present)
        raw_conditions = component_mapping.get("conditions", [])
        if raw_conditions and isinstance(raw_conditions, list):
            for cond in raw_conditions:
                if not isinstance(cond, dict):
                    continue
                field = cond.get("field")
                op_surface = cond.get("operator", "equals")
                value = cond.get("value")
                extraction_method = cond.get("extraction_method", "explicit_field_value")

                # Canonicalize condition operator
                canonical_op = self._canonicalize_condition_operator(op_surface)

                # Ensure field is always populated (Spec 8.8: never infer missing business info)
                if field is None and value is not None:
                    # Try TABLE + VALUE resolution
                    tables = extracted_rule.get("affected_tables", [])
                    inferred_field = None
                    for table in tables:
                        resolved = self.resolver.resolve_field(table, str(value), context)
                        if resolved:
                            inferred_field = resolved
                            break

                    if inferred_field:
                        field = inferred_field
                        extraction_method = "resolved_table_value"
                    else:
                        # Cannot determine field - Spec 8.8: mark for clarification
                        field = None
                        extraction_method = "value_only_needs_clarification"

                # Build normalized condition
                if field is not None:
                    rule["conditions"].append({
                        "field": field,
                        "operator": canonical_op,
                        "value": value,
                        "extraction_method": extraction_method,
                        "confidence": confidence_per_field.get("conditions", 0.95) if confidence_per_field else 0.95,
                    })
                else:
                    # Add as candidate condition for clarification generation
                    rule["conditions"].append({
                        "field": None,
                        "operator": canonical_op,
                        "value": value,
                        "extraction_method": "value_only_needs_clarification",
                        "confidence": 0.3,
                        "needs_clarification": True,
                    })

        # If no conditions at all, check for loose values to resolve
        if not rule["conditions"]:
            values = detailed_components.get("values", [])
            tables = detailed_components.get("tables", [])
            for val_info in values:
                val = val_info.get("word")
                inferred_field = None
                for table_info in tables:
                    table = table_info.get("word")
                    resolved = self.resolver.resolve_field(table, str(val), context)
                    if resolved:
                        inferred_field = resolved
                        break

                if inferred_field:
                    rule["conditions"].append({
                        "field": inferred_field,
                        "operator": "EQUALS",
                        "value": val,
                        "extraction_method": "resolved_table_value",
                        "confidence": 0.85,
                    })
                else:
                    rule["conditions"].append({
                        "field": None,
                        "operator": "EQUALS",
                        "value": val,
                        "extraction_method": "value_only_needs_clarification",
                        "confidence": 0.3,
                        "needs_clarification": True,
                    })

        # ---- Affected entities ----
        # Merge extracted with resolved
        all_tables = set(rule["affected_tables"])
        all_columns = set(rule["affected_columns"])
        for cond in rule["conditions"]:
            if cond.get("field"):
                parts = cond["field"].split(".")
                if len(parts) == 2:
                    all_tables.add(parts[0])
                    all_columns.add(parts[1])
        rule["affected_tables"] = sorted(all_tables)
        rule["affected_columns"] = sorted(all_columns)

        # ---- Per-field confidence ----
        if confidence_per_field is None:
            confidence_per_field = {
                "business_term": 0.95,
                "operation": 0.95,
                "conditions": 0.95,
                "scope": 0.95,
                "affected_entities": 0.95,
            }

        rule["per_field_confidence"] = confidence_per_field

        return rule


def construct_rules(
    domain_pack_id: str,
    extracted_rule: Dict[str, Any],
    component_mapping: Dict[str, Any],
    detailed_components: Dict[str, Any],
    logits_confidence: Dict[str, float] = None,
) -> Dict[str, Any]:
    """Convenience function to construct rules."""
    constructor = RuleConstructor(domain_pack_id)
    return constructor.construct_rule(
        extracted_rule,
        component_mapping,
        detailed_components,
        logits_confidence,
    )