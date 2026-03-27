package com.example.haha

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val _Zinc950  = Color(0xFF09090B)
private val _Zinc900  = Color(0xFF18181B)
private val _Zinc800  = Color(0xFF27272A)
private val _Zinc500  = Color(0xFF71717A)
private val _Zinc400  = Color(0xFFA1A1AA)
private val _Purple600 = Color(0xFF9333EA)
private val _Purple400 = Color(0xFFC084FC)
private val _Pink600   = Color(0xFFDB2777)

@Composable
fun ActiveSessionScreen(session: Session) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(_Zinc950)
            .padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Pulsing call indicator
        Box(contentAlignment = Alignment.Center) {
            Box(
                modifier = Modifier
                    .size(100.dp)
                    .clip(CircleShape)
                    .background(
                        Brush.radialGradient(
                            listOf(_Purple600.copy(alpha = 0.25f), Color.Transparent)
                        )
                    )
            )
            Box(
                modifier = Modifier
                    .size(72.dp)
                    .clip(CircleShape)
                    .background(
                        Brush.linearGradient(listOf(_Purple600, _Pink600))
                    ),
                contentAlignment = Alignment.Center
            ) {
                Text("📞", fontSize = 28.sp)
            }
        }

        Spacer(modifier = Modifier.height(28.dp))

        Text(
            "Обаждане в момента",
            color = Color.White,
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(4.dp))

        Text(
            "Свързваме се с ${session.recipient}",
            color = _Zinc500,
            fontSize = 14.sp
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Session details card
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(20.dp))
                .background(_Zinc900)
                .padding(20.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    "ДЕТАЙЛИ НА СЕСИЯТА",
                    color = _Zinc500,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.5.sp
                )
                listOf(
                    "ID" to session.id,
                    "Получател" to session.recipient,
                    "Статус" to session.state.name,
                ).forEach { (label, value) ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(label, color = _Zinc500, fontSize = 13.sp)
                        Text(
                            value,
                            color = Color.White,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(28.dp))

        CircularProgressIndicator(color = _Purple400, strokeWidth = 2.5.dp)
    }
}
