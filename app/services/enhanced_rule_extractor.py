"""Enhanced rule extraction with glossary, evidence, and per-field confidence."""

import re
import json
from typing import Dict, Any, List
from pathlib import Path
from app.services.glossary_service import get_glossary_service
from app.services.rule_construction import compute_rule_family_id


class EnhancedRuleExtractor:
    """Extract rules with glossary integration, evidence, and confidence tracking."""

    def __init__(self):
        """Initialize extractor with domain pack loader."""
        self.glossary_service = get_glossary_service()
        self.domain_configs = {}  # Cache for domain configs
        self.schemas = {}  # Cache for schemas
        self.relationships = {}  # Cache for relationships
        self.taxonomies = {}  # Cache for taxonomies

    def _load_domain_config(self, domain_pack_id: str) -> Dict[str, Any]:
        """Load domain_config.json for domain pack."""
        if domain_pack_id in self.domain_configs:
            return self.domain_configs[domain_pack_id]

        try:
            config_path = (
                Path(__file__).parent.parent.parent /
                "rie_ml" / "domain-packs" / domain_pack_id /
                "domain_config.json"
            )
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.domain_configs[domain_pack_id] = config
                return config
        except Exception as e:
            print(f"Warning: Could not load domain config for {domain_pack_id}: {e}")
            return {}

    def _load_schema(self, domain_pack_id: str) -> Dict[str, Any]:
        """Load schema.json from domain pack."""
        if domain_pack_id in self.schemas:
            return self.schemas[domain_pack_id]

        try:
            schema_path = (
                Path(__file__).parent.parent.parent /
                "rie_ml" / "domain-packs" / domain_pack_id /
                "schema" / "schema.json"
            )
            with open(schema_path, 'r') as f:
                schema = json.load(f)
                self.schemas[domain_pack_id] = schema
                return schema
        except Exception as e:
            print(f"Warning: Could not load schema for {domain_pack_id}: {e}")
            return {}

    def _load_relationships(self, domain_pack_id: str) -> Dict[str, Any]:
        """Load relationships.json from domain pack."""
        if domain_pack_id in self.relationships:
            return self.relationships[domain_pack_id]

        try:
            rel_path = (
                Path(__file__).parent.parent.parent /
                "rie_ml" / "domain-packs" / domain_pack_id /
                "schema" / "relationships.json"
            )
            with open(rel_path, 'r') as f:
                relationships = json.load(f)
                self.relationships[domain_pack_id] = relationships
                return relationships
        except Exception as e:
            print(f"Warning: Could not load relationships for {domain_pack_id}: {e}")
            return {}

    def _load_taxonomy(self, domain_pack_id: str) -> Dict[str, Any]:
        """Load taxonomy labels from domain pack."""
        if domain_pack_id in self.taxonomies:
            return self.taxonomies[domain_pack_id]

        try:
            tax_path = (
                Path(__file__).parent.parent.parent /
                "rie_ml" / "domain-packs" / domain_pack_id /
                "taxonomy" / "labels.json"
            )
            with open(tax_path, 'r') as f:
                taxonomy = json.load(f)
                self.taxonomies[domain_pack_id] = taxonomy
                return taxonomy
        except Exception as e:
            print(f"Warning: Could not load taxonomy for {domain_pack_id}: {e}")
            return {}

    def extract(
        self,
        feedback: str,
        schema_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Extract rules with full spec compliance using domain pack definitions.

        Returns:
            {
                "extraction": {
                    "extracted_rules": [...],      # Actual rules from feedback (authoritative)
                    "candidate_rules": [...],       # Alternative interpretations from glossary
                    "rules": [...]                  # Single authoritative rule (first extracted)
                },
                "extraction_confidence": 0.0-1.0,
                "evidence": "...",
                "rule_count": {
                    "extracted": int,
                    "candidates": int
                }
            }
        """
        schema_context = schema_context or {}
        domain_pack_id = schema_context.get("domain_pack_id")

        # Load domain pack resources (only if domain_pack_id is provided)
        domain_config = self._load_domain_config(domain_pack_id) if domain_pack_id else {}
        schema = self._load_schema(domain_pack_id) if domain_pack_id else {}
        relationships = self._load_relationships(domain_pack_id) if domain_pack_id else {}
        taxonomy = self._load_taxonomy(domain_pack_id) if domain_pack_id else {}

        # Extract business terms
        business_terms = self._extract_business_terms(feedback, domain_pack_id)

        # Extract operations
        operations = self._extract_operations(feedback)

        # Extract conditions and candidate conditions
        conditions = self._extract_conditions(feedback)
        candidate_conditions = self._extract_candidate_conditions(feedback)

        # Extract scope
        scope = self._extract_scope(feedback)

        # Build extracted rules (one per business term, authoritative)
        extracted_rules = []
        candidate_rules = []
        evidence_parts = []

        for i, term in enumerate(business_terms):
            operation = operations[i] if i < len(operations) else None  # None if unresolved
            rule_conditions = conditions if conditions else []

            # Promote high-confidence candidate conditions to main conditions if main conditions are empty
            if not rule_conditions and candidate_conditions:
                # Use candidates with confidence >= 0.7 as actual conditions
                high_conf_candidates = [c for c in candidate_conditions if c.get("confidence", 0) >= 0.7]
                if high_conf_candidates:
                    # Convert candidates to proper condition format
                    rule_conditions = []
                    for candidate in high_conf_candidates:
                        # Extract field and value from candidate text if possible
                        text = candidate.get("text", "").lower()

                        # Infer table and field from feedback context
                        inferred_table = None
                        inferred_field = None
                        inferred_value = text.strip()

                        # Extract table from feedback if mentioned
                        # Common tables: orders, customers, products, payments, etc.
                        for table in ["orders", "customers", "products", "payments", "invoices", "refunds"]:
                            if table in feedback.lower():
                                inferred_table = table
                                break

                        # Common status/state fields
                        if any(word in text for word in ["status", "cancelled", "active", "pending", "completed"]):
                            if inferred_table:
                                inferred_field = f"{inferred_table}.status"
                            else:
                                inferred_field = f"{term['term']}.status"
                            inferred_value = text.replace("status ", "").strip()

                        rule_conditions.append({
                            "field": inferred_field or f"{inferred_table or term['term']}",
                            "operator": "equals",
                            "value": inferred_value,
                            "inferred": True,
                            "source": "promoted_candidate"
                        })

            # Extract affected entities using business term glossary definitions
            affected_entities = self._extract_affected_entities(
                feedback, schema_context, schema, relationships, domain_config, [term]
            )

            # Build extraction evidence
            evidence_text = self._build_evidence(feedback, term, operation, conditions)
            evidence_parts.append(evidence_text)

            # Calculate per-field confidence
            field_confidence = self._calculate_field_confidence(
                term, operation, rule_conditions, scope, feedback
            )

            rule = {
                "business_term": term["term"],
                "operation": operation,
                "conditions": rule_conditions,
                "candidate_conditions": candidate_conditions,
                "scope": scope or "global",
                "time_window": self._extract_time_window(feedback),
                "affected_entities": affected_entities,
                "rule_family_id": compute_rule_family_id(term["term"], operation, rule_conditions),
                "extraction_evidence": evidence_text,
                "per_field_confidence": field_confidence,
                "glossary_definitions": term.get("glossary", {}),
            }

            # This is the extracted rule from the feedback
            extracted_rules.append(rule)

            # Also enrich with glossary candidates if available
            # These are alternative terms the glossary maps to
            glossary_candidates = term.get("glossary_candidates", [])
            for candidate in glossary_candidates:
                candidate_rules.append({
                    "business_term": candidate,
                    "operation": operation,
                    "conditions": rule_conditions,
                    "scope": scope or "global",
                    "time_window": self._extract_time_window(feedback),
                    "affected_entities": affected_entities,
                    "rule_family_id": compute_rule_family_id(candidate, operation, rule_conditions),
                    "extraction_evidence": evidence_text,
                    "per_field_confidence": field_confidence,
                    "glossary_definitions": term.get("glossary", {}),
                })

        # Calculate overall extraction confidence based on extracted rules only
        overall_confidence = self._calculate_overall_confidence(
            extracted_rules, feedback
        )

        rule_count = {
            "extracted": len(extracted_rules),
            "candidates": len(candidate_rules)
        }

        # Build detailed component mapping for baseline
        component_mapping = self._build_component_mapping(
            business_terms, operations, conditions, candidate_conditions, scope, feedback
        )

        return {
            "extraction": {
                "extracted_rules": extracted_rules,
                "candidate_rules": candidate_rules,
                "rules": extracted_rules[:1] if extracted_rules else [],
                "component_mapping": component_mapping,
                "detailed_components": self._build_detailed_components(
                    business_terms, operations, conditions, candidate_conditions
                )
            },
            "extraction_confidence": overall_confidence,
            "evidence": "\n".join(evidence_parts),
            "rule_count": rule_count,
            "extraction_method": "template_based_regex",
            "validation_ready": len(extracted_rules) > 0 and all(
                rule.get("conditions") for rule in extracted_rules
            )
        }

    def _extract_business_terms(
        self, feedback: str, domain_pack_id: str = None
    ) -> List[Dict[str, Any]]:
        """Extract business terms with glossary definitions including table/column mapping.

        Returns only the PRIMARY business term from the feedback (not all related
        glossary terms). Related terms are tracked as candidates for disambiguation.
        """
        # Handle None domain (gibberish/noise)
        if not domain_pack_id:
            return []

        glossary_service = get_glossary_service()
        glossary_terms = glossary_service.extract_glossary_terms(
            feedback, domain_pack_id
        )

        terms = []
        glossary = glossary_service.load_glossary_for_domain(domain_pack_id)

        # First, try to find exact matches in the feedback
        feedback_lower = feedback.lower()
        exact_matches = []
        partial_matches = []

        for gloss_term in glossary_terms:
            term_key = gloss_term["key"]
            term_lower = term_key.lower()

            # Check if the term appears exactly in the feedback
            if term_lower in feedback_lower:
                exact_matches.append(gloss_term)
            else:
                partial_matches.append(gloss_term)

        # Prioritize exact matches over partial matches
        all_glossary_terms = exact_matches + partial_matches

        # Only take the HIGHEST MATCH QUALITY term as the primary extracted term
        # The rest are candidates (alternative interpretations)
        for gloss_term in all_glossary_terms:
            term_data = glossary.get(gloss_term["key"], {})
            terms.append({
                "term": gloss_term["term"],
                "confidence": 0.90,
                "glossary": {gloss_term["term"]: gloss_term["definition"]},
                "glossary_definitions": {gloss_term["term"]: gloss_term["definition"]},  # Full definition with tables/columns
            })
            # Only take the first (highest match quality) term as the primary extracted term
            break

        # Fallback: extract common business terms
        if not terms:
            patterns = [
                (r"\b(revenue|metric|count|amount|sum|total|average)\b", 0.85),
                (r"\b(customer|order|payment|product|user|ticket)\b", 0.80),
            ]

            for pattern, conf in patterns:
                matches = re.finditer(pattern, feedback, re.IGNORECASE)
                for match in matches:
                    term_text = match.group(1)
                    # Avoid duplicates
                    if not any(t["term"] == term_text for t in terms):
                        terms.append({
                            "term": term_text,
                            "confidence": conf,
                            "glossary": {},
                            "glossary_definitions": {},
                        })
                        # Only take the first match
                        break
                if terms:
                    break

        # If still no terms found, check if feedback is gibberish
        # Don't hallucinate "metric" for noise - return empty list
        if not terms:
            # Check for gibberish: high non-alphanumeric ratio, no real words
            words = feedback.lower().split()
            alpha_count = sum(1 for c in feedback if c.isalpha())
            alnum_count = sum(1 for c in feedback if c.isalnum())
            total_chars = len(feedback)
            non_alnum_ratio = (total_chars - alnum_count) / max(total_chars, 1)
            has_real_word = any(len(w) >= 3 and w.isalpha() for w in words)

            if non_alnum_ratio > 0.5 or (len(words) > 0 and not has_real_word and len(feedback) > 20):
                return []  # No terms extracted - gibberish input

        return terms if terms else [{"term": "metric", "confidence": 0.5, "glossary": {}, "glossary_definitions": {}}]

    def _extract_operations(self, feedback: str) -> List[str]:
        """Extract operations from feedback."""
        operations = []

        operation_patterns = [
            (r"\b(exclude|do not include|should not|must not)\b", "exclude"),
            (r"\b(include|must include|should include)\b", "include"),
            (r"\b(restrict|limit|only)\b", "restrict"),
            (r"\b(map|replace|convert)\b", "map"),
            (r"\b(add|include additional)\b", "add"),
        ]

        for pattern, operation in operation_patterns:
            if re.search(pattern, feedback, re.IGNORECASE):
                operations.append(operation)

        return operations  # Empty list if no operation found (unresolved)

    def _extract_conditions(self, feedback: str) -> List[Dict[str, Any]]:
        """Extract conditions from feedback."""
        conditions = []
        candidate_conditions = []

        # Pattern 1: Explicit "field is/equals/contains value"
        condition_pattern = r"(\w+(?:\.\w+)?)\s+(is|equals|contains|matches)\s+['\"]?(\w+)['\"]?"
        matches = re.finditer(condition_pattern, feedback, re.IGNORECASE)

        for match in matches:
            field, operator_text, value = match.groups()
            operator_map = {
                "is": "equals",
                "equals": "equals",
                "contains": "contains",
                "matches": "equals",
            }
            conditions.append({
                "field": field if "." in field else f"unknown.{field}",
                "operator": operator_map.get(operator_text.lower(), "equals"),
                "value": value,
                "type": "structured",
                "confidence": 0.95
            })

        # Pattern 2: Extract meaningful phrases after operations like "exclude", "include", "filter"
        operation_keywords = ["exclude", "include", "filter", "remove", "add", "apply"]
        for keyword in operation_keywords:
            # Look for phrases like "exclude promotional discounts", "filter by region"
            phrase_pattern = rf"{keyword}\s+(?:by\s+)?(.+?)(?:\s+from|\s+where|\.$)"
            phrase_matches = re.finditer(phrase_pattern, feedback, re.IGNORECASE)

            for phrase_match in phrase_matches:
                condition_phrase = phrase_match.group(1).strip()
                # Clean up the phrase
                condition_phrase = re.sub(r'\s+', ' ', condition_phrase)

                candidate_conditions.append({
                    "text": condition_phrase,
                    "type": "unresolved_condition",
                    "confidence": 0.75,
                    "source": f"detected after '{keyword}'"
                })

        # Pattern 3: Extract phrases with common condition indicators
        condition_indicators = [
            (r"when\s+(.+?)(?:\s+then|\.$)", "when clause"),
            (r"where\s+(.+?)(?:\s+and|\s+or|\.$)", "where clause"),
            (r"if\s+(.+?)(?:\s+then|\.$)", "if clause"),
        ]

        for pattern, source in condition_indicators:
            indicator_matches = re.finditer(pattern, feedback, re.IGNORECASE)
            for indicator_match in indicator_matches:
                condition_phrase = indicator_match.group(1).strip()
                condition_phrase = re.sub(r'\s+', ' ', condition_phrase)

                candidate_conditions.append({
                    "text": condition_phrase,
                    "type": "unresolved_condition",
                    "confidence": 0.70,
                    "source": source
                })

        # Store candidate conditions in a separate field for clarification
        # Only return structured conditions for now
        return conditions

    def _extract_candidate_conditions(self, feedback: str) -> List[Dict[str, Any]]:
        """Extract candidate conditions (unresolved phrases) from feedback."""
        candidate_conditions = []

        # Pattern 1: Extract meaningful phrases after operations like "exclude", "include", "filter"
        operation_keywords = ["exclude", "include", "filter", "remove", "add", "apply"]
        for keyword in operation_keywords:
            # Look for phrases like "exclude promotional discounts", "filter by region"
            # End the phrase at: "from", "where", period, or end of sentence
            phrase_pattern = rf"{keyword}\s+(?:by\s+)?(.+?)(?:\s+from|\s+where|\.$|$)"
            phrase_matches = re.finditer(phrase_pattern, feedback, re.IGNORECASE)

            for phrase_match in phrase_matches:
                condition_phrase = phrase_match.group(1).strip()
                # Clean up the phrase
                condition_phrase = re.sub(r'\s+', ' ', condition_phrase)

                candidate_conditions.append({
                    "text": condition_phrase,
                    "type": "unresolved_condition",
                    "confidence": 0.75,
                    "source": f"detected after '{keyword}'"
                })

        # Pattern 2: Extract phrases with common condition indicators
        condition_indicators = [
            (r"when\s+(.+?)(?:\s+then|\.$)", "when clause"),
            (r"where\s+(.+?)(?:\s+and|\s+or|\.$)", "where clause"),
            (r"if\s+(.+?)(?:\s+then|\.$)", "if clause"),
        ]

        for pattern, source in condition_indicators:
            indicator_matches = re.finditer(pattern, feedback, re.IGNORECASE)
            for indicator_match in indicator_matches:
                condition_phrase = indicator_match.group(1).strip()
                condition_phrase = re.sub(r'\s+', ' ', condition_phrase)

                candidate_conditions.append({
                    "text": condition_phrase,
                    "type": "unresolved_condition",
                    "confidence": 0.70,
                    "source": source
                })

        # Pattern 3: Extract noun phrases that might be conditions
        # Look for phrases like "promotional discounts", "cancelled orders", etc.
        noun_phrase_pattern = r"(?:\b(a|the)\s+)?(\w+(?:\s+\w+){1,3})\b(?=\s+from|\s+where|\s+that|\.$)"
        noun_phrase_matches = re.finditer(noun_phrase_pattern, feedback, re.IGNORECASE)

        for noun_phrase_match in noun_phrase_matches:
            # Skip if it's just the business term itself
            if noun_phrase_match.group(2).lower() in ["revenue", "calculation", "total"]:
                continue

            condition_phrase = noun_phrase_match.group(2).strip()
            candidate_conditions.append({
                "text": condition_phrase,
                "type": "unresolved_condition",
                "confidence": 0.65,
                "source": "noun phrase detection"
            })

        # Remove duplicates
        seen_phrases = set()
        unique_candidates = []
        for candidate in candidate_conditions:
            phrase_key = candidate["text"].lower()
            if phrase_key not in seen_phrases:
                seen_phrases.add(phrase_key)
                unique_candidates.append(candidate)

        return unique_candidates

    def _extract_scope(self, feedback: str) -> str:
        """Extract scope from feedback."""
        scope_patterns = [
            (r"\b(global|all|entire|full)\b", "global"),
            (r"\b(regional?|region)\b", "regional"),
            (r"\b(depart|team)\b", "departmental"),
            (r"\b(user|customer|account)\b", "user-specific"),
        ]

        for pattern, scope in scope_patterns:
            if re.search(pattern, feedback, re.IGNORECASE):
                return scope

        return "global"

    def _extract_time_window(self, feedback: str) -> Dict[str, Any]:
        """Extract time window from feedback."""
        time_patterns = [
            (r"\b(current|this|today|now)\b.*?\b(quarter|month|week|day)\b", "current"),
            (r"\b(last|previous)\b.*?\b(quarter|month|week|day)\b", "previous"),
            (r"\b(next|upcoming|future)\b.*?\b(quarter|month|week|day)\b", "future"),
        ]

        for pattern, period in time_patterns:
            if re.search(pattern, feedback, re.IGNORECASE):
                return {"period": period}

        return {}

    def _extract_affected_entities(
        self,
        feedback: str,
        schema_context: Dict[str, Any],
        schema: Dict[str, Any] = None,
        relationships: Dict[str, Any] = None,
        domain_config: Dict[str, Any] = None,
        business_terms: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract affected tables and columns using business term → glossary mapping."""
        tables = []
        columns = []

        # Priority 1: Use glossary definitions from extracted business terms
        if business_terms:
            for term in business_terms:
                glossary_def = term.get("glossary_definitions", {})
                if glossary_def:
                    # Parse "Tables/columns:" line from glossary
                    # Format: "Tables/columns: `table.column`, `table.column`"
                    for key, value in glossary_def.items():
                        if isinstance(value, str) and "tables/columns:" in value.lower():
                            # Extract backtick-quoted table.column references
                            matches = re.findall(r'`([a-zA-Z0-9_.]+)`', value)
                            for match in matches:
                                if '.' in match:
                                    table, col = match.split('.', 1)
                                    if table not in tables:
                                        tables.append(table)
                                    if match not in columns:
                                        columns.append(match)
                                else:
                                    if match not in tables:
                                        tables.append(match)

        # Priority 2: From schema context if provided
        if not tables and schema_context.get("available_tables"):
            for table in schema_context["available_tables"]:
                tables.append(table)

        if not columns and schema_context.get("available_columns"):
            columns.extend(schema_context["available_columns"])

        # Priority 3: From domain pack schema.json
        if not tables and schema and "tables" in schema:
            schema_tables = schema.get("tables", {})
            for table_name in schema_tables.keys():
                # Simple case-insensitive substring match
                if table_name.lower() in feedback.lower():
                    tables.append(table_name)

        return {
            "tables": list(set(tables)) if tables else ["unknown"],
            "columns": list(set(columns)) if columns else ["unknown.unknown"],
        }

    def _build_evidence(
        self,
        feedback: str,
        term: Dict[str, Any],
        operation: str,
        conditions: List[Dict[str, Any]]
    ) -> str:
        """Build extraction evidence text."""
        evidence_parts = [
            f"Identified business term '{term['term']}' in feedback",
        ]
        if operation:
            evidence_parts.append(f"Extracted operation: {operation.upper()}")

        if conditions:
            evidence_parts.append(f"Conditions: {len(conditions)} extracted")

        # Find supporting text from feedback
        term_lower = term["term"].lower()
        if term_lower in feedback.lower():
            start = feedback.lower().find(term_lower)
            end = min(start + 100, len(feedback))
            evidence_parts.append(
                f"Supporting text: \"{feedback[start:end]}...\""
            )

        return " | ".join(evidence_parts)

    def _calculate_field_confidence(
        self,
        term: Dict[str, Any],
        operation: str,
        conditions: List[Dict[str, Any]],
        scope: str,
        feedback: str
    ) -> Dict[str, float]:
        """Calculate per-field confidence scores."""
        # Check if there are candidate conditions that weren't resolved
        has_candidate_conditions = "exclude" in feedback.lower() or "include" in feedback.lower() or "filter" in feedback.lower()

        # Calculate conditions confidence based on actual conditions and candidate detection
        if conditions:
            conditions_confidence = 0.70  # Structured conditions extracted
        elif has_candidate_conditions:
            conditions_confidence = 0.20  # Candidate conditions detected but not resolved
        else:
            conditions_confidence = 0.80  # No conditions needed for this rule type

        return {
            "business_term": min(0.95, term.get("confidence", 0.5)),
            "operation": 0.85 if operation and operation != "exclude" else (0.95 if operation == "exclude" else 0.50),
            "conditions": conditions_confidence,
            "scope": 0.80,
            "affected_entities": 0.75,
        }

    def _calculate_overall_confidence(
        self, rules: List[Dict[str, Any]], feedback: str
    ) -> float:
        """Calculate overall extraction confidence."""
        if not rules:
            return 0.0

        field_confidences = []
        for rule in rules:
            field_confs = rule.get("per_field_confidence", {})
            if field_confs:
                field_confidences.extend(field_confs.values())

        if not field_confidences:
            return 0.5

        return min(0.99, sum(field_confidences) / len(field_confidences))

    def _build_component_mapping(
        self,
        business_terms: List[Dict[str, Any]],
        operations: List[str],
        conditions: List[Dict[str, Any]],
        candidate_conditions: List[Dict[str, Any]],
        scope: str,
        feedback: str
    ) -> Dict[str, Any]:
        """Build detailed component mapping for extraction output."""
        return {
            "business_terms": [
                {
                    "term": t.get("term"),
                    "confidence": t.get("confidence", 0.7),
                    "extraction_method": "glossary_lookup",
                    "matched_in_feedback": t.get("term", "").lower() in feedback.lower()
                }
                for t in business_terms
            ],
            "operations": [
                {
                    "operation": op,
                    "extraction_method": "regex_pattern_matching"
                }
                for op in operations
            ],
            "conditions": [
                {
                    **cond,
                    "extraction_method": "regex_field_value_extraction"
                }
                for cond in conditions
            ],
            "candidate_conditions": [
                {
                    **cand,
                    "extraction_method": "heuristic_phrase_extraction"
                }
                for cand in candidate_conditions
            ],
            "scope": {
                "value": scope or "global",
                "extraction_method": "glossary_lookup"
            },
            "overall_extraction_method": "template_based_regex",
            "extraction_confidence": 0.75
        }

    def _build_detailed_components(
        self,
        business_terms: List[Dict[str, Any]],
        operations: List[str],
        conditions: List[Dict[str, Any]],
        candidate_conditions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build detailed breakdown of extracted components."""
        return {
            "business_terms": [
                {
                    "term": t.get("term"),
                    "confidence": t.get("confidence", 0.7),
                    "source": "glossary",
                    "definitions": t.get("glossary_definitions", {})
                }
                for t in business_terms
            ],
            "operations": operations,
            "conditions": {
                "extracted": conditions,
                "count": len(conditions),
                "extraction_method": "regex_pattern_matching",
                "components_per_condition": [
                    {
                        "field": c.get("field"),
                        "operator": c.get("operator", "equals"),
                        "value": c.get("value"),
                        "inferred": c.get("inferred", False),
                        "source": c.get("source", "direct_extraction")
                    }
                    for c in conditions
                ]
            },
            "candidate_conditions": {
                "unresolved": candidate_conditions,
                "count": len(candidate_conditions),
                "extraction_method": "heuristic_phrase_extraction"
            }
        }

