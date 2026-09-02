"""
Unified model loading utilities for DistilBERT, BERT, and RoBERTa classifiers
"""

import torch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ml_models import FEEDBACK_TYPE_LABELS, RULE_CATEGORY_LABELS


class MultiTaskBERTClassifier(torch.nn.Module):
    """Multi-task BERT classifier (matches train_bert_classifier.py architecture)"""

    def __init__(self, num_feedback_types=4, num_rule_categories=16, dropout=0.1):
        super().__init__()
        from transformers import AutoModel

        self.bert = AutoModel.from_pretrained('bert-base-uncased')
        hidden_size = self.bert.config.hidden_size

        # Task-specific heads - MUST match training script
        self.feedback_type_head = torch.nn.Sequential(
            torch.nn.Linear(hidden_size, 256),
            torch.nn.ReLU(),
            torch.nn.Dropout(dropout),
            torch.nn.Linear(256, num_feedback_types)
        )

        self.rule_category_head = torch.nn.Sequential(
            torch.nn.Linear(hidden_size, 256),
            torch.nn.ReLU(),
            torch.nn.Dropout(dropout),
            torch.nn.Linear(256, num_rule_categories)
        )

        self.is_actionable_head = torch.nn.Sequential(
            torch.nn.Linear(hidden_size, 128),
            torch.nn.ReLU(),
            torch.nn.Dropout(dropout),
            torch.nn.Linear(128, 1)
        )

        self.requires_clarification_head = torch.nn.Sequential(
            torch.nn.Linear(hidden_size, 128),
            torch.nn.ReLU(),
            torch.nn.Dropout(dropout),
            torch.nn.Linear(128, 1)
        )

    def forward(self, input_ids, attention_mask=None, **kwargs):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.last_hidden_state[:, 0, :]

        return {
            'feedback_type_logits': self.feedback_type_head(pooled_output),
            'rule_category_logits': self.rule_category_head(pooled_output),
            'is_actionable_logits': self.is_actionable_head(pooled_output),
            'requires_clarification_logits': self.requires_clarification_head(pooled_output),
        }


class MultiTaskRoBERTaClassifier(torch.nn.Module):
    """Multi-task RoBERTa classifier (matches train_roberta_classifier.py architecture)"""

    def __init__(self, num_feedback_types=4, num_rule_categories=16, dropout=0.1):
        super().__init__()
        from transformers import AutoModel

        self.roberta = AutoModel.from_pretrained('roberta-base')
        hidden_size = self.roberta.config.hidden_size

        # Task-specific heads with LayerNorm - MUST match training script
        self.feedback_type_head = torch.nn.Sequential(
            torch.nn.Linear(hidden_size, 512),
            torch.nn.ReLU(),
            torch.nn.LayerNorm(512),
            torch.nn.Dropout(0.15),
            torch.nn.Linear(512, 256),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(256, num_feedback_types)
        )

        self.rule_category_head = torch.nn.Sequential(
            torch.nn.Linear(hidden_size, 512),
            torch.nn.ReLU(),
            torch.nn.LayerNorm(512),
            torch.nn.Dropout(0.15),
            torch.nn.Linear(512, 256),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(256, num_rule_categories)
        )

        self.is_actionable_head = torch.nn.Sequential(
            torch.nn.Linear(hidden_size, 256),
            torch.nn.ReLU(),
            torch.nn.LayerNorm(256),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(256, 128),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(128, 1)
        )

        self.requires_clarification_head = torch.nn.Sequential(
            torch.nn.Linear(hidden_size, 256),
            torch.nn.ReLU(),
            torch.nn.LayerNorm(256),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(256, 128),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(128, 1)
        )

    def forward(self, input_ids, attention_mask=None, **kwargs):
        outputs = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.last_hidden_state[:, 0, :]

        return {
            'feedback_type_logits': self.feedback_type_head(pooled_output),
            'rule_category_logits': self.rule_category_head(pooled_output),
            'is_actionable_logits': self.is_actionable_head(pooled_output),
            'requires_clarification_logits': self.requires_clarification_head(pooled_output),
        }


def load_model(model_type, model_path, device='cpu'):
    """Load a trained model checkpoint"""
    checkpoint = torch.load(model_path, map_location=device)

    if model_type == 'distilbert':
        from ml_models.distilbert_classifier import MultiTaskDistilBERTClassifier
        model = MultiTaskDistilBERTClassifier(
            num_feedback_types=len(FEEDBACK_TYPE_LABELS),
            num_rule_categories=len(RULE_CATEGORY_LABELS)
        )
    elif model_type == 'bert':
        model = MultiTaskBERTClassifier(
            num_feedback_types=len(FEEDBACK_TYPE_LABELS),
            num_rule_categories=len(RULE_CATEGORY_LABELS)
        )
    elif model_type == 'roberta':
        model = MultiTaskRoBERTaClassifier(
            num_feedback_types=len(FEEDBACK_TYPE_LABELS),
            num_rule_categories=len(RULE_CATEGORY_LABELS)
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()

    return model
