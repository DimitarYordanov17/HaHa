package com.example.haha

sealed class AuthState {
    object Loading : AuthState()
    // sessionExpired = true when the token expired mid-session (not on a fresh app open)
    data class Unauthenticated(val sessionExpired: Boolean = false) : AuthState()
    data class Authenticated(val user: User) : AuthState()
}
