# Backend Codebase Review

---

## 1. Project Structure

```
backend/
├── app/
│   ├── main.py                        # FastAPI app, all routes, webhook handler, lifespan
│   ├── auth.py                        # Password hashing, JWT creation/verification
│   ├── database.py                    # Engine, session factory, Base, get_db dependency
│   ├── dependencies.py                # get_current_user FastAPI dependency
│   ├── models/
│   │   ├── __init__.py                # Re-exports User, PrankSession
│   │   ├── user.py                    # User ORM model
│   │   └── prank_session.py           # PrankSession ORM model + PrankSessionState enum
│   └── services/
│       ├── prank_orchestrator.py      # State machine event handler, timeout worker, per-session locks
│       ├── prank_session_service.py   # DB operations: create, fetch, transition, charge
│       └── telnyx_call_service.py     # Telnyx API wrapper: dial, bridge, hangup, playback
├── alembic/
│   ├── env.py                         # Async migration runner
│   └── versions/
│       └── 0001_initial_schema.py     # Initial schema: users + prank_sessions + enum + constraints
└── tests/
    ├── conftest.py                    # Stubs app.database to avoid needing a live DB
    ├── test_orchestrator.py           # Unit tests for PrankOrchestrator and timeout worker
    └── test_state_machine.py          # Unit tests for PrankSessionService transitions
```

**Module responsibilities:**

| Module | Role |
|---|---|
| `main.py` | HTTP entry point. Defines all routes, Pydantic schemas, webhook parsing, and the `_initiate_prank_session` helper. Acts as the wiring layer between HTTP and services. |
| `auth.py` | Pure functions: bcrypt password hashing and JWT encode/decode. No I/O. |
| `database.py` | Creates the async SQLAlchemy engine and session factory. Provides `get_db` generator for FastAPI dependency injection. |
| `dependencies.py` | `get_current_user` dependency — validates JWT, fetches User from DB, raises 401 on failure. |
| `models/user.py` | ORM mapping for the `users` table. |
| `models/prank_session.py` | ORM mapping for `prank_sessions`. Defines `PrankSessionState` enum. Includes a DB-level `CheckConstraint` requiring both `call_control_id`s before BRIDGED/PLAYING_AUDIO/COMPLETED. |
| `prank_session_service.py` | All DB mutations for a session: `create_session`, `get_session`, `transition_state`, `set_call_control_id`, `charge_and_transition_to_bridged`. Owns transition validation logic. |
| `prank_orchestrator.py` | Stateless class. Maps `(current_state, event_type, leg)` tuples to service calls and Telnyx API calls. Holds the per-session `asyncio.Lock` dict. Creates and tracks timeout worker tasks. |
| `telnyx_call_service.py` | Thin async HTTP client over the Telnyx REST API. Wraps all four operations (dial, bridge, hangup, playback) with a 3-attempt retry. |
| `alembic/` | Schema migration. Single migration creates both tables, the PostgreSQL enum type, indexes, and the check constraint. |

The separation of concerns is clean. `main.py` is the only file that imports from all layers, which is acceptable for a monolith at this scale. The orchestrator is stateless across requests; all durable state lives in the DB via the service layer.

---

## 2. Request Flow

### Step 1 — Android → `POST /start-prank`
`main.py:start_prank` receives `StartPrankRequest(recipient_phone_number)`. It reads `current_user` from `get_current_user` (JWT → DB lookup). Performs a pre-flight credit check (`credits < 1 → 400`). Calls `_initiate_prank_session`.

### Step 2 — Session creation
`_initiate_prank_session` (main.py:75) instantiates `PrankSessionService(db)`. Calls `service.create_session(sender, recipient, user_id)` which inserts a row in state `CREATED` and returns the `PrankSession` object. Immediately transitions to `CALLING_SENDER` via `service.transition_state`. Two DB commits have now occurred.

### Step 3 — Sender call initiated
Still in `_initiate_prank_session`: `TelnyxCallService().create_outbound_call(to=sender_phone, from=TELNYX_NUMBER, session_id, leg="sender")` is called. This POSTs to `https://api.telnyx.com/v2/calls` with a `client_state` field containing base64-encoded JSON `{"session_id": "...", "leg": "sender"}`. The `session_id` is returned to Android as `{"session_id": "..."}`. The HTTP request to Android is now complete.

