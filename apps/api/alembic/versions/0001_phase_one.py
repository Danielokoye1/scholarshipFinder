"""Phase one local foundation.

Revision ID: 0001_phase_one
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_phase_one"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profile_fields",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("field_key", sa.String(180), nullable=False, unique=True),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source", sa.String(500), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_profile_fields_field_key", "profile_fields", ["field_key"], unique=True)

    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
        sa.Column("document_type", sa.String(80), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("auto_upload_allowed", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_sha256", "documents", ["sha256"], unique=False)

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("automation_status", sa.String(32), nullable=False),
        sa.Column("operating_mode", sa.String(32), nullable=False),
        sa.Column("discovery_enabled", sa.Boolean(), nullable=False),
        sa.Column("eligibility_enabled", sa.Boolean(), nullable=False),
        sa.Column("preparation_enabled", sa.Boolean(), nullable=False),
        sa.Column("automatic_submission_enabled", sa.Boolean(), nullable=False),
        sa.Column("email_monitoring_enabled", sa.Boolean(), nullable=False),
        sa.Column("emergency_stop", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "system_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_system_events_created_at", "system_events", ["created_at"], unique=False)

    op.create_table(
        "scholarships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_name", sa.String(300), nullable=False),
        sa.Column("provider", sa.String(200), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("application_url", sa.String(2000), nullable=True),
        sa.Column("award_max_cents", sa.Integer(), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eligibility_status", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scholarships_deadline", "scholarships", ["deadline"], unique=False)
    op.create_index("ix_scholarships_source_url", "scholarships", ["source_url"], unique=True)

    op.create_table(
        "applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scholarship_id", sa.String(36), sa.ForeignKey("scholarships.id"), nullable=False),
        sa.Column("status", sa.String(48), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("award_result_cents", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scholarship_id", name="uq_application_scholarship"),
    )
    op.create_index("ix_applications_status", "applications", ["status"], unique=False)

    op.create_table(
        "manual_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("required_action", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_manual_tasks_status", "manual_tasks", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("manual_tasks")
    op.drop_table("applications")
    op.drop_table("scholarships")
    op.drop_table("system_events")
    op.drop_table("system_settings")
    op.drop_table("documents")
    op.drop_table("profile_fields")

