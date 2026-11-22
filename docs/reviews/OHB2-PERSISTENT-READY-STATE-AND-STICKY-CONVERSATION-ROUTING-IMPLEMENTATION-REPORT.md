# OHB2 — Persistent Ready State and Sticky Conversation Routing

## 1. Task ID and status

- **Task:** `OHB2-PERSISTENT-READY-STATE-AND-STICKY-CONVERSATION-ROUTING`
- **Status:** **DONE** (implementation and local verification)
- **Scope:** remove the 10-minute route inactivity cutoff, make the persisted
  `last_accessed_conversation:<telegram_id>` the default routing target, preserve
  `/start`, `/chat`, outbox, grouping, confirmation, cleanup, and Mini App behavior.

## 2. Baseline Git state

Recorded before any edit:

- Branch: `main`
- HEAD: `0774c9cff923a2ed02da36a1111a283a61600ea5`
- Tree: `faa7a3f03aa361698c6854281c162358bf38b84f`
- Staged: **0**
- Modified: **24**
- Untracked: **34**
- Ignored: `.openhands/`, `.pytest_cache/`, `__pycache__/` directories (not touched)

Pre-existing modified/untracked work was left untouched. No `git add`, `reset`, `clean`,
checkout/restore, commit, push, PR, merge, deployment, or Autopush operation was performed.

## 3. Exact cause of the 10-minute expiration

The cutoff was the route branch of the routing state, not an outbox or API timeout:

1. `bot/db.py`: `AWAITING_TTL = timedelta(minutes=10)`.
2. `bot/handlers.py::handle_text`: after reading `db.awaiting_state()`, it treated
   `kind == "route"` like a one-shot state and called `db.awaiting_is_expired(awaiting_at)`.
   When expired, it cleared `user_state` and replied
   `"انتهت مهلة التوجيه (10 دقايق من آخر نشاط)..."` without creating outbox work.
3. `bot/db.py::take_awaiting` independently marked an old `route` as `"expired"`.
4. There was no fallback from a cleared/expired route to the persisted
   `last_accessed_conversation:<telegram_id>` setting.

Thus the limitation came from the route state expiry in `handle_text`, with a second
legacy expiry in `take_awaiting`; it was not caused by outbox retry limits or API timeouts.

## 4. Before/after routing lifecycle

### Before

- Open A: `user_state = ("A", "route")` and `last_accessed = "A"`.
- Message within 10 minutes: routed to A.
- Message after 10 minutes: `handle_text` cleared the route and replied that routing
  expired; no outbox item was created.
- `/start` cleared `user_state`; a later text was not routed unless the user opened a
  conversation again or used `/chat`.
- `/chat` used `last_accessed` only for opening the view; ordinary text still needed a
  live route.

### After

- Open/select A: `last_accessed = "A"` and route state point to A.
- Any eligible ordinary text resolves to the persisted `last_accessed` target, even after
  inactivity or process restart. Route state no longer has an inactivity expiry.
- Opening/selecting B atomically updates `last_accessed` and the route target; later
  messages go to B.
- Sending a message does not change the target.
- `/start` clears transient route state but leaves the persisted target; subsequent text
  routes to it. `/chat` opens the persisted target without sending a prompt or creating a
  conversation.
- `/cancel` pauses default routing explicitly, without deleting the persisted target, so
  `/chat` can reopen it later.
- A missing target produces a clear Arabic instruction and no creation/fallback.
- Confirmed unavailable targets are cleared only on the safe, targeted paths described
  below. Transient errors leave the target intact.

## 5. Message paths audited and final behavior

| Path | Behavior after this change |
|---|---|
| Ordinary text | `handle_text` → persisted `last_accessed` target → `_send_prompt` → outbox |
| Existing prompt handler | Same `_send_prompt`/outbox path; source Telegram message ID still recorded |
| `reply` selection | `reply_prompt` persists the selected conversation; unexpired reply uses it; expired reply falls back to the persisted target |
| `route` submission | Route no longer expires; persisted target is authoritative over a stale route row |
| `newchat` / `reposearch` | Existing one-shot 10-minute behavior retained; these are not prompts to an already selected conversation |
| `/chat` | Opens the persisted last conversation; no prompt, no creation |
| `/start` | Existing reset behavior preserved; clears transient route and resumes paused routing |
| `/cancel` and its button | Existing explicit cancellation preserved via `routing_paused:<id>`; stored target remains for `/chat` |
| Commands | Registered `CommandHandler`s remain commands; not forwarded as prompts |
| Attachments/media/captions | Not forwarded to OpenHands by this bot path; unchanged and documented as unsupported for prompt routing |
| Mini App | Frozen; no changes |

## 6. Files changed and reasons

