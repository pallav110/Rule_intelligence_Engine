#!/usr/bin/env python3
"""
Prepare BIO Token-Level Training Data (Fixed Version)

Uses exact character-position matching for entity boundaries to ensure
precise token-level annotations. Solves class imbalance by proper alignment.
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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
    Assign BIO labels using exact character-position matching.

    This ensures precise token boundaries without fuzzy matching.
    """
    tokens_with_offsets = tokenize_with_offsets(text)
    labels = ['O'] * len(tokens_with_offsets)

    # Track which character ranges have been labeled
    labeled_ranges = []

    def add_label(entity_text: str, bio_label_prefix: str):
        """Add BIO labels for entity, respecting token boundaries."""
        positions = find_exact_positions(text, entity_text, case_sensitive=False)

        for pos_start, pos_end in positions:
            is_first_token = True

            for token_idx, (token, tok_start, tok_end) in enumerate(tokens_with_offsets):
                # Check if token overlaps with entity position
                if tok_start >= pos_start and tok_end <= pos_end:
                    # Check for conflicts with previously labeled ranges
                    conflict = False
                    for labeled_start, labeled_end in labeled_ranges:
                        if not (tok_end <= labeled_start or tok_start >= labeled_end):
                            conflict = True
                            break

                    if not conflict:
                        if is_first_token:
                            labels[token_idx] = f"B_{bio_label_prefix}"
                            is_first_token = False
                        else:
                            labels[token_idx] = f"I_{bio_label_prefix}"

                        labeled_ranges.append((tok_start, tok_end))

    # Label entities in priority order (most specific first)

    # 1. Business term (high priority)
    if 'business_term' in rule and rule['business_term']:
        add_label(rule['business_term'], 'BUSINESS_TERM')

    # 2. Conditions (fields, operators, values)
    if 'conditions' in rule and rule['conditions']:
        for condition in rule['conditions']:
            if 'field' in condition and condition['field']:
                add_label(condition['field'], 'FIELD')

            if 'value' in condition and condition['value']:
                value_str = str(condition['value'])
                # Only add if value is reasonably long (avoid single chars)
                if len(value_str) > 1:
                    add_label(value_str, 'VALUE')

    # 3. Operation
    if 'operation' in rule and rule['operation']:
        add_label(rule['operation'], 'OPERATION')

    # 4. Scope
    if 'scope' in rule and rule['scope']:
        scope_str = rule['scope']
        if scope_str not in ['global']:  # Don't label 'global' as it's common
            add_label(scope_str, 'SCOPE')

    # 5. Time window
    if 'time_window' in rule and rule['time_window']:
        if isinstance(rule['time_window'], dict):
            for key, val in rule['time_window'].items():
                if val and len(str(val)) > 1:
                    add_label(str(val).lower(), 'TIME_WINDOW')
        else:
            time_str = str(rule['time_window']).lower()
            if len(time_str) > 1:
                add_label(time_str, 'TIME_WINDOW')

    # 6. Threshold
    if 'threshold' in rule and rule['threshold']:
        threshold_str = str(rule['threshold'])
        if len(threshold_str) > 1:
            add_label(threshold_str, 'THRESHOLD')

    # 7. Affected entities (tables/columns)
    if 'affected_entities' in rule:
        entities = rule['affected_entities']
        if 'tables' in entities:
            for table in entities['tables']:
                if table:
                    add_label(table, 'TABLE')
        if 'columns' in entities:
            for column in entities['columns']:
                if column:
                    # Try full column name first
                    add_label(column, 'COLUMN')

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

    with open(file_path, 'r') as f:
        for line_idx, line in enumerate(f):
            if not line.strip():
                continue

            try:
                data = json.loads(line)
                feedback_text = data.get('feedback_text', '')
                rules = data.get('rules', [])

                # Create a sample for each rule
                for rule in rules:
                    sample = prepare_training_sample(feedback_text, rule)
                    samples.append(sample)

            except Exception as e:
                print(f"Error processing line {line_idx} in {file_path}: {e}")
                continue

    return samples


def main():
    """Prepare BIO training data from all domains."""
    from sklearn.model_selection import train_test_split

    output_dir = Path(__file__).parent.parent / "datasets" / "extraction_bio"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*80)
    print("PREPARING BIO TOKEN-LEVEL TRAINING DATA (FIXED - PRECISE MATCHING)")
    print("="*80)

    all_samples = []
    domains = ["ecommerce", "customer_support", "saas_subscription"]
    domain_counts = {}

    # Process each domain
    for domain in domains:
        file_path = Path(__file__).parent.parent / "dataset_generation" / "output" / domain / "extraction.jsonl"

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
    from collections import Counter
    label_dist = Counter()
    for sample in all_samples:
        for label in sample['bio_labels']:
            label_dist[label] += 1

    print(f"\n📈 Label Distribution (All Data):")
    for label, count in sorted(label_dist.items(), key=lambda x: -x[1]):
        pct = count / sum(label_dist.values()) * 100
        print(f"   {label:<20} {count:>5} ({pct:>5.1f}%)")

    # Split into train/val/test
    train_samples, temp_samples = train_test_split(all_samples, test_size=0.2, random_state=42)
    val_samples, test_samples = train_test_split(temp_samples, test_size=0.5, random_state=42)

    print(f"\n📋 Split Summary:")
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
        if label_counts['O'] < 0.95 * len(sample['bio_labels']):  # Has entities
            good_sample = sample
            break

    if good_sample:
        print(f"\n📝 Sample Training Instance (with entities):")
        print(f"   Text: {good_sample['text']}")
        print(f"   Tokens: {good_sample['tokens']}")
        print(f"   Labels: {good_sample['bio_labels']}")

    print("\n" + "="*80)
    print("✅ BIO DATA PREPARATION COMPLETE (FIXED)")
    print("="*80)


if __name__ == "__main__":
    main()
