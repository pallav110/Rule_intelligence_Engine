#!/usr/bin/env python3
"""Model loader for production inference

Handles loading models from the registry with automatic version resolution,
caching, and error handling.
"""

import torch
from pathlib import Path
from typing import Optional, Dict, Any
import sys
import logging

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from model_registry import ModelRegistry, ModelStatus, ModelType
from ml_models.distilbert_classifier import MultiTaskDistilBERTClassifier
from ml_models import FEEDBACK_TYPE_LABELS, RULE_CATEGORY_LABELS

logger = logging.getLogger(__name__)


class ModelLoader:
    """Production model loader with registry integration"""

    def __init__(self, device: str = 'cpu'):
        """Initialize model loader

        Args:
            device: 'cpu' or 'cuda'
        """
        self.device = torch.device(device)
        self.registry = ModelRegistry()
        self._model_cache = {}

    def load_production_model(
        self,
        model_name: str,
        model_type: Optional[ModelType] = None
    ) -> Dict[str, Any]:
        """Load the current production model

        Args:
            model_name: Name of the model
            model_type: Optional model type filter

        Returns:
            Dict containing model, metadata, and paths
        """
        print(f"🔍 Loading production model: {model_name}")

        # Get latest production version
        model_metadata = self.registry.get_latest_version(
            model_name,
            status=ModelStatus.PRODUCTION
        )

        if not model_metadata:
            raise ValueError(f"No production model found for {model_name}")

        print(f"✅ Found: v{model_metadata.version} (ID: {model_metadata.model_id})")

        return self._load_model_from_metadata(model_metadata)

    def load_model_by_id(self, model_id: str) -> Dict[str, Any]:
        """Load a specific model by ID

        Args:
            model_id: Model ID from registry

        Returns:
            Dict containing model, metadata, and paths
        """
        metadata = self.registry.get_model(model_id)
        if not metadata:
            raise ValueError(f"Model {model_id} not found in registry")

        return self._load_model_from_metadata(metadata)

    def _load_model_from_metadata(self, metadata) -> Dict[str, Any]:
        """Load model from metadata

        Args:
            metadata: ModelMetadata object

        Returns:
            Dict with loaded model and metadata
        """
        model_path = Path(metadata.model_path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model checkpoint not found: {model_path}")

        print(f"📦 Loading checkpoint from {model_path}")

        # Load model
        checkpoint = torch.load(model_path, map_location=self.device)

        # Instantiate model
        model = MultiTaskDistilBERTClassifier(
            num_feedback_types=len(FEEDBACK_TYPE_LABELS),
            num_rule_categories=len(RULE_CATEGORY_LABELS)
        )

        model.load_state_dict(checkpoint['model_state_dict'])
        model.to(self.device)
        model.eval()

        # Load calibration if available
        calibration_path = model_path.parent / "calibration_params.json"
        calibration_params = None
        if calibration_path.exists():
            import json
            with open(calibration_path, 'r') as f:
                calibration_params = json.load(f)
            print(f"✅ Loaded calibration parameters")

        print(f"✅ Model loaded successfully!")

        return {
            'model': model,
            'metadata': metadata,
            'device': self.device,
            'checkpoint_path': model_path,
            'calibration_params': calibration_params,
            'model_type': metadata.model_type,
            'version': metadata.version,
            'model_id': metadata.model_id
        }

    def list_available_models(self) -> Dict[str, Any]:
        """List all available models by status"""
        result = {}

        for status in [ModelStatus.PRODUCTION, ModelStatus.STAGING, ModelStatus.EXPERIMENTAL]:
            models = self.registry.list_models_by_status(status)
            if models:
                result[status.value] = [
                    {
                        'id': m.model_id,
                        'name': m.model_name,
                        'version': m.version,
                        'type': m.model_type.value,
                        'created': m.created_at,
                        'accuracy': m.evaluation_metrics.get('feedback_type_accuracy', 'N/A')
                    }
                    for m in models
                ]

        return result


def main():
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(description="Model Loader CLI")
    parser.add_argument('action', choices=['load-prod', 'load-by-id', 'list'])
    parser.add_argument('--model-name', help='Model name')
    parser.add_argument('--model-id', help='Model ID')
    parser.add_argument('--device', default='cpu', choices=['cpu', 'cuda'])

    args = parser.parse_args()

    loader = ModelLoader(device=args.device)

    if args.action == 'load-prod':
        if not args.model_name:
            print("❌ --model-name required")
            sys.exit(1)
        result = loader.load_production_model(args.model_name)
        print(f"\n🟢 Production model loaded: {result['metadata'].model_name} v{result['version']}")

    elif args.action == 'load-by-id':
        if not args.model_id:
            print("❌ --model-id required")
            sys.exit(1)
        result = loader.load_model_by_id(args.model_id)
        print(f"\n✅ Model loaded: {result['metadata'].model_name} v{result['version']}")

    elif args.action == 'list':
        import json
        available = loader.list_available_models()
        print("\n📋 Available Models:\n")
        print(json.dumps(available, indent=2))


if __name__ == "__main__":
    main()
