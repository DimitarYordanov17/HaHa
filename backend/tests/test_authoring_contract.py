"""
Regression coverage for the System 1 LLM contract.

These tests guard against the live failure mode where the model returned
partial nested objects like {"caller": {"persona": "X", "tone": null}},
which broke validation against the original non-optional Caller model.
"""

import pytest
from pydantic import ValidationError

from app.schemas.prank_authoring import (
    AuthoringLLMResult,
    CallerUpdate,
    Caller,
    Constraints,
    ConstraintsUpdate,
    DraftField,
    DraftUpdate,
    PrankDraft,
    PrankType,
    Progression,
    ProgressionUpdate,
    TargetEffect,
    TargetEffectUpdate,
)
from app.services.authoring_engine import _merge_draft


# ---------------------------------------------------------------------------
# Schema: partial nested update models tolerate null subfields
# ---------------------------------------------------------------------------

class TestPartialUpdateModels:
    def test_caller_update_tone_null(self):
        """Model returns caller.tone=null — must not fail validation."""
        cu = CallerUpdate(persona="confused delivery driver", tone=None)
        assert cu.persona == "confused delivery driver"
        assert cu.tone is None

    def test_caller_update_both_absent(self):
        cu = CallerUpdate()
        assert cu.persona is None
        assert cu.tone is None

    def test_target_effect_update_emotion_null(self):
        teu = TargetEffectUpdate(intended_emotion=None, duration_seconds=30)
        assert teu.intended_emotion is None
        assert teu.duration_seconds == 30

    def test_progression_update_opening_null(self):
        pu = ProgressionUpdate(opening=None, escalation="raises stakes slightly")
        assert pu.opening is None

    def test_constraints_update_all_null(self):
        cu = ConstraintsUpdate()
        assert cu.avoid_topics is None
        assert cu.max_duration_seconds is None
        assert cu.safe_word is None


# ---------------------------------------------------------------------------
# Schema: DraftUpdate with partial nested objects parses cleanly
# ---------------------------------------------------------------------------

class TestDraftUpdateParsing:
    def test_draft_update_with_partial_caller(self):
        """Core regression: partial caller inside full DraftUpdate."""
        payload = {
            "prank_type": None,
            "caller": {"persona": "confused delivery driver", "tone": None},
            "target_effect": {"intended_emotion": None, "duration_seconds": None},
            "progression": None,
            "constraints": None,
            "context_notes": None,
        }
        du = DraftUpdate(**payload)
        assert du.caller is not None
        assert du.caller.persona == "confused delivery driver"
        assert du.caller.tone is None
        assert du.target_effect is not None
        assert du.target_effect.intended_emotion is None

    def test_draft_update_all_none(self):
        du = DraftUpdate()
        assert du.caller is None
        assert du.target_effect is None

    def test_draft_update_valid_prank_type(self):
        du = DraftUpdate(prank_type="Chaos")
        assert du.prank_type == PrankType.CHAOS

    def test_draft_update_invalid_prank_type_rejected(self):
        with pytest.raises(ValidationError):
            DraftUpdate(prank_type="NotARealType")


# ---------------------------------------------------------------------------
# Schema: missing_fields enum rejects dotted subfield values
# ---------------------------------------------------------------------------

class TestMissingFieldsVocabulary:
    def test_valid_missing_fields_accepted(self):
        result = AuthoringLLMResult(
            reply="What kind of prank?",
            draft_update=DraftUpdate(),
            missing_fields=[DraftField.CALLER, DraftField.TARGET_EFFECT],
            is_draft_complete=False,
            ready_for_handoff=False,
        )
        assert DraftField.CALLER in result.missing_fields

    def test_dotted_subfield_rejected(self):
        """'caller.tone' is not a valid DraftField — must be rejected."""
        with pytest.raises((ValidationError, ValueError)):
            AuthoringLLMResult(
                reply="Hi",
                draft_update=DraftUpdate(),
                missing_fields=["caller.tone"],  # invalid
                is_draft_complete=False,
                ready_for_handoff=False,
            )

    def test_empty_missing_fields_accepted(self):
        result = AuthoringLLMResult(
            reply="All done!",
            draft_update=DraftUpdate(),
            missing_fields=[],
            is_draft_complete=True,
            ready_for_handoff=True,
        )
        assert result.missing_fields == []


# ---------------------------------------------------------------------------
# Engine: _merge_draft handles partial nested updates correctly
# ---------------------------------------------------------------------------