### Step 4 — Telnyx webhook: sender answers
Telnyx dials the sender. When the sender picks up, Telnyx POSTs `call.answered` to `POST /webhooks/telnyx`. `main.py:telnyx_webhook` decodes `client_state`, extracts `session_id` and `leg="sender"`, maps event to `PrankEventType.LEG_ANSWERED`, creates `PrankOrchestrator(db)`, calls `orchestrator.handle_event(session_id, LEG_ANSWERED, "sender", call_control_id)`.

### Step 5 — Orchestrator: CALLING_SENDER → CALLING_RECIPIENT
Inside `_handle_event_locked` (prank_orchestrator.py:98): state is `CALLING_SENDER`, event is `LEG_ANSWERED + sender`. Calls `service.set_call_control_id(session, "sender", ccid)` (commits). Calls `service.transition_state(session, CALLING_RECIPIENT)` (commits). Calls `telnyx.create_outbound_call(to=recipient_phone, leg="recipient")`. Returns; webhook responds 200.

### Step 6 — Telnyx webhook: recipient answers
Telnyx dials the recipient. When they answer, another `call.answered` webhook arrives with `leg="recipient"`. The orchestrator is now in `CALLING_RECIPIENT` state.

### Step 7 — Charge and bridge
`_handle_event_locked` (line 117): calls `service.set_call_control_id(session, "recipient", ccid)` then `service.charge_and_transition_to_bridged(session)`. Inside that function: decrements `user.credits -= 1`, sets `session.charged = True`, sets `session.state = BRIDGED`, commits everything in one transaction. Returns `True`. Back in the orchestrator: calls `telnyx.bridge_calls(recipient_ccid, sender_ccid)`.

### Step 8 — Telnyx webhook: bridge confirmed
Telnyx fires `call.bridged` for both legs. The orchestrator ignores the recipient-leg event. On the sender-leg `LEG_BRIDGED`: sleeps 300ms for media path stabilisation, then concurrently calls `telnyx.start_playback` for both legs, transitions to `PLAYING_AUDIO`, and spawns `_call_timeout_worker` as a background `asyncio.Task`.

### Step 9 — Audio plays, call runs
The audio plays over the bridge. The session stays in `PLAYING_AUDIO`. Android polls `GET /pranks/{id}` and sees state progress.

### Step 10 — Completion
Either: a leg hangs up → `call.hangup` webhook → orchestrator in `PLAYING_AUDIO` transitions to `COMPLETED`. Or: the timeout fires → `_call_timeout_worker` hangs up both legs and transitions `PLAYING_AUDIO → COMPLETED`.

---

## 3. State Machine Analysis

```
CREATED
  │  trigger: _initiate_prank_session (main.py:91)
  ▼
CALLING_SENDER
  │  trigger: LEG_ANSWERED + leg=sender (webhook)
  ▼
CALLING_RECIPIENT
  │  trigger: LEG_ANSWERED + leg=recipient (webhook)
  ▼
BRIDGED
  │  trigger: LEG_BRIDGED + leg=sender (webhook)
  ▼
PLAYING_AUDIO
  │  trigger: LEG_HANGUP or LEG_FAILED (any leg) (webhook)
  │           OR timeout worker fires
  ▼
COMPLETED

Any non-COMPLETED state → FAILED (on LEG_FAILED, LEG_HANGUP, or credit check failure)
```

### Per-state event table

| State | Accepted events | Transition | Module |
|---|---|---|---|
| `CALLING_SENDER` | `LEG_ANSWERED + sender` | → `CALLING_RECIPIENT` | `prank_orchestrator.py:99` |
| `CALLING_SENDER` | `LEG_FAILED + sender` | → `FAILED` | `prank_orchestrator.py:109` |
| `CALLING_RECIPIENT` | `LEG_ANSWERED + recipient` | → `BRIDGED` (+ charge) | `prank_session_service.py:91` |
| `CALLING_RECIPIENT` | `LEG_FAILED + recipient` | → `FAILED` | `prank_orchestrator.py:132` |
| `CALLING_RECIPIENT` | `LEG_HANGUP + sender` | → `FAILED` | `prank_orchestrator.py:134` |
| `BRIDGED` | `LEG_BRIDGED + sender` | → `PLAYING_AUDIO` | `prank_orchestrator.py:142` |
| `BRIDGED` | `LEG_BRIDGED + recipient` | silently ignored | `prank_orchestrator.py:162` |
| `BRIDGED` | `LEG_HANGUP or LEG_FAILED` | → `FAILED` | `prank_orchestrator.py:169` |
| `PLAYING_AUDIO` | `LEG_HANGUP or LEG_FAILED` | → `COMPLETED` | `prank_orchestrator.py:178` |
| `PLAYING_AUDIO` | `LEG_BRIDGED` | silently ignored (late event) | `prank_orchestrator.py:181` |
| `COMPLETED` or `FAILED` | any | silently ignored | `prank_orchestrator.py:188` |
| any state | unexpected event | `raise ValueError` → caught by webhook handler, logged, 200 returned | `prank_orchestrator.py:112, 137, 173, 184` |

