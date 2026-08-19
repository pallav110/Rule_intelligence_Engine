"""Dataset generators for synthetic feedback generation."""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from copy import deepcopy

from .config import GenerationConfig


# ---------------------------------------------------------------------------
# Domain-aware ID prefixes. Falls back to the first two letters of the
# domain_pack_id (uppercased) if the domain isn't listed here, so new domain
# packs don't silently collide on "EC_" ids.
# ---------------------------------------------------------------------------
DOMAIN_ID_PREFIXES = {
    "ecommerce": "EC",
    "customer_support": "CS",
    "saas_subscriptions": "SA",
}


@dataclass
class GenerationMetadata:
    """Metadata for generated records."""
    source_seed_id: str | None = None
    rule_family_id: str | None = None
    generation_method: str = ""
    dataset_version: str = ""
    annotation_version: str = ""
    generated_at: str = ""


# ---------------------------------------------------------------------------
# Natural-language condition phrasing.
#
# The old code built condition text as "<field> <operator> <value>", which is
# why generated feedback read like "status = cancelled" instead of the way
# your manually-written seeds actually talk ("cancelled orders", "test
# transactions"). This mirrors the phrasing patterns already present in your
# seed file (EC_FB001, EC_FB003, EC_FB010, EC_FB018, ...).
# ---------------------------------------------------------------------------
BOOLEAN_FIELD_PHRASES = {
    "is_test": "test transactions",
    "is_internal": "internal accounts",
    "is_active": "active records",
}


def _humanize(token: str) -> str:
    return token.replace("_", " ").strip()


def natural_condition_phrase(cond: dict[str, Any], table_hint: str = "") -> str:
    """Turn a single condition dict into a natural-language phrase."""
    field = cond.get("field", "") or ""
    operator = cond.get("operator", "")
    value = cond.get("value", "")
    field_simple = field.split(".")[-1] if "." in field else field
    table = field.split(".")[0] if "." in field else table_hint

    if operator == "equals":
        if isinstance(value, bool) and value is True:
            if field_simple in BOOLEAN_FIELD_PHRASES:
                return BOOLEAN_FIELD_PHRASES[field_simple]
            return f"{_humanize(field_simple.removeprefix('is_'))} records"
        if field_simple.endswith("status"):
            # e.g. orders.status = cancelled -> "cancelled orders"
            noun = _humanize(table) if table else "records"
            return f"{value} {noun}"
        return f"{_humanize(field_simple)} of {value}"

    if operator == "greater_than":
        return f"{_humanize(field_simple)} above {value}"

    if operator == "less_than":
        return f"{_humanize(field_simple)} below {value}"

    if operator == "is_not_null":
        return f"{_humanize(field_simple)} being present"

    # Fallback for any operator we haven't special-cased.
    return f"{_humanize(field_simple)} {operator} {value}"


def build_condition_text(rule: dict[str, Any]) -> str:
    """Join all conditions on a rule into one natural-language clause."""
    conditions = rule.get("conditions") or []
    if not conditions:
        return ""
    parts = [natural_condition_phrase(c) for c in conditions]
    parts = [p for p in parts if p]
    return " and ".join(parts)


def _sample_without_immediate_repeat(bank: list[str], count: int) -> list[str]:
    """Sample `count` items from `bank`.

    Uses sampling-without-replacement while the bank has enough unique
    entries; once the bank is exhausted it reshuffles and continues, but
    never places the same template twice in a row. This avoids the old
    bug where random.choice() with small template banks produced exact
    duplicate feedback_text rows within a single generation run.
    """
    if count <= 0 or not bank:
        return []
    result: list[str] = []
    pool: list[str] = []
    last = None
    while len(result) < count:
        if not pool:
            pool = bank.copy()
            random.shuffle(pool)
            if len(pool) > 1 and pool[0] == last:
                pool.append(pool.pop(0))
        item = pool.pop()
        result.append(item)
        last = item
    return result


