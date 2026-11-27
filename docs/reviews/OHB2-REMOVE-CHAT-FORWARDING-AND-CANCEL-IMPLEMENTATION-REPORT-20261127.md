# OHB2-REMOVE-CHAT-FORWARDING-AND-CANCEL — Baseline and Implementation Report

**Task ID:** `OHB2-REMOVE-CHAT-FORWARDING-AND-CANCEL`
**Date:** 2026-11-27
**Status:** COMPLETE — local verification green; no commit/push/PR/deploy
**Scope:** remove the chat-forwarding UX, forwarding-specific automatic routing,
`/cancel`, the `إلغاء التوجيه` button, and forwarding-specific callbacks/state; preserve
manual-copy and ordinary messaging.

## 1. Baseline Git state

Recorded before any edit:

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `main` |
| HEAD | `9a34a3a0006b1367f0ff089a083f1eaf1b1251c0` |
| Tree | `0409516d81ec5d360b8c3d19c80730b1f78865f2` |
| `git status --short` | empty |
| Staged files | 0 |
| Modified tracked files | 0 |
| Untracked status entries | 0 |
| Untracked files | 0 |
| Ignored | `.openhands/`, `.pytest_cache/`, `.venv/`, `__pycache__/`, `dist/`, `node_modules/` |

Baseline focused tests (real SQLite/handlers, deterministic fakes):

```text
python -m pytest -q \
  tests/test_persistent_ready_sticky_routing.py \
  tests/test_new01_cancel_prompt_atomicity.py \
  tests/test_def011_review_remediation.py \
  tests/test_4b.py tests/test_keyboards.py tests/test_messages.py \
  tests/test_features_hidden.py tests/test_chat_command_last_accessed.py \
  tests/test_wp07_atomic_state_outcome.py \
  tests/test_wp07_f1_notification_failure.py \
  tests/test_manual_polling_handler_outcome_coverage.py \
  tests/test_wp01_attachment_lifecycle.py \
  tests/test_wp01_stage1_cancellation.py \
  tests/test_new03_unavailable_selection_atomicity.py
=> 335 passed, exit 0
```

Baseline static checks:

```text
python -m pyflakes bot/ automation/ tools/ main.py tests/ => exit 0
git diff --check => exit 0
```

The immediately preceding full-suite run on the identical tree was **4413 passed,
0 failed** (recorded in the prior independent review); no code changed between that run
and this baseline.

## 2. Previous implementation and review findings discovered

### 2.1 Previous implementation

The forwarding behavior is the sticky-routing work documented in:

- `docs/reviews/OHB2-PERSISTENT-READY-STATE-AND-STICKY-CONVERSATION-ROUTING-IMPLEMENTATION-REPORT.md`

Current behavior in `bot/handlers.py` / `bot/db.py`:

- Opening/selecting a conversation writes `last_accessed_conversation:<telegram_id>`
  and an `awaiting` state of `(conversation_id, "route")`.
- The open-conversation view appends:
  `"✉️ رسايلك الجاية هتتبعت للشات ده لحد ما تفتح/تختار شات تاني. للإلغاء: زر إلغاء التوجيه أو /cancel."`
- `handle_text` treats `kind == "route"` as a permanent route and sends ordinary text
  to `last_target or pending`.
- `/cancel` and callback `cancelroute` call
  `clear_awaiting_and_record_outcome(..., pause_routing=True)`; a
  `routing_paused:<telegram_id>` setting blocks later default routing.
- `bot/keyboards.py` adds `CANCEL_ROUTE = "إلغاء التوجيه"` with callback
  `cancelroute`.
- `bot/app.py` registers `/cancel` and `^cancelroute$`.
- The Mini App itself has no forwarding-specific control; the forwarding UX is
  Telegram-only.

### 2.2 Exact previous review findings

The closest previous independent review is
`docs/reviews/OHB2-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md`. Its exact findings relevant
to this task are:

