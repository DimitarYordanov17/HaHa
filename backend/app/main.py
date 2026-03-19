import audioop
import base64
import json
import logging
import os
from contextlib import asynccontextmanager
from uuid import UUID

logging.basicConfig(level=logging.INFO)
# silence noisy third-party libs
for _noisy in ("httpcore", "httpx", "websockets", "asyncio"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.auth import hash_password, verify_password, create_access_token
from app.dependencies import get_current_user
from app.services.prank_orchestrator import PrankOrchestrator, PrankEventType
from app.services.stt.deepgram_stream import DeepgramStreamClient
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
    phone_number: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    phone_number: str
    credits: int

    class Config:
        from_attributes = True


class StartPrankRequest(BaseModel):
    recipient_phone_number: str


class DevStartPrankRequest(BaseModel):
    sender_phone: str
    recipient_phone: str


# ---------- shared prank helper ----------

async def _initiate_prank_session(
    sender_phone: str,
    recipient_phone: str,
    user_id: UUID,
    db: AsyncSession,
) -> UUID:
    service = PrankSessionService(db)
    session = await service.create_session(
        sender_number=sender_phone,
        recipient_number=recipient_phone,
        user_id=user_id,
    )
    logger.info(
        "Session %s created for sender=%s recipient=%s",
        session.id, sender_phone, recipient_phone,
    )
    await service.transition_state(session, PrankSessionState.CALLING_SENDER)

    telnyx = TelnyxCallService()
    await telnyx.create_outbound_call(
        to_number=sender_phone,
        from_number=os.environ["TELNYX_NUMBER"],
        session_id=session.id,
        leg="sender",
    )

    return session.id


# ---------- routes ----------

@app.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        phone_number=body.phone_number,
    )
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


@app.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/start-prank", status_code=200)
async def start_prank(
    body: StartPrankRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.credits < 1:
        raise HTTPException(status_code=400, detail="Insufficient credits")

    session_id = await _initiate_prank_session(
        sender_phone=current_user.phone_number,
        recipient_phone=body.recipient_phone_number,
        user_id=current_user.id,
        db=db,
    )
    return {"session_id": session_id}


# ---------- telnyx webhooks ----------

_TELNYX_EVENT_MAP = {
    "call.answered": PrankEventType.LEG_ANSWERED,
    "call.bridged": PrankEventType.LEG_BRIDGED,
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

@app.post("/dev/start-prank", status_code=200)
async def dev_start_prank(
    body: DevStartPrankRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.credits < 1:
        raise HTTPException(status_code=400, detail="Insufficient credits")

    session_id = await _initiate_prank_session(
        sender_phone=body.sender_phone,
        recipient_phone=body.recipient_phone,
        user_id=current_user.id,
        db=db,
    )
    return {"session_id": session_id}


# ---------- telnyx media stream (STT test) ----------

@app.websocket("/ws/telnyx-media")
async def telnyx_media_ws(websocket: WebSocket):
    """
    Receives Telnyx media stream events and pipes audio to Deepgram STT.
    MVP test only — transcripts are logged, not forwarded to the orchestrator.
    """
    print("[STT_WS] WebSocket connection incoming", flush=True)
    await websocket.accept()
    print("[STT_WS] WebSocket accepted", flush=True)
    logger.info("[STT_WS] WebSocket accepted")

    stt = DeepgramStreamClient()
    try:
        await stt.connect()
        print("[STT_WS] Deepgram connected", flush=True)
    except Exception as exc:
        print(f"[STT_WS] FAILED to connect to Deepgram: {exc}", flush=True)
        logger.exception("STT_WS failed to connect to Deepgram")
        await websocket.close()
        return

    frame_count = 0
    try:
        while True:
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("[STT_WS] JSON decode error, skipping")
                continue

            event = msg.get("event")

            if event == "connected":
                logger.info("[STT_WS] telnyx stream connected")

            elif event == "start":
                media_fmt = msg.get("start", {}).get("media_format", {})
                logger.info("[STT_WS] telnyx stream started encoding=%s sample_rate=%s",
                            media_fmt.get("encoding"), media_fmt.get("sample_rate"))

            elif event == "media":
                frame_count += 1
                payload_b64 = msg.get("media", {}).get("payload", "")
                if payload_b64:
                    pcma_bytes = base64.b64decode(payload_b64)
                    linear16_bytes = audioop.alaw2lin(pcma_bytes, 2)
                    await stt.send_audio(linear16_bytes)

            elif event == "stop":
                logger.info("[STT_WS] telnyx stream stopped after %d frames", frame_count)
                break

            else:
                logger.debug("[STT_WS] unknown event: %s", event)

    except WebSocketDisconnect:
        logger.info("[STT_WS] client disconnected after %d frames", frame_count)
    except Exception as exc:
        logger.exception("[STT_WS] unexpected error: %s", exc)
    finally:
        await stt.close()
        logger.info("[STT_WS] session ended, total frames forwarded: %d", frame_count)
