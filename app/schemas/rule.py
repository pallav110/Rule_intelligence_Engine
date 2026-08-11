from typing import Any

from pydantic import BaseModel


class RuleCondition(BaseModel):
    field: str
    operator: str
    value: Any | None = None
    scope: str | None = None
    time_window: str | None = None

class Rule(BaseModel):
    rule_id: str
    rule_category: str
    operation: str
    conditions: list[RuleCondition]
    affected_tables: list[str]
    affected_columns: list[str]