class FeedbackGenerator:
    """Base class for feedback generators."""
    
    # Class-level shared counter to ensure unique IDs across all generators
    _shared_counter = 0

    def __init__(self, config: GenerationConfig, seed_records: list[dict[str, Any]]):
        self.config = config
        self.seed_records = seed_records
        self.domain_pack = self._load_domain_pack()
        self.taxonomy = self.domain_pack["taxonomy"]
        self.schema = self.domain_pack["schema"]
        self.schema_fields = self._build_schema_fields()
        self._id_prefix = DOMAIN_ID_PREFIXES.get(
            config.domain_pack_id, config.domain_pack_id[:2].upper() or "GN"
        )

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
        """Generate a unique, domain-aware feedback ID."""
        FeedbackGenerator._shared_counter += 1
        return f"{self._id_prefix}_GEN{FeedbackGenerator._shared_counter:04d}"

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

    def _validate_schema_refs(self, record: dict[str, Any]) -> bool:
        """Check every field referenced by the record's rules against the
        schema fields available in *that record's own* schema_context.
        Returns True if all references are valid, False otherwise.

        This wires up self.schema_fields (previously computed but never
        used) so generated records carry a real, checked
        schema_validation_expected flag instead of an assumed one.
        """
        available = set(record.get("schema_context", {}).get("available_columns", []))
        for rule in record.get("rules", []):
            for cond in rule.get("conditions", []):
                field = cond.get("field")
                if field and (field not in self.schema_fields or field not in available):
                    return False
            for col in rule.get("affected_entities", {}).get("columns", []):
                if col not in self.schema_fields or col not in available:
                    return False
        return True

    def _tag_schema_validation(self, record: dict[str, Any]) -> dict[str, Any]:
        record["schema_validation_expected"] = "pass" if self._validate_schema_refs(record) else "fail"
        return record


class ParaphraseGenerator(FeedbackGenerator):
    """Generate paraphrases of existing feedback while preserving semantics."""

    OPERATION_TEMPLATES: dict[str, list[str]] = {
        "exclude": [
            "{term} should exclude {condition}.",
            "Exclude {condition} from {term}.",
            "{term} must not include {condition}.",
            "Don't count {condition} in {term}.",
            "{condition} should be excluded from {term}.",
            "Remove {condition} when calculating {term}.",
            "Please make sure {term} does not count {condition}.",
        ],
        "include": [
            "{term} should include {condition}.",
            "Include {condition} in {term}.",
            "{term} must include {condition}.",
            "Add {condition} to {term}.",
            "{condition} should be part of {term}.",
            "Make sure {term} accounts for {condition}.",
        ],
        "subtract": [
            "{term} should subtract {condition}.",
            "Subtract {condition} from {term}.",
            "{term} must deduct {condition}.",
            "{term} should net out {condition}.",
        ],
        "replace": [
            "{term} should use {condition} instead.",
            "Use {condition} for {term}.",
            "{term} should rely on {condition} going forward.",
            "Switch {term} over to {condition}.",
        ],
        "add": [
            "{term} calculation should add {condition}.",
            "Add {condition} to {term}.",
            "{term} should also account for {condition}.",
        ],
        "restrict": [
            "{term} should be restricted to {condition}.",
            "Only show {term} for {condition}.",
            "{term} access should be limited to {condition}.",
            "Restrict {term} so only {condition} can see it.",
        ],
    }

    # Used when a rule has no conditions at all (e.g. data-quality issues,
    # EC_FB013), instead of the old code silently producing "... exclude .".
    TERM_ONLY_TEMPLATES = [
        "There's an issue with {term}.",
        "{term} needs to be fixed.",
        "Please address the {term} problem.",
        "We need to clean up {term}.",
        "{term} isn't reliable right now.",
    ]

    def _condition_text_for(self, rule: dict[str, Any]) -> str:
        if rule.get("operation") == "restrict":
            scope = rule.get("scope") or ""
            if scope.startswith("region:"):
                return f"the {scope.split(':', 1)[1]} region"
        text = build_condition_text(rule)
        if text and rule.get("time_window") and rule.get("rule_category") == "time_rule":
            text += f", using {_humanize(rule['time_window'])} boundaries"
        return text

    def generate(self, seed: dict[str, Any], count: int = 3) -> list[dict[str, Any]]:
        """Generate paraphrases of a seed record."""
        if not seed.get("rules"):
            return []

        rule = seed["rules"][0]
        operation = rule.get("operation", "exclude")
        business_term = _humanize(rule.get("business_term", ""))
        condition_text = self._condition_text_for(rule)

        if condition_text:
            bank = self.OPERATION_TEMPLATES.get(operation, self.OPERATION_TEMPLATES["exclude"])
            picked = _sample_without_immediate_repeat(bank, count)
            texts = [t.format(term=business_term, condition=condition_text) for t in picked]
        else:
            picked = _sample_without_immediate_repeat(self.TERM_ONLY_TEMPLATES, count)
            texts = [t.format(term=business_term) for t in picked]

        generated = []
        for text in texts:
            record = self._copy_record_template(seed)
            record["feedback_text"] = text
            record["source_seed_id"] = seed.get("feedback_id")
            self._tag_schema_validation(record)
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

        # Earlier versions tried to strip the leading modal ("revenue
        # should exclude X" -> "revenue exclude X") to sound more casual,
        # but that breaks subject-verb agreement for most sentences (e.g.
        # "cancelled orders not contribute to revenue"). Keeping the modal
        # and just lowercasing/de-punctuating the sentence stays
        # grammatical for every seed, at the cost of a slightly more
        # formal register - an acceptable trade for correctness.
        original_text = (seed.get("feedback_text") or "").rstrip(".")
        rule_part = original_text[0].lower() + original_text[1:] if original_text else original_text

        templates = _sample_without_immediate_repeat(self.CONVERSATIONAL_TEMPLATES, count)
        generated = []
        for template in templates:
            record = self._copy_record_template(seed)
            record["feedback_text"] = template.format(rule=rule_part)
            record["source_seed_id"] = seed.get("feedback_id")
            self._tag_schema_validation(record)
            generated.append(record)
        return generated