### Atomicity
All transitions call `service.transition_state()` which calls `db.commit()` followed by `db.refresh()`. Each commit is a single PostgreSQL transaction. `charge_and_transition_to_bridged` performs the credit deduction, `session.charged = True`, and `session.state = BRIDGED` in a single transaction — these three changes are atomic.

### Invalid transition prevention
`transition_state` (prank_session_service.py:51) enforces a whitelist via `_ALLOWED_TRANSITIONS`. Any non-whitelisted forward transition raises `ValueError` before touching the DB. `FAILED` is allowed from any non-`COMPLETED` state as a special case. A duplicate no-op transition (same → same state) is silently skipped at line 54-60 without a DB write. There is additionally a DB-level `CheckConstraint` that prevents rows in BRIDGED/PLAYING_AUDIO/COMPLETED from having NULL call control IDs.

---

## 4. Concurrency Safety

### Per-session locking mechanism
`_session_locks` (prank_orchestrator.py:18) is a module-level `dict[UUID, asyncio.Lock]`. When `handle_event` is called, it calls `_session_locks.setdefault(session_id, asyncio.Lock())` to get or create the lock for that session, then acquires it before entering `_handle_event_locked`. This serialises all event processing for a given session within a single process.

### Duplicate webhook protection
Telnyx delivers webhooks at least once. The main idempotency guard for the most dangerous case (double charge) is `session.charged` in `charge_and_transition_to_bridged`: if already `True`, the function returns immediately without touching `user.credits`. For state transitions, the same-state no-op check in `transition_state` (line 54) prevents `ValueError` on duplicate transitions — commit is skipped, state is unchanged.

### Race condition: multiple workers
**This is the most significant concurrency risk.** `_session_locks` is an in-process `asyncio.Lock`. It provides no protection when the application runs with multiple workers (e.g. `uvicorn --workers 2`, gunicorn multi-process). In that deployment:

- Two different Telnyx webhook deliveries for the same session can arrive at different worker processes simultaneously.
- Both workers execute `handle_event` concurrently with no mutual exclusion.
- Both can read the session from DB with the same state.
- Both can enter `charge_and_transition_to_bridged` with `session.charged = False`.
- Both execute `user.credits -= 1` on their own SQLAlchemy identity maps.
- Both commit. PostgreSQL sees two separate UPDATE statements. The second commit wins and overwrites the first, resulting in a credit being deducted once (not twice) — or depending on transaction isolation, potentially twice.

Specifically: with the default PostgreSQL `READ COMMITTED` isolation, both transactions read `credits = N`, both compute `N - 1`, and both commit `credits = N - 1`. The net result is **one credit deducted instead of two** (not a double charge, but correctness is lost if multi-process scaling is ever used).

### Duplicate webhook with single worker
With a single worker, the asyncio lock prevents two events from processing simultaneously. A duplicate `LEG_ANSWERED + recipient` would:
1. First delivery: state = `CALLING_RECIPIENT`, `charged = False` → charge succeeds, state → `BRIDGED`.
2. Second delivery: state = `BRIDGED`, `LEG_ANSWERED` is not handled in `BRIDGED` → `raise ValueError` → caught by webhook handler → 200 returned, no side effects.

### Out-of-order webhooks
In `CALLING_SENDER` state, any event other than `LEG_ANSWERED+sender` or `LEG_FAILED+sender` raises `ValueError`. If `LEG_ANSWERED + recipient` arrives while still in `CALLING_SENDER` (theoretically impossible since the recipient is not called yet, but relevant if `client_state` is malformed or a stale webhook arrives), it raises `ValueError` and is discarded. This is correct behaviour but not logged with enough context to diagnose.

The previously observed error — `ValueError: Unexpected event LEG_ANSWERED + leg='sender' in state CALLING_RECIPIENT` — is caused by Telnyx re-delivering the sender's `call.answered` event after the state has already advanced to `CALLING_RECIPIENT`. This is benign (caught, logged, 200 returned) and does not affect the session.

