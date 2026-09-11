#!/usr/bin/env python3
"""
One-shot retrain for the DistilBERT token extractor against the NEW v0.2.0 dataset.

Regenerating + retraining the BIO slot-labeled token classifier in one go, so the
extraction head finally matches the classifiers (which were already retrained).

Pipeline (each step reuses an existing script — nothing re-implemented):
  1. prepare_bio_training_data.py   — regenerate BIO data from dataset_generation/output/<domain>/extraction.jsonl (the NEW source)
  2. balance_bio_dataset.py         — downsample padded "O" tokens, keep entities (default target O-ratio 0.70)
  3. train_distilbert_token_classifier.py — train the 16-label BIO head -> overwrites
                                            models/distilbert_token_extractor/checkpoints/best_model.pt
  4. evaluate_extraction_model.py   — write token_evaluation_results.json used by the DB registration step
  5. register_retrained_models.py   — INSIDE the api container (needs postgres on the docker network):
                                     refresh eval metrics on the ACTIVE distilbert-extractor row in place
                                     (idempotent; same checkpoint path, so the retrained weights are served immediately)

Prerequisites:
  - The Docker stack is up (rie_api + rie_postgres) so step 5 can reach Postgres.
  - The training python is passed via PYTHON (defaults to sys.executable). For a CUDA
    train pass the interpreter that has torch+transformers (e.g. .venv/bin/python).
  - Run from the repo root (rie_ml/... paths are computed relative to this file, so
    CWD does not actually matter, but repo must be checked out at the same location).

Usage:
  PYTHON=.venv/bin/python python rie_ml/scripts/training/retrain_token_extractor_all.py [--prepare-only] [--no-train] [--no-register]

Flags:
  --prepare-only  only regenerate + balance the BIO data, stop before training.
  --no-train      run data prep then skip the GPU training+eval (for testing the harness).
  --no-register   run everything up to and including eval, skip the DB registration step.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent      # -> repo root (/.../Rule-intelligence-Engine)
TRAINING = REPO / "rie_ml" / "scripts" / "training"
EVAL = REPO / "rie_ml" / "scripts" / "evaluation"
REG = REPO / "rie_ml" / "scripts" / "registration"
BIO_DIR = REPO / "rie_ml" / "datasets" / "extraction_bio"

# Container path (docker exec) mirrors the host bind-mount rie_ml:/app/rie_ml.
REGISTER_IN_CONTAINER = "/app/rie_ml/scripts/registration/register_retrained_models.py"
API_CONTAINER = "rie_api"


def _py():
    return os.environ.get("PYTHON", sys.executable)


def run(step, cmd, cwd=None):
    print(f"\n{'='*80}\n▶ STEP: {step}\n{'='*80}")
    print(f"   cmd: {' '.join(map(str, cmd))}\n")
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None)
    if r.returncode != 0:
        raise SystemExit(f"❌ STEP FAILED ({step}): exit {r.returncode}. Aborting — fix and rerun.")
    print(f"\n✅ STEP OK: {step}\n")


def main():
    ap = argparse.ArgumentParser(description="One-shot token-extractor retrain against the v0.2.0 dataset")
    ap.add_argument("--prepare-only", action="store_true",
                    help="regenerate + balance BIO data only, then stop")
    ap.add_argument("--no-train", action="store_true",
                    help="run data prep but skip GPU training + eval")
    ap.add_argument("--no-register", action="store_true",
                    help="run everything but skip the DB registration step")
    args = ap.parse_args()

    py = _py()
    print(f"Using python: {py}")
    print(f"REPO      : {REPO}")

    # Guard: the source data must exist before we regenerate.
    missing = []
    for d in ("ecommerce", "customer_support", "saas_subscription"):
        p = REPO / "rie_ml" / "dataset_generation" / "output" / d / "extraction.jsonl"
        if not p.exists():
            missing.append(p)
    if missing:
        raise SystemExit("❌ Source extraction.jsonl missing for: " + "; ".join(map(str, missing)))

    BIO_DIR.mkdir(parents=True, exist_ok=True)

    # --- 1. regenerate BIO data from the NEW dataset_generation output ----------
    run("Regenerate BIO training data (from v0.2.0 dataset_generation output)",
        [py, TRAINING / "prepare_bio_training_data.py"], cwd=REPO)

    # --- 2. balance O tokens ------------------------------------------------
    run("Balance O-token downsampling (keep entities)",
        [py, TRAINING / "balance_bio_dataset.py"], cwd=REPO)

    if args.prepare_only:
        print("\n∥ --prepare-only: BIO data regenerated + balanced. Done (skipping train/eval/register).")
        return

    if args.no_train:
        print("\n∥ --no-train: data prep complete. Skipped train/eval/register.")
        return

    # --- 3. train the token classifier --------------------------------------
    run("Train DistilBERT token classifier (16-label BIO head)",
        [py, TRAINING / "train_distilbert_token_classifier.py"], cwd=REPO)

    # --- 4. evaluate -> token_evaluation_results.json ------------------------
    run("Evaluate token classifier (writes token_evaluation_results.json)",
        [py, EVAL / "evaluate_extraction_model.py"], cwd=REPO)

    if args.no_register:
        print("\n∥ --no-register: train + eval complete. Skipped DB registration.")
        return

    # --- 5. refresh DB registry (inside api container for postgres access) ----
    print(f"\n{'='*80}\n▶ STEP: Refresh DB registry (extractor eval metrics)\n{'='*80}")
    print(f"   docker exec {API_CONTAINER} python {REGISTER_IN_CONTAINER}")
    r = subprocess.run(["docker", "exec", API_CONTAINER, "python",
                        REGISTER_IN_CONTAINER])
    if r.returncode != 0:
        raise SystemExit(f"❌ STEP FAILED (DB registration): exit {r.returncode}. "
                         "Confirm the Docker stack (rie_api/rie_postgres) is up.")
    print(f"\n✅ STEP OK: DB registration\n")

    print("\n" + "=" * 80)
    print("🎉 TOKEN EXTRACTOR RETRAIN COMPLETE — ACTIVE on the retrained weights")
    print("=" * 80)
    print(f"  Ckpt : {REPO / 'rie_ml/models/distilbert_token_extractor/checkpoints/best_model.pt'}")
    print(f"  Eval : {REPO / 'rie_ml/models/distilbert_token_extractor/token_evaluation_results.json'}")
    print("  Serve: MLModelService.extract() resolves /models/distilbert-extractor -> this checkpoint")


if __name__ == "__main__":
    main()