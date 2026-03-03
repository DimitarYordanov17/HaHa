package com.example.haha

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun ActiveSessionScreen(session: Session) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text("Session ID: ${session.id}")
        Spacer(modifier = Modifier.height(8.dp))
        Text("Recipient: ${session.recipient}")
        Spacer(modifier = Modifier.height(8.dp))
        Text("State: ${session.state}")
        Spacer(modifier = Modifier.height(24.dp))
        CircularProgressIndicator()
    }
}
