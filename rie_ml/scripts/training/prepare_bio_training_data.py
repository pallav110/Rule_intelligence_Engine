#!/usr/bin/env python3
"""
Prepare BIO Token-Level Training Data (Spec 8.4 / 8.12 compliant)

Converts extraction.jsonl (per domain) into BIO token-labeled training data
exactly as a human annotator would label per Spec 8.4's annotation scheme:

- FIELD is labeled only over the surface field word present in the text
  (e.g. "status" in "status equals cancelled"); the canonical "orders.status"
  is resolved in Rule Construction (Stage 2), not invented here.
- OPERATION covers BOTH the rule-level business operation phrase
  ("exclude", "must not include", "should use ... instead") and the
  condition operator words ("greater than", "above", ...) as shown in the
  spec's Condition Transformation Example ([OPERATION: "equals"]).
- VALUE/THRESHOLD use subword-span matching so tokens like "₹999" and
  "1,500" are labeled correctly.
- BUSINESS_TERM / SCOPE / TIME_WINDOW / TABLE / COLUMN labeled when the
  surface words exist in the text; nothing is invented (Spec 8.8).

Splits are rule_family_id aware (Spec 8.12: same-family examples stay in
the same split to prevent leakage).
"""

import json
import re
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Dict, Tuple
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# BIO labels for token classification
BIO_LABELS = [
    'O',                      # Outside any entity
    'B_BUSINESS_TERM',        # Beginning of business term
    'I_BUSINESS_TERM',        # Inside business term
    'B_OPERATION',            # Beginning of operation
    'I_OPERATION',            # Inside operation
    'B_FIELD',                # Beginning of field reference
    'I_FIELD',                # Inside field reference
    'B_VALUE',                # Beginning of condition value
    'I_VALUE',                # Inside condition value
    'B_SCOPE',                # Beginning of scope
    'I_SCOPE',                # Inside scope
    'B_TIME_WINDOW',          # Beginning of time window
    'I_TIME_WINDOW',          # Inside time window
    'B_THRESHOLD',            # Beginning of threshold
    'B_TABLE',                # Beginning of table reference
    'B_COLUMN',               # Beginning of column reference
]

LABEL2ID = {label: idx for idx, label in enumerate(BIO_LABELS)}
ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}


def _humanize(token: str) -> str:
    return token.replace("_", " ").strip()


# Rule-level operation surface phrases, keyed by canonical operation.
# Longest phrases first so "must not include" beats ...; phrases must never
# collide with a DIFFERENT operation's literal word (e.g. an EXCLUDE rule
# whose text says "must not include" must not label "include").
RULE_OP_SURFACE: Dict[str, List[str]] = {
    "exclude": [
        "must not include", "does not count", "do not count", "don't count",
        "should be excluded", "excluded from", "exclude", "not contribute",
        "removed from", "remove",
    ],
    "include": [
        "must include", "should be part of", "accounts for", "part of",
        "include", "count toward", "counts toward",
    ],
    "restrict": [
        "restricted to", "access should be limited to", "limited to",
        "only show", "restrict",
    ],
    "replace": [
        "instead of", "rely on", "switch", "use", "instead",
    ],
    "subtract": ["net out", "subtract", "deduct"],
    "add": ["also account for", "add to", "add"],
}

# Condition operator word phrases (Spec 8.4 Condition Transformation Example:
# [OPERATION: "equals"]).
COND_OP_SURFACE = {
    "equals": ["equal to", "equals"],
    "greater_than": ["greater than", "more than", "exceeds", "above", "over"],
    "less_than": ["less than", "below", "under"],
    "not_equals": ["does not equal", "doesn't equal", "not equal"],
    "is_not_null": ["is present", "has a value", "non-empty"],
}


def tokenize_with_offsets(text: str) -> List[Tuple[str, int, int]]:
    """
    Tokenize text and return tokens with their character offsets.

    Returns: List of (token, start_pos, end_pos)
    """
    tokens_with_offsets = []
    current_pos = 0

    for token in text.split():
        # Find token in text starting from current_pos
        start = text.find(token, current_pos)
        if start == -1:
            # Token not found, skip
            continue
        end = start + len(token)
        tokens_with_offsets.append((token, start, end))
        current_pos = end

    return tokens_with_offsets


