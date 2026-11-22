# OHB2 — DEF-011 F-03 — Independent Review Report

**Task ID:** `OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-AND-CLOSURE`
**Review date:** 2026-11-21
**Subject:** `docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md` and the current routing/outbox implementation at `main`

> This file is a new review artifact. The older
> `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` was **not overwritten**; it
> describes an earlier snapshot (`30dfa0d`) and is stale for the current snapshot (`9d1e13d`).

---

## A. Review identity and independence

| Item | Value |
|---|---|
| Reviewer conversation | `de819568-6590-47d2-906a-e4b94a4ddc7c` |
| Reviewer workspace | `/workspace/project/OpenHandBot` for inspection; tests run from an independent clone at `/tmp/ohb2-independent-clone` |
| Implementation conversation recorded in the prior review | `6715bb35bff4420d9802ed649c3cc2ea` — **not hosted in this environment** |
| Repository access | `git clone https://github.com/TM-AEM/OpenHandBot.git` into `/tmp/ohb2-independent-clone`; `HEAD = 9d1e13d72ed7dca8ffd2c6eebff1c6a36400ab17`; tree `cd8884be580cb3e84b9602d8d356201f9579b748` |
| Frozen inspection snapshot | `git archive HEAD` into `/tmp/ohb2-def011-f03-review`; 537 files; manifest SHA-256 `710c281b64d8a5392793e6b29d40541efb747b5e983e1161e421da3e55abbe42` |
| Base HEAD / tree | `9d1e13d72ed7dca8ffd2c6eebff1c6a36400ab17` / `cd8884be580cb3e84b9602d8d356201f9579b748` |
| Snapshot integrity | Independent clone and frozen snapshot both resolve to the same commit/tree; clone `git status` clean |
| Independence verdict | **INDEPENDENCE_ESTABLISHED** |

The current reviewer conversation is not the implementation conversation: the only hosted conversation is
`de819568…`, whose initial message is the independent-review task, while the implementation conversation
`6715bb35…` is absent. The repository used for tests was obtained by a fresh clone from GitHub, not by
continuing the implementation agent's workspace. The older independent review in `de819568…` is the
same reviewer identity, not the implementation identity; this review re-fetched the live repository at
`9d1e13d` and did not trust the earlier report's test output.

**Caveat:** the current task is a re-review within the prior independent reviewer conversation rather
than a brand-new reviewer identity. It is independent of the implementation conversation, but it is not
a new reviewer context relative to the earlier F-03 review.

---

## B. Scope and baseline

### B.1 Implementation report reviewed

- `docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md`
- `docs/reviews/OHB2-WP07-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md` (prior `INDEPENDENCE_NOT_ESTABLISHED` review)
- `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` (earlier independent report at `30dfa0d`)
- `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md`
- `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md`
- `tests/test_doc_code_parity.py`
- `bot/attachments.py`

### B.2 Routing/outbox files reviewed

- `bot/db.py`: `AWAITING_TTL`, `set_awaiting`, `awaiting_state`, `take_awaiting`, `set_awaiting_and_record_outcome`, `clear_awaiting_and_record_outcome`, `consume_one_shot_awaiting`, `add_or_group_outbox`, `add_creation_job`, settings helpers, deletion helpers.
- `bot/handlers.py`: `start`, `chat`, `_open_conversation_view`, `reply_prompt`, `handle_text`, `cancel_route`, `cancel_route_button`, `_send_prompt`, attachment and navigation paths.
- `bot/outbox.py`: `_post_claimed`, `_is_selected_target`, `_clear_unavailable_selection`, `deliver_outbox`, completion/cleanup.
- `bot/openhands_client.py`: `get_conversations`, `resume_sandbox`, `send_message`.
- Tests: `tests/test_persistent_ready_sticky_routing.py`, `tests/test_chat_command_last_accessed.py`, `tests/test_4b.py`, `tests/test_u04_concurrency.py`, `tests/test_one_shot_awaiting_atomicity.py`, `tests/test_duplicate_update_dispatch.py`, `tests/test_prompt_cleanup.py`, outbox/grouping/deletion/attachment routing tests, and `tests/test_doc_code_parity.py`.

