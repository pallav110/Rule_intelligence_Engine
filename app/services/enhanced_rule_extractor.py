"""Enhanced rule extraction with glossary, evidence, and per-field confidence."""

import re
import json
from typing import Dict, Any, List, Optional
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

    # ------------------------------------------------------------------
    # Condition-value vocabulary shared by candidate promotion (§8.4)
    # ------------------------------------------------------------------

    # Canonical status literals a promoted phrase must collapse onto. Mirrors
    # the status-adjective map in main.py _infer_conditions_from_text so the
    # baseline extractor emits the SAME clean value the inference step would.
    _STATUS_VALUE_WORDS = {
        "cancelled", "canceled", "completed", "pending", "refunded",
        "successful", "failed", "processing", "active", "inactive", "returned",
    }

    _TABLE_NOUNS = {
        "orders", "customers", "products", "payments", "invoices", "refunds",
        "transactions", "subscriptions", "tickets", "organizations", "sessions",
        "records", "purchases", "sales",
    }

    @staticmethod
    def _clean_condition_value(phrase: str) -> Optional[str]:
        """Collapse an unresolved candidate phrase to its core condition literal.

        Leading/trailing status adjective or an explicit "status VALUE":
            "cancelled orders across all stores for the last 30 days" -> "cancelled"
            "orders cancelled"                                        -> "cancelled"
            "status completed"                                        -> "completed"
        Unresolvable noun phrases stay unresolved:
            "promotional discounts" -> None        (not a clean literal)

        A None return means the phrase must NOT be promoted to a condition:
        it stays a candidate so existing inference / completeness / clarification
        logic handles it. Over-capturing a whole sentence as the condition value
        produced false conflicts against canonical rules (EC_R001's "cancelled"
        vs "cancelled orders across all stores for the last 30 days").
        """
        if not phrase or not isinstance(phrase, str):
            return None
        tokens = [t.strip(".,;:!?()\"'") for t in phrase.lower().split()]
        tokens = [t for t in tokens if t]
        if not tokens:
            return None
        # Single token is already a clean literal value.
        if len(tokens) == 1:
            return tokens[0]
        # Leading status adjective: "cancelled orders ..." -> "cancelled"
        if tokens[0] in EnhancedRuleExtractor._STATUS_VALUE_WORDS:
            return tokens[0]
        # Trailing status adjective after a bare table noun: "orders cancelled" -> "cancelled"
        if tokens[0] in EnhancedRuleExtractor._TABLE_NOUNS and tokens[-1] in EnhancedRuleExtractor._STATUS_VALUE_WORDS:
            return tokens[-1]
        # "status cancelled" -> "cancelled"
        if tokens[0] == "status" and len(tokens) > 1 and tokens[1] in EnhancedRuleExtractor._STATUS_VALUE_WORDS:
            return tokens[1]
        # Anything else is a sentence fragment, not a condition value.
        return None

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

        # Post-extraction: qualify bare fields with schema table.column
        if schema:
            conditions = self._qualify_bare_fields(conditions, feedback, schema)

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
                # Use candidates with confidence >= 0.7 as actual conditions —
                # but ONLY when the phrase collapses to a clean canonical
                # literal. A whole-sentence fragment ("cancelled orders across
                # all stores for the last 30 days") must NOT become the
                # condition value — it over-captured and produced false
                # conflicts against canonical rules. Unpromotable phrases stay
                # candidates and reach inference / clarification instead.
                high_conf_candidates = [c for c in candidate_conditions if c.get("confidence", 0) >= 0.7]
                if high_conf_candidates:
                    # Convert candidates to proper condition format
                    rule_conditions = []
                    for candidate in high_conf_candidates:
                        clean_value = self._clean_condition_value(candidate.get("text"))
                        if clean_value is None:
                            continue

                        text = candidate.get("text", "").lower()

                        # Infer table and field from feedback context
                        inferred_table = None
                        inferred_field = None

                        # Extract table from feedback if mentioned
                        # Common tables: orders, customers, products, payments, etc.
                        for table in ["orders", "customers", "products", "payments", "invoices", "refunds"]:
                            if table in feedback.lower():
                                inferred_table = table
                                break

                        # Common status/state fields — a promoted status literal
                        # maps onto <table>.status
                        if any(w in text for w in EnhancedRuleExtractor._STATUS_VALUE_WORDS):
                            inferred_field = f"{inferred_table or term['term']}.status"

                        rule_conditions.append({
                            "field": inferred_field or f"{inferred_table or term['term']}",
                            "operator": "equals",
                            "value": clean_value,
                            "inferred": True,
                            "source": "promoted_candidate",
                            "value_clean": True,
                        })

            # Extract affected entities from conditions first (explicit fields), then fall back to glossary
            affected_entities = self._extract_affected_entities_from_conditions(rule_conditions)
            if not affected_entities.get("tables") or affected_entities.get("tables") == ["unknown"]:
                # Fallback to glossary-based extraction
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

            # Also expose tables/columns at top level for duplicate detection compatibility
            tables = affected_entities.get("tables", []) if isinstance(affected_entities, dict) else []
            columns = affected_entities.get("columns", []) if isinstance(affected_entities, dict) else []

            rule = {
                "business_term": term["term"],
                "operation": operation,
                "conditions": rule_conditions,
                "candidate_conditions": candidate_conditions,
                "scope": scope or "global",
                "time_window": self._extract_time_window(feedback),
                "affected_entities": affected_entities,
                "affected_tables": tables,
                "affected_columns": columns,
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
                    "affected_tables": tables,
                    "affected_columns": columns,
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

        # Fallback: infer operation from exclude/include verbs when ML-style
        # patterns miss (e.g., "ignore", "do not count", "shouldn't count").
        if not operations:
            fb_lower = feedback.lower()
            _exclude_re = (
                r"\b(?:do not consider|ignore|leave out|not include|"
                r"shouldn'?t|should not|must not|can'?t|won'?t|do not count|"
                r"don'?t count|not count|remove|removed from|drop|drops|strip|"
                r"leave behind)\b"
            )
            _include_re = (
                r"\b(?:only .+ should(?:\s+\w+){0,3} (?:contribute|count|be included)|"
                r"must include|should be part of|count toward|contribute to|"
                r"account for)\b"
            )
            if re.search(_exclude_re, fb_lower):
                operations.append("exclude")
            elif re.search(_include_re, fb_lower):
                operations.append("include")

        return operations  # Empty list if no operation found (unresolved)

    def _extract_conditions(self, feedback: str) -> List[Dict[str, Any]]:
        """Extract conditions from feedback."""
        conditions = []
        candidate_conditions = []

        # Pattern 1: Explicit "field is/equals/contains/matches value"
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

        # Pattern 1b: "X should be greater than 1000" / "X is less than 500"
        # We intentionally *skip* common copulas/modal/determiner words when
        # scanning backward from the comparison operator so that "be", "should"
        # etc. are not treated as the field.
        _COPULA_WORDS = {
            "is", "be", "are", "was", "were", "should", "must", "will",
            "can", "would", "could", "shall", "the", "a", "an", "of",
            "to", "by", "that", "this", "for", "in", "at", "with", "than",
        }
        comparison_re = re.compile(
            r'\b(greater than|less than|more than|exceeds|above|over|below|under)\s+'
            r"(['\"]?[\d.]+['\"]?)\b",
            re.IGNORECASE,
        )
        operator_map = {
            "greater than": "greater_than", "more than": "greater_than",
            "exceeds": "greater_than", "above": "greater_than", "over": "greater_than",
            "less than": "less_than", "below": "less_than", "under": "less_than",
        }
        for match in comparison_re.finditer(feedback):
            operator_text, value = match.groups()
            value = value.strip("'\"")
            # Walk backward from operator to find the nearest non-copula word as field
            preceding = feedback[:match.start()].rstrip()
            words = preceding.split()
            field = None
            for w in reversed(words):
                wl = w.lower().strip(",;:()")
                if wl and wl not in _COPULA_WORDS:
                    field = wl
                    break
            conditions.append({
                "field": f"unknown.{field}" if field and "." not in field else (field or "unknown.metric"),
                "operator": operator_map.get(operator_text.lower(), "equals"),
                "value": value,
                "type": "structured",
                "confidence": 0.95,
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

    def _qualify_bare_fields(
        self, conditions: List[Dict[str, Any]], feedback: str, schema: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Qualify bare field names with table.column using schema context.

        When the baseline extractor produces a field like "refunds" or "orders"
        (no dot), or "unknown.status", we try to resolve it to a real
        "table.column" by:
        1. If the field starts with "unknown.", strip the prefix and treat the
           suffix as a bare column name.
        2. If the bare name matches a table in the schema, keep it as-is (it's
           a table reference, not a column).
        3. If the bare name matches a column in exactly one schema table,
           qualify it as "table.column".
        4. Otherwise, look for a table mentioned in the feedback and pair it
           with the bare column.
        """
        if not schema or not schema.get("tables"):
            return conditions

        # Table synonyms (same as distilbert_token_extractor)
        _TABLE_SYNONYMS = {
            "purchases": "orders", "transactions": "payments",
            "completed_order": "orders", "cancelled_order": "orders",
        }

        schema_tables = set(schema.get("tables", {}).keys())
        # Build column → [tables] map
        col_to_tables: Dict[str, List[str]] = {}
        for tname, tinfo in schema.get("tables", {}).items():
            for col_name in tinfo.get("columns", {}).keys():
                col_to_tables.setdefault(col_name.lower(), []).append(tname)

        # Detect table mentioned in feedback
        fb_lower = feedback.lower()
        mentioned_tables = [t for t in schema_tables if t.lower() in fb_lower]

        qualified = []
        for cond in conditions:
            field = cond.get("field") or ""
            if not field:
                qualified.append(cond)
                continue

            # Case A: "unknown.X" → strip prefix, treat X as bare column
            if field.startswith("unknown."):
                bare = field.split(".", 1)[1]
            elif "." in field:
                table_part, col_part = field.split(".", 1)
                # Already qualified — just normalize
                if table_part.lower() in {t.lower() for t in schema_tables}:
                    # Find the canonical table name
                    canonical = next(
                        (t for t in schema_tables if t.lower() == table_part.lower()),
                        table_part
                    )
                    cond = {**cond, "field": f"{canonical}.{col_part}"}
                qualified.append(cond)
                continue
            else:
                bare = field

            bare_lower = bare.lower().strip()
            bare_clean = _TABLE_SYNONYMS.get(bare_lower, bare_lower)

            # If bare name IS a table name, don't qualify (it's a table ref)
            if bare_clean in schema_tables or bare_lower in {t.lower() for t in schema_tables}:
                qualified.append(cond)
                continue

            # If bare name matches exactly one column in the schema
            if bare_lower in col_to_tables:
                tables = col_to_tables[bare_lower]
                if len(tables) == 1:
                    cond = {**cond, "field": f"{tables[0]}.{bare}"}
                elif mentioned_tables:
                    # Multiple tables have this column — use the one mentioned in feedback
                    matching = [t for t in tables if t in mentioned_tables]
                    if len(matching) == 1:
                        cond = {**cond, "field": f"{matching[0]}.{bare}"}
                    else:
                        cond = {**cond, "field": f"{tables[0]}.{bare}"}
                else:
                    cond = {**cond, "field": f"{tables[0]}.{bare}"}
            elif mentioned_tables:
                # Column not in schema, but a table is mentioned — pair them
                cond = {**cond, "field": f"{mentioned_tables[0]}.{bare}"}

            qualified.append(cond)

        return qualified

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

    def _extract_time_window(self, feedback: str) -> Optional[str]:
        """Extract a normalized time window string from feedback text.

        Ported from the DistilBERT token extractor so the baseline emits the
        same convention ("last_30_days", "current_month", "ytd", ...).
        Schema validation (§8.5 check 9) accepts null or such a string pattern —
        a dict is neither and would fail validation, hence string-or-None.
        """
        fb = feedback.lower()

        # Ordered by specificity — most specific first
        patterns = [
            (r"\blast\s+(\d+)\s+days?\b", lambda m: f"last_{m.group(1)}_days"),
            (r"\blast\s+(\d+)\s+weeks?\b", lambda m: f"last_{m.group(1)}_weeks"),
            (r"\blast\s+(\d+)\s+months?\b", lambda m: f"last_{m.group(1)}_months"),
            (r"\b(current|this)\s+month\b", lambda _: "current_month"),
            (r"\b(current|this)\s+quarter\b", lambda _: "current_quarter"),
            (r"\b(current|this)\s+week\b", lambda _: "current_week"),
            (r"\b(current|this)\s+year\b", lambda _: "current_year"),
            (r"\b(previous|last)\s+month\b", lambda _: "previous_month"),
            (r"\b(previous|last)\s+quarter\b", lambda _: "previous_quarter"),
            (r"\b(previous|last)\s+year\b", lambda _: "previous_year"),
            (r"\bytd\b|\byear\s+to\s+date\b", lambda _: "ytd"),
            (r"\bmtd\b|\bmonth\s+to\s+date\b", lambda _: "mtd"),
            (r"\bqtd\b|\bquarter\s+to\s+date\b", lambda _: "qtd"),
            (r"\brolling\s+(\d+)\s+(days?|weeks?|months?)\b",
             lambda m: f"rolling_{m.group(1)}_{m.group(2)}"),
            (r"\btrailing\s+(\d+)\s+(days?|weeks?|months?)\b",
             lambda m: f"trailing_{m.group(1)}_{m.group(2)}"),
            (r"\btoday\b", lambda _: "today"),
            (r"\byesterday\b", lambda _: "yesterday"),
        ]

        for pattern, extractor in patterns:
            match = re.search(pattern, fb)
            if match:
                return extractor(match)

        return None

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

    def _extract_affected_entities_from_conditions(self, conditions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract affected tables and columns from explicit conditions fields."""
        tables = []
        columns = []

        for cond in conditions:
            if not isinstance(cond, dict):
                continue
            field = cond.get("field", "")
            if field and "." in field:
                table, col = field.split(".", 1)
                if table not in tables:
                    tables.append(table)
                if field not in columns:
                    columns.append(field)

        return {
            "tables": tables,
            "columns": columns,
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