| ID | Severity | Exact finding | Current code status |
|---|---|---|---|
| F-01 | HIGH | `/chat` cleared only `last_accessed`; the matching `awaiting` route survived, so the next text was queued to the unavailable target and received an immediate success-looking ack. | Fix present in `_open_conversation_view` terminal-rejection path: `clear_last_accessed_conversation_id` + `clear_awaiting_conversation_id` in one transaction. Forwarding route is being removed entirely. |
| F-02 | HIGH | `_send_prompt` reported `وصل ✅` after durable queue insertion, before outbox delivery; pending/failed/unknown could produce a success-looking confirmation. | Fix present: ack says `تم حفظ طلبك، ولسه هيتبعت`; actual delivery remains the outbox notice. Must preserve. |
| F-03 | HIGH | Repository's exact F-03 is a **documentation defect**: F-03 notices said `DEF-011-C` was NOT IMPLEMENTED while current code had the local-only acceptance copy. | Not an architectural finding in the repository. No architectural conflict with forwarding removal was found. The task label says “architectural/decision constraint”; see §2.3. |
| F-06 | MEDIUM | `/cancel` cleared awaiting/outcome and set pause in separate transactions; a crash between them left routing active. | Current code uses one `clear_awaiting_and_record_outcome(..., pause_routing=True)` transaction. `/cancel` is being removed, so this path is being eliminated. |
| F-07 | MEDIUM | `handle_text` read the target before outbox insertion; a concurrent selection of B could complete while an A prompt was in flight, producing an outbox row for A after B became selected. | Current code has an `expected_routing` CAS at the outbox acceptance boundary; must preserve for ordinary `last_accessed` routing. |

Exact evidence locations:

- `docs/reviews/OHB2-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md:284-351`
- `docs/reviews/OHB2-DEF011-REMAINING-SCOPE-AND-READINESS-AUDIT-REPORT-20261124.md:202-207`
- `bot/handlers.py`: `_open_conversation_view`, `handle_text`, `cancel_route`,
  `cancel_route_button`, `_send_prompt`
- `bot/db.py`: `clear_awaiting_and_record_outcome`,
  `set_awaiting_and_record_outcome`, `add_or_group_outbox`, routing-pause helpers
- `bot/keyboards.py`: `CANCEL_ROUTE`, `conversation_actions`
- `bot/app.py`: `BOT_COMMANDS`, `CommandHandler("cancel")`,
  `CallbackQueryHandler(..., pattern=r"^cancelroute$")`

### 2.3 F-03 discrepancy and architectural constraint

The task labels F-03 as “conflict with the applicable architectural/decision
constraint”. The repository's exact F-03 is the documentation stale-C finding above; no
other F-03 with that description exists in the repository reports. This implementation
does not invent a new architectural decision.

The applicable approved architecture remains:

- one bot process plus the existing ASGI Mini App process;
- one SQLite owner;
- no new worker, queue, scheduler, database, or background process;
- no change to watcher/outbox/OpenHands lifecycle/review behavior.

Removing forwarding UX/state does not conflict with those constraints. If a hidden
requirement treats F-03 as an architectural gate, this task records the discrepancy and
keeps the approved architecture unchanged rather than silently reinterpreting it.

## 3. Baseline behavior that must be preserved

- Manual copy: `📄 عرض للنسخ اليدوي` (`copy:<conversation_id>`) and the `.txt` file
  button remain.
- Ordinary text/prompt submission: `_send_prompt` → `add_or_group_outbox` → outbox
  worker; no exactly-once claim.
- Conversation opening/selection, `/chat`, `/start`, `/help`, `/app`,
  `/notifications`, `/attachments*`, `/outbox*`.
- Persistent last-accessed conversation for `/chat` and ordinary default prompt
  routing, as described in the prior approved routing report.
- Explicit `reply` selection, `newchat`, `reposearch`.
- Mini App prompt submission/conversation management; no Mini App forwarding control
  exists to remove.
- Deletion/archive/inbox/status behavior.
- Unavailable target behavior: explicit error, no automatic creation, no silent
  fallback/reroute.
- F-02 queued-ack wording and F-07 target CAS.
- F-01 cleanup of unavailable selected target.

## 4. Assumptions

1. The supplied task text was truncated at “The removal must not break:”. The scope was
   reconstructed from the explicit objective and the approved routing report. The
   conservative reading is: remove the explicit `route` forwarding state/UX/cancel,
   while preserving the approved persistent `last_accessed` ordinary default routing.
