"""Calibration utilities for probability calibration (temperature scaling).

Provides simple temperature-scaling utilities that operate on probabilities by
converting to logits and back. Used to adjust module confidences before
making routing decisions.
"""
import math
from typing import Dict, Any


def _safe_logit(p: float) -> float:
    p = min(max(p, 1e-6), 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def calibrate_probability(p: float, temperature: float = 1.0) -> float:
    """Calibrate a single probability via temperature scaling.

    Args:
        p: input probability in (0,1).
        temperature: >0 temperature parameter; 1.0 means no change.

    Returns:
        calibrated probability in (0,1).
    """
    try:
        if temperature <= 0 or math.isclose(temperature, 1.0):
            return p
        logit = _safe_logit(p)
        calibrated = _sigmoid(logit / temperature)
        return float(min(max(calibrated, 0.0), 1.0))
    except Exception:
        return p


def calibrate_confidences(confidences: Dict[str, float], temperature: float = 1.0) -> Dict[str, float]:
    """Apply temperature scaling to a dictionary of confidences.

    Returns a new dict with calibrated values.
    """
    return {k: calibrate_probability(float(v or 0.0), temperature) for k, v in (confidences or {}).items()}
