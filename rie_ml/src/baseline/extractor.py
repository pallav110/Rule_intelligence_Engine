"""Baseline extractor for deterministic rule extraction.

This implements template-based rule extraction using business glossaries
and schema metadata. The extractor produces structured rules with
per-field confidence scores.

Training data format (from dataset_generation/output/extraction.jsonl):
  {
    "feedback_id": "...",
    "feedback_text": "...",
    "business_term": "revenue",
    "operation": "exclude",
    "conditions": [
      {"field": "orders.status", "operator": "equals", "value": "cancelled"}
    ],
    "scope": "global",
    "confidence": {
      "business_term": 0.95,
      "operation": 0.90,
      "conditions": 0.85,
      "scope": 0.80
    }
  }

The extractor produces a single dict with those keys — ready for
schema validation and duplicate/conflict detection.
"""

import json
import re
from typing import Dict, Any, List, Optional
from pathlib import Path


class BaselineExtractor:
    """Deterministic template-based rule extractor."""

    def __init__(self, glossary: Dict[str, Any], schema: Dict[str, Any]):
        """Initialize extractor with glossary and schema."""
        self.glossary = glossary
        self.schema = schema
        self._init_patterns()

    def _init_patterns(self):
        """Initialize extraction patterns.

        Normalizes glossary terms to handle underscores and spaces.
        """
        # Business term patterns (from glossary)
        self.business_term_patterns = {}
        for term, data in self.glossary.get("terms", {}).items():
            patterns = data.get("patterns", [term.lower()])

            # Generate additional patterns for normalization
            normalized_patterns = []
            for p in patterns:
                # Add original pattern
                normalized_patterns.append(p)

                # Add pattern with underscores replaced by spaces
                if '_' in p:
                    space_pattern = p.replace('_', ' ')
                    normalized_patterns.append(space_pattern)

                # Add pattern with spaces replaced by underscores
                if ' ' in p:
                    underscore_pattern = p.replace(' ', '_')
                    normalized_patterns.append(underscore_pattern)

            self.business_term_patterns[term] = [re.compile(p, re.IGNORECASE) for p in normalized_patterns]

        # Operation patterns
        self.operation_patterns = {
            "exclude": [
                re.compile(r"\b(exclude|remove|eliminate|omit|ignore|skip|drop)\b", re.I),
                re.compile(r"\b(should|must) not (include|contain|have)\b", re.I),
            ],
            "include": [
                re.compile(r"\b(include|add|incorporate|consider|account for)\b", re.I),
                re.compile(r"\b(should|must) (include|contain|have|qualify|count|consider)\b", re.I),
                re.compile(r"\b(should|must) be (included|qualified|counted|considered)\b", re.I),
                re.compile(r"\b(qualify for|be eligible for|get|receive)\b", re.I),
            ],
            "restrict": [
                re.compile(r"\b(restrict|limit|constrain|confine)\b", re.I),
                re.compile(r"\b(only|just) (allow|permit|enable)\b", re.I),
            ],
            "map": [
                re.compile(r"\b(map|convert|transform|translate)\b", re.I),
                re.compile(r"\b(should|must) be (mapped|converted)\b", re.I),
            ],
            "replace": [
                re.compile(r"\b(replace|substitute|swap|change|use)\b", re.I),
                re.compile(r"\b(should|must) be (replaced|substituted|changed)\b", re.I),
                re.compile(r"\b(should|must) use\b", re.I),
                re.compile(r"\b(over to|instead of)\b", re.I),
            ],
        }

        # Condition operator patterns
        self.operator_patterns = {
            "equals": [re.compile(r"\b(equals?|is|are|was|were|==)\b", re.I)],
            "not_equals": [re.compile(r"\b(not equals?|is not|are not|!=|<>)\b", re.I)],
            "greater_than": [re.compile(r"\b(greater than|>|above)\b", re.I)],
            "less_than": [re.compile(r"\b(less than|<|below)\b", re.I)],
            "greater_than_or_equal": [re.compile(r"\b(greater than or equal|>=)\b", re.I)],
            "less_than_or_equal": [re.compile(r"\b(less than or equal|<=)\b", re.I)],
            "in": [re.compile(r"\b(in|among|within)\b", re.I)],
            "not_in": [re.compile(r"\b(not in|outside|excluding)\b", re.I)],
            "contains": [re.compile(r"\b(contains?|has|have|includes?)\b", re.I)],
            "is_null": [re.compile(r"\b(is null|is empty|missing)\b", re.I)],
            "is_not_null": [re.compile(r"\b(is not null|is not empty|exists)\b", re.I)],
        }

        # Scope patterns
        self.scope_patterns = {
            "global": [re.compile(r"\b(global|all|every|entire|whole)\b", re.I)],
            "region": [re.compile(r"\b(region|area|zone|territory)\b", re.I)],
            "time": [re.compile(r"\b(time|period|window|duration)\b", re.I)],
        }

    def extract(
        self,
        feedback_text: str,
        classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract structured rule from feedback text.

        Parameters
        ----------
        feedback_text: str
            Raw feedback text.
        classification: dict
            Classification result (feedback_type, rule_category).

        Returns
        -------
        dict
            Extracted rule with per-field confidence.
        """
        text = feedback_text.lower()

        # Extract business term
        business_term, term_confidence = self._extract_business_term(text)

        # Extract operation
        operation, op_confidence = self._extract_operation(text)

        # Extract conditions (only explicit patterns, no inference)
        conditions, cond_confidence = self._extract_conditions(text, business_term)

        # Extract scope
        scope, scope_confidence = self._extract_scope(text)

        # Calculate overall confidence
        overall_confidence = (term_confidence + op_confidence + cond_confidence + scope_confidence) / 4

        return {
            "business_term": business_term,
            "operation": operation,
            "conditions": conditions,
            "scope": scope,
            "confidence": {
                "business_term": round(term_confidence, 3),
                "operation": round(op_confidence, 3),
                "conditions": round(cond_confidence, 3),
                "scope": round(scope_confidence, 3),
                "overall": round(overall_confidence, 3),
            }
        }

    def _extract_business_term(self, text: str) -> tuple:
        """Extract business term using glossary patterns.

        Prioritizes longer, more specific terms over shorter generic ones.
        """
        candidates = []

        # First pass: collect all matching terms with their confidence and specificity
        for term, patterns in self.business_term_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    # Calculate confidence based on pattern specificity
                    confidence = self.glossary.get("terms", {}).get(term, {}).get("confidence", 0.8)

                    # Add specificity score: longer terms are more specific
                    # Also boost terms that appear as complete words
                    specificity = len(term) / 10.0  # Normalize
                    if re.search(r'' + re.escape(term) + r'', text, re.IGNORECASE):
                        specificity += 0.5

                    total_score = confidence + specificity
                    candidates.append((term, total_score, confidence))
                    break  # Only consider best pattern per term

        # Second pass: if no glossary terms found, use fallback
        if not candidates:
            common_terms = ["revenue", "order", "customer", "product", "payment"]
            for term in common_terms:
                if term in text:
                    candidates.append((term, 0.6, 0.6))

        # Select best candidate by total score
        if candidates:
            # Sort by score descending, then by term length descending
            candidates.sort(key=lambda x: (-x[1], -len(x[0])))
            best_term, total_score, confidence = candidates[0]
            return best_term, confidence

        return None, 0.0

    def _extract_operation(self, text: str) -> tuple:
        """Extract operation using operation patterns."""
        best_operation = None
        best_confidence = 0.0

        for operation, patterns in self.operation_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    confidence = 0.85
                    if confidence > best_confidence:
                        best_operation = operation
                        best_confidence = confidence
                        break

        # Fallback: check for common operation keywords
        if not best_operation:
            if any(word in text for word in ["exclude", "remove", "omit"]):
                best_operation = "exclude"
                best_confidence = 0.7
            elif any(word in text for word in ["include", "add"]):
                best_operation = "include"
                best_confidence = 0.7

        return best_operation, best_confidence if best_confidence > 0 else 0.0

    def _extract_conditions(self, text: str, business_term: Optional[str]) -> tuple:
        """Extract conditions from feedback text.

        Strategy:
        1. Try explicit field.operator.value patterns (SQL-like)
        2. Fall back to inferring conditions from operation context
           e.g., "exclude cancelled orders" → infer orders.status = cancelled
        """
        conditions = []
        confidence = 0.0

        # Strategy 1: Try to find explicit field-operator-value patterns
        # Pattern: [field] [operator] [value]

        # Look for common patterns
        patterns = [
            # Pattern: field operator value
            (r"(\w+)\.(\w+)\s+(equals?|is|are|was|were|!=|<>|>|<|>=|<=|in|not in|contains?|is null|is not null)\s+([^\.]+)",
             "field", "operator", "value"),

            # Pattern: when field operator value
            (r"when\s+(\w+)\.(\w+)\s+(equals?|is|are|was|were|!=|<>|>|<|>=|<=|in|not in|contains?|is null|is not null)\s+([^\.]+)",
             "field", "operator", "value"),

            # Pattern: if field operator value
            (r"if\s+(\w+)\.(\w+)\s+(equals?|is|are|was|were|!=|<>|>|<|>=|<=|in|not in|contains?|is null|is not null)\s+([^\.]+)",
             "field", "operator", "value"),
        ]

        for pattern, field_idx, op_idx, val_idx in patterns:
            matches = re.finditer(pattern, text, re.I)
            for match in matches:
                try:
                    field = f"{match.group(1)}.{match.group(2)}"
                    operator = match.group(3).lower()
                    value = match.group(4).strip()

                    # Normalize operator
                    operator = self._normalize_operator(operator)

                    # Validate field exists in schema
                    if self._validate_field(field):
                        conditions.append({
                            "field": field,
                            "operator": operator,
                            "value": value
                        })
                        confidence = 0.8
                except (IndexError, AttributeError):
                    continue

        # Fallback: try to extract simple conditions
        if not conditions:
            # Look for "field is value" patterns
            simple_matches = re.finditer(r"(\w+)\.(\w+)\s+(is|are|was|were)\s+(\w+)", text, re.I)
            for match in simple_matches:
                try:
                    field = f"{match.group(1)}.{match.group(2)}"
                    value = match.group(4)

                    if self._validate_field(field):
                        conditions.append({
                            "field": field,
                            "operator": "equals",
                            "value": value
                        })
                        confidence = 0.7
                except (IndexError, AttributeError):
                    pass

        # Fallback 2: Extract conditions from common phrases
        if not conditions:
            # Pattern: "field status value" (e.g., "payment status failed")
            status_matches = re.finditer(r"(\w+)\s+status\s+(failed|successful|cancelled|pending)", text, re.I)
            for match in status_matches:
                try:
                    table = match.group(1).lower()
                    value = match.group(2).lower()

                    # Try common table names
                    field = f"{table}s.status"  # pluralize (payment -> payments)
                    if self._validate_field(field):
                        conditions.append({
                            "field": field,
                            "operator": "equals",
                            "value": value
                        })
                        confidence = 0.7
                        break
                except (IndexError, AttributeError):
                    pass

        # Fallback 3: Extract numeric conditions (e.g., "over 1000", "greater than 50")
        if not conditions:
            # Pattern: "over X" or "greater than X"
            over_matches = re.finditer(r"(over|greater than|above|more than)\s+(\d+)", text, re.I)
            for match in over_matches:
                try:
                    value = int(match.group(2))

                    # Try to find likely fields (amount, total, value, etc.)
                    likely_fields = ["orders.total_amount", "payments.amount", "orders.amount"]
                    for field in likely_fields:
                        if self._validate_field(field):
                            conditions.append({
                                "field": field,
                                "operator": "greater_than",
                                "value": value
                            })
                            confidence = 0.7
                            break
                    if conditions:
                        break
                except (IndexError, AttributeError, ValueError):
                    pass

        # NEW Fallback 4: Infer conditions from operation + context
        # e.g., "exclude cancelled orders" → orders.status = cancelled
        if not conditions:
            # Extract operation-specific value patterns
            # "exclude/remove [value]" patterns
            exclude_patterns = re.finditer(r"\b(exclude|remove|omit|skip|ignore|drop)\s+(\w+)\s+(\w+)?", text, re.I)
            for match in exclude_patterns:
                try:
                    operation = match.group(1).lower()
                    first_word = match.group(2).lower()
                    second_word = match.group(3).lower() if match.group(3) else None

                    # Try to infer: [adjective] [noun] → noun.status = adjective
                    # e.g., "cancelled orders" → orders.status = cancelled
                    if second_word:
                        # first_word is likely an adjective (cancelled, failed, test)
                        # second_word is likely a noun (orders, payments)
                        table_field = f"{second_word}.status"
                        if self._validate_field(table_field):
                            conditions.append({
                                "field": table_field,
                                "operator": "equals",
                                "value": first_word
                            })
                            confidence = 0.65  # Lower confidence for inferred conditions
                            break
                except (IndexError, AttributeError):
                    pass

        # Fallback 5: Extract "within X days" patterns
        if not conditions:
            within_matches = re.finditer(r"within\s+(\d+)\s+days", text, re.I)
            for match in within_matches:
                try:
                    days = int(match.group(1))
                    value = f"{days}_days_ago"

                    # Try to find date/time fields
                    likely_fields = ["customers.last_purchase_at", "orders.created_at", "customers.created_at"]
                    for field in likely_fields:
                        if self._validate_field(field):
                            conditions.append({
                                "field": field,
                                "operator": "greater_than",
                                "value": value
                            })
                            confidence = 0.7
                            break
                    if conditions:
                        break
                except (IndexError, AttributeError, ValueError):
                    pass

        # If we found conditions, calculate average confidence
        if conditions:
            confidence = min(0.9, confidence + 0.1 * len(conditions))

        return conditions, confidence

    def _normalize_operator(self, operator: str) -> str:
        """Normalize operator to standard form."""
        operator = operator.lower().strip()

        if operator in ["equal", "equals", "is", "are", "was", "were", "=="]:
            return "equals"
        elif operator in ["not equal", "not equals", "is not", "are not", "!=", "<>"]:
            return "not_equals"
        elif operator in ["greater than", ">"]:
            return "greater_than"
        elif operator in ["less than", "<"]:
            return "less_than"
        elif operator in ["greater than or equal", ">="]:
            return "greater_than_or_equal"
        elif operator in ["less than or equal", "<="]:
            return "less_than_or_equal"
        elif operator in ["in", "among", "within"]:
            return "in"
        elif operator in ["not in", "outside", "excluding"]:
            return "not_in"
        elif operator in ["contains", "has", "have", "includes"]:
            return "contains"
        elif operator in ["is null", "is empty", "missing"]:
            return "is_null"
        elif operator in ["is not null", "is not empty", "exists"]:
            return "is_not_null"

        return "equals"  # Default

    def _validate_field(self, field: str) -> bool:
        """Validate field exists in schema."""
        if "." not in field:
            return False

        table, column = field.split(".", 1)

        # Check if table exists
        if table not in self.schema.get("tables", {}):
            return False

        # Check if column exists in table
        table_schema = self.schema["tables"][table]
        if column not in table_schema.get("columns", {}):
            return False

        return True

    def _extract_scope(self, text: str) -> tuple:
        """Extract scope from feedback text."""
        # Check for global scope
        if any(pattern.search(text) for pattern in self.scope_patterns.get("global", [])):
            return "global", 0.9

        # Check for region scope
        if any(pattern.search(text) for pattern in self.scope_patterns.get("region", [])):
            # Try to extract specific region
            region_match = re.search(r"region[:\s]*(\w+)", text, re.I)
            if region_match:
                return f"region:{region_match.group(1).lower()}", 0.85
            return "region:unspecified", 0.75

        # Check for time scope
        if any(pattern.search(text) for pattern in self.scope_patterns.get("time", [])):
            return "time:unspecified", 0.75

        # Default to global
        return "global", 0.6


def load_glossary(domain: str = "ecommerce") -> Dict[str, Any]:
    """Load glossary for domain from markdown file."""
    # Try JSON first (for backward compatibility)
    glossary_json_path = Path(__file__).parent.parent.parent / "domain-packs" / domain / "glossary" / "glossary.json"
    if glossary_json_path.exists():
        with open(glossary_json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Try markdown file
    glossary_md_path = Path(__file__).parent.parent.parent / "domain-packs" / domain / "documentation" / "business_glossary.md"
    if glossary_md_path.exists():
        try:
            with open(glossary_md_path, "r", encoding="utf-8") as f:
                content = f.read()

            glossary = {"terms": {}}
            # Parse markdown glossary format: ### Term
            # Capture everything from ### Term through all bullet points until the next ### or EOF
            pattern = r'^###\s+([^\n]+)\n((?:(?!^###)[\s\S])*?)(?=^###|\Z)'
            matches = re.finditer(pattern, content, re.MULTILINE)

            for match in matches:
                term = match.group(1).strip().lower()
                definition = match.group(2).strip()

                # Extract tables/columns from definition
                tables_columns_match = re.search(r'Tables/columns:\s*([^\n]+)', definition, re.I)
                tables_columns = []
                if tables_columns_match:
                    tables_columns = [tc.strip() for tc in tables_columns_match.group(1).split(',')]

                glossary["terms"][term] = {
                    "term": term,
                    "definition": definition,
                    "tables_columns": tables_columns,
                    "patterns": [term]  # Use term itself as pattern
                }

            return glossary
        except Exception as e:
            print(f"Error loading glossary from {glossary_md_path}: {e}")
            return {"terms": {}}

    return {"terms": {}}


def load_schema(domain: str = "ecommerce") -> Dict[str, Any]:
    """Load schema for domain."""
    schema_path = Path(__file__).parent.parent.parent / "domain-packs" / domain / "schema" / "schema.json"

    if schema_path.exists():
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    return {"tables": {}}


if __name__ == "__main__":
    # Test the extractor
    glossary = load_glossary("ecommerce")
    schema = load_schema("ecommerce")

    extractor = BaselineExtractor(glossary, schema)

    # Test extraction
    test_feedback = "Revenue should exclude orders with status cancelled"
    classification = {
        "feedback_type": "business_rule_correction",
        "rule_category": "metric_definition"
    }

    result = extractor.extract(test_feedback, classification)
    print("Extraction Result:")
    print(json.dumps(result, indent=2))
