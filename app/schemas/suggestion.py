"""Schemas for suggestion, clarification, and review APIs."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# Suggestion schemas
class SuggestionCreateRequest(BaseModel):
    workspace_id: str
    feedback_id: str
    suggested_rule: dict
    confidence: float


class SuggestionResponse(BaseModel):
    suggestion_id: str
    workspace_id: str
    feedback_id: str
    suggested_rule: dict
    status: str
    confidence_score: float
    created_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class SuggestionApproveRequest(BaseModel):
    reviewer_id: Optional[str] = None


class SuggestionRejectRequest(BaseModel):
    reviewer_id: Optional[str] = None
    rejection_reason: Optional[str] = None


# Clarification schemas
class ClarificationCreateRequest(BaseModel):
    feedback_id: str
    classification: dict
    extraction: dict


class ClarificationResponse(BaseModel):
    clarification_id: str
    feedback_id: str
    questions: List[str]
    reason: str
    status: str
    response: Optional[str] = None
    created_at: datetime
    responded_at: Optional[datetime] = None


class ClarificationRespondRequest(BaseModel):
    response: str


# Review schemas
class ReviewCreateRequest(BaseModel):
    suggestion_id: str
    reviewer_id: Optional[str] = "auto"
    priority: Optional[str] = "normal"


class ReviewResponse(BaseModel):
    review_id: str
    suggestion_id: str
    reviewer_id: Optional[str] = None
    status: str
    priority: str
    decision: Optional[str] = None
    notes: Optional[str] = None
    assigned_at: datetime
    completed_at: Optional[datetime] = None


class ReviewCompleteRequest(BaseModel):
    decision: str  # "approved" or "rejected"
    notes: Optional[str] = None


class ReviewAssignRequest(BaseModel):
    reviewer_id: str