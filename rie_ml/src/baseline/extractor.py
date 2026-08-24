"""Baseline rule extraction for rie_ml (package: rie_ml/src/baseline/).

Matches the interface expected by ``app/services/rule_extractor.py``.

The ``extract`` method returns a dict with:
  - ``rules: list[dict]``    (each dict has business_term, operation,
                              conditions, scope, threshold, affected_entities)
  - ``confidence: float``

This is the deterministic baseline using keyword matching + regex.
"""

import re
from typing import Any, Dict, List


class BaselineRuleExtractor:
    """Regex-based rule extractor — the non‑ML baseline."""

    def extract(self, feedback: str, classification: Any,
                schema_context: dict) -> Dict[str, Any]:
        """Extract structured rules from ``feedback``.

        Parameters
        ----------
        feedback: str
        classification: Any
            Result of the classifier (dict or dataclass).  Currently
            unused but kept for contract compatibility.
        schema_context: dict
            ``{"available_tables": [...], "available_columns": [...]}``

        Returns
        -------
        dict
            ``{"rules": [...], "confidence": 0.0-1.0}``
        """
        # Parse operation keywords
        operation = self._detect_operation(feedback)

        # Parse business term
        business_term = self._detect_business_term(feedback)

        # Parse conditions using patterns like "X should [op] Y" or "X exceeds Y"
        conditions = self._extract_conditions(feedback, schema_context)

        # Confidence based on structural completeness
        confidence = self._compute_confidence(
            feedback, business_term, operation, conditions
        )

        rule = {
            "business_term": business_term,
            "operation": operation,
            "conditions": conditions,
            "scope": "global",
            "time_window": None,
            "threshold": self._extract_threshold(feedback),
            "affected_entities": {
                "tables": schema_context.get("available_tables", []),
                "columns": schema_context.get("available_columns", []),
            },
        }

        return {
            "rules": [rule] if business_term else [],
            "confidence": round(confidence, 4),
        }

    # ------------------------------------------------------------------
    #  Private helpers
    # ------------------------------------------------------------------

    def _detect_operation(self, text: str) -> str:
        mapping = [
            ("exclude", "exclude"),
            ("should not", "exclude"),
            ("must not", "exclude"),
            ("ignore", "exclude"),
            ("omit", "exclude"),
            ("should include", "include"),
            ("must include", "include"),
            ("should only", "restrict"),
            ("should be", "define"),
            ("calculate", "calculate"),
            ("divided by", "calculate"),
            ("divide", "calculate"),
        ]
        lowered = text.lower()
        for pattern, op in mapping:
            if pattern in lowered:
                return op
        return "include"

    def _detect_business_term(self, text: str) -> str:
        # look for patterns like "... should ..." or "... term ..."
        patterns = [
            r"([A-Za-z_][\w\s]+)\s+(?:should|must)",
            r"(?:Revenue|Sales|Cost|Margin|Conversion|Customers?)\s+([\w\s]+)",
        ]
        for pat in patterns:
            match = re.search(pat, text)
            if match:
                term = match.group(0).split("should")[0].strip().lower()
                if term:
                    return term.replace(" ", "_")
        return ""

    def _extract_conditions(self, text: str, schema) -> List[Dict[str, Any]]:
        # Look for "field operator value" patterns
        conditions = []
        columns = schema.get("available_columns", [])
        # Simple pattern: "<field> equals <value>"
        value_patterns = [
            (r"(>=|<=|>|<|equals|in|not in)\s+(.+)$", None),
        ]
        for col in columns:
            for pat, _ in value_patterns:
                # Build regex dynamically
                col_pattern = re.escape(col) + r"\s+(>=|<=|>|<|equals|not\s+in|in)\s+([A-Za-z0-9_]+)"
                match = re.search(col_pattern, text)
                if match:
                    op = match.group(1).replace("not in", "not_in").replace("in", "in")
                    value = match.group(2)
                    # Try to parse as int
                    try:
                        value = int(value)
                    except ValueError:
                        try:
                            value = float(value)
                        except ValueError:
                            pass  # keep as string
                    conditions.append({
                        "field": col,
                        "operator": op,
                        "value": value,
                    })
                    break
            if conditions:
                break
        return conditions

    def _extract_threshold(self, text: str) -> Any:
        """Look for numeric thresholds in the text."""
        match = re.search(r"\b(\d+)\s*(?:items|orders|customers|days|days)", text)
        if match:
            return int(match.group(1))
        return None

    def _compute_confidence(self, feedback: str, business_term: str,
                            operation: str, conditions: list) -> float:
        score = 0.2  # base
        if business_term:
            score += 0.3
        if operation and operation != "include":
            score += 0.2
        if conditions:
            score += 0.3
        return min(score, 1.0)