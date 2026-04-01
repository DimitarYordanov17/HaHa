package com.example.haha

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.haha.network.AuthoringDraftSummaryDto
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class HistoryUiState(
    val sessions: List<AuthoringDraftSummaryDto> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
)

class HistoryViewModel : ViewModel() {

    private val repository = AuthoringRepository()

    private val _state = MutableStateFlow(HistoryUiState())
    val state: StateFlow<HistoryUiState> = _state

    init {
        loadHistory()
    }

    fun loadHistory() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            repository.listSessions()
                .onSuccess { sessions ->
                    _state.value = _state.value.copy(
                        sessions = sessions,
                        isLoading = false,
                    )
                }
                .onFailure { e ->
                    _state.value = _state.value.copy(
                        isLoading = false,
                        error = e.message ?: "Грешка при зареждане на историята",
                    )
                }
        }
    }
}
