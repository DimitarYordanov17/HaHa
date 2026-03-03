package com.example.haha

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class SessionViewModel : ViewModel() {

    private val repository = SessionRepository()

    private val _state = MutableStateFlow<SessionUiState>(SessionUiState.Idle)
    val state: StateFlow<SessionUiState> = _state

    private var pollingJob: Job? = null

    fun startSession(recipient: String) {
        val current = _state.value
        if (current is SessionUiState.Creating || current is SessionUiState.Active) return

        viewModelScope.launch {
            _state.value = SessionUiState.Creating

            repository.createSession(recipient)
                .onSuccess { session ->
                    _state.value = SessionUiState.Active(session)
                    startPolling(session.id)
                }
                .onFailure { e ->
                    _state.value = SessionUiState.Failed(e.message ?: "Failed to create session")
                }
        }
    }

    private fun startPolling(sessionId: String) {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (isActive) {
                delay(POLL_INTERVAL_MS)

                repository.getSession(sessionId)
                    .onSuccess { session ->
                        when (session.state) {
                            BackendSessionState.COMPLETED -> {
                                _state.value = SessionUiState.Completed
                                return@launch
                            }
                            BackendSessionState.FAILED -> {
                                _state.value = SessionUiState.Failed("Session failed")
                                return@launch
                            }
                            else -> {
                                val current = _state.value
                                if (current !is SessionUiState.Active || current.session != session) {
                                    _state.value = SessionUiState.Active(session)
                                }
                            }
                        }
                    }
                // onFailure: transient network error — silently retry next tick
            }
        }
    }

    fun reset() {
        pollingJob?.cancel()
        pollingJob = null
        _state.value = SessionUiState.Idle
    }

    override fun onCleared() {
        super.onCleared()
        pollingJob?.cancel()
    }

    companion object {
        private const val POLL_INTERVAL_MS = 1500L
    }
}
