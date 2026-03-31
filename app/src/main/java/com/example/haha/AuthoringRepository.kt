package com.example.haha

import com.example.haha.network.AuthoringSessionDto
import com.example.haha.network.RetrofitClient
import com.example.haha.network.SendAuthoringMessageRequest
import com.example.haha.network.SendAuthoringMessageResponse

class AuthoringRepository {

    suspend fun createSession(): Result<AuthoringSessionDto> {
        return try {
            val response = RetrofitClient.api.createAuthoringSession()
            if (response.isSuccessful) {
                Result.success(response.body()!!.session)
            } else {
                Result.failure(Exception("HTTP ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun sendMessage(sessionId: String, content: String): Result<SendAuthoringMessageResponse> {
        return try {
            val response = RetrofitClient.api.sendAuthoringMessage(
                sessionId = sessionId,
                body = SendAuthoringMessageRequest(content = content)
            )
            if (response.isSuccessful) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("HTTP ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
