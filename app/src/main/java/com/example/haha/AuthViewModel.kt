package com.example.haha

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.haha.network.RetrofitClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class AuthViewModel(application: Application) : AndroidViewModel(application) {

    private val prefs = application.getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)

    private val _state = MutableStateFlow<AuthState>(AuthState.Loading)
    val state: StateFlow<AuthState> = _state

    init {
        checkAuth()
    }

    private fun checkAuth() {
        val token = prefs.getString("access_token", null)
        if (token == null) {
            _state.value = AuthState.Unauthenticated
            return
        }

        viewModelScope.launch {
            try {
                val response = RetrofitClient.api.getMe("Bearer $token")
                if (response.isSuccessful) {
                    _state.value = AuthState.Authenticated
                } else {
                    prefs.edit().remove("access_token").apply()
                    _state.value = AuthState.Unauthenticated
                }
            } catch (e: Exception) {
                prefs.edit().remove("access_token").apply()
                _state.value = AuthState.Unauthenticated
            }
        }
    }
}
