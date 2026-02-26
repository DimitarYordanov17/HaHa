"""Unit tests for PrankOrchestrator.handle_event and _call_timeout_worker."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.prank_session import PrankSessionState
from app.services.prank_orchestrator import PrankOrchestrator, PrankEventType, _call_timeout_worker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_session(state: PrankSessionState, *, sender_ccid="s-ccid", recipient_ccid=None):
    s = MagicMock()
    s.id = uuid4()
    s.state = state
    s.sender_number = "+1111"
    s.recipient_number = "+2222"
    s.sender_call_control_id = sender_ccid
    s.recipient_call_control_id = recipient_ccid
    return s


def _make_orchestrator():
    """Return a PrankOrchestrator with fully mocked service and telnyx."""
    db = AsyncMock()
    orch = PrankOrchestrator.__new__(PrankOrchestrator)
    orch.service = AsyncMock()
    orch.telnyx = AsyncMock()
    return orch


# ---------------------------------------------------------------------------
# Terminal state: COMPLETED / FAILED → events are silently ignored
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_ignored_when_session_completed():
    orch = _make_orchestrator()
    session = _make_mock_session(PrankSessionState.COMPLETED)
    orch.service.get_session = AsyncMock(return_value=session)

    await orch.handle_event(uuid4(), PrankEventType.LEG_HANGUP, leg="sender")

    orch.service.transition_state.assert_not_awaited()
    orch.telnyx.hangup_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_event_ignored_when_session_failed():
    orch = _make_orchestrator()
    session = _make_mock_session(PrankSessionState.FAILED)
    orch.service.get_session = AsyncMock(return_value=session)

    await orch.handle_event(uuid4(), PrankEventType.LEG_HANGUP, leg="sender")

    orch.service.transition_state.assert_not_awaited()


# ---------------------------------------------------------------------------
# CALLING_SENDER state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calling_sender_leg_answered_transitions_and_dials_recipient():
    orch = _make_orchestrator()
    session = _make_mock_session(PrankSessionState.CALLING_SENDER, sender_ccid=None)
    orch.service.get_session = AsyncMock(return_value=session)

    session_id = session.id
    await orch.handle_event(session_id, PrankEventType.LEG_ANSWERED, leg="sender", call_control_id="s-ccid")

    orch.service.set_call_control_id.assert_awaited_once_with(session, "sender", "s-ccid")
    orch.service.transition_state.assert_awaited_once_with(session, PrankSessionState.CALLING_RECIPIENT)
    orch.telnyx.create_outbound_call.assert_awaited_once()


@pytest.mark.asyncio
async def test_calling_sender_leg_failed_transitions_to_failed():
    orch = _make_orchestrator()
    session = _make_mock_session(PrankSessionState.CALLING_SENDER)
    orch.service.get_session = AsyncMock(return_value=session)

    await orch.handle_event(session.id, PrankEventType.LEG_FAILED, leg="sender")

    orch.service.transition_state.assert_awaited_once_with(session, PrankSessionState.FAILED)


@pytest.mark.asyncio
async def test_calling_sender_unexpected_event_raises():
    orch = _make_orchestrator()
    session = _make_mock_session(PrankSessionState.CALLING_SENDER)
    orch.service.get_session = AsyncMock(return_value=session)

    with pytest.raises(ValueError):
        await orch.handle_event(session.id, PrankEventType.LEG_ANSWERED, leg="recipient")


# ---------------------------------------------------------------------------
# CALLING_RECIPIENT state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calling_recipient_leg_answered_bridges_then_plays():
    orch = _make_orchestrator()
    session = _make_mock_session(PrankSessionState.CALLING_RECIPIENT, sender_ccid="s-ccid")
    orch.service.get_session = AsyncMock(return_value=session)

    mock_task = MagicMock()
    mock_task.add_done_callback = MagicMock()

    def _stub_create_task(coro):
        # Close the unawaited coroutine so it is not leaked (create_task is
        # mocked and won't schedule it, which would trigger RuntimeWarning).
        coro.close()
        return mock_task

    with patch("app.services.prank_orchestrator.asyncio.create_task", side_effect=_stub_create_task) as mock_create_task:
        await orch.handle_event(session.id, PrankEventType.LEG_ANSWERED, leg="recipient", call_control_id="r-ccid")

    orch.service.set_call_control_id.assert_awaited_once_with(session, "recipient", "r-ccid")

    transition_calls = orch.service.transition_state.await_args_list
    assert any(call.args == (session, PrankSessionState.BRIDGED) for call in transition_calls)
    assert any(call.args == (session, PrankSessionState.PLAYING_AUDIO) for call in transition_calls)

    orch.telnyx.bridge_calls.assert_awaited_once()
    orch.telnyx.start_playback.assert_awaited_once()
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_calling_recipient_bridge_failure_transitions_to_failed():
    orch = _make_orchestrator()
    session = _make_mock_session(PrankSessionState.CALLING_RECIPIENT, sender_ccid="s-ccid")
    orch.service.get_session = AsyncMock(return_value=session)
    orch.telnyx.bridge_calls = AsyncMock(side_effect=Exception("bridge error"))

    with patch("app.services.prank_orchestrator.asyncio.create_task") as mock_create_task:
        await orch.handle_event(session.id, PrankEventType.LEG_ANSWERED, leg="recipient", call_control_id="r-ccid")
        mock_create_task.assert_not_called()

    transition_calls = orch.service.transition_state.await_args_list
    final_states = [call.args[1] for call in transition_calls]
    assert PrankSessionState.FAILED in final_states
    assert PrankSessionState.PLAYING_AUDIO not in final_states


@pytest.mark.asyncio
async def test_calling_recipient_leg_failed_transitions_to_failed():
    orch = _make_orchestrator()
    session = _make_mock_session(PrankSessionState.CALLING_RECIPIENT)
    orch.service.get_session = AsyncMock(return_value=session)

    await orch.handle_event(session.id, PrankEventType.LEG_FAILED, leg="recipient")

    orch.service.transition_state.assert_awaited_once_with(session, PrankSessionState.FAILED)


@pytest.mark.asyncio
async def test_calling_recipient_sender_hangup_transitions_to_failed():
    orch = _make_orchestrator()
    session = _make_mock_session(PrankSessionState.CALLING_RECIPIENT)
    orch.service.get_session = AsyncMock(return_value=session)

    await orch.handle_event(session.id, PrankEventType.LEG_HANGUP, leg="sender")

    orch.service.transition_state.assert_awaited_once_with(session, PrankSessionState.FAILED)


# ---------------------------------------------------------------------------
# PLAYING_AUDIO state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", [PrankEventType.LEG_HANGUP, PrankEventType.LEG_FAILED])
async def test_playing_audio_hangup_or_failed_completes_session(event_type):
    orch = _make_orchestrator()
    session = _make_mock_session(PrankSessionState.PLAYING_AUDIO, sender_ccid="s", recipient_ccid="r")
    orch.service.get_session = AsyncMock(return_value=session)

    await orch.handle_event(session.id, event_type, leg="sender")

    orch.service.transition_state.assert_awaited_once_with(session, PrankSessionState.COMPLETED)


@pytest.mark.asyncio
async def test_playing_audio_unexpected_event_raises():
    orch = _make_orchestrator()
    session = _make_mock_session(PrankSessionState.PLAYING_AUDIO)
    orch.service.get_session = AsyncMock(return_value=session)

    with pytest.raises(ValueError):
        await orch.handle_event(session.id, PrankEventType.LEG_ANSWERED, leg="sender")


# ---------------------------------------------------------------------------
# Invalid leg
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_leg_raises_immediately():
    orch = _make_orchestrator()
    # get_session should not even be called
    with pytest.raises(ValueError, match="Invalid leg"):
        await orch.handle_event(uuid4(), PrankEventType.LEG_ANSWERED, leg="unknown")

    orch.service.get_session.assert_not_awaited()


# ---------------------------------------------------------------------------
# _call_timeout_worker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeout_worker_hangs_up_and_completes_session():
    session_id = uuid4()
    mock_session = MagicMock()
    mock_session.state = PrankSessionState.PLAYING_AUDIO

    mock_service = AsyncMock()
    mock_service.get_session = AsyncMock(return_value=mock_session)
    mock_service.transition_state = AsyncMock()

    mock_telnyx = AsyncMock()

    mock_db_cm = AsyncMock()
    mock_db_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_db_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.prank_orchestrator.asyncio.sleep", new=AsyncMock()),
        patch("app.services.prank_orchestrator.TelnyxCallService", return_value=mock_telnyx),
        patch("app.services.prank_orchestrator.SessionLocal", return_value=mock_db_cm),
        patch("app.services.prank_orchestrator.PrankSessionService", return_value=mock_service),
        patch.dict("os.environ", {"MAX_CALL_DURATION_SECONDS": "1"}),
    ):
        await _call_timeout_worker(session_id, "s-ccid", "r-ccid")

    assert mock_telnyx.hangup_call.await_count == 2
    mock_service.transition_state.assert_awaited_once_with(mock_session, PrankSessionState.COMPLETED)


@pytest.mark.asyncio
async def test_timeout_worker_skips_transition_when_already_completed():
    session_id = uuid4()
    mock_session = MagicMock()
    mock_session.state = PrankSessionState.COMPLETED

    mock_service = AsyncMock()
    mock_service.get_session = AsyncMock(return_value=mock_session)

    mock_telnyx = AsyncMock()
    mock_db_cm = AsyncMock()
    mock_db_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_db_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.prank_orchestrator.asyncio.sleep", new=AsyncMock()),
        patch("app.services.prank_orchestrator.TelnyxCallService", return_value=mock_telnyx),
        patch("app.services.prank_orchestrator.SessionLocal", return_value=mock_db_cm),
        patch("app.services.prank_orchestrator.PrankSessionService", return_value=mock_service),
        patch.dict("os.environ", {"MAX_CALL_DURATION_SECONDS": "1"}),
    ):
        await _call_timeout_worker(session_id, "s-ccid", "r-ccid")

    mock_service.transition_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_timeout_worker_hangup_failure_does_not_crash():
    """If hangup raises for one or both legs, the worker must not propagate."""
    session_id = uuid4()
    mock_session = MagicMock()
    mock_session.state = PrankSessionState.PLAYING_AUDIO

    mock_service = AsyncMock()
    mock_service.get_session = AsyncMock(return_value=mock_session)

    mock_telnyx = AsyncMock()
    mock_telnyx.hangup_call = AsyncMock(side_effect=Exception("already hung up"))

    mock_db_cm = AsyncMock()
    mock_db_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_db_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.prank_orchestrator.asyncio.sleep", new=AsyncMock()),
        patch("app.services.prank_orchestrator.TelnyxCallService", return_value=mock_telnyx),
        patch("app.services.prank_orchestrator.SessionLocal", return_value=mock_db_cm),
        patch("app.services.prank_orchestrator.PrankSessionService", return_value=mock_service),
        patch.dict("os.environ", {"MAX_CALL_DURATION_SECONDS": "1"}),
    ):
        # Must not raise
        await _call_timeout_worker(session_id, "s-ccid", "r-ccid")


@pytest.mark.asyncio
async def test_timeout_worker_state_transition_failure_does_not_crash():
    """If the DB state transition raises, the worker must not propagate."""
    session_id = uuid4()
    mock_session = MagicMock()
    mock_session.state = PrankSessionState.PLAYING_AUDIO

    mock_service = AsyncMock()
    mock_service.get_session = AsyncMock(return_value=mock_session)
    mock_service.transition_state = AsyncMock(side_effect=Exception("db error"))

    mock_telnyx = AsyncMock()
    mock_db_cm = AsyncMock()
    mock_db_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_db_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.prank_orchestrator.asyncio.sleep", new=AsyncMock()),
        patch("app.services.prank_orchestrator.TelnyxCallService", return_value=mock_telnyx),
        patch("app.services.prank_orchestrator.SessionLocal", return_value=mock_db_cm),
        patch("app.services.prank_orchestrator.PrankSessionService", return_value=mock_service),
        patch.dict("os.environ", {"MAX_CALL_DURATION_SECONDS": "1"}),
    ):
        # Must not raise
        await _call_timeout_worker(session_id, "s-ccid", "r-ccid")
