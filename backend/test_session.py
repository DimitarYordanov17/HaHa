import asyncio

from app.database import SessionLocal
from app.services.prank_session_service import PrankSessionService
from app.models import PrankSessionState


async def main():
    async with SessionLocal() as db:
        service = PrankSessionService(db)

        session = await service.create_session(
            sender_number="+359111111111",
            recipient_number="+359222222222",
        )
        print("Created:", session.state)

        await service.transition_state(session, PrankSessionState.CALLING_SENDER)
        print("State:", session.state)

        await service.transition_state(session, PrankSessionState.CALLING_RECIPIENT)
        print("State:", session.state)

        try:
            await service.transition_state(session, PrankSessionState.COMPLETED)
        except ValueError as e:
            print("Invalid transition blocked:", e)

        await service.transition_state(session, PrankSessionState.BRIDGED)
        print("State:", session.state)

        await service.transition_state(session, PrankSessionState.PLAYING_AUDIO)
        print("State:", session.state)

        await service.transition_state(session, PrankSessionState.COMPLETED)
        print("State:", session.state)

        try:
            await service.transition_state(session, PrankSessionState.FAILED)
        except ValueError as e:
            print("FAILED blocked after COMPLETED:", e)


asyncio.run(main())