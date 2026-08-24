"""Real clarification generation service for ambiguous feedback."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from uuid import uuid4


class ClarificationGenerator:
    """Generate clarification questions for ambiguous feedback."""

    def __init__(self):
        """Initialize clarification generator."""
        self.question_templates = self._load_question_templates()

    def _load_question_templates(self) -> Dict[str, List[str]]:
        """Load question templates for common ambiguities."""
        return {
            "scope": [
                "What is the exact scope of this rule? (global, department-specific, customer-tier-specific, etc.)",
                "Should this rule apply to all customers or specific segments?",
                "Are there any exclusions or exceptions to this rule?",
            ],
            "conditions": [
                "What are the specific conditions that should trigger this rule?",
                "How should edge cases be handled?",
                "Are there any threshold values or time-based conditions?",
            ],
            "timeline": [
                "What is the time window for this rule?",
                "Should this be evaluated daily, weekly, or in real-time?",
                "Is there a specific start/end date for this rule?",
            ],
            "entities": [
                "Which specific tables or entities does this rule affect?",
                "What are the primary and secondary entities involved?",
                "Are there any relationships or joins required?",
            ],
            "priority": [
                "What is the priority or urgency of this rule?",
                "How should this rule be prioritized relative to other rules?",
            ],
            "impact": [
                "What is the expected business impact of this rule?",
                "How many records or customers would be affected?",
                "What are the potential side effects?",
            ],
            "operation": [
                "Should records be excluded, included, modified, or something else?",
                "What specific action should be taken?",
                "Are there multiple possible actions depending on conditions?",
            ],
        }

    def generate(
        self,
        feedback_text: str,
        classification: Dict[str, Any],
        extraction: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate clarification questions based on feedback ambiguity.

        Returns:
            {
                "requires_clarification": bool,
                "confidence": float,
                "questions": [str],
                "ambiguity_reasons": [str],
                "extraction_gaps": [str],
                "suggested_focus_areas": [str],
            }
        """
        ambiguity_reasons = []
        extraction_gaps = []
        suggested_questions = []

        # 1. Check classification confidence
        classification_confidence = classification.get("confidence", 0.0)
        if classification_confidence < 0.6:
            ambiguity_reasons.append(f"Low classification confidence ({classification_confidence:.2%})")
            suggested_questions.extend(self.question_templates["scope"])

        # 2. Check for actionability concerns
        if not classification.get("is_actionable", False):
            ambiguity_reasons.append("Feedback flagged as non-actionable")
            suggested_questions.extend(self.question_templates["conditions"])

        # 3. Check extraction gaps
        extracted_rules = extraction.get("extracted_rules", [])
        if not extracted_rules or len(extracted_rules) == 0:
            ambiguity_reasons.append("No concrete rules could be extracted")
            extraction_gaps.append("No business terms identified")
            suggested_questions.extend(self.question_templates["entities"])
            suggested_questions.extend(self.question_templates["operation"])

        else:
            for rule in extracted_rules:
                # Check for missing critical fields
                if not rule.get("business_term"):
                    extraction_gaps.append("Missing business term")
                    suggested_questions.extend(self.question_templates["scope"])

                if not rule.get("conditions") or len(rule.get("conditions", [])) == 0:
                    extraction_gaps.append("Missing conditions or thresholds")
                    suggested_questions.extend(self.question_templates["conditions"])

                if not rule.get("affected_entities", {}).get("tables"):
                    extraction_gaps.append("Affected entities not identified")
                    suggested_questions.extend(self.question_templates["entities"])

                if not rule.get("operation"):
                    extraction_gaps.append("Operation/action not specified")
                    suggested_questions.extend(self.question_templates["operation"])

                # Check for scope ambiguity
                scope = rule.get("scope", "").lower()
                if not scope or scope == "unknown":
                    ambiguity_reasons.append("Rule scope is ambiguous")
                    suggested_questions.extend(self.question_templates["scope"])

        # 4. Check for temporal ambiguity
        if "time" in feedback_text.lower() or "when" in feedback_text.lower():
            has_time_info = any(
                rule.get("time_window") or rule.get("threshold") for rule in extracted_rules
            )
            if not has_time_info:
                ambiguity_reasons.append("Temporal aspects mentioned but not captured")
                extraction_gaps.append("Time window not specified")
                suggested_questions.extend(self.question_templates["timeline"])

        # 5. Deduplicate questions while preserving order
        seen = set()
        unique_questions = []
        for q in suggested_questions:
            if q not in seen:
                unique_questions.append(q)
                seen.add(q)

        # Limit to top 5 most relevant questions
        unique_questions = unique_questions[:5]

        # Determine if clarification is truly needed
        requires_clarification = (
            len(ambiguity_reasons) > 0
            or len(extraction_gaps) > 0
            or classification_confidence < 0.7
        )

        # Calculate confidence that clarification will help
        clarification_confidence = min(0.99, max(0.5, 1.0 - classification_confidence))

        return {
            "requires_clarification": requires_clarification,
            "confidence": round(clarification_confidence, 3),
            "questions": unique_questions,
            "ambiguity_reasons": ambiguity_reasons,
            "extraction_gaps": extraction_gaps,
            "suggested_focus_areas": self._identify_focus_areas(ambiguity_reasons, extraction_gaps),
        }

    def _identify_focus_areas(self, ambiguity_reasons: List[str], extraction_gaps: List[str]) -> List[str]:
        """Identify which aspects need most focus in clarification."""
        focus_areas = []

        if any("scope" in reason.lower() for reason in ambiguity_reasons + extraction_gaps):
            focus_areas.append("scope")

        if any("condition" in reason.lower() or "threshold" in reason.lower() for reason in ambiguity_reasons + extraction_gaps):
            focus_areas.append("conditions")

        if any("time" in reason.lower() for reason in ambiguity_reasons + extraction_gaps):
            focus_areas.append("timeline")

        if any("entit" in reason.lower() for reason in ambiguity_reasons + extraction_gaps):
            focus_areas.append("affected_entities")

        if any("operation" in reason.lower() or "action" in reason.lower() for reason in ambiguity_reasons + extraction_gaps):
            focus_areas.append("operation")

        return focus_areas