### B.3 Git status

Initial status at review start: branch `main`, HEAD `9d1e13d…`, `origin/main` identical, working tree clean
(`git status --porcelain` empty). Final repository status before adding this report: clean. The only
repository write made by this review is this report file. No implementation file was modified.

No required input was missing. The prior implementation conversation's directory was absent, but the
published commit and all required files were available.

---

## C. Technical review

### C.1 Root cause of the 10-minute limitation

The old route branch treated `route` as a one-shot state and called `awaiting_is_expired`; `take_awaiting`
also expired `route`. There was no persistent selected-conversation fallback, and `/start` cleared the
route state. This explains why inactivity required `/start` or reopening a conversation.

### C.2 Route expiration removal

- `bot/db.py:289-292` keeps `AWAITING_TTL = timedelta(minutes=10)`.
- `bot/db.py:3165-3170` documents that `route` is persistent and `awaiting_at` is compatibility/diagnostic only.
- `bot/db.py:3620-3668::take_awaiting` special-cases `route`: it renews `awaiting_at` and returns the
  route instead of expiring it.
- `bot/handlers.py:3054-3105::handle_text` reads state without consuming it; the `route` branch does
  not call `awaiting_is_expired`.
- The one-shot branches remain time-limited: `newchat`/`reposearch` at `bot/handlers.py:3058-3071`,
  `reply` at `3072-3085`, and atomic consumption in `db.add_or_group_outbox`/`add_creation_job`.
- A repository-wide search found no other expiry of `route`; `AWAITING_TTL` is the only routing TTL.
  The unrelated safety timeouts remain: attachment batch TTL 15 min, sandbox wait 120 s, outbox cleanup
  delays, inbox claim lease, and group window.

### C.3 Persistent selected-conversation routing

`last_accessed_conversation:<telegram_id>` is stored in the existing `settings` table
(`bot/db.py:4866-4921`). `set_awaiting_and_record_outcome` writes the selected conversation, route state,
update outcome, and clears `routing_paused:<telegram_id>` in one `BEGIN IMMEDIATE` transaction
(`bot/db.py:3288-3328`). `handle_text` resolves `target = last_target or pending` for a live route
(`bot/handlers.py:3086-3105`), so the persisted target is authoritative over a stale route row. The
`route` state is retained for compatibility, but the setting is the routing reference.

### C.4 Restart persistence

Both `user_state` and `settings` are SQLite tables; `last_accessed_conversation` survives close/reopen.
`tests/test_persistent_ready_sticky_routing.py::test_route_survives_database_reopen_and_process_restart`
reopens the database and drives `handle_text`; it passed from the independent clone. No in-memory route
cache was found in the routing path.

### C.5 Conversation switching

Opening A/B through `_open_conversation_view` updates `last_accessed` and route only after the view is
displayed (`bot/handlers.py:1283-1291`). Opening B therefore changes the default; the tests
`test_open_b_changes_default_target_for_later_messages` and
`test_opening_another_conversation_updates_last_accessed` passed. Sending a message does not write
`last_accessed`; `test_sending_does_not_silently_change_selected_target` passed.

### C.6 `/start`, `/chat`, and `/cancel`

- `/start` still shows the menu, clears transient awaiting state, records an explicit outcome, and
  resumes paused routing, but preserves the last-accessed setting (`bot/handlers.py:952-969`).
  `test_start_is_not_required_after_inactivity` passed.
- `/chat` reads only the persisted setting and calls `_open_conversation_view`; it creates no outbox
  or creation job (`bot/handlers.py:1301-1314`). `test_chat_opens_last_accessed_without_prompt_or_creation`
  passed.
- `/cancel` clears awaiting and records an outcome, then sets `routing_paused:<telegram_id>`; the last
  target is retained for `/chat` (`bot/handlers.py:3262-3289`). The normal test
  `test_cancel_pauses_default_routing_until_chat_reopens` passed.
