"""make audit_history workspace_id nullable

Spec §6.6 requires API access / authentication events to be auditable. A failed
login may name a workspace that does not exist (or name none at all), and that
is precisely the security event we must record — a NOT NULL FK would reject it.
The spec's audit fields are audit_id/entity_type/entity_id/action/performed_by/
timestamp; workspace_id is our own scoping column, so it may be null for
tenant-less system events.

Revision ID: ee468e948a60
Revises: 7c3f9a1e2d4b
Create Date: 2026-09-14 12:47:42.879022

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee468e948a60'
down_revision: Union[str, Sequence[str], None] = '7c3f9a1e2d4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow tenant-less audit events (auth failures, system API access)."""
    op.alter_column("audit_history", "workspace_id", existing_type=sa.String(length=50), nullable=True)


def downgrade() -> None:
    """Restore NOT NULL (only valid if no null rows exist)."""
    op.alter_column("audit_history", "workspace_id", existing_type=sa.String(length=50), nullable=False)
