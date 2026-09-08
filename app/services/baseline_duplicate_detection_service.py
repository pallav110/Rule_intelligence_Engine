"""Thin backward-compatible alias for the unified DuplicateDetectionService.

All logic now lives in ``app.services.duplicate_detection_service``.
This module re-exports the old names so existing imports keep working.
"""

from app.services.duplicate_detection_service import (
    DuplicateDetectionService,
    DuplicateDetector,
    to_spec_relationship_type,
    RELATIONSHIP_TYPE_SPEC_MAP,
)


class BaselineDuplicateDetectionService(DuplicateDetectionService):
    """Convenience alias that forces engine='baseline'."""

    def __init__(self):
        super().__init__(engine="baseline")


# Keep the old detector class name working for any direct imports.
BaselineDuplicateDetector = DuplicateDetector
