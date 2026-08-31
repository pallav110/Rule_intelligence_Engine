"""Real review routing service for intelligent reviewer assignment."""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from uuid import uuid4


class ReviewPriority(str, Enum):
    """Review priority levels."""

    AUTO_APPROVE = "auto_approve"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ReviewerType(str, Enum):
    """Types of reviewers."""

    AUTOMATED = "automated"
    DOMAIN_EXPERT = "domain_expert"
    MANAGER = "manager"
    QA = "qa"


class ReviewRouter:
    """Intelligently route suggestions for human or automated review."""

    AUTO_APPROVE_MIN_CONFIDENCE = 0.92
    AUTO_APPROVE_MAX_COMPLEXITY = 2

    def route(
        self,
        suggestion: Dict[str, Any],
        classification: Dict[str, Any],
        extraction: Dict[str, Any],
        conflict_check: Dict[str, Any],
        duplicate_check: Dict[str, Any],
        workspace_id: str,
        domain_id: str,
        clarification_required: bool = False,
    ) -> Dict[str, Any]:
        confidence = classification.get("confidence", 0.0)
        suggested_rule = suggestion or extraction.get("suggested_rule", {})
        has_conflict = conflict_check.get("has_conflict", False)
        is_duplicate = duplicate_check.get("is_duplicate", False)

        complexity = self._calculate_complexity(suggested_rule)
        impact = self._estimate_impact(suggested_rule, classification)
        risk_score = self._calculate_risk(has_conflict, is_duplicate, complexity)

        auto_approval_eligible = (
            confidence >= self.AUTO_APPROVE_MIN_CONFIDENCE
            and complexity <= self.AUTO_APPROVE_MAX_COMPLEXITY
            and not has_conflict
            and not is_duplicate
        )

        # Clarification required takes precedence over everything else
        if clarification_required:
            review_status = "clarification_required"
            priority = ReviewPriority.HIGH
            suggested_reviewer_type = ReviewerType.QA
            suggested_reviewer_id = self._select_reviewer(suggested_reviewer_type, domain_id)
            reasoning_factors = [
                "Mandatory rule information is missing",
                "Clarification required from submitter",
            ]
        elif auto_approval_eligible:
            review_status = "auto_approved"
            priority = ReviewPriority.AUTO_APPROVE
            suggested_reviewer_type = ReviewerType.AUTOMATED
            suggested_reviewer_id = "system:auto_approve"
            reasoning_factors = [
                "High confidence in classification",
                "Low complexity",
                "No conflicts detected",
                "No duplicates detected",
            ]
        else:
            review_status = "pending_review"
            priority, suggested_reviewer_type = self._determine_priority_and_reviewer(
                confidence,
                impact,
                risk_score,
                complexity,
                has_conflict,
                is_duplicate,
            )
            suggested_reviewer_id = self._select_reviewer(suggested_reviewer_type, domain_id)
            reasoning_factors = self._generate_reasoning_factors(
                confidence,
                impact,
                risk_score,
                complexity,
                has_conflict,
                is_duplicate,
            )

        escalation_reasons = []
        if clarification_required:
            escalation_reasons.append("Mandatory rule information is missing")
        if has_conflict:
            escalation_reasons.append("Detected conflicts with existing rules")
        if is_duplicate:
            escalation_reasons.append("Potential duplicate of existing rule")
        if confidence < 0.6:
            escalation_reasons.append("Low classification confidence")
        if complexity > 3:
            escalation_reasons.append("High rule complexity")

        return {
            "review_status": review_status,
            "priority": priority.value,
            "suggested_reviewer_type": suggested_reviewer_type.value,
            "suggested_reviewer_id": suggested_reviewer_id,
            "reasoning": {
                "confidence_score": round(min(1.0, confidence), 3),
                "impact_score": round(impact, 3),
                "complexity_score": round(complexity, 3),
                "risk_score": round(risk_score, 3),
                "factors": reasoning_factors,
            },
            "auto_approval_eligible": auto_approval_eligible,
            "escalation_reasons": escalation_reasons,
            "recommended_actions": self._generate_recommended_actions(
                review_status,
                priority,
                has_conflict,
                is_duplicate,
                confidence,
            ),
        }

    def _calculate_complexity(self, rule: Dict[str, Any]) -> float:
        complexity = 0.0
        complexity += min(0.4, len(rule.get("conditions", [])) * 0.1)

        scope = str(rule.get("scope", "global")).lower()
        if scope == "global":
            complexity += 0.1
        elif any(value in scope for value in ["department", "tier", "segment"]):
            complexity += 0.2
        else:
            complexity += 0.15

        operation = str(rule.get("operation", "")).lower()
        if operation in ["include", "exclude"]:
            complexity += 0.1
        elif operation in ["map", "restrict"]:
            complexity += 0.15
        else:
            complexity += 0.2

        entities = rule.get("affected_entities", {}) or {}
        complexity += min(0.15, len(entities.get("tables", [])) * 0.05)
        return min(1.0, complexity)

    def _estimate_impact(self, rule: Dict[str, Any], classification: Dict[str, Any]) -> float:
        scope = str(rule.get("scope", "global")).lower()
        if scope == "global":
            impact = 0.8
        elif "enterprise" in scope or "all_customers" in scope:
            impact = 0.7
        elif any(value in scope for value in ["department", "team"]):
            impact = 0.5
        else:
            impact = 0.3

        rule_category = str(classification.get("rule_category", "")).lower()
        if any(value in rule_category for value in ["sla", "critical", "revenue", "compliance"]):
            impact += 0.2

        entities = rule.get("affected_entities", {}) or {}
        if len(entities.get("tables", [])) > 2:
            impact += 0.1

        return min(1.0, impact)

    def _calculate_risk(self, has_conflict: bool, is_duplicate: bool, complexity: float) -> float:
        risk = 0.0
        if has_conflict:
            risk += 0.4
        if is_duplicate:
            risk += 0.3
        risk += complexity * 0.3
        return min(1.0, risk)

    def _determine_priority_and_reviewer(
        self,
        confidence: float,
        impact: float,
        risk: float,
        complexity: float,
        has_conflict: bool,
        is_duplicate: bool,
    ) -> Tuple[ReviewPriority, ReviewerType]:
        if (impact > 0.7 and risk > 0.5) or has_conflict:
            return ReviewPriority.URGENT, ReviewerType.MANAGER
        if impact > 0.7 or (confidence > 0.8 and complexity > 0.5):
            return ReviewPriority.HIGH, ReviewerType.DOMAIN_EXPERT
        if impact > 0.4 and risk > 0.2:
            return ReviewPriority.NORMAL, ReviewerType.DOMAIN_EXPERT
        if is_duplicate:
            return ReviewPriority.HIGH, ReviewerType.QA
        return ReviewPriority.LOW, ReviewerType.QA

    def _select_reviewer(self, reviewer_type: ReviewerType, domain_id: str) -> Optional[str]:
        if reviewer_type == ReviewerType.AUTOMATED:
            return "system:auto_approve"
        if reviewer_type == ReviewerType.MANAGER:
            return f"reviewer:manager:{domain_id}"
        if reviewer_type == ReviewerType.DOMAIN_EXPERT:
            return f"reviewer:expert:{domain_id}"
        return f"reviewer:qa:{domain_id}"

    def _generate_reasoning_factors(
        self,
        confidence: float,
        impact: float,
        risk: float,
        complexity: float,
        has_conflict: bool,
        is_duplicate: bool,
    ) -> List[str]:
        factors = []
        if confidence > 0.85:
            factors.append(f"High confidence ({confidence:.0%})")
        elif confidence < 0.65:
            factors.append(f"Low confidence ({confidence:.0%})")

        if impact > 0.7:
            factors.append("High business impact")
        elif impact < 0.4:
            factors.append("Low business impact")

        if risk > 0.6:
            factors.append("High risk profile")
        elif risk < 0.3:
            factors.append("Low risk profile")

        if complexity > 0.6:
            factors.append("High complexity")
        elif complexity < 0.3:
            factors.append("Low complexity")

        if has_conflict:
            factors.append("Conflicts with existing rules")
        if is_duplicate:
            factors.append("Potential duplicate")

        return factors

    def _generate_recommended_actions(
        self,
        review_status: str,
        priority: ReviewPriority,
        has_conflict: bool,
        is_duplicate: bool,
        confidence: float,
    ) -> List[str]:
        actions = []
        if review_status == "auto_approved":
            actions.append("Convert to business rule draft")
            actions.append("Schedule for stakeholder review")
            return actions

        if priority == ReviewPriority.URGENT:
            actions.append("Assign to manager immediately")
            actions.append("Schedule urgent review meeting")
        if has_conflict:
            actions.append("Contact existing rule owner")
            actions.append("Schedule conflict resolution discussion")
        if is_duplicate:
            actions.append("Compare with existing rule")
            actions.append("Determine if consolidation is possible")
        if confidence < 0.6:
            actions.append("Request additional clarification")
            actions.append("Re-analyze with expanded domain context")

        return actions


