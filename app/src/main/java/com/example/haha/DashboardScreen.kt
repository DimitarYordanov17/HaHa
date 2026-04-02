package com.example.haha

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

// ── Color tokens ─────────────────────────────────────────────────────────────
private val Zinc950   = AppColors.Background
private val Zinc900   = AppColors.Surface
private val Zinc800   = Color(0xFF27272A)
private val Zinc700   = Color(0xFF3F3F46)
private val Zinc600   = Color(0xFF52525B)
private val Zinc500   = AppColors.TextMuted
private val Zinc400   = Color(0xFFA1A1AA)
private val Zinc200   = Color(0xFFE4E4E7)
private val Purple600 = AppColors.Accent
private val Purple500 = Color(0xFFA855F7)
private val Purple400 = AppColors.AccentLight
private val Pink600   = AppColors.AccentPink
private val Green600  = Color(0xFF16A34A)
private val Green400  = Color(0xFF4ADE80)
private val Red400    = Color(0xFFF87171)

// ── Nav tabs ──────────────────────────────────────────────────────────────────
private enum class Tab { PRANK, HISTORY, BUY, PROFILE }

private data class TabItem(val tab: Tab, val icon: ImageVector, val label: String)

private val TABS = listOf(
    TabItem(Tab.PRANK,   Icons.Default.ChatBubble,   "Пранк"),
    TabItem(Tab.HISTORY, Icons.Default.Schedule,     "История"),
    TabItem(Tab.BUY,     Icons.Default.ShoppingBag,  "Купи"),
    TabItem(Tab.PROFILE, Icons.Default.Person,       "Профил"),
)

// ── Chat types ────────────────────────────────────────────────────────────────

private enum class MsgRole { ASSISTANT, USER }

private data class ChatMessage(
    val id: Long,
    val role: MsgRole,
    val text: String,
)

// ── Root screen ───────────────────────────────────────────────────────────────
@Composable
fun DashboardScreen(
    user: User,
    onBridged: () -> Unit,
    viewModel: SessionViewModel = viewModel()
) {
    LaunchedEffect(Unit) {
        viewModel.events.collect { event ->
            when (event) {
                SessionEvent.Bridged,
                SessionEvent.CreditsDeducted -> onBridged()
            }
        }
    }

    var activeTab by remember { mutableStateOf(Tab.PRANK) }

    Scaffold(
        containerColor = Zinc950,
        topBar = { AppTopBar(user = user, activeTab = activeTab, onBuyClick = { activeTab = Tab.BUY }) },
        bottomBar = { AppBottomNav(activeTab = activeTab, onTabSelected = { activeTab = it }) },
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .background(Zinc950)
        ) {
            when (activeTab) {
                Tab.PRANK   -> PrankBuilderTab(
                    onStartPrank = { phone -> viewModel.startSession(phone) }
                )
                Tab.HISTORY -> HistoryTab(
                    onNewPrank = { activeTab = Tab.PRANK },
                    onRefresh = {},
                )
                Tab.BUY     -> BuyTab(credits = user.credits)
                Tab.PROFILE -> ProfileTab(user = user, onNavigate = { activeTab = it })
            }
        }
    }
}

// ── Top bar ───────────────────────────────────────────────────────────────────
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppTopBar(user: User, activeTab: Tab, onBuyClick: () -> Unit) {
    val titles = mapOf(
        Tab.PRANK   to "PrankCall 🎭",
        Tab.HISTORY to "История",
        Tab.BUY     to "Купи токени",
        Tab.PROFILE to "Профил",
    )
    Surface(color = Zinc950, tonalElevation = 0.dp) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = titles[activeTab] ?: "PrankCall",
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                style = LocalTextStyle.current.copy(
                    brush = Brush.linearGradient(listOf(Purple400, Pink600))
                )
            )
            Row(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(Zinc800)
                    .clickable { onBuyClick() }
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text("🪙", fontSize = 14.sp)
                Text(
                    text = "${user.credits}",
                    color = Color.White,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold
                )
            }
        }
        HorizontalDivider(color = Zinc800.copy(alpha = 0.6f), thickness = 0.5.dp)
    }
}

