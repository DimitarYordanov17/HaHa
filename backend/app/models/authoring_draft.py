import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AuthoringDraft(Base):
    """
    Persistent record for one System 1 authoring session.

    The in-memory AuthoringStore is the hot path for the engine; this table
    is the write-through backing store that survives server restarts and
    provides the data for the user's prank history.

    draft_json / messages_json store the serialized Pydantic models as JSON
    text.  JSONB would allow server-side querying but Text is sufficient for
    V1 — the app fetches full rows and deserialises in Python.
    """

    __tablename__ = "authoring_drafts"
    __table_args__ = (
        Index("ix_authoring_drafts_user_id", "user_id"),
        Index("ix_authoring_drafts_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Mirrors AuthoringStatus enum values ("collecting_info", "drafting", "ready")
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="collecting_info",
    )
    # Full PrankDraft JSON — updated on every turn
    draft_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="'{}'")
    # Full message list JSON — updated on every turn
    messages_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="'[]'")
    recipient_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    # Denormalised from PrankDraft.prank_title — allows cheap list rendering
    # without deserialising draft_json for every row.
    prank_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Set the moment the user taps "Стартирай пранка".  Null = not yet launched.
    launched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
