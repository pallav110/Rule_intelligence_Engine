"""Domain Pack Matcher - Match extracted rules against active domain rules and schema."""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from difflib import SequenceMatcher


class DomainPackMatcher:
    """Match extracted rules against active domain pack rules, schema, and taxonomy."""

    def __init__(self):
        """Initialize domain pack matcher with caches."""
        self.active_rules_cache = {}
        self.schemas_cache = {}
        self.taxonomies_cache = {}

    def _load_active_rules(self, domain_pack_id: str) -> List[Dict[str, Any]]:
        """Load active_rules.json for domain pack."""
        if domain_pack_id in self.active_rules_cache:
            return self.active_rules_cache[domain_pack_id]

        try:
            rules_path = (
                Path(__file__).parent.parent.parent /
                "rie_ml" / "domain-packs" / domain_pack_id /
                "rules" / "active_rules.json"
            )
            with open(rules_path, 'r') as f:
                rules = json.load(f)
                self.active_rules_cache[domain_pack_id] = rules
                return rules
        except Exception as e:
            print(f"Warning: Could not load active rules for {domain_pack_id}: {e}")
            return []

    def _load_schema(self, domain_pack_id: str) -> Dict[str, Any]:
        """Load schema.json for domain pack."""
        if domain_pack_id in self.schemas_cache:
            return self.schemas_cache[domain_pack_id]

        try:
            schema_path = (
                Path(__file__).parent.parent.parent /
                "rie_ml" / "domain-packs" / domain_pack_id /
                "schema" / "schema.json"
            )
            with open(schema_path, 'r') as f:
                schema = json.load(f)
                self.schemas_cache[domain_pack_id] = schema
                return schema
        except Exception as e:
            print(f"Warning: Could not load schema for {domain_pack_id}: {e}")
            return {}

    def _load_taxonomy(self, domain_pack_id: str) -> Dict[str, Any]:
        """Load taxonomy labels for domain pack."""
        if domain_pack_id in self.taxonomies_cache:
            return self.taxonomies_cache[domain_pack_id]

        try:
            tax_path = (
                Path(__file__).parent.parent.parent /
                "rie_ml" / "domain-packs" / domain_pack_id /
                "taxonomy" / "labels.json"
            )
            with open(tax_path, 'r') as f:
                taxonomy = json.load(f)
                self.taxonomies_cache[domain_pack_id] = taxonomy
                return taxonomy
        except Exception as e:
            print(f"Warning: Could not load taxonomy for {domain_pack_id}: {e}")
            return {}

    def _similarity_score(self, str1: str, str2: str) -> float:
        """Calculate string similarity score (0.0-1.0)."""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def match_extracted_rules(
        self,
        extracted_rules: List[Dict[str, Any]],
        domain_pack_id: str
    ) -> Dict[str, Any]:
        """
        Match extracted rules against active domain rules.

        Returns:
            {
                "matched_rules": [
                    {
                        "extracted_rule": {...},
                        "matched_active_rule": {...},
                        "match_score": 0.0-1.0,
                        "match_reasons": ["business_term match", "operation match", ...]
                    }
                ],
                "unmatched_rules": [...],
                "domain_coverage": 0.0-1.0,
                "matching_confidence": 0.0-1.0
            }
        """
        active_rules = self._load_active_rules(domain_pack_id)
        schema = self._load_schema(domain_pack_id)
        taxonomy = self._load_taxonomy(domain_pack_id)

        matched = []
        unmatched = []
        match_scores = []

        for extracted_rule in extracted_rules:
            best_match = None
            best_score = 0.0
            best_reasons = []

            extracted_term = extracted_rule.get("business_term", "").lower()
            extracted_operation = extracted_rule.get("operation", "").lower()
            extracted_conditions = extracted_rule.get("conditions", [])
            extracted_tables = extracted_rule.get("affected_entities", {}).get("tables", [])

            # Try to match against each active rule
            for active_rule in active_rules:
                active_term = active_rule.get("business_term", "").lower()
                active_operation = active_rule.get("operation", "").lower()
                active_conditions = active_rule.get("conditions", [])
                active_tables = active_rule.get("affected_entities", {}).get("tables", [])

                score = 0.0
                reasons = []

                # Match business term (high weight)
                term_similarity = self._similarity_score(extracted_term, active_term)
                if term_similarity > 0.7:
                    score += term_similarity * 0.4
                    reasons.append(f"business_term match ({term_similarity:.1%})")

                # Match operation (medium weight)
                if extracted_operation == active_operation:
                    score += 0.3
                    reasons.append("operation exact match")
                elif extracted_operation and active_operation:
                    op_similarity = self._similarity_score(extracted_operation, active_operation)
                    if op_similarity > 0.6:
                        score += op_similarity * 0.2
                        reasons.append(f"operation similarity ({op_similarity:.1%})")

                # Match tables (medium weight)
                matching_tables = set(extracted_tables) & set(active_tables)
                if matching_tables:
                    table_match_ratio = len(matching_tables) / max(len(extracted_tables), len(active_tables), 1)
                    score += table_match_ratio * 0.2
                    reasons.append(f"table match ({len(matching_tables)} tables)")

                # Match conditions (low weight - lenient)
                if len(extracted_conditions) > 0 and len(active_conditions) > 0:
                    # At least one condition matches
                    for ext_cond in extracted_conditions:
                        for act_cond in active_conditions:
                            ext_field = ext_cond.get("field", "").lower()
                            act_field = act_cond.get("field", "").lower()
                            if ext_field == act_field or ext_field in act_field or act_field in ext_field:
                                score += 0.1
                                reasons.append("condition field match")
                                break

                if score > best_score:
                    best_score = score
                    best_match = active_rule
                    best_reasons = reasons

            if best_score > 0.5:  # Threshold for match
                matched.append({
                    "extracted_rule": extracted_rule,
                    "matched_active_rule": best_match,
                    "match_score": min(1.0, best_score),
                    "match_reasons": best_reasons
                })
                match_scores.append(best_score)
            else:
                unmatched.append({
                    "extracted_rule": extracted_rule,
                    "potential_matches": [
                        {
                            "active_rule_id": r.get("rule_id"),
                            "active_business_term": r.get("business_term"),
                            "similarity": self._similarity_score(extracted_term, r.get("business_term", "").lower())
                        }
                        for r in active_rules[:3]  # Top 3 candidates
                    ]
                })

        domain_coverage = len(matched) / max(len(extracted_rules), 1)
        matching_confidence = sum(match_scores) / max(len(match_scores), 1) if match_scores else 0.0

        return {
            "matched_rules": matched,
            "unmatched_rules": unmatched,
            "domain_coverage": domain_coverage,
            "matching_confidence": matching_confidence,
            "total_active_rules": len(active_rules),
            "matched_count": len(matched),
            "unmatched_count": len(unmatched)
        }

    def enrich_with_schema_details(
        self,
        extracted_rules: List[Dict[str, Any]],
        domain_pack_id: str
    ) -> List[Dict[str, Any]]:
        """
        Enrich extracted rules with schema column definitions and allowed values.

        Returns enriched rules with schema_enrichment field containing:
        - column_definitions: Details for each referenced column
        - allowed_values: Valid enum values for status/category fields
        - table_descriptions: Business meaning of tables
        """
        schema = self._load_schema(domain_pack_id)
        enriched = []

        for rule in extracted_rules:
            enrichment = {
                "column_definitions": {},
                "allowed_values": {},
                "table_descriptions": {}
            }

            # Get affected tables and columns
            tables = rule.get("affected_entities", {}).get("tables", [])
            columns = rule.get("affected_entities", {}).get("columns", [])
            conditions = rule.get("conditions", [])

            # Enrich with table descriptions
            schema_tables = schema.get("tables", {})
            for table in tables:
                if table in schema_tables:
                    enrichment["table_descriptions"][table] = {
                        "description": schema_tables[table].get("description", ""),
                        "primary_key": schema_tables[table].get("primary_key", ""),
                        "column_count": len(schema_tables[table].get("columns", {}))
                    }

            # Enrich with column definitions and allowed values
            for column in columns:
                if '.' in column:
                    table, col = column.split('.', 1)
                    if table in schema_tables and col in schema_tables[table].get("columns", {}):
                        col_def = schema_tables[table]["columns"][col]
                        enrichment["column_definitions"][column] = {
                            "type": col_def.get("type"),
                            "nullable": col_def.get("nullable"),
                            "description": col_def.get("description"),
                            "business_meaning": col_def.get("business_meaning")
                        }

                        # Extract allowed values for enum-like fields
                        if "allowed_values" in col_def:
                            enrichment["allowed_values"][column] = col_def["allowed_values"]

            # Also check conditions for field references
            for condition in conditions:
                field = condition.get("field", "")
                if '.' in field:
                    table, col = field.split('.', 1)
                    if table in schema_tables and col in schema_tables[table].get("columns", {}):
                        col_def = schema_tables[table]["columns"][col]
                        enrichment["column_definitions"][field] = {
                            "type": col_def.get("type"),
                            "nullable": col_def.get("nullable"),
                            "description": col_def.get("description"),
                            "business_meaning": col_def.get("business_meaning")
                        }

                        if "allowed_values" in col_def:
                            enrichment["allowed_values"][field] = col_def["allowed_values"]

            enriched.append({
                **rule,
                "schema_enrichment": enrichment
            })

        return enriched

    def get_related_rules(
        self,
        extracted_rule: Dict[str, Any],
        domain_pack_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get related active rules based on extracted rule."""
        active_rules = self._load_active_rules(domain_pack_id)

        extracted_term = extracted_rule.get("business_term", "").lower()
        extracted_tables = set(extracted_rule.get("affected_entities", {}).get("tables", []))

        related = []
        for active_rule in active_rules:
            active_term = active_rule.get("business_term", "").lower()
            active_tables = set(active_rule.get("affected_entities", {}).get("tables", []))

            # Score based on term similarity and table overlap
            term_sim = self._similarity_score(extracted_term, active_term)
            table_overlap = len(extracted_tables & active_tables) / max(len(extracted_tables | active_tables), 1)

            score = term_sim * 0.6 + table_overlap * 0.4

            if score > 0.3:  # Threshold for "related"
                related.append({
                    "rule": active_rule,
                    "relevance_score": score,
                    "shared_tables": list(extracted_tables & active_tables)
                })

        # Sort by relevance and return top N
        related.sort(key=lambda x: x["relevance_score"], reverse=True)
        return related[:limit]

    def validate_against_taxonomy(
        self,
        extracted_rules: List[Dict[str, Any]],
        domain_pack_id: str
    ) -> Dict[str, Any]:
        """
        Validate extracted rules against domain taxonomy.

        Returns:
            {
                "valid_terms": [...],
                "invalid_terms": [...],
                "valid_operations": [...],
                "invalid_operations": [...],
                "valid_operators": [...],
                "invalid_operators": [...],
                "overall_validity": 0.0-1.0
            }
        """
        taxonomy = self._load_taxonomy(domain_pack_id)

        valid_terms = []
        invalid_terms = []
        valid_operations = []
        invalid_operations = []
        valid_operators = []
        invalid_operators = []

        taxonomy_operations = taxonomy.get("operations", [])
        taxonomy_operators = taxonomy.get("operators", [])

        for rule in extracted_rules:
            # Validate business term (lenient - just check it's not empty)
            term = rule.get("business_term", "")
            if term:
                valid_terms.append(term)
            else:
                invalid_terms.append("empty business term")

            # Validate operation
            operation = rule.get("operation", "")
            if operation in taxonomy_operations:
                valid_operations.append(operation)
            elif operation:
                invalid_operations.append(operation)

            # Validate operators in conditions
            for condition in rule.get("conditions", []):
                operator = condition.get("operator", "")
                if operator in taxonomy_operators:
                    valid_operators.append(operator)
                elif operator:
                    invalid_operators.append(operator)

        total_items = (
            len(valid_terms) + len(invalid_terms) +
            len(valid_operations) + len(invalid_operations) +
            len(valid_operators) + len(invalid_operators)
        )
        valid_items = len(valid_terms) + len(valid_operations) + len(valid_operators)

        overall_validity = valid_items / max(total_items, 1)

        return {
            "valid_terms": list(set(valid_terms)),
            "invalid_terms": list(set(invalid_terms)),
            "valid_operations": list(set(valid_operations)),
            "invalid_operations": list(set(invalid_operations)),
            "valid_operators": list(set(valid_operators)),
            "invalid_operators": list(set(invalid_operators)),
            "overall_validity": overall_validity
        }
