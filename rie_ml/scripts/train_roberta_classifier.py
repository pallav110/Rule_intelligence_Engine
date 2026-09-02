#!/usr/bin/env python3
"""
Multi-Task RoBERTa Classifier Training Pipeline

Trains RoBERTa-base as an alternative candidate model
for comparison with DistilBERT and BERT.
"""

import json
import torch
import numpy as np
from torch.utils.data import DataLoader, Dataset
from pathlib import Path
import sys
from tqdm import tqdm
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ml_models import (
    FEEDBACK_TYPE_LABELS,
    RULE_CATEGORY_LABELS,
    FEEDBACK_TYPE_LABEL2ID,
    RULE_CATEGORY_LABEL2ID
)


class MultiTaskRoBERTaClassifier(torch.nn.Module):
    """Multi-task RoBERTa classifier"""

    def __init__(self, num_feedback_types, num_rule_categories):
        super().__init__()
        from transformers import AutoModel

        self.roberta = AutoModel.from_pretrained('roberta-base')

        hidden_size = self.roberta.config.hidden_size

        # Task-specific heads with improved architecture
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
            torch.nn.Dropout(0.05),
            torch.nn.Linear(128, 1)
        )

        self.requires_clarification_head = torch.nn.Sequential(
            torch.nn.Linear(hidden_size, 256),
            torch.nn.ReLU(),
            torch.nn.LayerNorm(256),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(256, 128),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.05),
            torch.nn.Linear(128, 1)
        )

    def forward(self, input_ids, attention_mask):
        """Forward pass"""
        outputs = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.pooler_output

        return {
            'feedback_type_logits': self.feedback_type_head(pooled_output),
            'rule_category_logits': self.rule_category_head(pooled_output),
            'is_actionable_logits': self.is_actionable_head(pooled_output),
            'requires_clarification_logits': self.requires_clarification_head(pooled_output)
        }


class FeedbackDataset(Dataset):
    """Feedback dataset for training"""

    def __init__(self, data, tokenizer, max_length=256):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]

        encoding = self.tokenizer(
            item['feedback_text'],
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'feedback_type': torch.tensor(
                FEEDBACK_TYPE_LABEL2ID.get(item['feedback_type'], 0),
                dtype=torch.long
            ),
            'rule_category': torch.tensor(
                RULE_CATEGORY_LABEL2ID.get(item['rule_category'], 0),
                dtype=torch.long
            ),
            'is_actionable': torch.tensor(item.get('is_actionable', 1), dtype=torch.float),
            'requires_clarification': torch.tensor(
                item.get('requires_clarification', 0),
                dtype=torch.float
            )
        }


