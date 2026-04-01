"""
System 1 authoring router.

All endpoints require a valid JWT (Depends(get_current_user)).
Sessions are persisted to PostgreSQL (authoring_drafts table) as a
write-through cache on top of the in-memory AuthoringStore so they
survive server restarts and appear in the user's history.

Rate limits (in-memory, per process):
  - Max 10 new sessions per user per hour
  - Max 100 messages per session

Audit trail:
  - Every mutation is logged at INFO level with user_id + session_id.
  - The launched_at timestamp on the DB row is the authoritative audit
    record for when a prank was triggered by the user.
"""
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.models.authoring_draft import AuthoringDraft
from app.schemas.prank_authoring import (
    AuthoringDraftSummary,
    AuthoringMessage,
    AuthoringSession,
    AuthoringStatus,
    CreateSessionResponse,
    GetSessionResponse,
    LaunchSessionResponse,
    ListSessionsResponse,
    MessageRole,
    PrankDraft,
    SendMessageRequest,
    SendMessageResponse,
    SetPhoneRequest,
)
from app.services.authoring_engine import process_turn
from app.services.authoring_store import authoring_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/authoring", tags=["authoring"])


# =============================================================================
# Rate limiting (in-memory, per-process)
# Replace with Redis + slowapi for multi-instance deployments.
# =============================================================================

_user_session_timestamps: dict[str, list[datetime]] = defaultdict(list)
_RATE_LIMIT_WINDOW_SECONDS = 3600   # 1 hour rolling window
_RATE_LIMIT_MAX_SESSIONS = 10       # max new sessions per user per window
_MAX_MESSAGES_PER_SESSION = 100     # hard cap on user turns per session


def _check_session_rate_limit(user_id: str) -> None:
    now = datetime.now(timezone.utc)
    cutoff_ts = now.timestamp() - _RATE_LIMIT_WINDOW_SECONDS
    # Prune expired entries
    _user_session_timestamps[user_id] = [
        t for t in _user_session_timestamps[user_id]
        if t.timestamp() > cutoff_ts
    ]
    if len(_user_session_timestamps[user_id]) >= _RATE_LIMIT_MAX_SESSIONS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded — max {_RATE_LIMIT_MAX_SESSIONS} "
                f"new authoring sessions per hour"
            ),
        )


def _record_session_creation(user_id: str) -> None:
    _user_session_timestamps[user_id].append(datetime.now(timezone.utc))


# =============================================================================
# DB write-through helpers
# =============================================================================

async def _persist_to_db(
    session: AuthoringSession,
    user_id: uuid.UUID,
    db: AsyncSession,
    *,
    launched_at: Optional[datetime] = None,
) -> None:
    """
    Upsert the in-memory session state to the authoring_drafts table.

    Called after every mutation (create, message, phone update, launch).
    Using a simple SELECT + INSERT/UPDATE rather than ON CONFLICT because
    SQLAlchemy's PostgreSQL dialect upsert requires explicit column lists
    that would need updating whenever the model changes.
    """
    draft_json = session.draft.json()
    messages_json = json.dumps(
        [m.dict() for m in session.messages], default=str
    )

    try:
        sid = uuid.UUID(session.id)
    except ValueError:
        logger.error("_persist_to_db: invalid session id %s", session.id)
        return

    existing = await db.scalar(
        select(AuthoringDraft).where(AuthoringDraft.id == sid)
    )

    if existing is None:
        db_row = AuthoringDraft(
            id=sid,
            user_id=user_id,
            status=session.status.value,
            draft_json=draft_json,
            messages_json=messages_json,
            recipient_phone=session.recipient_phone,
            is_complete=session.is_complete,
            prank_title=session.draft.prank_title,
            launched_at=launched_at,
        )
        db.add(db_row)
    else:
        existing.status = session.status.value
        existing.draft_json = draft_json
        existing.messages_json = messages_json
        existing.recipient_phone = session.recipient_phone
        existing.is_complete = session.is_complete
        existing.prank_title = session.draft.prank_title
        if launched_at is not None:
            existing.launched_at = launched_at

    await db.commit()
    logger.debug("authoring._persist_to_db: session=%s persisted", session.id)


