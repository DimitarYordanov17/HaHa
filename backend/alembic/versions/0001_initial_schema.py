"""Initial schema: users and prank_sessions

Revision ID: 0001
Revises:
Create Date: 2026-03-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENUM_VALUES = (
    "CREATED",
    "CALLING_SENDER",
    "CALLING_RECIPIENT",
    "BRIDGED",
    "PLAYING_AUDIO",
    "COMPLETED",
    "FAILED",
)
_ENUM_NAME = "pranksessionstate"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("phone_number", sa.String(50), nullable=False),
        sa.Column(
            "credits",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.execute(
        sa.text(
            f"CREATE TYPE {_ENUM_NAME} AS ENUM "
            f"({', '.join(repr(v) for v in _ENUM_VALUES)})"
        )
    )

    op.create_table(
        "prank_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_number", sa.String(), nullable=False),
        sa.Column("recipient_number", sa.String(), nullable=False),
        sa.Column("sender_call_control_id", sa.String(), nullable=True),
        sa.Column("recipient_call_control_id", sa.String(), nullable=True),
        sa.Column(
            "state",
            postgresql.ENUM(*_ENUM_VALUES, name=_ENUM_NAME, create_type=False),
            nullable=False,
            server_default=sa.text("'CREATED'"),
        ),
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
        sa.Column(
            "charged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.CheckConstraint(
            "state NOT IN ('BRIDGED', 'PLAYING_AUDIO', 'COMPLETED')"
            " OR (sender_call_control_id IS NOT NULL"
            "     AND recipient_call_control_id IS NOT NULL)",
            name="ck_prank_sessions_bridged_requires_call_ids",
        ),
    )
    op.create_index("ix_prank_sessions_user_id", "prank_sessions", ["user_id"])
    op.create_index("ix_prank_sessions_state", "prank_sessions", ["state"])
    op.create_index("ix_prank_sessions_created_at", "prank_sessions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_prank_sessions_created_at", table_name="prank_sessions")
    op.drop_index("ix_prank_sessions_state", table_name="prank_sessions")
    op.drop_index("ix_prank_sessions_user_id", table_name="prank_sessions")
    op.drop_table("prank_sessions")
    op.execute(sa.text(f"DROP TYPE {_ENUM_NAME}"))
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
