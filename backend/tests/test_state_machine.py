"""Unit tests for PrankSessionService state machine transitions."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.models.prank_session import PrankSession, PrankSessionState
from app.services.prank_session_service import PrankSessionService


def _make_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _make_session(state: PrankSessionState, *, sender_ccid=None, recipient_ccid=None):
    obj = MagicMock(spec=PrankSession)
    obj.id = uuid4()
    obj.state = state
    obj.sender_call_control_id = sender_ccid
    obj.recipient_call_control_id = recipient_ccid
    return obj


# ---------------------------------------------------------------------------
# Valid forward transitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_transition_created_to_calling_sender():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(PrankSessionState.CREATED)

    await service.transition_state(session, PrankSessionState.CALLING_SENDER)

    assert session.state == PrankSessionState.CALLING_SENDER
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_valid_transition_calling_sender_to_calling_recipient():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(PrankSessionState.CALLING_SENDER)

    await service.transition_state(session, PrankSessionState.CALLING_RECIPIENT)

    assert session.state == PrankSessionState.CALLING_RECIPIENT


@pytest.mark.asyncio
async def test_valid_transition_calling_recipient_to_bridged():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(
        PrankSessionState.CALLING_RECIPIENT,
        sender_ccid="s-ccid",
        recipient_ccid="r-ccid",
    )

    await service.transition_state(session, PrankSessionState.BRIDGED)

    assert session.state == PrankSessionState.BRIDGED


@pytest.mark.asyncio
async def test_valid_transition_bridged_to_playing_audio():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(
        PrankSessionState.BRIDGED,
        sender_ccid="s-ccid",
        recipient_ccid="r-ccid",
    )

    await service.transition_state(session, PrankSessionState.PLAYING_AUDIO)

    assert session.state == PrankSessionState.PLAYING_AUDIO


@pytest.mark.asyncio
async def test_valid_transition_playing_audio_to_completed():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(
        PrankSessionState.PLAYING_AUDIO,
        sender_ccid="s-ccid",
        recipient_ccid="r-ccid",
    )

    await service.transition_state(session, PrankSessionState.COMPLETED)

    assert session.state == PrankSessionState.COMPLETED


# ---------------------------------------------------------------------------
# Invalid / skipped transitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_skip_transition_raises():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(PrankSessionState.CALLING_SENDER)

    with pytest.raises(ValueError, match="Invalid transition"):
        await service.transition_state(session, PrankSessionState.COMPLETED)

    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_backward_transition_raises():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(PrankSessionState.PLAYING_AUDIO, sender_ccid="s", recipient_ccid="r")

    with pytest.raises(ValueError, match="Invalid transition"):
        await service.transition_state(session, PrankSessionState.BRIDGED)


# ---------------------------------------------------------------------------
# FAILED transitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("from_state", [
    PrankSessionState.CALLING_SENDER,
    PrankSessionState.CALLING_RECIPIENT,
    PrankSessionState.BRIDGED,
    PrankSessionState.PLAYING_AUDIO,
])
async def test_failed_allowed_from_non_completed_states(from_state):
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(from_state)

    await service.transition_state(session, PrankSessionState.FAILED)

    assert session.state == PrankSessionState.FAILED


@pytest.mark.asyncio
async def test_failed_blocked_from_completed():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(PrankSessionState.COMPLETED)

    with pytest.raises(ValueError, match="Cannot transition from COMPLETED to FAILED"):
        await service.transition_state(session, PrankSessionState.FAILED)

    db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Terminal state protection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_completed_blocks_forward_transition():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(PrankSessionState.COMPLETED)

    with pytest.raises(ValueError):
        await service.transition_state(session, PrankSessionState.FAILED)


@pytest.mark.asyncio
async def test_failed_blocks_any_forward_transition():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(PrankSessionState.FAILED)

    # FAILED → COMPLETED is not in _ALLOWED_TRANSITIONS so it raises
    with pytest.raises(ValueError):
        await service.transition_state(session, PrankSessionState.COMPLETED)


# ---------------------------------------------------------------------------
# Bridged/PLAYING_AUDIO/COMPLETED require both call_control_ids
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("target_state", [
    PrankSessionState.BRIDGED,
    PrankSessionState.PLAYING_AUDIO,
    PrankSessionState.COMPLETED,
])
async def test_bridged_states_require_both_call_ids(target_state):
    """Transitioning to BRIDGED/PLAYING_AUDIO/COMPLETED without both IDs must fail."""
    db = _make_db()
    service = PrankSessionService(db)

    # Build a session that is one step before each target so the forward check passes
    predecessor = {
        PrankSessionState.BRIDGED: PrankSessionState.CALLING_RECIPIENT,
        PrankSessionState.PLAYING_AUDIO: PrankSessionState.BRIDGED,
        PrankSessionState.COMPLETED: PrankSessionState.PLAYING_AUDIO,
    }[target_state]

    session = _make_session(predecessor, sender_ccid=None, recipient_ccid=None)

    with pytest.raises(ValueError, match="without both call control IDs"):
        await service.transition_state(session, target_state)

    db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_call_control_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_sender_call_control_id():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(PrankSessionState.CALLING_SENDER)

    await service.set_call_control_id(session, "sender", "s-ccid-123")

    assert session.sender_call_control_id == "s-ccid-123"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_recipient_call_control_id():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(PrankSessionState.CALLING_RECIPIENT)

    await service.set_call_control_id(session, "recipient", "r-ccid-456")

    assert session.recipient_call_control_id == "r-ccid-456"


@pytest.mark.asyncio
async def test_set_call_control_id_invalid_leg_raises():
    db = _make_db()
    service = PrankSessionService(db)
    session = _make_session(PrankSessionState.CALLING_SENDER)

    with pytest.raises(ValueError, match="Invalid leg"):
        await service.set_call_control_id(session, "third_party", "x-ccid")
