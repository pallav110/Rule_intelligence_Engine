#!/usr/bin/env python3
"""
Balance BIO Training Dataset (Improved Strategy)

Instead of removing samples, we intelligently downsample "O" tokens
while keeping all entity tokens to reach target ratio.
"""

import json
import numpy as np
from pathlib import Path
from collections import Counter
from typing import List, Dict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def analyze_samples(samples: List[Dict]) -> Dict:
    """Analyze label distribution in samples."""
    label_counts = Counter()

    for sample in samples:
        labels = sample['bio_labels']
        label_counts.update(labels)

    total_tokens = sum(label_counts.values())
    return {
        'label_counts': dict(label_counts),
        'total_tokens': total_tokens,
        'o_ratio': label_counts['O'] / total_tokens if total_tokens > 0 else 0
    }


def create_balanced_samples(samples: List[Dict], target_o_ratio: float = 0.70) -> List[Dict]:
    """
    Create balanced samples by downsampling O tokens while keeping entities.

    Strategy: For samples with many O tokens, randomly remove some O tokens
    while keeping all entity (B_*, I_*) tokens.
    """
    balanced_samples = []
    analysis_before = analyze_samples(samples)

    current_o_tokens = analysis_before['label_counts'].get('O', 0)
    current_entity_tokens = analysis_before['total_tokens'] - current_o_tokens

    target_o_tokens = int((current_entity_tokens / (1 - target_o_ratio)) * target_o_ratio)
    o_tokens_to_remove = max(0, current_o_tokens - target_o_tokens)

    print(f"\n📊 Downsampling Strategy:")
    print(f"   Current O tokens: {current_o_tokens}")
    print(f"   Current entity tokens: {current_entity_tokens}")
    print(f"   Target O tokens: {target_o_tokens}")
    print(f"   Need to remove: {o_tokens_to_remove} O tokens")

    # Calculate probability of keeping each O token
    total_o_in_samples = sum(
        sample['bio_labels'].count('O')
        for sample in samples
    )
    keep_probability = max(0, 1 - (o_tokens_to_remove / total_o_in_samples))

    print(f"   Keep probability for O tokens: {keep_probability:.2%}")

    # Process each sample
    for sample in samples:
        tokens = sample['tokens']
        bio_labels = sample['bio_labels']
        bio_label_ids = sample['bio_label_ids']
        rule = sample['rule']

        # Keep all entity tokens, randomly downsample O tokens
        new_tokens = []
        new_labels = []
        new_label_ids = []

        for token, label, label_id in zip(tokens, bio_labels, bio_label_ids):
            if label == 'O':
                # Randomly decide to keep this O token
                if np.random.random() < keep_probability:
                    new_tokens.append(token)
                    new_labels.append(label)
                    new_label_ids.append(label_id)
            else:
                # Always keep entity tokens
                new_tokens.append(token)
                new_labels.append(label)
                new_label_ids.append(label_id)

        # Only keep samples that still have tokens
        if new_tokens:
            balanced_samples.append({
                'tokens': new_tokens,
                'bio_labels': new_labels,
                'bio_label_ids': new_label_ids,
                'text': sample['text'],
                'rule': rule
            })

    return balanced_samples


def main():
    """Balance training data."""
    print("\n" + "="*80)
    print("BALANCING BIO DATASET - DOWNSAMPLE O TOKENS")
    print("="*80)

    output_dir = Path(__file__).parent.parent / "datasets" / "extraction_bio"

    # Load training data
    all_samples = []
    train_file = output_dir / "train_bio.jsonl"

    with open(train_file) as f:
        for line in f:
            if line.strip():
                all_samples.append(json.loads(line))

    print(f"\n📋 Original training samples: {len(all_samples)}")

    # Analyze original
    analysis_before = analyze_samples(all_samples)
    print(f"\nBefore Balancing:")
    for label, count in sorted(analysis_before['label_counts'].items(), key=lambda x: -x[1])[:10]:
        pct = count / analysis_before['total_tokens'] * 100
        print(f"   {label:<20} {count:>5} ({pct:>5.1f}%)")
    print(f"   Total tokens: {analysis_before['total_tokens']}")

    # Balance dataset - aim for 70% O instead of 90%
    np.random.seed(42)  # For reproducibility
    balanced_samples = create_balanced_samples(all_samples, target_o_ratio=0.70)

    # Analyze balanced
    analysis_after = analyze_samples(balanced_samples)
    print(f"\nAfter Balancing:")
    for label, count in sorted(analysis_after['label_counts'].items(), key=lambda x: -x[1])[:10]:
        pct = count / analysis_after['total_tokens'] * 100
        print(f"   {label:<20} {count:>5} ({pct:>5.1f}%)")
    print(f"   Total tokens: {analysis_after['total_tokens']}")

    # Save balanced dataset
    print(f"\n💾 Saving balanced dataset...")

    # Backup original
    import shutil
    if not (output_dir / "train_bio_original.jsonl").exists():
        shutil.copy(train_file, output_dir / "train_bio_original.jsonl")
        print(f"   ✅ Backed up original to train_bio_original.jsonl")

    # Save balanced
    with open(train_file, 'w') as f:
        for sample in balanced_samples:
            f.write(json.dumps(sample) + '\n')

    print(f"   ✅ Replaced train_bio.jsonl with {len(balanced_samples)} balanced samples")

    print(f"\n📊 Summary:")
    print(f"   Samples: {len(all_samples)} → {len(balanced_samples)} ({len(balanced_samples)/len(all_samples)*100:.1f}%)")
    print(f"   Tokens: {analysis_before['total_tokens']} → {analysis_after['total_tokens']} ({analysis_after['total_tokens']/analysis_before['total_tokens']*100:.1f}%)")
    print(f"   O ratio: {analysis_before['o_ratio']:.1%} → {analysis_after['o_ratio']:.1%}")
    print(f"   Entity token increase in proportion: {(1-analysis_before['o_ratio']):.1%} → {(1-analysis_after['o_ratio']):.1%}")

    print("\n" + "="*80)
    print("✅ DATASET BALANCING COMPLETE")
    print("="*80)
    print("\nNow retrain with:")
    print("   python3 scripts/train_distilbert_token_classifier.py")


if __name__ == "__main__":
    main()
