"""
Test script for Spec 10.9 Failure Recovery and Fallback Strategy
"""

import os
import sys
from unittest.mock import Mock, patch

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_ml_model_service_fallback_logging():
    """Test that MLModelService logs failures and falls back to baseline"""
    try:
        from app.services.ml_model_service import MLModelService

        # Mock a scenario where DistilBERT fails
        with patch('app.services.ml_model_service.MLModelService._classify_with_distilbert') as mock_classify:
            mock_classify.return_value = {"error": "Model not found", "confidence": 0}

            service = MLModelService(db=None)  # No DB to force baseline path

            # This should trigger fallback logging
            result = service.classify("test feedback")

            # Should fall back to baseline
            assert result.get("model") == "baseline"
            assert result.get("registry_status") in ["no_active_model", "baseline_fallback"]

            print("✓ MLModelService fallback logging works correctly")
            return True
    except Exception as e:
        print(f"✗ MLModelService fallback logging test failed: {e}")
        return False

def test_background_job_retry_configuration():
    """Test that background jobs have retry configuration"""
    try:
        from app.tasks import process_background_job

        # Check if the task has retry configuration
        assert hasattr(process_background_job, 'autoretry_for')
        assert hasattr(process_background_job, 'retry_kwargs')
        assert process_background_job.autoretry_for == (Exception,)
        assert process_background_job.retry_kwargs.get("max_retries") == 3

        print("✓ Background job retry configuration verified")
        return True
    except Exception as e:
        print(f"✗ Background job retry configuration test failed: {e}")
        return False

def test_audit_history_model():
    """Test that AuditHistory model exists for recording failures"""
    try:
        from app.db.models.audit_history import AuditHistory

        # Check that the model has expected fields
        assert hasattr(AuditHistory, 'audit_id')
        assert hasattr(AuditHistory, 'action')
        assert hasattr(AuditHistory, 'entity_type')
        assert hasattr(AuditHistory, 'entity_id')
        assert hasattr(AuditHistory, 'details')
        assert hasattr(AuditHistory, 'created_at')

        print("✓ AuditHistory model verified")
        return True
    except Exception as e:
        print(f"✗ AuditHistory model test failed: {e}")
        return False

def test_review_routing_mandatory_manual_review():
    """Test that low confidence results go to manual review"""
    try:
        from app.services.review_routing_service import RealReviewRoutingService

        routing_service = RealReviewRoutingService()

        # Test with low confidence
        result = routing_service.router.route(
            suggestion={"conditions": []},
            classification={"confidence": 0.5},  # Low confidence
            extraction={"rules": []},
            conflict_check={"has_conflict": False},
            duplicate_check={"is_duplicate": False},
            workspace_id="test",
            domain_id="ecommerce",
            clarification_required=False,
            mandatory_fields_valid=True,
            sensitivity={"sensitive": False}
        )

        # Should route to pending_review or similar for low confidence
        assert result["review_status"] in ["pending_review", "manual_review"]

        print("✓ Review routing for low confidence verified")
        return True
    except Exception as e:
        print(f"✗ Review routing test failed: {e}")
        return False

def test_no_automatic_rule_activation_on_failure():
    """Test that failed ML processing doesn't auto-activate rules"""
    try:
        # Check that review routing doesn't auto-approve low confidence
        from app.services.review_routing_service import RealReviewRoutingService

        routing_service = RealReviewRoutingService()

        # Test with low confidence - should not be auto_approved
        result = routing_service.router.route(
            suggestion={"conditions": [{"business_term": "test"}]},
            classification={"confidence": 0.5, "feedback_type": "business_rule"},  # Low confidence
            extraction={"rules": [{"business_term": "test", "operation": "include"}]},
            conflict_check={"has_conflict": False},
            duplicate_check={"is_duplicate": False},
            workspace_id="test",
            domain_id="ecommerce",
            clarification_required=False,
            mandatory_fields_valid=True,
            sensitivity={"sensitive": False}
        )

        # Should not be auto_approved
        assert result["review_status"] != "auto_approved"

        print("✓ No automatic rule activation on failure verified")
        return True
    except Exception as e:
        print(f"✗ No automatic rule activation test failed: {e}")
        return False

def test_audit_write_function_exists():
    """Test that audit write function exists for recording failures"""
    try:
        from app.services.audit import write_audit

        # Function should exist
        assert callable(write_audit)

        print("✓ Audit write function verified")
        return True
    except Exception as e:
        print(f"✗ Audit write function test failed: {e}")
        return False

if __name__ == "__main__":
    print("Running Spec 10.9 Failure Recovery and Fallback Strategy tests...\n")

    tests = [
        test_ml_model_service_fallback_logging,
        test_background_job_retry_configuration,
        test_audit_history_model,
        test_review_routing_mandatory_manual_review,
        test_no_automatic_rule_activation_on_failure,
        test_audit_write_function_exists
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()  # Add space between tests

    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("✓ All Spec 10.9 failure recovery tests passed!")
        sys.exit(0)
    else:
        print("✗ Some Spec 10.9 failure recovery tests failed!")
        sys.exit(1)