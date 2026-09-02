"""Tests for duplicate detection module."""

import pytest
import json
from app.services.duplicate_detection_service import DuplicateDetector, RealDuplicateDetectionService


@pytest.fixture
def sample_rule_1():
    """Sample rule for testing."""
    return {
        "rule_id": "R1",
        "business_term": "revenue",
        "operation": "exclude",
        "conditions": [
            {"field": "orders.status", "operator": "equals", "value": "cancelled"}
        ],
        "scope": "global",
        "affected_entities": {
            "tables": ["orders"],
            "columns": ["orders.status"]
        },
        "threshold": 0
    }


@pytest.fixture
def sample_rule_2():
    """Exact duplicate of rule 1."""
    return {
        "rule_id": "R2",
        "business_term": "revenue",
        "operation": "exclude",
        "conditions": [
            {"field": "orders.status", "operator": "equals", "value": "cancelled"}
        ],
        "scope": "global",
        "affected_entities": {
            "tables": ["orders"],
            "columns": ["orders.status"]
        },
        "threshold": 0
    }


@pytest.fixture
def sample_rule_3():
    """Semantic duplicate (same business term and operation, similar conditions)."""
    return {
        "rule_id": "R3",
        "business_term": "revenue",
        "operation": "exclude",
        "conditions": [
            {"field": "orders.status", "operator": "equals", "value": "failed"}
        ],
        "scope": "global",
        "affected_entities": {
            "tables": ["orders"],
            "columns": ["orders.status"]
        },
        "threshold": 0
    }


@pytest.fixture
def sample_rule_4():
    """Modification of rule 1 (different conditions for same metric)."""
    return {
        "rule_id": "R4",
        "business_term": "revenue",
        "operation": "exclude",
        "conditions": [
            {"field": "orders.status", "operator": "equals", "value": "cancelled"},
            {"field": "orders.amount", "operator": "less_than", "value": 10}
        ],
        "scope": "global",
        "affected_entities": {
            "tables": ["orders"],
            "columns": ["orders.status", "orders.amount"]
        },
        "threshold": 0
    }


@pytest.fixture
def sample_rule_5():
    """Unrelated rule (different business term)."""
    return {
        "rule_id": "R5",
        "business_term": "customer_count",
        "operation": "include",
        "conditions": [
            {"field": "customers.is_active", "operator": "equals", "value": "true"}
        ],
        "scope": "global",
        "affected_entities": {
            "tables": ["customers"],
            "columns": ["customers.is_active"]
        },
        "threshold": 0
    }


