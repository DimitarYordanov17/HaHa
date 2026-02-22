package com.example.haha

import android.content.Context
import android.os.Bundle
import android.util.Log
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.example.haha.network.MeResponse
import com.example.haha.network.RetrofitClient
import com.example.haha.network.TokenResponse
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class LoginActivity : AppCompatActivity() {

    private val TAG = "LoginActivity"
    private val PREFS_NAME = "auth_prefs"
    private val KEY_TOKEN = "access_token"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)

        val etEmail    = findViewById<EditText>(R.id.etEmail)
        val etPassword = findViewById<EditText>(R.id.etPassword)
        val btnLogin   = findViewById<Button>(R.id.btnLogin)
        val tvUserEmail = findViewById<TextView>(R.id.tvUserEmail)

        btnLogin.setOnClickListener {
            val email    = etEmail.text.toString().trim()
            val password = etPassword.text.toString()

            RetrofitClient.api.login(email, password).enqueue(object : Callback<TokenResponse> {
                override fun onResponse(call: Call<TokenResponse>, response: Response<TokenResponse>) {
                    if (response.isSuccessful) {
                        val token = response.body()?.accessToken
                        if (token == null) {
                            Log.e(TAG, "Login succeeded but token was null")
                            return
                        }

                        getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                            .edit()
                            .putString(KEY_TOKEN, token)
                            .apply()

                        Log.d(TAG, "Token saved: $token")

                        RetrofitClient.api.me("Bearer $token").enqueue(object : Callback<MeResponse> {
                            override fun onResponse(call: Call<MeResponse>, response: Response<MeResponse>) {
                                if (response.isSuccessful) {
                                    val email = response.body()?.email
                                    Log.d(TAG, "Logged in as: $email")
                                    tvUserEmail.text = email
                                } else {
                                    Log.e(TAG, "/me error ${response.code()}: ${response.errorBody()?.string()}")
                                }
                            }

                            override fun onFailure(call: Call<MeResponse>, t: Throwable) {
                                Log.e(TAG, "/me request failed: ${t.message}", t)
                            }
                        })
                    } else {
                        Log.e(TAG, "Login error ${response.code()}: ${response.errorBody()?.string()}")
                    }
                }

                override fun onFailure(call: Call<TokenResponse>, t: Throwable) {
                    Log.e(TAG, "Login request failed: ${t.message}", t)
                }
            })
        }
    }
}
