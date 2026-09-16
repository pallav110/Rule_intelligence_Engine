"""Central orchestrator for running the analysis pipeline for a single feedback item.

This module centralizes the pipeline (preprocess -> classify -> extract -> validate -> duplicate/conflict -> routing)
so other parts of the codebase (main API, clarification re-analysis) can call the same implementation.
"""
from typing import Any, Dict
from uuid import uuid4
from datetime import datetime


def run_analysis(db, workspace_id: str, feedback_text: str, feedback_id: str | None = None, schema_context: dict | None = None, submitted_by: str | None = None, domain_pack_id: str | None = None, reanalysis: bool = False) -> Dict[str, Any]:
    """Run the core pipeline and persist AnalysisRun + RuleSuggestion.

    Returns a dict with keys: analysis_run_id, suggestion_id, routing_decision, clarification_required, result (full response dict)
    """
    from app.db.models.analysis_run import AnalysisRun
    from app.db.models.rule_suggestion import RuleSuggestion
    from app.db.models.feedback import Feedback

    from app.services.feedback_preprocessor import FeedbackPreprocessor
    from app.services.enhanced_rule_extractor import EnhancedRuleExtractor
    from app.services.schema_validation_service import SchemaValidationService
    from app.services.baseline_duplicate_detection_service import BaselineDuplicateDetectionService
    from app.services.baseline_conflict_detection_service import BaselineConflictDetectionService
    from app.services.review_routing_service import RealReviewRoutingService
    from app.services.completeness_checker import CompletenessChecker, AmbiguityDetector
    from app.services.classifier import RealClassifier
    from app.services.calibration import calibrate_probability
    from app.services.sensitivity_service import assess_sensitivity

    schema_context = schema_context or {}
    domain_pack_id = domain_pack_id or schema_context.get("domain_pack_id", "ecommerce")

    feedback_id = feedback_id or str(uuid4())
    suggestion_id = str(uuid4())
    analysis_run_id = str(uuid4())

    thresholds = {
        "classification": 0.7,
        "extraction": 0.6,
        "schema_validation": 0.8,
        "conflict_detection": 0.7,
        "duplicate_detection": 0.85,
    }

    # Persist Feedback if not present (safe upsert-like behavior)
    try:
        existing_fb = db.query(Feedback).filter_by(feedback_id=feedback_id).first()
        if not existing_fb:
            fb = Feedback(
                feedback_id=feedback_id,
                workspace_id=workspace_id,
                feedback_text=feedback_text,
                submitted_by=submitted_by,
                processing_status="processing",
                created_at=datetime.utcnow(),
            )
            db.add(fb)
            db.flush()
    except Exception:
        # best-effort: continue even if feedback persistence fails
        pass

    ar = AnalysisRun(
        analysis_run_id=analysis_run_id,
        feedback_id=feedback_id,
        workspace_id=workspace_id,
        model_version_id=None,
        dataset_version_id=None,
        taxonomy_version="v1",
        domain_pack_id=domain_pack_id,
        threshold_configuration=thresholds,
        processing_mode="clarification_reanalysis" if reanalysis else "single",
        status="processing",
        started_at=datetime.utcnow(),
    )
    db.add(ar)
    db.flush()

    # Preprocess
    try:
        preprocessor = FeedbackPreprocessor()
        preprocessing_result = preprocessor.preprocess(feedback_text, schema_context)
        processed_text = preprocessing_result.get("processed_text", feedback_text)
    except Exception:
        processed_text = feedback_text
        preprocessing_result = {"processed_text": feedback_text, "steps": []}

    # Classify
    try:
        classifier = RealClassifier(domain=domain_pack_id)
        classification_result = classifier.classify(processed_text, schema_context)
    except Exception:
        classification_result = {"feedback_type": "unclear_feedback", "rule_category": None, "is_actionable": False, "confidence": 0.5}

    # Calibrate classification probability (temperature can be passed via schema_context)
    try:
        # Respect classifier-provided calibrated confidence (e.g., DistilBERT may have applied per-task temps).
        if 'calibrated_confidence' not in classification_result:
            temp = float(schema_context.get("calibration_temperature", 1.0))
            raw_conf = float(classification_result.get("confidence", 0.0) or 0.0)
            calibrated_conf = calibrate_probability(raw_conf, temp)
            classification_result["calibrated_confidence"] = calibrated_conf
            classification_result["calibration"] = {"temperature": temp, "raw_confidence": raw_conf}
    except Exception:
        pass

    # Extract
    try:
        extractor = EnhancedRuleExtractor()
        extraction_result = extractor.extract(processed_text, schema_context)
        extracted_rules = extraction_result.get("extraction", {}).get("extracted_rules", [])
    except Exception:
        extraction_result = {"extraction": {"extracted_rules": []}, "extraction_confidence": 0.5}
        extracted_rules = []

    # Schema validation
    try:
        schema_validator = SchemaValidationService(schema_context=schema_context)
        schema_validation_results = []
        for rule in extracted_rules:
            v = schema_validator.validate_rule(rule, schema_context.get("domain_pack_schema", {}))
            schema_validation_results.append(v)
        schema_validation_status = "PASS" if all(v.get("status") == "PASS" for v in schema_validation_results) else (
            "PARTIAL" if any(v.get("status") in ["PASS", "PARTIAL"] for v in schema_validation_results) else "FAIL"
        )
    except Exception:
        schema_validation_results = []
        schema_validation_status = "FAIL"

    primary_rule = extracted_rules[0] if extracted_rules else {}

    # Assess sensitivity
    try:
        sensitivity = assess_sensitivity(primary_rule, classification_result)
    except Exception:
        sensitivity = {"sensitive": False, "score": 0.0, "reasons": []}

    # Duplicate & Conflict detection
    try:
        duplicate_service = BaselineDuplicateDetectionService()
        duplicate_check = duplicate_service.check_duplicate(primary_rule, workspace_id, domain_pack_id, db)
    except Exception:
        duplicate_check = {"status": "none", "is_duplicate": False}

    try:
        conflict_service = BaselineConflictDetectionService()
        conflict_check = conflict_service.check_conflict(primary_rule, workspace_id, domain_pack_id, db)
    except Exception:
        conflict_check = {"has_conflict": False, "conflict_type": "no_conflict"}

    # Completeness & Ambiguity
    try:
        completeness_checker = CompletenessChecker()
        completeness_result = completeness_checker.generate_clarification_questions(primary_rule)
        ambiguity_detector = AmbiguityDetector()
        ambiguity_result = ambiguity_detector.generate_clarification_questions(primary_rule, processed_text)
        clarification_required = completeness_result.get("clarification_required") or ambiguity_result.get("clarification_required")
    except Exception:
        completeness_result = {"clarification_required": False, "questions": [], "missing_fields": []}
        ambiguity_result = {"clarification_required": False, "questions": [], "ambiguous_fields": []}
        clarification_required = False

    # Build clarification payload (questions + context) without modifying original feedback
    clarification_payload = None
    try:
        if clarification_required:
            clarification_payload = {
                "questions": completeness_result.get("questions", []) + ambiguity_result.get("questions", []),
                "missing_fields": completeness_result.get("missing_fields", []) + ambiguity_result.get("ambiguous_fields", []),
                "generated_at": datetime.utcnow().isoformat(),
            }
    except Exception:
        clarification_payload = None

    # Enforce 'no inference' guard for mandatory fields: if any mandatory field missing, mark clarification_required and strip inferred values
    try:
        required_keys = [
            "business_term",
            "operation",
            "scope",
            "affected_entities",
        ]
        missing_mandatory = []
        for key in required_keys:
            val = primary_rule.get(key) if isinstance(primary_rule, dict) else None
            if not val:
                missing_mandatory.append(key)
        if missing_mandatory:
            clarification_required = True
            # Remove any fields that look like inferred candidates to avoid auto-filling
            for k in missing_mandatory:
                if k in primary_rule:
                    primary_rule[k] = None
    except Exception:
        # If anything fails, keep existing clarification flag
        pass

    # Routing
    try:
        routing_service = RealReviewRoutingService()
        # Compute mandatory fields validation summary
        try:
            mandatory_fields_valid = all(v.get("mandatory_fields_valid", True) for v in schema_validation_results) if schema_validation_results else False
        except Exception:
            mandatory_fields_valid = False

        routing_decision = routing_service.route_suggestion(
            suggestion_id=suggestion_id,
            suggestion=primary_rule,
            classification=classification_result,
            extraction=extraction_result,
            conflict_check=conflict_check,
            duplicate_check=duplicate_check,
            workspace_id=workspace_id,
            domain_id=domain_pack_id,
            db=db,
            clarification_required=clarification_required,
            mandatory_fields_valid=mandatory_fields_valid,
            sensitivity=sensitivity,
        )
    except Exception:
        routing_decision = {"review_status": "pending_review", "priority": "normal", "reason": "routing_failed"}

    # Persist RuleSuggestion
    try:
        # merge clarification payload into preprocessing_result for persistence
        persisted_preprocessing = {**(preprocessing_result or {}), **({"clarification_requests": clarification_payload} if clarification_payload else {})}

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
            preprocessing_result=persisted_preprocessing,
            review_status=routing_decision.get("review_status", "pending_review"),
            suggested_rule=primary_rule,
            schema_validation_status=schema_validation_status,
            created_at=datetime.utcnow(),
        )
        db.add(rs)
        db.flush()
    except Exception:
        # swallow persistence errors but continue
        pass

    # Persist ExtractedRules (audit trail of individual rules from extraction step)
    try:
        from app.db.models.extracted_rule import ExtractedRule
        for idx, rule in enumerate(extracted_rules):
            er = ExtractedRule(
                extracted_rule_id=str(uuid4()),
                workspace_id=workspace_id,
                feedback_id=feedback_id,
                analysis_run_id=analysis_run_id,
                suggestion_id=suggestion_id,
                rule_family_id=rule.get("rule_family_id") or (f"{classification_result.get('rule_category', '').lower()}_{idx}" if classification_result.get('rule_category') else None),
                business_term=rule.get("business_term"),
                operation=rule.get("operation"),
                conditions=rule.get("conditions"),
                scope=rule.get("scope"),
                time_window=rule.get("time_window"),
                affected_tables=rule.get("affected_tables") or rule.get("affected_entities"),
                affected_columns=rule.get("affected_columns"),
                extraction_confidence=extraction_result.get("extraction_confidence"),
                schema_validation_status=schema_validation_status,
                rule_data=rule,
                created_at=datetime.utcnow(),
            )
            db.add(er)
        db.flush()
    except Exception:
        # swallow persistence errors but continue
        pass

    # Finish analysis run
    try:
        ar.status = "completed"
        ar.completed_at = datetime.utcnow()
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    # Build a compact result to return
    result = {
        "analysis_run_id": analysis_run_id,
        "suggestion_id": suggestion_id,
        "routing_decision": routing_decision,
        "clarification_required": clarification_required,
        "clarification": clarification_payload,
        "classification": classification_result,
        "extraction": extraction_result,
        "schema_validation": {
            "status": schema_validation_status,
            "results": schema_validation_results,
        },
        "duplicate_detection": duplicate_check,
        "conflict_detection": conflict_check,
    }

    return result
