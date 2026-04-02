import re
from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator


# Accepted phone format (after stripping spaces, dashes, parentheses):
#   +359XXXXXXXXX  — international format, 9 digits after country code
# Local format (0XXXXXXXXX) is NOT accepted — Telnyx requires +359 prefix.
_PHONE_RE = re.compile(r"^\+359\d{9}$")


class PrankType(str, Enum):
    CHAOS = "Chaos"
    STRUCTURED_REALITY = "Structured Reality"
    MISTAKEN_CONTINUATION = "Mistaken Continuation"
    REVERSE_CONCERN = "Reverse Concern"
    MICRO_ACCUSATION = "Micro Accusation"
    USELESS_OFFER = "Useless Offer"


class Caller(BaseModel):
    persona: str   # e.g. "confused delivery driver", "wrong number caller"
    tone: str      # e.g. "confident", "apologetic", "urgent"


class TargetEffect(BaseModel):
    intended_emotion: str          # e.g. "mild confusion", "light panic"
    duration_seconds: Optional[int] = None


class Progression(BaseModel):
    opening: str
    escalation: Optional[str] = None
    resolution: Optional[str] = None


class Constraints(BaseModel):
    avoid_topics: list[str] = []
    max_duration_seconds: Optional[int] = None
    safe_word: Optional[str] = None


class PrankDraft(BaseModel):
    """Partial/incomplete prank spec built up across authoring turns."""
    prank_type: Optional[PrankType] = None
    caller: Optional[Caller] = None
    target_effect: Optional[TargetEffect] = None
    progression: Optional[Progression] = None
    constraints: Optional[Constraints] = None
    context_notes: Optional[str] = None  # free-form notes from user turns
    prank_title: Optional[str] = None    # short product-style label, e.g. "Обурканият куриер"


class PrankPackage(BaseModel):
    """Fully realized prank spec ready for System 2 execution."""
    prank_type: PrankType
    caller: Caller
    target_effect: TargetEffect
    progression: Progression
    constraints: Constraints
    script_notes: str


# ---------- LLM contract ----------

class DraftField(str, Enum):
    """Constrained vocabulary for tracking incomplete draft fields."""
    PRANK_TYPE = "prank_type"
    CALLER = "caller"
    TARGET_EFFECT = "target_effect"
    PROGRESSION = "progression"
    CONSTRAINTS = "constraints"
    CONTEXT_NOTES = "context_notes"


class CallerUpdate(BaseModel):
    """Partial caller update — all fields optional so the model can omit unknowns."""
    persona: Optional[str] = None
    tone: Optional[str] = None


class TargetEffectUpdate(BaseModel):
    """Partial target-effect update — all fields optional."""
    intended_emotion: Optional[str] = None
    duration_seconds: Optional[int] = None


class ProgressionUpdate(BaseModel):
    """Partial progression update — all fields optional."""
    opening: Optional[str] = None
    escalation: Optional[str] = None
    resolution: Optional[str] = None


class ConstraintsUpdate(BaseModel):
    """Partial constraints update — all fields optional."""
    avoid_topics: Optional[list[str]] = None
    max_duration_seconds: Optional[int] = None
    safe_word: Optional[str] = None


class DraftUpdate(BaseModel):
    """
    Partial draft changes the LLM is allowed to propose.
    Kept separate from PrankDraft so merge rules can distinguish
    'intentionally absent' from 'not yet set'.
    All nested types are update variants with fully optional fields so
    partial responses (e.g. caller.tone=null) never fail validation.
    """
    prank_type: Optional[PrankType] = None
    caller: Optional[CallerUpdate] = None
    target_effect: Optional[TargetEffectUpdate] = None
    progression: Optional[ProgressionUpdate] = None
    constraints: Optional[ConstraintsUpdate] = None
    context_notes: Optional[str] = None
    prank_title: Optional[str] = None   # short product-style label set by model when ready


class AuthoringLLMResult(BaseModel):
    """
    Strict structured output contract for one System 1 authoring turn.
    The model must return this shape; backend validates before applying.
    """
    reply: str                           # assistant reply shown to the user
    draft_update: DraftUpdate            # proposed partial draft changes
    missing_fields: list[DraftField]     # fields still needed (informational)
    is_draft_complete: bool              # model's assessment — backend re-checks authoritatively
    ready_for_handoff: bool              # model signals completion — backend validates before accepting
    next_question: Optional[str] = None  # next question if authoring is not done
    notes: Optional[str] = None          # optional model reasoning (never shown to user)


class AuthoringStatus(str, Enum):
    COLLECTING_INFO = "collecting_info"  # gathering user requirements
    DRAFTING = "drafting"                # draft built, awaiting user confirmation/revision
    READY = "ready"                      # prank finalized and ready to launch


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class AuthoringMessage(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime


class AuthoringContext(BaseModel):
    """
    Packaged input for one authoring model turn.
    Internal — never serialized to the API. Lives here to avoid circular imports
    between authoring_engine and authoring_prompts.
    """
    system_instructions: str
    session_id: str
    current_status: AuthoringStatus
    current_draft: PrankDraft
    missing_fields: list[DraftField]
    recent_messages: list[AuthoringMessage]
    latest_user_message: str
    total_user_turns: int   # used by stub; real LLM reads history directly


class AuthoringSession(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    status: AuthoringStatus
    draft: PrankDraft
    messages: list[AuthoringMessage]
    latest_assistant_question: Optional[str] = None
    is_complete: bool = False
    recipient_phone: Optional[str] = None


# ---------- request / response models ----------

class CreateSessionResponse(BaseModel):
    session: AuthoringSession


class GetSessionResponse(BaseModel):
    session: AuthoringSession


class SendMessageRequest(BaseModel):
    content: str


class SendMessageResponse(BaseModel):
    assistant_reply: str
    draft: PrankDraft
    status: AuthoringStatus
    is_complete: bool
    session: AuthoringSession


class SetPhoneRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone_format(cls, v: str) -> str:
        # Normalize: strip spaces, dashes, and parentheses (keep + prefix if present)
        normalized = re.sub(r"[\s\-()]", "", v)
        if not _PHONE_RE.match(normalized):
            raise ValueError(
                "Невалиден телефонен номер — въведи с +359, без нулата (пример: +359879052660)"
            )
        return normalized


# ---------- history / summary models ----------

class AuthoringDraftSummary(BaseModel):
    """
    Lightweight read model for the history list.
    Returned by GET /authoring/sessions — one row per authoring session,
    fields extracted from the full draft so the client can render a card
    without deserialising the full session.
    """
    id: str
    status: AuthoringStatus
    is_complete: bool
    prank_title: Optional[str]
    recipient_phone: Optional[str]
    launched_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    # Extracted from PrankDraft for cheap rendering — null when not yet set
    caller_persona: Optional[str] = None
    opening: Optional[str] = None        # first 80 chars of progression.opening


class ListSessionsResponse(BaseModel):
    sessions: list[AuthoringDraftSummary]


class LaunchSessionResponse(BaseModel):
    launched: bool
    launched_at: Optional[datetime]