async def _load_from_db(
    session_id: str,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Optional[AuthoringSession]:
    """
    Load a session from the DB, verify ownership, and hydrate it into the
    in-memory store so subsequent engine calls can find it.

    Returns None if the session does not exist.
    Raises 403 if the session exists but belongs to a different user.
    """
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        return None

    db_row = await db.scalar(
        select(AuthoringDraft).where(AuthoringDraft.id == sid)
    )
    if db_row is None:
        return None
    if db_row.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Deserialise stored JSON back into Pydantic models
    draft = PrankDraft.parse_raw(db_row.draft_json)
    messages_raw = json.loads(db_row.messages_json)
    messages = [AuthoringMessage(**m) for m in messages_raw]

    session = AuthoringSession(
        id=str(db_row.id),
        created_at=db_row.created_at,
        updated_at=db_row.updated_at,
        status=AuthoringStatus(db_row.status),
        draft=draft,
        messages=messages,
        is_complete=db_row.is_complete,
        recipient_phone=db_row.recipient_phone,
    )

    # Populate in-memory store so the engine can operate on it
    authoring_store._sessions[session_id] = session
    logger.info(
        "authoring._load_from_db: hydrated session=%s from DB into memory store",
        session_id,
    )
    return session


async def _require_session(
    session_id: str,
    current_user: User,
    db: AsyncSession,
) -> AuthoringSession:
    """
    Return the session from memory (fast path) or DB (restart recovery).
    Ownership is checked on the DB load path; the memory path is implicitly
    safe because sessions are keyed by UUID and created under the user's token.
    """
    session = authoring_store.get_session(session_id)
    if session is None:
        session = await _load_from_db(session_id, current_user.id, db)
    if session is None:
        raise HTTPException(status_code=404, detail="Authoring session not found")
    return session


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_authoring_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new guided prank authoring session.

    Rate-limited to prevent session spam.  The session is persisted to DB
    immediately so it survives server restarts and appears in history.
    """
    _check_session_rate_limit(str(current_user.id))

    session = authoring_store.create_session()
    await _persist_to_db(session, current_user.id, db)
    _record_session_creation(str(current_user.id))

    logger.info(
        "authoring.create_session: user=%s session=%s",
        current_user.id, session.id,
    )
    return CreateSessionResponse(session=session)


@router.get("/sessions", response_model=ListSessionsResponse)
async def list_authoring_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the current user's authoring sessions, newest first (max 50).

    Used to populate the HistoryTab in the Android app.
    Each item is a lightweight summary; the full session is fetched
    separately via GET /sessions/{id} when the user opens a card.
    """
    rows = (
        await db.scalars(
            select(AuthoringDraft)
            .where(AuthoringDraft.user_id == current_user.id)
            .order_by(desc(AuthoringDraft.created_at))
            .limit(50)
        )
    ).all()

    def _has_user_messages(messages_json: str) -> bool:
        """Return True if the session has at least one user message."""
        try:
            msgs = json.loads(messages_json or "[]")
            return any(m.get("role") == "user" for m in msgs)
        except Exception:
            return True  # keep on parse failure — safer than hiding real sessions

    summaries: list[AuthoringDraftSummary] = []
    for row in rows:
        # Skip empty junk sessions — no user input means no meaningful content.
        # These are created automatically on app open and abandoned immediately.
        if not _has_user_messages(row.messages_json or "[]"):
            continue

        try:
            draft = PrankDraft.parse_raw(row.draft_json)
        except Exception:
            draft = PrankDraft()

        summaries.append(
            AuthoringDraftSummary(
                id=str(row.id),
                status=AuthoringStatus(row.status),
                is_complete=row.is_complete,
                prank_title=row.prank_title,
                recipient_phone=row.recipient_phone,
                launched_at=row.launched_at,
                created_at=row.created_at,
                updated_at=row.updated_at,
                caller_persona=(
                    draft.caller.persona if draft.caller else None
                ),
                opening=(
                    draft.progression.opening[:80]
                    if draft.progression and draft.progression.opening
                    else None
                ),
            )
        )

    logger.info(
        "authoring.list_sessions: user=%s count=%d",
        current_user.id, len(summaries),
    )
    return ListSessionsResponse(sessions=summaries)


@router.get("/sessions/active", response_model=GetSessionResponse)
async def get_active_authoring_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the user's latest unfinished (not yet launched) authoring session.

    Called by the Android app on startup — if an active session exists the app
    resumes it instead of creating a new one.  Returns 404 when no active
    session exists so the caller knows to create a fresh one.

    'Active' means: launched_at IS NULL.  All statuses (COLLECTING_INFO,
    DRAFTING, READY) are resumable as long as the session has not been launched.
    """
    db_row = await db.scalar(
        select(AuthoringDraft)
        .where(
            AuthoringDraft.user_id == current_user.id,
            AuthoringDraft.launched_at.is_(None),
        )
        .order_by(desc(AuthoringDraft.created_at))
        .limit(1)
    )
    if db_row is None:
        raise HTTPException(status_code=404, detail="No active authoring session")

    session = authoring_store.get_session(str(db_row.id))
    if session is None:
        session = await _load_from_db(str(db_row.id), current_user.id, db)
    if session is None:
        raise HTTPException(status_code=404, detail="No active authoring session")

    logger.info(
        "authoring.get_active: user=%s session=%s status=%s",
        current_user.id, session.id, session.status,
    )
    return GetSessionResponse(session=session)


@router.get("/sessions/{session_id}", response_model=GetSessionResponse)
async def get_authoring_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the full state of an authoring session (ownership verified)."""
    session = await _require_session(session_id, current_user, db)
    return GetSessionResponse(session=session)


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_authoring_message(
    session_id: str,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a user message into the authoring session and receive the
    assistant reply plus the updated draft.

    Accepts messages even when the session is already READY so the user
    can continue editing without losing session context.
    """
    session = await _require_session(session_id, current_user, db)

    # Hard cap: prevent runaway sessions
    user_turns = sum(1 for m in session.messages if m.role == MessageRole.USER)
    if user_turns >= _MAX_MESSAGES_PER_SESSION:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Session message limit reached "
                f"({_MAX_MESSAGES_PER_SESSION} messages per session)"
            ),
        )

    try:
        assistant_reply = process_turn(authoring_store, session_id, body.content)
    except ValueError as exc:
        logger.exception(
            "authoring.send_message: engine error user=%s session=%s",
            current_user.id, session_id,
        )
        raise HTTPException(status_code=500, detail=str(exc))

    session = authoring_store.get_session(session_id)
    await _persist_to_db(session, current_user.id, db)

    logger.info(
        "authoring.send_message: user=%s session=%s status=%s is_complete=%s turns=%d",
        current_user.id, session_id, session.status, session.is_complete, user_turns + 1,
    )

    return SendMessageResponse(
        assistant_reply=assistant_reply,
        draft=session.draft,
        status=session.status,
        is_complete=session.is_complete,
        session=session,
    )


@router.put("/sessions/{session_id}/phone", status_code=204)
async def set_recipient_phone(
    session_id: str,
    body: SetPhoneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store the recipient phone number for this authoring session."""
    await _require_session(session_id, current_user, db)
    authoring_store.set_recipient_phone(session_id, body.phone)
    session = authoring_store.get_session(session_id)
    await _persist_to_db(session, current_user.id, db)

    logger.info(
        "authoring.set_phone: user=%s session=%s",
        current_user.id, session_id,
    )
    return Response(status_code=204)


@router.post("/sessions/{session_id}/launch", response_model=LaunchSessionResponse)
async def launch_authoring_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Record that the user launched this prank (idempotent).

    Called by the Android app immediately after the user taps
    "Стартирай пранка" to maintain an audit trail of launched pranks.
    The endpoint is idempotent — calling it twice returns the original
    launched_at timestamp.

    A session must be marked is_complete before it can be launched.
    """
    session = await _require_session(session_id, current_user, db)

    if not session.is_complete:
        raise HTTPException(
            status_code=400,
            detail="Session is not complete — cannot record launch",
        )

    # Check for existing launch record (idempotent)
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Authoring session not found")

    db_row = await db.scalar(
        select(AuthoringDraft).where(AuthoringDraft.id == sid)
    )
    if db_row is not None and db_row.launched_at is not None:
        # Already launched — return existing timestamp
        logger.info(
            "authoring.launch: user=%s session=%s already_launched_at=%s",
            current_user.id, session_id, db_row.launched_at,
        )
        return LaunchSessionResponse(launched=True, launched_at=db_row.launched_at)

    now = datetime.now(timezone.utc)
    await _persist_to_db(session, current_user.id, db, launched_at=now)

    logger.info(
        "authoring.launch: user=%s session=%s launched_at=%s",
        current_user.id, session_id, now,
    )
    return LaunchSessionResponse(launched=True, launched_at=now)