// ── Bottom nav ────────────────────────────────────────────────────────────────
@Composable
private fun AppBottomNav(activeTab: Tab, onTabSelected: (Tab) -> Unit) {
    Surface(color = Zinc950, tonalElevation = 0.dp) {
        HorizontalDivider(color = Zinc800.copy(alpha = 0.6f), thickness = 0.5.dp)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(64.dp)
                .navigationBarsPadding(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            TABS.forEach { item ->
                val active = activeTab == item.tab
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .clickable { onTabSelected(item.tab) },
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Icon(
                        imageVector = item.icon,
                        contentDescription = item.label,
                        tint = if (active) Purple400 else Zinc500,
                        modifier = Modifier.size(22.dp)
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = item.label,
                        color = if (active) Purple400 else Zinc500,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }
    }
}

// ── Prank Builder tab — System 1 guided authoring ─────────────────────────────
@Composable
private fun PrankBuilderTab(
    viewModel: AuthoringViewModel = viewModel(),
    onStartPrank: (String) -> Unit = {},
) {
    val state by viewModel.state.collectAsState()
    var inputText by remember { mutableStateOf("") }
    // Local editing mode: lets user keep chatting after prank is ready without resetting session
    var editingMode by remember { mutableStateOf(false) }
    // Phone input is explicitly triggered by user after prank is ready — not shown automatically
    var showPhoneInput by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()

    // Reset local flow state when a new session starts
    LaunchedEffect(state.sessionId) {
        editingMode = false
        showPhoneInput = false
    }

    // Scroll to bottom on new message or when card appears
    LaunchedEffect(state.messages.size) {
        if (state.messages.isNotEmpty()) listState.animateScrollToItem(state.messages.lastIndex)
    }

    Column(modifier = Modifier.fillMaxSize().background(Zinc950)) {

        // Sub-header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Zinc950)
                .padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Асистент", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
        }
        HorizontalDivider(color = Zinc800.copy(alpha = 0.6f), thickness = 0.5.dp)

        // Thinking indicator — visible only while waiting for backend (not during initial session load)
        if (state.isLoading && state.sessionId != null) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Zinc900)
                    .padding(horizontal = 16.dp, vertical = 7.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                CircularProgressIndicator(modifier = Modifier.size(11.dp), color = Purple400, strokeWidth = 2.dp)
                Text("Мисля...", color = Zinc400, fontSize = 11.sp)
            }
        }

        // Messages (pure chat — no draft cards during authoring)
        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).padding(horizontal = 12.dp),
            contentPadding = PaddingValues(vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(state.messages, key = { it.id }) { msg ->
                ChatBubble(
                    msg = ChatMessage(
                        id = msg.id,
                        role = if (msg.role == "user") MsgRole.USER else MsgRole.ASSISTANT,
                        text = msg.text,
                    )
                )
            }
        }

        // Error (inline, below messages)
        val errorMsg = state.error
        if (errorMsg != null) {
            Text(
                text =

                    errorMsg,
                color = Red400,
                fontSize = 12.sp,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
            )
        }

        HorizontalDivider(color = Zinc800.copy(alpha = 0.6f), thickness = 0.5.dp)

        // Bottom area — staged flow based on state
        val recipientPhone = state.recipientPhone
        when {
            // Prank ready + phone collected — show ready card (or launched confirmation)
            state.isReady && !editingMode && recipientPhone != null -> {
                PrankReadyCard(
                    recipientPhone = recipientPhone,
                    draft = state.draft,
                    isLaunched = state.isLaunched,
                    onStartPrank = { viewModel.launchPrank(onStartPrank) },
                    onContinueEditing = { editingMode = true },
                    onNewPrank = { viewModel.reset() },
                    onEditPhone = { viewModel.clearRecipientPhone() },
                )
            }

            // Prank ready, user explicitly opened phone input
            state.isReady && !editingMode && showPhoneInput -> {
                PhoneCollectionBar(
                    onSubmit = { phone -> viewModel.submitRecipientPhone(phone) }
                )
            }

            // Prank ready, phone not yet collected — show CTA to start phone step
            state.isReady && !editingMode -> {
                ReadyProceedBanner(onProceed = { showPhoneInput = true })
            }

            // Chat is active (authoring in progress, or user is in editing mode after ready)
            else -> {
                // When editing a ready prank, show a persistent return-to-card banner above input
                if (editingMode) {
                    ReturnToCardBanner(onClick = { editingMode = false })
                }
                ChatInputBar(
                    inputText = inputText,
                    onInputChange = { inputText = it },
                    enabled = !state.isLoading && state.sessionId != null,
                    onSend = {
                        val text = inputText.trim()
                        inputText = ""
                        viewModel.sendMessage(text)
                    }
                )
            }
        }
    }
}

