import asyncio
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import DATABASE_URL
from app.models.prank_session import PrankSessionState
from app.services.prank_session_service import PrankSessionService
from app.services.prank_orchestrator import (
    PrankOrchestrator,
    PrankEventType,
)


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        service = PrankSessionService(db)
        orchestrator = PrankOrchestrator(db)

        # 1. Create session
        session = await service.create_session(
            sender_number="+359111111111",
            recipient_number="+359222222222",
        )
        print("Created:", session.state)

        # 2. Move to CALLING_SENDER manually (start lifecycle)
        await service.transition_state(
            session, PrankSessionState.CALLING_SENDER
        )
        print("After CALLING_SENDER:", session.state)

        # 3. Sender answers
        await orchestrator.handle_event(
            session.id,
            PrankEventType.LEG_ANSWERED,
            leg="sender",
            call_control_id="sender-ccid",
        )
        print("After sender answered:", session.state)

        # 4. Recipient answers
        await orchestrator.handle_event(
            session.id,
            PrankEventType.LEG_ANSWERED,
            leg="recipient",
            call_control_id="recipient-ccid",
        )
        print("After recipient answered (should be PLAYING_AUDIO):", session.state)

        # 5. Hangup during audio
        await orchestrator.handle_event(
            session.id,
            PrankEventType.LEG_HANGUP,
            leg="sender",
        )
        print("After hangup (should be COMPLETED):", session.state)


if __name__ == "__main__":
    asyncio.run(main())