package com.example.haha

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

class MainActivity : ComponentActivity() {

    private val authViewModel: AuthViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                val authState by authViewModel.state.collectAsState()
                when (val state = authState) {
                    AuthState.Loading -> Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(AppColors.Background),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = AppColors.AccentLight)
                    }
                    is AuthState.Unauthenticated -> LoginScreen(
                        sessionExpired = state.sessionExpired,
                        onLoginSuccess = { authViewModel.refreshAuth() }
                    )
                    is AuthState.Authenticated -> DashboardScreen(
                        user = state.user,
                        onBridged = { authViewModel.refreshUser() }
                    )
                }
            }
        }
    }
}
