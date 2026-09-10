"""Post-generation validator for validating generated synthetic data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections import Counter


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    record_id: str | None = None
    rejection_reason: str | None = None


class PostGenerationValidator:
    """Validates generated synthetic feedback records."""
    
    def __init__(self, domain_pack_path: Path, strict: bool = True):
        self.domain_pack_path = domain_pack_path
        self.strict = strict
        self.taxonomy = self._load_taxonomy()
        self.schema = self._load_schema()
        self.schema_fields = self._build_schema_fields()
        self.schema_tables = self._build_schema_tables()
    
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
    
    def _build_schema_tables(self) -> set[str]:
        """Build set of valid table names."""
        return set(self.schema.get("tables", {}).keys())
    
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
        """Validate a single generated record."""
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
        for table in record.get("schema_context", {}).get("available_tables", []):
            if table not in self.schema_tables:
                warnings.append(f"{ctx}: schema_context table '{table}' not in pack schema")
        
        for col in record.get("schema_context", {}).get("available_columns", []):
            if col not in self.schema_fields:
                warnings.append(f"{ctx}: schema_context column '{col}' not in pack schema")
        
        # Validate feedback_text is not empty
        if not record.get("feedback_text") or not record.get("feedback_text").strip():
            errors.append(f"{ctx}: feedback_text is empty")
        
        # Validate feedback_id format
        fid = record.get("feedback_id", "")
        # Don't hardcode prefix - allow different domains
        if not fid:
            errors.append(f"{ctx}: feedback_id is empty")
        
        # Validate rule_family_id format
        rfid = record.get("rule_family_id", "")
        if not rfid:
            errors.append(f"{ctx}: rule_family_id is empty")
        
        # Check for duplicate feedback_id in record structure (basic check)
        if "feedback_id" in record and record["feedback_id"] in str(record.get("rules", "")):
            warnings.append(f"{ctx}: feedback_id appears in rules (possible copy-paste error)")
        
        rejection_reason = "; ".join(errors) if errors else None
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            record_id=ctx,
            rejection_reason=rejection_reason
        )
    
    def validate_batch(
        self,
        records: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Validate a batch of generated records."""
        valid_records: list[dict[str, Any]] = []
        rejected_records: list[dict[str, Any]] = []
        all_errors: list[str] = []
        all_warnings: list[str] = []
        
        feedback_ids: set[str] = set()
        duplicate_ids: list[str] = []
        
        for record in records:
            fid = record.get("feedback_id")
            if fid in feedback_ids:
                duplicate_ids.append(fid)
                all_errors.append(f"duplicate feedback_id '{fid}'")
            else:
                feedback_ids.add(fid)
            
            result = self.validate_record(record)
            all_errors.extend([f"{fid}: {e}" for e in result.errors])
            all_warnings.extend([f"{fid}: {w}" for w in result.warnings])
            
            if result.is_valid:
                valid_records.append(record)
            else:
                rejected_records.append({
                    **record,
                    "_rejection_reason": result.rejection_reason,
                    "_validation_errors": result.errors,
                    "_validation_warnings": result.warnings,
                })
        
        return {
            "total_records": len(records),
            "valid_records": len(valid_records),
            "rejected_records": len(rejected_records),
            "duplicate_ids": duplicate_ids,
            "errors": all_errors,
            "warnings": all_warnings,
            "valid_records_data": valid_records,
            "rejected_records_data": rejected_records,
        }
    
    def check_annotation_consistency(
        self,
        records: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Check for annotation consistency issues across records."""
        issues: list[str] = []
        
        # Check rule_family_id consistency
        rule_family_groups: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            rfid = record.get("rule_family_id")
            if rfid:
                if rfid not in rule_family_groups:
                    rule_family_groups[rfid] = []
                rule_family_groups[rfid].append(record)
        
        # Check that records in same rule_family have consistent structure
        for rfid, group in rule_family_groups.items():
            if len(group) > 1:
                # Skip multi-rule families from consistency checks (they combine different rule types)
                if rfid.startswith("multi_"):
                    continue
                
                # Check that all have same feedback_type
                types = set(r.get("feedback_type") for r in group)
                if len(types) > 1:
                    issues.append(f"rule_family_id '{rfid}' has mixed feedback_types: {types}")
                
                # Check that all have same rule_category
                categories = set(r.get("rule_category") for r in group)
                if len(categories) > 1:
                    issues.append(f"rule_family_id '{rfid}' has mixed rule_categories: {categories}")
                
                # Check that rules are semantically similar (basic check)
                rule_structures = []
                for r in group:
                    for rule in r.get("rules", []):
                        structure = {
                            "business_term": rule.get("business_term"),
                            "operation": rule.get("operation"),
                        }
                        rule_structures.append(str(structure))
                
                if len(set(rule_structures)) > 1:
                    issues.append(f"rule_family_id '{rfid}' has different rule structures")
        
        return {
            "consistency_issues": issues,
            "is_consistent": len(issues) == 0,
        }
