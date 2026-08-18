from app.schemas.rule import Rule

class CanonicalRuleService:
    def build(self, rule_data: dict) -> Rule:
        return Rule.model_validate(rule_data)