class TestMergeDraftPartialUpdates:
    def _empty_draft(self) -> PrankDraft:
        return PrankDraft()

    def test_partial_caller_not_promoted_when_tone_missing(self):
        """CallerUpdate with tone=None must not create a broken Caller."""
        draft = self._empty_draft()
        update = DraftUpdate(caller=CallerUpdate(persona="confused driver", tone=None))
        result = _merge_draft(draft, update)
        assert result.caller is None  # can't build full Caller without tone

    def test_full_caller_promoted(self):
        draft = self._empty_draft()
        update = DraftUpdate(caller=CallerUpdate(persona="confused driver", tone="flustered"))
        result = _merge_draft(draft, update)
        assert result.caller is not None
        assert result.caller.persona == "confused driver"
        assert result.caller.tone == "flustered"

    def test_partial_target_effect_not_promoted_when_emotion_missing(self):
        draft = self._empty_draft()
        update = DraftUpdate(target_effect=TargetEffectUpdate(intended_emotion=None, duration_seconds=30))
        result = _merge_draft(draft, update)
        assert result.target_effect is None  # can't build without intended_emotion

    def test_full_target_effect_promoted(self):
        draft = self._empty_draft()
        update = DraftUpdate(target_effect=TargetEffectUpdate(intended_emotion="mild confusion"))
        result = _merge_draft(draft, update)
        assert result.target_effect is not None
        assert result.target_effect.intended_emotion == "mild confusion"
        assert result.target_effect.duration_seconds is None

    def test_progression_not_promoted_without_opening(self):
        draft = self._empty_draft()
        update = DraftUpdate(progression=ProgressionUpdate(opening=None, escalation="raises stakes"))
        result = _merge_draft(draft, update)
        assert result.progression is None

    def test_progression_promoted_with_opening(self):
        draft = self._empty_draft()
        update = DraftUpdate(progression=ProgressionUpdate(
            opening="Claims to be delivering a package",
            escalation=None,
        ))
        result = _merge_draft(draft, update)
        assert result.progression is not None
        assert result.progression.opening == "Claims to be delivering a package"
        assert result.progression.escalation is None

    def test_constraints_with_null_avoid_topics_handled(self):
        """ConstraintsUpdate.avoid_topics=None must not crash union logic."""
        draft = self._empty_draft()
        update = DraftUpdate(constraints=ConstraintsUpdate(avoid_topics=None, safe_word="pineapple"))
        result = _merge_draft(draft, update)
        assert result.constraints is not None
        assert result.constraints.avoid_topics == []
        assert result.constraints.safe_word == "pineapple"

    def test_existing_caller_not_overwritten(self):
        draft = PrankDraft(caller=Caller(persona="angry landlord", tone="stern"))
        update = DraftUpdate(caller=CallerUpdate(persona="new persona", tone="gentle"))
        result = _merge_draft(draft, update)
        assert result.caller.persona == "angry landlord"  # existing preserved


# ---------------------------------------------------------------------------
# Realistic live failure payload
# ---------------------------------------------------------------------------

class TestRealisticLivePayload:
    def test_live_failure_shape_now_parses(self):
        """
        Mirrors the failing response shape from the live OpenAI call:
        nested draft_update fields with explicit null subfields,
        and coarse missing_fields entries.
        """
        raw_json = """{
            "reply": "Got it! Who should the caller pretend to be, and what tone should they use?",
            "draft_update": {
                "prank_type": "Chaos",
                "caller": {"persona": null, "tone": null},
                "target_effect": {"intended_emotion": null, "duration_seconds": null},
                "progression": null,
                "constraints": null,
                "context_notes": "User wants a chaos-style prank"
            },
            "missing_fields": ["caller", "target_effect", "progression"],
            "is_draft_complete": false,
            "ready_for_handoff": false,
            "next_question": "Who should the caller pretend to be?",
            "notes": "Prank type inferred as Chaos. Need caller details next."
        }"""
        result = AuthoringLLMResult.parse_raw(raw_json)
        assert result.reply.startswith("Got it!")
        assert result.draft_update.prank_type == PrankType.CHAOS
        assert result.draft_update.caller is not None
        assert result.draft_update.caller.persona is None  # null tolerated
        assert DraftField.CALLER in result.missing_fields
        assert result.is_draft_complete is False

    def test_merge_of_live_failure_payload(self):
        """
        The realistic payload above should not crash _merge_draft and should
        only apply the fields that are actually populated.
        """
        du = DraftUpdate(
            prank_type=PrankType.CHAOS,
            caller=CallerUpdate(persona=None, tone=None),
            target_effect=TargetEffectUpdate(intended_emotion=None),
            context_notes="User wants a chaos-style prank",
        )
        result = _merge_draft(PrankDraft(), du)
        assert result.prank_type == PrankType.CHAOS
        assert result.caller is None       # partial with no subfields — not promoted
        assert result.target_effect is None  # no emotion — not promoted
        assert result.context_notes == "User wants a chaos-style prank"
