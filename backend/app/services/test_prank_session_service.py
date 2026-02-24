import asyncio
import uuid

from app.database import async_session_maker
from app.services.prank_session_service import PrankSessionService
from app.models import PrankSessionState


async def main():
    async with async_session_maker() as db:
        service = PrankSessionService(db)

        # 1️⃣ Create session
        session = await service.create_session(
            sender_number="+359111111111",
            recipient_number="+359222222222",
        )
        print("Created:", session.state)

        # 2️⃣ Valid transition chain
        await service.transition_state(session, PrankSessionState.CALLING_SENDER)
        print("→", session.state)

        await service.transition_state(session, PrankSessionState.CALLING_RECIPIENT)
        print("→", session.state)

        # 3️⃣ Invalid transition (should fail)
        try:
            await service.transition_state(session, PrankSessionState.COMPLETED)
        except ValueError as e:
            print("Invalid transition blocked:", e)

        # 4️⃣ Continue valid chain
        await service.transition_state(session, PrankSessionState.BRIDGED)
        print("→", session.state)

        await service.transition_state(session, PrankSessionState.PLAYING_AUDIO)
        print("→", session.state)

        await service.transition_state(session, PrankSessionState.COMPLETED)
        print("→", session.state)

        # 5️⃣ FAILED after completed (should fail)
        try:
            await service.transition_state(session, PrankSessionState.FAILED)
        except ValueError as e:
            print("FAILED blocked after COMPLETED:", e)


asyncio.run(main())