"""Register the RETRAINED DistilBERT models in the model_version registry (Spec 8.11).

Fixes the stale-registry problem: the ACTIVE rows still carry the OLD evaluation
metrics (e.g. classifier accuracy 0.9801) from before the retrain, while the
checkpoint files on disk are the new retrained weights. This script:

  1. Reads the latest eval results from disk (comprehensive_eval_test.json for the
     classifier, token_evaluation_results.json for the token extractor).
  2. Registers each retrained model as a NEW CANDIDATE row with correct metrics
     and full metadata (annotation_scheme_version, hyperparameters, datasets,
     training_timestamp) — previously None.
  3. Promotes each through CANDIDATE -> APPROVED -> ACTIVE.
  4. Archives the old ACTIVE rows so stale metrics can never be selected for inference.

Run INSIDE the api container (must be on the docker network to reach postgres):
    docker exec rie_api python /app/rie_ml/scripts/register_retrained_models.py

Idempotent: safe to re-run. Skips registration if the version already exists.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# This script runs INSIDE the api container, where the app/ package lives at
# /app/app. `python /app/rie_ml/.../script.py` (script-path invocation — the
# documented docker exec form) sets sys.path[0] to the script's own directory,
# NOT the container workdir /app, so `app` is otherwise not importable. Make the
# container mount root importable regardless of how the script is invoked.
sys.path.insert(0, "/app")

from app.db.database import SessionLocal
from app.db.models.model_version import ModelVersion
from app.schemas.model_version import ModelVersionCreateRequest
from app.services.model_version_service import ModelVersionService

REPO = Path("/app/rie_ml")

# ---------------------------------------------------------------------------
# 1. Load latest eval results from disk (bind-mounted, so these are the new files)
# ---------------------------------------------------------------------------
with open(REPO / "models" / "distilbert_candidate" / "comprehensive_eval_test.json") as f:
    classifier_eval = json.load(f)
with open(REPO / "models" / "distilbert_token_extractor" / "token_evaluation_results.json") as f:
    extractor_eval = json.load(f)

ft = classifier_eval["feedback_type"]
rc = classifier_eval["rule_category"]
ia = classifier_eval["is_actionable"]
rq = classifier_eval["requires_clarification"]

classifier_metrics = {
    "feedback_type_accuracy": ft["accuracy"],
    "feedback_type_macro_f1": ft["macro_f1"],
    "feedback_type_weighted_f1": ft["weighted_f1"],
    "rule_category_accuracy": rc["accuracy"],
    "rule_category_macro_f1": rc["macro_f1"],
    "is_actionable_accuracy": ia["accuracy"],
    "is_actionable_f1": ia["f1_score"],
    "requires_clarification_accuracy": rq["accuracy"],
    "requires_clarification_f1": rq["f1_score"],
    # Derive test size from the confusion matrix (v0.2.0 6-class frozen eval) so it
    # never drifts out of sync with the eval JSON (was hardcoded 201 / 4-class old set).
    "test_samples": sum(sum(row) for row in ft["confusion_matrix"]),
    "confusion_matrix_feedback_type": ft["confusion_matrix"],
    "per_category_f1": ft["per_category_f1"],
}

extractor_metrics = {
    "test_set_size": extractor_eval["test_set_size"],
    "overall_token_accuracy": extractor_eval["overall_accuracy"],
    "macro_precision": extractor_eval["macro_precision"],
    "macro_recall": extractor_eval["macro_recall"],
    "macro_f1": extractor_eval["macro_f1"],
    "per_label_f1": {k: v["f1"] for k, v in extractor_eval["per_label"].items()},
}

RETRAINED = [
    {
        "model_name": "distilbert-classifier",
        "model_type": "classification",
        "version": "v2.0.0",
        "description": (
            "Retrained multi-task DistilBERT classifier on balanced v0.2.0 "
            "combined set (1513 train / 323 val, spam prefiltered). Trained on "
            "CPU. feeback_type acc %g on the 328-sample 6-class frozen eval. "
            "Replaces baseline v2.0.0 as ACTIVE classification."
            % ft["accuracy"]
        ),
        "checkpoint_path": "/models/distilbert-classifier",
        "training_dataset_version_id": "feedback-combined-v2-train-1513",
        "validation_dataset_version_id": "feedback-combined-v2-val-323",
        "annotation_scheme_version": "multi-task-v1",
        "hyperparameters": {
            "model": "distilbert-base-uncased",
            "epochs": 10,
            "batch_size": 16,
            "learning_rate": 2e-5,
            "early_stopping_patience": 3,
            "tasks": ["feedback_type", "rule_category", "is_actionable", "requires_clarification"],
        },
        "training_timestamp": datetime(2026, 9, 11, 16, 42, 0, tzinfo=timezone.utc),
        "evaluation_metrics": classifier_metrics,
    },
    {
        "model_name": "distilbert-extractor",
        "model_type": "rule-extraction",
        "version": "v2.0.0",
        "description": (
            "Retrained DistilBERT BIO token classifier for rule extraction on "
            "balanced v0.2.0 data (950 train / 279 val, 19 labels incl. "
            "I_COLUMN/I_TABLE/I_THRESHOLD continuations). Overall acc %g, "
            "macro_f1 %g on the 273-sample 6-domain test BIO set."
            % (extractor_eval["overall_accuracy"], extractor_eval["macro_f1"])
        ),
        "checkpoint_path": "/models/distilbert-extractor",
        "training_dataset_version_id": "token-bio-v2-train-950",
        "validation_dataset_version_id": "token-bio-v2-val-279",
        "annotation_scheme_version": "BIO-19labels-v2",
        "hyperparameters": {
            "model": "distilbert-base-uncased",
            "epochs": 5,
            "batch_size": 8,
            "learning_rate": 2e-5,
            "num_labels": 19,
            "class_balanced": True,
            "task": "token_classification_rule_extraction",
        },
        "training_timestamp": datetime(2026, 9, 11, 16, 43, 0, tzinfo=timezone.utc),
        "evaluation_metrics": extractor_metrics,
    },
]


def main():
    db = SessionLocal()
    svc = ModelVersionService()

    for spec in RETRAINED:
        # Idempotency: skip if this model_name+version already registered
        existing = db.query(ModelVersion).filter_by(
            model_name=spec["model_name"], version=spec["version"]
        ).first()
        if existing:
            print(f"⚠️  {spec['model_name']} {spec['version']} already exists "
                  f"({existing.model_version_id}, status={existing.status}) — updating metrics")
            existing.evaluation_metrics = spec["evaluation_metrics"]
            existing.hyperparameters = spec["hyperparameters"]
            existing.annotation_scheme_version = spec["annotation_scheme_version"]
            db.commit()
            new_id = existing.model_version_id
            status = existing.status
        else:
            payload = ModelVersionCreateRequest(**spec)
            row = svc.create_model_version(db, payload)
            new_id = row.model_version_id
            status = row.status
            print(f"✅ Registered {spec['model_name']} {spec['version']} as CANDIDATE -> {new_id}")

        # Promote to ACTIVE through the lifecycle (only if not already ACTIVE)
        if status != "ACTIVE":
            svc.promote_model(db, new_id, "APPROVED")
            svc.promote_model(db, new_id, "ACTIVE")
            print(f"   ✅ Promoted {new_id} APPROVED -> ACTIVE")

        # Archive the OLD active rows for this model type (stale metrics must not win)
        stale = db.query(ModelVersion).filter(
            ModelVersion.model_type == spec["model_type"],
            ModelVersion.status == "ACTIVE",
            ModelVersion.model_version_id != new_id,
        ).all()
        for old in stale:
            old.status = "ARCHIVED"
            db.commit()
            print(f"   🗄️  Archived stale {old.model_name} {old.version} ({old.model_version_id}) "
                  f"old metrics: {old.evaluation_metrics}")

    # Final verification
    print("\n" + "=" * 60)
    print("FINAL REGISTRY STATE")
    print("=" * 60)
    for row in db.query(ModelVersion).order_by(ModelVersion.created_at.desc()).all():
        acc = row.evaluation_metrics.get("feedback_type_accuracy") or \
              row.evaluation_metrics.get("accuracy") or "—"
        print(f"  {row.model_type:<18} {row.model_name:<22} {row.version:<8} "
              f"{row.status:<9} ft_acc={acc} ann={row.annotation_scheme_version}")
    db.close()


if __name__ == "__main__":
    main()
