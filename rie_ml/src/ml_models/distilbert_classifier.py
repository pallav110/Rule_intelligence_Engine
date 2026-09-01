"""
Multi-Task DistilBERT Classifier for Business Feedback Classification

This module implements a DistilBERT-based classifier with 4 independent prediction heads:
1. Feedback Type (multi-class classification)
2. Rule Category (multi-class classification)
3. Is Actionable (binary classification)
4. Requires Clarification (binary classification)

Architecture (per specification Section 8.3.2):
    Input Text
        ↓
    DistilBERT Tokenizer (max_length=256)
        ↓
    DistilBERT Model (distilbert-base-uncased)
        ↓
    [CLS] Token Representation (hidden_state[:, 0, :])
        ↓
    ┌─────────────┬───────────────────┬──────────────┬─────────────────────┐
    ↓             ↓                   ↓              ↓
Feedback Type  Rule Category    Is Actionable  Requires Clarification
(Softmax)      (Softmax)        (Sigmoid)      (Sigmoid)

Loss Functions:
- Feedback Type: CrossEntropyLoss
- Rule Category: CrossEntropyLoss
- Is Actionable: BCEWithLogitsLoss
- Requires Clarification: BCEWithLogitsLoss

Total Loss: weighted sum of all 4 task losses
"""

import torch
import torch.nn as nn
from transformers import DistilBertModel, DistilBertConfig
from typing import Dict, Tuple, Optional


