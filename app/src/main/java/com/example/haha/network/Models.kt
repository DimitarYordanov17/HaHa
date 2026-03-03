package com.example.haha.network

import com.google.gson.annotations.SerializedName

// ---------- Requests ----------

data class RegisterRequest(
    val email: String,
    val password: String,
    @SerializedName("phone_number") val phoneNumber: String
)

data class CreateSessionRequest(
    @SerializedName("recipient_phone_number") val recipient: String
)

// LoginRequest is not needed — login uses @FormUrlEncoded fields directly in ApiService.

// ---------- Responses ----------

data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("token_type")   val tokenType: String
)

data class MeResponse(
    val email: String,
    @SerializedName("phone_number") val phoneNumber: String,
    val credits: Int
)
