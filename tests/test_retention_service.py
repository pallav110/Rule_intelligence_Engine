"""
Test script for Spec 10.7 Data Retention and Deletion functionality
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_retention_service_import():
    """Test that retention service can be imported"""
    try:
        from app.services.retention_service import RetentionService
        print("✓ RetentionService imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import RetentionService: {e}")
        return False

def test_config_import():
    """Test that config can be imported and has retention settings"""
    try:
        from app.config import settings
        # Check that retention settings exist
        assert hasattr(settings, 'RETENTION_FEEDBACK_DAYS')
        assert hasattr(settings, 'RETENTION_SUGGESTIONS_DAYS')
        assert hasattr(settings, 'RETENTION_AUDIT_HISTORY_LONG_TERM')
        assert hasattr(settings, 'RETENTION_EVALUATION_RESULTS_VERSION_CONTROLLED')
        assert hasattr(settings, 'RETENTION_BACKGROUND_JOBS_DAYS')
        print("✓ Config retention settings verified")
        return True
    except Exception as e:
        print(f"✗ Config import failed: {e}")
        return False

def test_retention_service_initialization():
    """Test that retention service initializes with correct values"""
    try:
        from app.services.retention_service import RetentionService
        from app.config import settings

        service = RetentionService()

        # Check that service has the expected attributes
        assert service.feedback_retention_days == settings.RETENTION_FEEDBACK_DAYS
        assert service.suggestions_retention_days == settings.RETENTION_SUGGESTIONS_DAYS
        assert service.background_jobs_retention_days == settings.RETENTION_BACKGROUND_JOBS_DAYS
        assert service.audit_history_long_term == settings.RETENTION_AUDIT_HISTORY_LONG_TERM
        assert service.evaluation_results_version_controlled == settings.RETENTION_EVALUATION_RESULTS_VERSION_CONTROLLED

        print("✓ RetentionService initialized with correct values")
        return True
    except Exception as e:
        print(f"✗ RetentionService initialization failed: {e}")
        return False

def test_external_model_data_config():
    """Test that Spec 10.6 external model data config is present"""
    try:
        from app.config import settings

        # Check that external model data settings exist
        assert hasattr(settings, 'EXTERNAL_MODEL_DATA_ENABLED')
        assert hasattr(settings, 'EXTERNAL_MODEL_ENDPOINT')
        assert hasattr(settings, 'EXTERNAL_MODEL_API_KEY')
        assert hasattr(settings, 'EXTERNAL_MODEL_CONSENT_REQUIRED')
        assert hasattr(settings, 'EXTERNAL_MODEL_ENCRYPTION_REQUIRED')
        assert hasattr(settings, 'EXTERNAL_MODEL_DATA_PROTECTION_COMPLIANT')
        assert hasattr(settings, 'EXTERNAL_MODEL_AUDIT_LOGGING_ENABLED')

        # Check that default is False (opt-in required)
        assert settings.EXTERNAL_MODEL_DATA_ENABLED == False

        print("✓ Spec 10.6 external model data config verified")
        return True
    except Exception as e:
        print(f"✗ External model data config test failed: {e}")
        return False

if __name__ == "__main__":
    print("Running Spec 10.6 and 10.7 retention tests...\n")

    tests = [
        test_retention_service_import,
        test_config_import,
        test_retention_service_initialization,
        test_external_model_data_config
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()  # Add space between tests

    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed!")
        sys.exit(1)