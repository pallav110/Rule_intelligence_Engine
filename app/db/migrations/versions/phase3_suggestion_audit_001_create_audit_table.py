"""Create suggestion_audit table for lifecycle tracking.

Revision ID: phase3_suggestion_audit_001
Revises: pgvector_001_add_pgvector_extension
Create Date: 2026-08-26 06:17:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'phase3_suggestion_audit_001'
down_revision = 'pgvector_001_add_pgvector_extension'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'suggestion_audit',
        sa.Column('audit_id', sa.String(50), nullable=False),
        sa.Column('suggestion_id', sa.String(50), nullable=False),
        sa.Column('from_status', sa.String(50), nullable=False),
        sa.Column('to_status', sa.String(50), nullable=False),
        sa.Column('transitioned_by', sa.String(100), nullable=False),
        sa.Column('transition_reason', sa.String(500), nullable=True),
        sa.Column('metadata', postgresql.JSON, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['suggestion_id'], ['rule_suggestions.suggestion_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('audit_id'),
        sa.Index('ix_suggestion_audit_suggestion_id', 'suggestion_id'),
    )


def downgrade():
    op.drop_table('suggestion_audit')
