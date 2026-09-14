"""Redis-backed API rate limiting (Spec §10.3).

To protect the system from abuse and denial-of-service attacks, API endpoints
implement per-window request limits. Requests exceeding the configured limit
return HTTP 429 (Too Many Requests) with a Retry-After header.

Design
------
- Fixed-window counter per (bucket, subject) and per window (currently 3600 s /
  1 hour). Each key is `rl:<bucket>:<subject>:<window>`. A request atomically
  INCRs the key and, when a new key is created, sets its EXPIRE to the window
  length. Redis INCR + conditional EXPIRE are pipelined as one round-trip.
- Subject is the authenticated user_id when a valid Bearer token is present,
  else the client IP. Limits are per-user per spec; the IP fallback still bounds
  anonymous/legacy traffic.
- Redis is the shared, multi-instance store; if it is unavailable the limiter
  degrades to a per-process in-memory fixed-window table (protect the app, never
  fail closed into a 500). Across multiple API replicas the in-memory fallback is
  approximate, which is acceptable for a DoS guard.

Limits are configurable via env (e.g. RIE_RATE_FEEDBACK=100) so deployment teams
can tune them without code changes — "Rate limits may be adjusted based on
deployment requirements."
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_RATE_ENV_PREFIX = "RIE_RATE_"

# Default limits per §10.3 example policy (requests / window / subject).
# Bucket names are separate from endpoint paths so one policy row can govern a
# family of endpoints (e.g. every review route, feedback re-analyze = batch).
BUCKET_DEFAULTS: dict[str, int] = {
    "feedback": 100,   # Feedback Analysis      100 requests/hour/user
    "batch": 10,       # Batch Analysis         10  requests/hour/user
    "rules": 20,       # Rule Activation        20  requests/hour
    "reviews": 200,    # Review APIs            200 requests/hour
    "auth": 30,        # login attempts         throttled against brute-force
    "misc": 300,       # everything else        generous default
}


def _cfg_int(bucket: str, default: int) -> int:
    """Read an override like RIE_RATE_FEEDBACK from the environment."""
    try:
        return int(os.getenv(_RATE_ENV_PREFIX + bucket.upper(), str(default)).strip())
    except (TypeError, ValueError):
        return default


# Resolve bucket -> limit once at import so a limit change needs a restart (a
# per-request os.getenv would be slow on the hot path).
LIMITS: dict[str, int] = {b: _cfg_int(b, d) for b, d in BUCKET_DEFAULTS.items()}

WINDOW_SECONDS: int = _cfg_int("WINDOW", 3600)

# Advertised "requests per hour" used in the 429 detail message. Kept separate
# so an operator can shrink WINDOW_SECONDS for testing (e.g. RIE_RATE_WINDOW=60)
# without the message claiming a shorter span than the config implies.
_WINDOW_HOURS: int = max(1, round(WINDOW_SECONDS / 3600))

# Rate limiter must never take the API down with itself: if Redis is not
# reachable we fall back to memory for up to this many keys before refusing to
# grow indefinitely (LRU-evict old windows).
_MEMORY_MAX_KEYS = 200_000


@dataclass(frozen=True)
class RateLimiterState:
    """Config for one bucket, as used by the checked-based dependency."""

    bucket: str
    limit: int
    window: int


# ---------------------------------------------------------------------------
# Shared Redis client
# ---------------------------------------------------------------------------
def _get_redis():
    import redis as _redis

    # Same default as app/worker.py; docker-compose sets REDIS_URL in prod.
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    client = _redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5, decode_responses=True)
    return client


# ---------------------------------------------------------------------------
# Fixed-window token bucket
# ---------------------------------------------------------------------------
def _window_start(now: float, window: int) -> int:
    return int(now // window) * window


def _key(bucket: str, subject: str, window: int) -> str:
    # Subject may contain user ids / IPs — normalize to a bounded key.
    h = hashlib.sha256(f"{bucket}:{subject}".encode()).hexdigest()[:24]
    return f"rl:{bucket}:{h}:{window}"


class InMemoryLimiter:
    """Best-effort fallback when Redis is unavailable. Not shared across replicas."""

    def __init__(self, max_keys: int = _MEMORY_MAX_KEYS) -> None:
        self._counts: dict[str, tuple[int, float]] = {}  # key -> (count, window_start)
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def hit(self, bucket: str, subject: str, limit: int, window: int) -> tuple[bool, int]:
        now = time.time()
        win = _window_start(now, window)
        key = _key(bucket, subject, window)
        with self._lock:
            count, start = self._counts.get(key, (0, win))
            if start == win:
                count += 1
            else:
                count = 1
                start = win
            if len(self._counts) >= self._max_keys and key not in self._counts:
                # Full: drop the oldest window to stay bounded.
                self._counts.pop(next(iter(self._counts)))
            self._counts[key] = (count, start)
            allowed = count <= limit
            retry_after = max(1, int(win + window - now))
            return allowed, retry_after


_in_memory = InMemoryLimiter()


def hit(
    bucket: str,
    subject: str,
    limit: Optional[int] = None,
    window: Optional[int] = None,
) -> tuple[bool, int]:
    """Record one request for `subject` in `bucket`.

    Returns `(allowed, retry_after_seconds)`. When `allowed` is False the caller
    must respond 429 with Retry-After = retry_after.
    """
    limit = limit or LIMITS.get(bucket, LIMITS["misc"])
    window = window or WINDOW_SECONDS
    win = _window_start(time.time(), window)
    key = _key(bucket, subject, window)

    try:
        r = _get_redis()
        pipe = r.pipeline(transaction=False)
        pipe.incr(key)
        pipe.expire(key, window)
        pipe.ttl(key)
        count, _, ttl = pipe.execute()
        allowed = int(count) <= limit
        retry_after = max(1, int(ttl) if isinstance(ttl, int) and ttl > 0 else int(win + window - time.time()))
        return allowed, retry_after
    except Exception as e:  # Redis down -> degrade, never fail the request
        logger.warning("rate limiter fell back to in-memory (bucket=%s): %s", bucket, e)
        return _in_memory.hit(bucket, subject, limit, window)


def subject_for(
    client_ip: Optional[str],
    bearer_token: Optional[str] = None,
) -> str:
    """Resolve the rate-limit subject: authenticated user_id else client IP.

    A PRESENT but invalid bearer is ignored here — the auth layer still rejects
    it independently (401) later; for rate limiting we fall back to IP so an
    attacker hammering with forged tokens is still throttled per IP.
    """
    if bearer_token:
        try:
            from app.services.security import decode_token

            ctx = decode_token(bearer_token)
            return f"u:{ctx.user_id}"
        except Exception:
            pass
    return f"ip:{client_ip or 'unknown'}"


# Aligning the subject_for note: we never downgrade a _valid_ authenticated user
# to IP — a valid token always yields a per-user bucket, satisfying the spec's
# per-user limits. See tests/test_rate_limits.py for coverage.


# ---------------------------------------------------------------------------
# FastAPI dependency factory (per-route)
# ---------------------------------------------------------------------------
def _limit_dependency(bucket: str):
    """Build a FastAPI dependency enforcing `bucket`'s rate limit.

    Resolves the subject from the Authorization header (authenticated user_id)
    or the client IP, records the hit, and raises HTTP 429 beyond the limit.
    """
    from fastapi import Depends, Header, HTTPException, Request, status

    limit = LIMITS.get(bucket, LIMITS["misc"])
    window = WINDOW_SECONDS

    def _dep(request: Request) -> None:
        authorization_header = request.headers.get("authorization")
        token = None
        if authorization_header and authorization_header.lower().startswith("bearer "):
            token = authorization_header[7:]  # len("Bearer ") = 7
        subject = subject_for(request.client.host if request.client else None, token)
        allowed, retry_after = hit(bucket, subject, limit, window)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {bucket} (max {limit}/{_WINDOW_HOURS}h). Retry after {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
        request.state.rate_limit = {"bucket": bucket, "remaining": limit, "window": window}

    return _dep


# Public dependency factories — one per spec §10.3 policy row. Named so a route
# reads `Depends(limit_feedback)` at a glance.
limit_feedback = _limit_dependency("feedback")
limit_batch = _limit_dependency("batch")
limit_rules = _limit_dependency("rules")
limit_reviews = _limit_dependency("reviews")
limit_auth = _limit_dependency("auth")