- **Transaction gap:** the clear/outcome and the pause are two separate commits. This is a finding
  (F-06).

### C.7 Message-path coverage

The actual handler registrations were checked in `bot/app.py:123-199`:

- ordinary text: `filters.TEXT & ~filters.COMMAND` → `handle_text`;
- commands: `CommandHandler` registrations, so they are not forwarded as prompts;
- route-based and reply-based paths: `handle_text` branches at `bot/handlers.py:3086-3115`;
- rapid messages: `db.add_or_group_outbox` merges within `GROUP_WINDOW`; the focused tests passed;
- after `/cancel`: `_reply_no_routing_target` when paused; passed;
- after opening another conversation: route/last target update; passed in the non-concurrent case.

**Caption/media:** `bot/app.py:181-193` registers text, supported documents, and unsupported media
separately. `handle_unsupported_attachment` does not forward captions (`bot/handlers.py:2767-2796`);
`tests/test_attachment_intent_a3.py` explicitly covers a caption without `text`. Caption/media prompt
forwarding does not exist in this architecture. This is an architectural limitation, not an F-03
regression.

### C.8 Missing, deleted, unavailable, and transient targets

- Local confirmed deletion: `_send_prompt` checks `db.is_deleted_with_retry`; it clears the matching
  `last_accessed`/awaiting only when `remote_deletion_state == REMOTE_CONFIRMED`
  (`bot/handlers.py:3314-3327`).
- `deleting`/`uncertain`: no clear; the existing target is preserved. `test_transient_upstream_errors_do_not_clear_selected_target`
  covers 503/429/None on the open path; outbox tests cover 503.
- 404/410 after the POST: outbox marks `failed`, clears the matching selection, sends the unavailable
  notice, and does not fall back (`bot/outbox.py:659-667`).
- 429/5xx/timeout before the POST: outbox returns the item to `pending` and preserves the target
  (`bot/outbox.py:610-632`); after the POST it becomes `unknown` and is not retried automatically.
- Empty 200 results and pre-POST 404 handling are findings F-04/F-05 below.
- `/chat` confirmed-missing handling is finding F-01 below.

### C.9 User isolation

`last_accessed_conversation:` and `routing_paused:` keys include `int(telegram_id)`
(`bot/db.py:4872-4878`). `test_last_accessed_is_isolated_per_telegram_user` and
`test_chat_owner_isolation` passed. The routing path reads the effective user ID; no cross-user key was
found.

### C.10 Outbox and delivery compatibility

- Ownership: one outbox worker; `deliver_outbox` claims the requested row by ID and calls the existing
  `_post_claimed` (`bot/outbox.py:356-370`). No new queue/worker/scheduler was introduced.
- Grouping: `add_or_group_outbox` retains `GROUP_WINDOW`, destination, message-ID tracking, and
  `client_ref` idempotency (`bot/db.py:3708-3875`).
- Retry/idempotency: `MAX_OUTBOX_ATTEMPTS`, `claim_outbox_by_id`, CAS status transitions, and
  `complete_outbox_sent` remain in place.
- Cleanup: `schedule_delivery_cleanup` is called only after successful completion and confirmation
  (`bot/outbox.py:290-314`); tests `test_confirmation_is_not_sent_for_failed_delivery` and
  `test_send_prompt_does_not_schedule_cleanup_before_delivery` passed.
- **But:** `_send_prompt` sends the user-facing `وصل ✅` immediately after inserting the `pending` row,
  before `client.send_message` (`bot/handlers.py:3335-3355`). This is finding F-02.
- Shutdown: cleanup tasks are cancelled through `cancel_cleanup_tasks` (`bot/app.py:347-349`); existing
  behavior preserved.

### C.11 Database/migration safety

No new table or migration is needed: `settings` already exists with `key TEXT PRIMARY KEY`, and
`user_state` already has the awaiting columns. `set_awaiting_and_record_outcome`,
`clear_awaiting_and_record_outcome`, and `complete_outbox_sent` use `BEGIN IMMEDIATE`/rollback. The
per-user keys prevent normal cross-user leakage. The transaction gap in `/cancel` is F-06; the
read-then-send race is F-07. A DB read failure in target resolution propagates rather than producing a
different target; this is fail-closed, though it may leave the update failed and retryable.

