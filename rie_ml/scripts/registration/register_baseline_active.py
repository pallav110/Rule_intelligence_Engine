#!/usr/bin/env python3
"""Register the retrained UNIFIED baseline classifier as ACTIVE (Spec 8.11 DB registry).

The API's MLModelService reads the ACTIVE `classification` model from the
`model_version` table. This registers our freshly-trained
`rie_ml/models/baseline/baseline_classifier_unified.pkl` (trained on the
balanced 1513-record combined set) as ACTIVE so the `active` path serves it.
Promoting to ACTIVE auto-archives the prior classification champion (the
DistilBERT v1.2.0 classifier) per the one-ACTIVE-per-type rule — DistilBERT
reclaims ACTIVE after the Task-145 retrain.

Run INSIDE the api container (needs postgres on the docker network):
    docker exec -i -w /app -e PYTHONPATH=/app rie_api python - < register_baseline_active.py
Idempotent: re-run updates the same version rather than stacking duplicates.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

from app.db.database import SessionLocal
from app.db.models.model_version import ModelVersion
from app.schemas.model_version import ModelVersionCreateRequest
from app.services.model_version_service import ModelVersionService

REPO = Path("/app/rie_ml")
MODEL = "/models/baseline/baseline_classifier_unified.pkl"


def load_metrics() -> dict:
    """Pull the newest baseline evaluation result off the MetricsStorage disk store."""
    results_dir = REPO / "datasets" / "evaluation" / "metrics" / "results"
    files = sorted(results_dir.glob("baseline_*.json"), key=lambda p: p.name)
    if not files:
        raise FileNotFoundError("no baseline_*.json metric results found")
    return json.loads(files[-1].read_text())


def build_spec(metrics: dict) -> dict:
    cls = metrics["classification"]
    acc = cls["accuracy"]
    per_cat = {
        k: {
            "precision": cls["precision"].get(k),
            "recall": cls["recall"].get(k),
            "f1": cls["f1_score"].get(k),
        }
        for k in cls["precision"]
    }
    return {
        "model_name": "baseline-deterministic-classifier",
        "model_type": "classification",  # ModelType enum has no baseline type; baseline is a classifier
        "version": "v2.0.0",
        "description": (
            "Unified TF-IDF + Logistic Regression baseline classifier, retrained on the "
            "balanced v0.2.0 combined set (1513 records). Cross-domain fallback served via "
            "RealClassifier when no torch checkpoint is ACTIVE. acc=%.4f on frozen eval."
            % acc
        ),
        "checkpoint_path": MODEL,
        "training_dataset_version_id": "feedback-combined-v2-train-1513",
        "validation_dataset_version_id": "feedback-combined-v2-val-322",
        "annotation_scheme_version": "multi-task-v1",
        "hyperparameters": {"approach": "tfidf+logistic-regression", "ngram_range": None},
        "training_timestamp": datetime(2026, 9, 11, 9, 45, 0, tzinfo=timezone.utc),
        "evaluation_metrics": {
            "feedback_type_accuracy": acc,
            "feedback_type_precision": cls["precision"],
            "feedback_type_recall": cls["recall"],
            "per_category_f1": per_cat,
            "dataset_split": metrics["dataset_split"],
            "dataset_size": metrics["dataset_size"],
            "total_samples": cls["total_samples"],
            "calibration_error": cls.get("calibration_error"),
        },
    }


def main() -> None:
    db = SessionLocal()
    svc = ModelVersionService()
    metrics = load_metrics()
    spec = build_spec(metrics)

    existing = (
        db.query(ModelVersion)
        .filter(
            ModelVersion.model_name == spec["model_name"],
            ModelVersion.version == spec["version"],
        )
        .first()
    )

    if existing:
        # Idempotent update — bring metrics up to date, then ensure ACTIVE.
        existing.evaluation_metrics = spec["evaluation_metrics"]
        existing.description = spec["description"]
        db.commit()
        row_id = existing.model_version_id
        status = existing.status
        print(f"Updated existing {row_id} (status={status})")
    else:
        payload = ModelVersionCreateRequest(**spec)
        row = svc.create_model_version(db, payload)
        row_id = row.model_version_id
        status = row.status
        print(f"Created {row_id} (status={status})")

    if status != "ACTIVE":
        svc.promote_model(db, row_id, "APPROVED")
        svc.promote_model(db, row_id, "ACTIVE")
        print(f"Promoted {row_id} APPROVED -> ACTIVE")

    print("\nFINAL classification rows (ACTIVE in bold):")
    for r in db.query(ModelVersion).filter(ModelVersion.model_type == "classification").order_by(ModelVersion.created_at).all():
        m = r.evaluation_metrics or {}
        acc = m.get("feedback_type_accuracy") or m.get("accuracy") or "—"
        print(f"  {r.version:<9}{str(r.status):<9}{r.model_version_id}  acc={acc}")

    active = (
        db.query(ModelVersion)
        .filter(ModelVersion.model_type == "classification", ModelVersion.status == "ACTIVE")
        .all()
    )
    n = len(active)
    db.close()
    if n != 1:
        raise SystemExit(f"expected exactly 1 ACTIVE classification, found {n}")
    print(f"\n✅ Exactly 1 ACTIVE classification row (baseline v2.0.0) — checkpoint {MODEL}")


if __name__ == "__main__":
    main()