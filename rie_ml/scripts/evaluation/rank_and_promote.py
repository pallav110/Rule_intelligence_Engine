#!/usr/bin/env python3
"""CLI to rank candidate models and promote the best one."""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import argparse
import torch
import numpy as np
from datetime import datetime

# Add src, app to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from evaluation.metrics_storage_db import MetricsStorageDB
from app.services.ml_model_service import MLModelService


class ModelRanker:
    """Rank candidate models and promote the best one."""

    def __init__(self, domain: str = "ecommerce"):
        self.domain = domain
        self.storage = MetricsStorageDB()
        self.model_service = MLModelService()
        self.models = {
            "distilbert": {
                "path": Path(__file__).parent.parent.parent / "models" / "distilbert_candidate" / "checkpoints" / "best_model.pt",
                "name": "distilbert-classifier",
                "version": "1.0.0"
            },
            "bert": {
                "path": Path(__file__).parent.parent.parent / "models" / "bert_candidate" / "checkpoints" / "best_model.pt",
                "name": "bert-classifier",
                "version": "1.0.0"
            },
            "roberta": {
                "path": Path(__file__).parent.parent.parent / "models" / "roberta_candidate" / "checkpoints" / "best_model.pt",
                "name": "roberta-classifier",
                "version": "1.0.0"
            }
        }
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _load_eval_metrics(self, model_name: str) -> Dict[str, Any]:
        """Load evaluation metrics from existing JSON result files."""
        # Look for evaluation results in the metrics results directory
        results_dir = Path(__file__).parent.parent.parent / "datasets" / "evaluation" / "metrics" / "results"

        if not results_dir.exists():
            return None

        # Search for model-specific result files - match exact model prefix
        # before the "_evaluation" suffix to avoid substring issues (bert matches roberta)
        model_results = []
        for f in results_dir.iterdir():
            if f.suffix == '.json':
                stem = f.stem
                # Remove _evaluation suffix to get the model identifier
                model_id = stem.removesuffix('_evaluation')
                if model_id == model_name:
                    model_results.append(f)

        if not model_results:
            return None

        # Use the most recent result file
        latest_result = max(model_results, key=lambda p: p.stat().st_mtime)
        with open(latest_result) as f:
            data = json.load(f)

        # Extract classification accuracy and macro F1
        classification = data.get("classification", {})
        extraction = data.get("extraction", {})
        duplicate = data.get("duplicate_detection", {})
        conflict = data.get("conflict_detection", {})

        # f1_score may be a single float or a dict of per-class F1 scores
        f1_raw = classification.get("f1_score", 0.0)
        if isinstance(f1_raw, dict):
            # Macro-average per-class F1 scores
            f1_score = sum(f1_raw.values()) / len(f1_raw) if f1_raw else 0.0
        else:
            f1_score = float(f1_raw)

        return {
            "model_name": model_name,
            "version": data.get("model_version", "1.0.0"),
            "accuracy": classification.get("accuracy", 0.0),
            "f1_score": f1_score,
            "classification_accuracy": classification.get("accuracy", 0.0),
            "classification_f1": f1_score,
            "extraction_exact_match_rate": extraction.get("exact_rule_match_rate", 0.0),
            "duplicate_f1": duplicate.get("f1_score", 0.0),
            "conflict_f1": conflict.get("f1_score", 0.0),
            "average_processing_time_seconds": data.get("average_processing_time_seconds", 0.0),
            "acceptance_criteria_passed": data.get("acceptance_criteria_passed", False),
            "dataset_size": data.get("dataset_size", 0),
            "timestamp": data.get("timestamp", datetime.utcnow().isoformat() + "Z")
        }

    def rank_models(self) -> List[Dict[str, Any]]:
        """Rank all models by evaluation metrics."""
        results = []
        for model_name in self.models:
            print(f"Loading evaluation results for {model_name} model...")
            result = self._load_eval_metrics(model_name)
            if result:
                results.append(result)
                print(f"  {model_name}: Accuracy={result['accuracy']:.2%}, F1={result['f1_score']:.2%}")
            else:
                print(f"  {model_name}: No evaluation results found on disk")

        # Sort by accuracy descending
        results.sort(key=lambda x: x["accuracy"], reverse=True)
        return results

    def promote_model(self, model_name: str, version: str = "1.0.0") -> Dict[str, Any]:
        """Promote a specific model to ACTIVE status through proper lifecycle."""
        model_info = self.models[model_name]
        model_id = self.storage.get_model_version_id(model_info["name"], version, "classification")

        if not model_id:
            print(f"Model {model_info['name']} v{version} not found in database, registering...")
            model_id = self.storage.ensure_model(
                model_name=model_info["name"],
                model_type="classification",
                version=version,
                checkpoint_path=str(model_info["path"]),
                evaluation_metrics={
                    "accuracy": 0.0,
                    "f1_score": 0.0
                }
            )

        # Check current status - skip if already ACTIVE
        current_id = self.storage.get_model_version_id(model_info["name"], version, "classification")
        if current_id:
            from app.db.models.model_version import ModelVersion
            from app.db.database import SessionLocal
            session = SessionLocal()
            try:
                mv = session.query(ModelVersion).filter(
                    ModelVersion.model_version_id == current_id
                ).first()
                if mv and mv.status == "ACTIVE":
                    print(f"  {model_info['name']} is already ACTIVE - skipping promotion")
                    session.close()
                    return {
                        "model_name": model_info["name"],
                        "model_id": model_id,
                        "promotion": {
                            "from_status": "ACTIVE",
                            "to_status": "ACTIVE",
                            "promoted_at": "",
                            "reason": "Already ACTIVE, skipping"
                        }
                    }
            finally:
                session.close()

        # Promote through proper lifecycle: CANDIDATE -> APPROVED -> ACTIVE
        # Step 1: Promote to APPROVED if not already there
        if current_id:
            try:
                approved_result = self.storage.promote(
                    model_version_id=current_id,
                    target_status="APPROVED",
                    reason=f"Promote via CLI: {model_info['name']} v{version} to APPROVED"
                )
                print(f"  {model_info['name']} promoted to APPROVED (was: {approved_result['from_status']})")
            except Exception as e:
                print(f"  Note: APPROVE step: {e}")

        # Step 2: Promote to ACTIVE
        promotion_result = self.storage.promote(
            model_version_id=model_id,
            target_status="ACTIVE",
            reason=f"Promoted via CLI: {model_info['name']} v{version}"
        )

        return {
            "model_name": model_info["name"],
            "model_id": model_id,
            "promotion": promotion_result
        }


