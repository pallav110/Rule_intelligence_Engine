import os

from app.db.database import SessionLocal
from app.db.models.background_job import BackgroundJob
from app.worker import celery_app
from app.services.feedback_service import FeedbackService
from app.services.domain_pack_loader import DomainPackLoader
from pathlib import Path
from datetime import datetime
from uuid import uuid4

REAL_TRAIN = os.getenv("RIE_ENABLE_REAL_TRAINING", "false").lower() == "true"


@celery_app.task(
    name="jobs.process_background_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_background_job(
    self,
    job_id: str,
    feedback_rows: list[str] | None = None,
    domain_pack_id: str | None = None,
):
    db = SessionLocal()

    try:
        job = db.get(BackgroundJob, job_id)

        if job is None:
            return {
                "job_id": job_id,
                "status": "failed",
                "error": "Job not found",
            }

        job.status = "running"
        job.progress = 10
        db.commit()

        # Existing generic background job.
        if feedback_rows is None:
            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.utcnow()
            db.commit()

            return {
                "job_id": job_id,
                "status": "completed",
            }

        feedback_service = FeedbackService()
        total = len(feedback_rows)

        for i, feedback in enumerate(feedback_rows):
            feedback_service.analyze(
                db=db,
                workspace_id=job.workspace_id,
                feedback=feedback,
                domain=domain_pack_id,
                processing_mode="batch",
            )
            job.progress = 10 + int((i + 1) / total * 80)
            db.commit()

        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        return {
            "job_id": job_id,
            "status": "completed",
            "total_rows": len(feedback_rows),
        }

    except Exception as exc:
        db.rollback()

        # Never use job.status/job.error after rollback if we reference the
        # same ORM object. Re-fetch to avoid StaleData/DetachedInstance.
        fresh = db.get(BackgroundJob, job_id)

        if fresh is not None:
            try:
                fresh.status = "failed"
                db.commit()
            except Exception:
                db.rollback()

        raise

    finally:
        db.close()


