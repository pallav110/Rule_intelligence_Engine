"""Validation service for business rule validation.

Uses trained baseline validator (schema-based) for deterministic
rule validation with fallback to simple checks if needed.
"""

import re
import os
from typing import Dict, Any, List
from pathlib import Path


class RealValidator:
    """Validate extracted business rules against schema."""

    def __init__(self, domain: str = "ecommerce"):
        """Initialize validator with optional trained baseline model."""
        self.domain = domain
        self.is_ready = False
        self.validator = None
        self.glossary = None
        self.schema = None
        self._fallback_to_simple = False

        # Try to load baseline validator
        self._load_baseline_validator()

    def _load_baseline_validator(self):
        """Load trained baseline validator if available."""
        try:
            from rie_ml.src.baseline.validator import BaselineValidator, load_glossary, load_schema

            # Load glossary and schema
            self.glossary = load_glossary(self.domain)
            self.schema = load_schema(self.domain)

            if self.glossary and self.schema:
                self.validator = BaselineValidator(self.schema, self.glossary)
                self.is_ready = True
                print(f"✅ Loaded baseline validator for domain: {self.domain}")
            else:
                print(f"⚠️  No glossary/schema found for {self.domain}, using simple fallback")
                self._fallback_to_simple = True
        except Exception as e:
            print(f"⚠️  Failed to load baseline validator: {e}, using simple fallback")
            self._fallback_to_simple = True

    def validate(
        self,
        extracted_rule: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate extracted rule against schema.

        Parameters
        ----------
        extracted_rule: dict
            Extracted rule with business_term, operation, conditions, scope.

        Returns
        -------
        dict
            {
                "status": "PASS|PARTIAL|FAIL",
                "coverage": 0.0-1.0,
                "mandatory_fields_valid": bool,
                "validated_fields": [str],
                "invalid_fields": [str],
                "validation_errors": [str],
                "missing_mandatory": [str],
                "method": "baseline|fallback"
            }
        """
        if self.is_ready and self.validator and not self._fallback_to_simple:
            try:
                result = self.validator.validate(extracted_rule)
                result["method"] = "baseline"
                return result
            except Exception as e:
                print(f"⚠️  Validator failed: {e}, falling back to simple checks")
                return self._validate_with_simple_checks(extracted_rule)
        else:
            return self._validate_with_simple_checks(extracted_rule)

    def _validate_with_simple_checks(self, extracted_rule: Dict[str, Any]) -> Dict[str, Any]:
        """Validate using simple checks (fallback)."""
        validated_fields = []
        invalid_fields = []
        validation_errors = []
        missing_mandatory = []

        # Check mandatory fields
        mandatory_fields = ["business_term", "operation", "scope"]
        for field in mandatory_fields:
            if field not in extracted_rule or not extracted_rule[field]:
                missing_mandatory.append(field)
                validation_errors.append(f"Missing mandatory field: {field}")

        # Validate business term
        if extracted_rule.get("business_term"):
            common_terms = ["revenue", "order", "customer", "product", "payment"]
            if extracted_rule["business_term"].lower() in common_terms:
                validated_fields.append("business_term")
            else:
                invalid_fields.append("business_term")
                validation_errors.append(f"Invalid business term: {extracted_rule['business_term']}")

        # Validate operation
        if extracted_rule.get("operation"):
            valid_ops = ["exclude", "include", "restrict", "map", "subtract"]
            if extracted_rule["operation"].lower() in valid_ops:
                validated_fields.append("operation")
            else:
                invalid_fields.append("operation")
                validation_errors.append(f"Invalid operation: {extracted_rule['operation']}")

        # Validate conditions
        if extracted_rule.get("conditions"):
            for i, cond in enumerate(extracted_rule["conditions"]):
                if "." in cond.get("field", ""):
                    validated_fields.append(f"conditions.{i}")
                else:
                    invalid_fields.append(f"conditions.{i}")
                    validation_errors.append(f"Field must be qualified: table.column")

        # Validate scope
        if extracted_rule.get("scope"):
            if extracted_rule["scope"] in ["global", "region:1", "region:2"]:
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
            "validated_fields": validated_fields,
            "invalid_fields": invalid_fields,
            "validation_errors": validation_errors,
            "missing_mandatory": missing_mandatory,
            "method": "fallback"
        }

    def train(self, training_data, labels):
        """Train validator (not used with baseline model)."""
        self.is_ready = True
        return {"status": "using_baseline_model"}


if __name__ == "__main__":
    # Test the validator
    validator = RealValidator("ecommerce")

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
    print(result)
