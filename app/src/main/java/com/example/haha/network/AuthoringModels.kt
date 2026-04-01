package com.example.haha.network

import com.google.gson.annotations.SerializedName

// ─── Nested types ────────────────────────────────────────────────────────────

data class CallerDto(
    val persona: String,
    val tone: String,
)

data class TargetEffectDto(
    @SerializedName("intended_emotion") val intendedEmotion: String,
    @SerializedName("duration_seconds") val durationSeconds: Int?,
)

data class ProgressionDto(
    val opening: String,
    val escalation: String?,
    val resolution: String?,
)

data class ConstraintsDto(
    @SerializedName("avoid_topics") val avoidTopics: List<String>,
    @SerializedName("max_duration_seconds") val maxDurationSeconds: Int?,
    @SerializedName("safe_word") val safeWord: String?,
)

data class PrankDraftDto(
    @SerializedName("prank_type") val prankType: String?,
    val caller: CallerDto?,
    @SerializedName("target_effect") val targetEffect: TargetEffectDto?,
    val progression: ProgressionDto?,
    val constraints: ConstraintsDto?,
    @SerializedName("context_notes") val contextNotes: String?,
    @SerializedName("prank_title") val prankTitle: String?,
)

data class AuthoringMessageDto(
    val role: String,
    val content: String,
    val timestamp: String,
)

data class AuthoringSessionDto(
    val id: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
    val status: String,
    val draft: PrankDraftDto,
    val messages: List<AuthoringMessageDto>,
    @SerializedName("latest_assistant_question") val latestAssistantQuestion: String?,
    @SerializedName("is_complete") val isComplete: Boolean,
    @SerializedName("recipient_phone") val recipientPhone: String?,
)

// ─── Requests ────────────────────────────────────────────────────────────────

data class SendAuthoringMessageRequest(
    val content: String,
)

data class SetRecipientPhoneRequest(
    val phone: String,
)

// ─── Responses ───────────────────────────────────────────────────────────────

data class CreateAuthoringSessionResponse(
    val session: AuthoringSessionDto,
)

data class SendAuthoringMessageResponse(
    @SerializedName("assistant_reply") val assistantReply: String,
    val draft: PrankDraftDto,
    val status: String,
    @SerializedName("is_complete") val isComplete: Boolean,
    val session: AuthoringSessionDto,
)

data class GetAuthoringSessionResponse(
    val session: AuthoringSessionDto,
)

// ─── History / summary ───────────────────────────────────────────────────────

/**
 * Lightweight summary of one authoring session — used to render HistoryTab cards.
 * Returned by GET /authoring/sessions (list endpoint).
 */
data class AuthoringDraftSummaryDto(
    val id: String,
    val status: String,
    @SerializedName("is_complete") val isComplete: Boolean,
    @SerializedName("prank_title") val prankTitle: String?,
    @SerializedName("recipient_phone") val recipientPhone: String?,
    @SerializedName("launched_at") val launchedAt: String?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
    // Extracted fields for cheap card rendering — null when not yet authored
    @SerializedName("caller_persona") val callerPersona: String?,
    val opening: String?,
)

data class ListAuthoringSessionsResponse(
    val sessions: List<AuthoringDraftSummaryDto>,
)

// ─── Launch ──────────────────────────────────────────────────────────────────

data class LaunchAuthoringSessionResponse(
    val launched: Boolean,
    @SerializedName("launched_at") val launchedAt: String?,
)
