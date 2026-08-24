import pytest

from app.services.feedback_preprocessor import (
    FeedbackPreprocessor,
    FeedbackValidationError,
)


AVAILABLE_DOMAINS = {
    "ecommerce",
    "customer_support",
    "saas_subscription",
}


def test_valid_feedback_is_normalized():
    result = FeedbackPreprocessor().preprocess(
        "  Refund orders should not count as revenue.  ",
        "ecommerce",
        AVAILABLE_DOMAINS,
    )

    assert result.normalized_text == (
        "Refund orders should not count as revenue."
    )
    assert result.original_text == (
        "  Refund orders should not count as revenue.  "
    )
    assert result.domain == "ecommerce"


def test_empty_feedback_is_rejected():
    with pytest.raises(FeedbackValidationError):
        FeedbackPreprocessor().preprocess(
            "   ",
            "ecommerce",
            AVAILABLE_DOMAINS,
        )


def test_unknown_domain_is_rejected():
    with pytest.raises(FeedbackValidationError):
        FeedbackPreprocessor().preprocess(
            "Refund orders should not count as revenue.",
            "unknown_domain",
            AVAILABLE_DOMAINS,
        )


def test_feedback_over_max_length_is_rejected():
    long_feedback = "a" * 10001

    with pytest.raises(FeedbackValidationError):
        FeedbackPreprocessor().preprocess(
            long_feedback,
            "ecommerce",
            AVAILABLE_DOMAINS,
        )