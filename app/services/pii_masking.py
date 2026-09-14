"""Personally Identifiable Information (PII) masking service for Spec §10.4.

Implements PII detection and masking to protect sensitive information
before it appears in logs, monitoring dashboards, or error messages.
"""

import re
from typing import Optional, Union
from app.logging_config import get_logger

logger = get_logger('pii_masking')


class PIIMasker:
    """Service for detecting and masking personally identifiable information."""

    # Regex patterns for common PII types
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    PHONE_PATTERN = re.compile(r'\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
    SSN_PATTERN = re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b')
    CREDIT_CARD_PATTERN = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')

    @staticmethod
    def mask_email(text: str) -> str:
        """Mask email addresses in text."""
        return PIIMasker.EMAIL_PATTERN.sub('[EMAIL_REDACTED]', text)

    @staticmethod
    def mask_phone(text: str) -> str:
        """Mask phone numbers in text."""
        return PIIMasker.PHONE_PATTERN.sub('[PHONE_REDACTED]', text)

    @staticmethod
    def mask_ssn(text: str) -> str:
        """Mask Social Security Numbers in text."""
        return PIIMasker.SSN_PATTERN.sub('[SSN_REDACTED]', text)

    @staticmethod
    def mask_credit_card(text: str) -> str:
        """Mask credit card numbers in text."""
        return PIIMasker.CREDIT_CARD_PATTERN.sub('[CREDIT_CARD_REDACTED]', text)

    @classmethod
    def mask_all_pii(cls, text: str) -> str:
        """Apply all PII masking to text."""
        if not text or not isinstance(text, str):
            return text

        masked = cls.mask_email(text)
        masked = cls.mask_phone(masked)
        masked = cls.mask_ssn(masked)
        masked = cls.mask_credit_card(masked)
        return masked

    @staticmethod
    def safe_log_text(text: Union[str, object], max_length: int = 200) -> str:
        """
        Safely prepare text for logging by:
        1. Converting to string if needed
        2. Truncating to max_length
        3. Applying PII masking
        """
        if text is None:
            return "None"

        # Convert to string
        text_str = str(text)

        # Truncate if too long
        if len(text_str) > max_length:
            text_str = text_str[:max_length] + "...[TRUNCATED]"

        # Apply PII masking
        return PIIMasker.mask_all_pii(text_str)


def mask_feedback_text(text: Optional[str]) -> str:
    """
    Mask PII in feedback text for safe logging.
    This function should be used wherever feedback text might be logged.
    """
    if not text:
        return ""
    return PIIMasker.mask_all_pii(text)


def mask_dict_for_logging(data: dict, sensitive_keys: Optional[set] = None) -> dict:
    """
    Create a copy of a dictionary with sensitive values masked for logging.

    Args:
        data: Dictionary to mask
        sensitive_keys: Set of keys to consider sensitive (if None, uses defaults)

    Returns:
        New dictionary with sensitive values masked
    """
    if not isinstance(data, dict):
        return {}

    if sensitive_keys is None:
        sensitive_keys = {
            'password', 'secret', 'token', 'credential', 'ssn',
            'social_security', 'credit_card', 'email', 'phone',
            'authorization', 'cookie', 'session'
        }

    masked_data = {}
    for key, value in data.items():
        key_lower = str(key).lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            masked_data[key] = '[REDACTED]'
        elif isinstance(value, str):
            masked_data[key] = PIIMasker.mask_all_pii(value)
        elif isinstance(value, dict):
            masked_data[key] = mask_dict_for_logging(value, sensitive_keys)
        elif isinstance(value, (list, tuple)):
            masked_data[key] = [
                PIIMasker.mask_all_pii(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            masked_data[key] = value

    return masked_data


# Convenience function for quick masking in logging statements
def safe_log(message: str, *args) -> str:
    """
    Format a log message with PII masking applied to all arguments.

    Usage:
        logger.info(safe_log("User %s logged in from %s", user_id, ip_address))
    """
    if not args:
        return PIIMasker.mask_all_pii(message)

    # Mask all arguments
    masked_args = []
    for arg in args:
        if isinstance(arg, str):
            masked_args.append(PIIMasker.mask_all_pii(arg))
        elif isinstance(arg, dict):
            masked_args.append(mask_dict_for_logging(arg))
        else:
            masked_args.append(str(arg))

    try:
        formatted = message % tuple(masked_args) if len(masked_args) == 1 else message.format(*masked_args)
    except (ValueError, IndexError):
        # Fallback to simple concatenation if formatting fails
        formatted = message + " " + " ".join(str(arg) for arg in masked_args)

    return PIIMasker.mask_all_pii(formatted)