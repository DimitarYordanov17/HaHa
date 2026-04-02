package com.example.haha.network

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * Central channel for auth-expiry signals.
 *
 * AuthInterceptor emits here whenever any protected endpoint returns 401.
 * AuthViewModel subscribes and transitions to Unauthenticated when it fires
 * while the user is in an Authenticated session (mid-session token expiry).
 *
 * Boot-time 401s (from checkAuth → GET /me) are handled directly in AuthViewModel
 * and ignored by the event bus subscriber via the `is Authenticated` guard.
 */
object AuthEventBus {
    private val _expired = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val expired: SharedFlow<Unit> = _expired.asSharedFlow()

    /** Called from OkHttp threads — must be non-suspending. */
    fun notifyExpired() {
        _expired.tryEmit(Unit)
    }
}
