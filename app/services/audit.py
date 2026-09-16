"""Audit-trail writer for Spec §6.6 / §10.11 (complete auditability).

`audit_history` is the immutable record the spec requires for feedback
submission, suggestion generation, review decisions, rule creation/activation,
status changes and API access. This module centralizes the write so every
producer emits the same shape (`audit_id`, `entity_type`, `entity_id`, `action`,
`performed_by`/`actor_id`, `timestamp`).

Auditing is deliberately BEST-EFFORT: a failure to record an audit row must
never turn a successful business operation into a 500, and must never be the
reason an auth decision changes. Errors are logged and swallowed.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


def write_audit(
    db,
    workspace_id: Optional[str],
    action: str,
    entity_type: str,
    entity_id: str,
    actor_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    commit: bool = False,
) -> Optional[str]:
    """Append one row to `audit_history`. Returns the audit_id, or None on failure.

    `commit=True` commits immediately (use when called outside a request's
    business transaction, e.g. from middleware or an error path).
    """
    from app.db.models.audit_history import AuditHistory

    def _row(ws: Optional[str]) -> "AuditHistory":
        return AuditHistory(
            audit_id=f"aud-{uuid.uuid4().hex[:10]}",
            workspace_id=ws,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )

    try:
        row = _row(workspace_id)
        db.add(row)
        if commit:
            db.commit()
        return row.audit_id
    except Exception as e:  # never let auditing break the operation
        # §10.10 Prometheus: count DB errors (best-effort, never alters behavior)
        try:
            from app.observability import DB_ERRORS  # type: ignore

            if DB_ERRORS is not None:
                DB_ERRORS.labels(operation="audit.write").inc()  # type: ignore[union-attr]
        except Exception:
            pass
        # A failed login may name a workspace that does not exist -> FK violation.
        # Such an event is exactly what we must record, so retry tenant-less.
        try:
            db.rollback()
            if workspace_id:
                row = _row(None)
                db.add(row)
                if commit:
                    db.commit()
                return row.audit_id
        except Exception as e2:
            logger.warning("audit write failed (action=%s entity=%s): %s / %s", action, entity_type, e, e2)
            try:
                db.rollback()
            except Exception:
                pass
        else:
            logger.warning("audit write failed (action=%s entity=%s): %s", action, entity_type, e)
        return None


def write_auth_event(
    action: str,
    path: str,
    status_code: int,
    workspace_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Record an authentication/authorization outcome in its own session.

    Separate session because middleware and FastAPI dependencies do not share
    the request's business session. Best-effort; never raises.
    """
    db = None
    try:
        from app.db.database import SessionLocal

        db = SessionLocal()
        return write_audit(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            entity_type="api_access",
            entity_id=path,
            details={**(details or {}), "status_code": status_code, "path": path},
            commit=True,
        )
    except Exception as e:
        logger.warning("audit auth-event write failed (%s %s): %s", action, path, e)
        return None
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
