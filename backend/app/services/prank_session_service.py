from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prank_session import PrankSession, PrankSessionState

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
        self, sender_number: str, recipient_number: str
    ) -> PrankSession:
        prank_session = PrankSession(
            sender_number=sender_number,
            recipient_number=recipient_number,
            state=PrankSessionState.CREATED,
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
