package com.example.haha

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.launch

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
private val Yellow400 = Color(0xFFFACC15)
private val Blue400   = Color(0xFF60A5FA)

// ── Nav tabs ──────────────────────────────────────────────────────────────────
private enum class Tab { PRANK, HISTORY, BUY, PROFILE }

private data class TabItem(val tab: Tab, val icon: ImageVector, val label: String)

private val TABS = listOf(
    TabItem(Tab.PRANK,   Icons.Default.ChatBubble,   "Пранк"),
    TabItem(Tab.HISTORY, Icons.Default.Schedule,     "История"),
    TabItem(Tab.BUY,     Icons.Default.ShoppingBag,  "Купи"),
    TabItem(Tab.PROFILE, Icons.Default.Person,       "Профил"),
)

// ── Chat wizard types ─────────────────────────────────────────────────────────
private enum class ChatStep { RECIPIENT_NAME, SCENARIO, PHONE, CONFIRM, DONE }

private enum class MsgRole { ASSISTANT, USER }

private data class ChatMessage(
    val id: Long,
    val role: MsgRole,
    val text: String,
    val chips: List<String>? = null,
    val summaryCard: SummaryCard? = null,
)

private data class SummaryCard(val recipientName: String, val scenario: String, val phone: String)

private val SCENARIOS = listOf("Фалшива доставка", "Банков служител", "Изненада от приятел", "Данъчна служба")

private fun maskPhone(phone: String): String {
    if (phone.length < 4) return phone
    return phone.dropLast(4).replace(Regex("\\d"), "*") + phone.takeLast(4)
}

// ── Root screen ───────────────────────────────────────────────────────────────
@Composable
fun DashboardScreen(
    user: User,
    onBridged: () -> Unit,
    viewModel: SessionViewModel = viewModel()
) {
    val sessionState by viewModel.state.collectAsState()

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
                    sessionState = sessionState,
                    onStartSession = { phone -> viewModel.startSession(phone) },
                    onReset = { viewModel.reset() }
                )
                Tab.HISTORY -> HistoryTab(onNewPrank = { activeTab = Tab.PRANK })
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