def find_exact_positions(text: str, target: str, case_sensitive: bool = False) -> List[Tuple[int, int]]:
    """Find exact character positions of target string in text."""
    if not target:
        return []

    # Normalize numeric formatting: "1,500" and "₹1,500" both match "1500"
    if target.isdigit() or (target.lstrip("-").replace(",", "").isdigit() and "." not in target.replace(",", "")):
        digits = target.replace(",", "")
        spaced = f" {digits} , "  # placeholder unused; plain digit search below
        positions = []
        for m in re.finditer(r"[\d][\d,]*(?:\.\d+)?", text, re.IGNORECASE):
            if m.group().replace(",", "").replace("₹", "").replace("$", "") == digits.replace(".", ""):
                positions.append((m.start(), m.end()))
                # Hmm: "999" vs "₹999" - group() is "999" (₹ not in \d class)
        # Fall back to verbatim search for non-currency strings
        text_search = text.lower() if not case_sensitive else text
        target_search = target.lower() if not case_sensitive else target
        extra = []
        start = 0
        while True:
            pos = text_search.find(target_search, start)
            if pos == -1:
                break
            extra.append((pos, pos + len(target)))
            start = pos + 1
        if positions:
            return positions
        return extra

    if not case_sensitive:
        text_search = text.lower()
        target_search = target.lower()
    else:
        text_search = text
        target_search = target

    positions = []
    start = 0
    while True:
        pos = text_search.find(target_search, start)
        if pos == -1:
            break
        positions.append((pos, pos + len(target)))
        start = pos + 1

    return positions


def assign_bio_labels_precise(text: str, rule: Dict) -> List[str]:
    """
    Assign BIO labels using span matching a human annotator would use.

    Subword spans are allowed: a token overlapping the entity position
    ("₹999" contains "999") is labeled as a whole, mirroring how the token
    classifier will later consume it.
    """
    tokens_with_offsets = tokenize_with_offsets(text)
    labels = ['O'] * len(tokens_with_offsets)

    # Track which token ranges have been labeled to prevent conflicts
    labeled_token_ids = set()

    def add_label(entity_text: str, bio_label_prefix: str):
        """Add BIO labels for entity over every occurrence in text."""
        positions = find_exact_positions(text, entity_text)
        if not positions:
            return

        for pos_start, pos_end in positions:
            is_first_token = True
            for token_idx, (token, tok_start, tok_end) in enumerate(tokens_with_offsets):
                if tok_start >= pos_end:
                    break  # past the entity
                entity_is_number = entity_text.replace(",", "").isdigit()
                if entity_is_number:
                    # Number entities: token may contain the number with
                    # currency/units attached ("₹999", "$1500", "90%")
                    overlaps = tok_start < pos_end and tok_end > pos_start
                else:
                    # Word entities: token must START at the entity start
                    # (covers trailing punctuation: "tickets." vs "tickets")
                    # or sit fully inside the entity span ("total amount")
                    starts_at = tok_start <= pos_start < tok_end or (tok_start == pos_start and tok_end > pos_start)
                    fully_inside = tok_start >= pos_start and tok_end <= pos_end
                    overlaps = starts_at or fully_inside
                if overlaps:
                    if token_idx in labeled_token_ids:
                        # Skip tokens already claimed by a more specific label
                        continue
                    labels[token_idx] = f"B_{bio_label_prefix}" if is_first_token else f"I_{bio_label_prefix}"
                    if tok_end > pos_end:
                        is_first_token = True  # entity continues on next word
                    else:
                        is_first_token = False
                    labeled_token_ids.add(token_idx)

    # ---- 1. Business term (highest priority, most specific) ----
    business_term = rule.get("business_term")
    if business_term:
        add_label(business_term, "BUSINESS_TERM")
        if isinstance(business_term, str) and "_" in business_term:
            add_label(_humanize(business_term), "BUSINESS_TERM")

    # ---- 2. Conditions: field, then threshold/value --------------
    # Priority: THRESHOLD (numeric comparison) > VALUE (categorical)
    conditions = rule.get("conditions") or []
    for condition in conditions:
        field = condition.get("field")
        if field:
            simple = field.split(".")[-1] if "." in str(field) else str(field)
            if not simple:
                simple = str(field)
            add_label(simple, "FIELD")
            if "_" in simple:
                add_label(_humanize(simple), "FIELD")

    # Second pass: threshold first (higher priority for numeric ops)
    for condition in conditions:
        value = condition.get("value")
        if value is None:
            continue
        value_str = str(value).lower()
        if len(value_str) <= 1 and not value_str.isdigit():
            continue
        operator = (condition.get("operator") or "").lower()
        rule_threshold = rule.get("threshold")
        is_threshold = (
            operator in ("greater_than", "less_than")
            or (rule_threshold is not None and str(rule_threshold).replace(",", "") == value_str.replace(",", ""))
        )
        if is_threshold:
            add_label(value_str, "THRESHOLD")

    # Third pass: remaining values (categorical)
    for condition in conditions:
        value = condition.get("value")
        if value is None:
            continue
        value_str = str(value).lower()
        if len(value_str) <= 1 and not value_str.isdigit():
            continue
        operator = (condition.get("operator") or "").lower()
        rule_threshold = rule.get("threshold")
        is_threshold = (
            operator in ("greater_than", "less_than")
            or (rule_threshold is not None and str(rule_threshold).replace(",", "") == value_str.replace(",", ""))
        )
        if not is_threshold:
            add_label(value_str, "VALUE")

    # ---- 3. Rule-level operation --------------------------------
    operation = (rule.get("operation") or "").lower()
    if operation:
        # Literal operation word when it appears verbatim
        add_label(operation, "OPERATION")
        # Surface phrases for that specific operation
        for phrase in RULE_OP_SURFACE.get(operation, []):
            add_label(phrase, "OPERATION")

    # Condition operator words: label only when the condition's value is
    # present in the same sentence (anchors the operator span)
    for condition in conditions:
        value = condition.get("value")
        if value is None or str(value).lower() not in text.lower()[:-1] or len(str(value)) <= 1:
            continue
        operator = (condition.get("operator") or "").lower()
        for phrase in COND_OP_SURFACE.get(operator, []):
            add_label(phrase, "OPERATION")

    # ---- 4. Scope -------------------------------------------------
    scope = rule.get("scope")
    if scope and str(scope) not in ("global", "Global"):
        scope_str = str(scope)
        add_label(scope_str, "SCOPE")
        if ":" in scope_str:
            suffix = scope_str.split(":", 1)[1]
            add_label(suffix, "SCOPE")
            add_label(_humanize(suffix), "SCOPE")
        else:
            add_label(_humanize(scope_str), "SCOPE")

    # ---- 5. Time window -------------------------------------------
    time_window = rule.get("time_window")
    if time_window:
        if isinstance(time_window, dict):
            for key, val in time_window.items():
                if val is None:
                    continue
                val_str = str(val).lower()
                if len(val_str) > 1:
                    add_label(val_str, "TIME_WINDOW")
                    add_label(_humanize(val_str), "TIME_WINDOW")
                if key in ("type", "unit") and len(val_str) > 1:
                    add_label(_humanize(val_str), "TIME_WINDOW")
        else:
            time_str = str(time_window).lower()
            if len(time_str) > 1:
                add_label(time_str, "TIME_WINDOW")
                add_label(_humanize(time_str), "TIME_WINDOW")

    # ---- 6. Affected entities (tables / columns) ------------------
    entities = rule.get("affected_entities") or {}
    for table in entities.get("tables", []):
        if table:
            add_label(table, "TABLE")
    for column in entities.get("columns", []):
        if column:
            col = str(column)
            simple = col.split(".")[-1]
            add_label(simple, "COLUMN")
            if "_" in simple:
                add_label(_humanize(simple), "COLUMN")

    return labels