2. `last_accessed` is ordinary selection state, not the forwarding-specific `route`
   state. `/chat` and ordinary prompt routing continue to use it.
3. Legacy `route` rows and `routing_paused` rows must be inert: they must not auto-route
   ordinary text or block ordinary messaging after the feature is removed.
4. Manual-copy is out of scope for removal and must remain functional.
5. No new architecture, schema, worker, or dependency will be introduced.

## 5. Planned implementation

1. Remove the forwarding instruction from `_open_conversation_view`; stop creating
   `route` state; atomically persist `last_accessed` + update outcome.
2. Remove the `route` branch from `handle_text`; keep `reply`, `newchat`, `reposearch`,
   and the persistent `last_accessed` default path.
3. Remove `/cancel`, `cancelroute`, `CANCEL_ROUTE`, their handlers/registrations, and
   the routing-pause state/checks.
4. Remove forwarding-specific state writes/checks while retaining legacy-safe behavior:
   legacy `route`/pause rows are ignored by ordinary text.
5. Keep manual-copy buttons and behavior untouched.
6. Preserve F-01 cleanup, F-02 ack wording, and F-07 `expected_routing` CAS for ordinary
   `last_accessed` routing.
7. Update help/docs and tests that encoded the removed forwarding behavior.
8. Add focused regression tests for all required removal/preservation cases.
9. Run focused/full Python, frontend, static, doc parity, security, and diff checks.

## 6. Files to inspect/update

- `bot/handlers.py`
- `bot/db.py`
- `bot/keyboards.py`
- `bot/app.py`
- `tests/test_persistent_ready_sticky_routing.py`
- `tests/test_new01_cancel_prompt_atomicity.py`
- `tests/test_def011_review_remediation.py`
- `tests/test_4b.py`
- `tests/test_keyboards.py`
- `tests/test_messages.py`
- `tests/test_features_hidden.py`
- `tests/test_chat_command_last_accessed.py`
- `tests/test_wp07_*`, `tests/test_manual_polling_*`, `tests/test_wp01_*` only where
  they use `/cancel`/route as setup for a removed behavior
- `README.md` / `docs/OPERATIONS_RUNBOOK.md` if they advertise the removed feature
- new focused test module and this report

No file has been edited yet. This report will be updated with implementation,
verification, and final Git status.


## 7. Implementation result

- `/cancel` was removed from `BOT_COMMANDS`, `HELP_TEXT`, and `build_application`;
  `cancel_route`/`cancel_route_button` and the `^cancelroute$` callback were removed;
  the `إلغاء التوجيه` keyboard button and its callback were removed.
- `_open_conversation_view` no longer appends forwarding instructions and no longer
  writes a `route` row/title. It clears transient awaiting state and persists
  `last_accessed_conversation_id` with the update outcome in one transaction.
- `handle_text` no longer has a `route` branch or pause checks. Ordinary text uses only
  the persisted `last_accessed` target; legacy `route` rows and `routing_paused:*`
  settings are inert.
- `pause_routing`/`resume_routing`/`is_routing_paused` and the `pause_routing` flag in
  `clear_awaiting_and_record_outcome` were removed.
- Document upload and accompanying attachment text now use the persisted last-accessed
  target instead of `route`.
- Regression tests were updated and `tests/test_remove_chat_forwarding_and_cancel.py`
  was added for the removal boundaries.

## 8. Final verification

- Focused forwarding/attachment/handler suite: **279 passed**.
- Document/attachment suite: **146 passed**.
- Full Python: **4407 passed, 0 failed** (74 pre-existing warnings; 327.06s).
- Node frontend: **280 pass / 0 fail**.
- `pyflakes`: 0; Bandit High: 0; pip-audit: no known vulnerabilities;
  `git diff --check`: clean.
- Residual production/docs grep: no `/cancel`, `cancelroute`, `cancel_route`,
  `cancel_route_button`, `إلغاء التوجيه`, `routing_paused`, `pause_routing`,
  `resume_routing`, or `is_routing_paused`; only generic `cancelled` status strings
  remain.

## 9. Not verified

- Python 3.11 / GitHub Actions CI was not run locally (local Python 3.13.15).
- No live Telegram or OpenHands call was made.
- No commit, push, PR, merge, deploy, or independent review was performed.
