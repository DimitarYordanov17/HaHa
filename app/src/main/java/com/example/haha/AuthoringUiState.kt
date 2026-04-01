package com.example.haha

import com.example.haha.network.PrankDraftDto

data class AuthoringChatMsg(
    val id: Long,
    val role: String,   // "user" | "assistant"
    val text: String,
)

data class AuthoringUiState(
    val sessionId: String? = null,
    val messages: List<AuthoringChatMsg> = emptyList(),
    // draft is tracked internally but NEVER shown during authoring — only used for ready-state card
    val draft: PrankDraftDto? = null,
    val status: String = "collecting_info",
    val isReady: Boolean = false,
    val recipientPhone: String? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
    // Set to true after the user taps "Стартирай пранка" — prevents double-launch
    // and transitions the card to a sent confirmation state.
    val isLaunched: Boolean = false,
)