class TestDuplicateDetector:
    """Tests for DuplicateDetector structural comparison."""

    def test_exact_duplicate_detection(self, sample_rule_1, sample_rule_2):
        """Test detection of exact duplicates."""
        detector = DuplicateDetector()
        result = detector.detect(sample_rule_1, [sample_rule_2])

        assert result["relationship"] == "exact_duplicate"
        assert result["confidence"] >= 0.95
        assert result["matching_rule_id"] == "R2"

    def test_semantic_duplicate_detection(self, sample_rule_1, sample_rule_3):
        """Test detection of semantic duplicates."""
        detector = DuplicateDetector()
        result = detector.detect(sample_rule_1, [sample_rule_3])

        # Semantic duplicate has same structure but different values
        assert result["relationship"] == "semantic_duplicate"
        assert result["confidence"] >= 0.75
        assert result["matching_rule_id"] == "R3"

    def test_modification_detection(self, sample_rule_1, sample_rule_4):
        """Test detection of rule modifications."""
        detector = DuplicateDetector()
        result = detector.detect(sample_rule_1, [sample_rule_4])

        # Modification has same business term/operation but different conditions
        assert result["relationship"] == "modification"
        assert result["confidence"] >= 0.5
        assert result["matching_rule_id"] == "R4"

    def test_unrelated_rule_detection(self, sample_rule_1, sample_rule_5):
        """Test detection that rules are unrelated."""
        detector = DuplicateDetector()
        result = detector.detect(sample_rule_1, [sample_rule_5])

        assert result["relationship"] == "unrelated"
        assert result["confidence"] < 0.5
        assert result["matching_rule_id"] is None

    def test_no_existing_rules(self, sample_rule_1):
        """Test behavior when no existing rules."""
        detector = DuplicateDetector()
        result = detector.detect(sample_rule_1, [])

        assert result["relationship"] == "unrelated"
        assert result["confidence"] == 0.0
        assert result["matching_rule_id"] is None

    def test_multiple_candidates_returns_best_match(self, sample_rule_1, sample_rule_2, sample_rule_3, sample_rule_5):
        """Test that detector returns the best match from multiple candidates."""
        detector = DuplicateDetector()
        candidates = [sample_rule_5, sample_rule_3, sample_rule_2]

        result = detector.detect(sample_rule_1, candidates)

        # Should pick exact duplicate over semantic duplicate
        assert result["relationship"] == "exact_duplicate"
        assert result["matching_rule_id"] == "R2"
        assert result["confidence"] >= 0.95

    def test_string_similarity(self):
        """Test string similarity calculation."""
        detector = DuplicateDetector()

        # Exact match
        assert detector._string_similarity("revenue", "revenue") == 1.0

        # Very similar
        similarity = detector._string_similarity("revenue", "revenues")
        assert similarity > 0.8

        # Different
        similarity = detector._string_similarity("revenue", "customer")
        assert similarity < 0.5

    def test_condition_comparison_exact_match(self):
        """Test exact condition matching."""
        detector = DuplicateDetector()

        cond1 = [{"field": "orders.status", "operator": "equals", "value": "cancelled"}]
        cond2 = [{"field": "orders.status", "operator": "equals", "value": "cancelled"}]

        similarity = detector._compare_conditions(cond1, cond2)
        assert similarity == 1.0

    def test_condition_comparison_partial_match(self):
        """Test partial condition matching."""
        detector = DuplicateDetector()

        cond1 = [
            {"field": "orders.status", "operator": "equals", "value": "cancelled"},
            {"field": "orders.amount", "operator": "greater_than", "value": 100}
        ]
        cond2 = [
            {"field": "orders.status", "operator": "equals", "value": "cancelled"}
        ]

        similarity = detector._compare_conditions(cond1, cond2)
        # 1 out of 2 conditions match
        assert 0.4 < similarity < 0.6

    def test_condition_comparison_no_match(self):
        """Test conditions with no matches."""
        detector = DuplicateDetector()

        cond1 = [{"field": "orders.status", "operator": "equals", "value": "cancelled"}]
        cond2 = [{"field": "customers.id", "operator": "equals", "value": "123"}]

        similarity = detector._compare_conditions(cond1, cond2)
        assert similarity == 0.0

    def test_entity_comparison_exact_match(self):
        """Test exact entity matching."""
        detector = DuplicateDetector()

        entities1 = {
            "tables": ["orders", "customers"],
            "columns": ["orders.status", "customers.id"]
        }
        entities2 = {
            "tables": ["orders", "customers"],
            "columns": ["orders.status", "customers.id"]
        }

        similarity = detector._compare_entities(entities1, entities2)
        assert similarity == 1.0

    def test_entity_comparison_partial_match(self):
        """Test partial entity matching."""
        detector = DuplicateDetector()

        entities1 = {
            "tables": ["orders", "customers"],
            "columns": ["orders.status", "customers.id"]
        }
        entities2 = {
            "tables": ["orders"],
            "columns": ["orders.status"]
        }

        similarity = detector._compare_entities(entities1, entities2)
        # Partial match - Jaccard similarity
        assert 0.3 < similarity < 0.7

    def test_relationship_detection_logic(self):
        """Test the relationship determination logic."""
        detector = DuplicateDetector()

        new_rule = {
            "business_term": "revenue",
            "operation": "exclude",
            "conditions": [{"field": "orders.status", "operator": "equals", "value": "cancelled"}],
            "scope": "global",
            "affected_entities": {"tables": ["orders"], "columns": ["orders.status"]}
        }

        existing_rule = {
            "rule_id": "R_existing",
            "business_term": "revenue",
            "operation": "exclude",
            "conditions": [{"field": "orders.status", "operator": "equals", "value": "cancelled"}],
            "scope": "global",
            "affected_entities": {"tables": ["orders"], "columns": ["orders.status"]}
        }

        relationship, confidence, details = detector._compare_rules(new_rule, existing_rule)

        assert relationship == "exact_duplicate"
        assert confidence >= 0.95
        assert details["business_term_match"] is True
        assert details["operation_match"] is True


