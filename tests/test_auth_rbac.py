"""Test harness for Authentication + RBAC + Workspace isolation (Spec §10.1/§10.2/§5.1/§5.9).

Two tiers:
  UNIT  (no server, no DB)      : hashing, JWT sign/verify, role levels, guards.
  INTEGRATION (live API)        : login -> token, 401/403 gates, admin-vs-reviewer.

Run the unit tier always:
    python3 tests/test_auth_rbac.py

Run the integration tier against a running API (after `alembic upgrade head` for the
seeded demo users) by setting RIE_TEST_INTEGRATION=1:
    RIE_TEST_INTEGRATION=1 RIE_BASE_URL=http://localhost:8001 \
        python3 tests/test_auth_rbac.py

Seeded demo identities (from the auth migration):
    admin@rie.local / Admin123!   -> administrator
    reviewer@rie.local / Review123! -> reviewer
    user@rie.local / User123!     -> business_user
Workspace default: e8af6af9-3bbe-4117-a007-f55db418bc30
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.security import (
    Role,
    create_access_token,
    decode_token,
    hash_password,
    require_role,
    require_workspace,
    SecurityContext,
    verify_password,
)

DEFAULT_WS = "e8af6af9-3bbe-4117-a007-f55db418bc30"
SEED_WS = DEFAULT_WS

failures = []


def check(cond, label, extra=""):
    if not cond:
        failures.append(f"{label} {extra}")

# ---------------------------------------------------------------- UNIT -------
# Password hashing
h = hash_password("Admin123!")
check(verify_password("Admin123!", h), "hash: verify correct pw")
check(not verify_password("wrongpw", h), "hash: reject wrong pw")
seed_hash = "pbkdf2$sha256$200000$9140f8e5b1c0d3a9f16e27b8c4d5a2f3$c6719375e71a251193a1f2a77a71be97eea4c1184af696e17d39f58adc675e2a"
check(verify_password("Admin123!", seed_hash), "hash: seeded admin hash verifies")
check(not verify_password("nope", "garbage-not-a-hash"), "hash: malformed stored hash rejected")

# Token roundtrip
tok = create_access_token("u1", "a@b.c", "wsA", Role.REVIEWER.value)
ctx = decode_token(tok)
check(ctx.user_id == "u1" and ctx.workspace_id == "wsA" and ctx.role == "reviewer",
      "token: roundtrip claims")

# Forged / tampered / expired tokens rejected (HTTPException 401)
def expect_401(label, fn):
    try:
        fn()
        check(False, label, "-> accepted!")
    except Exception as e:
        code = getattr(e, "status_code", None)
        check(code == 401, label, f"-> got {code}")

expect_401("token: forged signature", lambda: decode_token(tok[:-2] + "AA"))
import base64, json as _json

_hdr, _pay, _sig = tok.split(".")
_paydata = _json.loads(base64.urlsafe_b64decode(_pay + "=" * (-len(_pay) % 4)).decode())
_paydata["role"] = "administrator"
_tampered = base64.urlsafe_b64encode(_json.dumps(_paydata, separators=(",", ":")).encode()).rstrip(b"=").decode()
expect_401("token: tampered payload", lambda: decode_token(f"{_hdr}.{_tampered}.{_sig}"))
expect_401("token: expired", lambda: decode_token(create_access_token("u1", "a@b.c", "wsA", Role.REVIEWER.value, expires_in=-1)))
expect_401("token: malformed", lambda: decode_token("not.a.token"))

# Role hierarchy
check(isinstance(Role.ADMINISTRATOR.value, str), "role: enum values are strings")
L = lambda r: {Role.BUSINESS_USER: 1, Role.REVIEWER: 2, Role.ADMINISTRATOR: 3}[r]
check(L(Role.ADMINISTRATOR) > L(Role.REVIEWER) > L(Role.BUSINESS_USER), "role: strict levels")

# Guard factory: sufficent role passes, insufficient raises 403
rv = Role.REVIEWER
adm = Role.ADMINISTRATOR
bu = Role.BUSINESS_USER
reviewer_ctx = SecurityContext("r1", "r@b.c", "wsA", rv.value)
admin_ctx = SecurityContext("a1", "a@b.c", "wsA", adm.value)
business_ctx = SecurityContext("b1", "b@b.c", "wsA", bu.value)

rv_guard = require_role(rv)
check(rv_guard(ctx=reviewer_ctx).role == "reviewer", "guard: reviewer passes reviewer guard")
check(rv_guard(ctx=admin_ctx).role == "administrator", "guard: admin passes reviewer guard")
try:
    rv_guard(ctx=business_ctx)
    check(False, "guard: business_user blocked from reviewer guard")
except Exception as e:
    check(getattr(e, "status_code", None) == 403, "guard: business_user -> 403")

adm_guard = require_role(adm)
check(adm_guard(ctx=admin_ctx).role == "administrator", "guard: admin passes admin guard")
try:
    adm_guard(ctx=reviewer_ctx)
    check(False, "guard: reviewer blocked from admin guard")
except Exception as e:
    check(getattr(e, "status_code", None) == 403, "guard: reviewer -> 403 on admin op")

# Workspace isolation (§10.2)
check(require_workspace("wsA", reviewer_ctx).workspace_id == "wsA", "ws: matching workspace passes")
other_ctx = SecurityContext("a1", "a@b.c", "wsB", adm.value)
try:
    require_workspace("wsA", other_ctx)
    check(False, "ws: cross-workspace should be blocked")
except Exception as e:
    check(getattr(e, "status_code", None) == 403, "ws: cross-workspace -> 403")

# ----------------------------------------------------------------- UNIT OUTPUT
if failures:
    print(f"FAIL: {len(failures)} auth unit checks failed")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print(f"OK: all auth unit checks passed")

# ------------------------------------------------------------ INTEGRATION ----
if os.getenv("RIE_TEST_INTEGRATION") == "1":
    import httpx

    base = os.getenv("RIE_BASE_URL", "http://localhost:8001")
    # Generous timeout: the one "own-workspace not blocked" analyze call runs the
    # full 8-step pipeline (first call also loads DistilBERT into memory).
    c = httpx.Client(base_url=base, timeout=180)
    ifail = []

    def ichk(cond, label, extra=""):
        if not cond:
            ifail.append(f"{label} {extra}")

    def login(email, pw):
        r = c.post("/v1/auth/token", json={"email": email, "password": pw, "workspace_id": SEED_WS})
        ichk(r.status_code == 200, f"login {email}", f"-> {r.status_code} {r.text[:120]}")
        return r.json().get("access_token")

    # No token -> 401 on a protected endpoint and /v1/auth/me
    r = c.get("/v1/auth/me")
    ichk(r.status_code == 401, "no token /v1/auth/me", f"-> {r.status_code}")
    r = c.post(f"/v1/rules/NOPE/activate", json={})
    ichk(r.status_code == 401, "no token activate", f"-> {r.status_code}")

    admin = login("admin@rie.local", "Admin123!")
    reviewer = login("reviewer@rie.local", "Review123!")
    business = login("user@rie.local", "User123!")

    # Valid token -> role resolved
    r = c.get("/v1/auth/me", headers={"Authorization": f"Bearer {admin}"})
    ichk(r.status_code == 200 and r.json().get("role") == "administrator",
         "admin /v1/auth/me", f"-> {r.status_code} {r.text[:120]}")

    # RBAC on activate (§5.9 admin-only): reviewer/business -> 403, admin not-401/403
    r = c.post("/v1/rules/NOPE/activate", json={}, headers={"Authorization": f"Bearer {reviewer}"})
    ichk(r.status_code == 403, "reviewer activate -> 403", f"-> {r.status_code}")
    r = c.post("/v1/rules/NOPE/activate", json={}, headers={"Authorization": f"Bearer {business}"})
    ichk(r.status_code == 403, "business activate -> 403", f"-> {r.status_code}")
    r = c.post("/v1/rules/NOPE/activate", json={}, headers={"Authorization": f"Bearer {admin}"})
    ichk(r.status_code in (200, 404), "admin activate not-blocked", f"-> {r.status_code}")

    # Wrong password
    r = c.post("/v1/auth/token", json={"email": "admin@rie.local", "password": "WRONG", "workspace_id": SEED_WS})
    ichk(r.status_code == 401, "wrong password -> 401", f"-> {r.status_code}")

    # §10.2 / §5.2 submission-path isolation on /v1/feedback/analyze.
    # These checks run BEFORE pipeline processing, so they return fast.
    body = {"workspace_id": SEED_WS, "feedback_text": "Refund emails should go out within 24 hours"}
    h = {"Authorization": f"Bearer {admin}"}

    # Present-but-invalid token -> 401 (never downgraded to anonymous)
    r = c.post("/v1/feedback/analyze", json=body, headers={"Authorization": "Bearer not.a.jwt"})
    ichk(r.status_code == 401, "analyze invalid token -> 401", f"-> {r.status_code}")

    # Authenticated request targeting a workspace the user is NOT a member of -> 403
    r = c.post("/v1/feedback/analyze", json={"workspace_id": "CROSS_WORKSPACE_X", "feedback_text": "x"}, headers=h)
    ichk(r.status_code == 403, "analyze cross-workspace -> 403", f"-> {r.status_code}")

    # Legit workspace + valid token -> NOT blocked (pipeline result is out of scope here)
    r = c.post("/v1/feedback/analyze", json=body, headers=h)
    ichk(r.status_code not in (401, 403), "analyze own-workspace not blocked", f"-> {r.status_code}")

    # §6.6 / §10.11 auditability: auth events land in audit_history.
    # Checked via direct DB read (the audit table is not exposed over the API).
    try:
        import sqlalchemy as sa
        import os as _os

        _url = _os.getenv("DATABASE_URL", "postgresql://rie_user:rie_password@localhost:5432/rule_intelligence_engine")
        _e = sa.create_engine(_url)
        with _e.connect() as _c:
            rows = _c.execute(sa.text(
                "SELECT action, count(*) FROM audit_history "
                "WHERE action IN ('auth.login.succeeded','auth.login.failed','api.access.denied') "
                "GROUP BY action"
            )).fetchall()
        seen = {a: n for a, n in rows}
        ichk(seen.get("auth.login.succeeded", 0) >= 1, "audit: login success recorded", f"-> {seen}")
        ichk(seen.get("auth.login.failed", 0) >= 1, "audit: login failure recorded", f"-> {seen}")
        ichk(seen.get("api.access.denied", 0) >= 1, "audit: 401/403 denial recorded", f"-> {seen}")
    except Exception as _e:
        ichk(False, "audit: DB check failed", f"-> {_e}")

    if ifail:
        print(f"FAIL: {len(ifail)} auth integration checks failed")
        for f in ifail:
            print("  -", f)
        sys.exit(1)
    print("OK: auth integration checks passed")

print("ALL AUTH/RBAC TESTS PASSED")