class MultiTaskDistilBERTClassifier(nn.Module):
    """
    Multi-task DistilBERT classifier with 4 independent prediction heads.

    Args:
        num_feedback_types: Number of feedback type classes (default: 4)
        num_rule_categories: Number of rule category classes (default: 16)
        dropout: Dropout probability (default: 0.1)
        pretrained_model_name: HuggingFace model name (default: distilbert-base-uncased)
    """

    def __init__(
        self,
        num_feedback_types: int = 4,
        num_rule_categories: int = 16,
        dropout: float = 0.1,
        pretrained_model_name: str = "distilbert-base-uncased"
    ):
        super(MultiTaskDistilBERTClassifier, self).__init__()

        # Load pretrained DistilBERT
        self.distilbert = DistilBertModel.from_pretrained(pretrained_model_name)
        self.hidden_size = self.distilbert.config.hidden_size  # 768 for distilbert-base

        # Dropout for regularization
        self.dropout = nn.Dropout(dropout)

        # Task 1: Feedback Type Classification (multi-class)
        self.feedback_type_head = nn.Linear(self.hidden_size, num_feedback_types)

        # Task 2: Rule Category Classification (multi-class)
        self.rule_category_head = nn.Linear(self.hidden_size, num_rule_categories)

        # Task 3: Is Actionable (binary)
        self.is_actionable_head = nn.Linear(self.hidden_size, 1)

        # Task 4: Requires Clarification (binary)
        self.requires_clarification_head = nn.Linear(self.hidden_size, 1)

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Initialize classification head weights"""
        for head in [
            self.feedback_type_head,
            self.rule_category_head,
            self.is_actionable_head,
            self.requires_clarification_head
        ]:
            head.weight.data.normal_(mean=0.0, std=0.02)
            if head.bias is not None:
                head.bias.data.zero_()

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        feedback_type_labels: Optional[torch.Tensor] = None,
        rule_category_labels: Optional[torch.Tensor] = None,
        is_actionable_labels: Optional[torch.Tensor] = None,
        requires_clarification_labels: Optional[torch.Tensor] = None,
        task_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass through the model.

        Args:
            input_ids: Token IDs (batch_size, seq_len)
            attention_mask: Attention mask (batch_size, seq_len)
            feedback_type_labels: Labels for feedback type (batch_size,)
            rule_category_labels: Labels for rule category (batch_size,)
            is_actionable_labels: Labels for is_actionable (batch_size,)
            requires_clarification_labels: Labels for requires_clarification (batch_size,)
            task_weights: Optional weights for each task loss

        Returns:
            Dictionary containing logits and optionally loss for each task
        """
        # Get DistilBERT outputs
        outputs = self.distilbert(
            input_ids=input_ids,
            attention_mask=attention_mask
        )

        # Extract [CLS] token representation (first token)
        # Shape: (batch_size, hidden_size)
        hidden_state = outputs.last_hidden_state
        cls_representation = hidden_state[:, 0, :]

        # Apply dropout
        cls_representation = self.dropout(cls_representation)

        # Get logits for each task
        feedback_type_logits = self.feedback_type_head(cls_representation)
        rule_category_logits = self.rule_category_head(cls_representation)
        is_actionable_logits = self.is_actionable_head(cls_representation)
        requires_clarification_logits = self.requires_clarification_head(cls_representation)

        # Prepare output dictionary
        output = {
            "feedback_type_logits": feedback_type_logits,
            "rule_category_logits": rule_category_logits,
            "is_actionable_logits": is_actionable_logits,
            "requires_clarification_logits": requires_clarification_logits,
        }

        # Compute losses if labels are provided
        if all(label is not None for label in [
            feedback_type_labels,
            rule_category_labels,
            is_actionable_labels,
            requires_clarification_labels
        ]):
            losses = self._compute_losses(
                feedback_type_logits,
                rule_category_logits,
                is_actionable_logits,
                requires_clarification_logits,
                feedback_type_labels,
                rule_category_labels,
                is_actionable_labels,
                requires_clarification_labels,
                task_weights
            )
            output.update(losses)

        return output

    def _compute_losses(
        self,
        feedback_type_logits: torch.Tensor,
        rule_category_logits: torch.Tensor,
        is_actionable_logits: torch.Tensor,
        requires_clarification_logits: torch.Tensor,
        feedback_type_labels: torch.Tensor,
        rule_category_labels: torch.Tensor,
        is_actionable_labels: torch.Tensor,
        requires_clarification_labels: torch.Tensor,
        task_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, torch.Tensor]:
        """
        Compute losses for all tasks independently.

        Returns:
            Dictionary with individual losses and total weighted loss
        """
        # Default task weights (equal weighting)
        if task_weights is None:
            task_weights = {
                "feedback_type": 1.0,
                "rule_category": 1.0,
                "is_actionable": 1.0,
                "requires_clarification": 1.0,
            }

        # Task 1: Feedback Type (CrossEntropyLoss)
        feedback_type_loss_fn = nn.CrossEntropyLoss()
        feedback_type_loss = feedback_type_loss_fn(
            feedback_type_logits,
            feedback_type_labels
        )

        # Task 2: Rule Category (CrossEntropyLoss)
        rule_category_loss_fn = nn.CrossEntropyLoss()
        rule_category_loss = rule_category_loss_fn(
            rule_category_logits,
            rule_category_labels
        )

        # Task 3: Is Actionable (BCEWithLogitsLoss)
        is_actionable_loss_fn = nn.BCEWithLogitsLoss()
        is_actionable_loss = is_actionable_loss_fn(
            is_actionable_logits.squeeze(-1),
            is_actionable_labels.float()
        )

        # Task 4: Requires Clarification (BCEWithLogitsLoss)
        requires_clarification_loss_fn = nn.BCEWithLogitsLoss()
        requires_clarification_loss = requires_clarification_loss_fn(
            requires_clarification_logits.squeeze(-1),
            requires_clarification_labels.float()
        )

        # Total weighted loss
        total_loss = (
            task_weights["feedback_type"] * feedback_type_loss +
            task_weights["rule_category"] * rule_category_loss +
            task_weights["is_actionable"] * is_actionable_loss +
            task_weights["requires_clarification"] * requires_clarification_loss
        )

        return {
            "loss": total_loss,
            "feedback_type_loss": feedback_type_loss,
            "rule_category_loss": rule_category_loss,
            "is_actionable_loss": is_actionable_loss,
            "requires_clarification_loss": requires_clarification_loss,
        }

    def predict(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        return_probabilities: bool = True
    ) -> Dict[str, torch.Tensor]:
        """
        Make predictions (inference mode).

        Args:
            input_ids: Token IDs
            attention_mask: Attention mask
            return_probabilities: If True, return probabilities; else return logits

        Returns:
            Dictionary with predictions for each task
        """
        self.eval()
        with torch.no_grad():
            outputs = self.forward(input_ids, attention_mask)

        predictions = {}

        if return_probabilities:
            # Feedback Type (softmax)
            predictions["feedback_type_probs"] = torch.softmax(
                outputs["feedback_type_logits"], dim=-1
            )
            predictions["feedback_type_pred"] = torch.argmax(
                predictions["feedback_type_probs"], dim=-1
            )

            # Rule Category (softmax)
            predictions["rule_category_probs"] = torch.softmax(
                outputs["rule_category_logits"], dim=-1
            )
            predictions["rule_category_pred"] = torch.argmax(
                predictions["rule_category_probs"], dim=-1
            )

            # Is Actionable (sigmoid)
            predictions["is_actionable_probs"] = torch.sigmoid(
                outputs["is_actionable_logits"].squeeze(-1)
            )
            predictions["is_actionable_pred"] = (
                predictions["is_actionable_probs"] > 0.5
            ).long()

            # Requires Clarification (sigmoid)
            predictions["requires_clarification_probs"] = torch.sigmoid(
                outputs["requires_clarification_logits"].squeeze(-1)
            )
            predictions["requires_clarification_pred"] = (
                predictions["requires_clarification_probs"] > 0.5
            ).long()
        else:
            predictions = outputs

        return predictions

    def freeze_distilbert(self):
        """Freeze DistilBERT parameters (only train classification heads)"""
        for param in self.distilbert.parameters():
            param.requires_grad = False

    def unfreeze_distilbert(self):
        """Unfreeze DistilBERT parameters (fine-tune entire model)"""
        for param in self.distilbert.parameters():
            param.requires_grad = True

    def get_num_parameters(self) -> Dict[str, int]:
        """Get number of parameters in model"""
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        distilbert_params = sum(p.numel() for p in self.distilbert.parameters())
        head_params = total_params - distilbert_params

        return {
            "total": total_params,
            "trainable": trainable_params,
            "distilbert": distilbert_params,
            "classification_heads": head_params,
        }