def prepare_training_sample(feedback_text: str, rule: Dict) -> Dict:
    """Prepare a single training sample with tokens and BIO labels."""
    tokens_with_offsets = tokenize_with_offsets(feedback_text)
    tokens = [t[0] for t in tokens_with_offsets]
    bio_labels = assign_bio_labels_precise(feedback_text, rule)
    bio_label_ids = [LABEL2ID[label] for label in bio_labels]

    return {
        'tokens': tokens,
        'bio_labels': bio_labels,
        'bio_label_ids': bio_label_ids,
        'text': feedback_text,
        'rule': rule
    }


def process_extraction_file(file_path: Path) -> List[Dict]:
    """Process extraction.jsonl file and create BIO training samples."""
    samples = []

    with open(file_path) as f:
        for line_idx, line in enumerate(f):
            if not line.strip():
                continue

            try:
                data = json.loads(line)
                feedback_text = data.get('feedback_text', '')
                rules = data.get('rules', [])
                family_id = data.get('rule_family_id', 'unknown')

                # Create a sample for each rule
                for rule in rules:
                    sample = prepare_training_sample(feedback_text, rule)
                    sample['rule_family_id'] = family_id
                    samples.append(sample)

            except Exception as e:
                print(f"Error processing line {line_idx} in {file_path}: {e}")
                continue

    return samples