---

## 5. Credit Charging Safety

### Deduction location
`prank_session_service.py:113` — `user.credits -= 1` inside `charge_and_transition_to_bridged`.

### Idempotency guard
`session.charged` (Boolean, DB-persisted). Checked at line 100 before any credit operation. If `True`, the function returns immediately. Because `session.charged` is set to `True` in the same DB transaction as `user.credits -= 1`, the atomicity is correct: either both succeed or neither does.

### Duplicate billing analysis (single process)
Safe. The asyncio lock prevents concurrent execution for the same session. If a duplicate `LEG_ANSWERED + recipient` is delivered after the state has moved to `BRIDGED`, the orchestrator raises `ValueError` before `charge_and_transition_to_bridged` is ever called.

### Duplicate billing analysis (multi-process)
Not safe, as described in Section 4. Without a `SELECT ... FOR UPDATE` on the `prank_sessions` row (to prevent concurrent access), two processes can both see `charged = False` and both set `charged = True` in separate transactions. The last writer wins on `session.charged`, but `user.credits` is decremented by both, depending on transaction timing.

### Pre-flight check is not atomic with charge
`main.py:145` checks `current_user.credits < 1` before initiating the session. This is a convenience guard — it does not prevent the user from being debited by a concurrent session that was initiated at the same time. The `User` object fetched in `get_current_user` is already committed before `charge_and_transition_to_bridged` runs for any session. A user with 1 credit who fires two simultaneous `POST /start-prank` requests could create two sessions, pass both pre-flight checks, and have both sessions attempt to charge — resulting in `user.credits = -1`. There is no `CHECK (credits >= 0)` constraint in the DB to prevent this.

### Bug: dead code path in `charge_and_transition_to_bridged`
Lines 104-105:
```python
if session.state == PrankSessionState.BRIDGED:
    return session   # returns session object, not bool
```
This path is only reachable if the session is already `BRIDGED` but `session.charged` is `False`. This cannot happen in normal single-process operation (BRIDGED is only set by this function, which also sets `charged = True`). It returns the session object (truthy), so `if not bridged:` in the orchestrator evaluates to `False`, proceeding normally without charging. In multi-process scenarios this path could be reached and would silently skip charging. The second `if not session.charged:` block at line 107 is also unreachable (already checked at line 100) — this is dead code that adds confusion.

---

## 6. Timeout Handling

### Timer creation
`_call_timeout_worker` (prank_orchestrator.py:21) is created via `asyncio.create_task(...)` at line 155, immediately after the `PLAYING_AUDIO` transition. The task is stored in the module-level `_active_tasks: set[asyncio.Task]` with a `add_done_callback(_active_tasks.discard)` to auto-remove on completion. This prevents the task from being garbage-collected while it sleeps.

### Duration
Read from `os.environ["MAX_CALL_DURATION_SECONDS"]` at task start (not at app startup). The lifespan check at startup validates the variable is present, but the value is re-read each time a timeout worker starts. A value change mid-run would affect new sessions only.

### Hangup mechanism
After `asyncio.sleep(duration)`, the worker creates a fresh `TelnyxCallService()` and calls `hangup_call` for both `sender_call_control_id` and `recipient_call_control_id`. Each hangup is individually try/except'd — a failure on one leg does not prevent the other from being hung up. This is correct since a leg may already be down.

### State transition after timeout
The worker opens a new `SessionLocal()` DB session (correct — separate from any request-scoped session). Fetches the session fresh from DB. Only transitions to `COMPLETED` if state is still `PLAYING_AUDIO`. If the call already ended naturally (state is `COMPLETED` or `FAILED`), the worker logs and returns without DB mutation.

### Timer leak risk
If `LEG_BRIDGED + sender` fires twice (duplicate webhook), the orchestrator enters the `BRIDGED` handler a second time. It calls `asyncio.sleep(0.3)` then checks `if session.state != PrankSessionState.BRIDGED: return` — at this point the state is already `PLAYING_AUDIO`, so it returns before re-starting playback. However, `asyncio.create_task(_call_timeout_worker(...))` is called **before** this guard check at line 155. Looking at the code more carefully:

```python
# prank_orchestrator.py:142-161
elif state == PrankSessionState.BRIDGED:
    if event_type == PrankEventType.LEG_BRIDGED and leg == "sender":
        await asyncio.sleep(0.3)
        if session.state != PrankSessionState.BRIDGED:   # ← guard is AFTER sleep
            return
        await asyncio.gather(start_playback × 2)
        await service.transition_state(session, PLAYING_AUDIO)
        task = asyncio.create_task(_call_timeout_worker(...))  # ← task created here
```