class HinglishGenerator(FeedbackGenerator):
    """Generate Hinglish (Hindi-English mixed) feedback examples.

    Templates now mirror the code-switching pattern already used in your own
    manual seed EC_FB018 ("Revenue mein cancelled orders include mat karo
    yaar.") rather than appending a Hindi interjection to an otherwise fully
    English sentence.
    """

    EXCLUDE_TEMPLATES = [
        "{term} mein {condition} include mat karo.",
        "{term} mein {condition} include mat karo yaar.",
        "{term} se {condition} hatao.",
        "{condition} ko {term} calculation se nikaal do.",
        "Please {term} mein {condition} ko count mat karo.",
    ]
    INCLUDE_TEMPLATES = [
        "{term} mein {condition} bhi add karo.",
        "{condition} ko bhi {term} mein count karo.",
        "{term} calculation mein {condition} include karna zaroori hai.",
    ]
    GENERIC_TEMPLATES = [
        "{term} ka {condition} wala part thoda fix karo.",
        "Yaar {term} mein {condition} sahi se handle karo.",
        "{term} logic mein {condition} ke liye ek check add karo.",
    ]

    def generate(self, seed: dict[str, Any], count: int = 1) -> list[dict[str, Any]]:
        """Generate Hinglish versions of seed feedback."""
        if not seed.get("rules"):
            return []

        rule = seed["rules"][0]
        business_term = _humanize(rule.get("business_term", "revenue"))
        condition_text = build_condition_text(rule)
        if not condition_text:
            return []

        operation = rule.get("operation", "exclude")
        bank = {
            "exclude": self.EXCLUDE_TEMPLATES,
            "include": self.INCLUDE_TEMPLATES,
        }.get(operation, self.GENERIC_TEMPLATES)

        templates = _sample_without_immediate_repeat(bank, count)
        generated = []
        for template in templates:
            record = self._copy_record_template(seed)
            record["feedback_text"] = template.format(term=business_term, condition=condition_text)
            record["source_seed_id"] = seed.get("feedback_id")
            record["language_variant"] = "hinglish"
            self._tag_schema_validation(record)
            generated.append(record)
        return generated


