"""Add authoring_drafts table for System 1 session persistence

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-01 00:00:00.000000

Persists System 1 guided-authoring sessions so they survive server restarts
and provide the data for the user's prank history (GET /authoring/sessions).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "authoring_drafts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="collecting_info",
        ),
        # Full PrankDraft serialised as JSON text
        sa.Column(
            "draft_json",
            sa.Text(),
            nullable=False,
            server_default="'{}'",
        ),
        # Full message list serialised as JSON text
        sa.Column(
            "messages_json",
            sa.Text(),
            nullable=False,
            server_default="'[]'",
        ),
        sa.Column("recipient_phone", sa.String(50), nullable=True),
        sa.Column(
            "is_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        # Denormalised from PrankDraft.prank_title for cheap list queries
        sa.Column("prank_title", sa.String(200), nullable=True),
        # Null until user taps "Стартирай пранка"
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_authoring_drafts_user_id", "authoring_drafts", ["user_id"])
    op.create_index("ix_authoring_drafts_created_at", "authoring_drafts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_authoring_drafts_created_at", table_name="authoring_drafts")
    op.drop_index("ix_authoring_drafts_user_id", table_name="authoring_drafts")
    op.drop_table("authoring_drafts")