The `create_task` is inside the block that only runs when `session.state == BRIDGED` after the 300ms sleep. A duplicate `LEG_BRIDGED + sender` arriving after the first one has already advanced state to `PLAYING_AUDIO` would: read `state = BRIDGED` at the top of `_handle_event_locked` (line 95-96) — but by the time it reads state, if processing is serialised by the lock, state would already be `PLAYING_AUDIO`, so it would fall into the `PLAYING_AUDIO` handler and be silently ignored as a "late bridged event." Timer leak is therefore prevented by the lock in single-process operation.

### Missing: no timer reference stored per session
The timeout task is stored in the global `_active_tasks` set but not keyed by session ID. There is no way to cancel the timer for a specific session if it ends naturally. This is acceptable because the timer checks state before acting, but it means the task sleeps uselessly for the full duration even if the call ended in the first second.

---

## 7. Telnyx Integration

### Responsibilities of `TelnyxCallService`
Four operations: `create_outbound_call`, `bridge_calls`, `hangup_call`, `start_playback`. Each wraps an httpx POST to the Telnyx v2 REST API. The class is stateless and instantiated per-call-site.

### Retry logic
`_retry(func, retries=3)` with linear backoff: 0.5s, 1.0s (0.5 × attempt). Retries on any exception, including HTTP 4xx. This is incorrect — a 4xx response (e.g. 404 call not found, 422 invalid param) should not be retried; it will never succeed. The `response.raise_for_status()` raises `httpx.HTTPStatusError`, which `_retry` catches and retries, burning all three attempts before propagating. For 5xx or network errors, retry is appropriate. For 4xx, it wastes 1.5 seconds and adds noise.

### Error handling
All operations call `response.raise_for_status()`. Exceptions propagate to the caller (the orchestrator), which handles them at the call sites:
- `create_outbound_call` failures propagate out of `_initiate_prank_session` with no try/except → 500 to Android.
- `bridge_calls` failure is caught in the orchestrator → session transitions to `FAILED`.
- `hangup_call` failure in timeout worker is caught per-leg → logged, continues.
- `start_playback` failures are NOT caught in the orchestrator (line 150: `asyncio.gather(start_playback × 2)` — if either raises, it propagates out of `_handle_event_locked` → `ValueError` handler in webhook → logged, 200 returned, session stays in `BRIDGED` with no playback and no further state advance). This is a silent failure mode: the call is bridged and live but the audio never plays and the session never advances past `BRIDGED`.

### Idempotency concerns
Telnyx `bridge_calls` and `start_playback` are not idempotent by nature. The retry mechanism may send duplicate bridge or playback commands if a network error occurs after the request was received by Telnyx. Telnyx does not provide idempotency keys on these endpoints. Duplicate playback could cause audio to play twice (overlay mode is set to `True`, so a second `playback_start` would layer audio). This is unlikely in practice but unhandled.

### Audio URL
`start_playback` uses a hardcoded ngrok URL: `"https://uncabled-zina-fusilly.ngrok-free.dev/static/test.mp3"`. This is a development tunnel. In production this URL will be unavailable, playback will fail, and the call will be bridged in silence.

### `call_control_id` storage reliability
The `call_control_id` for each leg is not returned from `create_outbound_call` (the Telnyx API does return one in the response, but the code discards the response body at line 53). The `call_control_id` is instead received via the `call.answered` webhook and stored by `set_call_control_id`. This means there is a window between the call being placed and the webhook arriving where the `call_control_id` is unknown. If a hangup is needed during that window (e.g. the other leg failed), the system cannot hang up the new call. This is an acceptable trade-off for the current design but is worth noting.

### No webhook signature verification
`POST /webhooks/telnyx` (main.py:167) has no authentication. Any HTTP client can POST crafted events with arbitrary `session_id` and `leg` values to trigger state transitions, credit charges, or hangups. Telnyx provides HMAC-SHA256 webhook signatures via the `telnyx-signature-ed25519-*` headers. These are not checked anywhere in the codebase.

### No httpx timeout
`httpx.AsyncClient()` is created with no `timeout` parameter, which defaults to 5 seconds for httpx 0.20+. This is acceptable. However, this should be explicitly set to avoid surprises across httpx version changes.

---

## 8. Database Consistency

