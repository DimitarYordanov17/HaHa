import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from app.schemas.prank_authoring import (
    AuthoringSession,
    AuthoringStatus,
    AuthoringMessage,
    MessageRole,
    PrankDraft,
)

logger = logging.getLogger(__name__)


class AuthoringStore:
    """
    In-memory store for System 1 authoring sessions.

    Swap this for a DB-backed store when persistence is needed —
    the interface is the only contract the engine and router depend on.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, AuthoringSession] = {}

    def create_session(self) -> AuthoringSession:
        now = datetime.now(timezone.utc)
        welcome = AuthoringMessage(
            role=MessageRole.ASSISTANT,
            content="Разкажи ми — какъв пранк искаш да изиграем?",
            timestamp=now,
        )
        session = AuthoringSession(
            id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            status=AuthoringStatus.COLLECTING_INFO,
            draft=PrankDraft(),
            messages=[welcome],
            latest_assistant_question=None,
            is_complete=False,
            recipient_phone=None,
        )
        self._sessions[session.id] = session
        logger.info("AuthoringStore: created session %s", session.id)
        return session

    def get_session(self, session_id: str) -> Optional[AuthoringSession]:
        return self._sessions.get(session_id)

    def append_message(self, session_id: str, role: MessageRole, content: str) -> None:
        session = self._sessions[session_id]
        session.messages.append(
            AuthoringMessage(
                role=role,
                content=content,
                timestamp=datetime.now(timezone.utc),
            )
        )
        session.updated_at = datetime.now(timezone.utc)

    def set_recipient_phone(self, session_id: str, phone: str) -> None:
        session = self._sessions[session_id]
        session.recipient_phone = phone
        session.updated_at = datetime.now(timezone.utc)
        logger.info("AuthoringStore: set recipient_phone for session %s", session_id)

    def update_session(
        self,
        session_id: str,
        *,
        draft: Optional[PrankDraft] = None,
        status: Optional[AuthoringStatus] = None,
        latest_assistant_question: Optional[str] = None,
        is_complete: Optional[bool] = None,
    ) -> AuthoringSession:
        session = self._sessions[session_id]
        if draft is not None:
            session.draft = draft
        if status is not None:
            session.status = status
        if latest_assistant_question is not None:
            session.latest_assistant_question = latest_assistant_question
        if is_complete is not None:
            session.is_complete = is_complete
        session.updated_at = datetime.now(timezone.utc)
        return session


# Module-level singleton — same pattern as PrankOrchestrator._session_locks
authoring_store = AuthoringStore()