// ── Prank Builder tab ─────────────────────────────────────────────────────────
@Composable
private fun PrankBuilderTab(
    sessionState: SessionUiState,
    onStartSession: (String) -> Unit,
    onReset: () -> Unit,
) {
    var step by remember { mutableStateOf(ChatStep.RECIPIENT_NAME) }
    var recipientName by remember { mutableStateOf("") }
    var scenario by remember { mutableStateOf("") }
    var inputText by remember { mutableStateOf("") }
    var infoOpen by remember { mutableStateOf(false) }
    val messages = remember {
        mutableStateListOf(
            ChatMessage(
                id = 0L,
                role = MsgRole.ASSISTANT,
                text = "Здравей! 👋 Аз съм твоят пранк асистент. Ще ти помогна да създадеш незабравим пранк.\n\nКак се казва човекът, на когото искаш да се пошегуваш?"
            )
        )
    }

    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    fun addMsg(msg: ChatMessage) {
        messages.add(msg)
        scope.launch { listState.animateScrollToItem(messages.lastIndex) }
    }

    fun handleSend() {
        val text = inputText.trim()
        if (text.isBlank()) return
        inputText = ""
        addMsg(ChatMessage(id = System.currentTimeMillis(), role = MsgRole.USER, text = text))

        when (step) {
            ChatStep.RECIPIENT_NAME -> {
                recipientName = text
                addMsg(ChatMessage(
                    id = System.currentTimeMillis() + 1,
                    role = MsgRole.ASSISTANT,
                    text = "Страхотно! 😄 Ще пранкнем $text!\n\nИзбери сценарий:",
                    chips = SCENARIOS
                ))
                step = ChatStep.SCENARIO
            }
            ChatStep.PHONE -> {
                val summary = SummaryCard(recipientName, scenario, text)
                addMsg(ChatMessage(
                    id = System.currentTimeMillis() + 1,
                    role = MsgRole.ASSISTANT,
                    text = "Перфектно! Ето обобщение на пранка:",
                    summaryCard = summary
                ))
                step = ChatStep.CONFIRM
            }
            else -> {}
        }
    }

    fun handleChipSelect(chip: String) {
        scenario = chip
        addMsg(ChatMessage(id = System.currentTimeMillis(), role = MsgRole.USER, text = chip))
        addMsg(ChatMessage(
            id = System.currentTimeMillis() + 1,
            role = MsgRole.ASSISTANT,
            text = "Чудесен избор! 😈 Сценарият \"$chip\" ще работи перфектно.\n\nВъведи телефонния номер на $recipientName:"
        ))
        step = ChatStep.PHONE
    }

    fun handleStartPrank(summary: SummaryCard) {
        onStartSession(summary.phone)
        addMsg(ChatMessage(
            id = System.currentTimeMillis(),
            role = MsgRole.ASSISTANT,
            text = "✅ Обаждането е планирано! Следи статуса в \"История\"."
        ))
        step = ChatStep.DONE
    }

    // Session state feedback messages
    LaunchedEffect(sessionState) {
        when (sessionState) {
            SessionUiState.Completed -> {
                if (step == ChatStep.DONE) {
                    messages.add(ChatMessage(
                        id = System.currentTimeMillis(),
                        role = MsgRole.ASSISTANT,
                        text = "🎉 Обаждането завърши успешно!"
                    ))
                }
            }
            is SessionUiState.Failed -> {
                if (step == ChatStep.DONE) {
                    messages.add(ChatMessage(
                        id = System.currentTimeMillis(),
                        role = MsgRole.ASSISTANT,
                        text = "❌ Грешка: ${sessionState.message}"
                    ))
                    step = ChatStep.RECIPIENT_NAME
                }
            }
            else -> {}
        }
    }

    Column(modifier = Modifier.fillMaxSize().background(Zinc950)) {
        // Sub-header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Zinc950)
                .padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text("Пранк Асистент", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                Text("AI асистент", color = Zinc500, fontSize = 10.sp)
            }
            IconButton(onClick = { infoOpen = true }) {
                Icon(Icons.Default.Info, contentDescription = "Инфо", tint = Zinc500)
            }
        }
        HorizontalDivider(color = Zinc800.copy(alpha = 0.6f), thickness = 0.5.dp)

        // Session active banner
        if (sessionState is SessionUiState.Active || sessionState is SessionUiState.Creating) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Purple600.copy(alpha = 0.15f))
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(14.dp),
                    color = Purple400,
                    strokeWidth = 2.dp
                )
                Text(
                    text = if (sessionState is SessionUiState.Creating) "Свързване..." else "Обаждане в момента...",
                    color = Purple400,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium
                )
            }
        }

        // Messages list
        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).padding(horizontal = 12.dp),
            contentPadding = PaddingValues(vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(messages) { msg ->
                ChatBubble(
                    msg = msg,
                    currentStep = step,
                    onChipSelect = { handleChipSelect(it) },
                    onStartPrank = { handleStartPrank(it) }
                )
            }
        }

        // Completed / Failed reset
        if (sessionState == SessionUiState.Completed || sessionState is SessionUiState.Failed) {
            Button(
                onClick = {
                    onReset()
                    messages.clear()
                    messages.add(ChatMessage(
                        id = 0L,
                        role = MsgRole.ASSISTANT,
                        text = "Здравей! 👋 Аз съм твоят пранк асистент. Ще ти помогна да създадеш незабравим пранк.\n\nКак се казва човекът, на когото искаш да се пошегуваш?"
                    ))
                    step = ChatStep.RECIPIENT_NAME
                },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Purple600),
                shape = RoundedCornerShape(16.dp)
            ) {
                Text("Нов пранк", color = Color.White, fontWeight = FontWeight.Bold)
            }
        }

        HorizontalDivider(color = Zinc800.copy(alpha = 0.6f), thickness = 0.5.dp)

        // Input bar
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Zinc950)
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            val inputDisabled = step == ChatStep.SCENARIO || step == ChatStep.DONE ||
                    step == ChatStep.CONFIRM ||
                    sessionState is SessionUiState.Creating || sessionState is SessionUiState.Active

            TextField(
                value = inputText,
                onValueChange = { inputText = it },
                placeholder = {
                    Text(
                        text = when {
                            step == ChatStep.SCENARIO -> "Избери сценарий по-горе..."
                            step == ChatStep.DONE || step == ChatStep.CONFIRM -> "Пранкът е стартиран!"
                            step == ChatStep.PHONE -> "+359 88 ..."
                            else -> "Напиши съобщение..."
                        },
                        color = Zinc600, fontSize = 14.sp
                    )
                },
                enabled = !inputDisabled,
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
                        if (inputText.isNotBlank() && !inputDisabled) Purple600
                        else Purple600.copy(alpha = 0.3f)
                    )
                    .clickable(enabled = inputText.isNotBlank() && !inputDisabled) { handleSend() },
                contentAlignment = Alignment.Center
            ) {
                Icon(Icons.Default.Send, contentDescription = "Изпрати", tint = Color.White, modifier = Modifier.size(18.dp))
            }
        }
    }

    // Info dialog
    if (infoOpen) {
        AlertDialog(
            onDismissRequest = { infoOpen = false },
            containerColor = Zinc900,
            title = { Text("Как работи асистентът? 🎭", color = Color.White) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Стъпка по стъпка:", color = Zinc400, fontSize = 14.sp)
                    listOf(
                        "1." to "Посочи получателя — кажи ни как се казва.",
                        "2." to "Избери сценарий — фалшива доставка, банков служител и др.",
                        "3." to "Въведи телефона — номерът, на който да се обадим.",
                        "4." to "Потвърди и стартирай — ние правим останалото!",
                    ).forEach { (n, t) ->
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(n, color = Purple400, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                            Text(t, color = Zinc400, fontSize = 14.sp)
                        }
                    }
                    Surface(
                        color = Zinc800,
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            "💡 Всеки пранк = 1 токен. Купи повече от таб \"Купи\".",
                            color = Zinc400, fontSize = 12.sp,
                            modifier = Modifier.padding(12.dp)
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { infoOpen = false }) {
                    Text("Затвори", color = Purple400)
                }
            }
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChatBubble(
    msg: ChatMessage,
    currentStep: ChatStep,
    onChipSelect: (String) -> Unit,
    onStartPrank: (SummaryCard) -> Unit,
) {
    val isUser = msg.role == MsgRole.USER
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Column(
            modifier = Modifier.widthIn(max = 300.dp),
            horizontalAlignment = if (isUser) Alignment.End else Alignment.Start,
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // Message bubble
            Box(
                modifier = Modifier
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

            // Scenario chips
            if (msg.chips != null && currentStep == ChatStep.SCENARIO) {
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    msg.chips.forEach { chip ->
                        Box(
                            modifier = Modifier
                                .clip(CircleShape)
                                .background(Zinc800)
                                .clickable { onChipSelect(chip) }
                                .padding(horizontal = 12.dp, vertical = 8.dp)
                        ) {
                            Text(chip, color = Zinc200, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                        }
                    }
                }
            }

            // Summary card
            if (msg.summaryCard != null) {
                Surface(
                    color = Zinc900,
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.width(240.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(
                            "ДЕТАЙЛИ",
                            color = Zinc500,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.5.sp
                        )
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            listOf(
                                "Получател" to msg.summaryCard.recipientName,
                                "Сценарий" to msg.summaryCard.scenario,
                                "Телефон" to maskPhone(msg.summaryCard.phone),
                            ).forEach { (label, value) ->
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text(label, color = Zinc500, fontSize = 13.sp)
                                    Text(value, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                                }
                            }
                        }
                        if (currentStep == ChatStep.CONFIRM) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(12.dp))
                                    .background(
                                        Brush.linearGradient(listOf(Purple600, Pink600))
                                    )
                                    .clickable { onStartPrank(msg.summaryCard) }
                                    .padding(vertical = 12.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    "Стартирай пранка 🎭",
                                    color = Color.White,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

// ── History tab ───────────────────────────────────────────────────────────────
@Composable
private fun HistoryTab(onNewPrank: () -> Unit) {
    // No real history endpoint yet – show empty state
    Column(
        modifier = Modifier.fillMaxSize().background(Zinc950),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("🎭", fontSize = 64.sp)
        Spacer(modifier = Modifier.height(16.dp))
        Text("Все още нямаш пранкове", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            "Създай първия си пранк и тук ще виждаш статуса му в реално време.",
            color = Zinc500, fontSize = 14.sp,
            modifier = Modifier.padding(horizontal = 32.dp),
            textAlign = androidx.compose.ui.text.style.TextAlign.Center
        )
        Spacer(modifier = Modifier.height(24.dp))
        Row(
            modifier = Modifier
                .clip(RoundedCornerShape(16.dp))
                .background(Purple600)
                .clickable { onNewPrank() }
                .padding(horizontal = 20.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Icon(Icons.Default.Add, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
            Text("Нов пранк", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
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
