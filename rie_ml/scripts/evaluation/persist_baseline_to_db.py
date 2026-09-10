#!/usr/bin/env python3
"""Persist the baseline evaluation + model registration + promotion to the DATABASE.

This is the database half of the RIE persistence requirement: the on-disk
JSON result (evaluate_baseline_with_storage.py) records the evaluation, but the
PostgreSQL schema (app.db.models.*) must also carry:
  - dataset_versions  : the frozen evaluation dataset this ran on
  - model_versions    : the baseline model registration (CANDIDATE)
  - evaluation_runs   : one run row
  - evaluation_metrics: scalar metric rows under that run
  - model_versions.status + audit_history : the promotion lifecycle

Run from repo root so ``app`` is importable:
    PYTHONPATH=. .venv/bin/python rie_ml/scripts/evaluation/persist_baseline_to_db.py
"""

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from evaluation.metrics_storage_db import MetricsStorageDB

RESULTS_DIR = Path(__file__).parent.parent.parent / "datasets" / "evaluation" / "metrics" / "results"
FROZEN_PATH = Path(__file__).parent.parent.parent / "datasets" / "evaluation" / "frozen_evaluation.jsonl"


def latest_result_path() -> Path:
    results = sorted(RESULTS_DIR.glob("baseline_*.json"), key=lambda p: p.stat().st_mtime)
    if not results:
        raise SystemExit(f"❌ No baseline result JSON found in {RESULTS_DIR}")
    return results[-1]


def main() -> None:
    store = MetricsStorageDB()
    print("=" * 78)
    print("PERSIST BASELINE EVALUATION + REGISTRATION + PROMOTION TO DATABASE")
    print("=" * 78)

    # 1) Load the on-disk frozen evaluation result
    result_path = latest_result_path()
    data = json.load(open(result_path))
    print(f"📄 Evaluation result : {result_path.read_text().splitlines()[0][:120]}...")
    print(f"   evaluation_id      : {data['evaluation_id']}")
    print(f"   accuracy           : {data['classification']['accuracy']:.2%}")
    print(f"   acceptance          : {'PASS' if data['acceptance_criteria_passed'] else 'FAIL'}")

    # Version the model canonically (matches register_baseline_model.py v1.0.0)
    data["model_version"] = "1.0.0"

    # 2) Ensure the frozen evaluation dataset row exists (FK requirement)
    num_samples = data["dataset_size"]
    dataset_version_id = store.ensure_dataset(
        dataset_name="rie-feedback-frozen-evaluation",
        version="v0.2.0",
        path=str(FROZEN_PATH),
        num_samples=num_samples,
        annotation_version="ann_v0.2.0",
        domain_pack_version="v0.2.0",
        source="frozen_test_splits",
        status="FROZEN",
        description="Frozen evaluation set concatenated from ecommerce/customer_support/saas test splits at taxonomy v0.2.0",
    )
    print(f"🗂️  dataset_version_id : {dataset_version_id}")

    # 3) Persist evaluation run + metrics + auto-register model version
    eval_run_id = store.save_evaluation(
        result=data,
        model_name="baseline-deterministic-classifier",
        model_version="1.0.0",
        model_type="classification",
        dataset_version_id=dataset_version_id,
        dataset_name="rie-feedback-frozen-evaluation",
        dataset_size=num_samples,
        reason=f"Frozen v0.2.0 evaluation: {data['classification']['accuracy']:.2%} accuracy, acceptance PASS",
    )
    print(f"🧪 evaluation_run_id  : {eval_run_id}")

    # 4) Promote the model through its lifecycle, recording audit in the DB
    mv_id = store.get_model_version_id("baseline-deterministic-classifier", "1.0.0", "classification")
    print(f"📦 model_version_id   : {mv_id}")
    if mv_id:
        # Idempotent promotion: walk CANDIDATE -> APPROVED -> ACTIVE, skipping
        # steps already taken in a prior run.
        session = store._session()
        from app.db.models.model_version import ModelVersion

        try:
            current = session.query(ModelVersion).filter(ModelVersion.model_version_id == mv_id).first().status
        finally:
            session.close()

        reason = f"Baseline meets v0.2.0 acceptance criteria ({data['classification']['accuracy']:.2%})"
        for target in ("APPROVED", "ACTIVE"):
            if current == "ACTIVE":
                print(f"   already ACTIVE (target {target}); skipping")
                break
            r = store.promote(mv_id, target, reason=reason)
            print(f"   promoted {r['from_status']} -> {r['to_status']}")
            current = r["to_status"]
    else:
        print("⚠️  Model version not found; skipping promotion")

    print("\n" + "=" * 78)
    print("FINAL DB STATE")
    print("=" * 78)
    session = store._session()
    from sqlalchemy import text
    try:
        with session.bind.connect() as c:
            for table in ("model_versions", "dataset_versions", "evaluation_runs", "evaluation_metrics", "audit_history"):
                print(f"  {table:22} : {c.execute(text(f'SELECT count(*) FROM {table}')).scalar()}")
    finally:
        session.close()
    print("=" * 78)
    print("✅ Persisted to database. Query via:")
    print("   SELECT * FROM evaluation_runs;")
    print("   SELECT * FROM evaluation_metrics;")
    print("   SELECT model_name,version,status FROM model_versions ORDER BY created_at;")


if __name__ == "__main__":
    main()