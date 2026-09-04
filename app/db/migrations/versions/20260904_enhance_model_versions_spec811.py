"""enhance model_versions table for spec 8.11 compliance

Revision ID: 20260904_enhance_model_versions_spec811
Revises: b5dbc264746a
Create Date: 2026-09-04 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260904_enhance_model_versions_spec811'
down_revision: Union[str, Sequence[str], None] = 'b5dbc264746a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add new columns per spec 8.11."""
    # Add model_type column with enum
    op.add_column('model_versions',
        sa.Column('model_type', sa.String(50), nullable=False, server_default='other')
    )

    # Add checkpoint_path (extend from artifact_path)
    op.add_column('model_versions',
        sa.Column('checkpoint_path', sa.String(500), nullable=False, server_default='')
    )

    # Add dataset linkage columns
    op.add_column('model_versions',
        sa.Column('training_dataset_version_id', sa.String(100), nullable=True)
    )
    op.add_column('model_versions',
        sa.Column('validation_dataset_version_id', sa.String(100), nullable=True)
    )

    # Add annotation_scheme_version
    op.add_column('model_versions',
        sa.Column('annotation_scheme_version', sa.String(50), nullable=True)
    )

    # Add hyperparameters as JSON
    op.add_column('model_versions',
        sa.Column('hyperparameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # Add training_timestamp
    op.add_column('model_versions',
        sa.Column('training_timestamp', sa.DateTime(), nullable=True)
    )

    # Add evaluation_metrics as JSON
    op.add_column('model_versions',
        sa.Column('evaluation_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # Add updated_at
    op.add_column('model_versions',
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
    )

    # Update status column to have proper default and enum values
    # The status column already exists, just ensure default is CANDIDATE
    op.alter_column('model_versions', 'status',
        existing_type=sa.String(20),
        server_default='CANDIDATE'
    )

    # Create foreign key constraints for dataset versions (if table exists)
    # These will be created when dataset_versions table exists
    # op.create_foreign_key('fk_model_versions_training_dataset', 'model_versions', 'dataset_versions',
    #     ['training_dataset_version_id'], ['dataset_version_id'])
    # op.create_foreign_key('fk_model_versions_validation_dataset', 'model_versions', 'dataset_versions',
    #     ['validation_dataset_version_id'], ['dataset_version_id'])

    # Create index for active model lookup
    op.create_index('ix_model_versions_type_status', 'model_versions', ['model_type', 'status'])
    op.create_index('ix_model_versions_active_lookup', 'model_versions', ['model_type', 'status', 'created_at'])


def downgrade() -> None:
    """Downgrade schema - remove added columns."""
    # Drop indexes
    op.drop_index('ix_model_versions_active_lookup', table_name='model_versions')
    op.drop_index('ix_model_versions_type_status', table_name='model_versions')

    # Drop columns in reverse order
    op.drop_column('model_versions', 'updated_at')
    op.drop_column('model_versions', 'evaluation_metrics')
    op.drop_column('model_versions', 'training_timestamp')
    op.drop_column('model_versions', 'hyperparameters')
    op.drop_column('model_versions', 'annotation_scheme_version')
    op.drop_column('model_versions', 'validation_dataset_version_id')
    op.drop_column('model_versions', 'training_dataset_version_id')
    op.drop_column('model_versions', 'checkpoint_path')
    op.drop_column('model_versions', 'model_type')