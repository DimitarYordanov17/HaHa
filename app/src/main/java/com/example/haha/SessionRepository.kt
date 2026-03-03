package com.example.haha

import com.example.haha.network.CreateSessionRequest
import com.example.haha.network.RetrofitClient
import com.example.haha.network.SessionDto

class SessionRepository {

    suspend fun createSession(recipient: String): Result<Session> {
        return try {
            val response = RetrofitClient.api.createSession(CreateSessionRequest(recipient))
            if (response.isSuccessful) {
                Result.success(response.body()!!.toDomain())
            } else {
                Result.failure(Exception("HTTP ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getSession(id: String): Result<Session> {
        return try {
            val response = RetrofitClient.api.getSession(id)
            if (response.isSuccessful) {
                Result.success(response.body()!!.toDomain())
            } else {
                Result.failure(Exception("HTTP ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun SessionDto.toDomain(): Session {
        val state = try {
            BackendSessionState.valueOf(this.state)
        } catch (e: IllegalArgumentException) {
            BackendSessionState.FAILED
        }
        return Session(
            id = this.id,
            state = state,
            recipient = this.recipient
        )
    }
}