### C.12 Mini App and architecture

The reviewed routing diff does not touch `bot/web/` or the Mini App. The architecture remains one bot +
ASGI process, one SQLite owner, existing outbox workers, no backup feature, no exactly-once Telegram
claim, and no new service. The current commit does contain unrelated pre-existing sync changes; those
are not attributed to F-03.

---

## D. Test evidence

All commands below were executed by this reviewer from `/tmp/ohb2-independent-clone` (independent clone,
HEAD/tree `9d1e13d…`/`cd888…`) or the frozen archive with the same tree. Exit codes are actual.

| Check | Command | Result | Exit |
|---|---|---|---|
| Focused persistent routing | `python -m pytest -q tests/test_persistent_ready_sticky_routing.py` | **28 passed** | 0 |
| Relevant routing/outbox/attachment suite | 26-file focused command listed in §B.2 | **832 passed** | 0 |
| F-03 parity | `python -m pytest -q tests/test_doc_code_parity.py` | **14 passed** | 0 |
| Full Python suite | `python -m pytest -q` | **3688 passed, 0 failed**, 74 warnings | 0 |
| Frontend Node | `node --test tests/frontend/*.test.js` | **280 passed, 0 failed** | 0 |
| pyflakes | `python -m pyflakes bot tests` | no output | 0 |
| Bandit | `python -m bandit -r bot -lll -s B613` | **High: 0**, Medium: 14, Low: 3 | 0 |
| compileall | `python -m compileall -q bot` | no output | 0 |
| pip-audit | `python -m pip_audit -r requirements-dev.txt` | `No known vulnerabilities found` | 0 |
| git diff check | `git diff --check` | no output | 0 |

### D.1 F-03 mutation checks

Run in a scratch copy (`/tmp/ohb2-f03-mutations`), never in the checkout. Control: 14 passed.

| Mutation | Result |
|---|---|
| M1: rewrite historical `0 to_thread` claim | `test_t2_historical_stale_claims_are_preserved_verbatim` failed; 1 failed, 13 passed |
| M2: delete proposal correction notice | 4 failed, 10 passed (T-3 ×2, T-4, T-1) |
| M3: flip `DEF-011-A` to `IMPLEMENTED` | `test_t1_correction_notice_matches_actual_implementation_state` failed; 1 failed, 13 passed |
| M4: tamper §2.2 by one token | `test_t2_protected_sections_are_byte_for_byte_unchanged` failed; 1 failed, 13 passed |
| M5: change batch notice date to 2026-11-20 | `test_t4_both_notices_share_date_status_and_scope_language` failed; 1 failed, 13 passed |
| Control restored | 14 passed |

### D.2 Adversarial experiments

Run from the independent clone with fake Telegram/OpenHands objects; no network.

| Scenario | Observed result |
|---|---|
| 1. `/chat` last target confirmed missing, then ordinary text | `last_accessed=None`, `awaiting=("A","route")`, outbox `A/pending`, immediate reply `وصل ✅ ← «A»` |
| 2. Selected target exists, sandbox resume raises 404 | outbox `failed`; `last_accessed`/awaiting cleared; no POST; unavailable notice |
| 3. Selected target returns empty 200 list | outbox `failed`; target/awaiting cleared; no POST; unavailable notice |
| 4. `/cancel` clear succeeds, pause write raises | exception; `last_accessed=A`, awaiting none, `routing_paused=False` |
| 5. B opened while A prompt preparation is blocked | final `last_accessed=B`, awaiting B; outbox row still `A` |
| Process restart | covered by focused test; target survives reopen |
| Two users | covered by focused isolation test |
| Stale reply + valid target | existing test routes to persisted target; expired reply row is not consumed in that branch |
| 429/5xx/timeout | existing tests preserve target and retry/unknown as expected |

