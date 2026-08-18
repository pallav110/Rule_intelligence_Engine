from dataclasses import dataclass
from uuid import UUID, uuid4


MAX_FEEDBACK_LENGTH = 10_000


class FeedbackValidationError(ValueError):
    pass


@dataclass
class PreprocessedFeedback:
    feedback_id: UUID
    original_text: str
    normalized_text: str
    domain: str


class FeedbackPreprocessor:
    def preprocess(
        self,
        feedback: str,
        domain: str,
        available_domains: set[str],
    ) -> PreprocessedFeedback:
        if not isinstance(feedback, str):
            raise FeedbackValidationError("Feedback must be a string.")

        if not feedback.strip():
            raise FeedbackValidationError("Feedback cannot be empty.")

        if len(feedback) > MAX_FEEDBACK_LENGTH:
            raise FeedbackValidationError(
                f"Feedback exceeds maximum length of {MAX_FEEDBACK_LENGTH} characters."
            )

        if not isinstance(domain, str) or not domain.strip():
            raise FeedbackValidationError("Domain is required.")

        original_text = feedback
        normalized_text = " ".join(feedback.split())
        normalized_domain = domain.strip()

        if normalized_domain not in available_domains:
           raise FeedbackValidationError(
               f"Unknown domain: {normalized_domain}"
       )

        return PreprocessedFeedback(
            feedback_id=uuid4(),
            original_text=original_text,
            normalized_text=normalized_text,
            domain=normalized_domain,
        )