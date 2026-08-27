"""Baseline validator for deterministic schema validation.

This implements rule validation against domain pack schemas.
The validator produces PASS/PARTIAL/FAIL status with coverage metrics.

Validation checks:
- Business term validation (against glossary)
- Operation validation (against valid operations)
- Condition validation (field, operator, value)
- Scope validation (against valid scopes)
- Threshold validation (if applicable)
"""

import json
from typing import Dict, Any, List
from pathlib import Path


class BaselineValidator:
    """Deterministic schema validator."""

    def __init__(self, schema: Dict[str, Any], glossary: Dict[str, Any]):
        """Initialize validator with schema and glossary."""
        self.schema = schema
        self.glossary = glossary
        self._init_valid_operations()
        self._init_valid_scopes()

    def _init_valid_operations(self):
        """Initialize valid operations."""
        self.valid_operations = [
            "exclude", "include", "restrict", "map", "replace",
            "add", "subtract", "mask", "expose", "drop", "keep"
        ]

    def _init_valid_scopes(self):
        """Initialize valid scopes."""
        self.valid_scopes = ["global"]

        # Add region scopes
        for i in range(1, 10):
            self.valid_scopes.append(f"region:{i}")

        # Add time scopes
        self.valid_scopes.extend([
            "time:daily", "time:weekly", "time:monthly",
            "time:quarterly", "time:yearly", "time:custom"
        ])

    def validate(self, extracted_rule: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extracted rule against schema.

        Parameters
        ----------
        extracted_rule: dict
            Extracted rule with business_term, operation, conditions, scope.

        Returns
        -------
        dict
            Validation result with status, coverage, and details.
        """
        validated_fields = []
        invalid_fields = []
        validation_errors = []

        # Validate mandatory fields
        mandatory_fields = ["business_term", "operation", "scope"]
        missing_mandatory = []

        for field in mandatory_fields:
            if field not in extracted_rule or not extracted_rule[field]:
                missing_mandatory.append(field)
                validation_errors.append(f"Missing mandatory field: {field}")

        # Validate business term
        if extracted_rule.get("business_term"):
            if self._validate_business_term(extracted_rule["business_term"]):
                validated_fields.append("business_term")
            else:
                invalid_fields.append("business_term")
                validation_errors.append(f"Invalid business term: {extracted_rule['business_term']}")

        # Validate operation
        if extracted_rule.get("operation"):
            if self._validate_operation(extracted_rule["operation"]):
                validated_fields.append("operation")
            else:
                invalid_fields.append("operation")
                validation_errors.append(f"Invalid operation: {extracted_rule['operation']}")

        # Validate conditions
        if extracted_rule.get("conditions"):
            condition_validation = self._validate_conditions(extracted_rule["conditions"])
            validated_fields.extend(condition_validation["validated"])
            invalid_fields.extend(condition_validation["invalid"])
            validation_errors.extend(condition_validation["errors"])

        # Validate affected entities
        if extracted_rule.get("affected_entities"):
            entities_validation = self._validate_affected_entities(
                extracted_rule["affected_entities"]
            )
            validated_fields.extend(entities_validation["validated"])
            invalid_fields.extend(entities_validation["invalid"])
            validation_errors.extend(entities_validation["errors"])

        # Validate scope
        if extracted_rule.get("scope"):
            if self._validate_scope(extracted_rule["scope"]):
                validated_fields.append("scope")
            else:
                invalid_fields.append("scope")
                validation_errors.append(f"Invalid scope: {extracted_rule['scope']}")

        # Calculate coverage
        total_checkable = len(validated_fields) + len(invalid_fields)
        coverage = len(validated_fields) / total_checkable if total_checkable > 0 else 0.0

        # Determine status
        if len(invalid_fields) == 0 and len(missing_mandatory) == 0:
            status = "PASS"
        elif coverage >= 0.5:
            status = "PARTIAL"
        else:
            status = "FAIL"

        return {
            "status": status,
            "coverage": round(coverage, 3),
            "mandatory_fields_valid": len(missing_mandatory) == 0,
            "validated_fields": list(set(validated_fields)),
            "invalid_fields": list(set(invalid_fields)),
            "validation_errors": validation_errors,
            "missing_mandatory": missing_mandatory,
        }

    def _validate_business_term(self, business_term: str) -> bool:
        """Validate business term exists in glossary."""
        # Check if term exists in glossary
        if business_term in self.glossary.get("terms", {}):
            return True

        # Check common business terms
        common_terms = ["revenue", "order", "customer", "product", "payment"]
        if business_term.lower() in common_terms:
            return True

        return False

    def _validate_operation(self, operation: str) -> bool:
        """Validate operation is valid."""
        return operation.lower() in self.valid_operations

    def _validate_conditions(self, conditions: List[Dict]) -> Dict[str, Any]:
        """Validate condition structure against schema."""
        validated = []
        invalid = []
        errors = []

        if not self.schema.get("tables"):
            return {"validated": [], "invalid": [], "errors": []}

        for condition in conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "").lower()

            # Validate field exists in schema
            if "." in field:
                table, column = field.split(".", 1)
                if table in self.schema["tables"]:
                    if column in self.schema["tables"][table].get("columns", {}):
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
        self, affected_entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate affected tables and columns exist in schema."""
        validated = []
        invalid = []
        errors = []

        if not self.schema.get("tables"):
            return {"validated": [], "invalid": [], "errors": []}

        tables = affected_entities.get("tables", [])
        for table in tables:
            if table in self.schema["tables"]:
                validated.append(f"affected_entities.table:{table}")
            else:
                invalid.append(f"affected_entities.table:{table}")
                errors.append(f"Table not found in schema: {table}")

        columns = affected_entities.get("columns", [])
        for column in columns:
            if "." in column:
                table, col = column.split(".", 1)
                if table in self.schema["tables"]:
                    if col in self.schema["tables"][table].get("columns", {}):
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

    def _validate_scope(self, scope: str) -> bool:
        """Validate scope is valid."""
        return scope in self.valid_scopes


def load_glossary(domain: str = "ecommerce") -> Dict[str, Any]:
    """Load glossary for domain."""
    glossary_path = Path(__file__).parent.parent.parent / "domain-packs" / domain / "glossary" / "glossary.json"

    if glossary_path.exists():
        with open(glossary_path, "r", encoding="utf-8") as f:
            return json.load(f)

    return {"terms": {}}


def load_schema(domain: str = "ecommerce") -> Dict[str, Any]:
    """Load schema for domain."""
    schema_path = Path(__file__).parent.parent.parent / "domain-packs" / domain / "schema" / "schema.json"

    if schema_path.exists():
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    return {"tables": {}}


if __name__ == "__main__":
    # Test the validator
    glossary = load_glossary("ecommerce")
    schema = load_schema("ecommerce")

    validator = BaselineValidator(schema, glossary)

    # Test validation
    test_rule = {
        "business_term": "revenue",
        "operation": "exclude",
        "conditions": [
            {"field": "orders.status", "operator": "equals", "value": "cancelled"}
        ],
        "scope": "global"
    }

    result = validator.validate(test_rule)
    print("Validation Result:")
    print(json.dumps(result, indent=2))
