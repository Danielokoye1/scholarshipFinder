"""Add redacted Playwright inspection evidence and field plans.

Revision ID: 0004_form_inspection
Revises: 0003_safe_workflow
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_form_inspection"
down_revision: Union[str, None] = "0003_safe_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "browser_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("adapter", sa.String(80), nullable=False),
        sa.Column("start_url", sa.String(2000), nullable=False),
        sa.Column("final_url", sa.String(2000), nullable=True),
        sa.Column("initial_domain", sa.String(253), nullable=False),
        sa.Column("final_domain", sa.String(253), nullable=True),
        sa.Column("redirect_chain_json", sa.JSON(), nullable=False),
        sa.Column("page_title", sa.String(500), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("page_content_hash", sa.String(64), nullable=True),
        sa.Column("field_count", sa.Integer(), nullable=False),
        sa.Column("required_field_count", sa.Integer(), nullable=False),
        sa.Column("automatable_field_count", sa.Integer(), nullable=False),
        sa.Column("automatable_percent", sa.Float(), nullable=False),
        sa.Column("detected_barriers_json", sa.JSON(), nullable=False),
        sa.Column("blocked_requests_json", sa.JSON(), nullable=False),
        sa.Column("error_category", sa.String(80), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_browser_runs_application_id", "browser_runs", ["application_id"])
    op.create_index("ix_browser_runs_status", "browser_runs", ["status"])

    op.create_table(
        "form_field_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("browser_run_id", sa.String(36), sa.ForeignKey("browser_runs.id"), nullable=False),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("form_index", sa.Integer(), nullable=False),
        sa.Column("tag_name", sa.String(20), nullable=False),
        sa.Column("input_type", sa.String(40), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False),
        sa.Column("autocomplete", sa.String(120), nullable=True),
        sa.Column("profile_field_key", sa.String(180), nullable=True),
        sa.Column("mapping_confidence", sa.Float(), nullable=False),
        sa.Column("profile_status", sa.String(32), nullable=True),
        sa.Column("disposition", sa.String(40), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("browser_run_id", "ordinal", name="uq_form_field_plan_run_ordinal"),
    )
    op.create_index("ix_form_field_plans_browser_run_id", "form_field_plans", ["browser_run_id"])
    op.create_index("ix_form_field_plans_application_id", "form_field_plans", ["application_id"])


def downgrade() -> None:
    op.drop_table("form_field_plans")
    op.drop_table("browser_runs")
