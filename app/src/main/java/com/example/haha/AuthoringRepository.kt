package com.example.haha

import com.example.haha.network.AuthoringDraftSummaryDto
import com.example.haha.network.AuthoringSessionDto
import com.example.haha.network.LaunchAuthoringSessionResponse
import com.example.haha.network.RetrofitClient
import com.example.haha.network.SendAuthoringMessageRequest
import com.example.haha.network.SendAuthoringMessageResponse
import com.example.haha.network.SetRecipientPhoneRequest

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

    suspend fun setRecipientPhone(sessionId: String, phone: String): Result<Unit> {
        return try {
            val response = RetrofitClient.api.setRecipientPhone(
                sessionId = sessionId,
                body = SetRecipientPhoneRequest(phone = phone)
            )
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("HTTP ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Fetch the user's authoring session history (newest first, max 50).
     * Used to populate the HistoryTab.
     */
    suspend fun listSessions(): Result<List<AuthoringDraftSummaryDto>> {
        return try {
            val response = RetrofitClient.api.listAuthoringSessions()
            if (response.isSuccessful) {
                Result.success(response.body()!!.sessions)
            } else {
                Result.failure(Exception("HTTP ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Record that the user launched the prank from this authoring session.
     * Best-effort — failure does not block the actual prank call.
     */
    suspend fun launchSession(sessionId: String): Result<LaunchAuthoringSessionResponse> {
        return try {
            val response = RetrofitClient.api.launchAuthoringSession(sessionId = sessionId)
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
