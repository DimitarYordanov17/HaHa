package com.example.haha.network

import retrofit2.Call
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface ApiService {

    // JSON body: { "email": "...", "password": "..." }
    @POST("register")
    fun register(@Body body: RegisterRequest): Call<TokenResponse>

    // Callback-based — kept, not actively used
    @FormUrlEncoded
    @POST("login")
    fun login(
        @Field("username") email: String,
        @Field("password") password: String
    ): Call<TokenResponse>

    // Suspend — used by LoginViewModel
    @FormUrlEncoded
    @POST("login")
    suspend fun loginSuspend(
        @Field("username") email: String,
        @Field("password") password: String
    ): Response<TokenResponse>

    // Callback-based — kept, not actively used
    @GET("me")
    fun me(): Call<MeResponse>

    // Suspend — used by AuthViewModel
    @GET("me")
    suspend fun getMe(): Response<MeResponse>

    @POST("pranks")
    suspend fun createSession(@Body body: CreateSessionRequest): Response<SessionDto>

    @GET("pranks/{id}")
    suspend fun getSession(@Path("id") id: String): Response<SessionDto>
}