### D.3 Not run / not reproducible

- **Python 3.11 full suite:** `NOT_RUN`; this environment has Python 3.13.18. The full suite was run on
  3.13.
- **Real Telegram/OpenHands network:** `NOT_RUN`; all tests use deterministic fakes.
- **Exact seven-test increase from the implementation report:** `NOT_REPRODUCIBLE` at current HEAD.
  The current parity file has 14 tests (6 pre-existing + 8 F-03/T-5 tests), while the report describes
  13 tests and +7. T-5 was added after the earlier report. The current full suite is 3688; the old
  baseline is not present in this snapshot.
- **Mini App UI:** `NOT_RUN`; no Mini App code was changed by the reviewed routing work.
- **Real upstream deletion semantics:** `NOT_RUN`; only fake 404/410/empty/429/5xx responses were used.

---

## E. Findings

### E.1 Summary

| ID | Severity | Class | Finding |
|---|---|---|---|
| F-01 | **HIGH** | Confirmed defect / regression from persistent routing | `/chat` clears only `last_accessed`; the matching `awaiting` route survives, so the next text is queued to the unavailable target and receives an immediate success-looking ack. |
| F-02 | **HIGH** | Confirmed pre-existing defect | `_send_prompt` reports `وصل ✅` after durable queue insertion, before outbox delivery; pending/failed/unknown outcomes can therefore produce a success-looking confirmation. |
| F-03 | **HIGH** | Confirmed documentation defect | F-03 notices and the implementation report still say `DEF-011-C` is NOT IMPLEMENTED, while current `bot/handlers.py` contains the `DEF-011-C` local-only acceptance copy and tests. |
| F-04 | **MEDIUM** | Confirmed defect | A 404 from `resume_sandbox` (sandbox missing) is treated as confirmed conversation deletion; the selected target is cleared even though the conversation may still exist. |
| F-05 | **MEDIUM** | Potential/ambiguous classification | An empty 200 `get_conversations` result for the selected target is treated as confirmed missing and clears the target; an empty/partial response is not necessarily deletion. |
| F-06 | **MEDIUM** | Confirmed transaction gap | `/cancel` clears awaiting/outcome and sets pause in separate commits; a crash/DB failure between them leaves routing active. |
| F-07 | **MEDIUM** | Potential race | `handle_text` reads the target before the outbox insertion; a concurrent selection of B can complete while an A prompt is in flight, producing an outbox row for A after B became the selected target. |
| F-08 | **LOW** | Potential state combination / missing cleanup | An expired `reply` falls back to the last target without checking `routing_paused` and without consuming/clearing the stale reply row. |
| F-09 | **MEDIUM** | Confirmed documentation/evidence defect | The F-03 implementation report says five `to_thread` occurrences and T-4 says “five”; current code and notices say six. |
| F-10 | **LOW** | Scope drift / current-snapshot note | Current proposal has a later 2026-11-22 NAV post-decision update outside the F-03 notice; at current HEAD, “remove only the F-03 notice” no longer reconstructs the diagnosis original (it does at `30dfa0d`). |
| F-11 | **INFO** | Resolved follow-up | `BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` now has a dated correction notice and T-5; the historical row remains but is explicitly superseded. |
| F-12 | **INFO** | Stale prior review artifact | The earlier `GENUINELY` report is a valid review of `30dfa0d` but is not a closure report for current HEAD; it records five `to_thread` and C not implemented, both stale now. |

### E.2 Finding details

#### F-01 — `/chat` leaves the route alive after a confirmed-missing target

