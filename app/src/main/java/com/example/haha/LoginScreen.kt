package com.example.haha

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

@Composable
fun LoginScreen(
    onLoginSuccess: () -> Unit,
    sessionExpired: Boolean = false,
    viewModel: LoginViewModel = viewModel()
) {
    val email by viewModel.email.collectAsState()
    val password by viewModel.password.collectAsState()
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.events.collect { event ->
            when (event) {
                LoginEvent.Success -> onLoginSuccess()
            }
        }
    }

    val fieldColors = TextFieldDefaults.colors(
        focusedContainerColor = Color(0xFF27272A),
        unfocusedContainerColor = Color(0xFF27272A),
        disabledContainerColor = Color(0xFF27272A).copy(alpha = 0.5f),
        focusedTextColor = Color.White,
        unfocusedTextColor = Color.White,
        focusedIndicatorColor = Color.Transparent,
        unfocusedIndicatorColor = Color.Transparent,
        disabledIndicatorColor = Color.Transparent,
        focusedPlaceholderColor = AppColors.TextMuted,
        unfocusedPlaceholderColor = AppColors.TextMuted,
        cursorColor = AppColors.AccentLight,
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppColors.Background)
            .systemBarsPadding()
            .padding(horizontal = 24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            "PrankCall 🎭",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            style = LocalTextStyle.current.copy(
                brush = Brush.linearGradient(listOf(AppColors.AccentLight, AppColors.AccentPink))
            )
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text("Влез в акаунта си", color = AppColors.TextMuted, fontSize = 14.sp)

        if (sessionExpired) {
            Spacer(modifier = Modifier.height(20.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color(0xFF3F1515))
                    .padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                Text(
                    text = "Сесията ти изтече. Влез отново.",
                    color = Color(0xFFF87171),
                    fontSize = 13.sp,
                )
            }
        }

        Spacer(modifier = Modifier.height(40.dp))

        TextField(
            value = email,
            onValueChange = { viewModel.email.value = it },
            placeholder = { Text("Email") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = fieldColors,
        )
        Spacer(modifier = Modifier.height(12.dp))
        TextField(
            value = password,
            onValueChange = { viewModel.password.value = it },
            placeholder = { Text("Парола") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = fieldColors,
        )
        Spacer(modifier = Modifier.height(24.dp))

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(
                    if (uiState is LoginUiState.Loading)
                        AppColors.Accent.copy(alpha = 0.4f)
                    else
                        AppColors.Accent
                )
                .clickable(enabled = uiState !is LoginUiState.Loading) { viewModel.login() }
                .padding(vertical = 16.dp),
            contentAlignment = Alignment.Center
        ) {
            Text("Влез", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
        }

        if (uiState is LoginUiState.Loading) {
            Spacer(modifier = Modifier.height(20.dp))
            CircularProgressIndicator(color = AppColors.AccentLight, strokeWidth = 2.dp)
        }
        if (uiState is LoginUiState.Error) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = (uiState as LoginUiState.Error).message,
                color = Color(0xFFF87171),
                fontSize = 13.sp
            )
        }
    }
}
