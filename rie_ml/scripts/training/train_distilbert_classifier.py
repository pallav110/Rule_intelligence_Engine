#!/usr/bin/env python3
"""
Training Pipeline for Multi-Task DistilBERT Classifier

This script trains the DistilBERT candidate model on the combined training dataset
according to specification Section 8.3.2.

Features:
- Multi-task learning with weighted loss
- Early stopping on validation loss
- Checkpoint saving
- Training metrics logging
- Tensorboard logging (optional)
- Per-task metrics tracking

Usage:
    python train_distilbert_classifier.py [--config config.json]
"""

import json
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from transformers import DistilBertTokenizerFast, get_linear_schedule_with_warmup
from pathlib import Path
from typing import Dict, List, Any, Optional
from tqdm import tqdm
import sys
from datetime import datetime
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ml_models.distilbert_classifier import MultiTaskDistilBERTClassifier
from ml_models import FEEDBACK_TYPE_LABELS, RULE_CATEGORY_LABELS, MODEL_CONFIG, get_label_mappings


class FeedbackDataset(Dataset):
    """PyTorch Dataset for business feedback classification"""

    def __init__(
        self,
        data: List[Dict[str, Any]],
        tokenizer: DistilBertTokenizerFast,
        max_length: int = 256
    ):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        example = self.data[idx]

        # Get text
        text = example.get("feedback_text", "")

        # Tokenize
        encoding = self.tokenizer(
            text,
            add_special_tokens=True,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        # Get labels
        feedback_type = example.get("feedback_type")
        rule_category = example.get("rule_category")
        is_actionable = example.get("is_actionable", False)
        requires_clarification = example.get("requires_clarification", False)

        # Convert to label IDs
        # Note: irrelevant_spam should be filtered out before dataset creation (handled upstream)
        feedback_type_id = FEEDBACK_TYPE_LABELS.get(feedback_type, 0)
        rule_category_id = RULE_CATEGORY_LABELS.get(rule_category if rule_category else "none", 6)  # "none" = 6

        return {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'feedback_type': torch.tensor(feedback_type_id, dtype=torch.long),
            'rule_category': torch.tensor(rule_category_id, dtype=torch.long),
            'is_actionable': torch.tensor(int(is_actionable), dtype=torch.long),
            'requires_clarification': torch.tensor(int(requires_clarification), dtype=torch.long),
        }


class DistilBERTTrainer:
    """Trainer for multi-task DistilBERT classifier"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        print(f"Using device: {self.device}")

        # Initialize model
        self.model = MultiTaskDistilBERTClassifier(
            num_feedback_types=len(FEEDBACK_TYPE_LABELS),
            num_rule_categories=len(RULE_CATEGORY_LABELS),
            dropout=config.get('dropout', 0.1),
            pretrained_model_name=config.get('model_name', 'distilbert-base-uncased')
        )
        self.model.to(self.device)

        # Initialize tokenizer
        self.tokenizer = DistilBertTokenizerFast.from_pretrained(
            config.get('model_name', 'distilbert-base-uncased')
        )

        # Training state
        self.best_val_loss = float('inf')
        self.patience_counter = 0
        self.global_step = 0
        self.epoch = 0

        # Training history
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'train_metrics': [],
            'val_metrics': [],
        }

    def load_data(self, train_path: Path, val_path: Path) -> tuple:
        """Load training and validation data, filtering out irrelevant_spam (handled upstream)"""
        print(f"\nLoading training data from {train_path}...")
        train_data = []
        with open(train_path, 'r') as f:
            for line in f:
                if line.strip():
                    example = json.loads(line)
                    # Filter out irrelevant_spam - handled by upstream spam pre-filter
                    if example.get('feedback_type') != 'irrelevant_spam':
                        train_data.append(example)

        print(f"Loaded {len(train_data)} training examples (excluded spam)")

        print(f"\nLoading validation data from {val_path}...")
        val_data = []
        with open(val_path, 'r') as f:
            for line in f:
                if line.strip():
                    example = json.loads(line)
                    # Filter out irrelevant_spam - handled by upstream spam pre-filter
                    if example.get('feedback_type') != 'irrelevant_spam':
                        val_data.append(example)

        print(f"Loaded {len(val_data)} validation examples (excluded spam)")

        return train_data, val_data

    def create_dataloaders(self, train_data: List[Dict], val_data: List[Dict]) -> tuple:
        """Create PyTorch DataLoaders"""
        train_dataset = FeedbackDataset(
            train_data,
            self.tokenizer,
            max_length=self.config.get('max_length', 256)
        )

        val_dataset = FeedbackDataset(
            val_data,
            self.tokenizer,
            max_length=self.config.get('max_length', 256)
        )

        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.get('batch_size', 16),
            shuffle=True,
            num_workers=0,
            pin_memory=True if self.device.type == 'cuda' else False
        )

        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.get('batch_size', 16),
            shuffle=False,
            num_workers=0,
            pin_memory=True if self.device.type == 'cuda' else False
        )

        return train_loader, val_loader

    def setup_optimizer_and_scheduler(self, train_loader):
        """Setup optimizer and learning rate scheduler"""
        # Optimizer
        optimizer = AdamW(
            self.model.parameters(),
            lr=self.config.get('learning_rate', 2e-5),
            weight_decay=self.config.get('weight_decay', 0.01)
        )

        # Scheduler
        num_training_steps = len(train_loader) * self.config.get('num_epochs', 10)
        num_warmup_steps = self.config.get('warmup_steps', 100)

        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=num_warmup_steps,
            num_training_steps=num_training_steps
        )

        return optimizer, scheduler

    def train_epoch(self, train_loader, optimizer, scheduler) -> Dict[str, float]:
        """Train for one epoch"""
        self.model.train()
        total_loss = 0
        task_losses = {
            'feedback_type': 0,
            'rule_category': 0,
            'is_actionable': 0,
            'requires_clarification': 0,
        }

        progress_bar = tqdm(train_loader, desc=f'Epoch {self.epoch + 1}')

        for batch in progress_bar:
            # Move batch to device
            input_ids = batch['input_ids'].to(self.device)
            attention_mask = batch['attention_mask'].to(self.device)
            feedback_type = batch['feedback_type'].to(self.device)
            rule_category = batch['rule_category'].to(self.device)
            is_actionable = batch['is_actionable'].to(self.device)
            requires_clarification = batch['requires_clarification'].to(self.device)

            # Forward pass
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                feedback_type_labels=feedback_type,
                rule_category_labels=rule_category,
                is_actionable_labels=is_actionable,
                requires_clarification_labels=requires_clarification,
                task_weights=self.config.get('task_weights')
            )

            loss = outputs['loss']

            # Backward pass
            optimizer.zero_grad()
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

            optimizer.step()
            scheduler.step()

            # Track losses
            total_loss += loss.item()
            task_losses['feedback_type'] += outputs['feedback_type_loss'].item()
            task_losses['rule_category'] += outputs['rule_category_loss'].item()
            task_losses['is_actionable'] += outputs['is_actionable_loss'].item()
            task_losses['requires_clarification'] += outputs['requires_clarification_loss'].item()

            self.global_step += 1

            # Update progress bar
            progress_bar.set_postfix({'loss': f'{loss.item():.4f}'})

        # Average losses
        avg_loss = total_loss / len(train_loader)
        for key in task_losses:
            task_losses[key] /= len(train_loader)

        return {
            'total_loss': avg_loss,
            **task_losses
        }

    def evaluate(self, val_loader) -> Dict[str, float]:
        """Evaluate on validation set"""
        self.model.eval()
        total_loss = 0
        task_losses = {
            'feedback_type': 0,
            'rule_category': 0,
            'is_actionable': 0,
            'requires_clarification': 0,
        }

        with torch.no_grad():
            for batch in tqdm(val_loader, desc='Validation'):
                # Move batch to device
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                feedback_type = batch['feedback_type'].to(self.device)
                rule_category = batch['rule_category'].to(self.device)
                is_actionable = batch['is_actionable'].to(self.device)
                requires_clarification = batch['requires_clarification'].to(self.device)

                # Forward pass
                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    feedback_type_labels=feedback_type,
                    rule_category_labels=rule_category,
                    is_actionable_labels=is_actionable,
                    requires_clarification_labels=requires_clarification,
                    task_weights=self.config.get('task_weights')
                )

                loss = outputs['loss']

                # Track losses
                total_loss += loss.item()
                task_losses['feedback_type'] += outputs['feedback_type_loss'].item()
                task_losses['rule_category'] += outputs['rule_category_loss'].item()
                task_losses['is_actionable'] += outputs['is_actionable_loss'].item()
                task_losses['requires_clarification'] += outputs['requires_clarification_loss'].item()

        # Average losses
        avg_loss = total_loss / len(val_loader)
        for key in task_losses:
            task_losses[key] /= len(val_loader)

        return {
            'total_loss': avg_loss,
            **task_losses
        }

    def save_checkpoint(self, checkpoint_dir: Path, is_best: bool = False):
        """Save model checkpoint"""
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint = {
            'epoch': self.epoch,
            'global_step': self.global_step,
            'model_state_dict': self.model.state_dict(),
            'best_val_loss': self.best_val_loss,
            'config': self.config,
            'label_mappings': get_label_mappings(),
        }

        # Save latest checkpoint
        checkpoint_path = checkpoint_dir / f'checkpoint_epoch_{self.epoch + 1}.pt'
        torch.save(checkpoint, checkpoint_path)
        print(f"Saved checkpoint to {checkpoint_path}")

        # Save best checkpoint
        if is_best:
            best_path = checkpoint_dir / 'best_model.pt'
            torch.save(checkpoint, best_path)
            print(f"Saved best model to {best_path}")

    def train(self, train_path: Path, val_path: Path, output_dir: Path):
        """Main training loop"""
        print("\n" + "=" * 80)
        print("TRAINING MULTI-TASK DISTILBERT CLASSIFIER")
        print("=" * 80)

        # Load data
        train_data, val_data = self.load_data(train_path, val_path)

        # Create dataloaders
        train_loader, val_loader = self.create_dataloaders(train_data, val_data)

        # Setup optimizer and scheduler
        optimizer, scheduler = self.setup_optimizer_and_scheduler(train_loader)

        # Training loop
        num_epochs = self.config.get('num_epochs', 10)
        patience = self.config.get('early_stopping_patience', 3)

        print(f"\nStarting training for {num_epochs} epochs...")
        print(f"Early stopping patience: {patience}")
        print(f"Batch size: {self.config.get('batch_size', 16)}")
        print(f"Learning rate: {self.config.get('learning_rate', 2e-5)}")

        for epoch in range(num_epochs):
            self.epoch = epoch

            # Train
            train_metrics = self.train_epoch(train_loader, optimizer, scheduler)
            self.history['train_loss'].append(train_metrics['total_loss'])
            self.history['train_metrics'].append(train_metrics)

            # Validate
            val_metrics = self.evaluate(val_loader)
            self.history['val_loss'].append(val_metrics['total_loss'])
            self.history['val_metrics'].append(val_metrics)

            # Print epoch summary
            print(f"\nEpoch {epoch + 1}/{num_epochs}:")
            print(f"  Train Loss: {train_metrics['total_loss']:.4f}")
            print(f"  Val Loss: {val_metrics['total_loss']:.4f}")
            print(f"  Train Task Losses: FT={train_metrics['feedback_type']:.4f}, "
                  f"RC={train_metrics['rule_category']:.4f}, "
                  f"IA={train_metrics['is_actionable']:.4f}, "
                  f"RC={train_metrics['requires_clarification']:.4f}")

            # Early stopping check
            if val_metrics['total_loss'] < self.best_val_loss:
                self.best_val_loss = val_metrics['total_loss']
                self.patience_counter = 0
                self.save_checkpoint(output_dir / 'checkpoints', is_best=True)
            else:
                self.patience_counter += 1
                self.save_checkpoint(output_dir / 'checkpoints', is_best=False)

                if self.patience_counter >= patience:
                    print(f"\nEarly stopping triggered after {epoch + 1} epochs")
                    break

        # Save training history
        history_path = output_dir / 'training_history.json'
        with open(history_path, 'w') as f:
            json.dump(self.history, f, indent=2)
        print(f"\nTraining history saved to {history_path}")

        print("\n" + "=" * 80)
        print("TRAINING COMPLETE")
        print("=" * 80)
        print(f"Best validation loss: {self.best_val_loss:.4f}")
        print(f"Total epochs: {self.epoch + 1}")
        print(f"Best model saved to: {output_dir / 'checkpoints' / 'best_model.pt'}")


def main():
    # Configuration
    config = MODEL_CONFIG.copy()

    # Paths
    base_dir = Path(__file__).parent.parent.parent / "dataset_generation" / "output"
    output_dir = Path(__file__).parent.parent.parent / "models" / "distilbert_candidate"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Combine training data from all domains
    print("Combining training data from all domains...")
    all_train_data = []
    all_val_data = []

    for domain in ["ecommerce", "customer_support", "saas_subscription"]:
        train_path = base_dir / domain / "train.jsonl"
        val_path = base_dir / domain / "val.jsonl"

        with open(train_path, 'r') as f:
            for line in f:
                if line.strip():
                    all_train_data.append(json.loads(line))

        with open(val_path, 'r') as f:
            for line in f:
                if line.strip():
                    all_val_data.append(json.loads(line))

    # Save combined datasets
    combined_train_path = output_dir / "train_combined.jsonl"
    combined_val_path = output_dir / "val_combined.jsonl"

    with open(combined_train_path, 'w') as f:
        for example in all_train_data:
            f.write(json.dumps(example) + '\n')

    with open(combined_val_path, 'w') as f:
        for example in all_val_data:
            f.write(json.dumps(example) + '\n')

    print(f"Combined {len(all_train_data)} training examples")
    print(f"Combined {len(all_val_data)} validation examples")
    print(f"Saved to {output_dir}")

    # Initialize trainer
    trainer = DistilBERTTrainer(config)

    # Train
    trainer.train(combined_train_path, combined_val_path, output_dir)


if __name__ == "__main__":
    main()
