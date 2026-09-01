#!/usr/bin/env python3
"""Model Registry System

Manages model versions, tracking, and lifecycle:
- Registration of new models
- Version management
- Model metadata and lineage
- Promotion/demotion workflows
- Model loading and deployment
"""

import json
import torch
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import uuid
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.metrics_storage import BaselineEvaluationResult


class ModelStatus(str, Enum):
    """Model lifecycle status"""
    EXPERIMENTAL = "experimental"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ModelType(str, Enum):
    """Model type classification"""
    BASELINE_DETERMINISTIC = "baseline_deterministic"
    ML_CANDIDATE = "ml_candidate"
    ML_PRODUCTION = "ml_production"
    ML_DISTILBERT = "ml_distilbert"


@dataclass
class ModelMetadata:
    """Metadata for a registered model"""
    model_id: str
    model_name: str
    model_type: ModelType
    version: str
    status: ModelStatus
    created_at: str
    updated_at: str
    created_by: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    parent_model_id: Optional[str] = None  # For fine-tuned models
    training_config: Dict[str, Any] = field(default_factory=dict)
    evaluation_metrics: Dict[str, Any] = field(default_factory=dict)
    acceptance_criteria_passed: bool = False
    notes: str = ""
    model_path: str = ""
    checksum: str = ""  # For integrity checking

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['model_type'] = self.model_type.value
        data['status'] = self.status.value
        return data


@dataclass
class ModelVersion:
    """Version information for a model"""
    version: str
    model_id: str
    status: ModelStatus
    created_at: str
    evaluation_id: Optional[str] = None
    promotion_date: Optional[str] = None
    promotion_reason: str = ""


