"""Real clarification generation service for ambiguous feedback."""

from typing import Any, Dict, List
from datetime import datetime
from uuid import uuid4


class ClarificationGenerator:
    """Generate clarification questions for ambiguous feedback."""

    def __init__(self):
        self.question_templates = self._load_question_templates()

    def _load_question_templates(self) -> Dict[str, List[str]]:
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
        ambiguity_reasons = []
        extraction_gaps = []
        suggested_questions = []

        classification_confidence = classification.get("confidence", 0.0)
        is_actionable = classification.get("is_actionable", False)

        # Only add ambiguity reasons if actually applicable
        if classification_confidence < 0.6:
            ambiguity_reasons.append(f"Low classification confidence ({classification_confidence:.2%})")
            suggested_questions.extend(self.question_templates["scope"])

        # Only add non-actionable reason if actually non-actionable
        if not is_actionable:
            ambiguity_reasons.append("Feedback flagged as non-actionable")
            suggested_questions.extend(self.question_templates["conditions"])

        extracted_rules = extraction.get("extracted_rules") or extraction.get("rules") or []
        if isinstance(extraction.get("extraction"), dict):
            extracted_rules = extraction["extraction"].get("extracted_rules", extracted_rules)
            # Also get candidate rules count
            candidate_rules = extraction["extraction"].get("candidate_rules", [])

        if not extracted_rules:
            ambiguity_reasons.append("No concrete rules could be extracted")
            extraction_gaps.append("No business terms identified")
            suggested_questions.extend(self.question_templates["entities"])
            suggested_questions.extend(self.question_templates["operation"])
        else:
            # Check for ambiguity in extracted rules
            for rule in extracted_rules:
                if not rule.get("business_term"):
                    extraction_gaps.append("Missing business term")
                    suggested_questions.extend(self.question_templates["scope"])

                # Missing conditions is NOT necessarily an ambiguity - some rules don't need conditions
                # Only flag if there's a condition mentioned in feedback but not extracted
                feedback_lower = feedback_text.lower()
                has_condition_mention = any(word in feedback_lower for word in ["when", "if", "status", "equals", "greater", "less", "before", "after"])
                if not rule.get("conditions") and has_condition_mention:
                    extraction_gaps.append("Conditions mentioned but not extracted")
                    suggested_questions.extend(self.question_templates["conditions"])

                if not rule.get("affected_entities", {}).get("tables"):
                    extraction_gaps.append("Affected entities not identified")
                    suggested_questions.extend(self.question_templates["entities"])

                if not rule.get("operation"):
                    extraction_gaps.append("Operation/action not specified")
                    suggested_questions.extend(self.question_templates["operation"])

                scope = str(rule.get("scope", "")).lower()
                if not scope or scope == "unknown":
                    ambiguity_reasons.append("Rule scope is ambiguous")
                    suggested_questions.extend(self.question_templates["scope"])
            for rule in extracted_rules:
                if not rule.get("business_term"):
                    extraction_gaps.append("Missing business term")
                    suggested_questions.extend(self.question_templates["scope"])

                if not rule.get("conditions"):
                    extraction_gaps.append("Missing conditions or thresholds")
                    suggested_questions.extend(self.question_templates["conditions"])

                if not rule.get("affected_entities", {}).get("tables"):
                    extraction_gaps.append("Affected entities not identified")
                    suggested_questions.extend(self.question_templates["entities"])

                if not rule.get("operation"):
                    extraction_gaps.append("Operation/action not specified")
                    suggested_questions.extend(self.question_templates["operation"])

                scope = str(rule.get("scope", "")).lower()
                if not scope or scope == "unknown":
                    ambiguity_reasons.append("Rule scope is ambiguous")
                    suggested_questions.extend(self.question_templates["scope"])

        if "time" in feedback_text.lower() or "when" in feedback_text.lower():
            has_time_info = any(
                rule.get("time_window") or rule.get("threshold") for rule in extracted_rules
            )
            if not has_time_info:
                ambiguity_reasons.append("Temporal aspects mentioned but not captured")
                extraction_gaps.append("Time window not specified")
                suggested_questions.extend(self.question_templates["timeline"])

        seen = set()
        unique_questions = []
        for question in suggested_questions:
            if question not in seen:
                unique_questions.append(question)
                seen.add(question)

        unique_questions = unique_questions[:5]
        requires_clarification = (
            bool(ambiguity_reasons)
            or bool(extraction_gaps)
            or classification_confidence < 0.7
        )
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
        focus_areas = []
        combined = ambiguity_reasons + extraction_gaps

        if any("scope" in reason.lower() for reason in combined):
            focus_areas.append("scope")
        if any("condition" in reason.lower() or "threshold" in reason.lower() for reason in combined):
            focus_areas.append("conditions")
        if any("time" in reason.lower() for reason in combined):
            focus_areas.append("timeline")
        if any("entit" in reason.lower() for reason in combined):
            focus_areas.append("affected_entities")
        if any("operation" in reason.lower() or "action" in reason.lower() for reason in combined):
            focus_areas.append("operation")

        return focus_areas


