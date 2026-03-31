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

    fun reset() {
        _state.value = AuthoringUiState()
        createSession()
    }
}
