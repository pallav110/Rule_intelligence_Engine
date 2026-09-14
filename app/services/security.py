"""Security primitives for JWT authentication + RBAC (Spec §10.1, §10.2, §5.1).

Implements the authentication boundary that was previously only a workspace-routing
hint (`extract_workspace_from_context` decoded a JWT with verify_signature=False).
Here the token is actually VERIFIED (HS256 signature + exp), the caller is resolved
to a role, and every operation is scoped to the workspace membership that issued
the token.

Passwords: salted PBKDF2 via the stdlib (no new dependency), never stored/compared
in plaintext. Format:
    pbkdf2$sha256$<iterations>$<salt_hex>$<hash_hex>

JWTs: HS256 (HMAC-SHA256 over base64url header.payload), signed with the stdlib
`hmac`/`hashlib`/`base64` — deliberately NOT `import jwt`, because the venv ships
`jwt==1.4.0`, a different/shadowed package (a `JWT()` class) with no module-level
encode/decode. A stdlib implementation needs no dependency and emits standard
compact JWT tokens any real PyJWT could also verify.

Role model (least-privilege, Spec §10.1 / §10.11):
    business_user  -> submit feedback, view own suggestions, respond to clarifications
    reviewer       -> additionally approve / reject / request clarification
    administrator  -> additionally activate rules, manage datasets/models/config
Roles are strict levels: a role grants everything at or below its level, so a
>reviewer guard admits both reviewer and administrator.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_INSECURE_DEFAULT_SECRET = "rie-dev-insecure-secret-change-me"
# An empty/whitespace RIE_JWT_SECRET counts as UNSET — otherwise a set-but-empty
# var would silently become an empty signing key.
SECRET_KEY: str = (os.getenv("RIE_JWT_SECRET") or "").strip() or _INSECURE_DEFAULT_SECRET

# Which environment are we? Production MUST NOT run on the well-known default
# secret — anyone could forge a token for any user/role/workspace (§10.1).
# `ENV` is included because docker-compose.yml sets it to "production".
_ENV = (
    os.getenv("RIE_ENV") or os.getenv("ENVIRONMENT") or os.getenv("ENV") or "development"
).strip().lower()
_IS_PRODUCTION = _ENV in ("production", "prod")

if SECRET_KEY == _INSECURE_DEFAULT_SECRET:
    if _IS_PRODUCTION:
        raise RuntimeError(
            "RIE_JWT_SECRET must be set to a strong, unique value in production "
            f"(RIE_ENV={_ENV!r}). Refusing to start with the built-in development "
            "secret: tokens would be forgeable, breaking §10.1 authentication."
        )
    # Dev/test: boot without config, but say so loudly. Matches the repo's
    # no-config style (DATABASE_URL defaults the same way in app/db/database.py).
    import warnings

    warnings.warn(
        f"RIE_JWT_SECRET not set; using an insecure development secret "
        f"(RIE_ENV={_ENV!r}). Set RIE_JWT_SECRET before deploying."
    )

if _IS_PRODUCTION and len(SECRET_KEY) < 32:
    raise RuntimeError(
        f"RIE_JWT_SECRET is too short ({len(SECRET_KEY)} chars) for production; "
        "use at least 32 characters of random data."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_TTL: int = int(os.getenv("RIE_TOKEN_TTL", "86400"))  # 24h

_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16


class Role(str, Enum):
    BUSINESS_USER = "business_user"
    REVIEWER = "reviewer"
    ADMINISTRATOR = "administrator"


# Strict hierarchy: a higher role inherits every lower role's permissions.
ROLE_LEVEL: dict[Role, int] = {
    Role.BUSINESS_USER: 1,
    Role.REVIEWER: 2,
    Role.ADMINISTRATOR: 3,
}


@dataclass(frozen=True)
class SecurityContext:
    """Resolved identity + effective workspace role for an authenticated request."""

    user_id: str
    email: str
    workspace_id: str
    role: str

    @property
    def role_level(self) -> int:
        return ROLE_LEVEL.get(Role(self.role), 0)


# ---------------------------------------------------------------------------
# Password hashing (stdlib PBKDF2)
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a password with a fresh random salt (PBKDF2-HMAC-SHA256)."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2$sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time comparison of a candidate password against a stored hash."""
    try:
        scheme, hash_name, iterations, salt_hex, hash_hex = stored.split("$")
        if scheme != "pbkdf2" or hash_name != "sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        digest = hashlib.pbkdf2_hmac(hash_name, password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(digest, expected)
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# JWT issuance + verification (HS256 via stdlib)
# ---------------------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    # Re-pad base64url to a multiple of 4 before decoding.
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def create_access_token(
    user_id: str,
    email: str,
    workspace_id: str,
    role: str,
    expires_in: int = ACCESS_TOKEN_TTL,
) -> str:
    """Issue a signed HS256 access token carrying role + workspace claims."""
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": email,
        "workspace_id": workspace_id,
        "role": role,
        "token_type": "access",
        "iat": now,
        "exp": now + expires_in,
    }
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")) + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    )
    signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return signing_input + "." + _b64url(signature)


