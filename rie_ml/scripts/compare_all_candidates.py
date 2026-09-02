#!/usr/bin/env python3
"""
Unified Model Comparison Framework

Compares all three candidate models (DistilBERT, BERT, RoBERTa)
on the frozen test set and generates comparison reports.
"""

import json
import torch
import numpy as np
from torch.utils.data import DataLoader
from pathlib import Path
import sys
from tqdm import tqdm
from typing import Dict, List, Any
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ml_models import (
    FEEDBACK_TYPE_LABELS,
    RULE_CATEGORY_LABELS,
    FEEDBACK_TYPE_ID2LABEL,
    RULE_CATEGORY_ID2LABEL
)


class ModelEvaluator:
    """Unified evaluator for all candidate models"""

    def __init__(self, model_path: Path, model_type: str, device: str = 'cpu'):
        """
        Initialize evaluator

        Args:
            model_path: Path to model checkpoint
            model_type: 'distilbert', 'bert', or 'roberta'
            device: 'cpu' or 'cuda'
        """
        self.device = torch.device(device)
        self.model_type = model_type
        self.model_path = model_path

        print(f"🔧 Loading {model_type.upper()} model from {model_path}...")

        from ml_models.model_loader import load_model
        self.model = load_model(model_type, model_path, device)

        print(f"✅ {model_type.upper()} model loaded successfully!")

    def evaluate_on_testset(self, test_loader: DataLoader) -> Dict[str, Any]:
        """Evaluate model on test set"""
        print(f"\n📊 Evaluating {self.model_type.upper()} on test set...")

        all_predictions = {
            'feedback_type': [],
            'rule_category': [],
            'is_actionable': [],
            'requires_clarification': []
        }

        all_labels = {
            'feedback_type': [],
            'rule_category': [],
            'is_actionable': [],
            'requires_clarification': []
        }

        with torch.no_grad():
            for batch in tqdm(test_loader, desc="Evaluating"):
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)

                outputs = self.model(input_ids, attention_mask)

                # Feedback Type
                ft_preds = torch.argmax(torch.softmax(outputs['feedback_type_logits'], dim=-1), dim=-1)
                all_predictions['feedback_type'].append(ft_preds.cpu().numpy())
                all_labels['feedback_type'].append(batch['feedback_type'].numpy())

                # Rule Category
                rc_preds = torch.argmax(torch.softmax(outputs['rule_category_logits'], dim=-1), dim=-1)
                all_predictions['rule_category'].append(rc_preds.cpu().numpy())
                all_labels['rule_category'].append(batch['rule_category'].numpy())

                # Is Actionable
                ia_preds = (torch.sigmoid(outputs['is_actionable_logits'].squeeze()) > 0.5).long()
                all_predictions['is_actionable'].append(ia_preds.cpu().numpy())
                all_labels['is_actionable'].append(batch['is_actionable'].numpy())

                # Requires Clarification
                rc_preds_binary = (torch.sigmoid(outputs['requires_clarification_logits'].squeeze()) > 0.5).long()
                all_predictions['requires_clarification'].append(rc_preds_binary.cpu().numpy())
                all_labels['requires_clarification'].append(batch['requires_clarification'].numpy())

        # Concatenate all batches
        for key in all_predictions:
            all_predictions[key] = np.concatenate(all_predictions[key], axis=0)
            all_labels[key] = np.concatenate(all_labels[key], axis=0)

        return self._compute_metrics(all_predictions, all_labels)

    def _compute_metrics(self, predictions: Dict, labels: Dict) -> Dict[str, Any]:
        """Compute comprehensive metrics"""
        results = {}

        # Feedback Type
        unique_classes = np.unique(np.concatenate([labels['feedback_type'], predictions['feedback_type']]))
        ft_labels = [FEEDBACK_TYPE_ID2LABEL[i] if i < len(FEEDBACK_TYPE_ID2LABEL) else f"Class_{i}" for i in unique_classes]

        results['feedback_type'] = {
            'accuracy': float(accuracy_score(labels['feedback_type'], predictions['feedback_type'])),
            'macro_f1': float(f1_score(labels['feedback_type'], predictions['feedback_type'], average='macro', zero_division=0, labels=unique_classes)),
            'weighted_f1': float(f1_score(labels['feedback_type'], predictions['feedback_type'], average='weighted', zero_division=0, labels=unique_classes)),
            'macro_precision': float(precision_score(labels['feedback_type'], predictions['feedback_type'], average='macro', zero_division=0, labels=unique_classes)),
            'macro_recall': float(recall_score(labels['feedback_type'], predictions['feedback_type'], average='macro', zero_division=0, labels=unique_classes)),
        }

        # Rule Category
        unique_classes_rc = np.unique(np.concatenate([labels['rule_category'], predictions['rule_category']]))
        rc_labels = [RULE_CATEGORY_ID2LABEL[i] if i < len(RULE_CATEGORY_ID2LABEL) else f"Class_{i}" for i in unique_classes_rc]

        results['rule_category'] = {
            'accuracy': float(accuracy_score(labels['rule_category'], predictions['rule_category'])),
            'macro_f1': float(f1_score(labels['rule_category'], predictions['rule_category'], average='macro', zero_division=0, labels=unique_classes_rc)),
            'weighted_f1': float(f1_score(labels['rule_category'], predictions['rule_category'], average='weighted', zero_division=0, labels=unique_classes_rc)),
            'macro_precision': float(precision_score(labels['rule_category'], predictions['rule_category'], average='macro', zero_division=0, labels=unique_classes_rc)),
            'macro_recall': float(recall_score(labels['rule_category'], predictions['rule_category'], average='macro', zero_division=0, labels=unique_classes_rc)),
        }

        # Is Actionable
        results['is_actionable'] = {
            'accuracy': float(accuracy_score(labels['is_actionable'], predictions['is_actionable'])),
            'precision': float(precision_score(labels['is_actionable'], predictions['is_actionable'], zero_division=0)),
            'recall': float(recall_score(labels['is_actionable'], predictions['is_actionable'], zero_division=0)),
            'f1': float(f1_score(labels['is_actionable'], predictions['is_actionable'], zero_division=0)),
        }

        # Requires Clarification
        results['requires_clarification'] = {
            'accuracy': float(accuracy_score(labels['requires_clarification'], predictions['requires_clarification'])),
            'precision': float(precision_score(labels['requires_clarification'], predictions['requires_clarification'], zero_division=0)),
            'recall': float(recall_score(labels['requires_clarification'], predictions['requires_clarification'], zero_division=0)),
            'f1': float(f1_score(labels['requires_clarification'], predictions['requires_clarification'], zero_division=0)),
        }

        return results


