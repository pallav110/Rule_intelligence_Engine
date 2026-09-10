"""
Label mappings for multi-task DistilBERT classifier

These mappings define the label spaces for each classification task.
Mappings are derived from the authoritative specification Section 8.3.2.

IMPORTANT: These mappings must be saved with the model for inference.
"""

# Feedback Type Labels (5 classes) - per specification §8.3.2
# Updated from 4-class legacy to 5-class authoritative taxonomy
FEEDBACK_TYPE_LABELS = {
    "business_rule": 0,
    "issue_report": 1,
    "feature_request": 2,
    "question": 3,
    "general_feedback": 4,
}

FEEDBACK_TYPE_ID2LABEL = {v: k for k, v in FEEDBACK_TYPE_LABELS.items()}
FEEDBACK_TYPE_LABEL2ID = FEEDBACK_TYPE_LABELS  # Alias for compatibility


# Rule Category Labels (6 classes + None) - per specification §8.3.2
# Updated from 16-class legacy to 6-class authoritative taxonomy
RULE_CATEGORY_LABELS = {
    "metric_definition": 0,
    "filter_rule": 1,
    "mapping_rule": 2,
    "access_rule": 3,
    "join_rule": 4,
    "data_quality_rule": 5,
    "none": 6,  # For cases where rule_category is None (non-rule feedback types)
}

RULE_CATEGORY_ID2LABEL = {v: k for k, v in RULE_CATEGORY_LABELS.items()}
RULE_CATEGORY_LABEL2ID = RULE_CATEGORY_LABELS  # Alias for compatibility


# Boolean flags (binary classification)
# is_actionable: True/False
# requires_clarification: True/False


def get_label_mappings():
    """Return all label mappings as a dict for saving with model"""
    return {
        "feedback_type": {
            "label2id": FEEDBACK_TYPE_LABELS,
            "id2label": FEEDBACK_TYPE_ID2LABEL,
            "num_labels": len(FEEDBACK_TYPE_LABELS),
        },
        "rule_category": {
            "label2id": RULE_CATEGORY_LABELS,
            "id2label": RULE_CATEGORY_ID2LABEL,
            "num_labels": len(RULE_CATEGORY_LABELS),
        },
        "is_actionable": {
            "num_labels": 1,  # Binary classification
        },
        "requires_clarification": {
            "num_labels": 1,  # Binary classification
        },
    }


# Configuration constants from specification Section 8.3.2
MODEL_CONFIG = {
    "model_name": "distilbert-base-uncased",
    "max_length": 256,
    "batch_size": 16,
    "learning_rate": 2e-5,
    "num_epochs": 10,
    "early_stopping_patience": 3,
    "weight_decay": 0.01,
    "warmup_steps": 100,
    "gradient_accumulation_steps": 1,
}