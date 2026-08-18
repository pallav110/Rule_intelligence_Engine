from dataclasses import dataclass


@dataclass
class ValidationError:
    field: str
    reason: str


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError]


class SchemaValidator:
    def validate(
        self,
        references: list[str],
        schema: dict,
    ) -> ValidationResult:
        errors = []

        for reference in references:
            if "." not in reference:
                errors.append(
                    ValidationError(
                        field=reference,
                        reason="malformed_field_reference",
                    )
                )
                continue

            table, column = reference.split(".", 1)

            table_definition = schema.get("tables", {}).get(table)

            if table_definition is None:
                errors.append(
                    ValidationError(
                        field=reference,
                        reason="table_not_found",
                    )
                )
                continue

            columns = table_definition.get("columns", {})

            if column not in columns:
                errors.append(
                    ValidationError(
                        field=reference,
                        reason="column_not_found",
                    )
                )

        return ValidationResult(
            valid=not errors,
            errors=errors,
        )