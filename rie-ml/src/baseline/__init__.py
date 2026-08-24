"""RIE-ML baseline package.

Exports the deterministic baseline models that the backend services
(`app/services/classifier.py`, `app/services/rule_extractor.py`)
consume via ``rie_ml.baseline``.
"""

from .classifier import BaselineClassifier
from .extractor import BaselineRuleExtractor

__all__ = [
    "BaselineClassifier",
    "BaselineRuleExtractor",
]