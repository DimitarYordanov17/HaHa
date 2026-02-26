import base64
import json
import logging
import os
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.auth import hash_password, verify_password, create_access_token
from app.dependencies import get_current_user
from app.services.prank_orchestrator import PrankOrchestrator, PrankEventType
from app.services.prank_session_service import PrankSessionService
from app.services.telnyx_call_service import TelnyxCallService
from app.models.prank_session import PrankSessionState

from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if "MAX_CALL_DURATION_SECONDS" not in os.environ:
        raise RuntimeError(
            "Required environment variable MAX_CALL_DURATION_SECONDS is not set"
        )
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
# ---------- schemas ----------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- routes ----------

@app.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.commit()

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@app.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == form_data.username))
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@app.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}


# ---------- telnyx webhooks ----------

_TELNYX_EVENT_MAP = {
    "call.answered": PrankEventType.LEG_ANSWERED,
    "call.hangup": PrankEventType.LEG_HANGUP,
    "call.failed": PrankEventType.LEG_FAILED,
}


@app.post("/webhooks/telnyx", status_code=200)
async def telnyx_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()

    try:
        data = body["data"]
    except (KeyError, TypeError):
        logger.warning("Telnyx webhook missing 'data' field")
        return {"status": "ignored"}

    event_type = data.get("event_type")
    prank_event = _TELNYX_EVENT_MAP.get(event_type)
    if prank_event is None:
        return {"status": "ignored"}

    try:
        payload = data["payload"]
        call_control_id = payload["call_control_id"]
        client_state = json.loads(base64.b64decode(payload["client_state"]))
        leg = client_state["leg"]
        session_id = UUID(client_state["session_id"])
    except Exception:
        logger.exception("Telnyx webhook: failed to parse payload for event_type=%s", event_type)
        return {"status": "ignored"}

    try:
        orchestrator = PrankOrchestrator(db)
        await orchestrator.handle_event(
            session_id=session_id,
            event_type=prank_event,
            leg=leg,
            call_control_id=call_control_id,
        )
    except ValueError:
        logger.exception(
            "Telnyx webhook: orchestrator rejected event event_type=%s session_id=%s leg=%s",
            event_type, session_id, leg,
        )
        return {"status": "ignored"}

    return {"status": "ok"}


# ---------- dev endpoints ----------

class StartPrankRequest(BaseModel):
    sender_phone: str
    recipient_phone: str


@app.post("/dev/start-prank", status_code=200)
async def dev_start_prank(
    body: StartPrankRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PrankSessionService(db)
    session = await service.create_session(
        sender_number=body.sender_phone,
        recipient_number=body.recipient_phone,
    )
    logger.info("Session %s created for sender=%s recipient=%s", session.id, body.sender_phone, body.recipient_phone)
    await service.transition_state(session, PrankSessionState.CALLING_SENDER)

    telnyx = TelnyxCallService()
    await telnyx.create_outbound_call(
        to_number=body.sender_phone,
        from_number=os.environ["TELNYX_NUMBER"],
        session_id=session.id,
        leg="sender",
    )

    return {"session_id": session.id}
