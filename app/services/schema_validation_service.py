"""Schema validation service for extracted business rules.

Validates whether extracted entities and fields are valid within the active
Domain Pack and workspace schema. Produces PASS/PARTIAL/FAIL status with coverage metric.
"""

from typing import Dict, Any, List, Tuple
import json
from pathlib import Path


class SchemaValidationService:
    """Validates extracted rules against domain pack schema."""

    def __init__(self, domain_pack_schema: Dict[str, Any] = None, schema_context: Dict[str, Any] = None):
        """Initialize with domain pack schema or schema context."""
        # Support both old API (domain_pack_schema) and new API (schema_context)
        if schema_context:
            # Load schema from schema_context if available
            domain_pack_schema = schema_context.get("domain_pack_schema") or schema_context

        self.domain_pack_schema = domain_pack_schema or {}

    def validate_rule(
        self,
        rule: Dict[str, Any],
        schema: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Validate extracted rule against schema.

        Args:
            rule: Extracted rule dict with business_term, operation, conditions, etc.
            schema: Domain pack schema (tables, columns)

        Returns:
            {
                "status": "PASS|PARTIAL|FAIL",
                "coverage": 0.0-1.0,
                "mandatory_fields_valid": bool,
                "validated_fields": [...],
                "invalid_fields": [...],
                "validation_errors": [...],
                "missing_mandatory": [...],
                "schema_loaded": bool
            }
        """
        # Track if we have a valid schema for this validation
        schema = schema or self.domain_pack_schema
        schema_loaded = bool(schema and schema.get("tables"))
        validation_errors = []
        validated_fields = []
        invalid_fields = []
        missing_mandatory = []

        # Check mandatory fields
        mandatory_fields = ["business_term", "operation", "scope"]
        for field in mandatory_fields:
            if field not in rule or not rule[field]:
                missing_mandatory.append(field)
                validation_errors.append(f"Missing mandatory field: {field}")

        # Validate business term (glossary check would go here)
        if rule.get("business_term"):
            validated_fields.append("business_term")
        else:
            invalid_fields.append("business_term")

        # Validate operation
        valid_operations = [
            "exclude", "include", "restrict", "map", "replace", "add", "subtract"
        ]
        operation = rule.get("operation")
        if operation and operation.lower() in valid_operations:
            validated_fields.append("operation")
        else:
            invalid_fields.append("operation")
            validation_errors.append(
                f"Invalid or missing operation: {operation}. "
                f"Valid operations: {valid_operations}"
            )

        # Validate conditions against schema
        if "conditions" in rule and rule["conditions"]:
            condition_validation = self._validate_conditions(
                rule["conditions"], schema
            )
            validated_fields.extend(condition_validation["validated"])
            invalid_fields.extend(condition_validation["invalid"])
            validation_errors.extend(condition_validation["errors"])

        # Validate affected entities against schema
        affected_validation = self._validate_affected_entities(
            rule.get("affected_entities", {}), schema
        )
        validated_fields.extend(affected_validation["validated"])
        invalid_fields.extend(affected_validation["invalid"])
        validation_errors.extend(affected_validation["errors"])

        # Calculate coverage and status
        total_checkable = len(validated_fields) + len(invalid_fields)
        coverage = (
            len(validated_fields) / total_checkable if total_checkable > 0 else 0.0
        )

        # Determine status
        # If schema not loaded, status must be FAIL (cannot validate without schema)
        if not schema_loaded:
            status = "FAIL"
        elif len(invalid_fields) == 0 and len(missing_mandatory) == 0:
            status = "PASS"
        elif coverage >= 0.5:
            status = "PARTIAL"
        else:
            status = "FAIL"

        return {
            "status": status,
            "coverage": round(coverage, 3),
            "mandatory_fields_valid": len(missing_mandatory) == 0,
            "schema_loaded": schema_loaded,
            "validated_fields": list(set(validated_fields)),
            "invalid_fields": list(set(invalid_fields)),
            "validation_errors": validation_errors,
            "missing_mandatory": missing_mandatory,
        }

    def _validate_conditions(
        self, conditions: List[Dict[str, Any]], schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate condition structure against schema."""
        validated = []
        invalid = []
        errors = []

        # If no schema, skip validation (don't add error - top-level handles it)
        if not schema or not schema.get("tables"):
            return {"validated": [], "invalid": [], "errors": []}

        for condition in conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "").lower()

            # Validate field exists in schema
            if "." in field:
                table, column = field.split(".", 1)
                if table in schema["tables"]:
                    if column in schema["tables"][table].get("columns", {}):
                        validated.append(f"conditions.{field}")
                    else:
                        invalid.append(f"conditions.{field}")
                        errors.append(f"Column not found: {field}")
                else:
                    invalid.append(f"conditions.{field}")
                    errors.append(f"Table not found: {table}")
            else:
                invalid.append(f"conditions.{field}")
                errors.append(f"Field must be qualified: table.column (got: {field})")

            # Validate operator
            valid_operators = [
                "equals", "not_equals", "greater_than", "less_than",
                "greater_than_or_equal", "less_than_or_equal", "in", "not_in",
                "contains", "is_null", "is_not_null"
            ]
            if operator not in valid_operators:
                invalid.append(f"conditions.operator")
                errors.append(
                    f"Invalid operator: {operator}. Valid: {valid_operators}"
                )
            else:
                validated.append(f"conditions.operator")

        return {"validated": validated, "invalid": invalid, "errors": errors}

    def _validate_affected_entities(
        self, affected_entities: Dict[str, Any], schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate affected tables and columns exist in schema."""
        validated = []
        invalid = []
        errors = []

        if not schema.get("tables"):
            return {"validated": [], "invalid": [], "errors": []}

        tables = affected_entities.get("tables", [])
        for table in tables:
            if table in schema["tables"]:
                validated.append(f"affected_entities.table:{table}")
            else:
                invalid.append(f"affected_entities.table:{table}")
                errors.append(f"Table not found in schema: {table}")

        columns = affected_entities.get("columns", [])
        for column in columns:
            if "." in column:
                table, col = column.split(".", 1)
                if table in schema["tables"]:
                    if col in schema["tables"][table].get("columns", {}):
                        validated.append(f"affected_entities.column:{column}")
                    else:
                        invalid.append(f"affected_entities.column:{column}")
                        errors.append(f"Column not found: {column}")
                else:
                    invalid.append(f"affected_entities.column:{column}")
                    errors.append(f"Table not found: {table}")
            else:
                invalid.append(f"affected_entities.column:{column}")
                errors.append(f"Column must be qualified: table.column (got: {column})")

        return {"validated": validated, "invalid": invalid, "errors": errors}


def validate_extracted_rules(
    rules: List[Dict[str, Any]], schema: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Validate a list of extracted rules against schema."""
    service = SchemaValidationService(schema)
    return [service.validate_rule(rule, schema) for rule in rules]
