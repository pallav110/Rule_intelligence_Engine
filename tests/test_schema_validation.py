"""Tests for schema validation module."""

import pytest
from datetime import datetime
from app.services.schema_validation_service import SchemaValidationService, validate_extracted_rules
from app.services.validation_pipeline import ValidationPipeline


@pytest.fixture
def sample_schema():
    """Sample domain pack schema for testing."""
    return {
        "version": "schema_v0.1.0",
        "domain": "ecommerce",
        "tables": {
            "orders": {
                "description": "Customer orders",
                "columns": {
                    "order_id": {"type": "integer", "nullable": False},
                    "customer_id": {"type": "integer", "nullable": False},
                    "status": {"type": "string", "nullable": False, "allowed_values": ["pending", "completed", "cancelled"]},
                    "amount": {"type": "decimal", "nullable": False},
                    "created_at": {"type": "timestamp", "nullable": False}
                }
            },
            "customers": {
                "description": "Customer information",
                "columns": {
                    "customer_id": {"type": "integer", "nullable": False},
                    "name": {"type": "string", "nullable": False},
                    "email": {"type": "string", "nullable": True},
                    "country": {"type": "string", "nullable": True}
                }
            }
        }
    }


@pytest.fixture
def sample_glossary():
    """Sample business glossary."""
    return ["revenue", "order", "customer", "sales", "transaction"]


