"""Add pgvector extension and rule_embeddings table

Revision ID: pgvector_001
Revises: 8f9c2a5b3e1d
Create Date: 2026-08-26 05:11:46.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'pgvector_001'
down_revision: Union[str, Sequence[str], None] = '8f9c2a5b3e1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: Enable pgvector extension and create rule_embeddings table."""

    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create rule_embeddings table
    op.create_table(
        'rule_embeddings',
        sa.Column('embedding_id', sa.String(50), nullable=False),
        sa.Column('rule_id', sa.String(50), nullable=False),
        sa.Column('workspace_id', sa.String(100), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=False),  # Stores vector as text
        sa.Column('embedding_model', sa.String(100), nullable=False, server_default='sentence-transformers/all-MiniLM-L6-v2'),
        sa.Column('embedding_dimension', sa.Integer(), nullable=False, server_default='384'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['rule_id'], ['rules.rule_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.workspace_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('embedding_id')
    )

    # Create indexes for performance
    op.create_index('ix_rule_embeddings_rule_id', 'rule_embeddings', ['rule_id'])
    op.create_index('ix_rule_embeddings_workspace_id', 'rule_embeddings', ['workspace_id'])

    # Try to create pgvector index if extension is available
    # This will fail gracefully if pgvector is not available
    try:
        op.execute('CREATE INDEX IF NOT EXISTS ix_rule_embeddings_vector ON rule_embeddings USING ivfflat (embedding vector_cosine_ops)')
    except Exception:
        # pgvector not available, will use standard B-tree indexes
        pass


def downgrade() -> None:
    """Downgrade: Drop rule_embeddings table and pgvector extension."""

    # Drop table (cascade will handle indexes)
    op.drop_table('rule_embeddings')

    # Note: We don't drop the pgvector extension here as it might be used elsewhere
    # If you want to remove it, uncomment below
    # op.execute('DROP EXTENSION IF EXISTS vector CASCADE')
