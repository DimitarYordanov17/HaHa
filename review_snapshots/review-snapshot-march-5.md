# Android Codebase Review

## 1. Project Structure

```
app/src/main/java/com/example/haha/
│
├── HaHaApp.kt                     # Application subclass; initialises RetrofitClient
├── MainActivity.kt                # Single Activity; root Compose host; owns AuthViewModel
│
├── -- Domain / state models --
├── User.kt                        # Data class: email, phoneNumber, credits
├── Session.kt                     # Data class: id, state (BackendSessionState), recipient
├── BackendSessionState.kt         # Enum mirroring backend states
├── AuthState.kt                   # Sealed: Loading | Unauthenticated | Authenticated(user)
├── LoginUiState.kt                # Sealed: Idle | Loading | Error(message)
├── LoginEvent.kt                  # Sealed one-shot event: Success
├── SessionUiState.kt              # Sealed: Idle | Creating | Active(session) | Completed | Failed
├── SessionEvent.kt                # Sealed one-shot event: Bridged
│
├── -- ViewModels --
├── AuthViewModel.kt               # Manages auth lifecycle; reads/writes SharedPreferences token
├── LoginViewModel.kt              # Drives login form; saves token on success
├── SessionViewModel.kt            # Drives session lifecycle; owns polling loop
│
├── -- Repository --
├── SessionRepository.kt           # Maps API calls to domain Result<Session>; no auth logic
│
├── -- UI screens (Compose) --
├── LoginScreen.kt                 # Login form composable; delegates to LoginViewModel
├── DashboardScreen.kt             # Post-login shell; embeds session input + ActiveSessionScreen
├── ActiveSessionScreen.kt         # Read-only status display for an in-flight session
│
└── network/
    ├── ApiService.kt              # Retrofit interface for all endpoints
    ├── RetrofitClient.kt          # Singleton OkHttp + Retrofit builder; hardcoded base URL
    ├── AuthInterceptor.kt         # Reads token from SharedPreferences; attaches Bearer header
    ├── Models.kt                  # Request/response DTOs (Register, Login, Token, Me)
    └── SessionDto.kt              # DTO for prank session responses
```

**Layer summary:**

| Layer | Files | Responsibility |
|---|---|---|
| UI | `*Screen.kt`, `MainActivity.kt` | Render state, forward user actions to ViewModel |
| ViewModel | `AuthViewModel`, `LoginViewModel`, `SessionViewModel` | State holders, coroutine orchestration, one-shot events |
| Repository | `SessionRepository` | Network calls → `Result<Domain>` translation |
| Network | `network/` | Retrofit interface, OkHttp client, auth interceptor, DTOs |
| Domain | `Session`, `User`, `BackendSessionState`, state/event sealed classes | Pure data |

---

## 2. Architecture Evaluation

**Does UI call the API directly?**
No. All three screens (`LoginScreen`, `DashboardScreen`, `ActiveSessionScreen`) interact only with ViewModels via `collectAsState()` and event callbacks. No screen imports anything from `network/`.

**Are repositories used properly?**
Partially. `SessionRepository` correctly wraps both `createSession` and `getSession` into `Result<Session>` and performs the DTO-to-domain mapping. However there is no `AuthRepository` — auth-related API calls (`getMe`, `loginSuspend`) are made directly from `AuthViewModel` and `LoginViewModel` via `RetrofitClient.api.*`. This is the only SoC violation in the networking layer.

**Is networking isolated?**
Mostly yes. `RetrofitClient` is a global singleton, which is acceptable for this scale. All actual HTTP calls go through `ApiService`. No Composable touches the network.

**Violations of separation of concerns:**

1. **`AuthViewModel` and `LoginViewModel` call `RetrofitClient.api` directly** — there is no `AuthRepository`. Both ViewModels bypass the repository layer for all auth-related calls (`loginSuspend`, `getMe`).

2. **Token persistence is split across two ViewModels** — `LoginViewModel` writes the token to `SharedPreferences`; `AuthViewModel` reads and deletes it. There is no dedicated `TokenStore` or `AuthRepository` that owns this concern.

3. **`SessionViewModel` instantiates its own repository** (`private val repository = SessionRepository()`) instead of receiving it via dependency injection. This makes the ViewModel untestable in isolation.

---

## 3. State Management

**Where is session state stored?**
`SessionViewModel._state: MutableStateFlow<SessionUiState>` is the single source of truth for the current session. It is observed by `DashboardScreen` via `collectAsState()`.

**Is there a single source of truth?**
For session state: yes — `SessionViewModel._state` only. The `Session` domain object inside `SessionUiState.Active` holds the last polled backend state.

