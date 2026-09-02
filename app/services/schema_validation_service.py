"""Schema validation service for extracted business rules.

Validates whether extracted entities and fields are valid within the active
Domain Pack and workspace schema. Produces PASS/PARTIAL/FAIL status with coverage metric.

Performs 10 validation checks per spec 8.5:
1. Business term existence (glossary check)
2. Table existence
3. Column existence
4. Field-to-table relationship
5. Valid operation for identified field
6. Valid operator for field type
7. Valid value type for operator
8. Valid scope
9. Valid time window
10. Required rule components present
"""

from typing import Dict, Any, List
import json
from datetime import datetime


class SchemaValidationService:
    """Validates extracted rules against domain pack schema."""

    VALID_OPERATIONS = [
        "exclude", "include", "restrict", "map", "replace", "add", "subtract"
    ]

    VALID_OPERATORS = [
        "equals", "not_equals", "greater_than", "less_than",
        "greater_than_or_equal", "less_than_or_equal", "in", "not_in",
        "contains", "is_null", "is_not_null"
    ]

    # Type compatibility for operators
    OPERATOR_TYPE_COMPATIBILITY = {
        "equals": ["string", "integer", "boolean", "timestamp"],
        "not_equals": ["string", "integer", "boolean", "timestamp"],
        "greater_than": ["integer", "timestamp", "decimal"],
        "less_than": ["integer", "timestamp", "decimal"],
        "greater_than_or_equal": ["integer", "timestamp", "decimal"],
        "less_than_or_equal": ["integer", "timestamp", "decimal"],
        "in": ["string", "integer"],
        "not_in": ["string", "integer"],
        "contains": ["string"],
        "is_null": ["string", "integer", "boolean", "timestamp", "decimal"],
        "is_not_null": ["string", "integer", "boolean", "timestamp", "decimal"]
    }

    def __init__(self, domain_pack_schema: Dict[str, Any] = None, schema_context: Dict[str, Any] = None):
        """Initialize with domain pack schema or schema context."""
        if schema_context:
            domain_pack_schema = schema_context.get("domain_pack_schema") or schema_context
        self.domain_pack_schema = domain_pack_schema or {}

    def validate_rule(
        self,
        rule: Dict[str, Any],
        schema: Dict[str, Any] = None,
        glossary: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate extracted rule against schema.

        Args:
            rule: Extracted rule dict with business_term, operation, conditions, etc.
            schema: Domain pack schema (tables, columns)
            glossary: Business term glossary for validation

        Returns:
            {
                "status": "PASS|PARTIAL|FAIL",
                "coverage": 0.0-1.0,
                "mandatory_fields_valid": bool,
                "validated_fields": [...],
                "invalid_fields": [...],
                "validation_errors": [...],
                "missing_mandatory": [...],
                "schema_loaded": bool,
                "validation_timestamp": str,
                "check_results": {
                    "business_term_exists": bool,
                    "table_exists": bool,
                    "column_exists": bool,
                    "field_to_table_relation": bool,
                    "valid_operation": bool,
                    "valid_operator": bool,
                    "valid_value_type": bool,
                    "valid_scope": bool,
                    "valid_time_window": bool,
                    "required_components": bool
                }
            }
        """
        schema = schema or self.domain_pack_schema
        schema_loaded = bool(schema and schema.get("tables"))

        validation_errors = []
        validated_fields = []
        invalid_fields = []
        missing_mandatory = []
        check_results = {}

        # Track checks
        checks_passed = 0
        checks_total = 10

        # Check 1: Mandatory fields present
        mandatory_fields = ["business_term", "operation"]
        for field in mandatory_fields:
            if field not in rule or not rule[field]:
                missing_mandatory.append(field)
                validation_errors.append(f"Missing mandatory field: {field}")

        check_results["required_components"] = len(missing_mandatory) == 0
        if check_results["required_components"]:
            checks_passed += 1

        if missing_mandatory:
            checks_total += 1

        # Check 2: Business term exists (glossary check)
        business_term = rule.get("business_term", "").strip()
        if business_term:
            if glossary is None:
                glossary = self._extract_glossary_from_schema(schema)

            term_exists = any(
                business_term.lower() in term.lower() or term.lower() in business_term.lower()
                for term in glossary
            )

            if term_exists:
                validated_fields.append("business_term")
                check_results["business_term_exists"] = True
                checks_passed += 1
            else:
                invalid_fields.append("business_term")
                check_results["business_term_exists"] = False
                validation_errors.append(
                    f"Business term '{business_term}' not found in glossary"
                )
        else:
            check_results["business_term_exists"] = False

        # Check 3: Operation validation
        operation = rule.get("operation", "").lower()
        if operation in self.VALID_OPERATIONS:
            validated_fields.append("operation")
            check_results["valid_operation"] = True
            checks_passed += 1
        else:
            invalid_fields.append("operation")
            check_results["valid_operation"] = False
            validation_errors.append(
                f"Invalid operation: {operation}. Valid: {self.VALID_OPERATIONS}"
            )

        if not schema_loaded:
            # Schema not available, still try to validate operation
            check_results["table_exists"] = False
            check_results["column_exists"] = False
            check_results["field_to_table_relation"] = False
            check_results["valid_operator"] = False
            check_results["valid_value_type"] = False
            check_results["valid_scope"] = False
            check_results["valid_time_window"] = False
        else:
            # Check 4-7: Conditions validation
            conditions = rule.get("conditions", [])
            condition_validation = self._validate_conditions(conditions, schema)

            validated_fields.extend(condition_validation["validated"])
            invalid_fields.extend(condition_validation["invalid"])
            validation_errors.extend(condition_validation["errors"])

            check_results["table_exists"] = condition_validation["table_exists"]
            check_results["column_exists"] = condition_validation["column_exists"]
            check_results["field_to_table_relation"] = condition_validation["field_to_table_relation"]
            check_results["valid_operator"] = condition_validation["valid_operator"]
            check_results["valid_value_type"] = condition_validation["valid_value_type"]

            if check_results["table_exists"]:
                checks_passed += 1
            if check_results["column_exists"]:
                checks_passed += 1
            if check_results["field_to_table_relation"]:
                checks_passed += 1
            if check_results["valid_operator"]:
                checks_passed += 1
            if check_results["valid_value_type"]:
                checks_passed += 1

            # Check 8: Scope validation
            scope = rule.get("scope", "global").strip()
            scope_valid = self._validate_scope(scope, schema)
            check_results["valid_scope"] = scope_valid
            if scope_valid:
                validated_fields.append("scope")
                checks_passed += 1
            else:
                invalid_fields.append("scope")
                validation_errors.append(f"Invalid scope: {scope}")

            # Check 9: Time window validation
            time_window = rule.get("time_window")
            time_window_valid = self._validate_time_window(time_window)
            check_results["valid_time_window"] = time_window_valid
            if time_window_valid:
                if time_window:
                    validated_fields.append("time_window")
                checks_passed += 1
            else:
                invalid_fields.append("time_window")
                validation_errors.append(f"Invalid time window: {time_window}")

            # Validate affected entities
            affected_validation = self._validate_affected_entities(
                rule.get("affected_tables", []),
                rule.get("affected_columns", []),
                schema
            )
            validated_fields.extend(affected_validation["validated"])
            invalid_fields.extend(affected_validation["invalid"])
            validation_errors.extend(affected_validation["errors"])

        # Calculate coverage and determine status
        total_checkable = len(validated_fields) + len(invalid_fields)
        coverage = len(validated_fields) / total_checkable if total_checkable > 0 else 0.0

        if not schema_loaded:
            status = "FAIL"
            validation_errors.insert(0, "Schema not loaded - cannot validate")
        elif len(missing_mandatory) > 0:
            # Missing mandatory fields always means FAIL
            status = "FAIL"
        elif len(invalid_fields) == 0:
            # No invalid fields means PASS
            status = "PASS"
        elif coverage >= 0.5:
            # Partial validity
            status = "PARTIAL"
        else:
            # Most fields invalid
            status = "FAIL"

        return {
            "status": status,
            "coverage": round(coverage, 3),
            "checks_passed": checks_passed,
            "checks_total": checks_total,
            "mandatory_fields_valid": len(missing_mandatory) == 0,
            "schema_loaded": schema_loaded,
            "validated_fields": list(set(validated_fields)),
            "invalid_fields": list(set(invalid_fields)),
            "validation_errors": validation_errors,
            "missing_mandatory": missing_mandatory,
            "check_results": check_results,
            "validation_timestamp": datetime.utcnow().isoformat() + "Z"
        }

    def _validate_conditions(
        self, conditions: List[Dict[str, Any]], schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate conditions (checks 4-7)."""
        validated = []
        invalid = []
        errors = []
        tables_exist = True
        columns_exist = True
        field_to_table_valid = True
        operators_valid = True
        value_types_valid = True

        if not conditions or not schema.get("tables"):
            return {
                "validated": [], "invalid": [], "errors": [],
                "table_exists": False, "column_exists": False,
                "field_to_table_relation": False, "valid_operator": False,
                "valid_value_type": False
            }

        for condition in conditions:
            field = condition.get("field", "").strip()
            operator = condition.get("operator", "").lower().strip()
            value = condition.get("value")

            # Validate field format
            if not field or "." not in field:
                invalid.append(f"condition.{field or 'unknown'}")
                errors.append(f"Field must be qualified: table.column (got: {field})")
                field_to_table_valid = False
                continue

            table, column = field.split(".", 1)

            # Check table exists
            if table not in schema["tables"]:
                invalid.append(f"condition.{field}")
                errors.append(f"Table not found: {table}")
                tables_exist = False
                field_to_table_valid = False
                continue
            else:
                validated.append(f"condition.table:{table}")

            # Check column exists
            col_info = schema["tables"][table].get("columns", {}).get(column)
            if not col_info:
                invalid.append(f"condition.{field}")
                errors.append(f"Column not found: {field}")
                columns_exist = False
                field_to_table_valid = False
            else:
                validated.append(f"condition.column:{column}")
                field_to_table_valid = True

            # Validate operator
            if operator not in self.VALID_OPERATORS:
                invalid.append(f"condition.operator")
                errors.append(f"Invalid operator: {operator}. Valid: {self.VALID_OPERATORS}")
                operators_valid = False
            else:
                validated.append(f"condition.operator:{operator}")

                # Check operator compatibility with field type (if column info available)
                if col_info:
                    field_type = col_info.get("type", "").lower()
                    allowed_types = self.OPERATOR_TYPE_COMPATIBILITY.get(operator, [])
                    if allowed_types and field_type not in allowed_types:
                        invalid.append(f"condition.operator_type_mismatch")
                        errors.append(
                            f"Operator {operator} not compatible with field type {field_type}. "
                            f"Valid types: {allowed_types}"
                        )
                        value_types_valid = False
                    else:
                        validated.append(f"condition.value_type_compatible:{field_type}")

        return {
            "validated": validated,
            "invalid": invalid,
            "errors": errors,
            "table_exists": tables_exist,
            "column_exists": columns_exist,
            "field_to_table_relation": field_to_table_valid,
            "valid_operator": operators_valid,
            "valid_value_type": value_types_valid
        }

    def _validate_scope(self, scope: str, schema: Dict[str, Any]) -> bool:
        """Check 8: Validate scope against schema."""
        if not scope or scope == "global":
            return True

        # Check if scope matches any table or domain defined in schema
        if schema.get("domain") and scope.lower() == schema["domain"].lower():
            return True

        if schema.get("tables"):
            for table_name in schema["tables"].keys():
                if scope.lower() == table_name.lower():
                    return True

        return False

    def _validate_time_window(self, time_window: Any) -> bool:
        """Check 9: Validate time window format."""
        if time_window is None:
            return True

        if isinstance(time_window, str):
            time_window = time_window.strip().lower()
            # Accept common time window patterns
            valid_patterns = [
                "current", "last", "previous", "today", "yesterday",
                "week", "month", "quarter", "year", "day", "hour",
                "mtd", "qtd", "ytd", "rolling", "trailing"
            ]
            return any(pattern in time_window for pattern in valid_patterns)

        return False

    def _validate_affected_entities(
        self, affected_tables: List[str], affected_columns: List[str], schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate affected tables and columns exist in schema."""
        validated = []
        invalid = []
        errors = []

        if not schema.get("tables"):
            return {"validated": [], "invalid": [], "errors": []}

        for table in affected_tables:
            if table in schema["tables"]:
                validated.append(f"affected_table:{table}")
            else:
                invalid.append(f"affected_table:{table}")
                errors.append(f"Table not found in schema: {table}")

        for column in affected_columns:
            if "." not in column:
                invalid.append(f"affected_column:{column}")
                errors.append(f"Column must be qualified: table.column (got: {column})")
                continue

            table, col = column.split(".", 1)
            if table not in schema["tables"]:
                invalid.append(f"affected_column:{column}")
                errors.append(f"Table not found: {table}")
            elif col not in schema["tables"][table].get("columns", {}):
                invalid.append(f"affected_column:{column}")
                errors.append(f"Column not found: {column}")
            else:
                validated.append(f"affected_column:{column}")

        return {"validated": validated, "invalid": invalid, "errors": errors}

    def _extract_glossary_from_schema(self, schema: Dict[str, Any]) -> List[str]:
        """Extract business terms from schema metadata."""
        glossary = []

        if not schema:
            return glossary

        # Extract from table descriptions
        for table_name, table_info in schema.get("tables", {}).items():
            glossary.append(table_name)
            if "business_meaning" in table_info:
                glossary.append(table_info["business_meaning"])

            # Extract from column business meanings
            for col_name, col_info in table_info.get("columns", {}).items():
                glossary.append(col_name)
                if "business_meaning" in col_info:
                    glossary.append(col_info["business_meaning"])

        return list(set(glossary))


def validate_extracted_rules(
    rules: List[Dict[str, Any]], schema: Dict[str, Any], glossary: List[str] = None
) -> List[Dict[str, Any]]:
    """Validate a list of extracted rules against schema."""
    service = SchemaValidationService(schema)
    return [service.validate_rule(rule, schema, glossary) for rule in rules]