class MultiRuleGenerator(FeedbackGenerator):
    """Generate feedback containing multiple independent rules."""

    CONNECTORS = ["and", "and also", "as well as", "and additionally"]

    def generate(self, seeds: list[dict[str, Any]], count: int = 1) -> list[dict[str, Any]]:
        """Generate multi-rule feedback by combining compatible seeds."""
        generated = []
        actionable_seeds = [s for s in seeds if s.get("rules") and s.get("is_actionable")]
        if len(actionable_seeds) < 2:
            return generated

        seen_combos: set[tuple[str, ...]] = set()
        attempts = 0
        while len(generated) < count and attempts < count * 10:
            attempts += 1
            num_rules = random.randint(2, min(3, len(actionable_seeds)))
            selected = random.sample(actionable_seeds, num_rules)
            combo_key = tuple(sorted(s.get("feedback_id", "") for s in selected))
            if combo_key in seen_combos:
                continue
            seen_combos.add(combo_key)

            base = selected[0]
            record = self._copy_record_template(base)

            connector = random.choice(self.CONNECTORS)
            raw_texts = [s.get("feedback_text", "").rstrip(".") for s in selected]
            # Lowercase the first letter of every sentence after the first
            # so the join doesn't leave a capital letter mid-sentence
            # (e.g. "...₹999 as well as Cancelled orders must...").
            texts = [raw_texts[0]] + [
                (t[0].lower() + t[1:] if t else t) for t in raw_texts[1:]
            ]
            feedback_text = f" {connector} ".join(texts) + "."

            all_rules = []
            all_rule_family_ids = []
            for s in selected:
                all_rules.extend(deepcopy(s.get("rules", [])))
                all_rule_family_ids.append(s.get("rule_family_id", ""))

            record["feedback_text"] = feedback_text
            record["rules"] = all_rules
            record["rule_family_id"] = "multi_" + "_".join(sorted(set(all_rule_family_ids)))
            record["source_seed_id"] = ",".join(s.get("feedback_id", "") for s in selected)

            all_tables: set[str] = set()
            all_columns: set[str] = set()
            for s in selected:
                all_tables.update(s.get("schema_context", {}).get("available_tables", []))
                all_columns.update(s.get("schema_context", {}).get("available_columns", []))
            record["schema_context"] = {
                "available_tables": sorted(all_tables),
                "available_columns": sorted(all_columns),
            }

            self._tag_schema_validation(record)
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
        "{term} doesn't look right to me.",
        "Not sure why but {term} feels off lately.",
        "{term} numbers seem strange this week.",
        "Can we revisit how {term} is calculated?",
        "I don't think {term} is correct.",
        "{term} needs a second look.",
    ]

    def generate(self, seeds: list[dict[str, Any]], count: int = 3) -> list[dict[str, Any]]:
        """Generate ambiguous feedback from business terms."""
        generated = []
        business_terms = sorted({
            rule.get("business_term")
            for seed in seeds
            for rule in seed.get("rules", [])
            if rule.get("business_term")
        })
        if not business_terms:
            return generated

        # Pair (term, template) combinations so repeated terms don't get the
        # same template back-to-back, and we don't exhaust either list early.
        combos = [(t, tpl) for t in business_terms for tpl in self.AMBIGUOUS_TEMPLATES]
        picked = random.sample(combos, min(count, len(combos)))
        while len(picked) < count:
            picked.append(random.choice(combos))

        for term, template in picked:
            record = {
                "feedback_id": self._generate_feedback_id(),
                "domain": self.config.domain_pack_id,
                "domain_pack_version": self.config.domain_pack_version,
                "rule_family_id": f"ambiguous_{term}_{random.randint(1000, 9999)}",
                "feedback_text": template.format(term=_humanize(term)),
                "feedback_type": "unclear_feedback",
                "rule_category": None,
                "is_actionable": False,
                "requires_clarification": True,
                "schema_context": {"available_tables": [], "available_columns": []},
                "rules": [],
                "annotation_version": self.config.annotation_version,
                "source": "programmatic",
            }
            generated.append(record)

        return generated