For auth/user state: yes — `AuthViewModel._state: MutableStateFlow<AuthState>`. User credits live inside `AuthState.Authenticated.user` and are refreshed via `refreshUser()` when a `Bridged` event fires.

**State primitives used:**
- `MutableStateFlow` for all durable UI state (auth, login, session)
- `MutableSharedFlow(extraBufferCapacity = 1)` for one-shot events (login success, bridged)
- `remember { mutableStateOf("") }` for transient local form state in `SessionInputForm` and `DashboardScreen`

**Potential problems:**

1. **Credit display goes stale during a session.** Credits are displayed in `UserHeader` from `AuthState.Authenticated.user.credits`, which is only updated when `onBridged` fires (`SessionEvent.Bridged`). The `Bridged` event fires when the backend transitions `CALLING_RECIPIENT → BRIDGED`, which is before the audio plays and before the session ends. The credit is deducted on the backend at that same `BRIDGED` transition. So in the best case the display updates at the right moment — but only if `refreshUser()` is called promptly and the `/me` response is fresh. There is no refresh after the session completes.

2. **`previousBackendState` in the polling loop is local to the coroutine.** If the polling job is cancelled and restarted (e.g. ViewModel recreated), the `Bridged` one-shot event will fire again for the same session if the backend is still in `BRIDGED`. This could cause a spurious `refreshUser()` call on re-entry, though it is otherwise harmless.

3. **`SessionInputForm` holds the recipient phone number in local `remember` state.** If the Composable is recomposed and the local state is lost (e.g. due to config change between `Idle` and `Creating`), the entered number is not recovered. Because the ViewModel is scoped to the Activity, it survives rotation — but the local string does not.

---

## 4. Networking Layer

**Library:** Retrofit 2 with OkHttp, Gson converter.

**Where API calls are defined:** `network/ApiService.kt` — single interface, all endpoints in one place. Clean.

**Is authentication handled centrally?**
Yes. `AuthInterceptor` reads `access_token` from SharedPreferences on every request and attaches `Authorization: Bearer <token>`. It is registered as the first interceptor in `RetrofitClient`, so all calls made through `RetrofitClient.api` are automatically authenticated.

**Issues:**

1. **Hardcoded base URL: `http://172.20.10.2:8000/`** (`RetrofitClient.kt:11`). This is a local development address that will fail on any device not connected to the same hotspot. There is no build-variant override, no `BuildConfig` field, and no fallback. Shipping this as-is will break all production users.

2. **Plain HTTP, not HTTPS.** The base URL uses `http://`. This means tokens and call data are transmitted in cleartext. Android 9+ blocks cleartext traffic by default; this likely requires a `network_security_config.xml` exception to work at all, which is a security regression.

3. **Two duplicate login declarations in `ApiService`.** `login()` (callback-based `Call<>`) and `loginSuspend()` (suspend) both map to `POST login`. Only `loginSuspend` is actually used. The `Call<>`-based `login()` and `me()` are dead code.

4. **`register` endpoint is defined but never called** from any ViewModel or screen. There is no registration flow in the UI.

5. **`RetrofitClient` is a global object initialised from `Application.onCreate()`** with `appContext`. If `init()` is not called before `api` is first accessed (e.g. in a test), it will crash with `UninitializedPropertyAccessException`. No guard exists.

6. **`HttpLoggingInterceptor` is set to `BODY` level unconditionally** — logs full request and response bodies including the Bearer token in every environment, including production.

---

## 5. Session Flow Implementation

**How is `/start-prank` called?**

`DashboardScreen` → `SessionInputForm` → `onStart(recipient)` callback → `SessionViewModel.startSession(recipient)` → `SessionRepository.createSession(recipient)` → `RetrofitClient.api.createSession(CreateSessionRequest(recipient))` → `POST /start-prank`.

**Where is the session ID stored?**

Inside `SessionUiState.Active(session: Session)` within `SessionViewModel._state`. There is no persistent storage; the session ID lives only in memory for the lifetime of the ViewModel.

**Is polling implemented?**
Yes. `SessionViewModel.startPolling(sessionId)` launches a coroutine on `viewModelScope` that loops with a 1500 ms `delay` between `GET /pranks/{id}` calls.

**Does polling stop when the session ends?**
Yes, correctly. When the backend state is `COMPLETED` or `FAILED`, the loop executes `return@launch`, which terminates the coroutine. `onCleared()` also cancels `pollingJob`, so rotation or navigation away will stop polling. `reset()` cancels and nulls the job too.

**Gaps in the session flow:**

1. **No navigation to a dedicated session screen.** `ActiveSessionScreen` is rendered inline inside `DashboardScreen` as a Composable subtree — it is not a separate screen or destination. This is fine architecturally, but means back-navigation exits the app rather than returning to the input form.

