from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models.analysis_run import AnalysisRun
from app.db.models.feedback import Feedback
from app.schemas.feedback import (
    FeedbackAnalysisResponse,
    PreprocessingResponse,
    ClassificationResponse,
    ExtractionResponse,
    SchemaValidationResponse,
    DuplicateDetectionResponse,
    ConflictDetectionResponse,
    ClarificationResponse,
    RoutingDecisionResponse,
    PerFieldConfidence,
)
from app.services.domain_pack_loader import DomainPackLoader, DomainPackNotFoundError
from app.services.suggestion_service import SuggestionService
from app.services.feedback_preprocessor import FeedbackPreprocessor
from app.services.schema_validation_service import SchemaValidationService
from app.services.baseline_duplicate_detection_service import BaselineDuplicateDetectionService
from app.services.baseline_conflict_detection_service import BaselineConflictDetectionService
from app.services.review_routing_service import RealReviewRoutingService
from app.services.completeness_checker import CompletenessChecker, AmbiguityDetector


class FeedbackService:
    def __init__(self):
        self.domain_loader = DomainPackLoader()
        self.suggestion_service = SuggestionService()

    def analyze(
        self,
        db: Session,
        workspace_id: str,
        feedback: str,
        domain: str | None = None,
        processing_mode: str = "single",
        feedback_id: str | None = None,
        submitted_by: str | None = None,
        schema_context: dict | None = None,
    ) -> FeedbackAnalysisResponse:
        """Deprecated: Use app/main.py analyze_feedback endpoint instead.

        This method runs a simplified baseline pipeline for batch processing.
        """
        feedback_id = feedback_id or str(uuid4())
        analysis_run_id = str(uuid4())
        schema_context = schema_context or {}
        domain_pack_id = domain or schema_context.get("domain_pack_id", "customer_support")

        feedback_record = Feedback(
            feedback_id=feedback_id,
            workspace_id=workspace_id,
            feedback_text=feedback,
            submitted_by=submitted_by,
            processing_status="processing",
        )
        db.add(feedback_record)
        db.flush()

        analysis_run = AnalysisRun(
            analysis_run_id=analysis_run_id,
            feedback_id=feedback_id,
            workspace_id=workspace_id,
            domain_pack_id=domain_pack_id,
            processing_mode=processing_mode,
            status="processing",
            started_at=datetime.utcnow(),
        )
        db.add(analysis_run)
        db.flush()

        try:
            domain_pack = self.domain_loader.load(domain_pack_id)
        except DomainPackNotFoundError:
            domain_pack = {}

        # Step 1: Preprocessing
        preprocessor = FeedbackPreprocessor()
        preprocessing_result = preprocessor.preprocess(feedback, schema_context)
        processed_feedback = preprocessing_result.get("processed_text", feedback)

        # Step 2: Classification (baseline)
        extract_result = self.suggestion_service.extract(
            feedback=processed_feedback,
            domain_context=schema_context,
        )
        classification = extract_result["classification"]
        extraction = extract_result.get("extraction", {})
        extracted_rules = extraction.get("rules", []) if isinstance(extraction, dict) else []

        # Step 3: Schema Validation
        schema_validator = SchemaValidationService(schema_context=schema_context)
        schema_validation_results = []
        for rule in extracted_rules:
            validation = schema_validator.validate_rule(rule, schema_context.get("domain_pack_schema", {}))
            schema_validation_results.append(validation)

        is_actionable = classification.get("is_actionable", True)
        if not is_actionable or not extracted_rules:
            schema_validation_status = "N/A"
            schema_coverage = 0.0
            mandatory_fields_valid = False
            validation_errors = []
        else:
            schema_validation_status = "PASS" if all(v["status"] == "PASS" for v in schema_validation_results) else (
                "PARTIAL" if any(v["status"] in ["PASS", "PARTIAL"] for v in schema_validation_results) else "FAIL"
            )
            schema_coverage = sum(v["coverage"] for v in schema_validation_results) / len(schema_validation_results) if schema_validation_results else 0.0
            mandatory_fields_valid = all(v["mandatory_fields_valid"] for v in schema_validation_results)
            validation_errors = [e for v in schema_validation_results for e in v["validation_errors"]]

        # Step 4: Duplicate Detection
        primary_rule = extracted_rules[0] if extracted_rules else {}
        if domain_pack_id:
            dup_svc = BaselineDuplicateDetectionService()
            duplicate_check = dup_svc.check_duplicate(
                suggested_rule=primary_rule,
                workspace_id=workspace_id,
                domain_id=domain_pack_id,
                db=db,
            )
        else:
            duplicate_check = {
                "is_duplicate": False,
                "relationship": "unrelated",
                "matching_rule_id": None,
                "confidence": 0.0,
                "retrieval_stage": 0,
                "similar_rules": [],
                "details": {"reason": "No domain detected - skipping duplicate detection", "model_used": "none"}
            }

        # Step 5: Conflict Detection
        if domain_pack_id:
            cfl_svc = BaselineConflictDetectionService()
            conflict_check = cfl_svc.check_conflict(
                suggested_rule=primary_rule,
                workspace_id=workspace_id,
                domain_id=domain_pack_id,
                db=db,
            )
        else:
            conflict_check = {
                "has_conflict": False,
                "conflict_type": "no_conflict",
                "conflicting_rule_ids": [],
                "confidence": 0.0,
                "retrieval_stage": 0,
                "details": {"reason": "No domain detected - skipping conflict detection", "model_used": "none"}
            }

        # Step 6: Clarification
        completeness_checker = CompletenessChecker()
        completeness_result = completeness_checker.generate_clarification_questions(primary_rule)
        ambiguity_detector = AmbiguityDetector()
        ambiguity_result = ambiguity_detector.generate_clarification_questions(primary_rule, feedback)
        clarification_required = completeness_result["clarification_required"] or ambiguity_result["clarification_required"]
        clarification_questions = []
        clarification_reason = ""

        if completeness_result["clarification_required"]:
            clarification_questions.extend([q["question"] for q in completeness_result["questions"]])
            clarification_reason = f"Missing mandatory fields: {', '.join(completeness_result['missing_fields'])}"

        if ambiguity_result["clarification_required"]:
            clarification_questions.extend([q["question"] for q in ambiguity_result["questions"]])
            if clarification_reason:
                clarification_reason += "; Ambiguous fields: " + ", ".join(ambiguity_result['ambiguous_fields'])
            else:
                clarification_reason = f"Ambiguous fields: {', '.join(ambiguity_result['ambiguous_fields'])}"

        # Step 7: Routing (without DB to avoid creating reviews for non-existent suggestions)
        routing_service = RealReviewRoutingService()
        routing_decision = routing_service.route_suggestion(
            suggestion_id=str(uuid4()),
            suggestion=primary_rule,
            classification=classification,
            extraction=extract_result,
            conflict_check=conflict_check,
            duplicate_check=duplicate_check,
            workspace_id=workspace_id,
            domain_id=domain_pack_id,
            db=None,  # Don't persist review for batch job
            clarification_required=clarification_required,
            mandatory_fields_valid=mandatory_fields_valid,
            sensitivity={"sensitive": False, "score": 0.0, "reasons": []},
            schema_validation={"status": schema_validation_status},
        )

        feedback_record.processing_status = "processed"
        analysis_run.status = "completed"
        analysis_run.completed_at = datetime.utcnow()
        db.commit()

        # Build PerFieldConfidence
        per_field_conf = extraction.get("confidence", {})
        if per_field_conf:
            extraction_confidence = PerFieldConfidence(**per_field_conf)
        else:
            overall = extraction.get("extraction_confidence", 0.5)
            extraction_confidence = PerFieldConfidence(
                business_term=overall,
                operation=overall,
                conditions=overall,
                scope=overall,
                affected_entities=overall
            )

        # Build schema_loaded flag
        schema_loaded = schema_validation_results[0].get("schema_loaded", False) if schema_validation_results else False

        # Aggregate validated and invalid fields
        all_validated_fields = []
        all_invalid_fields = []
        all_validation_checks = {}
        for result in schema_validation_results:
            all_validated_fields.extend(result.get("validated_fields", []))
            all_invalid_fields.extend(result.get("invalid_fields", []))
            if result.get("check_results"):
                all_validation_checks.update(result.get("check_results", {}))

        # Build extraction response
        extraction_data = extract_result.get("extraction", {}) if isinstance(extract_result.get("extraction"), dict) else {}
        extraction_response = ExtractionResponse(
            extracted_rules=extraction_data.get("extracted_rules", []),
            candidate_rules=extraction_data.get("candidate_rules", []),
            rules=extraction_data.get("rules", []),
            confidence=extraction_confidence,
            evidence=extract_result.get("evidence", ""),
            rule_count=extract_result.get("rule_count", {"extracted": len(extracted_rules), "candidates": 0}),
            model=extract_result.get("model"),
            model_version_id=extract_result.get("model_version_id"),
            model_version=extract_result.get("model_version"),
            registry_status=extract_result.get("registry_status"),
        )

        # Build classification response
        classification_response = ClassificationResponse(
            feedback_type=classification.get("feedback_type", "unknown"),
            rule_category=classification.get("rule_category"),
            confidence=classification.get("confidence", 0.0),
            is_actionable=classification.get("is_actionable", False),
            model=classification.get("model"),
            model_version_id=classification.get("model_version_id"),
            model_version=classification.get("model_version"),
            registry_status=classification.get("registry_status"),
        )

        return FeedbackAnalysisResponse(
            feedback_id=feedback_id,
            suggestion_id=str(uuid4()),
            status=routing_decision.get("review_status", "pending_review").upper(),
            preprocessing=PreprocessingResponse(
                original_text=feedback,
                processed_text=processed_feedback,
                preprocessing_steps=preprocessing_result.get("preprocessing_steps", []),
                detected_keywords=preprocessing_result.get("detected_keywords", []),
                detected_schema_refs=preprocessing_result.get("detected_schema_refs", []),
                language_normalized=preprocessing_result.get("language_normalized", False),
            ),
            classification=classification_response,
            extraction=extraction_response,
            schema_validation=SchemaValidationResponse(
                status=schema_validation_status,
                coverage=schema_coverage,
                mandatory_fields_valid=mandatory_fields_valid,
                validation_errors=validation_errors,
                schema_loaded=schema_loaded,
                validated_fields=list(set(all_validated_fields)),
                invalid_fields=list(set(all_invalid_fields)),
                validation_checks=all_validation_checks,
            ),
            duplicate_detection=DuplicateDetectionResponse(
                status=duplicate_check.get("status", "none"),
                relationship=duplicate_check.get("relationship", "unrelated"),
                relationship_internal=duplicate_check.get("relationship"),
                is_duplicate=duplicate_check.get("is_duplicate", False),
                matching_rule_id=duplicate_check.get("matching_rule_id"),
                confidence=duplicate_check.get("confidence", 0.0),
                retrieval_stage=duplicate_check.get("retrieval_stage", 0),
                similar_rules=duplicate_check.get("similar_rules", []),
                details=duplicate_check.get("details", {}),
            ),
            conflict_detection=ConflictDetectionResponse(
                status=conflict_check.get("conflict_type", "no_conflict"),
                relationship=conflict_check.get("relationship", "compatible"),
                has_conflict=conflict_check.get("has_conflict", False),
                conflict_type=conflict_check.get("conflict_type", "no_conflict"),
                conflict_type_internal=conflict_check.get("conflict_type"),
                confidence=conflict_check.get("confidence", 0.0),
                retrieval_stage=conflict_check.get("retrieval_stage", 0),
                conflicting_rule_ids=conflict_check.get("conflicting_rule_ids", []),
                related_compatible_rule_ids=conflict_check.get("related_compatible_rule_ids", []),
                conflict_details=conflict_check.get("details", {}).get("all_conflicts", []),
                details=conflict_check.get("details", {}),
            ),
            clarification_required=clarification_required,
            clarification=ClarificationResponse(
                clarification_id=None,
                required=clarification_required,
                questions=clarification_questions,
                reason=clarification_reason,
                ambiguity_reasons=ambiguity_result.get("ambiguous_fields", []),
            ) if clarification_required else None,
            routing_decision=RoutingDecisionResponse(
                review_status=routing_decision.get("review_status", "pending_review"),
                priority=routing_decision.get("priority", "normal"),
                reason=routing_decision.get("reason", routing_decision.get("reasoning", {}).get("factors", [""])[0] if routing_decision.get("reasoning", {}).get("factors") else ""),
                suggested_reviewer_type=routing_decision.get("suggested_reviewer_type"),
                suggested_reviewer_id=routing_decision.get("suggested_reviewer_id"),
                auto_approval_eligible=routing_decision.get("auto_approval_eligible", False),
                reasoning=routing_decision.get("reasoning", {}),
            ),
        )
