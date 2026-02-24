import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class PrankSessionState(enum.Enum):
    CREATED = "CREATED"
    CALLING_SENDER = "CALLING_SENDER"
    CALLING_RECIPIENT = "CALLING_RECIPIENT"
    BRIDGED = "BRIDGED"
    PLAYING_AUDIO = "PLAYING_AUDIO"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PrankSession(Base):
    __tablename__ = "prank_sessions"
    __table_args__ = (
        Index("ix_prank_sessions_state", "state"),
        Index("ix_prank_sessions_created_at", "created_at"),
        # Guard against rows that reach a bridged/active/terminal state without
        # both legs being established.  Applied at the DB layer so ORM bypasses
        # (raw SQL, background workers) cannot violate the invariant.
        CheckConstraint(
            "state NOT IN ('BRIDGED', 'PLAYING_AUDIO', 'COMPLETED')"
            " OR (sender_call_control_id IS NOT NULL"
            "     AND recipient_call_control_id IS NOT NULL)",
            name="ck_prank_sessions_bridged_requires_call_ids",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    sender_number: Mapped[str] = mapped_column(String, nullable=False)
    recipient_number: Mapped[str] = mapped_column(String, nullable=False)
    sender_call_control_id: Mapped[str | None] = mapped_column(String, nullable=True)
    recipient_call_control_id: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[PrankSessionState] = mapped_column(
        SAEnum(PrankSessionState, name="pranksessionstate"),
        nullable=False,
        # DB-level default so rows inserted via raw SQL also start in CREATED.
        # text() is required: a bare string would emit DEFAULT CREATED (unquoted
        # identifier) instead of DEFAULT 'CREATED' (string literal).
        server_default=text("'CREATED'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        # onupdate causes SQLAlchemy to include `updated_at = now()` in the SET
        # clause of every ORM-issued UPDATE; `now()` is evaluated server-side by
        # PostgreSQL.  Raw SQL that bypasses the ORM will not refresh this column
        # — acceptable for V1.  A trigger can be added later if needed.
        onupdate=func.now(),
        nullable=False,
    )
