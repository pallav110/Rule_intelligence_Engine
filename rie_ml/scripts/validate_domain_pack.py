#!/usr/bin/env python3
"""Validate an RIE domain pack: schema refs, taxonomy labels, and unique IDs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent / "domain-packs" / "ecommerce"


def load_json(path: Path) -> dict | list:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_schema_fields(schema: dict) -> set[str]:
    fields: set[str] = set()
    for table, meta in schema.get("tables", {}).items():
        for column in meta.get("columns", {}):
            fields.add(f"{table}.{column}")
    return fields


def validate_taxonomy_value(value: str | None, allowed: set[str], field: str, ctx: str, errors: list[str]) -> None:
    if value is None:
        return
    if value not in allowed:
        errors.append(f"{ctx}: invalid {field} '{value}' (not in taxonomy)")


def validate_rule_fields(rule: dict, schema_fields: set[str], ctx: str, errors: list[str], warnings: list[str], allow_invalid: bool = False) -> None:
    for cond in rule.get("conditions", []):
        field = cond.get("field")
        if not field:
            errors.append(f"{ctx}: condition missing field")
            continue
        if field not in schema_fields:
            msg = f"{ctx}: unknown schema field '{field}'"
            if allow_invalid:
                warnings.append(msg + " (allowed: schema_validation_expected=fail)")
            else:
                errors.append(msg)

    for col in rule.get("affected_entities", {}).get("columns", []):
        if "." in col and col not in schema_fields:
            msg = f"{ctx}: unknown affected column '{col}'"
            if allow_invalid:
                warnings.append(msg)
            else:
                errors.append(msg)


def validate_rules_file(rules: list, schema_fields: set[str], taxonomy: dict, file_name: str, errors: list[str], warnings: list[str]) -> None:
    seen_ids: set[str] = set()
    for i, rule in enumerate(rules):
        ctx = f"{file_name}[{i}]"
        rid = rule.get("rule_id")
        if not rid:
            errors.append(f"{ctx}: missing rule_id")
        elif rid in seen_ids:
            errors.append(f"{ctx}: duplicate rule_id '{rid}'")
        else:
            seen_ids.add(rid)

        validate_taxonomy_value(rule.get("rule_category"), set(taxonomy["rule_categories"]), "rule_category", ctx, errors)
        validate_taxonomy_value(rule.get("operation"), set(taxonomy["operations"]), "operation", ctx, errors)
        for cond in rule.get("conditions", []):
            validate_taxonomy_value(cond.get("operator"), set(taxonomy["operators"]), "operator", ctx, errors)
        validate_rule_fields(rule, schema_fields, ctx, errors, warnings)


def validate_feedback_record(record: dict, schema_fields: set[str], taxonomy: dict, errors: list[str], warnings: list[str]) -> None:
    ctx = record.get("feedback_id", "<unknown>")
    allow_invalid = record.get("schema_validation_expected") == "fail"

    validate_taxonomy_value(record.get("feedback_type"), set(taxonomy["feedback_types"]), "feedback_type", ctx, errors)
    if record.get("rule_category") is not None:
        validate_taxonomy_value(record.get("rule_category"), set(taxonomy["rule_categories"]), "rule_category", ctx, errors)

    if record.get("requires_clarification") and record.get("rules"):
        errors.append(f"{ctx}: clarification record should have empty rules[]")

    if record.get("is_actionable") and not record.get("requires_clarification") and record.get("feedback_type") == "business_rule_correction":
        if not record.get("rules"):
            errors.append(f"{ctx}: actionable business_rule_correction must have rules[]")

    for j, rule in enumerate(record.get("rules", [])):
        rule_ctx = f"{ctx}.rules[{j}]"
        validate_taxonomy_value(rule.get("operation"), set(taxonomy["operations"]), "operation", rule_ctx, errors)
        for cond in rule.get("conditions", []):
            validate_taxonomy_value(cond.get("operator"), set(taxonomy["operators"]), "operator", rule_ctx, errors)
        validate_rule_fields(rule, schema_fields, rule_ctx, errors, warnings, allow_invalid=allow_invalid)

    for table in record.get("schema_context", {}).get("available_tables", []):
        if table not in {t for t in schema_fields} and table not in {f.split(".")[0] for f in schema_fields}:
            # tables are table names without dot
            pass
    schema_tables = {f.split(".")[0] for f in schema_fields}
    for table in record.get("schema_context", {}).get("available_tables", []):
        if table not in schema_tables:
            warnings.append(f"{ctx}: schema_context table '{table}' not in pack schema")

    for col in record.get("schema_context", {}).get("available_columns", []):
        if col not in schema_fields:
            warnings.append(f"{ctx}: schema_context column '{col}' not in pack schema")


def validate_pack(pack_root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    taxonomy = load_json(pack_root / "taxonomy" / "labels.json")
    schema = load_json(pack_root / "schema" / "schema.json")
    schema_fields = build_schema_fields(schema)

    active = load_json(pack_root / "rules" / "active_rules.json")
    conflicting = load_json(pack_root / "rules" / "conflicting_rules.json")
    validate_rules_file(active, schema_fields, taxonomy, "active_rules.json", errors, warnings)
    validate_rules_file(conflicting, schema_fields, taxonomy, "conflicting_rules.json", errors, warnings)

    feedback_ids: set[str] = set()
    seed_path = pack_root / "feedback" / "seed.jsonl"
    with seed_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            fid = record.get("feedback_id")
            if not fid:
                errors.append(f"seed.jsonl:{line_no}: missing feedback_id")
            elif fid in feedback_ids:
                errors.append(f"seed.jsonl:{line_no}: duplicate feedback_id '{fid}'")
            else:
                feedback_ids.add(fid)
            validate_feedback_record(record, schema_fields, taxonomy, errors, warnings)

    return errors, warnings


def main() -> int:
    pack_root = Path(sys.argv[1]) if len(sys.argv) > 1 else PACK_ROOT
    if not pack_root.exists():
        print(f"ERROR: pack not found at {pack_root}")
        return 1

    errors, warnings = validate_pack(pack_root)

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")

    if errors:
        print(f"\nValidation FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1

    print(f"Validation PASSED: 0 errors, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
