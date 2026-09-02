#!/usr/bin/env python3
"""Promote registered models through the lifecycle

Handles model promotion from experimental -> staging -> production,
with validation and approval workflows.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from model_registry import ModelRegistry, ModelStatus


def promote_to_staging(model_id: str, reason: str = ""):
    """Promote model to staging"""
    registry = ModelRegistry()

    print(f"\n📤 Promoting model {model_id} to STAGING...")
    try:
        model = registry.promote_model(
            model_id,
            ModelStatus.STAGING,
            promotion_reason=reason or "Approved for staging deployment"
        )
        print(f"✅ Successfully promoted to STAGING")
        print(f"   Version: {model.version}")
        print(f"   Status: {model.status.value}")
        return model
    except ValueError as e:
        print(f"❌ Promotion failed: {e}")
        sys.exit(1)


def promote_to_production(model_id: str, reason: str = ""):
    """Promote model to production"""
    registry = ModelRegistry()

    print(f"\n📤 Promoting model {model_id} to PRODUCTION...")
    try:
        model = registry.promote_model(
            model_id,
            ModelStatus.PRODUCTION,
            promotion_reason=reason or "Approved for production deployment"
        )
        print(f"✅ Successfully promoted to PRODUCTION")
        print(f"   Version: {model.version}")
        print(f"   Status: {model.status.value}")

        # Save promotion report
        registry_dir = Path(__file__).parent.parent / "models" / "registry"
        promotion_report = registry_dir / "promotion_history.json"

        history = []
        if promotion_report.exists():
            with open(promotion_report, 'r') as f:
                history = json.load(f)

        history.append({
            "model_id": model_id,
            "model_name": model.model_name,
            "version": model.version,
            "promoted_to": "production",
            "promoted_at": datetime.utcnow().isoformat() + "Z",
            "reason": reason or "Approved for production deployment",
            "accuracy": model.evaluation_metrics.get('feedback_type_accuracy', 'N/A')
        })

        with open(promotion_report, 'w') as f:
            json.dump(history, f, indent=2)

        return model
    except ValueError as e:
        print(f"❌ Promotion failed: {e}")
        sys.exit(1)


def get_production_model(model_name: str):
    """Get the current production model for a name"""
    registry = ModelRegistry()

    model = registry.get_latest_version(model_name, status=ModelStatus.PRODUCTION)
    if model:
        print(f"\n🟢 Current Production Model: {model_name}")
        print(f"   Version: {model.version}")
        print(f"   Model ID: {model.model_id}")
        print(f"   Created: {model.created_at}")
        print(f"   Accuracy: {model.evaluation_metrics.get('feedback_type_accuracy', 'N/A')}")
        return model
    else:
        print(f"\n❌ No production model found for {model_name}")
        return None


def show_model_status(model_id: str):
    """Show detailed status of a model"""
    registry = ModelRegistry()

    model = registry.get_model(model_id)
    if not model:
        print(f"❌ Model {model_id} not found")
        sys.exit(1)

    print(f"\n📊 Model Status Report")
    print(f"{'='*60}")
    print(f"Name: {model.model_name}")
    print(f"Version: {model.version}")
    print(f"Status: {model.status.value}")
    print(f"Model ID: {model.model_id}")
    print(f"Type: {model.model_type.value}")
    print(f"Created: {model.created_at}")
    print(f"Updated: {model.updated_at}")
    print(f"Created By: {model.created_by}")
    print(f"\n📈 Evaluation Metrics:")
    if model.evaluation_metrics:
        for key, value in model.evaluation_metrics.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")
    else:
        print("  No metrics available")

    print(f"\n📝 Notes:\n{model.notes}")
    print(f"{'='*60}")

    return model


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Model Promotion CLI")
    parser.add_argument('action', choices=['promote-staging', 'promote-prod', 'status', 'show-prod'])
    parser.add_argument('--model-id', help='Model ID to promote')
    parser.add_argument('--model-name', help='Model name to show production version')
    parser.add_argument('--reason', help='Reason for promotion')

    args = parser.parse_args()

    if args.action == 'promote-staging':
        if not args.model_id:
            print("❌ --model-id required")
            sys.exit(1)
        promote_to_staging(args.model_id, args.reason or "")

    elif args.action == 'promote-prod':
        if not args.model_id:
            print("❌ --model-id required")
            sys.exit(1)
        promote_to_production(args.model_id, args.reason or "")

    elif args.action == 'status':
        if not args.model_id:
            print("❌ --model-id required")
            sys.exit(1)
        show_model_status(args.model_id)

    elif args.action == 'show-prod':
        if not args.model_name:
            print("❌ --model-name required")
            sys.exit(1)
        get_production_model(args.model_name)


if __name__ == "__main__":
    main()
