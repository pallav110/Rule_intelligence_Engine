#!/usr/bin/env python3
"""Model Registry initialization and utilities"""

from pathlib import Path
from .registry import ModelRegistry, ModelType, ModelStatus

__all__ = ['ModelRegistry', 'ModelType', 'ModelStatus', 'get_registry']


def get_registry(registry_dir: Path = None) -> ModelRegistry:
    """Get or create the global model registry

    Args:
        registry_dir: Optional custom registry directory

    Returns:
        ModelRegistry instance
    """
    return ModelRegistry(registry_dir)