// ── Chat input bar ────────────────────────────────────────────────────────────
@Composable
private fun ChatInputBar(
    inputText: String,
    onInputChange: (String) -> Unit,
    enabled: Boolean,
    onSend: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Zinc950)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        TextField(
            value = inputText,
            onValueChange = onInputChange,
            placeholder = {
                Text(
                    text = if (enabled) "Напиши съобщение..." else "Зареждане...",
                    color = Zinc600, fontSize = 14.sp
                )
            },
            enabled = enabled,
            singleLine = true,
            modifier = Modifier.weight(1f),
            shape = RoundedCornerShape(20.dp),
            colors = TextFieldDefaults.colors(
                focusedContainerColor = Zinc800,
                unfocusedContainerColor = Zinc800,
                disabledContainerColor = Zinc800.copy(alpha = 0.5f),
                focusedTextColor = Color.White,
                unfocusedTextColor = Color.White,
                disabledTextColor = Zinc500,
                focusedIndicatorColor = Color.Transparent,
                unfocusedIndicatorColor = Color.Transparent,
                disabledIndicatorColor = Color.Transparent,
                cursorColor = Purple400,
            )
        )
        Box(
            modifier = Modifier
                .size(44.dp)
                .clip(RoundedCornerShape(14.dp))
                .background(
                    if (inputText.isNotBlank() && enabled) Purple600
                    else Purple600.copy(alpha = 0.3f)
                )
                .clickable(enabled = inputText.isNotBlank() && enabled) { onSend() },
            contentAlignment = Alignment.Center
        ) {
            Icon(Icons.Default.Send, contentDescription = "Изпрати", tint = Color.White, modifier = Modifier.size(18.dp))
        }
    }
}

// ── Phone collection bar ──────────────────────────────────────────────────────
// Accepted format: +359XXXXXXXXX only. Local 0XXXXXXXXX is rejected —
// Telnyx requires the +359 prefix. Spaces, dashes, and parentheses are stripped
// before validation and submission.
private val PHONE_VALIDATION_RE = Regex("""^\+359\d{9}$""")
private fun normalizePhone(raw: String): String = raw.replace(Regex("""[\s\-()]"""), "")
private fun isValidPhone(raw: String): Boolean = normalizePhone(raw).matches(PHONE_VALIDATION_RE)

@Composable
private fun PhoneCollectionBar(onSubmit: (String) -> Unit) {
    var phoneText by remember { mutableStateOf("") }
    var phoneError by remember { mutableStateOf<String?>(null) }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Zinc900)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text(
            "На кой номер да се обадим?",
            color = Zinc400,
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium,
        )
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            TextField(
                value = phoneText,
                onValueChange = {
                    phoneText = it
                    phoneError = null
                },
                placeholder = { Text("+359 88 ...", color = Zinc600, fontSize = 14.sp) },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                singleLine = true,
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(20.dp),
                colors = TextFieldDefaults.colors(
                    focusedContainerColor = Zinc800,
                    unfocusedContainerColor = Zinc800,
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                    focusedIndicatorColor = Color.Transparent,
                    unfocusedIndicatorColor = Color.Transparent,
                    cursorColor = Purple400,
                )
            )
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(if (phoneText.isNotBlank()) Purple600 else Purple600.copy(alpha = 0.3f))
                    .clickable(enabled = phoneText.isNotBlank()) {
                        val trimmed = phoneText.trim()
                        if (isValidPhone(trimmed)) {
                            onSubmit(normalizePhone(trimmed))
                        } else {
                            phoneError = "Въведи с +359, без нулата — например: +359879052660"
                        }
                    },
                contentAlignment = Alignment.Center
            ) {
                Icon(Icons.Default.ArrowForward, contentDescription = "Потвърди", tint = Color.White, modifier = Modifier.size(18.dp))
            }
        }
        if (phoneError != null) {
            Text(
                text = phoneError!!,
                color = Red400,
                fontSize = 11.sp,
            )
        }
    }
}

