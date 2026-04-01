package com.example.haha

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class AuthoringViewModel : ViewModel() {

    private val repository = AuthoringRepository()

    private val _state = MutableStateFlow(AuthoringUiState())
    val state: StateFlow<AuthoringUiState> = _state

    init {
        createSession()
    }

    private fun createSession() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)

            repository.createSession()
                .onSuccess { session ->
                    // Backend owns the welcome message — read from session.messages.
                    val messages = session.messages.mapIndexed { idx, msg ->
                        AuthoringChatMsg(
                            id = idx.toLong(),
                            role = msg.role,
                            text = msg.content,
                        )
                    }
                    _state.value = _state.value.copy(
                        sessionId = session.id,
                        messages = messages,
                        draft = session.draft,
                        status = session.status,
                        isReady = session.isComplete,
                        recipientPhone = session.recipientPhone,
                        isLoading = false,
                    )
                }
                .onFailure { e ->
                    _state.value = _state.value.copy(
                        isLoading = false,
                        error = e.message ?: "Не може да се стартира сесия",
                    )
                }
        }
    }

    fun sendMessage(content: String) {
        val sessionId = _state.value.sessionId ?: return
        if (_state.value.isLoading) return

        val userMsg = AuthoringChatMsg(
            id = System.currentTimeMillis(),
            role = "user",
            text = content,
        )
        _state.value = _state.value.copy(
            messages = _state.value.messages + userMsg,
            isLoading = true,
            error = null,
        )

        viewModelScope.launch {
            repository.sendMessage(sessionId, content)
                .onSuccess { response ->
                    val assistantMsg = AuthoringChatMsg(
                        id = System.currentTimeMillis(),
                        role = "assistant",
                        text = response.assistantReply,
                    )
                    _state.value = _state.value.copy(
                        messages = _state.value.messages + assistantMsg,
                        draft = response.draft,
                        status = response.status,
                        // Backend is authoritative: READY sessions always return is_complete=true.
                        // Editing turns also return is_complete=true (terminal status, never regresses).
                        isReady = response.isComplete,
                        isLoading = false,
                    )
                }
                .onFailure { e ->
                    _state.value = _state.value.copy(
                        isLoading = false,
                        error = e.message ?: "Грешка при изпращане",
                    )
                }
        }
    }

    fun submitRecipientPhone(phone: String) {
        val sessionId = _state.value.sessionId ?: return
        viewModelScope.launch {
            repository.setRecipientPhone(sessionId, phone)
                .onSuccess {
                    _state.value = _state.value.copy(recipientPhone = phone)
                }
                .onFailure { e ->
                    _state.value = _state.value.copy(error = e.message ?: "Грешка при запис на номера")
                }
        }
    }

    fun clearRecipientPhone() {
        // Clears local state only — next submitRecipientPhone() will overwrite backend value.
        _state.value = _state.value.copy(recipientPhone = null)
    }

    /**
     * Record the prank launch in the backend (audit trail) and trigger the
     * actual call via [onStartPrank].  Guard: does nothing if already launched.
     *
     * The backend call is best-effort — failure logs but does not block the
     * actual prank so the user experience is unaffected by a transient error.
     */
    fun launchPrank(onStartPrank: (String) -> Unit) {
        if (_state.value.isLaunched) return  // hard guard — prevent double-launch
        val sessionId = _state.value.sessionId ?: return
        val phone = _state.value.recipientPhone ?: return

        // Flip launched immediately (optimistic) so the button is disabled
        // before the coroutine starts.
        _state.value = _state.value.copy(isLaunched = true)

        viewModelScope.launch {
            // Record in backend — best-effort, never blocks the call
            repository.launchSession(sessionId)
                .onFailure { /* audit failure is non-fatal */ }
        }

        // Fire the actual System 2 call
        onStartPrank(phone)
    }

    fun reset() {
        _state.value = AuthoringUiState()
        createSession()
    }
}
