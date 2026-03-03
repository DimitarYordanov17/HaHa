package com.example.haha

sealed class SessionUiState {
    object Idle : SessionUiState()
    object Creating : SessionUiState()
    data class Active(val session: Session) : SessionUiState()
    object Completed : SessionUiState()
    data class Failed(val message: String) : SessionUiState()
}