class ConflictGenerator(FeedbackGenerator):
    """Generate conflicting rule variants.

    Follows your existing seed convention (EC_FB006 / EC_FB007) where a
    conflict is expressed as a second record sharing the base
    rule_family_id with a "_conflict" suffix, rather than an explicit
    new_rule/existing_rule pair object — matching how your data is actually
    structured today.

    Produces two kinds of conflicts:
      - threshold conflicts: same field, contradictory numeric threshold
      - operation conflicts: same field, opposite operation
        (include vs exclude) — a case the old generator didn't cover at all
    """

    def _threshold_conflict(self, seed: dict[str, Any]) -> dict[str, Any] | None:
        rule = seed["rules"][0]
        if rule.get("threshold") is None:
            return None
        original_threshold = rule["threshold"]
        if isinstance(original_threshold, (int, float)):
            new_threshold = (
                original_threshold * 0.5 if original_threshold > 100 else original_threshold * 2
            )
        else:
            new_threshold = 500

        record = self._copy_record_template(seed)
        new_rules = deepcopy(seed.get("rules", []))
        for r in new_rules:
            if r.get("threshold") is not None:
                r["threshold"] = new_threshold
                for cond in r.get("conditions", []):
                    if cond.get("value") == original_threshold:
                        cond["value"] = new_threshold
        record["rules"] = new_rules
        record["rule_family_id"] = f"{seed.get('rule_family_id')}_conflict"

        original_text = seed.get("feedback_text", "")
        if str(original_threshold) in original_text:
            feedback_text = original_text.replace(str(original_threshold), str(new_threshold))
        else:
            feedback_text = f"{original_text.rstrip('.')} (should be {new_threshold}, not {original_threshold})."
        record["feedback_text"] = feedback_text
        record["source_seed_id"] = seed.get("feedback_id")
        record["conflict_type"] = "threshold_conflict"
        return record

    def _operation_conflict(self, seed: dict[str, Any]) -> dict[str, Any] | None:
        rule = seed["rules"][0]
        flip = {"exclude": "include", "include": "exclude"}.get(rule.get("operation", ""))
        if not flip or not rule.get("conditions"):
            return None

        record = self._copy_record_template(seed)
        new_rules = deepcopy(seed.get("rules", []))
        new_rules[0]["operation"] = flip
        record["rules"] = new_rules
        record["rule_family_id"] = f"{seed.get('rule_family_id')}_conflict"

        condition_text = build_condition_text(new_rules[0])
        term = _humanize(rule.get("business_term", ""))
        verb = "includes" if flip == "include" else "excludes"
        record["feedback_text"] = f"{term.capitalize()} {verb} {condition_text}."
        record["source_seed_id"] = seed.get("feedback_id")
        record["conflict_type"] = "operation_conflict"
        return record

    def generate(self, seeds: list[dict[str, Any]], count: int = 2) -> list[dict[str, Any]]:
        """Generate conflicting rule pairs by modifying thresholds or flipping operations."""
        generated: list[dict[str, Any]] = []
        candidates = [s for s in seeds if s.get("rules")]
        if not candidates:
            return generated

        attempts = 0
        while len(generated) < count and attempts < count * 10:
            attempts += 1
            seed = random.choice(candidates)
            conflict = self._threshold_conflict(seed) or self._operation_conflict(seed)
            if conflict is not None:
                self._tag_schema_validation(conflict)
                generated.append(conflict)

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
        "Login page keeps timing out for no reason.",
        "The app crashes when I upload a large file.",
        "Notifications aren't showing up on my phone.",
        "Dark mode has some unreadable text.",
        "The settings page takes forever to save changes.",
        "Table columns don't resize properly on my screen.",
        "The app logs me out too frequently.",
    ]

    def generate(self, count: int = 5) -> list[dict[str, Any]]:
        """Generate non-rule feedback examples."""
        texts = _sample_without_immediate_repeat(self.NON_RULE_TEMPLATES, count)
        generated = []
        for text in texts:
            record = {
                "feedback_id": self._generate_feedback_id(),
                "domain": self.config.domain_pack_id,
                "domain_pack_version": self.config.domain_pack_version,
                "rule_family_id": f"nonrule_{random.randint(1000, 9999)}",
                "feedback_text": text,
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
        "Work from home and earn 5 lakh per month, click now!",
        "Limited offer!!! 90% off, click before it's gone!",
        "Your package could not be delivered, click to reschedule.",
        "Verify your account now or it will be suspended today.",
    ]

    def generate(self, count: int = 5) -> list[dict[str, Any]]:
        """Generate spam feedback examples."""
        texts = _sample_without_immediate_repeat(self.SPAM_TEMPLATES, count)
        generated = []
        for text in texts:
            record = {
                "feedback_id": self._generate_feedback_id(),
                "domain": self.config.domain_pack_id,
                "domain_pack_version": self.config.domain_pack_version,
                "rule_family_id": f"spam_{random.randint(1000, 9999)}",
                "feedback_text": text,
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
    """Generate feedback with invalid schema references for validation testing.

    Rewritten to build the sentence from the actual replaced field (matching
    your own seed convention in EC_FB024: "Revenue should exclude
    orders.unknown_field equals foo."), instead of guessing that the words
    "cancelled"/"test" appear in the source text.
    """

    INVALID_FIELDS = [
        "orders.unknown_field",
        "customers.fake_column",
        "payments.nonexistent_field",
        "products.missing_attr",
    ]

    def generate(self, seeds: list[dict[str, Any]], count: int = 3) -> list[dict[str, Any]]:
        """Generate feedback with invalid schema references."""
        generated = []
        candidates = [s for s in seeds if s.get("rules")]
        if not candidates:
            return generated

        for _ in range(count):
            seed = random.choice(candidates)
            record = self._copy_record_template(seed)
            invalid_field = random.choice(self.INVALID_FIELDS)

            new_rules = deepcopy(seed.get("rules", []))
            rule = new_rules[0]
            rule["conditions"] = [{"field": invalid_field, "operator": "equals", "value": "foo"}]
            rule["affected_entities"]["columns"] = [invalid_field]
            record["rules"] = new_rules
            record["schema_validation_expected"] = "fail"
            record["rule_family_id"] = f"invalid_{random.randint(1000, 9999)}"

            term = _humanize(rule.get("business_term", ""))
            operation = rule.get("operation", "exclude")
            record["feedback_text"] = f"{term.capitalize()} should {operation} {invalid_field} equals foo."
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
        
        # Reset shared counter for unique IDs
        FeedbackGenerator._shared_counter = 0
        
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

        for seed in self.seed_records:
            if seed.get("is_actionable") and seed.get("rules"):
                all_generated["paraphrases"].extend(
                    self.paraphrase_gen.generate(seed, count=self.config.paraphrase_multiplier)
                )
                all_generated["conversational"].extend(
                    self.conversational_gen.generate(seed, count=self.config.conversational_multiplier)
                )
                all_generated["hinglish"].extend(
                    self.hinglish_gen.generate(seed, count=self.config.hinglish_multiplier)
                )

        all_generated["multi_rule"].extend(
            self.multi_rule_gen.generate(self.seed_records, count=self.config.multi_rule_multiplier * 5)
        )
        all_generated["ambiguous"].extend(
            self.ambiguous_gen.generate(self.seed_records, count=self.config.target_ambiguous)
        )
        all_generated["conflicts"].extend(
            self.conflict_gen.generate(self.seed_records, count=self.config.target_conflict_pairs)
        )
        all_generated["non_rule"].extend(self.non_rule_gen.generate(count=10))
        all_generated["spam"].extend(self.spam_gen.generate(count=10))
        all_generated["invalid_schema"].extend(
            self.invalid_schema_gen.generate(self.seed_records, count=5)
        )

        return self._dedupe(all_generated)

    @staticmethod
    def _dedupe(all_generated: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        """Drop exact-duplicate feedback_text across the whole run.

        Small template/seed pools mean some categories can independently
        land on the same sentence (e.g. two operation-conflicts landing on
        the same seed+flip). Rather than silently letting duplicate rows
        into train/val/test, we keep the first occurrence and drop the
        rest, category by category in generation order.
        """
        seen: set[str] = set()
        deduped: dict[str, list[dict[str, Any]]] = {}
        for category, records in all_generated.items():
            kept = []
            for r in records:
                text = r.get("feedback_text", "")
                if text in seen:
                    continue
                seen.add(text)
                kept.append(r)
            deduped[category] = kept
        return deduped

    def assign_splits(
        self,
        all_generated: dict[str, list[dict[str, Any]]],
        train_ratio: float | None = None,
        val_ratio: float | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Group every record (seeds + generated) by rule_family_id and
        assign whole families to a single split.

        This is the piece your spec explicitly calls out and the previous
        version of this file didn't implement at all:
        "Paraphrases of the same underlying rule must remain in the same
        split. Otherwise, the model may appear accurate simply because it
        saw an almost identical statement during training."

        Records with no rule_family_id (shouldn't normally happen, but
        defensive) each get treated as their own singleton family.
        """
        train_ratio = train_ratio if train_ratio is not None else getattr(self.config, "train_ratio", 0.70)
        val_ratio = val_ratio if val_ratio is not None else getattr(self.config, "val_ratio", 0.15)

        families: dict[str, list[dict[str, Any]]] = {}

        def _add(record: dict[str, Any]) -> None:
            fam = record.get("rule_family_id") or f"singleton_{record.get('feedback_id')}"
            families.setdefault(fam, []).append(record)

        for seed in self.seed_records:
            _add(seed)
        for records in all_generated.values():
            for record in records:
                _add(record)

        family_ids = list(families.keys())
        random.shuffle(family_ids)

        n = len(family_ids)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        splits: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
        for i, fam in enumerate(family_ids):
            if i < n_train:
                bucket = "train"
            elif i < n_train + n_val:
                bucket = "validation"
            else:
                bucket = "test"
            splits[bucket].extend(families[fam])

        return splits