package com.example.haha.network

import com.google.gson.annotations.SerializedName

// ---------- Requests ----------

data class RegisterRequest(
    val email: String,
    val password: String
)

data class CreateSessionRequest(
    val recipient: String
)

// LoginRequest is not needed — login uses @FormUrlEncoded fields directly in ApiService.

// ---------- Responses ----------

data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("token_type")   val tokenType: String
)

data class MeResponse(
    val id: String,
    val email: String
)
