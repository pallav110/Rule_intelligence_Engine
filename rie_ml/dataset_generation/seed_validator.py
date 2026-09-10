"""Seed data validator for validating seed.jsonl before generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    record_id: str | None = None


class SeedValidator:
    """Validates seed data against domain pack schema and taxonomy."""
    
    def __init__(self, domain_pack_path: Path):
        self.domain_pack_path = domain_pack_path
        self.taxonomy = self._load_taxonomy()
        self.schema = self._load_schema()
        self.schema_fields = self._build_schema_fields()
    
    def _load_json(self, path: Path) -> dict[str, Any]:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    
    def _load_taxonomy(self) -> dict[str, Any]:
        return self._load_json(self.domain_pack_path / "taxonomy" / "labels.json")
    
    def _load_schema(self) -> dict[str, Any]:
        return self._load_json(self.domain_pack_path / "schema" / "schema.json")
    
    def _build_schema_fields(self) -> set[str]:
        """Build set of valid table.column fields."""
        fields: set[str] = set()
        for table, meta in self.schema.get("tables", {}).items():
            for column in meta.get("columns", {}):
                fields.add(f"{table}.{column}")
        return fields
    
    def _validate_taxonomy_value(
        self,
        value: str | None,
        allowed: set[str],
        field_name: str,
        ctx: str,
        errors: list[str]
    ) -> None:
        """Validate that a value is in the allowed taxonomy set."""
        if value is None:
            return
        if value not in allowed:
            errors.append(f"{ctx}: invalid {field_name} '{value}' (not in taxonomy)")
    
    def _validate_rule_fields(
        self,
        rule: dict[str, Any],
        ctx: str,
        errors: list[str],
        warnings: list[str],
        allow_invalid: bool = False
    ) -> None:
        """Validate rule field references against schema."""
        for cond in rule.get("conditions", []):
            field = cond.get("field")
            if not field:
                errors.append(f"{ctx}: condition missing field")
                continue
            if field not in self.schema_fields:
                msg = f"{ctx}: unknown schema field '{field}'"
                if allow_invalid:
                    warnings.append(msg + " (allowed: schema_validation_expected=fail)")
                else:
                    errors.append(msg)
        
        for col in rule.get("affected_entities", {}).get("columns", []):
            if "." in col and col not in self.schema_fields:
                msg = f"{ctx}: unknown affected column '{col}'"
                if allow_invalid:
                    warnings.append(msg)
                else:
                    errors.append(msg)
    
    def validate_record(self, record: dict[str, Any]) -> ValidationResult:
        """Validate a single seed record."""
        errors: list[str] = []
        warnings: list[str] = []
        
        ctx = record.get("feedback_id", "<unknown>")
        allow_invalid = record.get("schema_validation_expected") == "fail"
        
        # Check required fields
        required_fields = [
            "feedback_id", "domain", "domain_pack_version", "rule_family_id",
            "feedback_text", "feedback_type", "is_actionable", "requires_clarification",
            "annotation_version", "source"
        ]
        for field in required_fields:
            if field not in record:
                errors.append(f"{ctx}: missing required field '{field}'")
        
        # Validate JSONL validity (basic structure)
        if not isinstance(record, dict):
            errors.append(f"{ctx}: record is not a JSON object")
            return ValidationResult(False, errors, warnings, ctx)
        
        # Validate feedback_type
        # Allow "irrelevant_spam" as a special pre-filter class even though
        # it's not in the 5-class classifier taxonomy (per §8.3.2)
        allowed_feedback_types = set(self.taxonomy["feedback_types"]) | {"irrelevant_spam"}
        self._validate_taxonomy_value(
            record.get("feedback_type"),
            allowed_feedback_types,
            "feedback_type",
            ctx,
            errors
        )
        
        # Validate rule_category if present
        if record.get("rule_category") is not None:
            self._validate_taxonomy_value(
                record.get("rule_category"),
                set(self.taxonomy["rule_categories"]),
                "rule_category",
                ctx,
                errors
            )
        
        # Validate consistency between is_actionable, requires_clarification, and rules
        if record.get("requires_clarification") and record.get("rules"):
            errors.append(f"{ctx}: clarification record should have empty rules[]")

        if record.get("is_actionable") and not record.get("requires_clarification"):
            if record.get("feedback_type") == "business_rule" and not record.get("rules"):
                errors.append(f"{ctx}: actionable business_rule must have rules[]")
        
        # Validate rules
        for j, rule in enumerate(record.get("rules", [])):
            rule_ctx = f"{ctx}.rules[{j}]"
            
            # Validate operation
            self._validate_taxonomy_value(
                rule.get("operation"),
                set(self.taxonomy["operations"]),
                "operation",
                rule_ctx,
                errors
            )
            
            # Validate condition operators
            for cond in rule.get("conditions", []):
                self._validate_taxonomy_value(
                    cond.get("operator"),
                    set(self.taxonomy["operators"]),
                    "operator",
                    rule_ctx,
                    errors
                )
            
            # Validate field references
            self._validate_rule_fields(rule, rule_ctx, errors, warnings, allow_invalid=allow_invalid)
        
        # Validate schema_context tables and columns
        schema_tables = {f.split(".")[0] for f in self.schema_fields}
        for table in record.get("schema_context", {}).get("available_tables", []):
            if table not in schema_tables:
                warnings.append(f"{ctx}: schema_context table '{table}' not in pack schema")
        
        for col in record.get("schema_context", {}).get("available_columns", []):
            if col not in self.schema_fields:
                warnings.append(f"{ctx}: schema_context column '{col}' not in pack schema")
        
        # Validate consistency between schema_context and rules
        rule_tables = set()
        rule_columns = set()
        for rule in record.get("rules", []):
            for cond in rule.get("conditions", []):
                field = cond.get("field", "")
                if "." in field:
                    rule_tables.add(field.split(".")[0])
                    rule_columns.add(field)
            for col in rule.get("affected_entities", {}).get("columns", []):
                if "." in col:
                    rule_columns.add(col)
        
        schema_context_tables = set(record.get("schema_context", {}).get("available_tables", []))
        schema_context_columns = set(record.get("schema_context", {}).get("available_columns", []))
        
        if rule_tables and not rule_tables.issubset(schema_context_tables):
            missing = rule_tables - schema_context_tables
            warnings.append(f"{ctx}: rule tables {missing} not in schema_context.available_tables")
        
        if rule_columns and not rule_columns.issubset(schema_context_columns):
            missing = rule_columns - schema_context_columns
            warnings.append(f"{ctx}: rule columns {missing} not in schema_context.available_columns")
        
        return ValidationResult(len(errors) == 0, errors, warnings, ctx)
    
    def validate_seed_file(self, seed_path: Path) -> dict[str, Any]:
        """Validate entire seed.jsonl file."""
        all_errors: list[str] = []
        all_warnings: list[str] = []
        valid_records: list[dict[str, Any]] = []
        invalid_records: list[dict[str, Any]] = []
        feedback_ids: set[str] = set()
        rule_family_ids: set[str] = set()
        duplicate_feedback_ids: list[str] = []
        
        with seed_path.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    all_errors.append(f"seed.jsonl:{line_no}: invalid JSON - {e}")
                    continue
                
                fid = record.get("feedback_id")
                if not fid:
                    all_errors.append(f"seed.jsonl:{line_no}: missing feedback_id")
                    invalid_records.append(record)
                    continue
                
                if fid in feedback_ids:
                    duplicate_feedback_ids.append(fid)
                    all_errors.append(f"seed.jsonl:{line_no}: duplicate feedback_id '{fid}'")
                else:
                    feedback_ids.add(fid)
                
                rfid = record.get("rule_family_id")
                if rfid:
                    rule_family_ids.add(rfid)
                
                result = self.validate_record(record)
                all_errors.extend([f"{fid}: {e}" for e in result.errors])
                all_warnings.extend([f"{fid}: {w}" for w in result.warnings])
                
                if result.is_valid:
                    valid_records.append(record)
                else:
                    invalid_records.append(record)
        
        return {
            "is_valid": len(all_errors) == 0,
            "total_records": len(valid_records) + len(invalid_records),
            "valid_records": len(valid_records),
            "invalid_records": len(invalid_records),
            "unique_feedback_ids": len(feedback_ids),
            "unique_rule_family_ids": len(rule_family_ids),
            "duplicate_feedback_ids": duplicate_feedback_ids,
            "errors": all_errors,
            "warnings": all_warnings,
            "valid_records_data": valid_records,
            "invalid_records_data": invalid_records,
        }
