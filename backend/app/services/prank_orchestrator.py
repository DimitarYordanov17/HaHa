import asyncio
import logging
import os
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models.prank_session import PrankSessionState
from app.services.prank_session_service import PrankSessionService
from app.services.telnyx_call_service import TelnyxCallService

logger = logging.getLogger(__name__)

_active_tasks: set[asyncio.Task] = set()
_session_locks: dict[UUID, asyncio.Lock] = {}


async def _call_timeout_worker(
    session_id: UUID,
    sender_call_control_id: str,
    recipient_call_control_id: str,
) -> None:
    try:
        duration = int(os.environ.get("MAX_CALL_DURATION_SECONDS", "300"))
        logger.info(
            "TIMEOUT_WORKER_STARTED session=%s duration=%s",
            session_id,
            duration,
        )
        await asyncio.sleep(duration)

        logger.info("Timeout triggered for session %s, hanging up both legs", session_id)
        telnyx = TelnyxCallService()
        for ccid in (sender_call_control_id, recipient_call_control_id):
            try:
                await telnyx.hangup_call(ccid)
                logger.info("Timeout: hangup issued for call_control_id=%s", ccid)
            except Exception:
                logger.warning("Timeout: hangup failed for call_control_id=%s (leg may already be down)", ccid)

        async with SessionLocal() as db:
            service = PrankSessionService(db)
            try:
                session = await service.get_session(session_id)
                if session.state == PrankSessionState.PLAYING_AUDIO:
                    await service.transition_state(session, PrankSessionState.COMPLETED)
                    logger.info("Timeout: session %s transitioned to COMPLETED", session_id)
                else:
                    logger.info(
                        "Timeout: session %s already in state %s, skipping transition",
                        session_id, session.state.value,
                    )
            except Exception:
                logger.exception("Timeout: state transition failed for session %s", session_id)
    except Exception:
        logger.exception("Timeout worker crashed for session %s", session_id)


class PrankEventType(str, Enum):
    LEG_ANSWERED = "LEG_ANSWERED"
    LEG_BRIDGED = "LEG_BRIDGED"
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
        lock = _session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            await self._handle_event_locked(session_id, event_type, leg, call_control_id)

    async def _handle_event_locked(
        self,
        session_id: UUID,
        event_type: PrankEventType,
        leg: str,
        call_control_id: Optional[str],
    ) -> None:
        if leg not in ("sender", "recipient"):
            raise ValueError(f"Invalid leg: {leg!r}. Must be 'sender' or 'recipient'")

        session = await self.service.get_session(session_id)
        state = session.state

        if state == PrankSessionState.CALLING_SENDER:
            if event_type == PrankEventType.LEG_ANSWERED and leg == "sender":
                logger.info("Session %s: sender leg answered", session_id)
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
                logger.info("Session %s: recipient leg answered", session_id)
                await self.service.set_call_control_id(session, "recipient", call_control_id)
                sender_call_control_id = session.sender_call_control_id
                bridged = await self.service.charge_and_transition_to_bridged(session)
                if not bridged:
                    logger.info("Session %s: insufficient credits, transitioned to FAILED", session_id)
                    return
                try:
                    await self.telnyx.bridge_calls(call_control_id, sender_call_control_id)
                    logger.info("Session %s: bridge requested, waiting for call.bridged confirmation", session_id)
                except Exception:
                    logger.exception("Session %s: bridge failed, transitioning to FAILED", session_id)
                    await self.service.transition_state(session, PrankSessionState.FAILED)
                    return
            elif event_type == PrankEventType.LEG_FAILED and leg == "recipient":
                await self.service.transition_state(session, PrankSessionState.FAILED)
            elif event_type == PrankEventType.LEG_HANGUP and leg == "sender":
                await self.service.transition_state(session, PrankSessionState.FAILED)
            else:
                raise ValueError(
                    f"Unexpected event {event_type} + leg={leg!r} in state {state.value}"
                )

        elif state == PrankSessionState.BRIDGED:
            if event_type == PrankEventType.LEG_BRIDGED and leg == "sender":
                logger.info("Session %s: bridge confirmed, waiting 300ms for media path, then starting playback", session_id)
                sender_call_control_id = session.sender_call_control_id
                recipient_call_control_id = session.recipient_call_control_id
                await asyncio.sleep(0.3)
                if session.state != PrankSessionState.BRIDGED:
                    logger.debug("Playback skipped: session %s not in BRIDGED state", session.id)
                    return
                await asyncio.gather(
                    self.telnyx.start_playback(sender_call_control_id, leg="sender", session_id=session.id),
                    self.telnyx.start_playback(recipient_call_control_id, leg="recipient", session_id=session.id),
                )
                await self.service.transition_state(session, PrankSessionState.PLAYING_AUDIO)
                task = asyncio.create_task(_call_timeout_worker(
                    session_id=session.id,
                    sender_call_control_id=sender_call_control_id,
                    recipient_call_control_id=recipient_call_control_id,
                ))
                _active_tasks.add(task)
                task.add_done_callback(_active_tasks.discard)
            elif event_type == PrankEventType.LEG_BRIDGED and leg == "recipient":
                logger.debug(
                    "Ignoring call.bridged from %s leg for session %s",
                    leg,
                    session.id,
                )
                return
            elif event_type in (PrankEventType.LEG_HANGUP, PrankEventType.LEG_FAILED):
                await self.service.transition_state(session, PrankSessionState.FAILED)
                logger.info("Session %s: leg lost before playback (event=%s leg=%s)", session_id, event_type, leg)
            else:
                raise ValueError(
                    f"Unexpected event {event_type} + leg={leg!r} in state {state.value}"
                )

        elif state == PrankSessionState.PLAYING_AUDIO:
            if event_type in (PrankEventType.LEG_HANGUP, PrankEventType.LEG_FAILED):
                await self.service.transition_state(session, PrankSessionState.COMPLETED)
                logger.info("Session %s: completed (event=%s leg=%s)", session_id, event_type, leg)
            elif event_type == PrankEventType.LEG_BRIDGED:
                logger.info("Session %s: late bridged event ignored (event=%s leg=%s)", session_id, event_type, leg)
            else:
                raise ValueError(
                    f"Unexpected event {event_type} + leg={leg!r} in state {state.value}"
                )

        elif state in (PrankSessionState.FAILED, PrankSessionState.COMPLETED):
            logger.debug(
                "Ignoring event %s for terminal session %s (state=%s)",
                event_type.value,
                session.id,
                state.value,
            )
            return

        else:
            raise ValueError(
                f"Unexpected event {event_type} + leg={leg!r} in state {state.value}"
            )
