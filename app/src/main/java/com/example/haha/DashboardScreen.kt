package com.example.haha

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

@Composable
fun DashboardScreen(user: User, viewModel: SessionViewModel = viewModel()) {
    val sessionState by viewModel.state.collectAsState()

    Column(modifier = Modifier.fillMaxSize()) {
        UserHeader(user = user)
        Divider()
        Box(modifier = Modifier.weight(1f)) {
            when (val uiState = sessionState) {
                SessionUiState.Idle -> SessionInputForm(
                    onStart = { recipient -> viewModel.startSession(recipient) }
                )
                SessionUiState.Creating -> Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator()
                }
                is SessionUiState.Active -> ActiveSessionScreen(session = uiState.session)
                SessionUiState.Completed -> SessionResultScreen(
                    message = "Session Completed",
                    onReset = { viewModel.reset() }
                )
                is SessionUiState.Failed -> SessionResultScreen(
                    message = uiState.message,
                    onReset = { viewModel.reset() }
                )
            }
        }
    }
}

@Composable
private fun UserHeader(user: User) {
    Column(modifier = Modifier.padding(horizontal = 24.dp, vertical = 12.dp)) {
        Text("Calling from: ${user.phoneNumber}")
        Text("Credits: ${user.credits}")
    }
}

@Composable
private fun SessionInputForm(onStart: (String) -> Unit) {
    var recipient by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        OutlinedTextField(
            value = recipient,
            onValueChange = { recipient = it },
            label = { Text("Recipient phone number") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(modifier = Modifier.height(16.dp))
        Button(
            onClick = { onStart(recipient) },
            enabled = recipient.isNotBlank(),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Start Prank")
        }
    }
}

@Composable
private fun SessionResultScreen(message: String, onReset: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(message)
        Spacer(modifier = Modifier.height(16.dp))
        Button(onClick = onReset) {
            Text("Back")
        }
    }
}