def main():
    parser = argparse.ArgumentParser(description="Rank candidate models and promote the best one")
    parser.add_argument("--domain", default="ecommerce", help="Domain to evaluate on")
    parser.add_argument("--list", action="store_true", help="List all models and their status")
    parser.add_argument("--promote", type=str, help="Promote specific model by name (distilbert, bert, roberta)")
    parser.add_argument("--version", type=str, default="1.0.0", help="Model version to promote")
    parser.add_argument("--auto-promote", action="store_true", help="Auto-promote the best ranked model")
    parser.add_argument("--show-db", action="store_true", help="Show current database status")
    args = parser.parse_args()

    ranker = ModelRanker(domain=args.domain)

    if args.list or args.show_db:
        print("Current database status:")
        session = ranker.storage._session()
        from sqlalchemy import text
        try:
            with session.bind.connect() as c:
                for table in ("model_versions", "dataset_versions", "evaluation_runs", "evaluation_metrics", "audit_history"):
                    count = c.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                    print(f"  {table}: {count}")
        finally:
            session.close()
        return

    if args.promote:
        print(f"Promoting {args.promote} v{args.version}...")
        result = ranker.promote_model(args.promote, args.version)
        print(f"Promoted {result['model_name']} (ID: {result['model_id']})")
        print(f"Status: {result['promotion']['from_status']} -> {result['promotion']['to_status']}")
        return

    print("Ranking candidate models...")
    results = ranker.rank_models()

    if results:
        print("\nModel Rankings:")
        print("=" * 60)
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result['model_name']} v{result['version']}")
            print(f"     Accuracy: {result['accuracy']:.2%}")
            print(f"     F1 Score: {result['f1_score']:.2%}")
            print()

        if args.auto_promote:
            best = results[0]
            print(f"Auto-promoting best model: {best['model_name']}...")
            result = ranker.promote_model(best['model_name'].split("-")[0], best['version'])
            print(f"Promoted {result['model_name']} (ID: {result['model_id']})")
            print(f"Status: {result['promotion']['from_status']} -> {result['promotion']['to_status']}")
    else:
        print("No models found to rank.")


if __name__ == "__main__":
    main()