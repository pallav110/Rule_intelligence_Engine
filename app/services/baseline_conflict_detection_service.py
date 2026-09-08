"""Thin backward-compatible alias for the unified ConflictDetectionService.

All logic now lives in ``app.services.conflict_detection_service``.
This module re-exports the old names so existing imports keep working.
"""

from app.services.conflict_detection_service import (
    ConflictDetectionService,
    ConflictDetector,
    to_spec_conflict_type,
    CONFLICT_TYPE_SPEC_MAP,
)


class BaselineConflictDetectionService(ConflictDetectionService):
    """Convenience alias that forces engine='baseline'."""

    def __init__(self):
        super().__init__(engine="baseline")


# Keep the old detector class name working for any direct imports.
BaselineConflictDetector = ConflictDetector
