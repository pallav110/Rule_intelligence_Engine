"""Real clarification generation service for ambiguous feedback."""

from typing import Any, Dict, List
from datetime import datetime, timezone
from uuid import uuid4
import json
from pathlib import Path


class ClarificationGenerator:
    """Generate clarification questions for ambiguous feedback."""

    def __init__(self):
        self.question_templates = self._load_question_templates()
        self.domain_templates = self._load_domain_templates()

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

    def _load_domain_templates(self) -> Dict[str, Dict[str, List[str]]]:
        """Load domain-specific clarification templates from config."""
        try:
            config_path = Path(__file__).parent.parent / "config" / "clarification_templates.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load domain templates: {e}")
        return {}

    def generate(
        self,
        feedback_text: str,
        classification: Dict[str, Any],
        extraction: Dict[str, Any],
        domain_id: str = "ecommerce",
    ) -> Dict[str, Any]:
        ambiguity_reasons = []
        extraction_gaps = []
        suggested_questions = []

        # Get domain-specific templates
        domain_questions = self.domain_templates.get(domain_id, {})
        common_questions = self.domain_templates.get("common", {})

        classification_confidence = classification.get("confidence", 0.0)
        is_actionable = classification.get("is_actionable", False)

        # Only add ambiguity reasons if actually applicable
        if classification_confidence < 0.6:
            ambiguity_reasons.append(f"Low classification confidence ({classification_confidence:.2%})")
            # Use domain-specific scope questions if available
            if "scope" in domain_questions:
                suggested_questions.extend(domain_questions["scope"])
            else:
                suggested_questions.extend(self.question_templates["scope"])

        # Only add non-actionable reason if actually non-actionable
        if not is_actionable:
            ambiguity_reasons.append("Feedback flagged as non-actionable")
            if "conditions" in domain_questions:
                suggested_questions.extend(domain_questions["conditions"])
            else:
                suggested_questions.extend(self.question_templates["conditions"])

        extracted_rules = extraction.get("extracted_rules") or extraction.get("rules") or []
        if isinstance(extraction.get("extraction"), dict):
            extracted_rules = extraction["extraction"].get("extracted_rules", extracted_rules)

        if not extracted_rules:
            ambiguity_reasons.append("No concrete rules could be extracted")
            extraction_gaps.append("No business terms identified")
            if "entities" in domain_questions:
                suggested_questions.extend(domain_questions["entities"])
            else:
                suggested_questions.extend(self.question_templates["entities"])
            if "operation" in domain_questions:
                suggested_questions.extend(domain_questions["operation"])
            else:
                suggested_questions.extend(self.question_templates["operation"])
        else:
            # Check for ambiguity in extracted rules
            for rule in extracted_rules:
                if not rule.get("business_term"):
                    extraction_gaps.append("Missing business term")
                    if "scope" in domain_questions:
                        suggested_questions.extend(domain_questions["scope"])
                    else:
                        suggested_questions.extend(self.question_templates["scope"])

                # Missing conditions is NOT necessarily an ambiguity
                feedback_lower = feedback_text.lower()
                has_condition_mention = any(word in feedback_lower for word in ["when", "if", "status", "equals", "greater", "less", "before", "after", "exclude", "include", "filter", "remove", "add", "apply"])

                # Check for candidate conditions to generate more intelligent questions
                candidate_conditions = rule.get("candidate_conditions", [])

                # Also consider candidate conditions as evidence of condition mention
                if candidate_conditions and not has_condition_mention:
                    has_condition_mention = True

                if not rule.get("conditions") and (has_condition_mention or candidate_conditions):
                    extraction_gaps.append("Conditions mentioned but not extracted")

                    # If we have candidate conditions, ask targeted questions
                    if candidate_conditions:
                        for candidate in candidate_conditions:
                            condition_text = candidate.get("text", "")
                            if condition_text:
                                # Generate a targeted question about this specific candidate
                                targeted_question = f"How should '{condition_text}' be identified in the data? For example, is there a specific field, flag, or threshold that defines this condition?"
                                suggested_questions.insert(0, targeted_question)

                                # Add a follow-up question about the field
                                followup_question = f"What field or attribute should be used to check for '{condition_text}'?"
                                suggested_questions.insert(1, followup_question)
                                break  # Ask about the first candidate
                    else:
                        # Fallback to generic questions if no candidate conditions
                        if "conditions" in domain_questions:
                            suggested_questions.extend(domain_questions["conditions"])
                        else:
                            suggested_questions.extend(self.question_templates["conditions"])

                if not rule.get("affected_entities", {}).get("tables"):
                    extraction_gaps.append("Affected entities not identified")
                    if "entities" in domain_questions:
                        suggested_questions.extend(domain_questions["entities"])
                    else:
                        suggested_questions.extend(self.question_templates["entities"])

                if not rule.get("operation"):
                    extraction_gaps.append("Operation/action not specified")
                    if "operation" in domain_questions:
                        suggested_questions.extend(domain_questions["operation"])
                    else:
                        suggested_questions.extend(self.question_templates["operation"])

                scope = str(rule.get("scope", "")).lower()
                if not scope or scope == "unknown":
                    ambiguity_reasons.append("Rule scope is ambiguous")
                    if "scope" in domain_questions:
                        suggested_questions.extend(domain_questions["scope"])
                    else:
                        suggested_questions.extend(self.question_templates["scope"])

        if "time" in feedback_text.lower() or "when" in feedback_text.lower():
            has_time_info = any(
                rule.get("time_window") or rule.get("threshold") for rule in extracted_rules
            )
            if not has_time_info:
                ambiguity_reasons.append("Temporal aspects mentioned but not captured")
                extraction_gaps.append("Time window not specified")
                if "timeline" in domain_questions:
                    suggested_questions.extend(domain_questions["timeline"])
                else:
                    suggested_questions.extend(self.question_templates["timeline"])

        # Remove duplicates while preserving order
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
            "domain_id": domain_id,
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
        domain_id: str = "ecommerce",
        suggestion_id: str | None = None,
        analysis_run_id: str | None = None,
        db=None,
    ) -> Dict[str, Any]:
        """Generate clarification questions using domain-specific templates."""
        clarification_data = self.generator.generate(
            feedback_text,
            classification,
            extraction,
            domain_id=domain_id
        )

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
                    created_at=datetime.now(timezone.utc) if hasattr(datetime, 'now') else datetime.utcnow(),
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
                    "domain_id": domain_id,
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
            "domain_id": domain_id,
            "details": clarification_data,
        }

    def respond_to_clarification(
        self,
        clarification_id: str,
        response_text: str,
        responded_by: str | None = None,
        db=None,
    ) -> Dict[str, Any]:
        """Record clarification response and prepare for re-analysis."""
        if not db:
            return {
                "success": False,
                "message": "Database connection required",
            }

        try:
            from app.db.models.clarification import Clarification

            clarification = db.query(Clarification).filter_by(clarification_id=clarification_id).first()
            if clarification is None:
                return {
                    "success": False,
                    "message": "Clarification not found",
                }

            # Preserve immutable original feedback
            clarification.processing_status = "answered"
            clarification.clarification_response = response_text
            clarification.responded_by = responded_by
            clarification.responded_at = datetime.now(timezone.utc) if hasattr(datetime, 'now') else datetime.utcnow()
            db.commit()

            return {
                "success": True,
                "clarification_id": clarification_id,
                "feedback_id": clarification.feedback_id,
                "workspace_id": clarification.workspace_id,
                "suggestion_id": clarification.suggestion_id,
                "message": "Clarification response received. Ready for re-analysis.",
                "next_step": "re_analyze_with_clarification",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def re_analyze_with_clarification(
        self,
        feedback_id: str,
        clarification_response: str,
        original_feedback: str,
        workspace_id: str,
        domain_id: str = "ecommerce",
        db=None,
    ) -> Dict[str, Any]:
        """
        Re-analyze feedback with clarification response.
        Preserves original feedback immutability by keeping both versions.
        """
        try:
            # Augmented feedback combines original + clarification
            augmented_feedback = f"{original_feedback}\n\n[CLARIFICATION PROVIDED]\n{clarification_response}"

            if not db:
                return {
                    "success": True,
                    "feedback_id": feedback_id,
                    "augmented_feedback": augmented_feedback,
                    "original_feedback_preserved": True,
                    "clarification_response": clarification_response,
                    "workspace_id": workspace_id,
                    "domain_id": domain_id,
                    "next_step": "rerun_full_pipeline",
                    "message": "Ready to re-run classification, extraction, and validation with clarified feedback (no DB provided)"
                }

            # --- Minimal re-run of the core pipeline (classification -> extraction -> validation -> duplicate/conflict -> routing)
            from uuid import uuid4
            from datetime import datetime

            # Create a new AnalysisRun record to track this re-analysis
            try:
                from app.db.models.analysis_run import AnalysisRun
                from app.db.models.rule_suggestion import RuleSuggestion
                from app.db.models.feedback import Feedback
            except Exception:
                AnalysisRun = None
                RuleSuggestion = None

            analysis_run_id = str(uuid4())
            suggestion_id = str(uuid4())

            # Default thresholds (mirror main pipeline defaults)
            thresholds = {
                "classification": 0.7,
                "extraction": 0.6,
                "schema_validation": 0.8,
                "conflict_detection": 0.7,
                "duplicate_detection": 0.85,
            }

            if AnalysisRun:
                ar = AnalysisRun(
                    analysis_run_id=analysis_run_id,
                    feedback_id=feedback_id,
                    workspace_id=workspace_id,
                    model_version_id=None,
                    dataset_version_id=None,
                    taxonomy_version="v1",
                    domain_pack_id=domain_id,
                    threshold_configuration=thresholds,
                    processing_mode="clarification_reanalysis",
                    status="processing",
                    started_at=datetime.utcnow(),
                )
                db.add(ar)
                db.flush()

            # Preprocess
            try:
                from app.services.feedback_preprocessor import FeedbackPreprocessor
                preprocessor = FeedbackPreprocessor()
                preprocessing_result = preprocessor.preprocess(augmented_feedback, {})
                processed_text = preprocessing_result.get("processed_text", augmented_feedback)
            except Exception:
                processed_text = augmented_feedback
                preprocessing_result = {"processed_text": augmented_feedback, "steps": []}

            # Classify
            try:
                from app.services.classifier import RealClassifier
                classifier = RealClassifier(domain=domain_id)
                classification_result = classifier.classify(processed_text, {})
            except Exception:
                classification_result = {"feedback_type": "unclear_feedback", "rule_category": None, "is_actionable": False, "confidence": 0.5}

            # Extract
            try:
                from app.services.enhanced_rule_extractor import EnhancedRuleExtractor
                extractor = EnhancedRuleExtractor()
                extraction_result = extractor.extract(processed_text, {})
                extracted_rules = extraction_result.get("extraction", {}).get("extracted_rules", [])
            except Exception:
                extraction_result = {"extraction": {"extracted_rules": []}, "extraction_confidence": 0.5}
                extracted_rules = []

            # Schema validation
            try:
                from app.services.schema_validation_service import SchemaValidationService
                schema_validator = SchemaValidationService(schema_context={})
                schema_validation_results = []
                for rule in extracted_rules:
                    v = schema_validator.validate_rule(rule, {})
                    schema_validation_results.append(v)
                schema_validation_status = "PASS" if all(v["status"] == "PASS" for v in schema_validation_results) else (
                    "PARTIAL" if any(v["status"] in ["PASS", "PARTIAL"] for v in schema_validation_results) else "FAIL"
                )
            except Exception:
                schema_validation_results = []
                schema_validation_status = "FAIL"

            # Duplicate & Conflict detection
            try:
                from app.services.baseline_duplicate_detection_service import BaselineDuplicateDetectionService
                duplicate_service = BaselineDuplicateDetectionService()
                primary_rule = extracted_rules[0] if extracted_rules else {}
                duplicate_check = duplicate_service.check_duplicate(primary_rule, workspace_id, domain_id, db)
            except Exception:
                duplicate_check = {"status": "none", "is_duplicate": False}

            try:
                from app.services.baseline_conflict_detection_service import BaselineConflictDetectionService
                conflict_service = BaselineConflictDetectionService()
                conflict_check = conflict_service.check_conflict(primary_rule, workspace_id, domain_id, db)
            except Exception:
                conflict_check = {"has_conflict": False, "conflict_type": "no_conflict"}

            # Completeness & Ambiguity
            try:
                from app.services.completeness_checker import CompletenessChecker, AmbiguityDetector
                completeness_checker = CompletenessChecker()
                completeness_result = completeness_checker.generate_clarification_questions(primary_rule)
                ambiguity_detector = AmbiguityDetector()
                ambiguity_result = ambiguity_detector.generate_clarification_questions(primary_rule, augmented_feedback)
                clarification_required = completeness_result["clarification_required"] or ambiguity_result["clarification_required"]
            except Exception:
                completeness_result = {"clarification_required": False, "questions": [], "missing_fields": []}
                ambiguity_result = {"clarification_required": False, "questions": [], "ambiguous_fields": []}
                clarification_required = False

            # Routing
            try:
                from app.services.review_routing_service import RealReviewRoutingService
                routing_service = RealReviewRoutingService()
                routing_decision = routing_service.route_suggestion(
                    suggestion_id=suggestion_id,
                    suggestion=primary_rule,
                    classification=classification_result,
                    extraction=extraction_result,
                    conflict_check=conflict_check,
                    duplicate_check=duplicate_check,
                    workspace_id=workspace_id,
                    domain_id=domain_id,
                    db=db,
                    clarification_required=clarification_required,
                )
            except Exception:
                routing_decision = {"review_status": "pending_review", "priority": "normal", "reason": "routing_failed"}

            # Persist RuleSuggestion if model available
            if RuleSuggestion:
                try:
                    rs = RuleSuggestion(
                        suggestion_id=suggestion_id,
                        workspace_id=workspace_id,
                        feedback_id=feedback_id,
                        analysis_run_id=analysis_run_id,
                        feedback_type=classification_result.get("feedback_type"),
                        rule_category=classification_result.get("rule_category"),
                        classification_result=classification_result,
                        extraction_result="completed",
                        clarification_required=clarification_required,
                        review_status=routing_decision.get("review_status", "pending_review"),
                        suggested_rule=primary_rule,
                        preprocessing_result=preprocessing_result,
                        schema_validation_status=schema_validation_status,
                        created_at=datetime.utcnow(),
                    )
                    db.add(rs)
                    db.flush()
                except Exception:
                    pass

            # Mark analysis run completed
            if AnalysisRun:
                try:
                    ar.status = "completed"
                    ar.completed_at = datetime.utcnow()
                    db.commit()
                except Exception:
                    db.rollback()

            return {
                "success": True,
                "feedback_id": feedback_id,
                "augmented_feedback": augmented_feedback,
                "analysis_run_id": analysis_run_id,
                "suggestion_id": suggestion_id,
                "routing_decision": routing_decision,
                "clarification_required": clarification_required,
                "message": "Re-analysis completed and persisted",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


ClarificationService = RealClarificationService