class RealClarificationService:
    """Production clarification service with database integration."""

    def __init__(self):
        self.generator = ClarificationGenerator()

    def generate_clarification(
        self,
        feedback_id: str,
        feedback_text: str,
        classification: Dict[str, Any],
        extraction: Dict[str, Any],
        workspace_id: str,
        suggestion_id: str | None = None,
        analysis_run_id: str | None = None,
        db=None,
    ) -> Dict[str, Any]:
        clarification_data = self.generator.generate(feedback_text, classification, extraction)

        if not clarification_data["requires_clarification"]:
            return {
                "clarification_id": None,
                "created": False,
                "reason": "Feedback clarity is sufficient",
                "details": clarification_data,
            }

        if db:
            try:
                from app.db.models.clarification import Clarification

                clarification_id = str(uuid4())
                questions = clarification_data["questions"]
                clarification = Clarification(
                    clarification_id=clarification_id,
                    feedback_id=feedback_id,
                    workspace_id=workspace_id,
                    suggestion_id=suggestion_id,
                    analysis_run_id=analysis_run_id,
                    clarification_question=questions[0] if questions else "Please clarify the requested rule.",
                    questions=questions,
                    reason="; ".join(clarification_data["ambiguity_reasons"]),
                    processing_status="pending",
                    clarification_response=None,
                    created_at=datetime.utcnow(),
                    responded_at=None,
                )
                db.add(clarification)
                db.flush()

                return {
                    "clarification_id": clarification_id,
                    "created": True,
                    "feedback_id": feedback_id,
                    "questions": questions,
                    "status": "pending",
                    "reason": clarification.reason,
                    "details": clarification_data,
                }
            except Exception as e:
                return {
                    "clarification_id": None,
                    "created": False,
                    "error": str(e),
                    "details": clarification_data,
                }

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
        responded_by: str | None = None,
        db=None,
    ) -> Dict[str, Any]:
        if not db:
            return {
                "success": False,
                "message": "Database connection required",
            }

        try:
            from app.db.models.clarification import Clarification

            clarification = db.get(Clarification, clarification_id)
            if clarification is None:
                return {
                    "success": False,
                    "message": "Clarification not found",
                }

            clarification.processing_status = "answered"
            clarification.clarification_response = response_text
            clarification.responded_by = responded_by
            clarification.responded_at = datetime.utcnow()
            db.commit()

            return {
                "success": True,
                "clarification_id": clarification_id,
                "feedback_id": clarification.feedback_id,
                "workspace_id": clarification.workspace_id,
                "message": "Clarification response received. Ready for re-analysis.",
                "next_step": "re_analyze_with_clarification",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


ClarificationService = RealClarificationService
