from app.services.schema_validator import SchemaValidator


schema = {
    "tables": {
        "orders": {
            "columns": {
                "status": {},
                "customer_id": {},
            }
        }
    }
}


def test_valid_table_and_column():
    result = SchemaValidator().validate(
        ["orders.status"],
        schema,
    )

    assert result.valid is True
    assert result.errors == []


def test_invalid_table():
    result = SchemaValidator().validate(
        ["customers.status"],
        schema,
    )

    assert result.valid is False
    assert result.errors[0].reason == "table_not_found"


def test_invalid_column():
    result = SchemaValidator().validate(
        ["orders.customer_age"],
        schema,
    )

    assert result.valid is False
    assert result.errors[0].reason == "column_not_found"


def test_malformed_reference():
    result = SchemaValidator().validate(
        ["orders"],
        schema,
    )

    assert result.valid is False
    assert result.errors[0].reason == "malformed_field_reference"