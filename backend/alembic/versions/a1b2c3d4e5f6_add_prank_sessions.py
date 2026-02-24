"""Add prank_sessions table

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-02-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
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
    # Create the PostgreSQL enum type before the table that references it.
    op.execute(
        sa.text(
            f"CREATE TYPE {_ENUM_NAME} AS ENUM "
            f"({', '.join(repr(v) for v in _ENUM_VALUES)})"
        )
    )

    op.create_table(
        "prank_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("sender_number", sa.String(), nullable=False),
        sa.Column("recipient_number", sa.String(), nullable=False),
        sa.Column("sender_call_control_id", sa.String(), nullable=True),
        sa.Column("recipient_call_control_id", sa.String(), nullable=True),
        sa.Column(
            "state",
            # create_type=False: the type already exists; do not re-create it.
            postgresql.ENUM(*_ENUM_VALUES, name=_ENUM_NAME, create_type=False),
            nullable=False,
            # text() produces DEFAULT 'CREATED'; a bare string would produce
            # DEFAULT CREATED (unquoted identifier), which Postgres rejects.
            server_default=sa.text("'CREATED'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Guard: BRIDGED / PLAYING_AUDIO / COMPLETED require both call legs.
        sa.CheckConstraint(
            "state NOT IN ('BRIDGED', 'PLAYING_AUDIO', 'COMPLETED')"
            " OR (sender_call_control_id IS NOT NULL"
            "     AND recipient_call_control_id IS NOT NULL)",
            name="ck_prank_sessions_bridged_requires_call_ids",
        ),
    )

    op.create_index("ix_prank_sessions_state", "prank_sessions", ["state"])
    op.create_index("ix_prank_sessions_created_at", "prank_sessions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_prank_sessions_created_at", table_name="prank_sessions")
    op.drop_index("ix_prank_sessions_state", table_name="prank_sessions")
    op.drop_table("prank_sessions")
    op.execute(sa.text(f"DROP TYPE {_ENUM_NAME}"))
