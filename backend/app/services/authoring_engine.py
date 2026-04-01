"""
System 1 authoring engine.

Architecture
------------
process_turn() is the single public entry point. It runs these phases in order:

  1. Load session / persist user message
  2. Build AuthoringContext  (_build_authoring_context)
  3. Call model              (_call_model)
  4. Validate / sanitize     (_sanitize_result)
  5. Merge into draft        (_merge_draft)
  6. Determine new status    (_determine_status)    ← backend-authoritative
  7. Persist state + reply

LLM integration
---------------
_call_model(ctx) is the only OpenAI-touching function. It uses:
  - build_provider_messages(ctx) from authoring_prompts for the messages array
  - OPENAI_MODEL env var for model name (default: gpt-4o-mini)
  - response_format json_object for structured output
  - AuthoringLLMResult.parse_raw() to validate the response

Everything outside _call_model (merge, sanitize, status, persistence) is unchanged.
"""

import logging
import os

import openai

from app.schemas.prank_authoring import (
    AuthoringContext,
    AuthoringLLMResult,
    AuthoringMessage,
    AuthoringSession,
    AuthoringStatus,
    Caller,
    Constraints,
    DraftField,
    DraftUpdate,
    MessageRole,
    PrankDraft,
    Progression,
    TargetEffect,
)
from app.services.authoring_prompts import build_provider_messages, build_system_prompt
from app.services.authoring_store import AuthoringStore

logger = logging.getLogger(__name__)

_RECENT_MESSAGES_WINDOW = 8  # messages included in model context


# =============================================================================
# Context builder
# =============================================================================

def _build_authoring_context(session: AuthoringSession, latest_user_message: str) -> AuthoringContext:
    missing = _compute_missing_fields(session.draft)
    user_turns = sum(1 for m in session.messages if m.role == MessageRole.USER)
    return AuthoringContext(
        system_instructions=build_system_prompt(),
        session_id=session.id,
        current_status=session.status,
        current_draft=session.draft,
        missing_fields=missing,
        recent_messages=session.messages[-_RECENT_MESSAGES_WINDOW:],
        latest_user_message=latest_user_message,
        total_user_turns=user_turns,
    )


# =============================================================================
# Draft completeness
# =============================================================================

def _compute_missing_fields(draft: PrankDraft) -> list[DraftField]:
    missing: list[DraftField] = []
    if draft.prank_type is None:
        missing.append(DraftField.PRANK_TYPE)
    if draft.caller is None:
        missing.append(DraftField.CALLER)
    if draft.target_effect is None:
        missing.append(DraftField.TARGET_EFFECT)
    if draft.progression is None:
        missing.append(DraftField.PROGRESSION)
    if draft.constraints is None:
        missing.append(DraftField.CONSTRAINTS)
    return missing


def _is_draft_complete(draft: PrankDraft) -> bool:
    """Backend-authoritative completeness. Constraints are optional."""
    return (
        draft.prank_type is not None
        and draft.caller is not None
        and draft.target_effect is not None
        and draft.progression is not None
    )


# =============================================================================
# OpenAI config helpers
# =============================================================================

# gpt-4o-mini: fast, cheap, reliable structured JSON output — right fit for
# guided authoring. Override with OPENAI_MODEL for stronger reasoning if needed.
_MODEL_DEFAULT = "gpt-4o-mini"