def split_by_rule_family(samples: List[Dict], val_ratio: float = 0.18, test_ratio: float = 0.18) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Rule-family-aware split (Spec 8.12): every sample of the same
    rule_family_id goes to the same split, preventing leakage through
    paraphrases of the same rule.
    """
    import random

    families: Dict[str, List[Dict]] = defaultdict(list)
    for sample in samples:
        families[sample.get("rule_family_id", "unknown")].append(sample)

    family_ids = list(families.keys())
    random.Random(42).shuffle(family_ids)

    n = len(family_ids)
    n_val = int(n * val_ratio)
    n_test = int(n * test_ratio)

    train_s, val_s, test_s = [], [], []
    for idx, fam in enumerate(family_ids):
        bucket = "test" if idx < n_test else "val" if idx < n_test + n_val else "train"
        target = {"train": train_s, "val": val_s, "test": test_s}[bucket]
        target.extend(families[fam])

    return train_s, val_s, test_s


def main():
    """Prepare BIO training data from all domains."""
    output_dir = Path(__file__).parent.parent / "datasets" / "extraction_bio"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("PREPARING BIO TOKEN-LEVEL TRAINING DATA (SPEC 8.4/8.12 COMPLIANT)")
    print("=" * 80)

    all_samples = []
    domains = ["ecommerce", "customer_support", "saas_subscription"]
    domain_counts = {}

    # Process each domain
    for domain in domains:
        file_path = Path(__file__).parent.parent.parent / "dataset_generation" / "output" / domain / "extraction.jsonl"

        if file_path.exists():
            print(f"\n📦 Processing {domain}...")
            samples = process_extraction_file(file_path)
            all_samples.extend(samples)
            domain_counts[domain] = len(samples)
            print(f"   ✅ Loaded {len(samples)} samples")
        else:
            print(f"   ⚠️  File not found: {file_path}")

    print(f"\n📊 Domain Summary:")
    for domain, count in domain_counts.items():
        print(f"   {domain}: {count} samples")
    print(f"   Total: {len(all_samples)} samples")

    if len(all_samples) == 0:
        print("❌ No samples found! Exiting.")
        return

    # Analyze label distribution
    label_dist = Counter()
    for sample in all_samples:
        for label in sample['bio_labels']:
            label_dist[label] += 1

    print(f"\n📈 Label Distribution (All Data):")
    for label, count in sorted(label_dist.items(), key=lambda x: -x[1]):
        pct = count / sum(label_dist.values()) * 100
        print(f"   {label:<20} {count:>5} ({pct:>5.2f}%)")

    # Split by rule family (Spec 8.12: no leakage across paraphrases)
    train_samples, val_samples, test_samples = split_by_rule_family(all_samples)

    print(f"\n📋 Split Summary (rule-family aware):")
    print(f"   Train: {len(train_samples)} samples ({len(train_samples)/len(all_samples)*100:.1f}%)")
    print(f"   Val:   {len(val_samples)} samples ({len(val_samples)/len(all_samples)*100:.1f}%)")
    print(f"   Test:  {len(test_samples)} samples ({len(test_samples)/len(all_samples)*100:.1f}%)")

    # Save training data
    def save_split(samples, filename):
        with open(output_dir / filename, 'w') as f:
            for sample in samples:
                f.write(json.dumps(sample) + '\n')

    save_split(train_samples, 'train_bio.jsonl')
    save_split(val_samples, 'val_bio.jsonl')
    save_split(test_samples, 'test_bio.jsonl')

    print(f"\n✅ Training data saved to {output_dir}")

    # Save BIO label mapping
    label_mapping = {
        'labels': BIO_LABELS,
        'label2id': LABEL2ID,
        'id2label': {str(k): v for k, v in ID2LABEL.items()}
    }

    with open(output_dir / 'bio_labels.json', 'w') as f:
        json.dump(label_mapping, f, indent=2)

    print(f"✅ Label mapping saved")

    # Print sample with good annotation
    good_sample = None
    for sample in train_samples:
        label_counts = Counter(sample['bio_labels'])
        if label_counts['O'] < 0.90 * len(sample['bio_labels']):  # Has entities
            good_sample = sample
            break

    if good_sample:
        print(f"\n📝 Sample Training Instance (with entities):")
        print(f"   Text: {good_sample['text']}")
        print(f"   Tokens: {good_sample['tokens']}")
        print(f"   Labels: {good_sample['bio_labels']}")

    print("\n" + "=" * 80)
    print("✅ BIO DATA PREPARATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()