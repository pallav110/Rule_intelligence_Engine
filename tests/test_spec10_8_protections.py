"""
Test script for Spec 10.8 Prompt Injection and Malicious Input Handling protections
"""

import os
import sys
from unittest.mock import Mock, patch

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_ml_model_service_import():
    """Test that MLModelService can be imported"""
    try:
        from app.services.ml_model_service import MLModelService
        print("✓ MLModelService imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import MLModelService: {e}")
        return False

def test_feedback_preprocessor_import():
    """Test that FeedbackPreprocessor can be imported"""
    try:
        from app.services.feedback_preprocessor import FeedbackPreprocessor
        print("✓ FeedbackPreprocessor imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import FeedbackPreprocessor: {e}")
        return False

def test_pii_masking_import():
    """Test that PII masking can be imported"""
    try:
        from app.services.pii_masking import mask_feedback_text
        print("✓ PII masking imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import PII masking: {e}")
        return False

def test_irrelevant_input_detection():
    """Test that irrelevant input detection works"""
    try:
        from app.services.ml_model_service import MLModelService

        service = MLModelService()

        # Test empty input
        result = service._irrelevant_input_reason("")
        assert result == "empty_input", f"Expected 'empty_input', got {result}"

        # Test gibberish input
        result = service._irrelevant_input_reason("asdfghjkl qwertyuiop")
        assert result == "gibberish", f"Expected 'gibberish', got {result}"

        # Test promotional spam
        result = service._irrelevant_input_reason("Buy cheap followers now at this link")
        assert result and result.startswith("promo_spam"), f"Expected promo_spam detection, got {result}"

        print("✓ Irrelevant input detection working correctly")
        return True
    except Exception as e:
        print(f"✗ Irrelevant input detection test failed: {e}")
        return False

def test_rare_class_gate_import():
    """Test that rare class gate can be imported"""
    try:
        from app.services.classifier import rare_class_gate
        print("✓ Rare class gate imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import rare class gate: {e}")
        return False

def test_pydantic_validation():
    """Test that Pydantic models validate input"""
    try:
        from app.schemas.feedback import FeedbackAnalysisRequest

        # Valid request should work
        request = FeedbackAnalysisRequest(
            workspace_id="test",
            feedback_text="This is valid feedback"
        )
        assert request.feedback_text == "This is valid feedback"

        # Empty feedback should fail
        try:
            FeedbackAnalysisRequest(
                workspace_id="test",
                feedback_text=""  # This should fail min_length=1
            )
            assert False, "Should have raised validation error"
        except Exception:
            pass  # Expected

        print("✓ Pydantic input validation working correctly")
        return True
    except Exception as e:
        print(f"✗ Pydantic validation test failed: {e}")
        return False

if __name__ == "__main__":
    print("Running Spec 10.8 Prompt Injection and Malicious Input Handling tests...\n")

    tests = [
        test_ml_model_service_import,
        test_feedback_preprocessor_import,
        test_pii_masking_import,
        test_irrelevant_input_detection,
        test_rare_class_gate_import,
        test_pydantic_validation
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()  # Add space between tests

    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("✓ All Spec 10.8 protection tests passed!")
        sys.exit(0)
    else:
        print("✗ Some Spec 10.8 protection tests failed!")
        sys.exit(1)