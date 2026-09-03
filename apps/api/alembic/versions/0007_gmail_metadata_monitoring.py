"""Add metadata-only Gmail monitoring records.

Revision ID: 0007_gmail_metadata_monitoring
Revises: 0006_pre_submission_validation
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_gmail_metadata_monitoring"
down_revision: Union[str, None] = "0006_pre_submission_validation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_messages",
        sa.Column("provider_message_id", sa.String(128), primary_key=True),
        sa.Column("thread_id", sa.String(128), nullable=True),
        sa.Column("sender", sa.String(500), nullable=False),
        sa.Column("subject", sa.String(1000), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("is_unread", sa.Boolean(), nullable=False),
        sa.Column("is_actionable", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_email_messages_thread_id", "email_messages", ["thread_id"])
    op.create_index("ix_email_messages_received_at", "email_messages", ["received_at"])
    op.create_index("ix_email_messages_category", "email_messages", ["category"])
    op.create_index("ix_email_messages_is_unread", "email_messages", ["is_unread"])
    op.create_index("ix_email_messages_is_actionable", "email_messages", ["is_actionable"])
    op.create_index("ix_email_messages_last_seen_at", "email_messages", ["last_seen_at"])


def downgrade() -> None:
    op.drop_table("email_messages")
