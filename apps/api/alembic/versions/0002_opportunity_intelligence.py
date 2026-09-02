"""Add normalized scholarship intelligence and eligibility evidence.

Revision ID: 0002_opportunity_intelligence
Revises: 0001_phase_one
"""
from hashlib import sha256
import re
import unicodedata
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_opportunity_intelligence"
down_revision: Union[str, None] = "0001_phase_one"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scholarships", sa.Column("normalized_name", sa.String(300), nullable=True))
    op.add_column("scholarships", sa.Column("normalized_provider", sa.String(200), nullable=True))
    op.add_column("scholarships", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("scholarships", sa.Column("award_min_cents", sa.Integer(), nullable=True))
    op.add_column("scholarships", sa.Column("award_description", sa.String(500), nullable=True))
    op.add_column("scholarships", sa.Column("raw_deadline_text", sa.String(300), nullable=True))
    op.add_column("scholarships", sa.Column("deadline_timezone", sa.String(10), nullable=True))
    op.add_column(
        "scholarships",
        sa.Column("deadline_type", sa.String(40), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "scholarships",
        sa.Column("requirements_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column("scholarships", sa.Column("fingerprint", sa.String(64), nullable=True))
    op.add_column(
        "scholarships",
        sa.Column("legitimacy_status", sa.String(40), nullable=False, server_default="review_required"),
    )
    op.add_column(
        "scholarships",
        sa.Column("legitimacy_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scholarships",
        sa.Column("legitimacy_signals_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "scholarships",
        sa.Column("eligibility_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scholarships",
        sa.Column("automation_level", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("scholarships", sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, source_url, canonical_name, provider FROM scholarships")
    ).mappings()
    for row in rows:
        fingerprint = sha256(row["source_url"].strip().lower().encode("utf-8")).hexdigest()
        normalized_name = re.sub(
            r"[^a-z0-9]+", " ", unicodedata.normalize("NFKC", row["canonical_name"]).casefold()
        ).strip()
        normalized_provider = (
            re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKC", row["provider"]).casefold()).strip()
            if row["provider"]
            else None
        )
        connection.execute(
            sa.text(
                "UPDATE scholarships SET fingerprint = :fingerprint, normalized_name = :normalized_name, "
                "normalized_provider = :normalized_provider WHERE id = :id"
            ),
            {
                "fingerprint": fingerprint,
                "normalized_name": normalized_name,
                "normalized_provider": normalized_provider,
                "id": row["id"],
            },
        )
    with op.batch_alter_table("scholarships") as batch:
        batch.alter_column("fingerprint", existing_type=sa.String(64), nullable=False)
        batch.alter_column("normalized_name", existing_type=sa.String(300), nullable=False)
        batch.create_index("ix_scholarships_fingerprint", ["fingerprint"], unique=True)
        batch.create_index("ix_scholarships_normalized_name", ["normalized_name"], unique=False)
        batch.create_index("ix_scholarships_normalized_provider", ["normalized_provider"], unique=False)

    op.create_table(
        "scholarship_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scholarship_id", sa.String(36), sa.ForeignKey("scholarships.id"), nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=False, unique=True),
        sa.Column("adapter", sa.String(80), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_crawl_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scholarship_sources_scholarship_id", "scholarship_sources", ["scholarship_id"])

    op.create_table(
        "source_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scholarship_id", sa.String(36), sa.ForeignKey("scholarships.id"), nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("evidence_type", sa.String(80), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_source_evidence_scholarship_id", "source_evidence", ["scholarship_id"])

    op.create_table(
        "eligibility_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scholarship_id", sa.String(36), sa.ForeignKey("scholarships.id"), nullable=False),
        sa.Column("evidence_id", sa.String(36), sa.ForeignKey("source_evidence.id"), nullable=True),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("field_key", sa.String(180), nullable=True),
        sa.Column("operator", sa.String(40), nullable=False),
        sa.Column("expected_value_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_eligibility_rules_scholarship_id", "eligibility_rules", ["scholarship_id"])

    op.create_table(
        "eligibility_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scholarship_id", sa.String(36), sa.ForeignKey("scholarships.id"), nullable=False),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("eligibility_rules.id"), nullable=False),
        sa.Column("profile_field_id", sa.Integer(), sa.ForeignKey("profile_fields.id"), nullable=True),
        sa.Column("profile_value_json", sa.JSON(), nullable=True),
        sa.Column("result", sa.String(40), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evaluation_run_id", sa.String(36), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_eligibility_checks_scholarship_id", "eligibility_checks", ["scholarship_id"])
    op.create_index("ix_eligibility_checks_rule_id", "eligibility_checks", ["rule_id"])
    op.create_index("ix_eligibility_checks_evaluation_run_id", "eligibility_checks", ["evaluation_run_id"])
    op.create_index("ix_eligibility_checks_is_current", "eligibility_checks", ["is_current"])


def downgrade() -> None:
    op.drop_table("eligibility_checks")
    op.drop_table("eligibility_rules")
    op.drop_table("source_evidence")
    op.drop_table("scholarship_sources")
    with op.batch_alter_table("scholarships") as batch:
        batch.drop_index("ix_scholarships_normalized_provider")
        batch.drop_index("ix_scholarships_normalized_name")
        batch.drop_index("ix_scholarships_fingerprint")
        batch.drop_column("last_verified_at")
        batch.drop_column("automation_level")
        batch.drop_column("eligibility_score")
        batch.drop_column("legitimacy_signals_json")
        batch.drop_column("legitimacy_score")
        batch.drop_column("legitimacy_status")
        batch.drop_column("fingerprint")
        batch.drop_column("requirements_json")
        batch.drop_column("deadline_type")
        batch.drop_column("raw_deadline_text")
        batch.drop_column("deadline_timezone")
        batch.drop_column("award_description")
        batch.drop_column("award_min_cents")
        batch.drop_column("description")
        batch.drop_column("normalized_provider")
        batch.drop_column("normalized_name")
