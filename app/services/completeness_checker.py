"""Completeness checker for extracted rules.

This implements the V4 architecture's completeness check that triggers
clarification requests when mandatory information is missing.
"""

from typing import Dict, Any, List


class CompletenessChecker:
    """Check if extracted rules have all mandatory information."""

    def __init__(self):
        """Initialize completeness checker."""
        # Define mandatory fields based on V4 architecture
        self.mandatory_fields = [
            "business_term",
            "operation",
            "scope",
        ]

        # Define conditionally mandatory fields
        self.conditionally_mandatory = {
            "exclude": ["conditions"],  # Exclude operations need conditions
            "include": ["conditions"],  # Include operations need conditions
            "restrict": ["conditions", "threshold"],  # Restrict needs conditions and threshold
        }

    def check(self, extracted_rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if extracted rule has all mandatory information.

        Returns:
            {
                "is_complete": bool,
                "missing_fields": [str],
                "missing_conditional": [str],
                "completeness_score": float (0.0-1.0),
                "details": {
                    "business_term": bool,
                    "operation": bool,
                    "scope": bool,
                    "conditions": bool,
                    "threshold": bool,
                    "time_window": bool,
                }
            }
        """
        missing_fields = []
        missing_conditional = []
        completeness_details = {}

        # Check mandatory fields
        for field in self.mandatory_fields:
            present = extracted_rule.get(field) is not None and extracted_rule.get(field) != ""
            completeness_details[field] = present
            if not present:
                missing_fields.append(field)

        # Check conditionally mandatory fields based on operation
        operation = (extracted_rule.get("operation") or "").lower()
        if operation in self.conditionally_mandatory:
            for field in self.conditionally_mandatory[operation]:
                present = extracted_rule.get(field) is not None and len(extracted_rule.get(field) or []) > 0
                completeness_details[field] = present
                if not present:
                    missing_conditional.append(field)

        # Check optional but important fields
        optional_fields = ["threshold", "time_window"]
        for field in optional_fields:
            present = extracted_rule.get(field) is not None and extracted_rule.get(field) != ""
            completeness_details[field] = present

        # Calculate completeness score
        total_checkable = len(self.mandatory_fields) + len(optional_fields)
        present_count = sum(1 for v in completeness_details.values() if v)
        completeness_score = present_count / total_checkable if total_checkable > 0 else 0.0

        return {
            "is_complete": len(missing_fields) == 0 and len(missing_conditional) == 0,
            "missing_fields": missing_fields,
            "missing_conditional": missing_conditional,
            "completeness_score": round(completeness_score, 3),
            "details": completeness_details,
        }

    def generate_clarification_questions(self, extracted_rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate targeted clarification questions based on missing fields.

        Returns:
            {
                "clarification_required": bool,
                "questions": [
                    {
                        "field": str,
                        "question": str,
                        "priority": "high|medium|low"
                    }
                ],
                "missing_fields": [str]
            }
        """
        check_result = self.check(extracted_rule)

        if check_result["is_complete"]:
            return {
                "clarification_required": False,
                "questions": [],
                "missing_fields": [],
            }

        # Generate questions based on missing fields
        questions = []

        # High priority: Mandatory fields
        for field in check_result["missing_fields"]:
            if field == "business_term":
                questions.append({
                    "field": "business_term",
                    "question": "Which business term does this rule apply to? (e.g., revenue, churn, refund)",
                    "priority": "high"
                })
            elif field == "operation":
                questions.append({
                    "field": "operation",
                    "question": "What operation should be performed? (e.g., exclude, include, restrict, mask)",
                    "priority": "high"
                })
            elif field == "scope":
                questions.append({
                    "field": "scope",
                    "question": "What is the scope of this rule? (e.g., global, region:1, time:monthly)",
                    "priority": "high"
                })

        # High priority: Conditionally mandatory fields
        for field in check_result["missing_conditional"]:
            if field == "conditions":
                # Check for candidate conditions to generate more intelligent questions
                candidate_conditions = extracted_rule.get("candidate_conditions", [])

                if candidate_conditions:
                    # Use the first candidate condition for a targeted question
                    first_candidate = candidate_conditions[0]
                    condition_text = first_candidate.get("text", "")

                    if condition_text:
                        questions.append({
                            "field": "conditions",
                            "question": f"How should '{condition_text}' be identified in the data? For example, is there a specific field, flag, or threshold that defines this condition?",
                            "priority": "high",
                            "context": f"Candidate condition: {condition_text}"
                        })

                        # Add a follow-up question about the field
                        questions.append({
                            "field": "conditions",
                            "question": f"What field or attribute should be used to check for '{condition_text}'?",
                            "priority": "medium",
                            "context": f"Candidate condition: {condition_text}"
                        })
                else:
                    # Fallback to generic question if no candidate conditions
                    questions.append({
                        "field": "conditions",
                        "question": "What conditions should trigger this rule? (e.g., status = cancelled, amount > 1000)",
                        "priority": "high"
                    })
            elif field == "threshold":
                questions.append({
                    "field": "threshold",
                    "question": "What threshold value should be used for this restriction? (e.g., 100, 0.5, 1000)",
                    "priority": "high"
                })

        # Medium priority: Optional but important fields
        if not check_result["details"].get("time_window", False):
            questions.append({
                "field": "time_window",
                "question": "Is there a specific time window for this rule? (e.g., last 30 days, Q1 2024)",
                "priority": "medium"
            })

        return {
            "clarification_required": len(questions) > 0,
            "questions": questions,
            "missing_fields": check_result["missing_fields"] + check_result["missing_conditional"],
        }


class AmbiguityDetector:
    """Detect ambiguous business information in extracted rules."""

    def __init__(self):
        """Initialize ambiguity detector."""
        # Define ambiguous terms and patterns
        self.ambiguous_terms = [
            "some", "certain", "particular", "specific", "various",
            "different", "multiple", "several", "many", "few",
            "etc", "and so on", "etcetera", "and others", "and more"
        ]

        self.ambiguous_patterns = [
            r"\betc\.?\b",
            r"\band so on\b",
            r"\band others\b",
            r"\band more\b",
            r"\bvarious\b",
            r"\bseveral\b",
            r"\bsome\b",
        ]

    def detect(self, extracted_rule: Dict[str, Any], feedback_text: str) -> Dict[str, Any]:
        """
        Detect ambiguous business information.

        Returns:
            {
                "is_ambiguous": bool,
                "ambiguous_fields": [str],
                "ambiguity_score": float (0.0-1.0),
                "details": {
                    "business_term": bool,
                    "operation": bool,
                    "conditions": bool,
                    "scope": bool,
                    "threshold": bool,
                }
            }
        """
        ambiguous_fields = []
        ambiguity_details = {}

        # Check business term ambiguity
        business_term = (extracted_rule.get("business_term") or "").lower()
        term_ambiguous = any(term in business_term for term in self.ambiguous_terms)
        ambiguity_details["business_term"] = term_ambiguous
        if term_ambiguous:
            ambiguous_fields.append("business_term")

        # Check operation ambiguity
        operation = (extracted_rule.get("operation") or "").lower()
        op_ambiguous = operation not in [
            "exclude", "include", "restrict", "map", "replace",
            "add", "subtract", "mask", "expose", "drop", "keep"
        ]
        ambiguity_details["operation"] = op_ambiguous
        if op_ambiguous:
            ambiguous_fields.append("operation")

        # Check conditions ambiguity
        conditions = extracted_rule.get("conditions", [])
        conditions_ambiguous = False
        for cond in conditions:
            field = str(cond.get("field", "") or "").lower()
            value = str(cond.get("value", "") or "").lower()

            if any(term in field for term in self.ambiguous_terms) or \
               any(term in value for term in self.ambiguous_terms):
                conditions_ambiguous = True
                break

        ambiguity_details["conditions"] = conditions_ambiguous
        if conditions_ambiguous:
            ambiguous_fields.append("conditions")

        # Check scope ambiguity
        scope = (extracted_rule.get("scope") or "").lower()
        scope_ambiguous = scope not in ["global"] and not scope.startswith("region:") and not scope.startswith("time:")
        ambiguity_details["scope"] = scope_ambiguous
        if scope_ambiguous:
            ambiguous_fields.append("scope")

        # Check threshold ambiguity
        threshold = extracted_rule.get("threshold")
        threshold_ambiguous = threshold is not None and (threshold <= 0 or threshold > 1000000)
        ambiguity_details["threshold"] = threshold_ambiguous
        if threshold_ambiguous:
            ambiguous_fields.append("threshold")

        # Calculate ambiguity score
        total_checkable = len(ambiguity_details)
        ambiguous_count = sum(1 for v in ambiguity_details.values() if v)
        ambiguity_score = ambiguous_count / total_checkable if total_checkable > 0 else 0.0

        return {
            "is_ambiguous": len(ambiguous_fields) > 0,
            "ambiguous_fields": ambiguous_fields,
            "ambiguity_score": round(ambiguity_score, 3),
            "details": ambiguity_details,
        }

    def generate_clarification_questions(self, extracted_rule: Dict[str, Any], feedback_text: str) -> Dict[str, Any]:
        """
        Generate clarification questions for ambiguous information.

        Returns:
            {
                "clarification_required": bool,
                "questions": [
                    {
                        "field": str,
                        "question": str,
                        "priority": "high|medium|low"
                    }
                ],
                "ambiguous_fields": [str]
            }
        """
        detect_result = self.detect(extracted_rule, feedback_text)

        if not detect_result["is_ambiguous"]:
            return {
                "clarification_required": False,
                "questions": [],
                "ambiguous_fields": [],
            }

        # Generate questions based on ambiguous fields
        questions = []

        for field in detect_result["ambiguous_fields"]:
            if field == "business_term":
                questions.append({
                    "field": "business_term",
                    "question": "The business term is ambiguous. Please specify exactly which business concept this rule applies to.",
                    "priority": "high"
                })
            elif field == "operation":
                questions.append({
                    "field": "operation",
                    "question": "The operation is unclear. Please specify one of: exclude, include, restrict, map, replace, add, subtract, mask, expose, drop, keep",
                    "priority": "high"
                })
            elif field == "conditions":
                questions.append({
                    "field": "conditions",
                    "question": "The conditions contain ambiguous terms. Please specify exact field names, operators, and values.",
                    "priority": "high"
                })
            elif field == "scope":
                questions.append({
                    "field": "scope",
                    "question": "The scope is ambiguous. Please specify one of: global, region:N, or time:period",
                    "priority": "high"
                })
            elif field == "threshold":
                questions.append({
                    "field": "threshold",
                    "question": "The threshold value seems unreasonable. Please specify a realistic threshold value.",
                    "priority": "high"
                })

        return {
            "clarification_required": len(questions) > 0,
            "questions": questions,
            "ambiguous_fields": detect_result["ambiguous_fields"],
        }
