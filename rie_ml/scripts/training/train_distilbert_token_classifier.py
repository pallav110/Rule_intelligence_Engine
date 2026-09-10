#!/usr/bin/env python3
"""
Multi-Domain DistilBERT Token Classification for Rule Extraction

Trains DistilBERT for BIO token-level classification to extract rule components
(business_term, operation, conditions, scope, etc.) from feedback text.
"""

import json
import torch
import numpy as np
from torch.utils.data import DataLoader, Dataset
from pathlib import Path
import sys
from tqdm import tqdm
from datetime import datetime
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Load BIO labels
BIO_LABELS_FILE = Path(__file__).parent.parent.parent / "datasets" / "extraction_bio" / "bio_labels.json"
with open(BIO_LABELS_FILE, 'r') as f:
    label_mapping = json.load(f)
    BIO_LABELS = label_mapping['labels']
    LABEL2ID = label_mapping['label2id']
    ID2LABEL = {int(k): v for k, v in label_mapping['id2label'].items()}

NUM_LABELS = len(BIO_LABELS)


class RuleExtractionDataset(Dataset):
    """Token classification dataset for rule extraction."""

    def __init__(self, data_file, tokenizer, max_length=256):
        self.data = []
        self.tokenizer = tokenizer
        self.max_length = max_length

        # Load JSONL file
        with open(data_file, 'r') as f:
            for line in f:
                if line.strip():
                    self.data.append(json.loads(line))

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        tokens = item['tokens']
        bio_label_ids = item['bio_label_ids']

        # Tokenize with subword handling
        encoding = self.tokenizer(
            tokens,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt',
            is_split_into_words=True
        )

        # Map BIO labels to subword tokens
        word_ids = encoding.word_ids()
        label_ids = [-100] * len(word_ids)  # -100 = ignore in loss

        for i, word_idx in enumerate(word_ids):
            if word_idx is not None and word_idx < len(bio_label_ids):
                label_ids[i] = bio_label_ids[word_idx]

        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'token_type_ids': encoding.get('token_type_ids', torch.zeros(encoding['input_ids'].shape[1])).squeeze(),
            'labels': torch.tensor(label_ids, dtype=torch.long)
        }


class DistilBERTTokenClassifier(torch.nn.Module):
    """DistilBERT for token-level classification."""

    def __init__(self, num_labels, dropout=0.1):
        super().__init__()
        from transformers import AutoModel

        self.distilbert = AutoModel.from_pretrained('distilbert-base-uncased')
        hidden_size = self.distilbert.config.hidden_size

        # Token classification head
        self.dropout = torch.nn.Dropout(dropout)
        self.classifier = torch.nn.Linear(hidden_size, num_labels)

    def forward(self, input_ids, attention_mask=None, token_type_ids=None, **kwargs):
        outputs = self.distilbert(
            input_ids=input_ids,
            attention_mask=attention_mask
        )
        sequence_output = outputs.last_hidden_state

        sequence_output = self.dropout(sequence_output)
        logits = self.classifier(sequence_output)

        return logits


def compute_metrics(predictions, labels, id2label):
    """Compute precision, recall, F1 for token classification."""
    from sklearn.metrics import classification_report, confusion_matrix

    # Flatten and filter out ignored indices (-100)
    pred_flat = predictions.flatten()
    labels_flat = labels.flatten()

    mask = labels_flat != -100
    pred_flat = pred_flat[mask]
    labels_flat = labels_flat[mask]

    # Get unique labels present in predictions or labels
    unique_labels = sorted(set(list(pred_flat) + list(labels_flat)))
    target_names = [id2label.get(i, f"LABEL_{i}") for i in unique_labels]

    report = classification_report(
        labels_flat,
        pred_flat,
        labels=unique_labels,
        target_names=target_names,
        output_dict=True,
        zero_division=0
    )

    return report