class RealClarificationService:
    """Production clarification service with database integration."""

    def __init__(self):
        """Initialize service."""
        self.generator = ClarificationGenerator()

    def generate_clarification(
        self,
        feedback_id: str,
        feedback_text: str,
        classification: Dict[str, Any],
        extraction: Dict[str, Any],
        workspace_id: str,
        db=None,
    ) -> Dict[str, Any]:
        """Generate and persist clarification record."""
        # Generate questions
        clarification_data = self.generator.generate(feedback_text, classification, extraction)

        if not clarification_data["requires_clarification"]:
            return {
                "clarification_id": None,
                "created": False,
                "reason": "Feedback clarity is sufficient",
                "details": clarification_data,
            }

        # If DB available, persist clarification
        if db:
            try:
                from app.db.models.clarification import Clarification

                clarification_id = str(uuid4())
                clarification = Clarification(
                    clarification_id=clarification_id,
                    feedback_id=feedback_id,
                    workspace_id=workspace_id,
                    questions=clarification_data["questions"],
                    reason="; ".join(clarification_data["ambiguity_reasons"]),
                    status="pending",
                    response=None,
                    created_at=datetime.utcnow(),
                    responded_at=None,
                )
                db.add(clarification)
                db.flush()

                return {
                    "clarification_id": clarification_id,
                    "created": True,
                    "feedback_id": feedback_id,
                    "questions": clarification_data["questions"],
                    "status": "pending",
                    "reason": "; ".join(clarification_data["ambiguity_reasons"]),
                    "details": clarification_data,
                }

            except Exception as e:
                return {
                    "clarification_id": None,
                    "created": False,
                    "error": str(e),
                    "details": clarification_data,
                }
        else:
            # Return transient clarification (not persisted)
            return {
                "clarification_id": str(uuid4()),
                "created": False,
                "persisted": False,
                "questions": clarification_data["questions"],
                "details": clarification_data,
            }

    def respond_to_clarification(
        self,
        clarification_id: str,
        response_text: str,
        db=None,
    ) -> Dict[str, Any]:
        """Handle clarification response and trigger re-analysis."""
        if not db:
            return {
                "success": False,
                "message": "Database connection required",
            }

        try:
            from sqlalchemy import text

            # Update clarification status
            query = text(
                """
                UPDATE clarifications
                SET status = 'answered', response = :response, responded_at = NOW()
                WHERE clarification_id = :clarification_id
                RETURNING feedback_id, workspace_id
            """
            )

            result = db.execute(
                query, {"clarification_id": clarification_id, "response": response_text}
            )
            db.commit()

            row = result.fetchone()
            if row:
                feedback_id, workspace_id = row
                return {
                    "success": True,
                    "clarification_id": clarification_id,
                    "feedback_id": feedback_id,
                    "workspace_id": workspace_id,
                    "message": "Clarification response received. Ready for re-analysis.",
                    "next_step": "re_analyze_with_clarification",
                }
            else:
                return {
                    "success": False,
                    "message": "Clarification not found",
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