class TestSchemaValidationService:
    """Tests for SchemaValidationService."""

    def test_validate_rule_pass(self, sample_schema, sample_glossary):
        """Test validation of a complete, valid rule."""
        service = SchemaValidationService(sample_schema)

        rule = {
            "business_term": "revenue",
            "operation": "exclude",
            "conditions": [
                {"field": "orders.status", "operator": "equals", "value": "cancelled"}
            ],
            "scope": "global",
            "affected_tables": ["orders"],
            "affected_columns": ["orders.status"]
        }

        result = service.validate_rule(rule, sample_schema, sample_glossary)

        assert result["status"] == "PASS"
        assert result["coverage"] == 1.0
        assert result["mandatory_fields_valid"] is True
        assert result["schema_loaded"] is True
        assert len(result["validation_errors"]) == 0

    def test_validate_rule_missing_mandatory_field(self, sample_schema, sample_glossary):
        """Test validation fails when mandatory field missing."""
        service = SchemaValidationService(sample_schema)

        rule = {
            "operation": "exclude",
            # Missing business_term
            "conditions": [
                {"field": "orders.status", "operator": "equals", "value": "cancelled"}
            ]
        }

        result = service.validate_rule(rule, sample_schema, sample_glossary)

        # Missing mandatory fields = FAIL
        assert result["status"] == "FAIL"
        assert "business_term" in result["missing_mandatory"]
        assert result["mandatory_fields_valid"] is False

    def test_validate_rule_invalid_operation(self, sample_schema, sample_glossary):
        """Test validation detects invalid operation."""
        service = SchemaValidationService(sample_schema)

        rule = {
            "business_term": "revenue",
            "operation": "invalid_op",
            "conditions": []
        }

        result = service.validate_rule(rule, sample_schema, sample_glossary)

        # Invalid operation detected (but with valid business_term and scope, coverage > 0.5)
        assert result["status"] in ["PARTIAL", "FAIL"]
        assert "operation" in result["invalid_fields"]
        assert any("Invalid operation" in e for e in result["validation_errors"])

    def test_validate_rule_invalid_table(self, sample_schema, sample_glossary):
        """Test validation detects invalid table."""
        service = SchemaValidationService(sample_schema)

        rule = {
            "business_term": "revenue",
            "operation": "exclude",
            "conditions": [
                {"field": "nonexistent.column", "operator": "equals", "value": "test"}
            ]
        }

        result = service.validate_rule(rule, sample_schema, sample_glossary)

        # Invalid table detected (but with other valid fields, may be PARTIAL)
        assert result["status"] in ["PARTIAL", "FAIL"]
        assert "Table not found" in str(result["validation_errors"])

    def test_validate_rule_invalid_column(self, sample_schema, sample_glossary):
        """Test validation detects invalid column."""
        service = SchemaValidationService(sample_schema)

        rule = {
            "business_term": "revenue",
            "operation": "exclude",
            "conditions": [
                {"field": "orders.nonexistent_col", "operator": "equals", "value": "test"}
            ]
        }

        result = service.validate_rule(rule, sample_schema, sample_glossary)

        assert result["status"] in ["PARTIAL", "FAIL"]
        assert "Column not found" in str(result["validation_errors"])

    def test_validate_rule_invalid_operator(self, sample_schema, sample_glossary):
        """Test validation detects invalid operator."""
        service = SchemaValidationService(sample_schema)

        rule = {
            "business_term": "revenue",
            "operation": "exclude",
            "conditions": [
                {"field": "orders.status", "operator": "invalid_op", "value": "test"}
            ]
        }

        result = service.validate_rule(rule, sample_schema, sample_glossary)

        assert result["status"] in ["PARTIAL", "FAIL"]
        assert any("Invalid operator" in e for e in result["validation_errors"])

    def test_validate_rule_operator_type_mismatch(self, sample_schema, sample_glossary):
        """Test validation detects operator/type mismatch."""
        service = SchemaValidationService(sample_schema)

        rule = {
            "business_term": "revenue",
            "operation": "exclude",
            "conditions": [
                # 'greater_than' not valid for string field
                {"field": "orders.status", "operator": "greater_than", "value": 100}
            ]
        }

        result = service.validate_rule(rule, sample_schema, sample_glossary)

        assert result["status"] in ["PARTIAL", "FAIL"]
        # Should detect the mismatch
        assert any("operator" in e.lower() or "type" in e.lower() for e in result["validation_errors"])

    def test_validate_rule_no_schema(self, sample_glossary):
        """Test validation fails gracefully without schema."""
        service = SchemaValidationService({})

        rule = {
            "business_term": "revenue",
            "operation": "exclude",
            "conditions": [
                {"field": "orders.status", "operator": "equals", "value": "cancelled"}
            ]
        }

        result = service.validate_rule(rule, {}, sample_glossary)

        assert result["status"] == "FAIL"
        assert result["schema_loaded"] is False

    def test_validate_rule_partial_valid(self, sample_schema, sample_glossary):
        """Test PARTIAL status when some fields invalid."""
        service = SchemaValidationService(sample_schema)

        rule = {
            "business_term": "revenue",
            "operation": "exclude",
            "conditions": [
                {"field": "orders.status", "operator": "equals", "value": "cancelled"},
                {"field": "orders.nonexistent", "operator": "equals", "value": "test"}
            ],
            "affected_tables": ["orders", "nonexistent_table"]
        }

        result = service.validate_rule(rule, sample_schema, sample_glossary)

        assert result["status"] == "PARTIAL"
        assert result["coverage"] >= 0.5
        assert len(result["invalid_fields"]) > 0

    def test_validate_rule_check_results(self, sample_schema, sample_glossary):
        """Test that check_results contains all 10 checks."""
        service = SchemaValidationService(sample_schema)

        rule = {
            "business_term": "revenue",
            "operation": "exclude",
            "conditions": [
                {"field": "orders.status", "operator": "equals", "value": "cancelled"}
            ],
            "scope": "global",
            "time_window": "current month"
        }

        result = service.validate_rule(rule, sample_schema, sample_glossary)

        assert "check_results" in result
        assert "required_components" in result["check_results"]
        assert "business_term_exists" in result["check_results"]
        assert "valid_operation" in result["check_results"]
        assert "table_exists" in result["check_results"]
        assert "column_exists" in result["check_results"]
        assert "field_to_table_relation" in result["check_results"]
        assert "valid_operator" in result["check_results"]
        assert "valid_value_type" in result["check_results"]
        assert "valid_scope" in result["check_results"]
        assert "valid_time_window" in result["check_results"]

    def test_validate_time_window_valid(self, sample_schema):
        """Test time window validation accepts valid patterns."""
        service = SchemaValidationService(sample_schema)

        valid_windows = ["current month", "last quarter", "ytd", "rolling 30 days", "trailing week"]

        for window in valid_windows:
            result = service._validate_time_window(window)
            assert result is True, f"Should accept: {window}"

    def test_validate_time_window_invalid(self, sample_schema):
        """Test time window validation rejects invalid patterns."""
        service = SchemaValidationService(sample_schema)

        invalid_windows = ["xyz", "something random", "12345"]

        for window in invalid_windows:
            result = service._validate_time_window(window)
            assert result is False, f"Should reject: {window}"

    def test_validate_scope_valid(self, sample_schema):
        """Test scope validation."""
        service = SchemaValidationService(sample_schema)

        # Global scope
        assert service._validate_scope("global", sample_schema) is True

        # Table name
        assert service._validate_scope("orders", sample_schema) is True
        assert service._validate_scope("customers", sample_schema) is True

        # Domain
        assert service._validate_scope("ecommerce", sample_schema) is True

    def test_validate_scope_invalid(self, sample_schema):
        """Test scope validation rejects invalid scopes."""
        service = SchemaValidationService(sample_schema)

        assert service._validate_scope("nonexistent_table", sample_schema) is False


