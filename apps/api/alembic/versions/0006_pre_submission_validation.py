"""Add immutable pre-submission validation snapshots.

Revision ID: 0006_pre_submission_validation
Revises: 0005_offline_dry_run_filling
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_pre_submission_validation"
down_revision: Union[str, None] = "0005_offline_dry_run_filling"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("browser_run_id", sa.String(36), sa.ForeignKey("browser_runs.id"), nullable=False),
        sa.Column("dry_run_fill_id", sa.String(36), sa.ForeignKey("dry_run_fills.id"), nullable=False),
        sa.Column("safety_assessment_id", sa.String(36), sa.ForeignKey("safety_assessments.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("operating_mode", sa.String(32), nullable=False),
        sa.Column("source_page_hash", sa.String(64), nullable=False),
        sa.Column("fill_manifest_hash", sa.String(64), nullable=False),
        sa.Column("validation_manifest_hash", sa.String(64), nullable=False),
        sa.Column("eligibility_run_id", sa.String(36), nullable=True),
        sa.Column("checks_json", sa.JSON(), nullable=False),
        sa.Column("blockers_json", sa.JSON(), nullable=False),
        sa.Column("profile_manifest_json", sa.JSON(), nullable=False),
        sa.Column("document_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_validation_snapshots_application_id", "validation_snapshots", ["application_id"])
    op.create_index("ix_validation_snapshots_browser_run_id", "validation_snapshots", ["browser_run_id"])
    op.create_index("ix_validation_snapshots_dry_run_fill_id", "validation_snapshots", ["dry_run_fill_id"])
    op.create_index("ix_validation_snapshots_status", "validation_snapshots", ["status"])
    op.create_index(
        "ix_validation_snapshots_validation_manifest_hash",
        "validation_snapshots",
        ["validation_manifest_hash"],
    )


def downgrade() -> None:
    op.drop_table("validation_snapshots")
