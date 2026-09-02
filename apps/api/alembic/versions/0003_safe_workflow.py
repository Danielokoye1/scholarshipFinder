"""Add Phase 3 safety gates and application workflow.

Revision ID: 0003_safe_workflow
Revises: 0002_opportunity_intelligence
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_safe_workflow"
down_revision: Union[str, None] = "0002_opportunity_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    def column_names(table: str) -> set[str]:
        return {item["name"] for item in sa.inspect(bind).get_columns(table)}

    def index_names(table: str) -> set[str]:
        return {item["name"] for item in sa.inspect(bind).get_indexes(table)}

    scholarship_columns = column_names("scholarships")
    if "safety_status" not in scholarship_columns:
        op.add_column(
            "scholarships",
            sa.Column("safety_status", sa.String(40), nullable=False, server_default="review_required"),
        )
    if "priority_score" not in scholarship_columns:
        op.add_column(
            "scholarships", sa.Column("priority_score", sa.Float(), nullable=False, server_default="0")
        )

    application_columns = column_names("applications")
    application_additions = [
        sa.Column("safety_status", sa.String(40), nullable=False, server_default="review_required"),
        sa.Column("automation_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("manual_effort_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ]
    for column in application_additions:
        if column.name not in application_columns:
            op.add_column("applications", column)
    if "ix_applications_priority_score" not in index_names("applications"):
        op.create_index("ix_applications_priority_score", "applications", ["priority_score"])

    manual_task_columns = column_names("manual_tasks")
    with op.batch_alter_table("manual_tasks") as batch:
        if "scholarship_id" not in manual_task_columns:
            batch.add_column(sa.Column("scholarship_id", sa.String(36), nullable=True))
            batch.create_foreign_key(
                "fk_manual_tasks_scholarship_id", "scholarships", ["scholarship_id"], ["id"]
            )
        if "direct_url" not in manual_task_columns:
            batch.add_column(sa.Column("direct_url", sa.String(2000), nullable=True))
        if "priority_score" not in manual_task_columns:
            batch.add_column(sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"))
        if "resolved_at" not in manual_task_columns:
            batch.add_column(sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    if "ix_manual_tasks_scholarship_id" not in index_names("manual_tasks"):
        op.create_index("ix_manual_tasks_scholarship_id", "manual_tasks", ["scholarship_id"])
    if "ix_manual_tasks_priority_score" not in index_names("manual_tasks"):
        op.create_index("ix_manual_tasks_priority_score", "manual_tasks", ["priority_score"])

    op.create_table(
        "application_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("from_status", sa.String(48), nullable=True),
        sa.Column("to_status", sa.String(48), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_application_events_application_id", "application_events", ["application_id"])
    op.create_index("ix_application_events_created_at", "application_events", ["created_at"])

    op.create_table(
        "domain_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("domain", sa.String(253), nullable=False, unique=True),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_domain_policies_domain", "domain_policies", ["domain"], unique=True)

    op.create_table(
        "safety_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scholarship_id", sa.String(36), sa.ForeignKey("scholarships.id"), nullable=False),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("domain_policies.id"), nullable=True),
        sa.Column("application_domain", sa.String(253), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_safety_assessments_scholarship_id", "safety_assessments", ["scholarship_id"])
    op.create_index("ix_safety_assessments_application_id", "safety_assessments", ["application_id"])
    op.create_index("ix_safety_assessments_application_domain", "safety_assessments", ["application_domain"])
    op.create_index("ix_safety_assessments_is_current", "safety_assessments", ["is_current"])

    op.create_table(
        "priority_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("eligibility_weight", sa.Float(), nullable=False),
        sa.Column("award_weight", sa.Float(), nullable=False),
        sa.Column("urgency_weight", sa.Float(), nullable=False),
        sa.Column("completion_weight", sa.Float(), nullable=False),
        sa.Column("effort_weight", sa.Float(), nullable=False),
        sa.Column("award_reference_cents", sa.Integer(), nullable=False),
        sa.Column("urgency_window_days", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("priority_settings")
    op.drop_table("safety_assessments")
    op.drop_table("domain_policies")
    op.drop_table("application_events")
    with op.batch_alter_table("manual_tasks") as batch:
        batch.drop_index("ix_manual_tasks_priority_score")
        batch.drop_index("ix_manual_tasks_scholarship_id")
        batch.drop_column("resolved_at")
        batch.drop_column("priority_score")
        batch.drop_column("direct_url")
        batch.drop_column("scholarship_id")
    with op.batch_alter_table("applications") as batch:
        batch.drop_index("ix_applications_priority_score")
        batch.drop_column("version")
        batch.drop_column("started_at")
        batch.drop_column("last_error")
        batch.drop_column("manual_effort_score")
        batch.drop_column("priority_score")
        batch.drop_column("completion_percent")
        batch.drop_column("automation_level")
        batch.drop_column("safety_status")
    with op.batch_alter_table("scholarships") as batch:
        batch.drop_column("priority_score")
        batch.drop_column("safety_status")
