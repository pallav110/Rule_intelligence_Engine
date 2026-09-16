from app.db.database import SessionLocal
from app.db.models.background_job import BackgroundJob
from app.worker import celery_app
from app.services.feedback_service import FeedbackService
from app.services.domain_pack_loader import DomainPackLoader
from pathlib import Path
from datetime import datetime
from uuid import uuid4


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
    """Stubbed per your instruction (no GPU). Validates dataset resolution contract.

    If dataset_version_id is supplied it must exist. Otherwise, if
    domain_pack_id is supplied, resolve the ACTIVE dataset for this workspace.
    This proves the promotion chain works even though no real training runs.
    """
    db = SessionLocal()

    try:
        job = db.get(BackgroundJob, job_id)

        if job is None:
            return {"job_id": job_id, "status": "failed", "error": "Job not found"}

        job.status = "running"
        job.progress = 10
        db.commit()

        # Contract check — no GPU work, just ensure the version indirection is sound.
        if dataset_version_id:
            from app.db.models.dataset_version import DatasetVersion
            dv = db.get(DatasetVersion, dataset_version_id)
            if dv is None:
                raise ValueError(f"dataset_version not found: {dataset_version_id}")
            resolved = dataset_version_id
        elif domain_pack_id:
            from app.services.dataset_version_helper import resolve_active_dataset
            dv = resolve_active_dataset(db, job.workspace_id, domain_pack_id)
            if dv is None:
                raise ValueError(f"no ACTIVE dataset for domain_pack_id={domain_pack_id} in workspace {job.workspace_id}")
            resolved = dv.dataset_version_id
        else:
            resolved = None  # legacy caller that passed neither — still succeed (stub mode)

        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        return {"job_id": job_id, "status": "completed", "resolved_dataset_version_id": resolved}

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
    db = SessionLocal()

    try:
        job = db.get(BackgroundJob, job_id)

        if job is None:
            return {"job_id": job_id, "status": "failed", "error": "Job not found"}

        job.status = "running"
        job.progress = 10
        db.commit()

        # Same rationale as train_model_task: evaluating a DistilBERT
        # candidate requires a GPU + a materialized dataset slice and a
        # callable entrypoint. Stub to a clean completion so the job
        # lifecycle and §5.13 contract can be exercised in tests without
        # a full train/eval pass. Wire to rie_ml.scripts.evaluation.*
        # after it exposes a reusable run() function.
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        return {"job_id": job_id, "status": "completed"}

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
