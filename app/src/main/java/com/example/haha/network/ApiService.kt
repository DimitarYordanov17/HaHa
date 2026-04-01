package com.example.haha.network

import retrofit2.Call
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
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

    @POST("start-prank")
    suspend fun createSession(@Body body: CreateSessionRequest): Response<SessionDto>

    @GET("pranks/{id}")
    suspend fun getSession(@Path("id") id: String): Response<SessionDto>

    // ─── System 1 — Guided prank authoring ───────────────────────────────────

    @POST("authoring/sessions")
    suspend fun createAuthoringSession(): Response<CreateAuthoringSessionResponse>

    @POST("authoring/sessions/{sessionId}/messages")
    suspend fun sendAuthoringMessage(
        @Path("sessionId") sessionId: String,
        @Body body: SendAuthoringMessageRequest
    ): Response<SendAuthoringMessageResponse>

    @GET("authoring/sessions/{sessionId}")
    suspend fun getAuthoringSession(
        @Path("sessionId") sessionId: String
    ): Response<GetAuthoringSessionResponse>

    @PUT("authoring/sessions/{sessionId}/phone")
    suspend fun setRecipientPhone(
        @Path("sessionId") sessionId: String,
        @Body body: SetRecipientPhoneRequest
    ): Response<Unit>

    // List all authoring sessions for the current user (history)
    @GET("authoring/sessions")
    suspend fun listAuthoringSessions(): Response<ListAuthoringSessionsResponse>

    // Record that the user launched a prank from an authoring session
    @POST("authoring/sessions/{sessionId}/launch")
    suspend fun launchAuthoringSession(
        @Path("sessionId") sessionId: String
    ): Response<LaunchAuthoringSessionResponse>
}