- **Severity:** HIGH
- **File/function:** `bot/handlers.py::_open_conversation_view` (lines 1225-1236), `::handle_text` (3054-3105), `::_send_prompt` (3335-3355)
- **Reproduction:** Open A; make A missing; run `/chat`; then send ordinary text. Observed `last_accessed=None`, `awaiting=("A","route")`, outbox `A/pending`, reply `وصل ✅ ← «A»`.
- **Impact:** the selected target is not fully cleared after confirmed unavailability. The next prompt is queued to the unavailable chat; the user first sees a success-looking ack and only later gets an outbox failure. No silent fallback to another conversation occurs, but the no-target path is bypassed.
- **Evidence:** isolated adversarial experiment from the independent clone; `tests/test_chat_command_last_accessed.py:73-84` currently asserts that the route remains `("A","route")` after `/chat` clears `last_accessed`. That test locks in the behavior.
- **Regression:** yes for the persistent-routing change: route no longer expires and `handle_text` uses `last_target or pending`; the stale route now survives indefinitely.
- **Remediation:** on terminal rejection, atomically clear both the matching `last_accessed` and matching `awaiting` state (and any relevant pause), or make `handle_text` refuse when the only remaining route was invalidated. Add a test that exercises the actual next-message routing decision, not only the setting.

#### F-02 — “وصل ✅” is sent before delivery

- **Severity:** HIGH
- **File/function:** `bot/handlers.py::_send_prompt` (3335-3355); `bot/outbox.py::_post_claimed` (655-716)
- **Reproduction:** With a live route, send text. `add_or_group_outbox` returns a `pending` row; `_send_prompt` immediately replies `وصل ✅`; no `client.send_message` has run yet.
- **Impact:** pending, failed, and unknown delivery outcomes can be preceded by a user-facing success-looking acknowledgement. The later `اتبعت ✅` notice is the actual delivery confirmation, but the first message is misleading and violates the requirement that a queued/pending/ambiguous message must not be reported as successfully delivered.
- **Evidence:** code inspection; `tests/test_persistent_ready_sticky_routing.py:74` expects `وصل ✅` immediately after the handler; `tests/test_prompt_cleanup.py` only proves cleanup is not scheduled before delivery. The implementation report says confirmation wording was unchanged, which is true but does not make the wording safe.
- **Regression:** pre-existing; not introduced by this routing diff.
- **Remediation:** change the immediate ack to an explicit “saved/queued” wording, or delay the success-looking confirmation until `sent` and keep the existing `اتبعت ✅` notice as the delivery confirmation.

#### F-03 — F-03 notices say `DEF-011-C` is not implemented, but the current code implements its local-only copy

- **Severity:** HIGH
- **Files:** `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md:37-39`, `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md:217-219`, `docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md:78-80`
- **Code evidence:** `bot/handlers.py:2349-2353` contains `ATTACHMENT_ACCEPTED_TEXT` with the explicit `OHB2-WP01/DEF-011-C` marker and local-only wording (“حفظه محليًا بشكل مؤقت”); `tests/test_wp01_attachment_lifecycle.py:440-444` asserts the accepted and duplicate messages are distinct and truthful. `git diff 30dfa0d..9d1e13d` shows the copy was added after the F-03 review snapshot.
- **Impact:** the F-03 notices’ “C NOT IMPLEMENTED” claim is not accurate for current HEAD. The status table and closure reasoning are therefore wrong: `DEF-011` may still be open because of A, but not for the stated C reason.
- **Regression:** current documentation drift caused by later WP-01 work not being reconciled into the F-03 notices; the earlier report was accurate at `30dfa0d`.
- **Remediation:** update both notices and the implementation report to state C’s actual current status (implemented or precisely partial), or identify the remaining C gap. Add a parity assertion that ties the C row to the actual `ATTACHMENT_ACCEPTED_TEXT`/test state.

#### F-04 — Sandbox-resume 404 is treated as conversation deletion

- **Severity:** MEDIUM
- **File/function:** `bot/outbox.py::_post_claimed` (543-545, 598-609); `bot/openhands_client.py::resume_sandbox` (373-374)
- **Reproduction:** Selected target A has `sandbox_status=STOPPED` and a sandbox id; `get_conversations` returns A; `resume_sandbox` raises `ApiError(404)`. Observed: outbox `failed`, `last_accessed`/awaiting cleared, unavailable notice, no POST.
- **Impact:** a missing/expired sandbox is not proof that the conversation is deleted. The selected target can be lost and the user told the chat is gone while the conversation may still be valid.
- **Evidence:** isolated adversarial experiment; code path catches every `ApiError` with status 404/410 in the pre-POST `try`, not only conversation metadata calls.
- **Regression:** pre-existing classification, made user-visible by persistent selection.
- **Remediation:** classify 404/410 by source operation; only conversation metadata/`send-message` 404/410 can confirm unavailable. A sandbox-resume 404 should be transient/unavailable-sandbox, preserving the selected target.

