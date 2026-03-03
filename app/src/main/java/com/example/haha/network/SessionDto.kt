package com.example.haha.network

import com.google.gson.annotations.SerializedName

data class SessionDto(
    val id: String,
    val state: String,
    val recipient: String,
    @SerializedName("created_at") val createdAt: String
)
