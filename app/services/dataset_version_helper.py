"""Helper for dataset version lifecycle.

Scalable approach:
- Each generate_dataset run creates a DatasetVersion row whose path is the
  job-scoped output dir (rie_ml/dataset_generation/output/<uuid>).
- One version per (workspace_id, domain_pack_id) can be ACTIVE; promotion
  archives the previous ACTIVE. Training always resolves ACTIVE via DB, never
  via a hardcoded filesystem path.
- Legacy rows without workspace_id remain readable (global seed datasets).

This avoids the trap where successive generates either clobber
output/ecommerce or spawn orphaned folders the user must wire manually.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models.dataset_version import DatasetVersion
from app.services.domain_pack_loader import DomainPackLoader


def next_dataset_version(db: Session, workspace_id: str | None, domain_pack_id: str) -> str:
    """Monotonic per-(workspace,domain) version: v0.1.0, v0.2.0, …"""
    q = db.query(DatasetVersion).filter(DatasetVersion.domain_pack_id == domain_pack_id)
    if workspace_id:
        q = q.filter(
            (DatasetVersion.workspace_id == workspace_id)
            | (DatasetVersion.workspace_id.is_(None))  # include legacy globals in max
        )
    # Pull existing versions that look like vX.Y.Z — fall back to 0.1.0
    max_minor = 0
    for (v,) in q.with_entities(DatasetVersion.version).all():
        try:
            # expect v0.N.0
            parts = v.lstrip("v").split(".")
            if len(parts) >= 2:
                minor = int(parts[1])
                max_minor = max(max_minor, minor)
        except Exception:
            continue
    return f"v0.{max_minor + 1}.0"


def create_version_for_job(
    db: Session,
    *,
    workspace_id: str,
    domain_pack_id: str,
    output_dir: Path,
    num_samples: int,
    job_id: str,
) -> DatasetVersion:
    loader = DomainPackLoader()
    try:
        cfg = loader.load(domain_pack_id)
        domain_version = cfg.get("version", "unknown")
        annotation_version = cfg.get("annotation_version", "ann_v0.1.0")
    except Exception:
        domain_version = "unknown"
        annotation_version = "ann_v0.1.0"

    version = next_dataset_version(db, workspace_id, domain_pack_id)
    # dataset_name encodes scope so the (dataset_name, version) unique
    # constraint naturally shards by workspace+domain without a new index.
    dataset_name = f"{domain_pack_id}__{workspace_id}__generated"

    dv = DatasetVersion(
        dataset_version_id=f"dsv-{uuid4().hex[:10]}",
        dataset_name=dataset_name,
        version=version,
        domain_pack_id=domain_pack_id,
        domain_pack_version=domain_version,
        annotation_version=annotation_version,
        source="generated",
        path=str(output_dir),
        status="PENDING",
        workspace_id=workspace_id,
        num_samples=num_samples,
        description=f"Generated via background job {job_id} ({num_samples} samples)",
    )
    db.add(dv)
    db.flush()
    return dv


def promote_to_active(db: Session, dataset_version_id: str) -> DatasetVersion:
    """Set this version to ACTIVE and archive any previous ACTIVE in the same scope."""
    dv = db.get(DatasetVersion, dataset_version_id)
    if dv is None:
        raise ValueError(f"dataset_version not found: {dataset_version_id}")
    # Archive siblings
    siblings = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.domain_pack_id == dv.domain_pack_id,
            DatasetVersion.workspace_id == dv.workspace_id,
            DatasetVersion.status == "ACTIVE",
            DatasetVersion.dataset_version_id != dv.dataset_version_id,
        )
        .all()
    )
    for s in siblings:
        s.status = "ARCHIVED"
    dv.status = "ACTIVE"
    db.flush()
    return dv


def resolve_active_dataset(db: Session, workspace_id: str, domain_pack_id: str) -> DatasetVersion | None:
    """Return the ACTIVE dataset for this workspace+domain, or None."""
    return (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.workspace_id == workspace_id,
            DatasetVersion.domain_pack_id == domain_pack_id,
            DatasetVersion.status == "ACTIVE",
        )
        .order_by(DatasetVersion.created_at.desc())
        .first()
    )