#### F-05 — Empty 200 result is treated as confirmed missing

- **Severity:** MEDIUM
- **File/function:** `bot/outbox.py::_post_claimed` (527-539); `bot/openhands_client.py::get_conversations` (90-103)
- **Reproduction:** Selected target A; fake `get_conversations` returns `[]` with HTTP 200. Observed: outbox `failed`, target/awaiting cleared, unavailable notice, no POST.
- **Impact:** an empty list can be an incomplete/eventually-consistent response; it is weaker evidence than 404/410 or a tombstone. Clearing the target on empty can lose a valid selection.
- **Evidence:** `tests/test_persistent_ready_sticky_routing.py::test_outbox_confirmed_missing_target_fails_without_fallback` expects this behavior for the `empty` mode; the client does not distinguish a complete empty list from a partial result.
- **Regression:** current classification, not introduced by routing; the test enshrines it.
- **Remediation:** treat empty as ambiguous and retry/preserve unless a tombstone or explicit 404/410 confirms deletion; adjust the test to separate “empty” from “confirmed missing”.

#### F-06 — `/cancel` clear/outcome and pause are separate transactions

- **Severity:** MEDIUM
- **File/function:** `bot/handlers.py::cancel_route` (3262-3273), `::cancel_route_button` (3276-3289); `bot/db.py::clear_awaiting_and_record_outcome` (3256-3286), `pause_routing` (4915-4917)
- **Reproduction:** Monkeypatch `db.pause_routing` to raise after `clear_awaiting_and_record_outcome` succeeds. Observed: exception; `last_accessed=A`, awaiting none, `routing_paused=False`.
- **Impact:** if the process/database fails between the two commits, `/cancel` clears the route but does not pause default routing; the next text routes to the retained last target despite the user’s cancellation.
- **Evidence:** isolated adversarial experiment; code inspection shows two independent commits.
- **Regression:** new pause semantics introduced with the persistent-routing change.
- **Remediation:** add a single DB method that clears awaiting, records the outcome, and sets pause in one `BEGIN IMMEDIATE` transaction; test rollback at each write.

#### F-07 — Read-then-send race between selection and prompt submission

- **Severity:** MEDIUM (potential race)
- **File/function:** `bot/handlers.py::handle_text` (3054-3055 read; 3102-3105 send); `::_open_conversation_view` (1286-1291 write)
- **Reproduction:** Block `_send_prompt` for a message that resolved A; open B to completion; release the message. Observed final `last_accessed=B`, awaiting B, but outbox row A.
- **Impact:** a message prepared before a concurrent selection can be delivered to the previous conversation after the user has selected B. This is a linearizability/order issue, not a stale in-memory route: the read was valid when it happened.
- **Evidence:** deterministic barrier experiment in the independent clone; no per-user routing lock or expected-target CAS exists between target read and outbox insertion.
- **Regression:** new persistent routing makes the old target sticky; the race is not covered by the focused tests.
- **Remediation:** serialize per-user selection and prompt insertion (single-user lock) or pass the expected target and CAS it in `add_or_group_outbox`; alternatively document the chosen linearization and add a race test.

#### F-08 — Expired reply fallback ignores pause and leaves stale state

- **Severity:** LOW
- **File/function:** `bot/handlers.py::handle_text` (3072-3085)
- **Reproduction:** Set a valid last target A, an expired `reply` awaiting state, and `routing_paused=1`; send text. The expired-reply branch calls `_send_prompt` without checking pause and without consuming the reply row.
- **Impact:** in this abnormal/raced state, a message can route despite a pause, and the stale `reply` row persists. Normal `/cancel` clears awaiting, so this requires a race/corrupt state; not a normal user path.
- **Evidence:** code inspection; no test covers expired reply + pause.
- **Regression:** current state-machine interaction; low.
- **Remediation:** check pause in the expired-reply branch and atomically clear/consume the expired reply state; add a discriminating test.

