"""Add offline dry-run filling and provenance evidence.

Revision ID: 0005_offline_dry_run_filling
Revises: 0004_form_inspection
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_offline_dry_run_filling"
down_revision: Union[str, None] = "0004_form_inspection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dry_run_fills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("browser_run_id", sa.String(36), sa.ForeignKey("browser_runs.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("execution_scope", sa.String(40), nullable=False),
        sa.Column("source_page_hash", sa.String(64), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=True),
        sa.Column("field_count", sa.Integer(), nullable=False),
        sa.Column("filled_field_count", sa.Integer(), nullable=False),
        sa.Column("skipped_field_count", sa.Integer(), nullable=False),
        sa.Column("errors_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dry_run_fills_application_id", "dry_run_fills", ["application_id"])
    op.create_index("ix_dry_run_fills_browser_run_id", "dry_run_fills", ["browser_run_id"])
    op.create_index("ix_dry_run_fills_status", "dry_run_fills", ["status"])

    op.create_table(
        "fill_field_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("fill_run_id", sa.String(36), sa.ForeignKey("dry_run_fills.id"), nullable=False),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("field_plan_id", sa.String(36), sa.ForeignKey("form_field_plans.id"), nullable=False),
        sa.Column("profile_field_id", sa.Integer(), sa.ForeignKey("profile_fields.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("profile_field_key", sa.String(180), nullable=False),
        sa.Column("profile_status", sa.String(32), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("profile_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_type", sa.String(40), nullable=False),
        sa.Column("value_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("fill_run_id", "field_plan_id", name="uq_fill_evidence_run_field"),
    )
    op.create_index("ix_fill_field_evidence_fill_run_id", "fill_field_evidence", ["fill_run_id"])
    op.create_index("ix_fill_field_evidence_application_id", "fill_field_evidence", ["application_id"])
    op.create_index("ix_fill_field_evidence_field_plan_id", "fill_field_evidence", ["field_plan_id"])


def downgrade() -> None:
    op.drop_table("fill_field_evidence")
    op.drop_table("dry_run_fills")