### Session factory configuration
`database.py:8`: `async_sessionmaker(engine, expire_on_commit=False)`. `expire_on_commit=False` means ORM objects remain usable after a commit without triggering lazy loads. This is the correct choice for async SQLAlchemy where implicit I/O is not allowed.

### Commit strategy
Each `PrankSessionService` method performs exactly one `db.commit()` + `db.refresh()` call. The `charge_and_transition_to_bridged` function combines three mutations (user.credits, session.charged, session.state) into a single transaction. This is correct and atomic.

`set_call_control_id` is a separate commit from `charge_and_transition_to_bridged`, meaning there is a window between the recipient's `call_control_id` being stored and the BRIDGED transition where the row has a `call_control_id` set but state is still `CALLING_RECIPIENT`. This is fine — the CheckConstraint only fires on the BRIDGED commit, by which time both IDs are already set.

### Missing DB-level constraint: credits cannot go negative
`user.credits` has no `CHECK (credits >= 0)` constraint. A TOCTOU race (two concurrent sessions for the same user, both passing the pre-flight check) can result in `credits = -1`. PostgreSQL would accept this write. Adding `CHECK (credits >= 0)` would cause the offending commit to raise `IntegrityError`, preventing negative balances.

### Missing SELECT FOR UPDATE
`charge_and_transition_to_bridged` fetches the User via `session.get(User, session.user_id)` — a plain SELECT with no row lock. Under concurrent execution (multi-process deployment), two transactions can both read the same `credits` value and both decrement it, producing the wrong final value. A `SELECT ... FOR UPDATE` on the User row would prevent this.

### Identity map / stale read risk
`session.get(User, user_id)` (prank_session_service.py:108) queries the SQLAlchemy identity map first. If the `User` object was loaded earlier in the same `AsyncSession` (e.g. in `get_current_user` during the webhook request), the cached object is returned without hitting the DB. However, the webhook endpoint does not call `get_current_user` (it is unauthenticated), so the `AsyncSession` is fresh and `session.get` will issue a SELECT. This is safe for the webhook path but brittle — the correctness depends on the User not having been loaded earlier in the same session.

### Migration correctness
`0001_initial_schema.py` creates:
- `users`: correct columns, index on email (unique), no `CHECK (credits >= 0)` (missing).
- `prank_sessions`: correct columns, FK to users with `ON DELETE CASCADE`, indexes on `user_id`, `state`, `created_at`, CheckConstraint for bridged states requiring both CCIDs.
- PostgreSQL ENUM type `pranksessionstate` created separately before the table — correct for PostgreSQL.

`downgrade()` drops indexes, tables, and the enum in the correct order. The `charged` column has no migration comment explaining why it exists separately from state — minor documentation gap.

### Foreign key: cascade delete
`prank_sessions.user_id` has `ON DELETE CASCADE`. Deleting a user deletes all their sessions. This is an intentional choice but could be dangerous in production if admin tooling deletes users without awareness of the billing implications. There is no soft-delete mechanism.

---

## 9. Logging and Observability

### What is currently logged

| Event | Location | Log level |
|---|---|---|
| Session created | `main.py:87` | INFO |
| Sender leg answered | `prank_orchestrator.py:100` | INFO |
| Recipient leg answered | `prank_orchestrator.py:118` | INFO |
| Insufficient credits at bridge time | `prank_orchestrator.py:123` | INFO |
| Bridge requested | `prank_orchestrator.py:127` | INFO |
| Bridge failed | `prank_orchestrator.py:129` | EXCEPTION |
| Leg lost before playback | `prank_orchestrator.py:171` | INFO |
| Session completed (hangup/fail) | `prank_orchestrator.py:180` | INFO |
| Late bridged event | `prank_orchestrator.py:182` | INFO |
| Timeout worker started | `prank_orchestrator.py:28` | INFO |
| Timeout triggered | `prank_orchestrator.py:35` | INFO |
| Timeout hangup issued/failed | `prank_orchestrator.py:40-42` | INFO/WARNING |
| Timeout state transition skipped | `prank_orchestrator.py:53` | INFO |
| Bridge started (Telnyx) | `telnyx_call_service.py:72` | INFO |
| Playback started (Telnyx) | `telnyx_call_service.py:111` | INFO |
| Webhook bad payload | `main.py:189` | EXCEPTION |
| Orchestrator rejected event | `main.py:201` | EXCEPTION |

### Important events NOT logged

