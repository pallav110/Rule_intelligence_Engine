"""add auth users and workspace members

Adds the users and workspace_members tables backing Spec §10.1 RBAC / §10.2
workspace isolation, and seeds a default workspace with three demo identities
(administrator / reviewer / business_user) so the authentication flow is testable
immediately after `alembic upgrade head`.

Revision ID: 7c3f9a1e2d4b
Revises: fb5bdc75776b
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
# NOTE: this MUST be a short id — Alembic stores it in alembic_version.version_num
# which is varchar(32). A descriptive string overflows it.
revision: str = "7c3f9a1e2d4b"
down_revision: Union[str, Sequence[str], None] = "fb5bdc75776b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The workspace the demo identities are members of. Must match the env default in
# app/main.py:extract_workspace_from_context (DEFAULT_WORKSPACE_ID) so an un-tokened
# request and a token-authenticated request address the same logical tenant.
DEFAULT_WORKSPACE_ID = "e8af6af9-3bbe-4117-a007-f55db418bc30"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "workspace_members",
        sa.Column("membership_id", sa.String(length=50), nullable=False),
        sa.Column("workspace_id", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.workspace_id"]),
        sa.PrimaryKeyConstraint("membership_id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member_workspace_user"),
    )

    # --- Seed the default workspace (get-or-create) + demo identities ----------
    now = "2026-09-14T00:00:00.000000"
    op.execute(
        sa.text(
            f"INSERT INTO workspaces (workspace_id, name, description, status, created_at) "
            f"VALUES (:wid, 'Default Workspace', 'Seeded by auth migration', 'active', :ts) "
            f"ON CONFLICT (workspace_id) DO NOTHING"
        ).bindparams(wid=DEFAULT_WORKSPACE_ID, ts=now)
    )

    # Deterministic PBKDF2-HMAC-SHA256 hashes (200k iters, fixed salt).
    # Plaintext demo passwords (for tests / local login only):
    #   admin@rie.local    / Admin123!
    #   reviewer@rie.local / Review123!
    #   user@rie.local     / User123!
    users = [
        ("u-admin-0001", "admin@rie.local",
         "pbkdf2$sha256$200000$9140f8e5b1c0d3a9f16e27b8c4d5a2f3$c6719375e71a251193a1f2a77a71be97eea4c1184af696e17d39f58adc675e2a",
         "Demo Administrator", "administrator"),
        ("u-review-0001", "reviewer@rie.local",
         "pbkdf2$sha256$200000$9140f8e5b1c0d3a9f16e27b8c4d5a2f3$fd63491b6d557f67a1259dd0d6469ea4f12287ae992823eb56e2d2df7de7f234",
         "Demo Reviewer", "reviewer"),
        ("u-user-0001", "user@rie.local",
         "pbkdf2$sha256$200000$9140f8e5b1c0d3a9f16e27b8c4d5a2f3$5ada4f222910d981a63828cc58c5f16a87703801467718740a9dfaa43467eb8d",
         "Demo Business User", "business_user"),
    ]
    for uid, email, pw_hash, name, role in users:
        op.execute(
            sa.text(
                "INSERT INTO users (user_id, email, password_hash, name, status, created_at, updated_at) "
                "VALUES (:uid, :email, :pw, :name, 'active', :ts, :ts) "
                "ON CONFLICT (user_id) DO NOTHING"
            ).bindparams(uid=uid, email=email, pw=pw_hash, name=name, ts=now)
        )
        op.execute(
            sa.text(
                "INSERT INTO workspace_members (membership_id, workspace_id, user_id, role, created_at) "
                "VALUES (:mid, :wid, :uid, :role, :ts) "
                "ON CONFLICT (workspace_id, user_id) DO NOTHING"
            ).bindparams(mid=f"m-{uid}", wid=DEFAULT_WORKSPACE_ID, uid=uid, role=role, ts=now)
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("workspace_members")
    op.drop_table("users")