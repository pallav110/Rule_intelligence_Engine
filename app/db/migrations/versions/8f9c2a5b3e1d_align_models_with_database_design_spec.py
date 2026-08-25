"""align models with database design spec

Revision ID: 8f9c2a5b3e1d
Revises: 70f8421d8630
Create Date: 2026-08-25 06:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f9c2a5b3e1d'
down_revision: Union[str, Sequence[str], None] = '70f8421d8630'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to align models with specification."""

    # Workspace: add description, status, created_at
    op.add_column('workspaces', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('workspaces', sa.Column('status', sa.String(30), nullable=False, server_default='active'))
    op.add_column('workspaces', sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))

    # Feedback: rename content to feedback_text, add submitted_by, processing_status
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.alter_column('content', new_column_name='feedback_text')
        batch_op.add_column(sa.Column('submitted_by', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('processing_status', sa.String(30), nullable=False, server_default='received'))

    # Rule: add business_term, domain_id, scope, threshold, time_window, affected_entities, created_at
    op.add_column('rules', sa.Column('business_term', sa.String(255), nullable=True))
    op.add_column('rules', sa.Column('domain_id', sa.String(100), nullable=True))
    op.add_column('rules', sa.Column('scope', sa.JSON(), nullable=True))
    op.add_column('rules', sa.Column('threshold', sa.JSON(), nullable=True))
    op.add_column('rules', sa.Column('time_window', sa.JSON(), nullable=True))
    op.add_column('rules', sa.Column('affected_entities', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('rules', sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))

    # DomainPack: add workspace_id, schema_metadata, business_glossary, configuration
    op.add_column('domain_packs', sa.Column('workspace_id', sa.String(50), sa.ForeignKey('workspaces.workspace_id'), nullable=True))
    op.add_column('domain_packs', sa.Column('schema_metadata', sa.JSON(), nullable=True))
    op.add_column('domain_packs', sa.Column('business_glossary', sa.JSON(), nullable=True))
    op.add_column('domain_packs', sa.Column('configuration', sa.JSON(), nullable=True))

    # Clarification: add suggestion_id, questions, reason, clarification_response, responded_by, responded_at, processing_status
    with op.batch_alter_table('clarifications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('suggestion_id', sa.String(50), sa.ForeignKey('rule_suggestions.suggestion_id'), nullable=True))
        batch_op.add_column(sa.Column('questions', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('clarification_response', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('responded_by', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('responded_at', sa.DateTime(), nullable=True))
        # Rename question to clarification_question and status to processing_status
        batch_op.alter_column('question', new_column_name='clarification_question')
        batch_op.alter_column('status', new_column_name='processing_status')
        # Make feedback_id and analysis_run_id nullable for spec flexibility
        batch_op.alter_column('feedback_id', existing_type=sa.String(50), nullable=True)
        batch_op.alter_column('analysis_run_id', existing_type=sa.String(50), nullable=True)

    # Review: add status, priority, notes, assigned_at, completed_at; make decision nullable
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(30), nullable=False, server_default='assigned'))
        batch_op.add_column(sa.Column('priority', sa.String(30), nullable=False, server_default='normal'))
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('assigned_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
        batch_op.add_column(sa.Column('completed_at', sa.DateTime(), nullable=True))
        # Rename comment to notes (if not already done)
        try:
            batch_op.alter_column('comment', new_column_name='notes')
        except:
            pass  # Column may have already been renamed
        # Rename reviewed_at if it doesn't exist, or add it
        batch_op.add_column(sa.Column('reviewed_at', sa.DateTime(), nullable=True))
        # Make decision nullable
        batch_op.alter_column('decision', existing_type=sa.String(30), nullable=True)
        # Make reviewer_id nullable
        batch_op.alter_column('reviewer_id', existing_type=sa.String(100), nullable=True)

    # BackgroundJob: add progress, completed_at (if not already present)
    with op.batch_alter_table('background_jobs', schema=None) as batch_op:
        try:
            batch_op.add_column(sa.Column('progress', sa.Integer(), nullable=False, server_default='0'))
        except:
            pass  # Column may already exist
        try:
            batch_op.add_column(sa.Column('completed_at', sa.DateTime(), nullable=True))
        except:
            pass  # Column may already exist

    # DatasetVersion: add description, num_samples, domain_pack_id (and add version_name as alias for dataset_name)
    with op.batch_alter_table('dataset_versions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('num_samples', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('domain_pack_id', sa.String(50), sa.ForeignKey('domain_packs.pack_id'), nullable=True))

    # ModelVersion: map model_path to artifact_path, add description, dataset_version_id, metrics
    with op.batch_alter_table('model_versions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('dataset_version_id', sa.String(100), sa.ForeignKey('dataset_versions.dataset_version_id'), nullable=True))
        batch_op.add_column(sa.Column('metrics', sa.JSON(), nullable=True))

    # EvaluationRun: add classification_accuracy, classification_f1, complete_rule_accuracy, duplicate_f1, conflict_f1, calibration_error
    with op.batch_alter_table('evaluation_runs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('classification_accuracy', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('classification_f1', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('complete_rule_accuracy', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('duplicate_f1', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('conflict_f1', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('calibration_error', sa.Float(), nullable=True))

    # RuleComparison: add extracted_rule_id, compared_rule_id
    with op.batch_alter_table('rule_comparisons', schema=None) as batch_op:
        batch_op.add_column(sa.Column('extracted_rule_id', sa.String(50), sa.ForeignKey('extracted_rules.extracted_rule_id'), nullable=True))
        batch_op.add_column(sa.Column('compared_rule_id', sa.String(50), sa.ForeignKey('rules.rule_id'), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""

    # RuleComparison
    with op.batch_alter_table('rule_comparisons', schema=None) as batch_op:
        batch_op.drop_column('compared_rule_id')
        batch_op.drop_column('extracted_rule_id')

    # EvaluationRun
    with op.batch_alter_table('evaluation_runs', schema=None) as batch_op:
        batch_op.drop_column('calibration_error')
        batch_op.drop_column('conflict_f1')
        batch_op.drop_column('duplicate_f1')
        batch_op.drop_column('complete_rule_accuracy')
        batch_op.drop_column('classification_f1')
        batch_op.drop_column('classification_accuracy')

    # ModelVersion
    with op.batch_alter_table('model_versions', schema=None) as batch_op:
        batch_op.drop_column('metrics')
        batch_op.drop_column('dataset_version_id')
        batch_op.drop_column('description')

    # DatasetVersion
    with op.batch_alter_table('dataset_versions', schema=None) as batch_op:
        batch_op.drop_column('domain_pack_id')
        batch_op.drop_column('num_samples')
        batch_op.drop_column('description')

    # BackgroundJob
    with op.batch_alter_table('background_jobs', schema=None) as batch_op:
        batch_op.drop_column('completed_at')
        batch_op.drop_column('progress')

    # Review
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.drop_column('reviewed_at')
        batch_op.alter_column('decision', existing_type=sa.String(30), nullable=False)
        batch_op.alter_column('reviewer_id', existing_type=sa.String(100), nullable=False)
        batch_op.drop_column('completed_at')
        batch_op.drop_column('assigned_at')
        batch_op.drop_column('notes')
        batch_op.drop_column('priority')
        batch_op.drop_column('status')

    # Clarification
    with op.batch_alter_table('clarifications', schema=None) as batch_op:
        batch_op.alter_column('feedback_id', existing_type=sa.String(50), nullable=False)
        batch_op.alter_column('analysis_run_id', existing_type=sa.String(50), nullable=False)
        batch_op.alter_column('processing_status', new_column_name='status')
        batch_op.alter_column('clarification_question', new_column_name='question')
        batch_op.drop_column('responded_at')
        batch_op.drop_column('responded_by')
        batch_op.drop_column('clarification_response')
        batch_op.drop_column('reason')
        batch_op.drop_column('questions')
        batch_op.drop_column('suggestion_id')

    # DomainPack
    op.drop_column('domain_packs', 'configuration')
    op.drop_column('domain_packs', 'business_glossary')
    op.drop_column('domain_packs', 'schema_metadata')
    op.drop_column('domain_packs', 'workspace_id')

    # Rule
    op.drop_column('rules', 'created_at')
    op.drop_column('rules', 'affected_entities')
    op.drop_column('rules', 'time_window')
    op.drop_column('rules', 'threshold')
    op.drop_column('rules', 'scope')
    op.drop_column('rules', 'domain_id')
    op.drop_column('rules', 'business_term')

    # Feedback
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.drop_column('processing_status')
        batch_op.drop_column('submitted_by')
        batch_op.alter_column('feedback_text', new_column_name='content')

    # Workspace
    op.drop_column('workspaces', 'created_at')
    op.drop_column('workspaces', 'status')
    op.drop_column('workspaces', 'description')
