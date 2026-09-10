#!/usr/bin/env python3
"""CLI to rank candidate models and promote the best one."""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import argparse
import torch
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from evaluation.metrics_storage_db import MetricsStorageDB
from ml_models.model_loader import load_model
from services.ml_model_service import MLModelService

class ModelRanker:
    """Rank candidate models and promote the best one."""

    def __init__(self, domain: str = "ecommerce"):
        self.domain = domain
        self.storage = MetricsStorageDB()
        self.model_service = MLModelService()
        self.models = {
            "distilbert": {
                "path": Path(__file__).parent.parent.parent / "models" / "distilbert_candidate" / "checkpoints" / "best_model.pt",
                "type": "classification",
                "name": "distilbert-classifier",
                "version": "1.0.0"
            },
            "bert": {
                "path": Path(__file__).parent.parent.parent / "models" / "bert_candidate" / "checkpoints" / "best_model.pt",
                "type": "classification",
                "name": "bert-classifier",
                "version": "1.0.0"
            },
            "roberta": {
                "path": Path(__file__).parent.parent.parent / "models" / "roberta_candidate" / "checkpoints" / "best_model.pt",
                "type": "classification",
                "name": "roberta-classifier",
                "version": "1.0.0"
            }
        }
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def evaluate_model(self, model_name: str) -> Dict[str, Any]:
        """Evaluate a single model."""
        model_info = self.models[model_name]
        if not model_info["path"].exists():
            print(f"Warning: Model checkpoint not found at {model_info['path']}")
            return None

        try:
            model = load_model(model_info["path"], model_type=model_info["type"]).to(self.device)

            # Load test dataset
            test_path = Path(__file__).parent.parent.parent / "dataset_generation" / "output" / self.domain / "test.jsonl"
            test_data = [json.loads(line) for line in open(test_path)]

            # Here you would implement actual evaluation
            # For now, we'll use metrics from existing evaluation results
            eval_results_path = Path(__file__).parent.parent.parent / "datasets" / "evaluation" / "metrics" / "results"
            model_results = list(eval_results_path.glob(f"*{model_name}*.json"))

            if model_results:
                latest_result = max(model_results, key=lambda p: p.stat().st_mtime)
                with open(latest_result) as f:
                    data = json.load(f)
                    return {
                        "model_name": model_info["name"],
                        "version": model_info["version"],
                        "accuracy": data.get("classification", {}).get("accuracy", 0.0),
                        "f1_score": data.get("classification", {}).get("f1_score", 0.0),
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
            else:
                # Fallback to mock metrics if no evaluation results found
                return {
                    "model_name": model_info["name"],
                    "version": model_info["version"],
                    "accuracy": 0.0,
                    "f1_score": 0.0,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
        except Exception as e:
            print(f"Error evaluating {model_name}: {str(e)}")
            return None

    def rank_models(self) -> List[Dict[str, Any]]:
        """Rank all models by evaluation metrics."""
        results = []
        for model_name in self.models:
            print(f"Evaluating {model_name} model...")
            result = self.evaluate_model(model_name)
            if result:
                results.append(result)
                print(f"  {model_name}: Accuracy={result['accuracy']:.2%}, F1={result['f1_score']:.2%}")
            else:
                print(f"  {model_name}: FAILED (checkpoint not found or evaluation error)")

        # Sort by accuracy descending
        results.sort(key=lambda x: x["accuracy"], reverse=True)
        return results

    def promote_model(self, model_name: str, version: str = "1.0.0") -> Dict[str, Any]:
        """Promote a specific model to ACTIVE status."""
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
                    "accuracy": 0.0,  # Would be filled from evaluation
                    "f1_score": 0.0
                }
            )

        # Promote the model
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