def compare_all_models():
    """Compare all three candidate models"""
    from transformers import DistilBertTokenizerFast

    # Define FeedbackDataset locally to avoid import issues
    class FeedbackDataset:
        def __init__(self, data, tokenizer, max_length=256):
            self.data = data
            self.tokenizer = tokenizer
            self.max_length = max_length

        def __len__(self):
            return len(self.data)

        def __getitem__(self, idx):
            from ml_models import FEEDBACK_TYPE_LABEL2ID, RULE_CATEGORY_LABEL2ID
            item = self.data[idx]

            # Use feedback_text field
            text = item.get('feedback_text', item.get('text', ''))

            encoding = self.tokenizer(
                text,
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

    # Load test data
    print("📦 Loading frozen test set...")
    test_data = []
    domains = ["ecommerce", "customer_support", "saas_subscription"]

    for domain in domains:
        domain_path = Path(__file__).parent.parent / "dataset_generation" / "output" / domain / "test.jsonl"
        if domain_path.exists():
            with open(domain_path, 'r') as f:
                for line in f:
                    if line.strip():
                        test_data.append(json.loads(line))

    print(f"Loaded {len(test_data)} test examples\n")

    # Create dataloader
    tokenizer = DistilBertTokenizerFast.from_pretrained('distilbert-base-uncased')
    test_dataset = FeedbackDataset(test_data, tokenizer, max_length=256)
    test_loader = DataLoader(test_dataset, batch_size=16, shuffle=False)

    # Evaluate all models
    results = {}
    models_config = [
        ('distilbert', Path(__file__).parent.parent / "models" / "distilbert_candidate" / "checkpoints" / "best_model.pt"),
        ('bert', Path(__file__).parent.parent / "models" / "bert_candidate" / "checkpoints" / "best_model.pt"),
        ('roberta', Path(__file__).parent.parent / "models" / "roberta_candidate" / "checkpoints" / "best_model.pt"),
    ]

    for model_type, model_path in models_config:
        if model_path.exists():
            try:
                evaluator = ModelEvaluator(model_path, model_type)
                results[model_type] = evaluator.evaluate_on_testset(test_loader)
            except Exception as e:
                print(f"❌ Error evaluating {model_type}: {e}")
        else:
            print(f"⚠️  {model_type} model not found at {model_path}")

    # Generate comparison report
    print("\n" + "="*80)
    print("MODEL COMPARISON REPORT")
    print("="*80)

    comparison_report = {
        "timestamp": "2026-09-01T09:33:00Z",
        "test_set_size": len(test_data),
        "models": results,
        "summary": {}
    }

    # Calculate summary statistics
    for task in ['feedback_type', 'rule_category', 'is_actionable', 'requires_clarification']:
        accuracies = []
        for model_type, model_results in results.items():
            if task in model_results:
                accuracies.append((model_type, model_results[task].get('accuracy', 0)))

        if accuracies:
            accuracies.sort(key=lambda x: x[1], reverse=True)
            comparison_report['summary'][task] = {
                'best_model': accuracies[0][0],
                'best_accuracy': accuracies[0][1],
                'all_models': dict(accuracies)
            }

    # Print results
    print("\n📊 RESULTS BY TASK\n")

    for task in ['feedback_type', 'rule_category', 'is_actionable', 'requires_clarification']:
        print(f"\n{task.upper().replace('_', ' ')}")
        print("-" * 60)

        for model_type, model_results in results.items():
            if task in model_results:
                metrics = model_results[task]
                acc = metrics.get('accuracy', 0)
                f1 = metrics.get('macro_f1') or metrics.get('f1', 0)
                print(f"  {model_type:15} | Acc: {acc:6.2%} | F1: {f1:6.4f}")

    # Save comparison report
    report_path = Path(__file__).parent.parent / "models" / "model_comparison_report.json"
    with open(report_path, 'w') as f:
        json.dump(comparison_report, f, indent=2)

    print(f"\n💾 Comparison report saved to {report_path}")

    print("\n" + "="*80)
    print("✅ MODEL COMPARISON COMPLETE")
    print("="*80)

    return comparison_report


if __name__ == "__main__":
    compare_all_models()
