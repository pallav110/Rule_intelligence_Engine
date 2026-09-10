#!/usr/bin/env python3
"""Database persistence bridge for RIE model evaluation & promotion results.

Records evaluation results, the dataset they ran on, and model registration /
promotion lifecycles into the PostgreSQL database that the application uses
(app.db.models.*), so results are queryable and durable — not only JSON on disk.

This complements (not replaces) the file-based ``MetricsStorage``, which remains
the JSON fallback.

Usage (from repo root, so ``app`` is importable):

    from rie_ml.src.evaluation.metrics_storage_db import MetricsStorageDB
    store = MetricsStorageDB()
    model_id = store.ensure_model("baseline-deterministic-classifier", ...)
    ds_id = store.ensure_dataset("frozen_evaluation-v0.2.0", frozen_path, n=201)
    store.save_evaluation(result_dict, model_id=model_id, dataset_version_id=ds_id,
                          domain_pack_ids=[...])
    store.promote(model_id, "APPROVED", reason="Met acceptance criteria")
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class MetricsStorageDB:
    """Persist evaluation + promotion results to the application database."""

    def __init__(self, session_factory=None):
        # Import lazily so this module can be imported even without the app /
        # DB stack present (files-only use stays functional).
        self.session_factory = session_factory or self._default_session_factory()

    # ------------------------------------------------------------------
    #  DB plumbing
    # ------------------------------------------------------------------

    @staticmethod
    def _default_session_factory():
        from app.db.database import SessionLocal
        return SessionLocal

    def _session(self):
        return self.session_factory()

    # ------------------------------------------------------------------
    #  Dataset versions
    # ------------------------------------------------------------------

    def ensure_dataset(
        self,
        dataset_name: str,
        version: str,
        path: str,
        num_samples: Optional[int] = None,
        annotation_version: str = "ann_v0.2.0",
        domain_pack_version: str = "v0.2.0",
        source: str = "programmatic",
        status: str = "FROZEN",
        description: Optional[str] = None,
    ) -> str:
        """Create (or return existing) a dataset version row.

        Returns the dataset_version_id.
        """
        from app.db.models.dataset_version import DatasetVersion

        session = self._session()
        try:
            existing = (
                session.query(DatasetVersion)
                .filter(
                    DatasetVersion.dataset_name == dataset_name,
                    DatasetVersion.version == version,
                )
                .first()
            )
            if existing:
                return existing.dataset_version_id

            ds = DatasetVersion(
                dataset_version_id=f"dsv-{uuid.uuid4().hex[:10]}",
                dataset_name=dataset_name,
                version=version,
                description=description,
                num_samples=num_samples,
                domain_pack_version=domain_pack_version,
                annotation_version=annotation_version,
                source=source,
                path=path,
                status=status,
            )
            session.add(ds)
            session.commit()
            session.refresh(ds)
            return ds.dataset_version_id
        finally:
            session.close()

    # ------------------------------------------------------------------
    #  Model versions (registration) — spec 8.11 lifecycle
    # ------------------------------------------------------------------

    def get_model_version_id(
        self, model_name: str, version: str, model_type: str = "other"
    ) -> Optional[str]:
        from app.db.models.model_version import ModelVersion

        session = self._session()
        try:
            mv = (
                session.query(ModelVersion)
                .filter(
                    ModelVersion.model_name == model_name,
                    ModelVersion.version == version,
                    ModelVersion.model_type == model_type,
                )
                .first()
            )
            return mv.model_version_id if mv else None
        finally:
            session.close()

    def ensure_model(
        self,
        model_name: str,
        model_type: str,
        version: str,
        checkpoint_path: str,
        description: Optional[str] = None,
        evaluation_metrics: Optional[Dict[str, Any]] = None,
        annotation_scheme_version: str = "ann_v0.2.0",
        training_dataset_version_id: Optional[str] = None,
        validation_dataset_version_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Register (or return existing) a model version in the DB.

        Returns the model_version_id. Status defaults to CANDIDATE.
        """
        from app.schemas.model_version import ModelVersionCreateRequest

        existing = self.get_model_version_id(model_name, version, model_type)
        if existing:
            return existing

        service = self._model_version_service()
        session = self._session()
        try:
            payload = ModelVersionCreateRequest(
                model_name=model_name,
                model_type=model_type,  # service normalizes to dashed type
                version=version,
                description=description,
                checkpoint_path=checkpoint_path,
                training_dataset_version_id=training_dataset_version_id,
                validation_dataset_version_id=validation_dataset_version_id,
                annotation_scheme_version=annotation_scheme_version,
                hyperparameters={"tags": tags or []},
                evaluation_metrics=evaluation_metrics,
            )
            mv = service.create_model_version(session, payload)
            return mv.model_version_id
        finally:
            session.close()

    @staticmethod
    def _model_version_service():
        from app.services.model_version_service import ModelVersionService
        return ModelVersionService()

    # ------------------------------------------------------------------
    #  Evaluation runs + metrics
    # ------------------------------------------------------------------

    def save_evaluation(
        self,
        result: Any,
        *,
        model_version_id: Optional[str] = None,
        model_name: str = "baseline-deterministic-classifier",
        model_version: str = "1.0.0",
        model_type: str = "classification",  # must be one of the 7 ModelType enum values
        dataset_version_id: Optional[str] = None,
        dataset_name: str = "rie-feedback-frozen-evaluation",
        dataset_path: Optional[str] = None,
        dataset_size: Optional[int] = None,
        domain_pack_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> str:
        """Persist one evaluation result to evaluation_runs + evaluation_metrics.

        ``result`` may be a ``BaselineEvaluationResult`` (has .to_dict()) or a
        bare dict following the same shape. Returns the evaluation_run_id.
        """
        import json

        from app.db.models.evaluation_metric import EvaluationMetric
        from app.db.models.evaluation_run import EvaluationRun

        data = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        finalize_close = False

        # Ensure dataset version exists (FK requirement)
        if dataset_version_id is None:
            path = dataset_path or f"rie_ml/datasets/evaluation/{data.get('dataset_split','frozen_evaluation')}.jsonl"
            dataset_version_id = self.ensure_dataset(
                dataset_name=dataset_name,
                version=data.get("model_version", model_version) or model_version,
                path=path,
                num_samples=dataset_size or data.get("dataset_size"),
            )

        # Ensure model version exists (FK requirement); persist metrics on it
        if model_version_id is None:
            model_version_id = self.ensure_model(
                model_name=model_name,
                model_type=model_type,
                version=data.get("model_version", model_version) or model_version,
                checkpoint_path=str(Path("rie_ml/models/baseline/baseline_classifier_unified.pkl")),
                description=(reason or "") + " (registered from MetricsStorageDB)",
                evaluation_metrics={
                    "classification_accuracy": self._g(data, "classification", "accuracy"),
                    "extraction_exact_match_rate": self._g(data, "extraction", "exact_rule_match_rate"),
                    "duplicate_f1": self._g(data, "duplicate_detection", "f1_score"),
                    "conflict_f1": self._g(data, "conflict_detection", "f1_score"),
                    "dataset_size": data.get("dataset_size"),
                },
            )

        classification = data.get("classification", {})
        extraction = data.get("extraction", {})
        duplicate = data.get("duplicate_detection", {})
        conflict = data.get("conflict_detection", {})

        evaluation_run_id = f"evrun-{uuid.uuid4().hex[:10]}"
        run = EvaluationRun(
            evaluation_run_id=evaluation_run_id,
            model_version_id=model_version_id,
            dataset_version_id=dataset_version_id,
            domain_pack_id=domain_pack_id,
            status="completed",
            classification_accuracy=classification.get("accuracy"),
            classification_f1=classification.get("f1_score"),
            complete_rule_accuracy=extraction.get("exact_rule_match_rate"),
            duplicate_f1=duplicate.get("f1_score"),
            conflict_f1=conflict.get("f1_score"),
            calibration_error=classification.get("calibration_error"),
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        # Discrete metric rows
        scalar_metrics = {
            "classification_accuracy": classification.get("accuracy"),
            "classification_calibration_error": classification.get("calibration_error"),
            "classification_total_samples": classification.get("total_samples"),
            "classification_correct_predictions": classification.get("correct_predictions"),
            "extraction_exact_rule_match_rate": extraction.get("exact_rule_match_rate"),
            "extraction_schema_validation_pass_rate": extraction.get("schema_validation_pass_rate"),
            "duplicate_f1": duplicate.get("f1_score"),
            "duplicate_precision": duplicate.get("precision"),
            "duplicate_recall": duplicate.get("recall"),
            "conflict_f1": conflict.get("f1_score"),
            "conflict_precision": conflict.get("precision"),
            "conflict_recall": conflict.get("recall"),
            "average_processing_time_seconds": data.get("average_processing_time_seconds"),
            "acceptance_criteria_passed": 1.0 if data.get("acceptance_criteria_passed") else 0.0,
        }
        metric_rows = []
        for name, value in scalar_metrics.items():
            if value is None:
                continue
            val = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else (1.0 if value else 0.0)
            metric_rows.append(
                EvaluationMetric(
                    metric_id=f"met-{uuid.uuid4().hex[:10]}",
                    evaluation_run_id=evaluation_run_id,
                    metric_name=name,
                    metric_value=val,
                    metric_details=None,
                )
            )

        session = self._session()
        try:
            session.add(run)
            # Flush the parent first so its PK exists before the child FK rows —
            # evaluation_metrics.evaluation_run_id FK depends on the run row, and
            # with explicit PKs (no relationship) flask order is otherwise arbitrary.
            session.flush()
            session.add_all(metric_rows)
            session.commit()
        finally:
            session.close()

        return evaluation_run_id

    # ------------------------------------------------------------------
    #  Promotion — lifecycle recorded in the DB (model_versions.status + audit)
    # ------------------------------------------------------------------

    _ALLOWED_STATUSES = {"CANDIDATE", "APPROVED", "ACTIVE", "ARCHIVED"}

    def promote(self, model_version_id: str, target_status: str, reason: str = "") -> Dict[str, Any]:
        """Promote a model through CANDIDATE -> APPROVED -> ACTIVE -> ARCHIVED.

        Records the transition in the model_versions table (status + updated_at)
        and writes an audit entry so promotion history is queryable in the DB.
        Returns a summary dict.
        """
        target = target_status.upper()
        if target not in self._ALLOWED_STATUSES:
            raise ValueError(f"Invalid status: {target_status}")

        service = self._model_version_service()
        session = self._session()
        try:
            # Fetch current
            from app.db.models.model_version import ModelVersion

            mv = (
                session.query(ModelVersion)
                .filter(ModelVersion.model_version_id == model_version_id)
                .first()
            )
            if not mv:
                raise ValueError(f"Model version not found in DB: {model_version_id}")

            prev = mv.status
            # Validate + apply transition via the service
            updated = service.promote_model(session, model_version_id, target)
            new_status = updated.status

            # Audit record (reuse audit_history table if present)
            self._write_audit(
                session,
                entity_type="model_version",
                entity_id=model_version_id,
                action=f"promote:{prev}->{new_status}",
                reason=reason or f"Promoted {prev} -> {new_status}",
            )
            return {
                "model_version_id": model_version_id,
                "from_status": prev,
                "to_status": new_status,
                "promoted_at": datetime.utcnow().isoformat(),
                "reason": reason,
            }
        finally:
            session.close()

    @staticmethod
    def _write_audit(session, entity_type: str, entity_id: str, action: str, reason: str) -> None:
        """Insert into audit_history if the table/model exists; else no-op."""
        try:
            from app.db.models.audit_history import AuditHistory

            session.add(
                AuditHistory(
                    audit_id=f"aud-{uuid.uuid4().hex[:10]}",
                    # audit_history.workspace_id is a NOT NULL FK to workspaces —
                    # 'default' exists in the seed data, so promotions always land.
                    workspace_id="default",
                    actor_id="rie_pipeline",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    action=action,
                    details={"reason": reason},
                )
            )
            session.commit()
        except Exception as e:
            session.rollback()  # audit is best-effort; never fail the promotion
            print(f"⚠️  Audit write skipped (best-effort): {e}")

    # ------------------------------------------------------------------

    @staticmethod
    def _g(d: Dict[str, Any], section: str, key: str) -> Any:
        return (d.get(section) or {}).get(key)


def main() -> None:
    """CLI smoke: show current DB model/evaluation counts via this module."""
    db = MetricsStorageDB()
    session = db._session()
    from sqlalchemy import text

    try:
        with session.bind.connect() as c:
            print("model_versions:",
                  c.execute(text("SELECT count(*) FROM model_versions")).scalar())
            print("dataset_versions:",
                  c.execute(text("SELECT count(*) FROM dataset_versions")).scalar())
            print("evaluation_runs:",
                  c.execute(text("SELECT count(*) FROM evaluation_runs")).scalar())
            print("evaluation_metrics:",
                  c.execute(text("SELECT count(*) FROM evaluation_metrics")).scalar())
    finally:
        session.close()


if __name__ == "__main__":
    main()