"""add pgvector extension and rule_embeddings table

Revision ID: 0001_add_pgvector_and_rule_embeddings
Revises: 
Create Date: 2026-09-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_add_pgvector_and_rule_embeddings'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pgvector extension and embeddings table.
    # Use raw SQL to reference the `vector` type provided by pgvector.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_embeddings (
            id UUID PRIMARY KEY,
            rule_id VARCHAR(100) NOT NULL,
            embedding vector(1536),
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
        );
        """
    )

    # Create an ivfflat index for approximate nearest neighbor searches (requires pgvector >= 0.4)
    try:
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_rule_embeddings_embedding ON rule_embeddings USING ivfflat (embedding) WITH (lists = 100);"
        )
    except Exception:
        # If the cluster doesn't support ivfflat (older pgvector), silently skip index creation.
        pass


def downgrade() -> None:
    # Drop the embeddings table and attempt to drop extension if safe
    op.execute("DROP TABLE IF EXISTS rule_embeddings;")
    try:
        op.execute("DROP EXTENSION IF EXISTS vector;")
    except Exception:
        pass