class TestValidationPipeline:
    """Tests for ValidationPipeline."""

    def test_validation_pipeline_pass(self, sample_schema):
        """Test pipeline with all validations passing."""
        pipeline = ValidationPipeline()
        pipeline.domain_schema = sample_schema
        pipeline.schema_validator = SchemaValidationService(sample_schema)
        pipeline.glossary = ["revenue", "order", "customer"]

        classification_result = {
            "confidence": 0.95,
            "feedback_type": "metric_definition"
        }

        extraction_result = {
            "confidence": 0.92,
            "extracted_rules": [
                {
                    "business_term": "revenue",
                    "operation": "exclude",
                    "conditions": [
                        {"field": "orders.status", "operator": "equals", "value": "cancelled"}
                    ],
                    "scope": "global",
                    "affected_tables": ["orders"],
                    "affected_columns": ["orders.status"]
                }
            ]
        }

        result = pipeline.validate_suggestion(
            classification_result,
            extraction_result,
            "Exclude cancelled orders from revenue"
        )

        assert result["overall_status"] == "APPROVED"
        assert result["mandatory_review_required"] is False
        assert result["routing_recommendation"] == "STANDARD"

    def test_validation_pipeline_schema_fail_blocks(self, sample_schema):
        """Test that schema FAIL blocks suggestion."""
        pipeline = ValidationPipeline()
        pipeline.domain_schema = sample_schema
        pipeline.schema_validator = SchemaValidationService(sample_schema)
        pipeline.glossary = ["revenue"]

        classification_result = {"confidence": 0.95}
        extraction_result = {
            "confidence": 0.92,
            "extracted_rules": [
                {
                    # Missing mandatory business_term - will trigger FAIL
                    "operation": "exclude",
                    "conditions": [
                        {"field": "orders.status", "operator": "equals", "value": "cancelled"}
                    ]
                }
            ]
        }

        result = pipeline.validate_suggestion(
            classification_result,
            extraction_result,
            "test"
        )

        # Schema FAIL (missing mandatory field) should block with mandatory review
        assert result["mandatory_review_required"] is True
        assert any("Schema validation FAILED" in reason for reason in result["mandatory_review_reasons"])
        assert result["overall_status"] == "BLOCKED"

    def test_validation_pipeline_low_classification_confidence(self, sample_schema):
        """Test that low classification confidence requires review."""
        pipeline = ValidationPipeline()
        pipeline.domain_schema = sample_schema
        pipeline.schema_validator = SchemaValidationService(sample_schema)
        pipeline.glossary = ["revenue"]

        classification_result = {"confidence": 0.50}  # Below 70% threshold
        extraction_result = {
            "confidence": 0.92,
            "extracted_rules": [
                {
                    "business_term": "revenue",
                    "operation": "exclude",
                    "conditions": [
                        {"field": "orders.status", "operator": "equals", "value": "cancelled"}
                    ]
                }
            ]
        }

        result = pipeline.validate_suggestion(
            classification_result,
            extraction_result,
            "test"
        )

        assert result["mandatory_review_required"] is True
        assert result["routing_recommendation"] == "REVIEWER"

    def test_validation_pipeline_no_rules_extracted(self, sample_schema):
        """Test handling when no rules extracted."""
        pipeline = ValidationPipeline()
        pipeline.domain_schema = sample_schema
        pipeline.schema_validator = SchemaValidationService(sample_schema)

        classification_result = {"confidence": 0.95}
        extraction_result = {
            "confidence": 0.30,
            "extracted_rules": []
        }

        result = pipeline.validate_suggestion(
            classification_result,
            extraction_result,
            "ambiguous feedback"
        )

        assert result["overall_status"] == "BLOCKED"
        assert result["mandatory_review_required"] is True
        assert result["routing_recommendation"] == "CLARIFICATION"

    def test_validation_report_generation(self, sample_schema):
        """Test generation of human-readable validation report."""
        pipeline = ValidationPipeline()
        pipeline.domain_schema = sample_schema
        pipeline.schema_validator = SchemaValidationService(sample_schema)
        pipeline.glossary = ["revenue"]

        classification_result = {"confidence": 0.95}
        extraction_result = {
            "confidence": 0.92,
            "extracted_rules": [
                {
                    "business_term": "revenue",
                    "operation": "exclude",
                    "conditions": [
                        {"field": "orders.status", "operator": "equals", "value": "cancelled"}
                    ]
                }
            ]
        }

        result = pipeline.validate_suggestion(
            classification_result,
            extraction_result,
            "test"
        )

        report = pipeline.generate_validation_report(result)

        assert "SCHEMA VALIDATION REPORT" in report
        assert "Overall Status" in report
        assert result["overall_status"] in report


def test_validate_extracted_rules_multiple(sample_schema):
    """Test validation of multiple rules."""
    rules = [
        {
            "business_term": "revenue",
            "operation": "exclude",
            "conditions": [
                {"field": "orders.status", "operator": "equals", "value": "cancelled"}
            ]
        },
        {
            "business_term": "order",
            "operation": "include",
            "conditions": [
                {"field": "orders.amount", "operator": "greater_than", "value": 100}
            ]
        }
    ]

    results = validate_extracted_rules(rules, sample_schema)

    assert len(results) == 2
    assert all("status" in r for r in results)
    assert all("coverage" in r for r in results)