2. **The session ID is not persisted.** If the process is killed while a session is active (e.g. by the system), the session ID is lost and there is no way to resume polling. The user will see the idle form with no indication that a session is in progress on the backend.

3. **No timeout on the `Creating` state.** If `POST /start-prank` hangs (server slow or no network), the UI shows an infinite spinner with no cancel button and no timeout. The request will eventually time out at the OkHttp level (default: no timeout set), but the user has no way to abort.

4. **`BackendSessionState.PLAYING_AUDIO` and `CALLING_SENDER` / `CALLING_RECIPIENT` all fall through to the `else` branch** in `SessionViewModel.startPolling` (line 72–77), which just updates `SessionUiState.Active(session)`. This is correct, but `ActiveSessionScreen` renders all these as `"State: <enum name>"` raw text with no human-readable labels.

---

## 6. UI Layer

**Are Composables pure UI?**
Largely yes. All three screen composables observe ViewModel state and delegate actions upward. No composable imports `RetrofitClient`, `SessionRepository`, or any coroutine scope manipulation.

**Do they contain business logic?**
Minor violations:

1. **`LoginScreen` mutates ViewModel-owned `MutableStateFlow` directly** (`viewModel.email.value = it`, line 51; `viewModel.password.value = it`, line 60). This is a SoC smell: the composable is writing to ViewModel internals rather than calling an event handler. Should be `viewModel.onEmailChanged(it)`.

2. **`DashboardScreen` owns the `SessionViewModel`** via `viewModel()`. Since `DashboardScreen` is not a navigation destination but a composable called from `MainActivity`, the ViewModel is effectively scoped to the Activity — which is correct. However, re-creating the ViewModel would require re-passing `user` from `AuthState`, which is already done. This is acceptable but slightly fragile.

3. **`SessionInputForm` holds the recipient phone string in local `remember` state**, not in a ViewModel. For a single-field form this is acceptable, but it means the field is cleared on any recomposition that recreates the composable (e.g. when `SessionUiState` changes and back to `Idle`).

**Do Composables directly call APIs?**
No.

---

## 7. Design Risks

### Risk 1 — Hardcoded plaintext localhost URL (Critical)
`RetrofitClient.BASE_URL = "http://172.20.10.2:8000/"` will fail for any user not on the same local network. Android 9+ blocks cleartext HTTP by default. This is a production blocker.

### Risk 2 — No 401 handling after login (High)
`AuthInterceptor` attaches the token, but if the token expires mid-session, the API calls from `SessionRepository` will get a 401 response. `SessionRepository` maps any non-2xx response to `Result.failure(Exception("HTTP 401"))`, which `SessionViewModel` silently ignores (the `onFailure` block is a no-op: just continues polling). The user will see an infinite spinner with no feedback and no logout.

`AuthViewModel.checkAuth()` handles 401 on the `getMe` call, but `SessionRepository` never calls `getMe` — it just calls `createSession` and `getSession`. Those 401s are never forwarded to `AuthViewModel`.

### Risk 3 — Credit display is stale after session completion (Medium)
`onBridged` (called when `SessionEvent.Bridged` fires) triggers `authViewModel.refreshUser()`. This is the only time credits are refreshed. After a session ends (`COMPLETED`), credits are not re-fetched. A user who runs a second prank immediately will see the old credit count until `Bridged` fires again.

### Risk 4 — Session state lost on process death (Medium)
The session ID is held only in `SessionViewModel._state`. Android can kill the process while a session is active. On restart, the ViewModel re-initialises to `SessionUiState.Idle` and polling stops. The backend session continues but the client has no reference to it.

### Risk 5 — `SessionViewModel` constructs its own repository (Low-Medium)
`private val repository = SessionRepository()` — no dependency injection. This makes `SessionViewModel` impossible to unit test without hitting real network. It also means the repository cannot be swapped or mocked. Any future repository constructor change silently breaks the ViewModel.

### Risk 6 — `BODY`-level HTTP logging in all builds (Low)
`HttpLoggingInterceptor.Level.BODY` logs full request and response bodies, including `Authorization: Bearer <token>`. In a production build this will log credentials to logcat, readable by any app with `READ_LOGS` permission on pre-API-26 devices.

### Risk 7 — `MutableSharedFlow` event replay edge case (Low)
`SharedFlow(extraBufferCapacity = 1)` buffers one event if there is no collector. `LoginScreen` and `DashboardScreen` start collecting inside `LaunchedEffect(Unit)`. If the composable enters composition after the event has already been emitted (e.g. rapid state change before composition starts), the event may be replayed and trigger a duplicate `onLoginSuccess` or `onBridged` callback. This is especially relevant for `SessionEvent.Bridged` since `onBridged` calls `refreshUser()` — a duplicate call is harmless but unintended.

---

## 8. Refactoring Recommendations

