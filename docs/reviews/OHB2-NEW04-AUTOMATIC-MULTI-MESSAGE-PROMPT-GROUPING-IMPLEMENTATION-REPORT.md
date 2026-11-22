# OHB2-NEW04 — Automatic Multi-Message Prompt Grouping

**Task:** `OHB2-NEW04-AUTOMATIC-MULTI-MESSAGE-PROMPT-GROUPING`
**Status:** `IMPLEMENTED — SELF-VERIFIED`; **independent review NOT PERFORMED**; not release-ready.
**Date:** 2026-11-22
**Branch:** `agent/ohb2-new01-cancel-race`
**Baseline HEAD:** `efa1f02` (NEW-02 committed), working tree clean at start.
**Git state after work:** intended changes are committed on local `main` as part of the authorized exact synchronization; no PR/merge/deploy and Autopush remains inactive.

---

## 1. Task and status

Implemented the owner-approved 3-second inactivity debounce for Telegram prompt messages.
The existing outbox row is the durable batch; no new table, worker, process, scheduler, or
SQLite owner was introduced. NEW-01 cancellation atomicity and NEW-02 identity/cleanup safety
remain in place. NEW-03 was not touched and remains OPEN.

## 2. Baseline audit

- Branch `agent/ohb2-new01-cancel-race`, HEAD `efa1f02`.
- `git status --short --branch` was clean before changes.
- Previous committed work inspected: NEW-01 outbox acceptance/cancellation guard, NEW-02
  explicit-reply grouping and cleanup identity, outbox claim/recovery, prompt cleanup,
  routing/sticky selection, Mini App outbox path.
- Existing tests inspected: `test_grouping.py`, `test_new02_prompt_grouping_identity.py`,
  `test_new01_cancel_prompt_atomicity.py`, `test_duplicate_update_dispatch.py`,
  `test_prompt_cleanup.py`, `test_telegram_prompt_cleanup_durable.py`, outbox/recovery suites.
- Earlier report numbers were not assumed; all results below are from commands run in this
  workspace.

## 3. Files inspected and modified

Inspected: `bot/handlers.py`, `bot/db.py`, `bot/outbox.py`, `bot/web/services.py`, prompt
dispatch/worker/recovery paths, routing and cancellation paths, and the relevant tests.

Modified:

- `bot/db.py` — `GROUP_WINDOW=3s`; time-window grouping; reply identity retained;
  `telegram_message_parts` additive column/migration; ordering and duplicate identity safety.
- `bot/handlers.py` — documentation of the new grouping semantics only; the handler still
  durably records before acknowledging.
- `bot/outbox.py` — documentation of the worker maturity/claim semantics only.
- `tests/test_grouping.py` — NEW-04 grouping, boundary, ordering, isolation and worker tests.
- `tests/test_new04_prompt_grouping_debounce.py` — 11 focused restart/recovery/dedupe/
  isolation/cancellation/concurrency/debounce tests.
- `tests/test_new02_prompt_grouping_identity.py`, `tests/test_4b.py`,
  `tests/test_existing_conversation_repository_context.py`,
  `tests/test_persistent_ready_sticky_routing.py`, `tests/test_miniapp_operations.py` —
  updated expectations for the owner-approved time-window behavior while retaining
  cleanup/ownership assertions.

No Mini App source/frontend file was modified.

## 4. Batch lifecycle and database design

The durable `outbox` row is the batch:

1. First eligible prompt: `INSERT` a `pending` row with `created_at=updated_at=now`.
2. Subsequent eligible prompt within the window: append text and message identity to the
   same row and set `updated_at=now` (resets the inactivity deadline).
3. Expiry: the existing outbox worker may claim the row only when
   `updated_at <= now - GROUP_WINDOW`.
4. Dispatch: the existing `claim_outbox`/`_post_claimed` path sends the complete row once.
5. Cleanup: the existing per-row original IDs + acknowledgement IDs + confirmation cleanup.

No separate finalization table or second SQLite writer exists. The additive
`telegram_message_parts` JSON column stores `(message_id, text)` pairs so the text can be
ordered by Telegram message ID; old rows receive `[]` and fall back safely to their existing
text and arrival order.

## 5. Exact debounce semantics

- Window: exactly **3 seconds** (`GROUP_WINDOW = timedelta(seconds=3)`).
- A message at elapsed `0 <= elapsed <= 3s` from the last accepted part joins the row.
- Every accepted part updates `updated_at`, so the next deadline is 3 seconds after that part.
- At exactly 3 seconds the boundary is inclusive for acceptance; the worker also considers
  the row mature at `updated_at + 3s`.
- If acceptance and expiry race, SQLite `BEGIN IMMEDIATE` serializes them: either acceptance
  wins and refreshes the deadline, or claim wins and the new message starts a new row. No
  partially refreshed row can be claimed.
- The deadline is persisted in `updated_at`; no in-memory timer is authoritative.
- A restart sees `pending` rows and the worker waits/claims according to the same persisted
  deadline.

## 6. Ordering, identity, routing and isolation

- Batch key is `(conversation_id, chat_id)`. Bot access is private-chat only
  (`chat.type == "private"`), so the private chat ID is the user identity; different chats
  never share a row.
- Different OpenHands conversations use different `conversation_id` values and therefore
  different rows.
- A routing change is checked at the acceptance boundary (`expected_routing`), including the
  NEW-01 routing-pause check. A pending A row is not redirected to B; later B messages form a
  B row.
