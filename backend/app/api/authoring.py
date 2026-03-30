import logging
from fastapi import APIRouter, HTTPException

from app.schemas.prank_authoring import (
    CreateSessionResponse,
    GetSessionResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.authoring_store import authoring_store
from app.services.authoring_engine import process_turn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/authoring", tags=["authoring"])


@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_authoring_session():
    """Create a new prank authoring session and return its initial state."""
    session = authoring_store.create_session()
    return CreateSessionResponse(session=session)


@router.get("/sessions/{session_id}", response_model=GetSessionResponse)
async def get_authoring_session(session_id: str):
    """Return the current state of an authoring session."""
    session = authoring_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Authoring session not found")
    return GetSessionResponse(session=session)


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_authoring_message(session_id: str, body: SendMessageRequest):
    """
    Send a user message into the authoring session.

    This is the core endpoint for the guided prank authoring loop.
    Returns the assistant reply, updated prank draft, and session status.
    """
    session = authoring_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Authoring session not found")

    if session.is_complete:
        raise HTTPException(status_code=400, detail="Authoring session is already complete")

    try:
        assistant_reply = process_turn(authoring_store, session_id, body.content)
    except ValueError as exc:
        logger.exception("AuthoringEngine error for session %s", session_id)
        raise HTTPException(status_code=500, detail=str(exc))

    session = authoring_store.get_session(session_id)

    return SendMessageResponse(
        assistant_reply=assistant_reply,
        draft=session.draft,
        status=session.status,
        is_complete=session.is_complete,
        session=session,
    )