def create_model(
    num_feedback_types: int = 4,
    num_rule_categories: int = 16,
    dropout: float = 0.1,
    pretrained_model_name: str = "distilbert-base-uncased"
) -> MultiTaskDistilBERTClassifier:
    """
    Factory function to create model instance.

    Args:
        num_feedback_types: Number of feedback type classes
        num_rule_categories: Number of rule category classes
        dropout: Dropout probability
        pretrained_model_name: HuggingFace model checkpoint

    Returns:
        Initialized MultiTaskDistilBERTClassifier
    """
    model = MultiTaskDistilBERTClassifier(
        num_feedback_types=num_feedback_types,
        num_rule_categories=num_rule_categories,
        dropout=dropout,
        pretrained_model_name=pretrained_model_name
    )

    return model


if __name__ == "__main__":
    # Test model initialization
    print("Testing MultiTaskDistilBERTClassifier...")

    model = create_model()
    params = model.get_num_parameters()

    print(f"\nModel Parameters:")
    print(f"  Total: {params['total']:,}")
    print(f"  Trainable: {params['trainable']:,}")
    print(f"  DistilBERT: {params['distilbert']:,}")
    print(f"  Classification Heads: {params['classification_heads']:,}")

    # Test forward pass
    batch_size = 2
    seq_len = 32

    input_ids = torch.randint(0, 30522, (batch_size, seq_len))
    attention_mask = torch.ones(batch_size, seq_len)

    # Test inference
    predictions = model.predict(input_ids, attention_mask)
    print(f"\nTest inference successful!")
    print(f"  Feedback type predictions shape: {predictions['feedback_type_pred'].shape}")
    print(f"  Rule category predictions shape: {predictions['rule_category_pred'].shape}")
    print(f"  Is actionable predictions shape: {predictions['is_actionable_pred'].shape}")
    print(f"  Requires clarification predictions shape: {predictions['requires_clarification_pred'].shape}")
