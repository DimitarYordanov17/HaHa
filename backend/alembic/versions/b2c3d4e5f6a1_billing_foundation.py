"""Billing foundation: user_id on prank_sessions, credits on users

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-02-27 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "b2c3d4e5f6a1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Billing balance for each user.  Starts at zero; deduction logic is not
    # implemented yet — this column is the schema foundation only.
    op.add_column(
        "users",
        sa.Column(
            "credits",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Link each prank session to the user who initiated it.  Nullable during
    # the transition period; the application layer will be updated to always
    # supply user_id before this is tightened to NOT NULL.
    op.add_column(
        "prank_sessions",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_prank_sessions_user_id", "prank_sessions", ["user_id"])

    op.add_column(
        "prank_sessions",
        sa.Column(
            "charged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("prank_sessions", "charged")
    op.drop_index("ix_prank_sessions_user_id", table_name="prank_sessions")
    op.drop_column("prank_sessions", "user_id")
    op.drop_column("users", "credits")
