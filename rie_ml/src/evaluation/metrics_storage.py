#!/usr/bin/env python3
"""Persistent metrics storage for baseline and ML model evaluation results.

Stores evaluation results to disk so they can be retrieved, compared, and tracked over time.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import uuid


@dataclass
class ClassificationMetrics:
    """Classification module evaluation metrics."""
    accuracy: float
    precision: Dict[str, float]  # per-category
    recall: Dict[str, float]  # per-category
    f1_score: Dict[str, float]  # per-category
    calibration_error: float
    confusion_matrix: Dict[str, Dict[str, int]]
    total_samples: int
    correct_predictions: int


@dataclass
class ExtractionMetrics:
    """Rule extraction module evaluation metrics."""
    business_term_precision: float
    business_term_recall: float
    business_term_f1: float
    operation_precision: float
    operation_recall: float
    operation_f1: float
    conditions_precision: float
    conditions_recall: float
    conditions_f1: float
    scope_precision: float
    scope_recall: float
    scope_f1: float
    time_window_precision: float
    time_window_recall: float
    time_window_f1: float
    affected_entities_precision: float
    affected_entities_recall: float
    affected_entities_f1: float
    threshold_precision: float
    threshold_recall: float
    threshold_f1: float
    exact_rule_match_rate: float
    schema_validation_pass_rate: float
    total_samples: int


@dataclass
class DuplicateDetectionMetrics:
    """Duplicate detection module evaluation metrics."""
    precision: float
    recall: float
    f1_score: float
    recall_at_k: float
    false_positive_rate: float
    false_negative_rate: float
    exact_duplicates_precision: float
    exact_duplicates_recall: float
    semantic_duplicates_precision: float
    semantic_duplicates_recall: float
    total_pairs: int
    true_positives: int
    false_positives: int
    false_negatives: int


@dataclass
class ConflictDetectionMetrics:
    """Conflict detection module evaluation metrics."""
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    false_conflict_rate: float
    missed_conflict_rate: float
    conflict_recall: float
    classification_accuracy: float
    logical_contradictions_precision: float
    logical_contradictions_recall: float
    threshold_conflicts_precision: float
    threshold_conflicts_recall: float
    scope_conflicts_precision: float
    scope_conflicts_recall: float
    time_window_conflicts_precision: float
    time_window_conflicts_recall: float
    permission_conflicts_precision: float
    permission_conflicts_recall: float
    total_pairs: int
    true_positives: int
    false_positives: int
    false_negatives: int


@dataclass
class ClarificationMetrics:
    """Clarification generation evaluation metrics."""
    detection_precision: float
    detection_recall: float
    detection_f1_score: float
    missed_clarification_cases: int
    incorrect_clarification_requests: int
    average_resolution_time_seconds: float
    total_cases: int
    correct_clarifications: int


@dataclass
class BaselineEvaluationResult:
    """Complete baseline evaluation result."""
    evaluation_id: str
    timestamp: str
    model_type: str  # "baseline_deterministic", "ml_candidate", etc.
    model_version: str
    dataset_split: str  # "frozen_evaluation", "validation", etc.
    dataset_size: int
    classification: ClassificationMetrics
    extraction: ExtractionMetrics
    duplicate_detection: DuplicateDetectionMetrics
    conflict_detection: ConflictDetectionMetrics
    clarification: ClarificationMetrics
    average_processing_time_seconds: float
    notes: str
    acceptance_criteria_passed: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "evaluation_id": self.evaluation_id,
            "timestamp": self.timestamp,
            "model_type": self.model_type,
            "model_version": self.model_version,
            "dataset_split": self.dataset_split,
            "dataset_size": self.dataset_size,
            "classification": asdict(self.classification),
            "extraction": asdict(self.extraction),
            "duplicate_detection": asdict(self.duplicate_detection),
            "conflict_detection": asdict(self.conflict_detection),
            "clarification": asdict(self.clarification),
            "average_processing_time_seconds": self.average_processing_time_seconds,
            "notes": self.notes,
            "acceptance_criteria_passed": self.acceptance_criteria_passed,
        }


class MetricsStorage:
    """Manage persistent storage and retrieval of evaluation metrics."""

    def __init__(self, storage_dir: Optional[Path] = None):
        """Initialize metrics storage.

        Args:
            storage_dir: Directory for storing metrics. Defaults to rie_ml/datasets/evaluation/metrics
        """
        if storage_dir is None:
            storage_dir = Path(__file__).parent.parent.parent / "datasets" / "evaluation" / "metrics"

        self.storage_dir = Path(storage_dir)
        self.results_dir = self.storage_dir / "results"
        self.summaries_dir = self.storage_dir / "summaries"
        self.comparisons_dir = self.storage_dir / "comparisons"

        # Create directories
        for dir_path in [self.results_dir, self.summaries_dir, self.comparisons_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def save_result(self, result: BaselineEvaluationResult) -> Path:
        """Save evaluation result to disk.

        Args:
            result: BaselineEvaluationResult to save

        Returns:
            Path to saved file
        """
        result_file = self.results_dir / f"{result.evaluation_id}.json"

        with open(result_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

        return result_file

    def load_result(self, evaluation_id: str) -> Optional[BaselineEvaluationResult]:
        """Load evaluation result from disk.

        Args:
            evaluation_id: ID of the evaluation to load

        Returns:
            BaselineEvaluationResult or None if not found
        """
        result_file = self.results_dir / f"{evaluation_id}.json"

        if not result_file.exists():
            return None

        with open(result_file, 'r') as f:
            data = json.load(f)

        # Reconstruct dataclass objects
        return self._dict_to_result(data)

    def list_results(self, model_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List all stored evaluation results.

        Args:
            model_type: Filter by model type (optional)
            limit: Maximum number of results to return

        Returns:
            List of evaluation result metadata
        """
        results = []

        for result_file in sorted(self.results_dir.glob("*.json"), reverse=True)[:limit]:
            with open(result_file, 'r') as f:
                data = json.load(f)

            if model_type and data.get("model_type") != model_type:
                continue

            results.append({
                "evaluation_id": data["evaluation_id"],
                "timestamp": data["timestamp"],
                "model_type": data["model_type"],
                "model_version": data["model_version"],
                "acceptance_criteria_passed": data["acceptance_criteria_passed"],
            })

        return results

    def save_summary_report(self, result: BaselineEvaluationResult) -> Path:
        """Save a human-readable summary report.

        Args:
            result: BaselineEvaluationResult to summarize

        Returns:
            Path to saved report
        """
        report_file = self.summaries_dir / f"{result.evaluation_id}_summary.txt"

        lines = [
            "=" * 80,
            "BASELINE EVALUATION REPORT",
            "=" * 80,
            f"Evaluation ID: {result.evaluation_id}",
            f"Timestamp: {result.timestamp}",
            f"Model Type: {result.model_type}",
            f"Model Version: {result.model_version}",
            f"Dataset: {result.dataset_split} ({result.dataset_size} samples)",
            "",
            "CLASSIFICATION METRICS",
            "-" * 80,
            f"  Accuracy: {result.classification.accuracy * 100:.2f}%",
            f"  Calibration Error: {result.classification.calibration_error:.4f}",
            f"  Per-Category F1 Scores:",
            *[f"    {cat}: {score:.4f}" for cat, score in result.classification.f1_score.items()],
            "",
            "RULE EXTRACTION METRICS",
            "-" * 80,
            f"  Business Term F1: {result.extraction.business_term_f1:.4f}",
            f"  Operation F1: {result.extraction.operation_f1:.4f}",
            f"  Conditions F1: {result.extraction.conditions_f1:.4f}",
            f"  Scope F1: {result.extraction.scope_f1:.4f}",
            f"  Time Window F1: {result.extraction.time_window_f1:.4f}",
            f"  Affected Entities F1: {result.extraction.affected_entities_f1:.4f}",
            f"  Threshold F1: {result.extraction.threshold_f1:.4f}",
            f"  Exact Rule Match Rate: {result.extraction.exact_rule_match_rate * 100:.2f}%",
            f"  Schema Validation Pass Rate: {result.extraction.schema_validation_pass_rate * 100:.2f}%",
            "",
            "DUPLICATE DETECTION METRICS",
            "-" * 80,
            f"  Precision: {result.duplicate_detection.precision:.4f}",
            f"  Recall: {result.duplicate_detection.recall:.4f}",
            f"  F1 Score: {result.duplicate_detection.f1_score:.4f}",
            f"  Recall@K: {result.duplicate_detection.recall_at_k:.4f}",
            f"  False Positive Rate: {result.duplicate_detection.false_positive_rate:.4f}",
            f"  False Negative Rate: {result.duplicate_detection.false_negative_rate:.4f}",
            "",
            "CONFLICT DETECTION METRICS",
            "-" * 80,
            f"  Precision: {result.conflict_detection.precision:.4f}",
            f"  Recall: {result.conflict_detection.recall:.4f}",
            f"  F1 Score: {result.conflict_detection.f1_score:.4f}",
            f"  Accuracy: {result.conflict_detection.accuracy:.4f}",
            f"  False Conflict Rate: {result.conflict_detection.false_conflict_rate:.4f}",
            f"  Missed Conflict Rate: {result.conflict_detection.missed_conflict_rate:.4f}",
            "",
            "CLARIFICATION METRICS",
            "-" * 80,
            f"  Detection Precision: {result.clarification.detection_precision:.4f}",
            f"  Detection Recall: {result.clarification.detection_recall:.4f}",
            f"  Detection F1: {result.clarification.detection_f1_score:.4f}",
            f"  Average Resolution Time: {result.clarification.average_resolution_time_seconds:.2f}s",
            "",
            "PERFORMANCE",
            "-" * 80,
            f"  Average Processing Time: {result.average_processing_time_seconds:.2f}s per sample",
            "",
            "ACCEPTANCE CRITERIA",
            "-" * 80,
            f"  Status: {'✅ PASSED' if result.acceptance_criteria_passed else '❌ FAILED'}",
            "",
            "NOTES",
            "-" * 80,
            result.notes,
            "=" * 80,
        ]

        with open(report_file, 'w') as f:
            f.write("\n".join(lines))

        return report_file

    def compare_results(self, baseline_id: str, candidate_id: str) -> Dict[str, Any]:
        """Compare two evaluation results.

        Args:
            baseline_id: ID of baseline evaluation
            candidate_id: ID of candidate evaluation

        Returns:
            Comparison report
        """
        baseline = self.load_result(baseline_id)
        candidate = self.load_result(candidate_id)

        if not baseline or not candidate:
            return {"error": "One or both evaluation results not found"}

        comparison = {
            "baseline_id": baseline_id,
            "candidate_id": candidate_id,
            "baseline_timestamp": baseline.timestamp,
            "candidate_timestamp": candidate.timestamp,
            "improvements": {},
            "regressions": {},
        }

        # Compare classification
        if baseline.classification.accuracy < candidate.classification.accuracy:
            comparison["improvements"]["classification_accuracy"] = {
                "baseline": baseline.classification.accuracy,
                "candidate": candidate.classification.accuracy,
                "improvement": candidate.classification.accuracy - baseline.classification.accuracy,
            }
        elif baseline.classification.accuracy > candidate.classification.accuracy:
            comparison["regressions"]["classification_accuracy"] = {
                "baseline": baseline.classification.accuracy,
                "candidate": candidate.classification.accuracy,
                "regression": baseline.classification.accuracy - candidate.classification.accuracy,
            }

        # Compare extraction F1 scores
        for field in ["business_term", "operation", "conditions", "scope", "time_window", "affected_entities", "threshold"]:
            baseline_f1 = getattr(baseline.extraction, f"{field}_f1")
            candidate_f1 = getattr(candidate.extraction, f"{field}_f1")

            if baseline_f1 < candidate_f1:
                comparison["improvements"][f"extraction_{field}_f1"] = {
                    "baseline": baseline_f1,
                    "candidate": candidate_f1,
                    "improvement": candidate_f1 - baseline_f1,
                }
            elif baseline_f1 > candidate_f1:
                comparison["regressions"][f"extraction_{field}_f1"] = {
                    "baseline": baseline_f1,
                    "candidate": candidate_f1,
                    "regression": baseline_f1 - candidate_f1,
                }

        # Compare duplicate detection
        comparison["duplicate_detection"] = {
            "baseline_precision": baseline.duplicate_detection.precision,
            "candidate_precision": candidate.duplicate_detection.precision,
            "baseline_recall": baseline.duplicate_detection.recall,
            "candidate_recall": candidate.duplicate_detection.recall,
        }

        # Compare conflict detection
        comparison["conflict_detection"] = {
            "baseline_precision": baseline.conflict_detection.precision,
            "candidate_precision": candidate.conflict_detection.precision,
            "baseline_recall": baseline.conflict_detection.recall,
            "candidate_recall": candidate.conflict_detection.recall,
        }

        comparison["overall_improvement"] = len(comparison["improvements"]) > len(comparison["regressions"])

        return comparison

    def save_comparison(self, comparison: Dict[str, Any]) -> Path:
        """Save comparison report to disk.

        Args:
            comparison: Comparison report

        Returns:
            Path to saved comparison
        """
        comparison_id = str(uuid.uuid4())[:8]
        comparison_file = self.comparisons_dir / f"comparison_{comparison_id}.json"

        with open(comparison_file, 'w') as f:
            json.dump(comparison, f, indent=2)

        return comparison_file

    @staticmethod
    def _dict_to_result(data: Dict[str, Any]) -> BaselineEvaluationResult:
        """Convert dictionary to BaselineEvaluationResult."""
        return BaselineEvaluationResult(
            evaluation_id=data["evaluation_id"],
            timestamp=data["timestamp"],
            model_type=data["model_type"],
            model_version=data["model_version"],
            dataset_split=data["dataset_split"],
            dataset_size=data["dataset_size"],
            classification=ClassificationMetrics(**data["classification"]),
            extraction=ExtractionMetrics(**data["extraction"]),
            duplicate_detection=DuplicateDetectionMetrics(**data["duplicate_detection"]),
            conflict_detection=ConflictDetectionMetrics(**data["conflict_detection"]),
            clarification=ClarificationMetrics(**data["clarification"]),
            average_processing_time_seconds=data["average_processing_time_seconds"],
            notes=data["notes"],
            acceptance_criteria_passed=data["acceptance_criteria_passed"],
        )
