"""complete rule intelligence database schema

Revision ID: 16e31c8f9de4
Revises: 8668d8db2946
Create Date: 2026-08-20 13:18:47.889477

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "16e31c8f9de4"
down_revision: Union[str, Sequence[str], None] = "8668d8db2946"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "audit_history",
        sa.Column("audit_id", sa.String(length=50), nullable=False),
        sa.Column("workspace_id", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.workspace_id"],
        ),
        sa.PrimaryKeyConstraint("audit_id"),
    )

    op.create_table(
        "reviews",
        sa.Column("review_id", sa.String(length=50), nullable=False),
        sa.Column("workspace_id", sa.String(length=50), nullable=False),
        sa.Column("suggestion_id", sa.String(length=50), nullable=False),
        sa.Column("reviewer_id", sa.String(length=100), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["rule_suggestions.suggestion_id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.workspace_id"],
        ),
        sa.PrimaryKeyConstraint("review_id"),
    )

    op.create_table(
        "rule_comparisons",
        sa.Column("comparison_id", sa.String(length=50), nullable=False),
        sa.Column("workspace_id", sa.String(length=50), nullable=False),
        sa.Column("suggestion_id", sa.String(length=50), nullable=True),
        sa.Column("comparison_type", sa.String(length=30), nullable=False),
        sa.Column("relationship", sa.String(length=50), nullable=False),
        sa.Column("matching_rule_id", sa.String(length=50), nullable=True),
        sa.Column("conflicting_rule_id", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conflicting_rule_id"],
            ["rules.rule_id"],
        ),
        sa.ForeignKeyConstraint(
            ["matching_rule_id"],
            ["rules.rule_id"],
        ),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["rule_suggestions.suggestion_id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.workspace_id"],
        ),
        sa.PrimaryKeyConstraint("comparison_id"),
    )

    # Analysis run traceability fields.
    op.add_column(
        "analysis_runs",
        sa.Column(
            "model_version_id",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "analysis_runs",
        sa.Column(
            "dataset_version_id",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "analysis_runs",
        sa.Column(
            "taxonomy_version",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "analysis_runs",
        sa.Column(
            "domain_pack_id",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "analysis_runs",
        sa.Column(
            "threshold_configuration",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "analysis_runs",
        sa.Column(
            "processing_mode",
            sa.String(length=30),
            nullable=False,
            server_default="single",
        ),
    )
    op.add_column(
        "analysis_runs",
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.add_column(
        "analysis_runs",
        sa.Column(
            "completed_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        None,
        "analysis_runs",
        "domain_packs",
        ["domain_pack_id"],
        ["pack_id"],
    )
    op.create_foreign_key(
        None,
        "analysis_runs",
        "dataset_versions",
        ["dataset_version_id"],
        ["dataset_version_id"],
    )
    op.create_foreign_key(
        None,
        "analysis_runs",
        "model_versions",
        ["model_version_id"],
        ["model_version_id"],
    )

    # Extracted rule structure and traceability.
    op.add_column(
        "extracted_rules",
        sa.Column(
            "suggestion_id",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "extracted_rules",
        sa.Column(
            "rule_family_id",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "extracted_rules",
        sa.Column(
            "business_term",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        "extracted_rules",
        sa.Column(
            "operation",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "extracted_rules",
        sa.Column(
            "conditions",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "extracted_rules",
        sa.Column(
            "scope",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "extracted_rules",
        sa.Column(
            "time_window",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "extracted_rules",
        sa.Column(
            "affected_tables",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "extracted_rules",
        sa.Column(
            "affected_columns",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "extracted_rules",
        sa.Column(
            "extraction_confidence",
            sa.Float(),
            nullable=True,
        ),
    )
    op.add_column(
        "extracted_rules",
        sa.Column(
            "schema_validation_status",
            sa.String(length=30),
            nullable=True,
        ),
    )

    op.alter_column(
        "extracted_rules",
        "rule_data",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        nullable=True,
    )

    op.create_foreign_key(
        None,
        "extracted_rules",
        "rule_suggestions",
        ["suggestion_id"],
        ["suggestion_id"],
    )

    # Rule suggestion processing and review state.
    op.add_column(
        "rule_suggestions",
        sa.Column(
            "feedback_type",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "rule_suggestions",
        sa.Column(
            "rule_category",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "rule_suggestions",
        sa.Column(
            "classification_result",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "rule_suggestions",
        sa.Column(
            "extraction_result",
            sa.String(length=30),
            nullable=True,
        ),
    )
    op.add_column(
        "rule_suggestions",
        sa.Column(
            "schema_validation_status",
            sa.String(length=30),
            nullable=True,
        ),
    )
    op.add_column(
        "rule_suggestions",
        sa.Column(
            "duplicate_status",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "rule_suggestions",
        sa.Column(
            "conflict_status",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "rule_suggestions",
        sa.Column(
            "clarification_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "rule_suggestions",
        sa.Column(
            "review_status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
    )

    op.alter_column(
        "rule_suggestions",
        "suggested_rule",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        nullable=True,
    )

    # Preserve existing review state before removing the old column.
    op.execute(
        """
        UPDATE rule_suggestions
        SET review_status = status
        WHERE status IS NOT NULL
        """
    )

    op.drop_column("rule_suggestions", "status")

    # Business rule lifecycle and activation metadata.
    op.add_column(
        "rules",
        sa.Column(
            "suggestion_id",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "rules",
        sa.Column(
            "rule_name",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        "rules",
        sa.Column(
            "rule_definition",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "rules",
        sa.Column(
            "activated_by",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "rules",
        sa.Column(
            "activated_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        None,
        "rules",
        "rule_suggestions",
        ["suggestion_id"],
        ["suggestion_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        None,
        "rules",
        type_="foreignkey",
    )
    op.drop_column("rules", "activated_at")
    op.drop_column("rules", "activated_by")
    op.drop_column("rules", "rule_definition")
    op.drop_column("rules", "rule_name")
    op.drop_column("rules", "suggestion_id")

    # Restore the old status column from review_status before removing it.
    op.add_column(
        "rule_suggestions",
        sa.Column(
            "status",
            sa.VARCHAR(length=30),
            autoincrement=False,
            nullable=False,
            server_default="pending",
        ),
    )

    op.execute(
        """
        UPDATE rule_suggestions
        SET status = review_status
        WHERE review_status IS NOT NULL
        """
    )

    op.alter_column(
        "rule_suggestions",
        "status",
        server_default=None,
    )

    op.alter_column(
        "rule_suggestions",
        "suggested_rule",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        nullable=False,
    )

    op.drop_column("rule_suggestions", "review_status")
    op.drop_column("rule_suggestions", "clarification_required")
    op.drop_column("rule_suggestions", "conflict_status")
    op.drop_column("rule_suggestions", "duplicate_status")
    op.drop_column("rule_suggestions", "schema_validation_status")
    op.drop_column("rule_suggestions", "extraction_result")
    op.drop_column("rule_suggestions", "classification_result")
    op.drop_column("rule_suggestions", "rule_category")
    op.drop_column("rule_suggestions", "feedback_type")

    op.drop_constraint(
        None,
        "extracted_rules",
        type_="foreignkey",
    )
    op.alter_column(
        "extracted_rules",
        "rule_data",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        nullable=False,
    )
    op.drop_column("extracted_rules", "schema_validation_status")
    op.drop_column("extracted_rules", "extraction_confidence")
    op.drop_column("extracted_rules", "affected_columns")
    op.drop_column("extracted_rules", "affected_tables")
    op.drop_column("extracted_rules", "time_window")
    op.drop_column("extracted_rules", "scope")
    op.drop_column("extracted_rules", "conditions")
    op.drop_column("extracted_rules", "operation")
    op.drop_column("extracted_rules", "business_term")
    op.drop_column("extracted_rules", "rule_family_id")
    op.drop_column("extracted_rules", "suggestion_id")

    op.drop_constraint(
        None,
        "analysis_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        None,
        "analysis_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        None,
        "analysis_runs",
        type_="foreignkey",
    )
    op.drop_column("analysis_runs", "completed_at")
    op.drop_column("analysis_runs", "started_at")
    op.drop_column("analysis_runs", "processing_mode")
    op.drop_column("analysis_runs", "threshold_configuration")
    op.drop_column("analysis_runs", "domain_pack_id")
    op.drop_column("analysis_runs", "taxonomy_version")
    op.drop_column("analysis_runs", "dataset_version_id")
    op.drop_column("analysis_runs", "model_version_id")

    op.drop_table("rule_comparisons")
    op.drop_table("reviews")
    op.drop_table("audit_history")
