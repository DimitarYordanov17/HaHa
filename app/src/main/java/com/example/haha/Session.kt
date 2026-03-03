package com.example.haha

data class Session(
    val id: String,
    val state: BackendSessionState,
    val recipient: String
)
