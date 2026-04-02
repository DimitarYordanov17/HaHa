package com.example.haha

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.haha.network.AuthEventBus
import com.example.haha.network.MeResponse
import com.example.haha.network.RetrofitClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class AuthViewModel(application: Application) : AndroidViewModel(application) {

    private val prefs = application.getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)

    private val _state = MutableStateFlow<AuthState>(AuthState.Loading)
    val state: StateFlow<AuthState> = _state

    init {
        // Boot-time check: clear token on 401 or network failure (device offline at startup)
        checkAuth(clearTokenOnNetworkError = true)

        // Mid-session expiry: any protected endpoint returning 401 emits here via AuthInterceptor.
        // Guard: only handle this when we're Authenticated — boot-time 401s are handled by
        // checkAuth above and would show the session-expired banner incorrectly if not guarded.
        viewModelScope.launch {
            AuthEventBus.expired.collect {
                if (_state.value is AuthState.Authenticated) {
                    _state.value = AuthState.Unauthenticated(sessionExpired = true)
                }
            }
        }
    }

    // Called post-login. Token was just saved — only a 401 means it's invalid.
    // Network errors should not erase a token that the server just issued.
    fun refreshAuth() {
        _state.value = AuthState.Loading
        checkAuth(clearTokenOnNetworkError = false)
    }

    // Re-fetches /me and updates the user in the current Authenticated state.
    // Does NOT log out on any failure — treats all errors as transient.
    fun refreshUser() {
        if (_state.value !is AuthState.Authenticated) return
        viewModelScope.launch {
            try {
                val response = RetrofitClient.api.getMe()
                if (response.isSuccessful) {
                    _state.value = AuthState.Authenticated(response.body()!!.toUser())
                }
                // 401 here is handled by AuthInterceptor → AuthEventBus → the collector above
            } catch (_: Exception) {
                // transient error — keep current state
            }
        }
    }

    private fun checkAuth(clearTokenOnNetworkError: Boolean) {
        val token = prefs.getString("access_token", null)
        if (token == null) {
            _state.value = AuthState.Unauthenticated()
            return
        }

        viewModelScope.launch {
            try {
                val response = RetrofitClient.api.getMe()
                when {
                    response.isSuccessful -> {
                        _state.value = AuthState.Authenticated(response.body()!!.toUser())
                    }
                    response.code() == 401 -> {
                        // Token stored but rejected by server. AuthInterceptor already cleared
                        // the token from prefs. Show normal login (no session-expired banner).
                        _state.value = AuthState.Unauthenticated()
                    }
                    else -> {
                        // Non-401 HTTP error (5xx, etc.) — server problem, not an invalid token
                        _state.value = AuthState.Unauthenticated()
                    }
                }
            } catch (e: Exception) {
                // Network exception — token validity unknown
                if (clearTokenOnNetworkError) {
                    prefs.edit().remove("access_token").apply()
                }
                _state.value = AuthState.Unauthenticated()
            }
        }
    }

    private fun MeResponse.toUser() = User(
        email = email,
        phoneNumber = phoneNumber,
        credits = credits
    )
}