- `bot/db.py`
  - Clarified that `AWAITING_TTL` applies to one-shot states, not `route`.
  - `take_awaiting` no longer expires `route`.
  - Added `routing_paused:<telegram_id>` helpers in the existing `settings` table;
    opening/selecting a conversation clears the pause atomically with the saved target.
- `bot/handlers.py`
  - Route resolution now uses `last_accessed` as the authoritative target; route state
    is synchronized when it differs.
  - Removed route inactivity expiration; added persistent-target fallback for ordinary
    text and expired `reply` state.
  - Added clear no-target Arabic response; no automatic creation or fallback.
  - Updated the open-conversation Arabic hint from a 10-minute window to persistent
    routing.
  - Confirmed remote deletion clears the persisted target/route only when the remote
    deletion state is confirmed; a `deleting` tombstone does not destroy the target.
  - `/start` resumes routing; `/cancel` and its button pause default routing.
- `bot/outbox.py`
  - Added targeted unavailable-target handling for an outbox item whose saved target is
    confirmed missing by an empty result or HTTP 404/410.
  - Failed item is preserved as `failed`; target and route are cleared only when they
    match that conversation; user receives a truthful Arabic notice.
  - Transient errors retain the existing retry/`unknown` behavior and do not clear the
    target.
- `tests/test_4b.py`, `tests/test_handlers.py`, `tests/test_messages.py`,
  `tests/test_wp07_nav06_open_conversation_atomic.py`
  - Updated assertions that encoded the old 10-minute route behavior and old UI hint.
  - Replaced the route-expiry expectation with route-survival and no-hidden-expiry
    expectations.
- `tests/test_persistent_ready_sticky_routing.py` (new)
  - 28 deterministic tests (25 test functions plus parametrization) covering readiness,
    sticky selection, isolation, missing/deleted/transient targets, message paths,
    command registration, rapid grouping, `/start`, and `/chat`.
- `.agent/PROGRESS.md`
  - Appended task status, acceptance summary, and verification counts to the existing
    progress log; no unrelated content was removed.

## 7. Database/schema changes and migration safety

- **No schema migration was added by this task.**
- `routing_paused:<telegram_id>` uses the existing `settings` key/value table.
- The existing `user_state` and `last_accessed_conversation:<telegram_id>` storage are
  reused; no new persistence owner, queue, worker, or scheduler.
- Pre-existing outbox/settings schema changes from earlier work were not altered by this
  task.

## 8. Persistence across inactivity and process restart

- `last_accessed_conversation:<telegram_id>` is stored in SQLite and is read for every
  eligible message.
- `route` state remains in `user_state`, but no longer expires by time. A process restart
  therefore cannot make a previously selected conversation unreachable through a timer.
- `/chat` reads the same persisted setting, so it works after restart without creating a
  conversation or submitting a prompt.
- The new test `test_route_survives_database_reopen_and_process_restart` closes and
  reopens the same SQLite file before routing a message.

## 9. Missing/deleted/unavailable/transient behavior

- **No target:** clear Arabic response
  `"مفيش شات محدد. افتح شات من القائمة أو استخدم /start أو /chat الأول..."`;
  no outbox item and no creation job.
- **Local confirmed remote deletion:** if `remote_deletion_state` is confirmed, the
  persisted target and matching route are cleared; no fallback.
- **Local `deleting` tombstone:** no outbox item and no fallback; the target is retained
  because deletion is not yet confirmed.
- **Outbox saved target missing:** empty `get_conversations` result or HTTP 404/410 for
  the saved target marks the item `failed`, clears only the matching target/route, and
  sends `"الشات المحدد مش موجود أو اتشال..."`.
- **Transient 5xx / 429 / timeout / ambiguous outcome:** existing safe retry or
  `unknown` behavior is preserved; target is not cleared and no fallback occurs.
- The outbox row is retained on failure; the prompt is not silently lost or routed to a
  different conversation.

## 10. `/start` and `/chat` compatibility evidence

- `test_start_is_not_required_after_inactivity`: `/start` clears awaiting; subsequent
  text still routes to the persisted A target.
- `test_chat_opens_last_accessed_without_prompt_or_creation`: `/chat` opens A, creates no
  outbox/creation work, and preserves the target.
- `test_cancel_pauses_default_routing_until_chat_reopens`: `/cancel` stops default routing
  without deleting the stored target; `/chat` reopens it and routing resumes.
- Existing `tests/test_chat_command_last_accessed.py` remains green (12 tests).
- Command registration test confirms `start`, `chat`, and `help` remain
  `CommandHandler`s.

## 11. Outbox, grouping, retry, idempotency, confirmation, cleanup

- No new queue/worker/scheduler was introduced.
- `_send_prompt` still records before delivery, preserves grouping, and passes the source
  Telegram message ID.
