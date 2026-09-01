#!/usr/bin/env python3
"""
Quick reference for all three candidate models
"""

MODELS = {
    "DistilBERT": {
        "status": "✅ TRAINED & EVALUATED",
        "checkpoint": "rie_ml/models/distilbert_candidate/checkpoints/best_model.pt",
        "performance": {
            "feedback_type": "98.01%",
            "rule_category": "47.26%",
            "is_actionable": "97.51%",
            "requires_clarification": "98.51%"
        },
        "deployment_status": "🟢 PRODUCTION",
        "model_id": "a6680da5-4ab6-41c8-a88e-fc395e94a804"
    },
    "BERT": {
        "status": "⏳ TRAINING SCRIPT READY",
        "checkpoint": "rie_ml/models/bert_candidate/checkpoints/best_model.pt",
        "train_cmd": "python rie_ml/scripts/train_bert_classifier.py",
        "evaluate_cmd": "python rie_ml/scripts/compare_all_candidates.py",
        "notes": "Full-size BERT model for higher accuracy"
    },
    "RoBERTa": {
        "status": "⏳ TRAINING SCRIPT READY",
        "checkpoint": "rie_ml/models/roberta_candidate/checkpoints/best_model.pt",
        "train_cmd": "python rie_ml/scripts/train_roberta_classifier.py",
        "evaluate_cmd": "python rie_ml/scripts/compare_all_candidates.py",
        "notes": "Improved BERT variant with better generalization"
    }
}

# Quick commands
COMMANDS = {
    "train_bert": "python rie_ml/scripts/train_bert_classifier.py",
    "train_roberta": "python rie_ml/scripts/train_roberta_classifier.py",
    "compare_all": "python rie_ml/scripts/compare_all_candidates.py",
    "register_distilbert": "python rie_ml/scripts/register_distilbert_model.py",
    "register_baseline": "python rie_ml/scripts/register_baseline_model.py",
    "promote_model": "python rie_ml/scripts/promote_model.py promote-prod --model-id <id>",
    "load_production": "python -c \"from rie_ml.src.model_registry.loader import ModelLoader; loader = ModelLoader(); print(loader.load_production_model('distilbert-feedback-classifier'))\"",
}

if __name__ == "__main__":
    import json
    print("📊 MODEL CANDIDATES SUMMARY\n")
    print(json.dumps(MODELS, indent=2))
    print("\n🚀 QUICK COMMANDS\n")
    print(json.dumps(COMMANDS, indent=2))
