import logging
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prank_session import PrankSession, PrankSessionState
from app.models.user import User

logger = logging.getLogger(__name__)

# Valid forward transitions. FAILED is handled separately (allowed from any
# non-COMPLETED state) so it does not appear as a value here.
_ALLOWED_TRANSITIONS: dict[PrankSessionState, PrankSessionState] = {
    PrankSessionState.CREATED: PrankSessionState.CALLING_SENDER,
    PrankSessionState.CALLING_SENDER: PrankSessionState.CALLING_RECIPIENT,
    PrankSessionState.CALLING_RECIPIENT: PrankSessionState.BRIDGED,
    PrankSessionState.BRIDGED: PrankSessionState.PLAYING_AUDIO,
    PrankSessionState.PLAYING_AUDIO: PrankSessionState.COMPLETED,
}


class PrankSessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(
        self, sender_number: str, recipient_number: str, user_id: uuid.UUID
    ) -> PrankSession:
        prank_session = PrankSession(
            sender_number=sender_number,
            recipient_number=recipient_number,
            state=PrankSessionState.CREATED,
            user_id=user_id,
        )
        self.session.add(prank_session)
        await self.session.commit()
        await self.session.refresh(prank_session)
        return prank_session

    async def get_session(self, session_id: UUID) -> PrankSession:
        result = await self.session.execute(
            select(PrankSession).where(PrankSession.id == session_id)
        )
        prank_session = result.scalar_one_or_none()
        if prank_session is None:
            raise ValueError(f"PrankSession {session_id} not found")
        return prank_session

    async def transition_state(
        self, session: PrankSession, new_state: PrankSessionState
    ) -> None:
        if session.state == new_state:
            logger.debug(
                "Skipping duplicate transition: session=%s state=%s",
                session.id,
                new_state.value,
            )
            return

        current = session.state

        if new_state == PrankSessionState.FAILED:
            if current == PrankSessionState.COMPLETED:
                raise ValueError(
                    f"Cannot transition from {current.value} to FAILED"
                )
        else:
            allowed_next = _ALLOWED_TRANSITIONS.get(current)
            if allowed_next != new_state:
                raise ValueError(
                    f"Invalid transition: {current.value} → {new_state.value}"
                )

        _REQUIRES_BOTH_IDS = {
            PrankSessionState.BRIDGED,
            PrankSessionState.PLAYING_AUDIO,
            PrankSessionState.COMPLETED,
        }
        if new_state in _REQUIRES_BOTH_IDS:
            if session.sender_call_control_id is None or session.recipient_call_control_id is None:
                raise ValueError(
                    f"Cannot transition to {new_state.value} without both call control IDs set"
                )

        session.state = new_state
        await self.session.commit()
        await self.session.refresh(session)

    async def charge_and_transition_to_bridged(self, session: PrankSession) -> bool:
        """Atomically charge 1 credit and transition to BRIDGED.

        Idempotent: if session.charged is already True, skips deduction and
        still transitions to BRIDGED (handles duplicate webhook delivery).

        Returns True on success, False if the user had insufficient credits
        (session is set to FAILED and committed before returning).
        """
        if session.charged:
            logger.debug("Session %s already charged", session.id)
            return True

        if session.state == PrankSessionState.BRIDGED:
            return session

        if not session.charged:
            user = await self.session.get(User, session.user_id)
            if user.credits < 1:
                session.state = PrankSessionState.FAILED
                await self.session.commit()
                return False
            user.credits -= 1
            session.charged = True

        session.state = PrankSessionState.BRIDGED
        await self.session.commit()
        await self.session.refresh(session)
        return True

    async def set_call_control_id(
        self, session: PrankSession, leg: str, call_control_id: str
    ) -> None:
        if leg == "sender":
            session.sender_call_control_id = call_control_id
        elif leg == "recipient":
            session.recipient_call_control_id = call_control_id
        else:
            raise ValueError(f"Invalid leg: {leg!r}. Must be 'sender' or 'recipient'")

        await self.session.commit()
        await self.session.refresh(session)