### 1. Extract an `AuthRepository` (highest value, low effort)
Move `loginSuspend` and `getMe` calls — currently scattered across `AuthViewModel` and `LoginViewModel` — into a single `AuthRepository`. Own token read/write there too. Both ViewModels become thin.

```kotlin
class AuthRepository(private val prefs: SharedPreferences) {
    suspend fun login(email: String, password: String): Result<String> { ... }
    suspend fun getMe(): Result<User> { ... }
    fun saveToken(token: String) { ... }
    fun clearToken() { ... }
    fun getToken(): String? { ... }
}
```

### 2. Introduce a `TokenStore` (low effort, high clarity)
`SharedPreferences("auth_prefs")` is accessed directly in three places (`AuthViewModel`, `LoginViewModel`, `AuthInterceptor`). The key `"access_token"` is a magic string repeated across files. Extract to a single class:

```kotlin
class TokenStore(context: Context) {
    fun get(): String?
    fun set(token: String)
    fun clear()
}
```

### 3. Use build-variant base URL, not hardcoded string
Replace `RetrofitClient.BASE_URL` with `BuildConfig.API_BASE_URL` and set it per build variant in `build.gradle`:
```gradle
buildTypes {
    debug   { buildConfigField "String", "API_BASE_URL", '"http://172.20.10.2:8000/"' }
    release { buildConfigField "String", "API_BASE_URL", '"https://api.yourproductiondomain.com/"' }
}
```

### 4. Remove dead API methods
Delete `ApiService.register()`, `ApiService.login()` (Call-based), and `ApiService.me()` (Call-based). They are unused and create confusion about which overload to call.

### 5. Replace direct ViewModel MutableStateFlow write in LoginScreen
Change `viewModel.email.value = it` to a ViewModel method `viewModel.onEmailChanged(it)`. This encapsulates the state mutation and avoids exposing `MutableStateFlow` as public API.

### 6. Handle 401 in SessionRepository / propagate to AuthViewModel
When `getSession` or `createSession` returns 401, emit a distinct error type (e.g. `SessionError.Unauthorized`) and let `SessionViewModel` signal `AuthViewModel` to log out. The simplest approach is an `onUnauthorized: () -> Unit` callback passed to `SessionViewModel` (or handled via a shared `AuthEvent` flow).

### 7. Disable BODY-level HTTP logging in release builds
```kotlin
level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BODY
        else HttpLoggingInterceptor.Level.NONE
```

### 8. Add a cancel button and request timeout for the `Creating` state
Set an OkHttp `callTimeout` (e.g. 15 seconds) and add a "Cancel" button visible during `SessionUiState.Creating` that calls `viewModel.reset()`.

---

## 9. Code Quality Observations

**Unused code:**

- `ApiService.register()` — defined, never called, no registration screen exists.
- `ApiService.login()` (callback `Call<>`) — superseded by `loginSuspend`; comment says "kept, not actively used".
- `ApiService.me()` (callback `Call<>`) — superseded by `getMe`; same comment.
- `Models.kt` contains `RegisterRequest` — only used by the dead `register` endpoint.

**Inconsistent naming:**

- `ApiService.createSession` maps to `POST /start-prank`, but the endpoint is named `start-prank` while the Kotlin method is `createSession`. Inconsistency between HTTP resource name and method name makes it harder to trace which endpoint is being called.
- `SessionRepository.createSession` and `getSession` follow REST naming, but `ApiService.getSession` calls `GET /pranks/{id}` — the path segment is `pranks`, not `sessions`. The naming is inconsistent between layers.
- `BackendSessionState` is a fine name, but the `Session` domain model uses it as `session.state` — so callers write `session.state: BackendSessionState`. The `Backend` prefix is redundant once it's inside the domain object; `SessionState` would be cleaner.

**Overly manual pattern:**

- `SessionRepository.toDomain()` uses `BackendSessionState.valueOf(this.state)` with a catch that maps unknown states to `FAILED`. This is correct but silent — an unknown state from the backend (e.g. a new state added server-side) will silently appear as `FAILED` with no log. Worth adding a warning log before returning `FAILED`.

**Missing abstraction:**

- There is no `Screen` or navigation abstraction. All "navigation" is implicit state switching inside `MainActivity`'s `when(authState)` and `DashboardScreen`'s `when(sessionState)`. For the current screen count (3 screens) this is acceptable. It will become unmanageable at 5+ screens. Consider Compose Navigation before adding the next screen.

**Class size:**

- All classes are appropriately small and focused. No god classes. `DashboardScreen.kt` at 123 lines is the largest file and is only that long because it hosts three small private composables (`UserHeader`, `SessionInputForm`, `SessionResultScreen`) that could each be their own file but do not need to be yet.
