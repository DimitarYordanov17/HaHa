package com.example.haha

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.haha.network.RetrofitClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class LoginViewModel(application: Application) : AndroidViewModel(application) {

    private val prefs = application.getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)

    val email = MutableStateFlow("")
    val password = MutableStateFlow("")

    private val _uiState = MutableStateFlow<LoginUiState>(LoginUiState.Idle)
    val uiState: StateFlow<LoginUiState> = _uiState

    fun login() {
        viewModelScope.launch {
            _uiState.value = LoginUiState.Loading
            try {
                val response = RetrofitClient.api.loginSuspend(email.value, password.value)
                if (response.isSuccessful) {
                    val token = response.body()?.accessToken
                    if (token == null) {
                        _uiState.value = LoginUiState.Error("Login succeeded but token was missing")
                        return@launch
                    }
                    prefs.edit().putString("access_token", token).apply()
                    _uiState.value = LoginUiState.Idle
                } else if (response.code() == 401) {
                    _uiState.value = LoginUiState.Error("Invalid credentials")
                } else {
                    _uiState.value = LoginUiState.Error("Login failed (${response.code()})")
                }
            } catch (e: Exception) {
                _uiState.value = LoginUiState.Error("Network error: ${e.message}")
            }
        }
    }
}
