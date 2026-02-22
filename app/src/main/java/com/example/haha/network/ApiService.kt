package com.example.haha.network

import retrofit2.Call
import retrofit2.http.Body
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

interface ApiService {

    // JSON body: { "email": "...", "password": "..." }
    @POST("register")
    fun register(@Body body: RegisterRequest): Call<TokenResponse>

    // Form-encoded: username=<email>&password=<password>  (OAuth2PasswordRequestForm)
    @FormUrlEncoded
    @POST("login")
    fun login(
        @Field("username") email: String,
        @Field("password") password: String
    ): Call<TokenResponse>

    @GET("me")
    fun me(@Header("Authorization") bearer: String): Call<MeResponse>
}