- Message identity: valid positive `telegram_message_id` values are stored. Duplicate
  `update_id` is rejected before writing; duplicate message identity in a pending row is
  rejected without appending content. Parts are sorted by `message_id` when all parts have
  valid IDs; otherwise arrival order is retained.
- Text and IDs are persisted before any acknowledgement is sent.

## 7. Restart and crash recovery

- `pending`: remains after restart and is claimed when mature.
- `claimed` before POST: `outbox_recover` returns it to `pending`; safe to retry.
- `sending` before restart: moves to `unknown`; no automatic second POST.
- `sent`/`unknown`/`failed`: never re-sent automatically.
- A crash before/after insertion cannot create a second logical prompt because the same
  outbox row is the batch; there is no second finalization insert.

## 8. Outbox atomicity and duplicate-dispatch protections

- Claim is an atomic `UPDATE ... WHERE status='pending'`; a row cannot be claimed twice.
- Repeated finalization/claim attempts return no row once claimed.
- A retry that returns the row to `pending` reuses the same row and logical prompt.
- No exactly-once external Telegram delivery is claimed; the existing at-most-once semantics
  remain.

## 9. NEW-01 compatibility

The existing `BEGIN IMMEDIATE` acceptance boundary and `routing_paused:<telegram_id>` check are
unchanged. `tests/test_new01_cancel_prompt_atomicity.py` passes. Added
`test_cancel_during_pending_batch_preserves_accepted_part_and_rejects_later`: a part accepted
before `/cancel` remains in its pending row; a later part after `/cancel` is rejected. This is
the existing NEW-01 rule (accepted-before-cancel survives), not a batching bypass.

## 10. NEW-02 compatibility

- Explicit `reply_to_message_id` remains the strongest identity signal and can continue the
  batch containing that message even outside the time window.
- A reply to a message not in a pending batch is not time-merged into an unrelated row.
- Original message IDs, acknowledgement IDs, cleanup isolation, and no-delete-unknown
  guarantees remain covered by the NEW-02 tests.
- The previously time-separation expectation is intentionally changed because NEW-04 has
  explicit owner approval for time-window grouping; the identity/cleanup safety tests remain.

## 11. Tests and exact results

Commands run in `/workspace/project/OpenHandBot`:

| Command | Result |
|---|---|
| `python -m pytest -q` | **3754 passed**, 0 failed, 74 warnings (exit 0) |
| Focused NEW-04/NEW-01/NEW-02/outbox/handlers suites | **275 passed** (exit 0) |
| `tests/test_new04_prompt_grouping_debounce.py` | **11 passed** |
| `pytest -q tests/test_new04_prompt_grouping_debounce.py tests/test_grouping.py` | **41 passed** |
| `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** (exit 0) |
| `python -m pyflakes bot automation tools main.py tests/` | exit **0** |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High **0**, exit 0 |
| `python -m pip_audit -r requirements-dev.txt` | No known vulnerabilities, exit 0 |
| `python -m compileall -q bot automation tools main.py tests` | exit **0** |
| `git diff --check` | exit **0** |

Covered behavior includes: first-message dispatch after 3s, append within window, deadline
reset, several parts in order, no dispatch while parts continue, final dispatch after last
part, boundary acceptance, restart recovery, expired-deadline recovery, claimed-row recovery,
duplicate message identity, chat/destination isolation, cancellation during a pending batch,
and concurrent claim/append without content loss.

## 12. Independent review

**INDEPENDENT REVIEW NOT PERFORMED.** No genuinely separate reviewer session or independent
checkout was available in this environment. This report is an implementation report plus
self-review; it must not be described as independently reviewed or release-ready.

## 13. Remaining findings, risks and follow-up

- No exactly-once Telegram delivery; existing at-most-once behavior is unchanged.
- The approved trade-off remains: two independent messages within 3 seconds may be grouped.
- Mini App files were not modified; the shared DB path can group a Mini App prompt that is
  submitted without `client_ref`. The current frontend always sends `client_ref`, so this is
  an edge case, documented for follow-up.
- Per-part acknowledgements still mean "saved/queued", not "batch delivered"; the final
  delivery confirmation remains the existing completion notice.
- No live Telegram/OpenHands network test was performed.
- NEW-03 remains OPEN and untouched.

## 14. Git state

- Working-tree changes: `bot/db.py`, `bot/handlers.py`, `bot/outbox.py`,
  `tests/test_grouping.py`, `tests/test_new02_prompt_grouping_identity.py`,
  `tests/test_4b.py`, `tests/test_existing_conversation_repository_context.py`,
  `tests/test_persistent_ready_sticky_routing.py`, `tests/test_miniapp_operations.py`,
  `.agent/PROGRESS.md`, the new `tests/test_new04_prompt_grouping_debounce.py`, and
  `docs/reviews/OHB2-NEW04-AUTOMATIC-MULTI-MESSAGE-PROMPT-GROUPING-IMPLEMENTATION-REPORT.md`.
- Intended changes are committed on local `main` as part of synchronization; no PR, merge,
  deployment, or Autopush activation.


## 15. Safety confirmation

No `git reset`, `git clean`, force operation, broad deletion, `git add .`, PR, merge,
deployment, release, production Telegram/OpenHands call, or Autopush activation was
performed. The user-authorized synchronization commit and push to `main` were performed.
Existing NEW-01/NEW-02 work and unrelated workspace state were preserved.