// ── Ready proceed banner — shown after prank is ready, before phone step ──────
@Composable
private fun ReadyProceedBanner(onProceed: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Zinc900)
            .clickable { onProceed() }
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("🎭", fontSize = 16.sp)
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text("Пранкът е готов!", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                Text("Добавете номер на получателя →", color = Zinc400, fontSize = 12.sp)
            }
        }
        Icon(Icons.Default.ArrowForward, contentDescription = null, tint = Purple400, modifier = Modifier.size(18.dp))
    }
}

// ── Return to card banner — sticky above chat input when editing a ready prank ─
@Composable
private fun ReturnToCardBanner(onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Purple600.copy(alpha = 0.12f))
            .clickable { onClick() }
            .padding(horizontal = 16.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Icon(Icons.Default.ArrowBack, contentDescription = null, tint = Purple400, modifier = Modifier.size(14.dp))
        Text("Обратно към пранк картата", color = Purple400, fontSize = 12.sp, fontWeight = FontWeight.Medium)
    }
}

// ── Prank ready card ──────────────────────────────────────────────────────────
@Composable
private fun PrankReadyCard(
    recipientPhone: String,
    draft: com.example.haha.network.PrankDraftDto?,
    isLaunched: Boolean,
    onStartPrank: () -> Unit,
    onContinueEditing: () -> Unit,
    onNewPrank: () -> Unit,
    onEditPhone: () -> Unit,
) {
    Surface(
        color = Zinc900,
        shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Header — changes after launch
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(if (isLaunched) "✅" else "🎭", fontSize = 18.sp)
                Text(
                    text = if (isLaunched) "Пранкът е изпратен!" else "Пранкът е готов",
                    color = if (isLaunched) Green400 else Color.White,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold,
                )
            }

            // Summary — short product-style title derived from prank_title (model-generated)
            // or falling back to caller.persona when the title is not yet set.
            val summary = draft?.prankTitle
                ?: draft?.caller?.persona?.replaceFirstChar { it.uppercaseChar() }
            if (summary != null) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(Zinc800)
                        .padding(horizontal = 12.dp, vertical = 10.dp)
                ) {
                    Text(summary, color = Zinc200, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                }
            }

            // Recipient — edit disabled after launch to prevent confusion
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Получател", color = Zinc500, fontSize = 13.sp)
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(recipientPhone, color = Zinc200, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                    if (!isLaunched) {
                        Box(
                            modifier = Modifier
                                .size(26.dp)
                                .clip(RoundedCornerShape(6.dp))
                                .background(Zinc800)
                                .clickable { onEditPhone() },
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(Icons.Default.Edit, contentDescription = "Промени номера", tint = Zinc400, modifier = Modifier.size(13.dp))
                        }
                    }
                }
            }
            HorizontalDivider(color = Zinc800)

            if (isLaunched) {
                // ── Post-launch state: "Нов пранк" only ──────────────────────
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(Zinc800)
                        .clickable { onNewPrank() }
                        .padding(vertical = 13.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text("Нов пранк", color = Zinc200, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                }
            } else {
                // ── Pre-launch state: primary + secondary actions ─────────────
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(Brush.linearGradient(listOf(Purple600, Pink600)))
                        .clickable { onStartPrank() }
                        .padding(vertical = 13.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text("Стартирай пранка 🎭", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(12.dp))
                            .background(Zinc800)
                            .clickable { onContinueEditing() }
                            .padding(vertical = 11.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("Продължи", color = Zinc200, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                    }
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(12.dp))
                            .background(Zinc800)
                            .clickable { onNewPrank() }
                            .padding(vertical = 11.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("Нов пранк", color = Zinc500, fontSize = 13.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun ChatBubble(msg: ChatMessage) {
    val isUser = msg.role == MsgRole.USER
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Box(
            modifier = Modifier
                .widthIn(max = 300.dp)
                .clip(
                    RoundedCornerShape(
                        topStart = 18.dp, topEnd = 18.dp,
                        bottomStart = if (isUser) 18.dp else 4.dp,
                        bottomEnd = if (isUser) 4.dp else 18.dp
                    )
                )
                .background(if (isUser) Purple600 else Zinc800)
                .padding(horizontal = 16.dp, vertical = 12.dp)
        ) {
            Text(
                text = msg.text,
                color = if (isUser) Color.White else Zinc200,
                fontSize = 14.sp,
                lineHeight = 20.sp
            )
        }
    }
}

// ── History tab ───────────────────────────────────────────────────────────────
@Composable
private fun HistoryTab(
    onNewPrank: () -> Unit,
    onRefresh: () -> Unit,
    viewModel: HistoryViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()

    // Refresh the list every time this tab is navigated to
    LaunchedEffect(Unit) {
        viewModel.loadHistory()
    }

    Box(modifier = Modifier.fillMaxSize().background(Zinc950)) {
        when {
            state.isLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Purple400, strokeWidth = 2.dp)
                }
            }

            state.sessions.isEmpty() && state.error == null -> {
                // Empty state
                Column(
                    modifier = Modifier.fillMaxSize(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Text("🎭", fontSize = 56.sp)
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        "Няма завършени пранкове",
                        color = Color.White,
                        fontSize = 17.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        "Тук ще се появяват картите на стартираните ти пранкове.",
                        color = Zinc500,
                        fontSize = 13.sp,
                        modifier = Modifier.padding(horizontal = 36.dp),
                        textAlign = TextAlign.Center,
                    )
                    Spacer(modifier = Modifier.height(24.dp))
                    Row(
                        modifier = Modifier
                            .clip(RoundedCornerShape(16.dp))
                            .background(Purple600)
                            .clickable { onNewPrank() }
                            .padding(horizontal = 20.dp, vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Icon(Icons.Default.Add, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
                        Text("Нов пранк", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            }

            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(state.sessions, key = { it.id }) { session ->
                        PrankHistoryCard(session = session)
                    }
                }
            }
        }

        // Error banner (non-blocking)
        val errorMsg = state.error
        if (errorMsg != null && !state.isLoading) {
            Box(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .background(Zinc900)
                    .padding(horizontal = 16.dp, vertical = 10.dp)
            ) {
                Text(errorMsg, color = Red400, fontSize = 12.sp)
            }
        }
    }
}

// ── Prank history card ────────────────────────────────────────────────────────
@Composable
private fun PrankHistoryCard(session: com.example.haha.network.AuthoringDraftSummaryDto) {
    Surface(
        color = Zinc900,
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            // Title row + status badge
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                val title = session.prankTitle
                    ?: session.callerPersona?.replaceFirstChar { it.uppercaseChar() }
                    ?: "Непълен пранк"
                Text(
                    text = title,
                    color = Color.White,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(modifier = Modifier.width(8.dp))
                val (badgeLabel, badgeColor) = when {
                    session.launchedAt != null -> "Изпратен" to Green400
                    session.isComplete        -> "Готов"    to Purple400
                    else                      -> "Чернова"  to Zinc500
                }
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .background(badgeColor.copy(alpha = 0.15f))
                        .padding(horizontal = 7.dp, vertical = 3.dp),
                ) {
                    Text(
                        text = badgeLabel,
                        color = badgeColor,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                    )
                }
            }

            // Opening premise excerpt
            if (session.opening != null) {
                Text(
                    text = session.opening,
                    color = Zinc400,
                    fontSize = 12.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }

            // Recipient + date row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (session.recipientPhone != null) {
                    Text("📞 ${session.recipientPhone}", color = Zinc500, fontSize = 11.sp)
                } else {
                    Spacer(modifier = Modifier.weight(1f))
                }
                // Show date portion of ISO timestamp ("2026-04-01")
                Text(
                    text = session.createdAt.take(10),
                    color = Zinc600,
                    fontSize = 11.sp,
                )
            }
        }
    }
}

// ── Buy tab ───────────────────────────────────────────────────────────────────
private data class PrankPackage(
    val id: String,
    val label: String,
    val tokens: Int,
    val price: String,
    val perPrank: String,
    val emoji: String,
    val highlight: Boolean = false,
)

private val PACKAGES = listOf(
    PrankPackage("starter", "Starter",  1, "2.99 лв.", "2.99 лв./пранк", "🎯"),
    PrankPackage("popular", "Popular",  5, "9.99 лв.", "2.00 лв./пранк", "🔥", highlight = true),
    PrankPackage("pro",     "Pro",     10, "14.99 лв.","1.50 лв./пранк", "👑"),
)

@Composable
private fun BuyTab(credits: Int) {
    var selected by remember { mutableStateOf<PrankPackage?>(null) }
    var localCredits by remember(credits) { mutableStateOf(credits) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Zinc950)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 20.dp)
    ) {
        // Balance pill
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center
        ) {
            Row(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(Zinc800)
                    .padding(horizontal = 20.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Text("🪙", fontSize = 16.sp)
                Text("$localCredits", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Text("налични токена", color = Zinc400, fontSize = 14.sp)
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        PACKAGES.forEach { pkg ->
            Spacer(modifier = Modifier.height(10.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(16.dp))
                    .background(
                        if (pkg.highlight)
                            Brush.linearGradient(listOf(Purple600.copy(alpha = 0.35f), Zinc900))
                        else
                            Brush.linearGradient(listOf(Zinc900, Zinc900))
                    )
                    .then(
                        if (pkg.highlight)
                            Modifier.then(Modifier) // border handled below
                        else Modifier
                    )
                    .clickable { selected = pkg }
                    .padding(16.dp)
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(48.dp)
                            .clip(RoundedCornerShape(14.dp))
                            .background(if (pkg.highlight) Purple600.copy(alpha = 0.3f) else Zinc800),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(pkg.emoji, fontSize = 22.sp)
                    }
                    Column(modifier = Modifier.weight(1f)) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            Text(pkg.label, color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Bold)
                            if (pkg.highlight) {
                                Box(
                                    modifier = Modifier
                                        .clip(CircleShape)
                                        .background(Purple600)
                                        .padding(horizontal = 6.dp, vertical = 2.dp)
                                ) {
                                    Text("ПОПУЛЯРЕН", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                        Text(
                            "${pkg.tokens} ${if (pkg.tokens == 1) "пранк" else "пранка"} · ${pkg.perPrank}",
                            color = Zinc400, fontSize = 12.sp
                        )
                    }
                    Text(pkg.price, color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                }
            }
        }
    }

    // Confirm dialog
    selected?.let { pkg ->
        AlertDialog(
            onDismissRequest = { selected = null },
            containerColor = Zinc900,
            title = { Text("Потвърди покупката", color = Color.White) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Surface(color = Zinc800, shape = RoundedCornerShape(16.dp)) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Пакет", color = Zinc400, fontSize = 14.sp)
                                Text("${pkg.label} ${pkg.emoji}", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                            }
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Токени", color = Zinc400, fontSize = 14.sp)
                                Text("+${pkg.tokens}", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                            }
                            HorizontalDivider(color = Zinc700)
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Сума", color = Zinc400, fontSize = 14.sp)
                                Text(pkg.price, color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            },
            confirmButton = {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(16.dp))
                        .background(Purple600)
                        .clickable {
                            localCredits += pkg.tokens
                            selected = null
                        }
                        .padding(vertical = 14.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Check, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
                        Text("Плати ${pkg.price}", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
        )
    }
}

// ── Profile tab ───────────────────────────────────────────────────────────────
@Composable
private fun ProfileTab(user: User, onNavigate: (Tab) -> Unit) {
    var termsOpen by remember { mutableStateOf(false) }
    val initial = (user.email.firstOrNull() ?: '?').uppercaseChar()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Zinc950)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Avatar block
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .clip(CircleShape)
                    .background(Brush.linearGradient(listOf(Purple500, Pink600))),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "$initial",
                    color = Color.White,
                    fontSize = 32.sp,
                    fontWeight = FontWeight.Bold
                )
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(user.email, color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Bold)
            Row(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(Zinc800)
                    .padding(horizontal = 12.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text("🪙", fontSize = 13.sp)
                Text("${user.credits} токена", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            }
        }

        // Account info card
        Surface(color = Zinc900, shape = RoundedCornerShape(16.dp)) {
            Column {
                Text(
                    "АКАУНТ",
                    color = Zinc500, fontSize = 10.sp, fontWeight = FontWeight.Bold,
                    letterSpacing = 1.5.sp,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                )
                HorizontalDivider(color = Zinc800.copy(alpha = 0.6f))
                if (user.phoneNumber != null) {
                    Row(modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Телефон", color = Zinc600, fontSize = 10.sp)
                            Text(user.phoneNumber, color = Color.White, fontSize = 14.sp)
                        }
                    }
                    HorizontalDivider(color = Zinc800.copy(alpha = 0.6f), modifier = Modifier.padding(horizontal = 16.dp))
                }
                Row(modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("Email", color = Zinc600, fontSize = 10.sp)
                        Text(user.email, color = Color.White, fontSize = 14.sp)
                    }
                }
            }
        }

        // Refer a friend card
        Surface(
            color = Color.Transparent,
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(16.dp))
                    .background(Brush.linearGradient(listOf(Purple600.copy(alpha = 0.3f), Pink600.copy(alpha = 0.15f))))
                    .padding(16.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("🎁", fontSize = 20.sp)
                        Text("Покани приятел", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                    }
                    Text(
                        "Получи 1 безплатен пранк за всеки поканен приятел!",
                        color = Zinc400, fontSize = 13.sp
                    )
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(12.dp))
                            .background(Color.Transparent)
                            .then(Modifier)
                            .padding(1.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(11.dp))
                                .background(Purple600.copy(alpha = 0.1f))
                                .clickable { /* dummy */ }
                                .padding(vertical = 12.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("Копирай реферален линк", color = Purple400, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            }
        }

        // Menu rows
        Surface(color = Zinc900, shape = RoundedCornerShape(16.dp)) {
            Column {
                listOf(
                    "История на пранковете" to { onNavigate(Tab.HISTORY) },
                    "Купи токени" to { onNavigate(Tab.BUY) },
                    "Общи условия" to { termsOpen = true },
                ).forEachIndexed { i, (label, action) ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { action() }
                            .padding(horizontal = 16.dp, vertical = 16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(label, color = Zinc200, fontSize = 14.sp)
                        Icon(Icons.Default.ChevronRight, contentDescription = null, tint = Zinc600, modifier = Modifier.size(16.dp))
                    }
                    if (i < 2) HorizontalDivider(color = Zinc800.copy(alpha = 0.6f), modifier = Modifier.padding(horizontal = 16.dp))
                }
            }
        }
    }

    // Terms dialog
    if (termsOpen) {
        AlertDialog(
            onDismissRequest = { termsOpen = false },
            containerColor = Zinc900,
            title = { Text("Общи условия", color = Color.White) },
            text = {
                Column(
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text("Добре дошли в PrankCall. Чрез използването на нашата платформа, вие се съгласявате с настоящите общи условия.", color = Zinc400, fontSize = 13.sp)
                    Text("1. Отговорност: Потребителите носят пълна отговорност за пранковете, които инициират.", color = Zinc400, fontSize = 13.sp)
                    Text("2. Забранено съдържание: Забранено е използването за тормоз или незаконно поведение.", color = Zinc400, fontSize = 13.sp)
                    Text("3. Поверителност: Телефонните номера се изтриват след приключване на обаждането.", color = Zinc400, fontSize = 13.sp)
                    Text("4. Токени: Закупените токени не подлежат на връщане след употреба.", color = Zinc400, fontSize = 13.sp)
                    Text("Последна актуализация: Март 2026", color = Zinc600, fontSize = 11.sp)
                }
            },
            confirmButton = {
                TextButton(onClick = { termsOpen = false }) {
                    Text("Затвори", color = Purple400)
                }
            }
        )
    }
}
