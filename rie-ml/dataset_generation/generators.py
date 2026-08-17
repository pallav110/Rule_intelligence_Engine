"""Dataset generators for synthetic feedback generation."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from copy import deepcopy

from .config import GenerationConfig


@dataclass
class GenerationMetadata:
    """Metadata for generated records."""
    source_seed_id: str | None = None
    rule_family_id: str | None = None
    generation_method: str = ""
    dataset_version: str = ""
    annotation_version: str = ""
    generated_at: str = ""


class FeedbackGenerator:
    """Base class for feedback generators."""
    
    def __init__(self, config: GenerationConfig, seed_records: list[dict[str, Any]]):
        self.config = config
        self.seed_records = seed_records
        self.domain_pack = self._load_domain_pack()
        self.taxonomy = self.domain_pack["taxonomy"]
        self.schema = self.domain_pack["schema"]
        self.schema_fields = self._build_schema_fields()
        self._counter = 0
    
    def _load_domain_pack(self) -> dict[str, Any]:
        """Load domain pack data."""
        pack_path = self.config.domain_pack_path
        with (pack_path / "taxonomy" / "labels.json").open(encoding="utf-8") as f:
            taxonomy = json.load(f)
        with (pack_path / "schema" / "schema.json").open(encoding="utf-8") as f:
            schema = json.load(f)
        return {"taxonomy": taxonomy, "schema": schema}
    
    def _build_schema_fields(self) -> set[str]:
        """Build set of valid table.column fields."""
        fields: set[str] = set()
        for table, meta in self.schema.get("tables", {}).items():
            for column in meta.get("columns", {}):
                fields.add(f"{table}.{column}")
        return fields
    
    def _generate_feedback_id(self) -> str:
        """Generate unique feedback ID."""
        self._counter += 1
        return f"EC_GEN{self._counter:04d}"
    
    def _create_metadata(self, source_seed_id: str, rule_family_id: str, method: str) -> GenerationMetadata:
        """Create generation metadata."""
        from datetime import datetime
        return GenerationMetadata(
            source_seed_id=source_seed_id,
            rule_family_id=rule_family_id,
            generation_method=method,
            dataset_version=self.config.dataset_version,
            annotation_version=self.config.annotation_version,
            generated_at=datetime.utcnow().isoformat() + "Z",
        )
    
    def _copy_record_template(self, seed: dict[str, Any]) -> dict[str, Any]:
        """Copy seed record as template for generation."""
        return {
            "feedback_id": self._generate_feedback_id(),
            "domain": seed.get("domain", self.config.domain_pack_id),
            "domain_pack_version": self.config.domain_pack_version,
            "rule_family_id": seed.get("rule_family_id"),
            "feedback_text": "",
            "feedback_type": seed.get("feedback_type"),
            "rule_category": seed.get("rule_category"),
            "is_actionable": seed.get("is_actionable"),
            "requires_clarification": seed.get("requires_clarification", False),
            "schema_context": deepcopy(seed.get("schema_context", {})),
            "rules": deepcopy(seed.get("rules", [])),
            "annotation_version": self.config.annotation_version,
            "source": "programmatic",
        }


class ParaphraseGenerator(FeedbackGenerator):
    """Generate paraphrases of existing feedback while preserving semantics."""
    
    # Paraphrase templates for different rule patterns
    PARAPHRASE_TEMPLATES = {
        "exclude": [
            "{term} should exclude {condition}.",
            "Exclude {condition} from {term}.",
            "{term} must not include {condition}.",
            "Don't count {condition} in {term}.",
            "{condition} should be excluded from {term}.",
            "Remove {condition} when calculating {term}.",
        ],
        "include": [
            "{term} should include {condition}.",
            "Include {condition} in {term}.",
            "{term} must include {condition}.",
            "Add {condition} to {term}.",
            "{condition} should be part of {term}.",
        ],
        "filter_rule": [
            "{term} should only include {condition}.",
            "Only {condition} should count for {term}.",
            "{term} is for {condition} only.",
            "Restrict {term} to {condition}.",
        ],
    }
    
    def generate(self, seed: dict[str, Any], count: int = 3) -> list[dict[str, Any]]:
        """Generate paraphrases of a seed record."""
        if not seed.get("rules"):
            return []
        
        generated = []
        for _ in range(count):
            record = self._copy_record_template(seed)
            
            # Extract rule components for paraphrasing
            rule = seed["rules"][0] if seed["rules"] else {}
            operation = rule.get("operation", "")
            business_term = rule.get("business_term", "")
            
            # Build condition text
            condition_parts = []
            for cond in rule.get("conditions", []):
                field = cond.get("field", "")
                value = cond.get("value", "")
                operator = cond.get("operator", "")
                
                # Simplify field name for readability
                field_simple = field.split(".")[-1] if "." in field else field
                
                if operator == "equals":
                    condition_parts.append(f"{field_simple} = {value}")
                elif operator == "greater_than":
                    condition_parts.append(f"{field_simple} > {value}")
                elif operator == "is_not_null":
                    condition_parts.append(f"{field_simple} is present")
                else:
                    condition_parts.append(f"{field_simple} {operator} {value}")
            
            condition_text = " and ".join(condition_parts) if condition_parts else ""
            
            # Select appropriate template
            templates = self.PARAPHRASE_TEMPLATES.get(operation, self.PARAPHRASE_TEMPLATES["exclude"])
            template = random.choice(templates)
            
            # Generate paraphrase
            feedback_text = template.format(
                term=business_term.replace("_", " "),
                condition=condition_text
            )
            
            record["feedback_text"] = feedback_text
            record["source_seed_id"] = seed.get("feedback_id")
            generated.append(record)
        
        return generated


class ConversationalGenerator(FeedbackGenerator):
    """Generate natural conversational feedback from business rules."""
    
    CONVERSATIONAL_TEMPLATES = [
        "Can we make sure {rule}?",
        "I think {rule}.",
        "Please ensure that {rule}.",
        "We need to {rule}.",
        "It would be great if {rule}.",
        "Can you please {rule}?",
        "Hey, can we {rule}?",
        "I was wondering if we could {rule}.",
    ]
    
    def generate(self, seed: dict[str, Any], count: int = 2) -> list[dict[str, Any]]:
        """Generate conversational versions of seed feedback."""
        if not seed.get("rules"):
            return []
        
        generated = []
        original_text = seed.get("feedback_text", "")
        
        for _ in range(count):
            record = self._copy_record_template(seed)
            
            # Convert original to more conversational form
            if original_text.endswith("."):
                rule_part = original_text[:-1].lower()
            else:
                rule_part = original_text.lower()
            
            # Remove "should" for more natural conversation
            if rule_part.startswith("revenue should"):
                rule_part = rule_part.replace("revenue should", "revenue")
            
            template = random.choice(self.CONVERSATIONAL_TEMPLATES)
            feedback_text = template.format(rule=rule_part)
            
            record["feedback_text"] = feedback_text
            record["source_seed_id"] = seed.get("feedback_id")
            generated.append(record)
        
        return generated


class HinglishGenerator(FeedbackGenerator):
    """Generate Hinglish (Hindi-English mixed) feedback examples."""
    
    HINGLISH_TEMPLATES = [
        "{term} mein {condition} include mat karo.",
        "{term} se {condition} hatao yaar.",
        "Please {term} mein {condition} add karo.",
        "{term} calculation mein {condition} exclude kar do.",
        "Yaar, {term} ko {condition} ke liye fix karo.",
    ]
    
    HINGLISH_REPLACEMENTS = {
        "revenue": "revenue",
        "exclude": "include mat karo",
        "include": "add karo",
        "cancelled": "cancelled",
        "test": "test",
        "orders": "orders",
    }
    
    def generate(self, seed: dict[str, Any], count: int = 1) -> list[dict[str, Any]]:
        """Generate Hinglish versions of seed feedback."""
        if not seed.get("rules"):
            return []
        
        generated = []
        
        for _ in range(count):
            record = self._copy_record_template(seed)
            
            rule = seed["rules"][0] if seed["rules"] else {}
            business_term = rule.get("business_term", "revenue")
            operation = rule.get("operation", "exclude")
            
            # Build condition in Hinglish
            condition_parts = []
            for cond in rule.get("conditions", []):
                field = cond.get("field", "")
                value = cond.get("value", "")
                field_simple = field.split(".")[-1] if "." in field else field
                condition_parts.append(f"{field_simple} {value}")
            
            condition_text = " and ".join(condition_parts) if condition_parts else ""
            
            # Select template
            template = random.choice(self.HINGLISH_TEMPLATES)
            
            # Generate Hinglish feedback
            feedback_text = template.format(
                term=business_term,
                condition=condition_text
            )
            
            record["feedback_text"] = feedback_text
            record["source_seed_id"] = seed.get("feedback_id")
            generated.append(record)
        
        return generated


class MultiRuleGenerator(FeedbackGenerator):
    """Generate feedback containing multiple independent rules."""
    
    def generate(self, seeds: list[dict[str, Any]], count: int = 1) -> list[dict[str, Any]]:
        """Generate multi-rule feedback by combining compatible seeds."""
        generated = []
        
        # Filter seeds with rules
        actionable_seeds = [s for s in seeds if s.get("rules") and s.get("is_actionable")]
        
        if len(actionable_seeds) < 2:
            return generated
        
        for _ in range(count):
            # Select 2-3 random seeds
            num_rules = random.randint(2, min(3, len(actionable_seeds)))
            selected = random.sample(actionable_seeds, num_rules)
            
            # Create combined record
            base = selected[0]
            record = self._copy_record_template(base)
            
            # Combine feedback texts
            texts = [s.get("feedback_text", "") for s in selected]
            feedback_text = " and ".join(texts)
            
            # Combine rules
            all_rules = []
            all_rule_family_ids = []
            for s in selected:
                all_rules.extend(s.get("rules", []))
                all_rule_family_ids.append(s.get("rule_family_id", ""))
            
            record["feedback_text"] = feedback_text
            record["rules"] = all_rules
            record["rule_family_id"] = f"multi_{'_'.join(all_rule_family_ids[:2])}"
            record["source_seed_id"] = ",".join([s.get("feedback_id", "") for s in selected])
            
            # Combine schema contexts
            all_tables = set()
            all_columns = set()
            for s in selected:
                all_tables.update(s.get("schema_context", {}).get("available_tables", []))
                all_columns.update(s.get("schema_context", {}).get("available_columns", []))
            
            record["schema_context"] = {
                "available_tables": list(all_tables),
                "available_columns": list(all_columns),
            }
            
            generated.append(record)
        
        return generated


class AmbiguousGenerator(FeedbackGenerator):
    """Generate ambiguous feedback requiring clarification."""
    
    AMBIGUOUS_TEMPLATES = [
        "Fix {term}.",
        "There's an issue with {term}.",
        "{term} calculation seems wrong.",
        "Please check {term}.",
        "Something's off with {term}.",
        "Can you look at {term}?",
    ]
    
    def generate(self, seeds: list[dict[str, Any]], count: int = 3) -> list[dict[str, Any]]:
        """Generate ambiguous feedback from business terms."""
        generated = []
        
        # Extract business terms from seeds
        business_terms = set()
        for seed in seeds:
            for rule in seed.get("rules", []):
                if rule.get("business_term"):
                    business_terms.add(rule.get("business_term"))
        
        if not business_terms:
            return generated
        
        for _ in range(count):
            term = random.choice(list(business_terms))
            
            record = {
                "feedback_id": self._generate_feedback_id(),
                "domain": self.config.domain_pack_id,
                "domain_pack_version": self.config.domain_pack_version,
                "rule_family_id": f"ambiguous_{term}_{random.randint(1000, 9999)}",
                "feedback_text": "",
                "feedback_type": "unclear_feedback",
                "rule_category": None,
                "is_actionable": False,
                "requires_clarification": True,
                "schema_context": {"available_tables": [], "available_columns": []},
                "rules": [],
                "annotation_version": self.config.annotation_version,
                "source": "programmatic",
            }
            
            template = random.choice(self.AMBIGUOUS_TEMPLATES)
            record["feedback_text"] = template.format(term=term.replace("_", " "))
            
            generated.append(record)
        
        return generated


class ConflictGenerator(FeedbackGenerator):
    """Generate conflicting rule pairs."""
    
    def generate(self, seeds: list[dict[str, Any]], count: int = 2) -> list[dict[str, Any]]:
        """Generate conflicting rule pairs by modifying threshold values."""
        generated = []
        
        # Find seeds with numeric thresholds
        threshold_seeds = []
        for seed in seeds:
            for rule in seed.get("rules", []):
                if rule.get("threshold") is not None:
                    threshold_seeds.append(seed)
                    break
        
        if len(threshold_seeds) < 1:
            return generated
        
        for _ in range(count):
            seed = random.choice(threshold_seeds)
            rule = seed["rules"][0] if seed["rules"] else {}
            
            # Create conflicting version with different threshold
            record = self._copy_record_template(seed)
            
            original_threshold = rule.get("threshold", 0)
            # Create conflict by changing threshold significantly
            if isinstance(original_threshold, (int, float)):
                new_threshold = original_threshold * 0.5 if original_threshold > 100 else original_threshold * 2
            else:
                new_threshold = 500  # default conflict value
            
            # Update rule with conflicting threshold
            new_rules = deepcopy(seed.get("rules", []))
            for r in new_rules:
                if r.get("threshold") is not None:
                    r["threshold"] = new_threshold
                    # Update conditions if they reference the threshold
                    for cond in r.get("conditions", []):
                        if cond.get("value") == original_threshold:
                            cond["value"] = new_threshold
            
            record["rules"] = new_rules
            record["rule_family_id"] = f"{seed.get('rule_family_id')}_conflict"
            
            # Generate conflicting feedback text
            original_text = seed.get("feedback_text", "")
            if str(original_threshold) in original_text:
                feedback_text = original_text.replace(str(original_threshold), str(new_threshold))
            else:
                feedback_text = f"{original_text} (conflict: use {new_threshold} instead)"
            
            record["feedback_text"] = feedback_text
            record["source_seed_id"] = seed.get("feedback_id")
            
            generated.append(record)
        
        return generated


class NonRuleGenerator(FeedbackGenerator):
    """Generate non-rule feedback (UI/UX complaints, etc.)."""
    
    NON_RULE_TEMPLATES = [
        "The checkout button overlaps the footer on mobile.",
        "The dashboard loads too slowly.",
        "Can we change the color of the submit button?",
        "The font size is too small on the reports page.",
        "Navigation menu is confusing on tablet.",
        "The export feature doesn't work for PDFs.",
        "The search bar is hard to find.",
        "Page layout breaks on Safari browser.",
    ]
    
    def generate(self, count: int = 5) -> list[dict[str, Any]]:
        """Generate non-rule feedback examples."""
        generated = []
        
        for _ in range(count):
            record = {
                "feedback_id": self._generate_feedback_id(),
                "domain": self.config.domain_pack_id,
                "domain_pack_version": self.config.domain_pack_version,
                "rule_family_id": f"nonrule_{random.randint(1000, 9999)}",
                "feedback_text": random.choice(self.NON_RULE_TEMPLATES),
                "feedback_type": "non_rule_feedback",
                "rule_category": None,
                "is_actionable": False,
                "requires_clarification": False,
                "schema_context": {"available_tables": [], "available_columns": []},
                "rules": [],
                "annotation_version": self.config.annotation_version,
                "source": "programmatic",
            }
            generated.append(record)
        
        return generated


class SpamGenerator(FeedbackGenerator):
    """Generate spam/irrelevant feedback."""
    
    SPAM_TEMPLATES = [
        "Buy cheap meds now!!! Visit scam-site.com",
        "Click here for free iPhone!!!",
        "You won lottery!!! Send bank details to claim.",
        "Make $10000/day from home!!! No work needed.",
        "Hot singles in your area!!! Click now!!!",
        "Free crypto giveaway!!! Send 1 BTC to get 10 back.",
        "Urgent: Your account will be deleted unless you click this link.",
        "Congratulations!!! You've been selected for a prize.",
    ]
    
    def generate(self, count: int = 5) -> list[dict[str, Any]]:
        """Generate spam feedback examples."""
        generated = []
        
        for _ in range(count):
            record = {
                "feedback_id": self._generate_feedback_id(),
                "domain": self.config.domain_pack_id,
                "domain_pack_version": self.config.domain_pack_version,
                "rule_family_id": f"spam_{random.randint(1000, 9999)}",
                "feedback_text": random.choice(self.SPAM_TEMPLATES),
                "feedback_type": "irrelevant_spam",
                "rule_category": None,
                "is_actionable": False,
                "requires_clarification": False,
                "schema_context": {"available_tables": [], "available_columns": []},
                "rules": [],
                "annotation_version": self.config.annotation_version,
                "source": "programmatic",
            }
            generated.append(record)
        
        return generated


class InvalidSchemaGenerator(FeedbackGenerator):
    """Generate feedback with invalid schema references for validation testing."""
    
    INVALID_FIELDS = [
        "orders.unknown_field",
        "customers.fake_column",
        "payments.nonexistent_field",
        "products.missing_attr",
    ]
    
    def generate(self, seeds: list[dict[str, Any]], count: int = 3) -> list[dict[str, Any]]:
        """Generate feedback with invalid schema references."""
        generated = []
        
        if not seeds:
            return generated
        
        for _ in range(count):
            seed = random.choice(seeds)
            record = self._copy_record_template(seed)
            
            # Replace a valid field with an invalid one
            new_rules = deepcopy(seed.get("rules", []))
            for rule in new_rules:
                for cond in rule.get("conditions", []):
                    if cond.get("field") and "." in cond["field"]:
                        cond["field"] = random.choice(self.INVALID_FIELDS)
                        break
                for col in rule.get("affected_entities", {}).get("columns", []):
                    if "." in col:
                        rule["affected_entities"]["columns"] = [random.choice(self.INVALID_FIELDS)]
                        break
            
            record["rules"] = new_rules
            record["schema_validation_expected"] = "fail"
            record["rule_family_id"] = f"invalid_{random.randint(1000, 9999)}"
            
            # Update feedback text to reflect invalid field
            original_text = seed.get("feedback_text", "")
            invalid_field = random.choice(self.INVALID_FIELDS)
            field_simple = invalid_field.split(".")[-1]
            feedback_text = original_text.replace("cancelled", field_simple).replace("test", field_simple)
            
            record["feedback_text"] = feedback_text
            record["source_seed_id"] = seed.get("feedback_id")
            
            generated.append(record)
        
        return generated


class GenerationPipeline:
    """Main pipeline for generating all types of synthetic feedback."""
    
    def __init__(self, config: GenerationConfig, seed_records: list[dict[str, Any]]):
        self.config = config
        self.seed_records = seed_records
        
        # Set random seed for reproducibility
        random.seed(config.random_seed)
        
        # Initialize generators
        self.paraphrase_gen = ParaphraseGenerator(config, seed_records)
        self.conversational_gen = ConversationalGenerator(config, seed_records)
        self.hinglish_gen = HinglishGenerator(config, seed_records)
        self.multi_rule_gen = MultiRuleGenerator(config, seed_records)
        self.ambiguous_gen = AmbiguousGenerator(config, seed_records)
        self.conflict_gen = ConflictGenerator(config, seed_records)
        self.non_rule_gen = NonRuleGenerator(config, seed_records)
        self.spam_gen = SpamGenerator(config, seed_records)
        self.invalid_schema_gen = InvalidSchemaGenerator(config, seed_records)
    
    def generate_all(self) -> dict[str, list[dict[str, Any]]]:
        """Generate all types of synthetic feedback."""
        all_generated: dict[str, list[dict[str, Any]]] = {
            "paraphrases": [],
            "conversational": [],
            "hinglish": [],
            "multi_rule": [],
            "ambiguous": [],
            "conflicts": [],
            "non_rule": [],
            "spam": [],
            "invalid_schema": [],
        }
        
        # Generate from each seed
        for seed in self.seed_records:
            # Skip non-actionable seeds for rule-based generation
            if seed.get("is_actionable") and seed.get("rules"):
                # Paraphrases
                paraphrases = self.paraphrase_gen.generate(
                    seed, count=self.config.paraphrase_multiplier
                )
                all_generated["paraphrases"].extend(paraphrases)
                
                # Conversational
                conversational = self.conversational_gen.generate(
                    seed, count=self.config.conversational_multiplier
                )
                all_generated["conversational"].extend(conversational)
                
                # Hinglish
                hinglish = self.hinglish_gen.generate(
                    seed, count=self.config.hinglish_multiplier
                )
                all_generated["hinglish"].extend(hinglish)
        
        # Multi-rule (combines multiple seeds)
        multi_rule = self.multi_rule_gen.generate(
            self.seed_records, count=self.config.multi_rule_multiplier * 5
        )
        all_generated["multi_rule"].extend(multi_rule)
        
        # Ambiguous
        ambiguous = self.ambiguous_gen.generate(
            self.seed_records, count=self.config.target_ambiguous
        )
        all_generated["ambiguous"].extend(ambiguous)
        
        # Conflicts
        conflicts = self.conflict_gen.generate(
            self.seed_records, count=self.config.target_conflict_pairs
        )
        all_generated["conflicts"].extend(conflicts)
        
        # Non-rule
        non_rule = self.non_rule_gen.generate(count=10)
        all_generated["non_rule"].extend(non_rule)
        
        # Spam
        spam = self.spam_gen.generate(count=10)
        all_generated["spam"].extend(spam)
        
        # Invalid schema
        invalid_schema = self.invalid_schema_gen.generate(
            self.seed_records, count=5
        )
        all_generated["invalid_schema"].extend(invalid_schema)
        
        return all_generated