def train_token_classifier():
    """Train DistilBERT token classifier."""
    from transformers import DistilBertTokenizerFast
    import torch.optim as optim

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Paths
    output_dir = Path(__file__).parent.parent.parent / "models" / "distilbert_token_extractor"
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir = output_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    # Load training data
    print("\n📦 Loading token classification training data...")
    train_file = Path(__file__).parent.parent.parent / "datasets" / "extraction_bio" / "train_bio.jsonl"
    val_file = Path(__file__).parent.parent.parent / "datasets" / "extraction_bio" / "val_bio.jsonl"

    # Create tokenizer and datasets
    tokenizer = DistilBertTokenizerFast.from_pretrained('distilbert-base-uncased')
    train_dataset = RuleExtractionDataset(train_file, tokenizer)
    val_dataset = RuleExtractionDataset(val_file, tokenizer)

    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=8)

    print(f"Train samples: {len(train_dataset)}")
    print(f"Val samples: {len(val_dataset)}")
    print(f"Number of token labels: {NUM_LABELS}")

    # Initialize model
    model = DistilBERTTokenClassifier(num_labels=NUM_LABELS)
    model.to(device)

    # Training setup
    optimizer = optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=5,
        eta_min=1e-6
    )

    # Compute class weights to handle imbalance
    label_counts = defaultdict(int)
    for batch in train_loader:
        labels = batch['labels'].flatten()
        for label_id in labels:
            if label_id != -100:
                label_counts[label_id.item()] += 1

    # Weight inversely proportional to class frequency
    total_samples = sum(label_counts.values())
    class_weights = torch.ones(NUM_LABELS)
    for label_id, count in label_counts.items():
        if count > 0:
            class_weights[label_id] = total_samples / (NUM_LABELS * count)

    class_weights = class_weights.to(device)
    print(f"\n📊 Class Weights (for balancing):")
    for i, weight in enumerate(class_weights):
        if i < NUM_LABELS:
            label_name = ID2LABEL.get(i, f'LABEL_{i}')
            print(f"   {label_name:<25} weight={weight:.4f}")

    # Loss function with class weights (ignores -100 labels from padding/subword handling)
    criterion = torch.nn.CrossEntropyLoss(ignore_index=-100, weight=class_weights)

    best_val_loss = float('inf')
    patience = 3
    patience_counter = 0

    # Training loop
    print("\n" + "="*80)
    print("TRAINING DISTILBERT TOKEN CLASSIFIER FOR RULE EXTRACTION")
    print("="*80)

    training_history = {
        'epochs': [],
        'train_loss': [],
        'val_loss': [],
        'val_metrics': []
    }

    for epoch in range(5):
        print(f"\n📚 Epoch {epoch + 1}/5")

        # Training
        model.train()
        train_loss = 0.0

        for batch in tqdm(train_loader, desc="Training"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            optimizer.zero_grad()

            logits = model(input_ids, attention_mask)
            loss = criterion(logits.view(-1, NUM_LABELS), labels.view(-1))

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            train_loss += loss.item()

        avg_train_loss = train_loss / len(train_loader)
        print(f"Training Loss: {avg_train_loss:.4f}")

        # Validation
        model.eval()
        val_loss = 0.0
        all_predictions = []
        all_labels = []

        with torch.no_grad():
            for batch in tqdm(val_loader, desc="Validation"):
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                labels = batch['labels'].to(device)

                logits = model(input_ids, attention_mask)
                loss = criterion(logits.view(-1, NUM_LABELS), labels.view(-1))
                val_loss += loss.item()

                # Store predictions for metrics
                predictions = torch.argmax(logits, dim=-1)
                all_predictions.append(predictions.cpu().numpy())
                all_labels.append(labels.cpu().numpy())

        scheduler.step()
        avg_val_loss = val_loss / len(val_loader)
        print(f"Validation Loss: {avg_val_loss:.4f}")

        # Compute metrics
        predictions_flat = np.concatenate(all_predictions)
        labels_flat = np.concatenate(all_labels)
        metrics = compute_metrics(predictions_flat, labels_flat, ID2LABEL)

        # Print per-label F1 scores
        print("\n📊 Per-Label F1 Scores:")
        for label_name in ['B_BUSINESS_TERM', 'B_OPERATION', 'B_FIELD', 'B_VALUE', 'B_SCOPE', 'B_THRESHOLD', 'B_TABLE', 'B_COLUMN']:
            if label_name in metrics:
                f1 = metrics[label_name].get('f1-score', 0)
                print(f"   {label_name}: {f1:.4f}")

        training_history['epochs'].append(epoch + 1)
        training_history['train_loss'].append(avg_train_loss)
        training_history['val_loss'].append(avg_val_loss)
        training_history['val_metrics'].append(metrics)

        # Save best model
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            patience_counter = 0

            checkpoint = {
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'epoch': epoch,
                'loss': avg_val_loss,
                'num_labels': NUM_LABELS,
                'bio_labels': BIO_LABELS,
                'label2id': LABEL2ID
            }

            best_model_path = checkpoints_dir / "best_model.pt"
            torch.save(checkpoint, best_model_path)
            print(f"✅ Saved best model to {best_model_path}")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"\n⏱️  Early stopping triggered after {epoch + 1} epochs")
                break

    # Save training history
    history_file = output_dir / "training_history.json"
    with open(history_file, 'w') as f:
        # Convert numpy types to native Python types for JSON serialization
        history_serializable = {
            'epochs': training_history['epochs'],
            'train_loss': [float(x) for x in training_history['train_loss']],
            'val_loss': [float(x) for x in training_history['val_loss']],
            'val_metrics': training_history['val_metrics']
        }
        json.dump(history_serializable, f, indent=2)

    print("\n" + "="*80)
    print("✅ DISTILBERT TOKEN CLASSIFIER TRAINING COMPLETE")
    print("="*80)

    return checkpoints_dir / "best_model.pt"


if __name__ == "__main__":
    train_token_classifier()
