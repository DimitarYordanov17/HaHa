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
    val draft: PrankDraftDto? = null,
    val status: String = "collecting_info",
    val isReady: Boolean = false,
    val isLoading: Boolean = false,
    val error: String? = null,
)
