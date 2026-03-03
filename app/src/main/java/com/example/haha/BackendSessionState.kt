package com.example.haha

enum class BackendSessionState {
    CREATED,
    CALLING_SENDER,
    CALLING_RECIPIENT,
    BRIDGED,
    PLAYING_AUDIO,
    COMPLETED,
    FAILED
}