def decode_token(token: str) -> SecurityContext:
    """Verify the HS256 signature + expiry and return the resolved context.

    Raises HTTPException(401) on an invalid/forged/expired token (Spec §5.1/§5.19).
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed authentication token")

    signing_input = parts[0] + "." + parts[1]
    try:
        signature = _b64url_decode(parts[2])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed authentication token")
    try:
        signing_bytes = signing_input.encode("ascii")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed authentication token")
    expected = hmac.new(SECRET_KEY.encode("utf-8"), signing_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token signature")

    try:
        claims = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token payload")

    if claims.get("token_type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    if claims.get("role") not in ROLE_LEVEL:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown role in token")
    if int(claims.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    if not claims.get("sub") or not claims.get("workspace_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing required claims")

    return SecurityContext(
        user_id=claims["sub"],
        email=claims.get("email", ""),
        workspace_id=claims["workspace_id"],
        role=claims["role"],
    )


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
def get_security_context(authorization: Optional[str] = Header(default=None)) -> SecurityContext:
    """Require a valid Bearer token. 401 when missing/invalid (Spec §5.1)."""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token")
    if not authorization.upper().startswith("BEARER "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization scheme")
    token = authorization[7:].strip()
    return decode_token(token)


def optional_security_context(authorization: Optional[str] = Header(default=None)) -> Optional[SecurityContext]:
    """Return the authenticated context when a Bearer token is present.

    Unlike get_security_context, a MISSING token is not an error — callers use
    this to keep the unauthenticated (legacy dashboard/smoke) submission path
    working while still enforcing §10.2 workspace isolation when a token IS
    supplied. A PRESENT but invalid token is still a 401 (we never silently
    downgrade an authenticated attempt to anonymous).
    """
    if not authorization:
        return None
    if not authorization.upper().startswith("BEARER "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization scheme")
    token = authorization[7:].strip()
    return decode_token(token)


def require_role(*roles: Role):
    """Dependency factory: require the caller to hold at least one of `roles`.

    403 when the authenticated user's role does not grant any allowed role.
    Composes with get_security_context via Depends(factory)(ctx).
    """
    allowed_level = max(ROLE_LEVEL[r] for r in roles)

    def _dep(ctx: SecurityContext = Depends(get_security_context)) -> SecurityContext:
        if ctx.role_level < allowed_level:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role for this operation")
        return ctx

    return _dep


def require_workspace(workspace_id: str, ctx: SecurityContext) -> SecurityContext:
    """Enforce Spec §10.2 workspace isolation.

    The operation's target workspace must equal the workspace the token was issued
    for (which, at login, was validated against an active membership row).
    403 otherwise — cross-workspace access is prohibited.
    """
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace not specified")
    if workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-workspace access is prohibited")
    return ctx


def authenticate_credentials(db, email: str, password: str, workspace_id: str) -> Optional[SecurityContext]:
    """Resolve a login (email+password) against a workspace membership.

    Returns None when credentials are wrong, the user is inactive, or the user is
    not an active member of the workspace. The caller turns None into a 401.
    """
    from app.db.models.user import User
    from app.db.models.workspace_member import WorkspaceMember

    user = db.query(User).filter_by(email=email.lower().strip()).first()
    if not user:
        return None
    if user.status != "active":
        return None
    if not verify_password(password, user.password_hash):
        return None

    member = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == user.user_id, WorkspaceMember.workspace_id == workspace_id)
        .first()
    )
    if not member:
        return None

    return SecurityContext(user_id=user.user_id, email=user.email, workspace_id=workspace_id, role=member.role)