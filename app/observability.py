"""Prometheus metrics + structured logging + Sentry bridge (Spec §10.10).

Everything here is opt-in and import-safe when the optional deps are absent:
- prometheus_client required for /metrics; module is a thin shim when absent.
- Sentry only initialises if RIE_SENTRY_DSN or SENTRY_DSN is set and
  sentry-sdk is installed; import failure is swallowed.
- Structured JSON log lines are emitted via Python logging regardless.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

_LOG = logging.getLogger("rie.observability")

# ── Structured logging helpers ─────────────────────────────────────

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
        }
        for k in ("request_id", "workspace_id", "actor", "route", "status_code", "duration_ms"):
            v = getattr(record, k, None)
            if v is not None:
                payload[k] = v
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Allow callers to attach arbitrary structured fields via extra={"extra": {...}}
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _install_json_handler_if_requested() -> None:
    """If RIE_LOG_FORMAT=json, replace the root handlers' formatter."""
    mode = (os.getenv("RIE_LOG_FORMAT") or os.getenv("LOG_FORMAT") or "").strip().lower()
    if mode != "json":
        return
    fmt = JsonFormatter()
    root = logging.getLogger()
    for h in root.handlers:
        try:
            h.setFormatter(fmt)
        except Exception:
            pass
    # If somehow there were no handlers, add one.
    if not root.handlers:
        h = logging.StreamHandler()
        h.setFormatter(fmt)
        root.addHandler(h)


# ── Prometheus shim ───────────────────────────────────────────────

_PROM_AVAILABLE = False
try:
    from prometheus_client import Counter, Histogram, Gauge, CONTENT_TYPE_LATEST, generate_latest  # type: ignore

    _PROM_AVAILABLE = True
except Exception:
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"  # type: ignore

    def generate_latest(*_a, **_kw):  # type: ignore
        return b"# prometheus_client not installed; set prometheus_client in requirements\n"

    # lightweight no-op fallbacks so instrumentation sites don't branch
    class _NoopMetric:  # type: ignore
        def labels(self, *a, **kw): return self
        def inc(self, *a, **kw): pass
        def observe(self, *a, **kw): pass
        def set(self, *a, **kw): pass

    Counter = Histogram = Gauge = lambda *a, **kw: _NoopMetric()  # type: ignore

if _PROM_AVAILABLE:
    REQUEST_COUNTER = Counter(
        "rie_http_requests_total",
        "Total HTTP requests",
        labelnames=("method", "route", "status"),
    )
    REQUEST_DURATION = Histogram(
        "rie_http_request_duration_seconds",
        "HTTP request duration",
        labelnames=("method", "route"),
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
    )
    FEEDBACK_ANALYSES = Counter(
        "rie_feedback_analyses_total",
        "Feedback analyses completed",
        labelnames=("domain", "mode"),
    )
    BACKGROUND_JOBS = Counter(
        "rie_background_jobs_total",
        "Background jobs by type and outcome",
        labelnames=("job_type", "outcome"),
    )
    ACTIVE_JOBS = Gauge(
        "rie_background_jobs_active",
        "Background jobs currently running",
        labelnames=("job_type",),
    )
    DB_ERRORS = Counter(
        "rie_db_errors_total",
        "Database errors by operation",
        labelnames=("operation",),
    )
    AUTH_FAILURES = Counter(
        "rie_auth_failures_total",
        "Authentication / authorization failures",
        labelnames=("reason",),
    )
else:  # no-op singletons so callers can unconditionally use them
    REQUEST_COUNTER = REQUEST_DURATION = FEEDBACK_ANALYSES = BACKGROUND_JOBS = ACTIVE_JOBS = DB_ERRORS = AUTH_FAILURES = Counter()  # type: ignore


def metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST  # type: ignore


def metrics_payload() -> bytes:
    return generate_latest()  # type: ignore


# ── Sentry bridge ─────────────────────────────────────────────────

def init_sentry(app_name: str = "rule-intelligence-engine") -> bool:
    """Initialise Sentry if a DSN is configured and the SDK is installed.

    Uses the FastAPI integration when available. Returns True if enabled.
    Safe to call multiple times (re-entrant guard via attribute).
    """
    if getattr(init_sentry, "_done", False):  # type: ignore[attr-defined]
        return bool(getattr(init_sentry, "_enabled", False))  # type: ignore[attr-defined]
    init_sentry._done = True  # type: ignore[attr-defined]
    dsn = (os.getenv("RIE_SENTRY_DSN") or os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        init_sentry._enabled = False  # type: ignore[attr-defined]
        return False
    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration  # type: ignore

        env = (os.getenv("RIE_ENV") or os.getenv("ENVIRONMENT") or os.getenv("ENV") or "production").strip() or "production"
        try:
            sentry_sdk.init(
                dsn=dsn,
                environment=env,
                traces_sample_rate=float(os.getenv("RIE_SENTRY_TRACES_SAMPLE_RATE", "0.0") or 0.0),
                send_default_pii=False,
                integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            )
        except TypeError:
            # older SDK without new kwargs
            sentry_sdk.init(dsn=dsn, environment=env)
        _LOG.info("Sentry enabled (env=%s)", env)
        init_sentry._enabled = True  # type: ignore[attr-defined]
        return True
    except ModuleNotFoundError:
        _LOG.warning("RIE_SENTRY_DSN is set but sentry-sdk is not installed; Sentry disabled")
    except Exception as e:  # pragma: no cover
        _LOG.warning("Sentry init failed: %s", e)
    init_sentry._enabled = False  # type: ignore[attr-defined]
    return False


def capture_exception(exc: BaseException, **context: Any) -> None:
    """Forward to Sentry when enabled; always logs."""
    try:
        _LOG.exception("unhandled exception: %s", exc, extra={"extra": context} if context else None)
    except Exception:
        pass
    try:
        import sentry_sdk  # type: ignore

        if getattr(sentry_sdk, "Hub", None) and getattr(sentry_sdk.Hub, "current", None):  # type: ignore
            with sentry_sdk.push_scope() as scope:  # type: ignore[attr-defined]
                for k, v in context.items():
                    scope.set_extra(k, v)
                sentry_sdk.capture_exception(exc)
        else:
            import sentry_sdk as _s

            _s.capture_exception(exc)
    except Exception:
        pass


# ── Celery helpers ────────────────────────────────────────────────

def note_job_active(job_type: str, delta: int) -> None:
    """Bump ACTIVE_JOBS gauge when available."""
    try:
        if delta > 0:
            ACTIVE_JOBS.labels(job_type=job_type).inc(delta)  # type: ignore
        elif delta < 0:
            ACTIVE_JOBS.labels(job_type=job_type).inc(delta)  # type: ignore
    except Exception:
        pass


def note_job_done(job_type: str, outcome: str) -> None:
    try:
        BACKGROUND_JOBS.labels(job_type=job_type, outcome=outcome).inc()  # type: ignore
    except Exception:
        pass
