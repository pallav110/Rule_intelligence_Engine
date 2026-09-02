#!/usr/bin/env python3
"""
Model Loader for Token Classification (Rule Extraction)

Unified loader supporting DistilBERT token classifier for BIO token prediction.
"""

import torch
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class DistilBERTTokenClassifier(torch.nn.Module):
    """DistilBERT for token-level BIO classification."""

    def __init__(self, num_labels=16, dropout=0.1):
        super().__init__()
        from transformers import AutoModel

        self.distilbert = AutoModel.from_pretrained('distilbert-base-uncased')
        hidden_size = self.distilbert.config.hidden_size

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


def load_token_classifier(model_path, device='cpu'):
    """
    Load a trained token classifier checkpoint.

    Args:
        model_path: Path to checkpoint
        device: 'cpu' or 'cuda'

    Returns:
        Tuple of (model, bio_labels, label2id, id2label)
    """
    checkpoint = torch.load(model_path, map_location=device)

    num_labels = checkpoint.get('num_labels', 16)
    bio_labels = checkpoint.get('bio_labels', [])
    label2id = checkpoint.get('label2id', {})

    model = DistilBERTTokenClassifier(num_labels=num_labels)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()

    id2label = {int(k): v for k, v in enumerate(bio_labels)}

    return model, bio_labels, label2id, id2label


def load_bio_labels(bio_labels_file):
    """Load BIO label mappings."""
    with open(bio_labels_file, 'r') as f:
        mapping = json.load(f)
    return mapping['labels'], mapping['label2id'], {int(k): v for k, v in mapping['id2label'].items()}
