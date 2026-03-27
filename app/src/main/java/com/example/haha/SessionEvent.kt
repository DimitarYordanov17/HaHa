package com.example.haha

sealed class SessionEvent {
    object Bridged : SessionEvent()
    object CreditsDeducted : SessionEvent()
}