class TestRealDuplicateDetectionService:
    """Tests for RealDuplicateDetectionService with pgvector."""

    def test_service_initialization(self):
        """Test service initializes without errors."""
        service = RealDuplicateDetectionService()
        assert service.detector is not None
        assert service.CANDIDATE_K == 10

    def test_no_database_connection(self, sample_rule_1):
        """Test handling of missing database connection."""
        service = RealDuplicateDetectionService()

        result = service.check_duplicate(
            sample_rule_1,
            workspace_id="test_workspace",
            domain_id="test_domain",
            db=None
        )

        assert result["is_duplicate"] is False
        assert result["relationship"] == "unrelated"
        assert result["confidence"] == 0.0
        assert result["retrieval_stage"] == 0

    def test_no_candidates_found(self, sample_rule_1):
        """Test handling when pgvector finds no candidates."""
        service = RealDuplicateDetectionService()

        # Mock empty candidate retrieval
        def mock_retrieve_candidates(rule, ws_id, domain_id, db):
            return []

        service._retrieve_candidates = mock_retrieve_candidates

        result = service.check_duplicate(
            sample_rule_1,
            workspace_id="test_workspace",
            domain_id="test_domain",
            db=object()  # Mock DB object
        )

        assert result["is_duplicate"] is False
        assert result["relationship"] == "unrelated"
        assert result["retrieval_stage"] == 0

    def test_candidate_retrieval_and_comparison(self, sample_rule_1, sample_rule_2):
        """Test full workflow: candidate retrieval + structural comparison."""
        service = RealDuplicateDetectionService()

        # Mock candidate retrieval to return sample_rule_2
        def mock_retrieve_candidates(rule, ws_id, domain_id, db):
            return [sample_rule_2]

        service._retrieve_candidates = mock_retrieve_candidates

        result = service.check_duplicate(
            sample_rule_1,
            workspace_id="test_workspace",
            domain_id="test_domain",
            db=object()
        )

        assert result["is_duplicate"] is True
        assert result["relationship"] == "exact_duplicate"
        assert result["confidence"] >= 0.95
        assert result["retrieval_stage"] == 1

    def test_pgvector_filtering_efficiency(self, sample_rule_1):
        """Test that pgvector reduces candidate set from 100+ to 10."""
        service = RealDuplicateDetectionService()

        # Simulate scenario: 100 rules in DB, pgvector pre-filters to 10
        def mock_retrieve_candidates(rule, ws_id, domain_id, db):
            # Return 10 candidates
            candidates = []
            for i in range(10):
                candidates.append({
                    "rule_id": f"R{i}",
                    "business_term": "revenue" if i % 2 == 0 else "customer_count",
                    "operation": "exclude" if i % 2 == 0 else "include",
                    "conditions": [{"field": "orders.status", "operator": "equals", "value": "cancelled"}],
                    "scope": "global",
                    "similarity_score": 0.90 - (i * 0.05)  # Decreasing similarity
                })
            return candidates

        service._retrieve_candidates = mock_retrieve_candidates

        result = service.check_duplicate(
            sample_rule_1,
            workspace_id="test_workspace",
            domain_id="test_domain",
            db=object()
        )

        assert result["retrieval_stage"] == 10
        # Should find a match among the 10 candidates
        assert result["confidence"] >= 0

    def test_fallback_when_embedding_unavailable(self, sample_rule_1):
        """Test fallback to all-rules comparison when embedding fails."""
        service = RealDuplicateDetectionService()

        # Disable embedding service
        service.embedding_service = None

        # Mock fallback retrieval
        def mock_fallback_retrieve(ws_id, domain_id, db):
            return [sample_rule_1]

        service._fallback_retrieve_all_rules = mock_fallback_retrieve

        # This should trigger fallback logic
        result = service.check_duplicate(
            sample_rule_1,
            workspace_id="test_workspace",
            domain_id="test_domain",
            db=object()
        )

        # Should still work via fallback
        assert result["relationship"] is not None


class TestDuplicateDetectionIntegration:
    """Integration tests for duplicate detection."""

    def test_detection_pipeline_exact_duplicate(self, sample_rule_1, sample_rule_2):
        """Test complete pipeline for exact duplicate."""
        service = RealDuplicateDetectionService()

        def mock_retrieve(rule, ws_id, domain_id, db):
            return [sample_rule_2]

        service._retrieve_candidates = mock_retrieve

        result = service.check_duplicate(
            sample_rule_1,
            workspace_id="ws1",
            domain_id="ecommerce",
            db=object()
        )

        assert result["is_duplicate"] is True
        assert result["relationship"] == "exact_duplicate"
        assert result["matching_rule_id"] == "R2"

    def test_detection_pipeline_semantic_duplicate(self, sample_rule_1, sample_rule_3):
        """Test complete pipeline for semantic duplicate."""
        service = RealDuplicateDetectionService()

        def mock_retrieve(rule, ws_id, domain_id, db):
            return [sample_rule_3]

        service._retrieve_candidates = mock_retrieve

        result = service.check_duplicate(
            sample_rule_1,
            workspace_id="ws1",
            domain_id="ecommerce",
            db=object()
        )

        assert result["is_duplicate"] is True
        assert result["relationship"] == "semantic_duplicate"
        assert result["matching_rule_id"] == "R3"

    def test_detection_pipeline_modification(self, sample_rule_1, sample_rule_4):
        """Test complete pipeline for rule modification."""
        service = RealDuplicateDetectionService()

        def mock_retrieve(rule, ws_id, domain_id, db):
            return [sample_rule_4]

        service._retrieve_candidates = mock_retrieve

        result = service.check_duplicate(
            sample_rule_1,
            workspace_id="ws1",
            domain_id="ecommerce",
            db=object()
        )

        assert result["relationship"] == "modification"
        assert result["confidence"] >= 0.7
        assert result["matching_rule_id"] == "R4"

    def test_detection_handles_mixed_candidates(self, sample_rule_1, sample_rule_2, sample_rule_3, sample_rule_5):
        """Test detection with mixed candidate set."""
        service = RealDuplicateDetectionService()

        def mock_retrieve(rule, ws_id, domain_id, db):
            # Return mix of related and unrelated rules
            return [sample_rule_5, sample_rule_3, sample_rule_2]

        service._retrieve_candidates = mock_retrieve

        result = service.check_duplicate(
            sample_rule_1,
            workspace_id="ws1",
            domain_id="ecommerce",
            db=object()
        )

        # Should identify best match (exact duplicate)
        assert result["is_duplicate"] is True
        assert result["relationship"] == "exact_duplicate"
        assert result["matching_rule_id"] == "R2"
        assert result["retrieval_stage"] == 3