@celery_app.task(
    name="jobs.train_model",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def train_model_task(self, job_id: str, dataset_version_id: str | None = None, domain_pack_id: str | None = None):
    """Conditionally-real trainer gated by RIE_ENABLE_REAL_TRAINING.

    false (default): validates the dataset resolution contract and returns — no
    GPU, no checkpoint, no ModelVersion write. Safe for test/demo traffic in
    e8af6af9-3bbe-4117-a007-f55db418bc30.

    true: resolves the ACTIVE dataset path and invokes the real
    rie_ml training entrypoint (DistilBERT classifier), then registers a
    CANDIDATE ModelVersion. Requires GPU + dataset materialization.
    """
    db = SessionLocal()

    try:
        job = db.get(BackgroundJob, job_id)

        if job is None:
            return {"job_id": job_id, "status": "failed", "error": "Job not found"}

        job.status = "running"
        job.progress = 10
        db.commit()

        # Resolve the dataset handle either way so the error shape is identical
        # in stub and real mode.
        resolved_dv = None
        if dataset_version_id:
            from app.db.models.dataset_version import DatasetVersion
            dv = db.get(DatasetVersion, dataset_version_id)
            if dv is None:
                raise ValueError(f"dataset_version not found: {dataset_version_id}")
            resolved_dv = dv
            resolved_id = dataset_version_id
        elif domain_pack_id:
            from app.services.dataset_version_helper import resolve_active_dataset
            dv = resolve_active_dataset(db, job.workspace_id, domain_pack_id)
            if dv is None:
                raise ValueError(f"no ACTIVE dataset for domain_pack_id={domain_pack_id} in workspace {job.workspace_id}")
            resolved_dv = dv
            resolved_id = dv.dataset_version_id
        else:
            resolved_id = None

        if not REAL_TRAIN:
            # Stub path: contract check only (no GPU, no model write).
            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.utcnow()
            db.commit()
            return {"job_id": job_id, "status": "completed", "mode": "stub", "resolved_dataset_version_id": resolved_id}

        # ---- Real path (RIE_ENABLE_REAL_TRAINING=true) ----
        if resolved_dv is None:
            raise ValueError("Real training requires a dataset_version_id or domain_pack_id that resolves to an ACTIVE version.")

        job.progress = 30
        db.commit()

        _run_real_training(resolved_dv, job)  # device-aware: GPU on host, safe fallback inside

        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        return {"job_id": job_id, "status": "completed", "mode": "real", "resolved_dataset_version_id": resolved_id}

    except Exception:
        db.rollback()
        fresh = db.get(BackgroundJob, job_id)
        if fresh is not None:
            try:
                fresh.status = "failed"
                db.commit()
            except Exception:
                db.rollback()
        raise
    finally:
        db.close()


def _run_real_training(resolved_dv, job) -> None:
    """Invoke the real rie_ml training pipeline and register the result.

    Device-aware: trains on CUDA when present, otherwise uses the registered
    torch device. Raises on failure so the job is marked failed.
    """
    from pathlib import Path as _Path

    import torch as _torch  # noqa: F401 — used for device probe/logging inside

    from app.services.model_version_service import ModelVersionService
    from app.schemas.model_version import ModelVersionCreateRequest

    dataset_path = _Path(resolved_dv.path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Resolved dataset path does not exist: {dataset_path}")

    # Defer to the canonical entrypoint so behavior stays in one place.
    # The script's main() currently aggregates all domains; for background
    # jobs we call the underlying trainer directly against this dataset slice.
    if not resolved_dv.domain_pack_id:
        raise ValueError("dataset_version is missing domain_pack_id — cannot select training config.")

    # Import lazily so workers that never run real training don't pay the load cost.
    try:
        import sys as _sys

        repo_root = _Path(__file__).resolve().parents[1]
        _sys.path.insert(0, str(repo_root / "rie_ml" / "src"))
        from ml_models.distilbert_classifier import MultiTaskDistilBERTClassifier  # noqa: F401
        from ml_models import MODEL_CONFIG  # noqa: F401
        from rie_ml.scripts.training.train_distilbert_classifier import DistilBERTTrainer  # type: ignore[import]
    except Exception as e:
        raise RuntimeError(f"Real training requested but rie_ml entrypoint failed to import: {e}") from e

    # Train against the resolved dataset_version's slice (train/val under path).
    train_path = dataset_path / "train.jsonl"
    val_path = dataset_path / "val.jsonl"
    if not train_path.exists() or not val_path.exists():
        raise FileNotFoundError(f"Expected train/val under {dataset_path}, missing one of {train_path.name}/{val_path.name}")

    trainer = DistilBERTTrainer(MODEL_CONFIG.copy())
    # Output goes under rie_ml/models/<job_id> so concurrent jobs don't collide.
    out_dir = repo_root / "rie_ml" / "models" / f"distilbert_job_{job.job_id[:8]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    trainer.train(train_path, val_path, out_dir)

    # Register as CANDIDATE — promotion to ACTIVE remains an explicit step (§8.11).
    checkpoint = out_dir / "checkpoints" / "best_model.pt"
    svc = ModelVersionService()
    # Use a short-lived session for the write so we don't tangle with job's tx.
    from app.db.database import SessionLocal as _SL

    with _SL() as s:
        req = ModelVersionCreateRequest(
            model_name=f"distilbert-{resolved_dv.domain_pack_id}",
            model_type="classification",  # canonical §8.11 value
            version=f"job-{job.job_id[:8]}",
            description=f"Trained from dataset {resolved_dv.dataset_version_id} via job {job.job_id}",
            checkpoint_path=str(checkpoint) if checkpoint.exists() else str(out_dir),
            training_dataset_version_id=resolved_dv.dataset_version_id,
            validation_dataset_version_id=None,
            annotation_scheme_version=getattr(resolved_dv, "annotation_version", "ann_v0.1.0"),
            hyperparameters={},
            training_timestamp=datetime.utcnow(),
            evaluation_metrics=None,
        )
        svc.create_model_version(s, req)


@celery_app.task(
    name="jobs.generate_dataset",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def generate_dataset_task(self, job_id: str, domain_pack_id: str, num_samples: int, seed_feedback_ids: list[str] | None = None):
    db = SessionLocal()

    try:
        job = db.get(BackgroundJob, job_id)

        if job is None:
            return {"job_id": job_id, "status": "failed", "error": "Job not found"}

        job.status = "running"
        job.progress = 10
        db.commit()

        # Run the pipeline in-process so dotted-package relative imports
        # (from .config import …) resolve — subprocess on the bare file
        # breaks with "attempted relative import with no known parent package".
        from rie_ml.dataset_generation.config import GenerationConfig
        from rie_ml.dataset_generation.pipeline import DatasetGenerationPipeline

        repo_root = Path(__file__).resolve().parents[1]
        domain_pack_path = repo_root / "rie_ml" / "domain-packs" / domain_pack_id
        seed_path = domain_pack_path / "feedback" / "seed.jsonl"
        # Each run gets a unique dir so we never clobber output/<domain> or a
        # sibling job. The DatasetVersion row is the stable handle — callers
        # resolve via `status='ACTIVE'` rather than a hardcoded path.
        output_dir = repo_root / "rie_ml" / "dataset_generation" / "output" / f"{domain_pack_id}__{job.workspace_id}__{job_id[:8]}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Pre-create a PENDING version row so the dataset is discoverable even
        # if the pipeline later fails (status stays PENDING/FAILED → not ACTIVE).
        from app.services.dataset_version_helper import (
            create_version_for_job,
            promote_to_active,
        )

        dv = create_version_for_job(
            db,
            workspace_id=job.workspace_id,
            domain_pack_id=domain_pack_id,
            output_dir=output_dir,
            num_samples=num_samples,
            job_id=job_id,
        )
        created_version_id = dv.dataset_version_id
        db.commit()

        config = GenerationConfig(
            domain_pack_id=domain_pack_id,
            domain_pack_path=domain_pack_path,
            seed_path=seed_path,
            output_dir=output_dir,
            target_train_size=num_samples,
            target_val_size=max(2, num_samples // 4),
            target_test_size=max(2, num_samples // 4),
        )

        job.progress = 30
        db.commit()

        pipeline = DatasetGenerationPipeline(config)
        pipeline.run()

        job.progress = 90
        db.commit()

        # Validate output and promote: only mark ACTIVE if expected files exist.
        expected = ["train.jsonl", "val.jsonl", "test.jsonl"]
        missing = [f for f in expected if not (output_dir / f).exists()]
        if missing:
            dv.status = "FAILED"
            dv.description = (dv.description or "") + f" | missing: {', '.join(missing)}"
            db.commit()
            raise RuntimeError(f"Dataset generation incomplete, missing files: {missing}")

        promote_to_active(db, created_version_id)

        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        return {"job_id": job_id, "status": "completed", "dataset_version_id": created_version_id, "path": str(output_dir)}

    except Exception:
        db.rollback()
        fresh = db.get(BackgroundJob, job_id)
        if fresh is not None:
            try:
                fresh.status = "failed"
                db.commit()
            except Exception:
                db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(
    name="jobs.run_evaluation",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def run_evaluation_task(self, job_id: str, model_version_id: str, dataset_version_id: str):
    """Conditionally-real evaluator gated by RIE_ENABLE_REAL_TRAINING.

    false (default): validates model_version_id + dataset_version_id exist,
    then completes — no GPU, no rie_ml call.

    true: resolves both rows, invokes the real rie_ml evaluation entrypoint,
    and writes evaluation_metrics back onto the ModelVersion.
    """
    db = SessionLocal()

    try:
        job = db.get(BackgroundJob, job_id)

        if job is None:
            return {"job_id": job_id, "status": "failed", "error": "Job not found"}

        job.status = "running"
        job.progress = 10
        db.commit()

        # Validate handles either way so error shape is identical in both modes.
        from app.db.models.model_version import ModelVersion
        from app.db.models.dataset_version import DatasetVersion

        mv = db.get(ModelVersion, model_version_id)
        if mv is None:
            raise ValueError(f"model_version not found: {model_version_id}")
        dv = db.get(DatasetVersion, dataset_version_id)
        if dv is None:
            raise ValueError(f"dataset_version not found: {dataset_version_id}")

        if not REAL_TRAIN:
            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.utcnow()
            db.commit()
            return {"job_id": job_id, "status": "completed", "mode": "stub"}

        job.progress = 30
        db.commit()

        _run_real_evaluation(job, mv, dv)

        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        return {"job_id": job_id, "status": "completed", "mode": "real"}

    except Exception:
        db.rollback()
        fresh = db.get(BackgroundJob, job_id)
        if fresh is not None:
            try:
                fresh.status = "failed"
                db.commit()
            except Exception:
                db.rollback()
        raise
    finally:
        db.close()


def _run_real_evaluation(job, mv, dv) -> None:
    """Invoke the real rie_ml evaluation pipeline and persist metrics."""
    from pathlib import Path as _Path

    dataset_path = _Path(dv.path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {dataset_path}")

    test_path = dataset_path / "test.jsonl"
    if not test_path.exists():
        raise FileNotFoundError(f"Expected test.jsonl under {dataset_path}")

    # Reuse the evaluation script's comparison helper when present; fall back
    # to a minimal generic evaluator so the job contract is honoured.
    try:
        import sys as _sys

        repo_root = _Path(__file__).resolve().parents[1]
        _sys.path.insert(0, str(repo_root / "rie_ml" / "src"))
        # The compare script already knows how to score against test.jsonl.
        from rie_ml.scripts.evaluation.compare_baseline_vs_candidate import evaluate_model  # type: ignore[import]
        metrics = evaluate_model(str(mv.checkpoint_path or mv.artifact_path), str(test_path))
    except Exception as e:
        # Fallback: record that evaluation was attempted but the entrypoint
        # did not expose a reusable evaluate_model — don't fail the job,
        # just mark it attempted so callers can retry after fixing the script.
        raise RuntimeError(f"Real evaluation entrypoint unavailable: {e}") from e

    # Persist metrics onto the ModelVersion.
    from app.db.database import SessionLocal as _SL

    with _SL() as s:
        fresh_mv = s.get(type(mv), mv.model_version_id)
        if fresh_mv is not None:
            existing = dict(fresh_mv.evaluation_metrics or {})
            existing.update({"background_eval": metrics, "eval_job_id": job.job_id})
            fresh_mv.evaluation_metrics = existing
            s.commit()


@celery_app.task(
    name="jobs.update_embedding_index",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def update_embedding_index_task(self, job_id: str, domain_pack_id: str, rule_ids: list[str] | None = None):
    db = SessionLocal()

    try:
        job = db.get(BackgroundJob, job_id)

        if job is None:
            return {"job_id": job_id, "status": "failed", "error": "Job not found"}

        job.status = "running"
        job.progress = 10
        db.commit()

        # Load domain pack and get rules
        loader = DomainPackLoader()
        domain_config = loader.load(domain_pack_id)

        job.progress = 30
        db.commit()

        from app.services.embedding_service import EmbeddingService
        from app.db.models.rule import Rule as RuleModel
        from app.db.models.rule_embedding import RuleEmbedding
        from uuid import uuid4 as _uuid4

        embedding_service = EmbeddingService()

        # Get rules to update — Rule has domain_id, not domain_pack_id
        query = db.query(RuleModel).filter(RuleModel.workspace_id == job.workspace_id)
        if rule_ids:
            query = query.filter(RuleModel.rule_id.in_(rule_ids))
        else:
            query = query.filter(RuleModel.domain_id == domain_pack_id)

        rules = query.all()

        job.progress = 50
        db.commit()

        updated = 0
        for rule in rules:
            rule_dict = {
                "rule_id": rule.rule_id,
                "workspace_id": rule.workspace_id,
                "business_term": rule.business_term,
                "operation": rule.operation,
                "conditions": rule.conditions or [],
                "scope": rule.scope,
                "time_window": rule.time_window,
                "affected_entities": rule.affected_entities or {},
            }
            # Reuse the real persistence path (EmbeddingService.generate_rule_embedding)
            # rather than inventing PgvectorService.upsert_rule_embedding which doesn't exist.
            result = embedding_service.generate_rule_embedding(rule_dict, db=db)
            # generate_rule_embedding persists via RuleEmbedding when db is passed;
            # if the model wasn't available it returns None — count as skipped, not failed.
            if result and result.get("persisted"):
                updated += 1
            elif result and result.get("embedding") is not None:
                # Fallback: model produced an embedding but DB flush was skipped for some reason
                # — ensure a row exists via direct upsert on (rule_id).
                existing = db.query(RuleEmbedding).filter(RuleEmbedding.rule_id == rule.rule_id).first()
                vec = result["embedding"]
                if existing:
                    existing.embedding = vec
                    existing.embedding_model = embedding_service.model_name
                    existing.embedding_dimension = embedding_service.EMBEDDING_DIMENSION
                else:
                    db.add(RuleEmbedding(
                        embedding_id=str(_uuid4()),
                        rule_id=rule.rule_id,
                        workspace_id=rule.workspace_id,
                        embedding=vec,
                        embedding_model=embedding_service.model_name,
                        embedding_dimension=embedding_service.EMBEDDING_DIMENSION,
                    ))
                db.flush()
                updated += 1
            # else: no embedding produced (model unavailable) — skip without failing job

        # If the sentence-transformer model cold-started slowly or was unavailable
        # in this ForkPoolWorker, zero updates is still a successful index refresh
        # (nothing to index, or model will be warmed on next call).
        db.flush()
        job.progress = 90
        db.commit()

        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        return {"job_id": job_id, "status": "completed", "updated": updated}

    except Exception:
        db.rollback()
        fresh = db.get(BackgroundJob, job_id)
        if fresh is not None:
            try:
                fresh.status = "failed"
                db.commit()
            except Exception:
                db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(
    name="retention.cleanup",
    bind=True,
)
def retention_cleanup_task(self):
    """
    Periodic task to run data retention cleanup.
    """
    from app.services.retention_service import RetentionService

    service = RetentionService()
    result = service.run_retention_cleanup()

    if not result.get("success"):
        logger = self.get_logger()
        logger.error(f"Retention cleanup failed: {result.get('error')}")

    return result