def train_roberta_model():
    """Train multi-task RoBERTa model"""
    from transformers import RobertaTokenizerFast
    import torch.optim as optim

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Paths
    output_dir = Path(__file__).parent.parent / "models" / "roberta_candidate"
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir = output_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    # Load data from all domains
    print("\n📦 Loading training data from all domains...")
    train_data = []
    domains = ["ecommerce", "customer_support", "saas_subscription"]

    for domain in domains:
        domain_path = Path(__file__).parent.parent / "dataset_generation" / "output" / domain / "train.jsonl"
        if domain_path.exists():
            with open(domain_path, 'r') as f:
                for line in f:
                    if line.strip():
                        train_data.append(json.loads(line))

    print(f"Loaded {len(train_data)} training examples")

    # Load validation data
    val_data = []
    for domain in domains:
        domain_path = Path(__file__).parent.parent / "dataset_generation" / "output" / domain / "val.jsonl"
        if domain_path.exists():
            with open(domain_path, 'r') as f:
                for line in f:
                    if line.strip():
                        val_data.append(json.loads(line))

    print(f"Loaded {len(val_data)} validation examples")

    # Create tokenizer and datasets
    tokenizer = RobertaTokenizerFast.from_pretrained('roberta-base')
    train_dataset = FeedbackDataset(train_data, tokenizer)
    val_dataset = FeedbackDataset(val_data, tokenizer)

    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=8)

    # Initialize model
    model = MultiTaskRoBERTaClassifier(
        num_feedback_types=len(FEEDBACK_TYPE_LABELS),
        num_rule_categories=len(RULE_CATEGORY_LABELS)
    )
    model.to(device)

    # Training setup
    optimizer = optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=5,
        eta_min=1e-6
    )

    # Loss weights for multi-task learning
    loss_weights = {
        'feedback_type': 1.0,
        'rule_category': 0.8,
        'is_actionable': 0.7,
        'requires_clarification': 0.6
    }

    criterion_classification = torch.nn.CrossEntropyLoss()
    criterion_binary = torch.nn.BCEWithLogitsLoss()

    best_val_loss = float('inf')
    patience = 3
    patience_counter = 0

    # Training loop
    print("\n" + "="*80)
    print("TRAINING MULTI-TASK ROBERTA CLASSIFIER")
    print("="*80)

    for epoch in range(5):
        print(f"\n📚 Epoch {epoch + 1}/5")

        # Training
        model.train()
        train_loss = 0.0

        for batch in tqdm(train_loader, desc="Training"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            feedback_type = batch['feedback_type'].to(device)
            rule_category = batch['rule_category'].to(device)
            is_actionable = batch['is_actionable'].to(device)
            requires_clarification = batch['requires_clarification'].to(device)

            optimizer.zero_grad()

            outputs = model(input_ids, attention_mask)

            # Compute losses
            loss_ft = criterion_classification(
                outputs['feedback_type_logits'],
                feedback_type
            ) * loss_weights['feedback_type']

            loss_rc = criterion_classification(
                outputs['rule_category_logits'],
                rule_category
            ) * loss_weights['rule_category']

            loss_ia = criterion_binary(
                outputs['is_actionable_logits'].squeeze(),
                is_actionable
            ) * loss_weights['is_actionable']

            loss_reqc = criterion_binary(
                outputs['requires_clarification_logits'].squeeze(),
                requires_clarification
            ) * loss_weights['requires_clarification']

            loss = loss_ft + loss_rc + loss_ia + loss_reqc

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            train_loss += loss.item()

        avg_train_loss = train_loss / len(train_loader)
        print(f"Training Loss: {avg_train_loss:.4f}")

        # Validation
        model.eval()
        val_loss = 0.0

        with torch.no_grad():
            for batch in tqdm(val_loader, desc="Validation"):
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                feedback_type = batch['feedback_type'].to(device)
                rule_category = batch['rule_category'].to(device)
                is_actionable = batch['is_actionable'].to(device)
                requires_clarification = batch['requires_clarification'].to(device)

                outputs = model(input_ids, attention_mask)

                loss_ft = criterion_classification(
                    outputs['feedback_type_logits'],
                    feedback_type
                ) * loss_weights['feedback_type']

                loss_rc = criterion_classification(
                    outputs['rule_category_logits'],
                    rule_category
                ) * loss_weights['rule_category']

                loss_ia = criterion_binary(
                    outputs['is_actionable_logits'].squeeze(),
                    is_actionable
                ) * loss_weights['is_actionable']

                loss_reqc = criterion_binary(
                    outputs['requires_clarification_logits'].squeeze(),
                    requires_clarification
                ) * loss_weights['requires_clarification']

                loss = loss_ft + loss_rc + loss_ia + loss_reqc
                val_loss += loss.item()

        scheduler.step()
        avg_val_loss = val_loss / len(val_loader)
        print(f"Validation Loss: {avg_val_loss:.4f}")

        # Save best model
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            patience_counter = 0

            checkpoint = {
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'epoch': epoch,
                'loss': avg_val_loss
            }

            best_model_path = checkpoints_dir / "best_model.pt"
            torch.save(checkpoint, best_model_path)
            print(f"✅ Saved best model to {best_model_path}")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"\n⏱️  Early stopping triggered after {epoch + 1} epochs")
                break

    print("\n" + "="*80)
    print("✅ ROBERTA TRAINING COMPLETE")
    print("="*80)

    return checkpoints_dir / "best_model.pt"


if __name__ == "__main__":
    train_roberta_model()
