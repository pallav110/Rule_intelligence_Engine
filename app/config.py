"""
Application configuration for Rule Intelligence Engine.

Handles environment-based configuration including external model data policy
for Spec §10.6 and data retention policies for Spec §10.7.
"""

import os
from typing import Optional


class Settings:
    """Application settings loaded from environment variables."""

    # External Model Data Policy (Spec §10.6)
    # Controls whether feedback data can be sent to external AI services
    EXTERNAL_MODEL_DATA_ENABLED: bool = (
        os.getenv("RIE_EXTERNAL_MODEL_DATA_ENABLED", "false").lower() == "true"
    )

    # When external model data is enabled, these additional settings apply:
    EXTERNAL_MODEL_ENDPOINT: Optional[str] = os.getenv("RIE_EXTERNAL_MODEL_ENDPOINT")
    EXTERNAL_MODEL_API_KEY: Optional[str] = os.getenv("RIE_EXTERNAL_MODEL_API_KEY")
    EXTERNAL_MODEL_CONSENT_REQUIRED: bool = (
        os.getenv("RIE_EXTERNAL_MODEL_CONSENT_REQUIRED", "true").lower() == "true"
    )

    # Security settings for external transmission
    EXTERNAL_MODEL_ENCRYPTION_REQUIRED: bool = (
        os.getenv("RIE_EXTERNAL_MODEL_ENCRYPTION_REQUIRED", "true").lower() == "true"
    )

    # Data protection compliance
    EXTERNAL_MODEL_DATA_PROTECTION_COMPLIANT: bool = (
        os.getenv("RIE_EXTERNAL_MODEL_DATA_PROTECTION_COMPLIANT", "false").lower() == "true"
    )

    # Audit logging for external transmissions
    EXTERNAL_MODEL_AUDIT_LOGGING_ENABLED: bool = (
        os.getenv("RIE_EXTERNAL_MODEL_AUDIT_LOGGING_ENABLED", "true").lower() == "true"
    )

    # Data Retention and Deletion Policies (Spec §10.7)
    # Feedback retention in days (configurable)
    RETENTION_FEEDBACK_DAYS: int = int(os.getenv("RIE_RETENTION_FEEDBACK_DAYS", "365"))
    # Suggestions retention in days (configurable)
    RETENTION_SUGGESTIONS_DAYS: int = int(os.getenv("RIE_RETENTION_SUGGESTIONS_DAYS", "365"))
    # Audit History retention: long-term retention (boolean)
    RETENTION_AUDIT_HISTORY_LONG_TERM: bool = (
        os.getenv("RIE_RETENTION_AUDIT_HISTORY_LONG_TERM", "true").lower() == "true"
    )
    # Evaluation Results retention: version controlled (boolean)
    RETENTION_EVALUATION_RESULTS_VERSION_CONTROLLED: bool = (
        os.getenv("RIE_RETENTION_EVALUATION_RESULTS_VERSION_CONTROLLED", "true").lower() == "true"
    )
    # Background Jobs retention in days (configurable)
    RETENTION_BACKGROUND_JOBS_DAYS: int = int(os.getenv("RIE_RETENTION_BACKGROUND_JOBS_DAYS", "30"))


# Global settings instance
settings = Settings()


def is_external_model_data_allowed() -> bool:
    """
    Check if external model data transmission is allowed per Spec §10.6.

    Returns:
        bool: True if external model data transmission is enabled and properly configured
    """
    if not settings.EXTERNAL_MODEL_DATA_ENABLED:
        return False

    # If consent is required, check if it's been given
    if settings.EXTERNAL_MODEL_CONSENT_REQUIRED:
        # In a real implementation, this would check a consent database or flag
        # For now, we rely on the explicit ENABLED flag combined with consent requirement
        pass

    # Check if endpoint is configured when external model data is enabled
    if settings.EXTERNAL_MODEL_DATA_ENABLED and not settings.EXTERNAL_MODEL_ENDPOINT:
        return False

    # Check if data protection compliance is required and met
    if settings.EXTERNAL_MODEL_DATA_PROTECTION_COMPLIANT_REQUIRED and not settings.EXTERNAL_MODEL_DATA_PROTECTION_COMPLIANT:
        return False

    return True


def get_external_model_config() -> dict:
    """
    Get external model configuration for use by services.

    Returns:
        dict: Configuration for external model services
    """
    return {
        "enabled": settings.EXTERNAL_MODEL_DATA_ENABLED,
        "endpoint": settings.EXTERNAL_MODEL_ENDPOINT,
        "api_key": settings.EXTERNAL_MODEL_API_KEY,
        "consent_required": settings.EXTERNAL_MODEL_CONSENT_REQUIRED,
        "encryption_required": settings.EXTERNAL_MODEL_ENCRYPTION_REQUIRED,
        "data_protection_compliant": settings.EXTERNAL_MODEL_DATA_PROTECTION_COMPLIANT,
        "audit_logging_enabled": settings.EXTERNAL_MODEL_AUDIT_LOGGING_ENABLED,
    }


def get_retention_feedback_days() -> int:
    """
    Get feedback retention period in days.

    Returns:
        int: Retention period for feedback in days
    """
    return settings.RETENTION_FEEDBACK_DAYS


def get_retention_suggestions_days() -> int:
    """
    Get suggestions retention period in days.

    Returns:
        int: Retention period for suggestions in days
    """
    return settings.RETENTION_SUGGESTIONS_DAYS


def is_audit_history_long_term() -> bool:
    """
    Check if audit history should be retained long-term.

    Returns:
        bool: True if audit history is configured for long-term retention
    """
    return settings.RETENTION_AUDIT_HISTORY_LONG_TERM


def are_evaluation_results_version_controlled() -> bool:
    """
    Check if evaluation results should be version controlled.

    Returns:
        bool: True if evaluation results are configured for version control
    """
    return settings.RETENTION_EVALUATION_RESULTS_VERSION_CONTROLLED


def get_retention_background_jobs_days() -> int:
    """
    Get background jobs retention period in days.

    Returns:
        int: Retention period for background jobs in days
    """
    return settings.RETENTION_BACKGROUND_JOBS_DAYS