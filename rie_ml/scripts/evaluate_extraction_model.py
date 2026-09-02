#!/usr/bin/env python3
"""
Evaluate DistilBERT Token Classifier on Frozen Test Set

Evaluates token-level BIO classification performance for rule extraction.
"""

import json
import torch
import numpy as np
from pathlib import Path
import sys
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
from collections import defaultdict
from tqdm import tqdm
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ml_models.token_classifier_loader import load_token_classifier, load_bio_labels


def evaluate_token_classifier():
    """Evaluate token classifier on test set."""

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Load model and labels
    model_path = Path(__file__).parent.parent / "models" / "distilbert_token_extractor" / "checkpoints" / "best_model.pt"
    bio_labels_file = Path(__file__).parent.parent / "datasets" / "extraction_bio" / "bio_labels.json"
    test_file = Path(__file__).parent.parent / "datasets" / "extraction_bio" / "test_bio.jsonl"
    output_dir = Path(__file__).parent.parent / "models" / "distilbert_token_extractor"

    if not model_path.exists():
        print(f"❌ Model not found: {model_path}")
        return

    print(f"\n📦 Loading model from {model_path}")
    model, bio_labels, label2id, id2label = load_token_classifier(model_path, device=device)
    from transformers import DistilBertTokenizerFast
    tokenizer = DistilBertTokenizerFast.from_pretrained('distilbert-base-uncased')

    # Load test data
    print(f"\n📋 Loading test data from {test_file}")
    test_samples = []
    with open(test_file, 'r') as f:
        for line in f:
            if line.strip():
                test_samples.append(json.loads(line))

    print(f"   Test samples: {len(test_samples)}")

    # Evaluate
    print("\n" + "="*80)
    print("EVALUATING DISTILBERT TOKEN CLASSIFIER")
    print("="*80)

    all_true_labels = []
    all_pred_labels = []
    per_sample_results = []

    for sample in tqdm(test_samples, desc="Evaluating"):
        tokens = sample['tokens']
        true_labels = sample['bio_labels']
        true_label_ids = sample['bio_label_ids']

        # Tokenize
        encoding = tokenizer(
            tokens,
            max_length=256,
            padding='max_length',
            truncation=True,
            return_tensors='pt',
            is_split_into_words=True
        )

        input_ids = encoding['input_ids'].to(device)
        attention_mask = encoding['attention_mask'].to(device)

        # Predict
        with torch.no_grad():
            logits = model(input_ids, attention_mask)

        # Map predictions back to original tokens properly
        word_ids = encoding.word_ids()
        predictions = []
        pred_ids = []

        # For each word position, collect predictions from its subword tokens
        word_predictions = {}
        for token_idx, word_idx in enumerate(word_ids):
            if word_idx is not None:
                logit = logits[0, token_idx, :]
                pred_id = torch.argmax(logit).item()

                # Take the first subword's prediction for this word
                if word_idx not in word_predictions:
                    word_predictions[word_idx] = pred_id

        # Create predictions list in word order
        for word_idx in range(len(tokens)):
            if word_idx in word_predictions:
                pred_id = word_predictions[word_idx]
                if pred_id < len(id2label):
                    predictions.append(id2label[pred_id])
                    pred_ids.append(pred_id)
                else:
                    predictions.append('O')
                    pred_ids.append(LABEL2ID['O'])
            else:
                predictions.append('O')
                pred_ids.append(LABEL2ID['O'])

        # Only compare valid label IDs (not -100)
        valid_indices = [i for i, lid in enumerate(true_label_ids) if lid != -100]
        if valid_indices:
            for idx in valid_indices:
                if idx < len(pred_ids):
                    all_true_labels.append(true_label_ids[idx])
                    all_pred_labels.append(pred_ids[idx])

        per_sample_results.append({
            'tokens': tokens,
            'true_labels': true_labels,
            'predicted_labels': predictions,
            'match': predictions == true_labels
        })

    # Compute metrics
    print("\n" + "="*80)
    print("EVALUATION RESULTS")
    print("="*80)

    # Filter out -100 (ignored tokens)
    valid_mask = np.array(all_true_labels) != -100
    true_filtered = np.array(all_true_labels)[valid_mask]
    pred_filtered = np.array(all_pred_labels)[:len(true_filtered)]

    precision, recall, f1, support = precision_recall_fscore_support(
        true_filtered,
        pred_filtered,
        average=None,
        zero_division=0
    )

    # Per-label results
    print(f"\n📊 Per-Label Performance:")
    print(f"{'Label':<25} {'Precision':<12} {'Recall':<12} {'F1':<12} {'Support':<10}")
    print("-" * 70)

    for label_id in sorted(set(true_filtered)):
        label_name = id2label.get(label_id, f"LABEL_{label_id}")
        prec = precision[label_id] if label_id < len(precision) else 0
        rec = recall[label_id] if label_id < len(recall) else 0
        f1_score = f1[label_id] if label_id < len(f1) else 0
        supp = support[label_id] if label_id < len(support) else 0
        print(f"{label_name:<25} {prec:<12.4f} {rec:<12.4f} {f1_score:<12.4f} {int(supp):<10}")

    # Macro averages
    macro_precision = np.mean(precision)
    macro_recall = np.mean(recall)
    macro_f1 = np.mean(f1)

    print("-" * 70)
    print(f"{'MACRO AVERAGE':<25} {macro_precision:<12.4f} {macro_recall:<12.4f} {macro_f1:<12.4f}")

    # Overall accuracy
    accuracy = np.mean(pred_filtered == true_filtered)
    print(f"\n🎯 Overall Token Accuracy: {accuracy:.4f} ({int(np.sum(pred_filtered == true_filtered))}/{len(true_filtered)} tokens)")

    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)

    evaluation_results = {
        'evaluation_date': datetime.now().isoformat(),
        'test_set_size': len(test_samples),
        'total_tokens': len(true_filtered),
        'overall_accuracy': float(accuracy),
        'macro_precision': float(macro_precision),
        'macro_recall': float(macro_recall),
        'macro_f1': float(macro_f1),
        'per_label': {}
    }

    for label_id in sorted(set(true_filtered)):
        label_name = id2label.get(label_id, f"LABEL_{label_id}")
        prec = precision[label_id] if label_id < len(precision) else 0
        rec = recall[label_id] if label_id < len(recall) else 0
        f1_score = f1[label_id] if label_id < len(f1) else 0
        supp = support[label_id] if label_id < len(support) else 0

        evaluation_results['per_label'][label_name] = {
            'precision': float(prec),
            'recall': float(rec),
            'f1': float(f1_score),
            'support': int(supp)
        }

    # Add sample results
    evaluation_results['sample_predictions'] = per_sample_results[:5]

    results_file = output_dir / 'token_evaluation_results.json'
    with open(results_file, 'w') as f:
        json.dump(evaluation_results, f, indent=2)

    print(f"\n✅ Results saved to {results_file}")

    return evaluation_results


if __name__ == "__main__":
    evaluate_token_classifier()