1. **Credit deduction success** — `charge_and_transition_to_bridged` never logs "charged user X, credits now N". When investigating a billing issue, there is no audit trail in logs. Only the DB can tell you whether a charge occurred.

2. **State transitions** — `transition_state` does not log the transition. The only way to reconstruct the state history from logs is through the orchestrator's event logs, which cover most but not all paths.

3. **`set_call_control_id`** — no log. If a `call_control_id` is overwritten by a duplicate webhook, there is no record.

4. **Webhook received (before processing)** — there is no entry log for each webhook arrival. Logging `event_type`, `session_id`, and `leg` at the start of `telnyx_webhook` would be essential for production debugging.

5. **Telnyx API errors during retry** — `_retry` does not log intermediate failures. If Telnyx returns 500 and the first two retries fail silently before the third succeeds, there is no record.

6. **`create_outbound_call` result** — the call creation response (which contains the `call_control_id`) is never logged. If the outbound call silently failed, the logs would show nothing until the timeout fires.

7. **No structured logging / trace ID** — all log messages use `session_id` as a manual correlation key, but there is no request ID threading through the full webhook chain. In a system where one prank call generates ~10 webhook events across ~30 seconds, correlating all events for a single call requires manually filtering logs by `session_id`.

---

## 10. Potential Design Risks

### Risk 1 — No webhook signature verification (Critical for production)
`POST /webhooks/telnyx` is completely unauthenticated. Any actor who knows the webhook URL can:
- Fabricate `call.answered` events to trigger credit charges against any session.
- Fabricate `call.hangup` events to terminate active sessions.
- Replay real events to cause double-processing.

Telnyx signs every webhook with an Ed25519 key. The `telnyx-signature-ed25519-signature` and `telnyx-signature-ed25519-timestamp` headers must be verified before processing.

### Risk 2 — Multi-process deployment breaks concurrency guarantees (High)
The entire concurrency model relies on `asyncio.Lock` in `_session_locks`. This works for a single uvicorn worker but fails silently under any multi-process deployment. There is no warning, no error, and no documentation. Deploying with `--workers 2` would introduce race conditions in credit charging and state transitions without any observable indication.

### Risk 3 — `user.credits` can go negative; no DB constraint (High)
Two rapid `POST /start-prank` requests from the same user with 1 credit will both pass the pre-flight check (`credits < 1`), both create sessions, and both attempt to charge. With no `CHECK (credits >= 0)` and no row lock, both charges succeed and `user.credits` becomes `-1`. This is a real billing vulnerability if credits have monetary value.

### Risk 4 — `start_playback` failure is silently absorbed (Medium)
If `telnyx.start_playback` raises (e.g. 422 from Telnyx, network error), the exception propagates out of `asyncio.gather`, exits `_handle_event_locked`, and is caught by the `except ValueError` block in the webhook handler — except it is not a `ValueError`, it is an `httpx.HTTPStatusError`. That means it propagates past the `except ValueError` block and becomes an unhandled exception in `telnyx_webhook`, causing FastAPI to return a 500. Telnyx will retry the webhook. The session state is `BRIDGED` (already committed). The retry will re-enter the `BRIDGED` handler and attempt playback again. This self-heals on retry, but it is unintentional and not documented.

More critically: if all retries fail, the webhook handler returns 500 repeatedly, Telnyx exhausts its retry budget, and the session is permanently stuck in `BRIDGED` — bridged but silent, never completing, never timing out (the timeout task was not created because it is created after `asyncio.gather`).

### Risk 5 — Hardcoded ngrok audio URL (Medium, production blocker)
`telnyx_call_service.py:103`: `"https://uncabled-zina-fusilly.ngrok-free.dev/static/test.mp3"`. This is a development tunnel that will be offline in production. Playback will fail for every call. Should be `os.environ["AUDIO_URL"]` or similar.

### Risk 6 — No idempotency key on `POST /start-prank` (Medium)
A network timeout on the Android side after the server has already created the session and initiated the call will cause Android to retry. The second request creates a second session and dials the sender again. The user now has two active sessions competing for their one credit. The pre-flight check is per-request and does not check for in-progress sessions. Adding a check for active sessions before creating a new one would prevent this.

### Risk 7 — `dev/start-prank` endpoint is unrestricted in production code (Medium)
`POST /dev/start-prank` accepts arbitrary `sender_phone` and `recipient_phone` from any authenticated user. It has no dev-mode guard. A normal user can use this endpoint to spoof their sender number to any phone number, making the call appear to come from an arbitrary number. This may violate telephony regulations and Telnyx ToS.