def _get_openai_client() -> openai.OpenAI:
    """
    Return an OpenAI client. Fails clearly if OPENAI_API_KEY is not set.
    Client is created per-call (OpenAI SDK is stateless; cost is negligible).
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set — authoring requires an OpenAI API key"
        )
    return openai.OpenAI(api_key=api_key)


def _get_model() -> str:
    return os.environ.get("OPENAI_MODEL", _MODEL_DEFAULT).strip() or _MODEL_DEFAULT


# =============================================================================
# Model call
# =============================================================================

def _call_model(ctx: AuthoringContext) -> AuthoringLLMResult:
    """
    Call OpenAI and return a validated AuthoringLLMResult.

    This is the only function with provider-specific code.
    The prompt/context payload is owned by authoring_prompts.build_provider_messages().
    """
    client = _get_openai_client()
    model = _get_model()
    messages = build_provider_messages(ctx)

    logger.debug(
        "AuthoringEngine._call_model: session=%s model=%s", ctx.session_id, model
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
        )
    except openai.OpenAIError as exc:
        logger.error(
            "AuthoringEngine._call_model: OpenAI error session=%s: %s",
            ctx.session_id, exc,
        )
        raise ValueError(f"Model call failed: {exc}") from exc

    content = response.choices[0].message.content

    try:
        return AuthoringLLMResult.parse_raw(content)
    except Exception as exc:
        logger.error(
            "AuthoringEngine._call_model: malformed model output session=%s content=%.500s",
            ctx.session_id, content,
        )
        raise ValueError(f"Model returned invalid AuthoringLLMResult: {exc}") from exc


# =============================================================================
# Result validation
# =============================================================================

def _sanitize_result(result: AuthoringLLMResult, session: AuthoringSession) -> AuthoringLLMResult:
    """
    Validate and sanitize raw model output before applying it.
    Backend rules override model claims where they conflict.
    """
    if result.ready_for_handoff:
        preview = _merge_draft(session.draft, result.draft_update)
        if not _is_draft_complete(preview):
            logger.warning(
                "session=%s: model claimed ready_for_handoff=True but draft incomplete after merge; overriding",
                session.id,
            )
            result = result.copy(update={"ready_for_handoff": False})

    return result


# =============================================================================
# Draft merge
# =============================================================================

def _merge_draft(current: PrankDraft, update: DraftUpdate, allow_overwrite: bool = False) -> PrankDraft:
    """
    Merge a DraftUpdate into the current PrankDraft.

    Rules (default, allow_overwrite=False):
    - None update fields are skipped (no field erasure allowed)
    - prank_type: accept only if not already set
    - caller: promote to full Caller only when both persona+tone are present;
              if caller already exists, fill any absent sub-fields only
    - target_effect: promote to full TargetEffect only when intended_emotion present;
                     if already exists, fill absent sub-fields only
    - progression: promote when opening is present; fill gaps only if already exists
    - constraints: union avoid_topics; fill other sub-fields only if absent
    - context_notes: append, never replace
    - prank_title: always overwrite (latest model-assigned title wins)

    When allow_overwrite=True (READY session in editing mode):
    - caller, target_effect, progression sub-fields are replaced (not just gap-filled)
    - allows user edits to actually change the draft and reflect on the card
    """
    patches: dict = {}

    if update.prank_type is not None and current.prank_type is None:
        patches["prank_type"] = update.prank_type

    if update.caller is not None:
        if current.caller is None:
            # Only promote to full Caller when both required fields are present
            if update.caller.persona is not None and update.caller.tone is not None:
                patches["caller"] = Caller(
                    persona=update.caller.persona,
                    tone=update.caller.tone,
                )
        else:
            sub = {}
            if update.caller.persona is not None:
                if allow_overwrite or not current.caller.persona:
                    sub["persona"] = update.caller.persona
            if update.caller.tone is not None:
                if allow_overwrite or not current.caller.tone:
                    sub["tone"] = update.caller.tone
            if sub:
                patches["caller"] = current.caller.copy(update=sub)

    if update.target_effect is not None:
        if current.target_effect is None:
            # Only promote when required field is present
            if update.target_effect.intended_emotion is not None:
                patches["target_effect"] = TargetEffect(
                    intended_emotion=update.target_effect.intended_emotion,
                    duration_seconds=update.target_effect.duration_seconds,
                )
        else:
            sub = {}
            if update.target_effect.intended_emotion is not None:
                if allow_overwrite or not current.target_effect.intended_emotion:
                    sub["intended_emotion"] = update.target_effect.intended_emotion
            if update.target_effect.duration_seconds is not None:
                if allow_overwrite or current.target_effect.duration_seconds is None:
                    sub["duration_seconds"] = update.target_effect.duration_seconds
            if sub:
                patches["target_effect"] = current.target_effect.copy(update=sub)

    if update.progression is not None:
        if current.progression is None:
            if update.progression.opening is not None:
                patches["progression"] = Progression(
                    opening=update.progression.opening,
                    escalation=update.progression.escalation,
                    resolution=update.progression.resolution,
                )
        else:
            if allow_overwrite:
                # Replace any sub-field the model provides
                sub = {k: v for k, v in update.progression.dict(exclude_none=True).items()}
            else:
                # Fill gaps only
                sub = {
                    k: v
                    for k, v in update.progression.dict(exclude_none=True).items()
                    if getattr(current.progression, k) is None
                }
            if sub:
                patches["progression"] = current.progression.copy(update=sub)

    if update.constraints is not None:
        if current.constraints is None:
            patches["constraints"] = Constraints(
                avoid_topics=update.constraints.avoid_topics or [],
                max_duration_seconds=update.constraints.max_duration_seconds,
                safe_word=update.constraints.safe_word,
            )
        else:
            merged_topics = list(
                set(current.constraints.avoid_topics)
                | set(update.constraints.avoid_topics or [])
            )
            sub = {
                k: v
                for k, v in update.constraints.dict(exclude_none=True).items()
                if k != "avoid_topics" and getattr(current.constraints, k) is None
            }
            patches["constraints"] = current.constraints.copy(
                update={"avoid_topics": merged_topics, **sub}
            )

    if update.context_notes is not None:
        existing = current.context_notes or ""
        if update.context_notes not in existing:
            patches["context_notes"] = (
                (existing + "\n" + update.context_notes).strip()
                if existing
                else update.context_notes
            )

    # prank_title: always overwrite — latest model-assigned title wins
    if update.prank_title is not None:
        patches["prank_title"] = update.prank_title

    return current.copy(update=patches) if patches else current


# =============================================================================
# Status determination — backend-authoritative
# =============================================================================

_MIN_USER_TURNS_BEFORE_READY = 2  # must have ≥2 user turns before prank can be marked ready


def _determine_status(
    merged_draft: PrankDraft,
    result: AuthoringLLMResult,
    session: AuthoringSession,
) -> tuple[AuthoringStatus, bool]:
    """
    Determine next status and completion flag.
    Backend rules are authoritative; model output is advisory.

    Product rule: a prank cannot become READY after only the first user message.
    The user must have sent at least _MIN_USER_TURNS_BEFORE_READY messages so
    there is at least one assistant shaping reply and one user response to it.
    """
    if session.status == AuthoringStatus.READY:
        return AuthoringStatus.READY, True  # terminal — never regress

    draft_complete = _is_draft_complete(merged_draft)

    if result.ready_for_handoff and draft_complete:
        user_turns = sum(1 for m in session.messages if m.role == MessageRole.USER)
        if user_turns < _MIN_USER_TURNS_BEFORE_READY:
            logger.info(
                "session=%s: ready_for_handoff=True suppressed — only %d user turn(s), "
                "need at least %d",
                session.id, user_turns, _MIN_USER_TURNS_BEFORE_READY,
            )
            return AuthoringStatus.COLLECTING_INFO, False
        return AuthoringStatus.READY, True

    if draft_complete:
        return AuthoringStatus.DRAFTING, False

    return AuthoringStatus.COLLECTING_INFO, False


# =============================================================================
# Main entry point
# =============================================================================

def process_turn(store: AuthoringStore, session_id: str, user_content: str) -> str:
    """
    Process one user turn in a System 1 authoring session.

    Phases:
      1. Load session and persist user message
      2. Build AuthoringContext for the model
      3. Call model (_call_model — OpenAI with authoring_prompts payload)
      4. Validate / sanitize result
      5. Merge result into current draft
      6. Determine new status (backend-authoritative)
      7. Persist updated state and assistant reply
    """
    # Phase 1 — load + persist user message
    session = store.get_session(session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")

    store.append_message(session_id, MessageRole.USER, user_content)
    session = store.get_session(session_id)

    logger.debug(
        "AuthoringEngine.process_turn: session=%s status=%s messages=%d",
        session_id, session.status, len(session.messages),
    )

    # Phase 2 — build context
    ctx = _build_authoring_context(session, user_content)

    # Phase 3 — call model
    raw_result = _call_model(ctx)

    # Phase 4 — validate / sanitize
    result = _sanitize_result(raw_result, session)

    # Phase 5 — merge draft
    # When the session is already READY (user is editing), allow the model to
    # overwrite already-set fields so the card reflects the actual edited state.
    editing = session.status == AuthoringStatus.READY
    new_draft = _merge_draft(session.draft, result.draft_update, allow_overwrite=editing)

    # Phase 6 — determine status
    new_status, is_complete = _determine_status(new_draft, result, session)

    # Phase 7 — persist
    store.update_session(
        session_id,
        draft=new_draft,
        status=new_status,
        latest_assistant_question=result.reply,
        is_complete=is_complete,
    )
    store.append_message(session_id, MessageRole.ASSISTANT, result.reply)

    return result.reply
