from app.schemas.review import ReviewState


def test_review_states_are_defined():
    assert ReviewState.SUGGESTED.value == "SUGGESTED"
    assert ReviewState.UNDER_REVIEW.value == "UNDER_REVIEW"
    assert ReviewState.NEEDS_CLARIFICATION.value == "NEEDS_CLARIFICATION"
    assert ReviewState.APPROVED.value == "APPROVED"
    assert ReviewState.REJECTED.value == "REJECTED"
    assert ReviewState.ARCHIVED.value == "ARCHIVED"