class RealReviewRoutingService:
    """Production review routing service with database integration."""

    def __init__(self):
        self.router = ReviewRouter()

    def route_suggestion(
        self,
        suggestion_id: str,
        suggestion: Dict[str, Any],
        classification: Dict[str, Any],
        extraction: Dict[str, Any],
        conflict_check: Dict[str, Any],
        duplicate_check: Dict[str, Any],
        workspace_id: str,
        domain_id: str,
        db=None,
        clarification_required: bool = False,
    ) -> Dict[str, Any]:
        routing_decision = self.router.route(
            suggestion,
            classification,
            extraction,
            conflict_check,
            duplicate_check,
            workspace_id,
            domain_id,
            clarification_required,
        )

        if db and routing_decision["review_status"] != "auto_approved":
            try:
                from app.db.models.review import Review

                review_id = str(uuid4())
                review = Review(
                    review_id=review_id,
                    suggestion_id=suggestion_id,
                    workspace_id=workspace_id,
                    reviewer_id=routing_decision["suggested_reviewer_id"],
                    status="assigned",
                    priority=routing_decision["priority"],
                    decision=None,
                    notes=None,
                    assigned_at=datetime.utcnow(),
                    completed_at=None,
                    created_at=datetime.utcnow(),
                )
                db.add(review)
                db.flush()

                routing_decision["review_id"] = review_id
                routing_decision["persisted"] = True
            except Exception as e:
                routing_decision["db_error"] = str(e)
                routing_decision["persisted"] = False

        return routing_decision


ReviewRoutingService = RealReviewRoutingService
