"""Add execution_timestamps to analysis_runs

Revision ID: add_execution_timestamps
Revises: phase3_suggestion_audit_001_create_audit_table
Create Date: 2026-08-31 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_execution_timestamps'
down_revision: Union[str, None] = 'phase3_suggestion_audit_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add execution_timestamps column to analysis_runs table
    op.add_column('analysis_runs', sa.Column('execution_timestamps', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove execution_timestamps column from analysis_runs table
    op.drop_column('analysis_runs', 'execution_timestamps')