class ModelRegistry:
    """Central registry for managing models"""

    def __init__(self, registry_dir: Path = None):
        """Initialize model registry

        Args:
            registry_dir: Directory to store registry files. Defaults to rie_ml/models/registry
        """
        if registry_dir is None:
            registry_dir = Path(__file__).parent.parent.parent / "models" / "registry"

        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_dir = self.registry_dir / "metadata"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        self.index_file = self.registry_dir / "index.json"
        self.lineage_file = self.registry_dir / "lineage.json"

        self._index = self._load_index()
        self._lineage = self._load_lineage()

    def _load_index(self) -> Dict[str, List[ModelMetadata]]:
        """Load model index from disk"""
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                data = json.load(f)
                result = {}
                for model_name, models in data.items():
                    result[model_name] = []
                    for m in models:
                        # Convert string enums back to enum types
                        m['model_type'] = ModelType(m['model_type'])
                        m['status'] = ModelStatus(m['status'])
                        result[model_name].append(ModelMetadata(**m))
                return result
        return {}

    def _save_index(self) -> None:
        """Save model index to disk"""
        data = {
            model_name: [m.to_dict() for m in models]
            for model_name, models in self._index.items()
        }
        with open(self.index_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_lineage(self) -> Dict[str, Any]:
        """Load model lineage from disk"""
        if self.lineage_file.exists():
            with open(self.lineage_file, 'r') as f:
                return json.load(f)
        return {"relationships": {}}

    def _save_lineage(self) -> None:
        """Save model lineage to disk"""
        with open(self.lineage_file, 'w') as f:
            json.dump(self._lineage, f, indent=2)

    def register_model(
        self,
        model_name: str,
        model_type: ModelType,
        version: str,
        model_path: str,
        created_by: str = "system",
        description: str = "",
        tags: List[str] = None,
        parent_model_id: Optional[str] = None,
        training_config: Dict[str, Any] = None,
        evaluation_metrics: Dict[str, Any] = None,
        acceptance_criteria_passed: bool = False,
        notes: str = ""
    ) -> ModelMetadata:
        """Register a new model version

        Args:
            model_name: Human-readable model name
            model_type: Type of model
            version: Version string (e.g., "1.0.0")
            model_path: Path to model checkpoint/artifacts
            created_by: User/system that created the model
            description: Model description
            tags: Tags for categorization
            parent_model_id: ID of parent model if this is a fine-tune
            training_config: Training hyperparameters used
            evaluation_metrics: Evaluation results
            acceptance_criteria_passed: Whether model meets acceptance criteria
            notes: Additional notes

        Returns:
            ModelMetadata object for the registered model
        """
        model_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"

        metadata = ModelMetadata(
            model_id=model_id,
            model_name=model_name,
            model_type=model_type,
            version=version,
            status=ModelStatus.EXPERIMENTAL,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            description=description,
            tags=tags or [],
            parent_model_id=parent_model_id,
            training_config=training_config or {},
            evaluation_metrics=evaluation_metrics or {},
            acceptance_criteria_passed=acceptance_criteria_passed,
            notes=notes,
            model_path=model_path,
            checksum=self._compute_checksum(model_path)
        )

        # Add to index
        if model_name not in self._index:
            self._index[model_name] = []
        self._index[model_name].append(metadata)

        # Add to lineage if parent exists
        if parent_model_id:
            if "relationships" not in self._lineage:
                self._lineage["relationships"] = {}
            self._lineage["relationships"][model_id] = {
                "parent_id": parent_model_id,
                "relationship": "fine_tuned_from"
            }

        # Save metadata file
        metadata_file = self.metadata_dir / f"{model_id}.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)

        self._save_index()
        self._save_lineage()

        return metadata

    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        """Retrieve model metadata by ID"""
        for models in self._index.values():
            for model in models:
                if model.model_id == model_id:
                    return model
        return None

    def get_model_versions(self, model_name: str) -> List[ModelMetadata]:
        """Get all versions of a model"""
        return self._index.get(model_name, [])

    def get_latest_version(self, model_name: str, status: Optional[ModelStatus] = None) -> Optional[ModelMetadata]:
        """Get the latest version of a model, optionally filtered by status

        Args:
            model_name: Name of the model
            status: Optional status filter (e.g., only PRODUCTION models)

        Returns:
            Latest ModelMetadata matching criteria, or None
        """
        versions = self.get_model_versions(model_name)
        if not versions:
            return None

        # Filter by status if specified
        if status:
            versions = [v for v in versions if v.status == status]

        if not versions:
            return None

        # Return most recent by created_at
        return max(versions, key=lambda v: v.created_at)

    def promote_model(
        self,
        model_id: str,
        target_status: ModelStatus,
        promotion_reason: str = ""
    ) -> ModelMetadata:
        """Promote a model to a new status

        Args:
            model_id: ID of model to promote
            target_status: Target status (e.g., PRODUCTION)
            promotion_reason: Reason for promotion

        Returns:
            Updated ModelMetadata
        """
        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        # Validate status transition
        valid_transitions = {
            ModelStatus.EXPERIMENTAL: [ModelStatus.STAGING, ModelStatus.DEPRECATED],
            ModelStatus.STAGING: [ModelStatus.PRODUCTION, ModelStatus.EXPERIMENTAL, ModelStatus.DEPRECATED],
            ModelStatus.PRODUCTION: [ModelStatus.DEPRECATED],
            ModelStatus.DEPRECATED: [ModelStatus.ARCHIVED],
            ModelStatus.ARCHIVED: []
        }

        if target_status not in valid_transitions.get(model.status, []):
            raise ValueError(
                f"Cannot transition from {model.status} to {target_status}"
            )

        # Update model
        model.status = target_status
        model.updated_at = datetime.utcnow().isoformat() + "Z"

        if target_status == ModelStatus.PRODUCTION:
            model.promotion_date = model.updated_at
            model.notes = promotion_reason

        # Demote other versions in same status tier if promoting to PRODUCTION
        if target_status == ModelStatus.PRODUCTION:
            for other_models in self._index.values():
                for other in other_models:
                    if other.model_id != model_id and other.status == ModelStatus.PRODUCTION:
                        other.status = ModelStatus.STAGING
                        other.updated_at = model.updated_at

        # Update metadata file
        metadata_file = self.metadata_dir / f"{model_id}.json"
        with open(metadata_file, 'w') as f:
            json.dump(model.to_dict(), f, indent=2)

        self._save_index()
        return model

    def compare_models(self, model_id_1: str, model_id_2: str) -> Dict[str, Any]:
        """Compare two models side-by-side

        Args:
            model_id_1: First model ID
            model_id_2: Second model ID

        Returns:
            Comparison report
        """
        model1 = self.get_model(model_id_1)
        model2 = self.get_model(model_id_2)

        if not model1 or not model2:
            raise ValueError("One or both models not found")

        return {
            "model_1": {
                "id": model1.model_id,
                "name": model1.model_name,
                "version": model1.version,
                "status": model1.status.value,
                "metrics": model1.evaluation_metrics,
                "created_at": model1.created_at
            },
            "model_2": {
                "id": model2.model_id,
                "name": model2.model_name,
                "version": model2.version,
                "status": model2.status.value,
                "metrics": model2.evaluation_metrics,
                "created_at": model2.created_at
            },
            "comparison_date": datetime.utcnow().isoformat() + "Z"
        }

    def list_models_by_status(self, status: ModelStatus) -> List[ModelMetadata]:
        """List all models with a specific status"""
        models = []
        for model_list in self._index.values():
            models.extend([m for m in model_list if m.status == status])
        return models

    def search_models(self, query: str) -> List[ModelMetadata]:
        """Search models by name or tags

        Args:
            query: Search term

        Returns:
            List of matching models
        """
        results = []
        query_lower = query.lower()

        for model_list in self._index.values():
            for model in model_list:
                # Search by name
                if query_lower in model.model_name.lower():
                    results.append(model)
                    continue

                # Search by tags
                if any(query_lower in tag.lower() for tag in model.tags):
                    results.append(model)
                    continue

                # Search by description
                if query_lower in model.description.lower():
                    results.append(model)

        return results

    def get_model_lineage(self, model_id: str, depth: int = 3) -> Dict[str, Any]:
        """Get the lineage (parent/child relationships) of a model

        Args:
            model_id: Model ID to trace
            depth: How many levels to traverse

        Returns:
            Lineage tree
        """
        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        lineage = {
            "id": model_id,
            "name": model.model_name,
            "version": model.version,
            "children": [],
            "parent": None
        }

        # Add parent
        if model.parent_model_id:
            parent = self.get_model(model.parent_model_id)
            if parent:
                lineage["parent"] = {
                    "id": parent.model_id,
                    "name": parent.model_name,
                    "version": parent.version
                }

        # Add children (if depth > 0)
        if depth > 0:
            relationships = self._lineage.get("relationships", {})
            for child_id, rel in relationships.items():
                if rel.get("parent_id") == model_id:
                    child = self.get_model(child_id)
                    if child:
                        lineage["children"].append({
                            "id": child_id,
                            "name": child.model_name,
                            "version": child.version
                        })

        return lineage

    def export_model_report(self, model_id: str, output_path: Path = None) -> Path:
        """Export a comprehensive model report

        Args:
            model_id: Model ID
            output_path: Where to save the report

        Returns:
            Path to generated report
        """
        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        if output_path is None:
            output_path = self.registry_dir / f"report_{model_id}.json"

        report = {
            "model": model.to_dict(),
            "lineage": self.get_model_lineage(model_id),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        return output_path

    @staticmethod
    def _compute_checksum(model_path: str) -> str:
        """Compute checksum for a model file"""
        import hashlib

        model_path = Path(model_path)
        if not model_path.exists():
            return ""

        sha256_hash = hashlib.sha256()
        with open(model_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()[:16]


def main():
    """Example usage of model registry"""
    import argparse

    parser = argparse.ArgumentParser(description="Model Registry CLI")
    parser.add_argument('command', choices=['register', 'list', 'promote', 'info', 'compare'])
    parser.add_argument('--model-name', help='Model name')
    parser.add_argument('--model-id', help='Model ID')
    parser.add_argument('--version', help='Model version')
    parser.add_argument('--model-path', help='Path to model')
    parser.add_argument('--status', help='Target status')
    parser.add_argument('--compare-with', help='Model ID to compare with')

    args = parser.parse_args()

    registry = ModelRegistry()

    if args.command == 'list':
        for model_name, versions in registry._index.items():
            print(f"\n{model_name}:")
            for v in versions:
                print(f"  v{v.version} ({v.status.value}) - {v.model_id}")

    elif args.command == 'info':
        if args.model_id:
            model = registry.get_model(args.model_id)
            if model:
                print(json.dumps(model.to_dict(), indent=2))

    elif args.command == 'promote':
        if args.model_id and args.status:
            try:
                target_status = ModelStatus[args.status.upper()]
                model = registry.promote_model(args.model_id, target_status)
                print(f"✅ Promoted {model.model_id} to {model.status.value}")
            except Exception as e:
                print(f"❌ Error: {e}")

    elif args.command == 'compare':
        if args.model_id and args.compare_with:
            comparison = registry.compare_models(args.model_id, args.compare_with)
            print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
