"""NER-based entity extraction using domain pack schema context."""

import re
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Entity:
    """Extracted entity with type and value."""
    type: str
    value: str
    confidence: float
    table: Optional[str] = None
    column: Optional[str] = None
    source: str = "regex"  # regex, fuzzy_match, context_inference


class EntityExtractor:
    """Extract named entities from feedback text using domain pack schema."""

    def __init__(self, domain_pack: Dict[str, Any]):
        """Initialize extractor with domain pack schema."""
        self.domain_pack = domain_pack
        self.schema = domain_pack.get("tables", {})
        self.entity_patterns = self._build_patterns()

    def _build_patterns(self) -> Dict[str, List[Tuple[str, float]]]:
        """
        Build regex patterns for domain entities from schema.
        Returns dict mapping entity_type -> [(pattern, confidence), ...]
        """
        patterns = {}

        # Extract column names and values as entity patterns
        for table_name, table_def in self.schema.items():
            columns = table_def.get("columns", {})
            for col_name, col_def in columns.items():
                # Add column as potential entity
                entity_type = self._infer_entity_type(col_name, col_def)
                if entity_type:
                    pattern = self._make_pattern(col_name)
                    if entity_type not in patterns:
                        patterns[entity_type] = []
                    patterns[entity_type].append((pattern, 0.8))

                # Add allowed_values as entity patterns
                if "allowed_values" in col_def:
                    for val in col_def["allowed_values"]:
                        if entity_type not in patterns:
                            patterns[entity_type] = []
                        val_pattern = rf"\b{re.escape(val)}\b"
                        patterns[entity_type].append((val_pattern, 0.9))

        return patterns

    def _infer_entity_type(self, col_name: str, col_def: Dict[str, Any]) -> Optional[str]:
        """Infer entity type from column name and definition."""
        col_lower = col_name.lower()

        # Customer-related
        if "customer" in col_lower or "segment" in col_lower:
            return "CUSTOMER_SEGMENT"
        if "tier" in col_lower or "plan" in col_lower:
            return "ACCOUNT_TYPE"
        if "email" in col_lower or "contact" in col_lower:
            return "CONTACT_INFO"

        # Time-related
        if any(x in col_lower for x in ["date", "time", "at", "minutes", "hours", "days"]):
            return "TIME_PERIOD"

        # Status and operational
        if "status" in col_lower or "state" in col_lower:
            return "STATUS"
        if "priority" in col_lower:
            return "PRIORITY"

        # Access and scope
        if "department" in col_lower or "team" in col_lower:
            return "DEPARTMENT"
        if "role" in col_lower or "permission" in col_lower:
            return "ROLE"

        # Product-related
        if "product" in col_lower or "item" in col_lower:
            return "PRODUCT"

        # Data quality
        if "is_" in col_lower or "active" in col_lower or "internal" in col_lower:
            return "DATA_QUALITY_FLAG"

        return None

    def _make_pattern(self, text: str) -> str:
        """Convert text to regex pattern."""
        words = text.split("_")
        # Match with or without underscores, case-insensitive
        pattern = r"\b" + r"\s*".join(re.escape(w) for w in words) + r"\b"
        return pattern

    def extract(self, feedback_text: str) -> Dict[str, Any]:
        """Extract entities from feedback text."""
        entities = []
        affected_tables = set()
        affected_columns = set()

        # Run pattern matching
        for entity_type, patterns in self.entity_patterns.items():
            for pattern, base_confidence in patterns:
                matches = re.finditer(pattern, feedback_text, re.IGNORECASE)
                for match in matches:
                    entity_value = match.group(0).strip()

                    # Find which table/column this refers to
                    table, column = self._find_source_table_column(entity_type, entity_value)
                    if table:
                        affected_tables.add(table)
                        if column:
                            affected_columns.add(f"{table}.{column}")

                    # Boost confidence if matched against allowed_values
                    confidence = self._calculate_confidence(entity_type, entity_value, base_confidence)

                    entities.append(
                        Entity(
                            type=entity_type,
                            value=entity_value,
                            confidence=confidence,
                            table=table,
                            column=column,
                            source="regex",
                        )
                    )

        # Extract time windows (e.g., "60 days", "within 24 hours")
        time_entities = self._extract_time_windows(feedback_text)
        entities.extend(time_entities)

        # Extract numbers/thresholds
        threshold_entities = self._extract_thresholds(feedback_text)
        entities.extend(threshold_entities)

        return {
            "entities": [
                {
                    "type": e.type,
                    "value": e.value,
                    "confidence": e.confidence,
                    "table": e.table,
                    "column": e.column,
                    "source": e.source,
                }
                for e in entities
            ],
            "affected_entities": {
                "tables": sorted(list(affected_tables)),
                "columns": sorted(list(affected_columns)),
            },
            "entity_count": len(entities),
        }

    def _find_source_table_column(self, entity_type: str, entity_value: str) -> Tuple[Optional[str], Optional[str]]:
        """Find which table/column this entity refers to."""
        entity_lower = entity_value.lower()

        for table_name, table_def in self.schema.items():
            columns = table_def.get("columns", {})
            for col_name, col_def in columns.items():
                col_lower = col_name.lower()

                # Match against column name
                if col_lower.replace("_", " ") == entity_lower.replace("_", " "):
                    return table_name, col_name

                # Match against allowed_values
                if "allowed_values" in col_def:
                    for val in col_def["allowed_values"]:
                        if val.lower() == entity_lower:
                            return table_name, col_name

        return None, None

    def _calculate_confidence(self, entity_type: str, entity_value: str, base_confidence: float) -> float:
        """Calculate entity confidence score."""
        confidence = base_confidence

        # Boost for exact matches
        if entity_value.lower() in ["free", "pro", "enterprise", "active", "inactive", "standard", "high", "urgent"]:
            confidence = min(0.99, confidence + 0.15)

        # Reduce for short/ambiguous matches
        if len(entity_value) < 3:
            confidence = max(0.4, confidence - 0.2)

        return round(confidence, 3)

    def _extract_time_windows(self, text: str) -> List[Entity]:
        """Extract time window specifications like '60 days', 'within 24 hours'."""
        entities = []

        # Pattern: number + time unit
        time_patterns = [
            (r"(\d+)\s*(days?|weeks?|months?|years?|hours?|minutes?|seconds?)", "TIME_PERIOD"),
            (r"(within|within)\s+(\d+)\s*(days?|weeks?|months?|hours?)", "TIME_PERIOD"),
            (r"(first|within)\s+(\d+)\s*(response|reply)", "SLA_WINDOW"),
        ]

        for pattern, etype in time_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                value = match.group(0).strip()
                entities.append(
                    Entity(
                        type=etype,
                        value=value,
                        confidence=0.85,
                        source="time_pattern",
                    )
                )

        return entities

    def _extract_thresholds(self, text: str) -> List[Entity]:
        """Extract numeric thresholds and percentages."""
        entities = []

        # Pattern: number (possibly with unit)
        threshold_patterns = [
            (r"(\d+)\s*%", "PERCENTAGE"),
            (r"\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", "CURRENCY"),
            (r"((\d+)\s*(?:count|records?|items?|rows?|tickets?))", "COUNT"),
        ]

        for pattern, etype in threshold_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                value = match.group(0).strip()
                entities.append(
                    Entity(
                        type=etype,
                        value=value,
                        confidence=0.8,
                        source="threshold_pattern",
                    )
                )

        return entities


class RealEntityExtractor(EntityExtractor):
    """Production entity extractor using domain pack schema."""

    def extract_with_context(self, feedback_text: str, domain_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract entities with full context information."""
        base_extraction = self.extract(feedback_text)

        # If domain context provided, validate extracted entities against it
        if domain_context:
            base_extraction["validated"] = self._validate_against_context(
                base_extraction["entities"], domain_context
            )

        return base_extraction

    def _validate_against_context(self, entities: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extracted entities against domain context."""
        validation_result = {
            "valid_count": 0,
            "invalid_count": 0,
            "warnings": [],
        }

        context_tables = set(context.get("tables", []))
        context_columns = set(context.get("columns", []))

        for entity in entities:
            if entity.get("table") and entity["table"] not in context_tables:
                validation_result["warnings"].append(f"Entity table {entity['table']} not in context")
                validation_result["invalid_count"] += 1
            else:
                validation_result["valid_count"] += 1

        return validation_result