- Outbox `pending`/`failed`/`unknown` states and retry caps are unchanged except for the
  targeted confirmed-unavailable branch described above.
- Confirmation wording and cleanup timing were not changed.
- Existing suites passed:
  - `tests/test_prompt_cleanup.py`
  - `tests/test_outbox.py`
  - `tests/test_outbox_commands.py`
  - `tests/test_outbox_concurrency_28c.py`
  - `tests/test_outbox_notice_tombstone.py`
  - `tests/test_outbox_pre_cas_recovery.py`
  - `tests/test_outbox_tombstone_toctou.py`
  - `tests/test_resurrection_fix.py`
  - `tests/test_stabilization_f02_f06.py`
  - `tests/test_audit_remediation_f01_f07.py`

## 12. Tests added, exact commands, and actual results

Commands were run with the repository test virtualenv
`/tmp/ohb2-chat-venv/bin/python` (pytest 9.0.3):

```text
python -m pytest -q tests/test_persistent_ready_sticky_routing.py
=> 28 passed, exit 0

python -m pytest -q tests/test_chat_command_last_accessed.py tests/test_handlers.py \
  tests/test_4b.py tests/test_wp07_route_renewal_and_policy.py \
  tests/test_u04_concurrency.py tests/test_one_shot_awaiting_atomicity.py \
  tests/test_duplicate_update_dispatch.py tests/test_messages.py \
  tests/test_wp07_nav06_open_conversation_atomic.py
=> 290 passed, exit 0

python -m pytest -q
=> 3688 passed, 0 failed, exit 0
```

Baseline focused run before edits was **278 passed, 0 failed**. The final full-suite
increase is **+28 tests** (the new 28-case module). The pre-existing full-suite count
recorded from the immediately preceding task was 3660; no pre-existing failure was
observed in the baseline focused run.

Outbox/delivery regression batch:

```text
python -m pytest -q tests/test_outbox.py tests/test_outbox_commands.py \
  tests/test_outbox_concurrency_28c.py tests/test_outbox_notice_tombstone.py \
  tests/test_outbox_pre_cas_recovery.py tests/test_outbox_tombstone_toctou.py \
  tests/test_resurrection_fix.py tests/test_prompt_cleanup.py \
  tests/test_stabilization_f02_f06.py tests/test_audit_remediation_f01_f07.py
=> 255 passed, exit 0
```

## 13. Lint, static analysis, security, dependency, and diff checks

```text
python -m py_compile <changed Python files>       => 0
python -m pyflakes bot/ automation/ tools/ main.py tests/ => 0
python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
  => exit 0; High 0, Medium 19, Low 5
python -m pip_audit -r requirements-dev.txt       => exit 0; no known vulnerabilities
node --test tests/frontend/*.test.js              => 280 passed, 0 failed, exit 0
git diff --check                                  => exit 0
```

## 14. Limitations and unsupported message types

- No real Telegram or OpenHands production call was made; all external interactions in
  the new tests are fakes. Runtime behavior against the live services is **UNVERIFIED**.
- `newchat` and `reposearch` retain their existing 10-minute one-shot expiry; they are
  not prompts to an already selected conversation. `reply` is the selected-conversation
  one-shot path and falls back to the persisted target after expiry.
- Caption/media prompt forwarding is not a supported path in the current architecture;
  attachments remain on their separate local attachment flow and were not changed.
- Mini App remains frozen and unmodified.
- The outbox still does not provide exactly-once Telegram delivery; the existing
  at-most-once/unknown semantics were preserved.
- A local tombstone in the ambiguous `deleting` state does not clear the target; only
  confirmed remote deletion or an outbox-confirmed missing target does.

## 15. Final Git state

- Branch: `main` (unchanged)
- HEAD: `0774c9cff923a2ed02da36a1111a283a61600ea5` (unchanged)
- Tree: `faa7a3f03aa361698c6854281c162358bf38b84f` (unchanged)
- Staged: **0**
- Modified: **28** (baseline 24 plus four test files updated by this task)
- Untracked: **35** before this report; **36** after adding this report
- This task's existing-file edits:
  `bot/db.py`, `bot/handlers.py`, `bot/outbox.py`,
  `tests/test_4b.py`, `tests/test_handlers.py`, `tests/test_messages.py`,
  `tests/test_wp07_nav06_open_conversation_atomic.py`
- New test: `tests/test_persistent_ready_sticky_routing.py`
- New report: this file
- All other modified/untracked files, including pre-existing work and Mini App files,
  were preserved; no Mini App file was touched.

## 16. Authorization and publication state

**No commit, push, PR, merge, deployment, or Autopush activation occurred.**
No staging was performed. No destructive Git operation was used. No production API call
or secret exposure occurred.
