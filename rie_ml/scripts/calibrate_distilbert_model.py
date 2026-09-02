#!/usr/bin/env python3
"""
Calibration Script for Multi-Task DistilBERT Classifier

This script implements temperature scaling calibration for each of the 4 prediction tasks
independently, as required by specification Section 8.3.2.

Temperature scaling adjusts raw model probabilities to be better calibrated:
    calibrated_prob = softmax(logits / temperature)

Each task gets its own temperature parameter optimized on the validation set.

Usage:
    python calibrate_distilbert_model.py --model_path <path_to_best_model.pt>
"""

import json
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from pathlib import Path
import sys
from typing import Dict, List, Any
import numpy as np
from tqdm import tqdm
from scipy.optimize import minimize

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ml_models.distilbert_classifier import MultiTaskDistilBERTClassifier
from ml_models import FEEDBACK_TYPE_LABELS, RULE_CATEGORY_LABELS


class TemperatureScaler:
    """Temperature scaling calibrator for classification tasks"""

    def __init__(self):
        self.temperature = 1.0

    def fit(self, logits: np.ndarray, labels: np.ndarray):
        """
        Optimize temperature on validation set to minimize NLL.

        Args:
            logits: Raw model logits (N, num_classes)
            labels: Ground truth labels (N,)
        """
        def negative_log_likelihood(temp):
            temp = temp[0]
            scaled_logits = logits / temp
            # Compute softmax
            exp_logits = np.exp(scaled_logits - np.max(scaled_logits, axis=1, keepdims=True))
            probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
            # Compute NLL
            n = len(labels)
            nll = -np.sum(np.log(probs[np.arange(n), labels] + 1e-12)) / n
            return nll

        # Optimize temperature
        result = minimize(negative_log_likelihood, [1.0], bounds=[(0.01, 10.0)])
        self.temperature = result.x[0]

        return self

    def transform(self, logits: np.ndarray) -> np.ndarray:
        """Apply temperature scaling to logits"""
        scaled_logits = logits / self.temperature
        exp_logits = np.exp(scaled_logits - np.max(scaled_logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
        return probs


class BinaryTemperatureScaler:
    """Temperature scaling for binary classification tasks"""

    def __init__(self):
        self.temperature = 1.0

    def fit(self, logits: np.ndarray, labels: np.ndarray):
        """Optimize temperature for binary task"""
        def negative_log_likelihood(temp):
            temp = temp[0]
            scaled_logits = logits / temp
            probs = 1 / (1 + np.exp(-scaled_logits))
            # Binary cross entropy
            epsilon = 1e-12
            bce = -np.mean(
                labels * np.log(probs + epsilon) +
                (1 - labels) * np.log(1 - probs + epsilon)
            )
            return bce

        result = minimize(negative_log_likelihood, [1.0], bounds=[(0.01, 10.0)])
        self.temperature = result.x[0]

        return self

    def transform(self, logits: np.ndarray) -> np.ndarray:
        """Apply temperature scaling to binary logits"""
        scaled_logits = logits / self.temperature
        probs = 1 / (1 + np.exp(-scaled_logits))
        return probs


def compute_ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """
    Compute Expected Calibration Error (ECE).

    Args:
        probs: Predicted probabilities (N, num_classes)
        labels: Ground truth labels (N,)
        n_bins: Number of bins for calibration

    Returns:
        ECE value
    """
    confidences = np.max(probs, axis=1)
    predictions = np.argmax(probs, axis=1)
    accuracies = (predictions == labels)

    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(confidences, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    ece = 0.0
    for i in range(n_bins):
        mask = bin_indices == i
        if np.sum(mask) > 0:
            avg_confidence = np.mean(confidences[mask])
            avg_accuracy = np.mean(accuracies[mask])
            bin_weight = np.sum(mask) / len(confidences)
            ece += bin_weight * np.abs(avg_confidence - avg_accuracy)

    return ece


def compute_binary_ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """Compute ECE for binary classification"""
    confidences = np.maximum(probs, 1 - probs)
    predictions = (probs > 0.5).astype(int)
    accuracies = (predictions == labels)

    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(confidences, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    ece = 0.0
    for i in range(n_bins):
        mask = bin_indices == i
        if np.sum(mask) > 0:
            avg_confidence = np.mean(confidences[mask])
            avg_accuracy = np.mean(accuracies[mask])
            bin_weight = np.sum(mask) / len(confidences)
            ece += bin_weight * np.abs(avg_confidence - avg_accuracy)

    return ece


class DistilBERTCalibrator:
    """Main calibrator for multi-task DistilBERT model"""

    def __init__(self, model_path: Path, device: str = 'cpu'):
        self.device = torch.device(device)

        # Load trained model
        print(f"Loading model from {model_path}...")
        checkpoint = torch.load(model_path, map_location=self.device)

        self.model = MultiTaskDistilBERTClassifier(
            num_feedback_types=len(FEEDBACK_TYPE_LABELS),
            num_rule_categories=len(RULE_CATEGORY_LABELS)
        )
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.to(self.device)
        self.model.eval()

        # Calibrators for each task
        self.feedback_type_scaler = TemperatureScaler()
        self.rule_category_scaler = TemperatureScaler()
        self.is_actionable_scaler = BinaryTemperatureScaler()
        self.requires_clarification_scaler = BinaryTemperatureScaler()

        print("✅ Model loaded successfully")

    def collect_predictions(self, val_loader: DataLoader) -> Dict[str, np.ndarray]:
        """Collect all predictions and labels from validation set"""
        print("\n📊 Collecting predictions on validation set...")

        all_logits = {
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
            for batch in tqdm(val_loader, desc="Collecting"):
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)

                outputs = self.model(input_ids, attention_mask)

                # Collect logits
                all_logits['feedback_type'].append(
                    outputs['feedback_type_logits'].cpu().numpy()
                )
                all_logits['rule_category'].append(
                    outputs['rule_category_logits'].cpu().numpy()
                )
                all_logits['is_actionable'].append(
                    outputs['is_actionable_logits'].squeeze(-1).cpu().numpy()
                )
                all_logits['requires_clarification'].append(
                    outputs['requires_clarification_logits'].squeeze(-1).cpu().numpy()
                )

                # Collect labels
                all_labels['feedback_type'].append(batch['feedback_type'].numpy())
                all_labels['rule_category'].append(batch['rule_category'].numpy())
                all_labels['is_actionable'].append(batch['is_actionable'].numpy())
                all_labels['requires_clarification'].append(batch['requires_clarification'].numpy())

        # Concatenate all batches
        for key in all_logits:
            all_logits[key] = np.concatenate(all_logits[key], axis=0)
            all_labels[key] = np.concatenate(all_labels[key], axis=0)

        return all_logits, all_labels

    def calibrate(self, val_loader: DataLoader) -> Dict[str, Any]:
        """Calibrate all tasks independently"""
        print("\n" + "=" * 80)
        print("CALIBRATING MULTI-TASK DISTILBERT CLASSIFIER")
        print("=" * 80)

        # Collect predictions
        all_logits, all_labels = self.collect_predictions(val_loader)

        results = {}

        # Task 1: Feedback Type
        print("\n🔧 Calibrating Feedback Type...")
        uncal_probs = torch.softmax(
            torch.from_numpy(all_logits['feedback_type']), dim=-1
        ).numpy()
        ece_before = compute_ece(uncal_probs, all_labels['feedback_type'])

        self.feedback_type_scaler.fit(
            all_logits['feedback_type'],
            all_labels['feedback_type']
        )

        cal_probs = self.feedback_type_scaler.transform(all_logits['feedback_type'])
        ece_after = compute_ece(cal_probs, all_labels['feedback_type'])

        results['feedback_type'] = {
            'temperature': float(self.feedback_type_scaler.temperature),
            'ece_before': float(ece_before),
            'ece_after': float(ece_after),
            'improvement': float(ece_before - ece_after)
        }
        print(f"  Temperature: {self.feedback_type_scaler.temperature:.4f}")
        print(f"  ECE before: {ece_before:.4f}")
        print(f"  ECE after: {ece_after:.4f}")
        print(f"  Improvement: {ece_before - ece_after:.4f}")

        # Task 2: Rule Category
        print("\n🔧 Calibrating Rule Category...")
        uncal_probs = torch.softmax(
            torch.from_numpy(all_logits['rule_category']), dim=-1
        ).numpy()
        ece_before = compute_ece(uncal_probs, all_labels['rule_category'])

        self.rule_category_scaler.fit(
            all_logits['rule_category'],
            all_labels['rule_category']
        )

        cal_probs = self.rule_category_scaler.transform(all_logits['rule_category'])
        ece_after = compute_ece(cal_probs, all_labels['rule_category'])

        results['rule_category'] = {
            'temperature': float(self.rule_category_scaler.temperature),
            'ece_before': float(ece_before),
            'ece_after': float(ece_after),
            'improvement': float(ece_before - ece_after)
        }
        print(f"  Temperature: {self.rule_category_scaler.temperature:.4f}")
        print(f"  ECE before: {ece_before:.4f}")
        print(f"  ECE after: {ece_after:.4f}")
        print(f"  Improvement: {ece_before - ece_after:.4f}")

        # Task 3: Is Actionable
        print("\n🔧 Calibrating Is Actionable...")
        uncal_probs = torch.sigmoid(
            torch.from_numpy(all_logits['is_actionable'])
        ).numpy()
        ece_before = compute_binary_ece(uncal_probs, all_labels['is_actionable'])

        self.is_actionable_scaler.fit(
            all_logits['is_actionable'],
            all_labels['is_actionable']
        )

        cal_probs = self.is_actionable_scaler.transform(all_logits['is_actionable'])
        ece_after = compute_binary_ece(cal_probs, all_labels['is_actionable'])

        results['is_actionable'] = {
            'temperature': float(self.is_actionable_scaler.temperature),
            'ece_before': float(ece_before),
            'ece_after': float(ece_after),
            'improvement': float(ece_before - ece_after)
        }
        print(f"  Temperature: {self.is_actionable_scaler.temperature:.4f}")
        print(f"  ECE before: {ece_before:.4f}")
        print(f"  ECE after: {ece_after:.4f}")
        print(f"  Improvement: {ece_before - ece_after:.4f}")

        # Task 4: Requires Clarification
        print("\n🔧 Calibrating Requires Clarification...")
        uncal_probs = torch.sigmoid(
            torch.from_numpy(all_logits['requires_clarification'])
        ).numpy()
        ece_before = compute_binary_ece(uncal_probs, all_labels['requires_clarification'])

        self.requires_clarification_scaler.fit(
            all_logits['requires_clarification'],
            all_labels['requires_clarification']
        )

        cal_probs = self.requires_clarification_scaler.transform(
            all_logits['requires_clarification']
        )
        ece_after = compute_binary_ece(cal_probs, all_labels['requires_clarification'])

        results['requires_clarification'] = {
            'temperature': float(self.requires_clarification_scaler.temperature),
            'ece_before': float(ece_before),
            'ece_after': float(ece_after),
            'improvement': float(ece_before - ece_after)
        }
        print(f"  Temperature: {self.requires_clarification_scaler.temperature:.4f}")
        print(f"  ECE before: {ece_before:.4f}")
        print(f"  ECE after: {ece_after:.4f}")
        print(f"  Improvement: {ece_before - ece_after:.4f}")

        return results

    def save_calibration_params(self, output_path: Path):
        """Save calibration parameters"""
        params = {
            'feedback_type_temperature': self.feedback_type_scaler.temperature,
            'rule_category_temperature': self.rule_category_scaler.temperature,
            'is_actionable_temperature': self.is_actionable_scaler.temperature,
            'requires_clarification_temperature': self.requires_clarification_scaler.temperature,
        }

        with open(output_path, 'w') as f:
            json.dump(params, f, indent=2)

        print(f"\n💾 Calibration parameters saved to {output_path}")


def main():
    from transformers import DistilBertTokenizerFast
    from torch.utils.data import Dataset

    # Paths
    model_path = Path(__file__).parent.parent / "models" / "distilbert_candidate" / "checkpoints" / "best_model.pt"
    val_path = Path(__file__).parent.parent / "models" / "distilbert_candidate" / "val_combined.jsonl"
    output_dir = Path(__file__).parent.parent / "models" / "distilbert_candidate"

    # Load validation data
    print("Loading validation data...")
    val_data = []
    with open(val_path, 'r') as f:
        for line in f:
            if line.strip():
                val_data.append(json.loads(line))
    print(f"Loaded {len(val_data)} validation examples")

    # Create dataset and dataloader
    from train_distilbert_classifier import FeedbackDataset

    tokenizer = DistilBertTokenizerFast.from_pretrained('distilbert-base-uncased')
    val_dataset = FeedbackDataset(val_data, tokenizer, max_length=256)
    val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)

    # Calibrate
    calibrator = DistilBERTCalibrator(model_path)
    calibration_results = calibrator.calibrate(val_loader)

    # Save results
    calibrator.save_calibration_params(output_dir / 'calibration_params.json')

    results_path = output_dir / 'calibration_results.json'
    with open(results_path, 'w') as f:
        json.dump(calibration_results, f, indent=2)

    print(f"📊 Calibration results saved to {results_path}")

    print("\n" + "=" * 80)
    print("✅ CALIBRATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
