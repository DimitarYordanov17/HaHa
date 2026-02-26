import asyncio
import os
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models.prank_session import PrankSessionState
from app.services.prank_session_service import PrankSessionService
from app.services.telnyx_call_service import TelnyxCallService

_active_tasks: set[asyncio.Task] = set()


async def _call_timeout_worker(
    session_id: UUID,
    sender_call_control_id: str,
    recipient_call_control_id: str,
) -> None:
    try:
        duration = int(os.environ.get("MAX_CALL_DURATION_SECONDS", "115"))
        print("KONDIO")
        await asyncio.sleep(duration)

        telnyx = TelnyxCallService()
        for ccid in (sender_call_control_id, recipient_call_control_id):
            try:
                await telnyx.hangup_call(ccid)
            except Exception as e:
                print(f"[timeout] hangup failed for {ccid}: {e}")

        async with SessionLocal() as db:
            service = PrankSessionService(db)
            try:
                session = await service.get_session(session_id)
                if session.state == PrankSessionState.PLAYING_AUDIO:
                    await service.transition_state(session, PrankSessionState.COMPLETED)
            except Exception as e:
                print(f"[timeout] state transition failed: {e}")
    except Exception as e:
        print(f"[timeout] worker crashed: {e}")


class PrankEventType(str, Enum):
    LEG_ANSWERED = "LEG_ANSWERED"
    LEG_FAILED = "LEG_FAILED"
    LEG_HANGUP = "LEG_HANGUP"


class PrankOrchestrator:
    def __init__(self, db: AsyncSession) -> None:
        self.service = PrankSessionService(db)
        self.telnyx = TelnyxCallService()

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
                await self.telnyx.create_outbound_call(
                    to_number=session.recipient_number,
                    from_number=session.sender_number,
                    session_id=session.id,
                    leg="recipient",
                )
            elif event_type == PrankEventType.LEG_FAILED and leg == "sender":
                await self.service.transition_state(session, PrankSessionState.FAILED)
            else:
                raise ValueError(
                    f"Unexpected event {event_type} + leg={leg!r} in state {state.value}"
                )

        elif state == PrankSessionState.CALLING_RECIPIENT:
            if event_type == PrankEventType.LEG_ANSWERED and leg == "recipient":
                await self.service.set_call_control_id(session, "recipient", call_control_id)
                sender_call_control_id = session.sender_call_control_id
                await self.service.transition_state(session, PrankSessionState.BRIDGED)
                try:
                    await self.telnyx.bridge_calls(sender_call_control_id, call_control_id)
                except Exception:
                    await self.service.transition_state(session, PrankSessionState.FAILED)
                    return
                await self.service.transition_state(session, PrankSessionState.PLAYING_AUDIO)
                await self.telnyx.start_playback(sender_call_control_id)
                task = asyncio.create_task(_call_timeout_worker(
                    session_id=session.id,
                    sender_call_control_id=sender_call_control_id,
                    recipient_call_control_id=call_control_id,
                ))
                _active_tasks.add(task)
                task.add_done_callback(_active_tasks.discard)
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
            print("call finished")

        else:
            raise ValueError(
                f"Unexpected event {event_type} + leg={leg!r} in state {state.value}"
            )
