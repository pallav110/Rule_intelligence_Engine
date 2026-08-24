"""Phase 3 — Clarification generation workflow.

Detects when feedback is unclear or missing critical information,
and generates clarification questions to send back to the user.

Triggered when:
  - Classification result has ``requires_clarification=True``
  - Extraction confidence is below threshold
  - Missing key fields (business_term, conditions, etc.)
"""

from typing import Dict, Any, List


class ClarificationGenerator:
    def __init__(self, confidence_threshold: float = 0.6):
        self.confidence_threshold = confidence_threshold

    def generate(self, feedback: str, classification: Dict[str, Any],
                 extraction: Dict[str, Any]) -> Dict[str, Any]:
        """Generate clarification questions if needed.

        Returns
        -------
        dict
            ``{"needs_clarification": bool, "questions": List[str], "reason": str}``
        """
        questions = []
        reason = ""

        # Check if classifier flagged it
        if classification.get("requires_clarification"):
            reason = "Unclear feedback detected by classifier"
            questions.append("Could you provide more details about what rule you want to define?")

        # Check extraction confidence
        if extraction.get("confidence", 1.0) < self.confidence_threshold:
            reason = "Low extraction confidence"
            questions.append("Which specific field or metric are you referring to?")

        # Check for missing business term
        rules = extraction.get("rules", [])
        if not rules or not any(r.get("business_term") for r in rules):
            reason = "Missing business term"
            questions.append("What is the name of the metric or business term you're defining?")

        # Check for missing conditions
        if rules and not any(r.get("conditions") for r in rules):
            reason = "Missing conditions"
            questions.append("What are the specific conditions or filters for this rule?")

        # Check for ambiguous operations
        if rules and any(r.get("operation") == "include" and not r.get("conditions") for r in rules):
            reason = "Ambiguous operation"
            questions.append("Should this rule include or exclude certain records? Please specify.")

        return {
            "needs_clarification": len(questions) > 0,
            "questions": questions,
            "reason": reason,
        }