"""
Label mappings for multi-task DistilBERT classifier

These mappings define the label spaces for each classification task.
Mappings are derived from the actual dataset validation results.

IMPORTANT: These mappings must be saved with the model for inference.
"""

# Feedback Type Labels (4 classes)
# Based on specification Section 8.3.2 and dataset validation
FEEDBACK_TYPE_LABELS = {
    "business_rule_correction": 0,
    "unclear_feedback": 1,
    "irrelevant_spam": 2,
    "non_rule_feedback": 3,
}

FEEDBACK_TYPE_ID2LABEL = {v: k for k, v in FEEDBACK_TYPE_LABELS.items()}


# Rule Category Labels (13 classes + None)
# Based on dataset validation results
RULE_CATEGORY_LABELS = {
    "calculation_correction": 0,
    "filter_rule": 1,
    "metric_definition": 2,
    "status_mapping": 3,
    "join_correction": 4,
    "column_meaning": 5,
    "time_rule": 6,
    "entity_definition": 7,
    "data_quality_issue": 8,
    "access_scope_rule": 9,
    "expected_result_correction": 10,
    "access_rule": 11,
    "mapping_rule": 12,
    "join_rule": 13,
    "data_quality_rule": 14,
    "none": 15,  # For cases where rule_category is None
}

RULE_CATEGORY_ID2LABEL = {v: k for k, v in RULE_CATEGORY_LABELS.items()}


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