### Risk 8 — JWT expiry is 30 minutes, hardcoded (Low)
`auth.py:9`: `ACCESS_TOKEN_EXPIRE_MINUTES = 30`. This is a constant, not configurable. There is no refresh token mechanism. A user whose token expires mid-session will get 401s on `GET /pranks/{id}` polling, but since the webhook processing is server-side, the session will complete correctly — the client just won't see updates until re-login. This is a UX issue, not a security issue.

### Risk 9 — JWT algorithm is partially configurable (Low)
`JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")`. If misconfigured to `"none"`, JWT verification would accept unsigned tokens. `python-jose` by default does not accept `"none"` for `decode`, but the code does not explicitly reject it. Should explicitly enforce `algorithm="HS256"` without an env override, or validate the algorithm value on startup.

---

## 11. Refactoring Recommendations

### 1. Verify Telnyx webhook signatures (Critical, ~30 lines)
Before any parsing, verify the `telnyx-signature-ed25519-signature` and `telnyx-signature-ed25519-timestamp` headers using the Telnyx public key. Reject any request that fails verification with 400. This eliminates the entire class of webhook spoofing attacks.

### 2. Move audio URL to environment variable (Critical, 1 line)
Replace the hardcoded ngrok URL in `telnyx_call_service.py:103` with `os.environ["AUDIO_URL"]`. Add it to the lifespan startup check alongside `MAX_CALL_DURATION_SECONDS`. This is a production blocker that is trivially fixed.

### 3. Add `CHECK (credits >= 0)` to the `users` table (High, 1 migration)
Add a new Alembic migration:
```sql
ALTER TABLE users ADD CONSTRAINT ck_users_credits_non_negative CHECK (credits >= 0);
```
This turns a silent billing bug into an `IntegrityError` that is caught, logged, and handled. No application code changes needed — `charge_and_transition_to_bridged` already has a `credits < 1` check that would catch this before the DB constraint fires in normal operation.

### 4. Add `SELECT FOR UPDATE` in `charge_and_transition_to_bridged` (High, 2 lines)
Replace:
```python
user = await self.session.get(User, session.user_id)
```
with a query that locks the row:
```python
result = await self.session.execute(
    select(User).where(User.id == session.user_id).with_for_update()
)
user = result.scalar_one()
```
This prevents concurrent reads from seeing stale credit values under multi-process deployments. This should be implemented together with the `credits >= 0` constraint.

### 5. Guard or remove `POST /dev/start-prank` (Medium, ~5 lines)
Either remove the endpoint entirely, or add an env-based guard:
```python
if not os.environ.get("DEV_MODE"):
    raise HTTPException(status_code=404)
```
The endpoint exists for development convenience but exposes sender number spoofing in production.

### 6. Clean up dead code in `charge_and_transition_to_bridged` (Low, ~5 lines)
Remove lines 104-105 (`if session.state == PrankSessionState.BRIDGED: return session`) — this path is unreachable in correct operation and returns the wrong type. Remove lines 107-114's `if not session.charged:` wrapper since the identical check at line 100 already ensures `session.charged` is `False` at that point. The function body simplifies to a straight-line charge + commit.

### 7. Log the credit deduction (Low, 1 line)
After `user.credits -= 1` in `charge_and_transition_to_bridged`, add:
```python
logger.info("Session %s: charged user %s, credits remaining=%s", session.id, session.user_id, user.credits)
```
This is the most important billing event in the system and currently produces no log output.

### 8. Add a webhook entry log (Low, 1 line)
At the top of `telnyx_webhook`, before parsing, add:
```python
logger.debug("Telnyx webhook received: event_type=%s", data.get("event_type"))
```
After successful parse:
```python
logger.info("Telnyx webhook: event=%s session=%s leg=%s", event_type, session_id, leg)
```
This gives a complete event log without relying on the orchestrator to log each case.

### 9. Add `GET /pranks/{id}` endpoint (Missing feature, ~10 lines)
Android polls `GET /pranks/{id}` (referenced in `ApiService.kt`), but this endpoint is not defined in `main.py`. This endpoint is either implemented elsewhere (not visible in the codebase) or is missing entirely. If missing, all Android polling returns 404 and the session screen never updates. This endpoint should return at minimum `{id, state, charged}`.

### 10. Set explicit httpx timeout (Low, 1 line per client)
Pass `timeout=10.0` to `httpx.AsyncClient()` in `TelnyxCallService` to make the timeout explicit and version-independent.