#### F-09 — F-03 implementation report is stale on `to_thread` count

- **Severity:** MEDIUM
- **Files:** `docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md:78, 112, 264`; current `bot/attachments.py` has 6 `to_thread` occurrences; proposal/batch notices say six; `tests/test_doc_code_parity.py:248-253, 346-348` assert six.
- **Impact:** the implementation report’s evidence and T-4 description (“five”) are false for current HEAD. The report cannot be used as closure evidence without correction.
- **Evidence:** `grep -c to_thread bot/attachments.py` = 6; current parity test passed with six; report says 5.
- **Regression:** stale artifact after later code change, not a runtime defect.
- **Remediation:** update the implementation report (or mark it historical) and add a generated count assertion; do not change code for this.

#### F-10 — Current proposal contains a later NAV post-decision update outside F-03

- **Severity:** LOW
- **File:** `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md:16-18`
- **Evidence:** current proposal includes a 2026-11-22 NAV-01..06 post-decision update added after the F-03 notice. At `30dfa0d`/`0774c9c`, removing the F-03 notice plus its trailing separator reproduces the diagnosis original (`82fbf986…`); at current HEAD it does not because the later update remains.
- **Impact:** current HEAD is not a pure F-03 remediation snapshot. This is scope drift, not a defect in the F-03 notice itself.
- **Remediation:** handle in a separate reconciliation task; preserve the historical update and document the current-vs-F-03 commit boundary.

#### F-11 — BATCH04 stale reference is resolved (INFO)

`docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md:303-314` now contains a dated
correction notice; the historical row at `:300` remains but is explicitly superseded. `T-5` passes.
It is no longer an unqualified stale reference. No modification is recommended.

#### F-12 — Earlier `GENUINELY` report is stale for current HEAD (INFO)

The earlier report reviewed `30dfa0d` and recorded five `to_thread` occurrences and C not implemented.
Current HEAD has six and a C copy. The earlier report remains valid for its snapshot; it is not a
closure report for `9d1e13d`. This review does not overwrite it.

---

## F. Final verdict

# `FAIL`

Independence is established and the snapshot is exact, but material findings remain:

- **F-01** confirms `/chat` can leave a stale route and queue a prompt to a confirmed-missing target.
- **F-02** confirms a success-looking acknowledgement before delivery.
- **F-03** confirms the F-03 notices’ `DEF-011-C` status is factually wrong at current HEAD.
- F-04/F-05 show over-broad target clearing; F-06 shows a cancel transaction gap; F-07 is a potential
  selection/submission race.

The existing tests all pass, but they do not cover these behaviors; the failure is therefore not
detectable from the green suite alone. This is a **FAIL** for the current implementation/closure
snapshot, not a claim that every subsystem is broken.

---

## G. Closure recommendation

**DEF-011 F-03 is still open pending remediation.**

- It is **not** eligible for closure.
- It is **not** eligible for closure with notes while F-03’s own C status is factually wrong.
- `DEF-011` as a whole remains open: `DEF-011-A` (reservation ledger) is still absent; `DEF-011-C`
  appears implemented in current code but the F-03 notices have not been reconciled; `D6` remains
  deferred.
- **Owner acceptance is not granted by this report.** A passing independent review is not owner
  acceptance.

No unrelated finding or work package is closed by this report.

---

## Review safety confirmation

- No implementation source, test, historical document, schema, dependency, or Mini App file was
  modified.
- The only repository write is this report file.
- No commit, push, PR, merge, deployment, release, or Autopush activation occurred.
- Tests and mutations ran from `/tmp/ohb2-independent-clone`, `/tmp/ohb2-def011-f03-review`, and
  `/tmp/ohb2-f03-mutations`; the live checkout remained clean except for this report.
