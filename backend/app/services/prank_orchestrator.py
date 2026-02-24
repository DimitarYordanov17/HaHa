from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prank_session import PrankSessionState
from app.services.prank_session_service import PrankSessionService


class PrankEventType(str, Enum):
    LEG_ANSWERED = "LEG_ANSWERED"
    LEG_FAILED = "LEG_FAILED"
    LEG_HANGUP = "LEG_HANGUP"


class PrankOrchestrator:
    def __init__(self, db: AsyncSession) -> None:
        self.service = PrankSessionService(db)

    async def handle_event(
        self,
        session_id: UUID,
        event_type: PrankEventType,
        leg: str,
        call_control_id: Optional[str] = None,
    ) -> None:
        if leg not in ("sender", "recipient"):
            raise ValueError(f"Invalid leg: {leg!r}. Must be 'sender' or 'recipient'")

        session = await self.service.get_session(session_id)
        state = session.state

        if state == PrankSessionState.CALLING_SENDER:
            if event_type == PrankEventType.LEG_ANSWERED and leg == "sender":
                await self.service.set_call_control_id(session, "sender", call_control_id)
                await self.service.transition_state(session, PrankSessionState.CALLING_RECIPIENT)
            elif event_type == PrankEventType.LEG_FAILED and leg == "sender":
                await self.service.transition_state(session, PrankSessionState.FAILED)
            else:
                raise ValueError(
                    f"Unexpected event {event_type} + leg={leg!r} in state {state.value}"
                )

        elif state == PrankSessionState.CALLING_RECIPIENT:
            if event_type == PrankEventType.LEG_ANSWERED and leg == "recipient":
                await self.service.set_call_control_id(session, "recipient", call_control_id)
                await self.service.transition_state(session, PrankSessionState.BRIDGED)
                await self.service.transition_state(session, PrankSessionState.PLAYING_AUDIO)
            elif event_type == PrankEventType.LEG_FAILED and leg == "recipient":
                await self.service.transition_state(session, PrankSessionState.FAILED)
            elif event_type == PrankEventType.LEG_HANGUP and leg == "sender":
                await self.service.transition_state(session, PrankSessionState.FAILED)
            else:
                raise ValueError(
                    f"Unexpected event {event_type} + leg={leg!r} in state {state.value}"
                )

        elif state == PrankSessionState.BRIDGED:
            raise ValueError(
                f"Unexpected event {event_type} + leg={leg!r} in state {state.value}"
            )

        elif state == PrankSessionState.PLAYING_AUDIO:
            if event_type in (PrankEventType.LEG_HANGUP, PrankEventType.LEG_FAILED):
                await self.service.transition_state(session, PrankSessionState.COMPLETED)
            else:
                raise ValueError(
                    f"Unexpected event {event_type} + leg={leg!r} in state {state.value}"
                )

        elif state in (PrankSessionState.FAILED, PrankSessionState.COMPLETED):
            raise ValueError(
                f"No events allowed in terminal state {state.value}"
            )

        else:
            raise ValueError(
                f"Unexpected event {event_type} + leg={leg!r} in state {state.value}"
            )
