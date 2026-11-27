# OHB2-REMOVE-CHAT-FORWARDING-R01-R02-REMEDIATION — Implementation Report

**Task ID:** `OHB2-REMOVE-CHAT-FORWARDING-R01-R02-REMEDIATION`  
**Date:** 2026-11-27  
**Verdict:** `DONE`  
**Scope:** Fix only independent-review findings R-01 and R-02. No general routing refactor, no
commit/staging/push, no live integration.

---

## 1. Actual baseline

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `main` |
| HEAD | `12bd85291c02fcadb9203538f1b67fbd7498070a` |
| HEAD tree | `67aae5f0f1e2f9439b2c8dd5efc2ec0aee5c8f74` |
| Staged files | none |
| Tracked modifications | none |
| Untracked files | pre-existing independent-review report |
| Ignored artifacts | `.venv/`, `node_modules/`, caches, `.openhands/` |
| Pre-existing untracked file | `docs/reviews/OHB2-REMOVE-CHAT-FORWARDING-AND-CANCEL-INDEPENDENT-REVIEW-20261127.md` |

The checkout matches the independent review's historical observation: HEAD `12bd852`, tree
`67aae5f0...`, no staged or tracked working-tree changes. The only pre-existing untracked file
was the independent-review report; it was preserved byte-for-byte and is not modified by this
task.

No reset, clean, stash, branch switch, fetch, pull, rebase, merge, cherry-pick, commit, push,
PR, deployment, or live Telegram/OpenHands call was performed.

---

## 2. Findings and root cause

### R-01 — pending selection routed to stale `last_accessed`

Root cause:

- `handle_attachment` read only `get_last_accessed_conversation()` and accepted any non-empty
  value, without checking whether `user_state.awaiting_kind` was `newchat` or `reposearch`.
- `_handle_accompanying_text` compared a live attachment batch only with `last_accessed`; it did
  not check the pending selection state.
- The attachment DB acceptance methods did not re-check the pending selection inside their
  `BEGIN IMMEDIATE` transactions, so a state created between the handler read and the write
  could still bind the old target.

Effect: with `last_accessed=A` and a pending `newchat`/`reposearch`, a document or accompanying
text could be accepted against A instead of being rejected until the user completes selection.

### R-02 — silent clear-to-None CAS outcome

Root cause:

- After `add_or_group_outbox(...) == 0`, `_send_prompt` computed
  `routing_changed = last is not None and last != conversation_id`.
- A concurrent clear to `None` therefore made `routing_changed` false; no user reply was sent,
  even though the prompt was not accepted and the outcome became `explicitly_ignored`.

Effect: the prompt was not queued, but the user received no explanation.

---

## 3. Implementation

### `bot/db.py`

- Added `ATTACHMENT_BLOCKING_SELECTION_KINDS = {"newchat", "reposearch"}`.
- Added `AttachmentSelectionPending` for the transaction-level race.
- Added `_attachment_blocking_selection_kind_nocommit(...)`, which reads `user_state` through the
  caller's existing connection and does not depend on `last_accessed`.
- Added the guard inside the existing `BEGIN IMMEDIATE` transactions:
  - `record_attachment_intent` — accompanying text.
  - `accept_attachment_item` — appending an item to a live batch.
  - `accept_attachment_item_into_new_batch` — creating a new batch.
- On a blocking state, the transaction rolls back and raises `AttachmentSelectionPending`; no
  batch, item, intent, or acceptance row is written.

### `bot/attachments.py`

- Added `StageStatus.REJECTED_SELECTION`.
- `AttachmentService.accept` rejects a pending `newchat`/`reposearch` before authorization or
  classification, avoiding a remote authorization call and avoiding old-batch expiry mutation in
  the normal path.
- The existing acceptance try block catches `AttachmentSelectionPending` and returns
  `AcceptOutcome.REJECTED` with `REJECTED_SELECTION`; it does not download bytes or create a row.

### `bot/handlers.py`

- Added actionable attachment/text messages:
  - pending: complete/restart selection; the file/text was not saved.
  - expired: the selection timeout ended; restart selection.
- Added `_pending_selection_state(...)` and `_reject_pending_selection(...)`.
  - Non-expired pending state: marks the update explicitly ignored and replies.
  - Expired state: clears `awaiting` and records the outcome atomically through
    `clear_awaiting_and_record_outcome`, then replies.
- `handle_attachment` checks the pending selection before reading `last_accessed`.
- `_handle_accompanying_text` checks it after classifying a live batch and before comparing
  `last_accessed`; a pending selection cannot attach text to the old batch.
- `record_attachment_intent` catches `AttachmentSelectionPending` from the DB race and rejects
  the text with the same actionable message.
- `_send_prompt` now distinguishes:
  - expected target still selected;
  - selection changed to another conversation;
  - selection cleared to `None`;
  - duplicate/already-recorded outcome.
  A clear-to-None sends `"الشات المختار اتغيّر أو اتشال قبل حفظ رسالتك..."` and creates no
  outbox row. A genuine DB exception still propagates; it is not converted to a success or a
  silent ignore.

### `.agent/PROGRESS.md`

Added one narrow task section at the top with the goal, six acceptance criteria, actual baseline,
completed work, and `DONE` status. Existing progress sections were preserved.

---

## 4. Transaction and CAS guarantees

- The pending-selection check is repeated inside the same `BEGIN IMMEDIATE` transaction that
  writes the attachment intent/item/batch. The check and write are therefore serialized against
  `new_chat_no_repo`/`pick_repo`/`repo_search_prompt` state writes.
- On `AttachmentSelectionPending`, the DB transaction rolls back before returning; the service
  returns a structured rejection; the handler sends an actionable reply and does not claim
  acceptance.
- Expired awaiting state is cleared with `clear_awaiting_and_record_outcome`, which writes the
  clear and the update outcome in one transaction. There is no fallback to `last_accessed`.
- R-02 does not change the outbox CAS or durable-outbox semantics. It only makes the existing
  `out_id == 0` branch distinguish clear-to-None from an unchanged target and from a duplicate.
- No fallback conversation, automatic creation, new worker, new queue, new schema, or new
  persistence architecture was introduced.

---

## 5. Regression tests added

File: `tests/test_remove_chat_forwarding_r01_r02_remediation.py` — **13 tests**.

R-01 document tests:

1. `last_accessed=A` + pending `newchat` + document ⇒ no batch/item for A; actionable reply;
   explicitly ignored.
2. `last_accessed=A` + pending `reposearch` + document ⇒ no batch/item for A; actionable reply;
   explicitly ignored.
3. Pending selection with no `last_accessed` ⇒ explicit reply, no batch, no silent loss.
4. Expired pending `newchat` ⇒ state cleared, no batch, timeout reply, explicitly ignored.
5. No pending selection ⇒ normal attachment behavior still targets the selected conversation.
6. Pending selection created inside the service call after the handler precheck ⇒ DB guard rejects
   atomically; no batch/item.
7. Direct service acceptance with pending `newchat` ⇒ `REJECTED_SELECTION`, no batch/item.

R-01 accompanying-text tests:

8. Pending `newchat` + live old batch + text ⇒ no intent recorded against the old batch; reply.
9. Pending `reposearch` + live old batch + text ⇒ no intent recorded against the old batch; reply.

R-02 tests:

10. Clear to `None` immediately before CAS ⇒ explicit reply, no outbox, no false success.
11. Change from A to B immediately before CAS ⇒ existing “selection changed” reply, no outbox.
12. `add_or_group_outbox` raises a genuine database error ⇒ exception propagates; no reply/ack;
    no outbox row.
13. CAS succeeds with expected target ⇒ prompt queued and queued-ack sent.

The race tests use `asyncio.Event` synchronization and monkeypatched DB/blocking functions; there
are no sleeps or live network calls.

---

## 6. Verification — exact commands and results

All commands were run from `/workspace/project/OpenHandBot` with the existing `.venv`
(Python 3.13.15).

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_remove_chat_forwarding_r01_r02_remediation.py` | **13 passed**, exit 0, 1.69s |
| Expanded focused suite (35 files: new tests + removal/routing/attachment/handler/outcome tests) | **995 passed**, 2 warnings, exit 0, 95.38s |
| `python -m pytest -q` | **4420 passed**, 0 failed, 74 warnings, exit 0, 338.85s |
| `node --test tests/frontend/*.test.js` | **280 pass, 0 fail**, exit 0 |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **0 findings**, exit 0 |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **0 High, 22 Medium, 7 Low**, exit 0 |
| `python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities**, exit 0 |
| `python -m pytest -q tests/test_doc_code_parity.py` | **16 passed**, exit 0 |
| `git diff --check` | clean, exit 0 |

Bandit's 7 Low/22 Medium findings match the pre-existing baseline reported by the independent
review; no new High finding was introduced. The full-suite warnings are pre-existing
PTB/Starlette deprecations and are not hidden.

### Not run

- **Python 3.11 full suite / GitHub Actions CI:** NOT RUN. Local runtime is Python 3.13.15.
- **Live Telegram/OpenHands integration:** NOT RUN.
- **Mini App browser/UI run:** NOT RUN; only the existing Node frontend suite was run.

---

## 7. Compatibility checks

- **`/cancel`, `cancelroute`, `cancel_route`, `cancel_route_button`:** production grep found no
  matches; only generic `cancelled/canceled` status wording remains.
- **Routing pause state:** `routing_paused`, `pause_routing`, `resume_routing`,
  `is_routing_paused` — no production matches.
- **Forwarding instructions/buttons:** grep for `إلغاء التوجيه`, `التوجيه متوقف`,
  `رسايلك الجاية`, `لحد ما تفتح` — no production matches.
- **Ordinary `last_accessed` prompt routing:** covered by the expanded focused suite and full
  suite; normal prompt acceptance still queues to the selected conversation.
- **Manual copy and `.txt` controls:** covered by the focused/full suites; no source change.
- **New-chat/repository-search workflows:** pending states are rejected for attachments/text;
  the actual new-chat/repository-selection text paths remain unchanged.
- **Attachment lifecycle/batching/accompanying text:** focused and full suites pass.
- **CAS/durable outbox guarantees:** existing CAS tests and new R-02 tests pass; no outbox
  architecture change.
- **DEF-011-C local-only copy:** not modified; existing attachment copy behavior remains.
- **Approved architecture:** no schema, migration, worker, queue, dependency, or decision change.

One pre-existing low-severity residual remains outside this task's scope:

- `bot/handlers.py:3282` still has the old wording `انتهت مهلة التوجيه` in the ordinary text
  timeout branch (R-03 from the independent review).
- `bot/db.py:4834` still contains the legacy `if kind == "route"` branch in `take_awaiting`
  (R-04 from the independent review).
- Historical/planning docs still contain stale `/cancel` references (R-05).

These were not changed because this task explicitly limits scope to R-01/R-02.

---

## 8. Final Git state

### Committed

None. HEAD remains `12bd85291c02fcadb9203538f1b67fbd7498070a`; tree remains
`67aae5f0f1e2f9439b2c8dd5efc2ec0aee5c8f74`.

### Working tree

Modified tracked files:

- `.agent/PROGRESS.md` — narrow task section.
- `bot/attachments.py` — early selection rejection and outcome mapping.
- `bot/db.py` — transaction-level selection guard.
- `bot/handlers.py` — prechecks, messages, race response.

Untracked files:

- `tests/test_remove_chat_forwarding_r01_r02_remediation.py` — new regression tests.
- `docs/reviews/OHB2-REMOVE-CHAT-FORWARDING-AND-CANCEL-INDEPENDENT-REVIEW-20261127.md` —
  pre-existing independent-review report, preserved.

Staging area: empty. No commit, push, branch, PR, deployment, or live call was made.

### Unrelated pre-existing work

The pre-existing independent-review report was not modified. No other pre-existing tracked or
untracked work was overwritten. `.agent/PROGRESS.md` was changed only by adding the new task
section at the top, as required by `AGENTS.md` §2; existing sections were left intact.

---

## 9. Remaining limitations

- The R-01 guard is intentionally scoped to the persisted `newchat`/`reposearch` awaiting states.
  The transient repository-list screen shown by `start_new_chat` has no persisted pending state;
  a document sent while only that menu is open remains governed by normal `last_accessed`
  selection. Changing that would require a new persisted menu state and is outside this task's
  approved scope.
- R-03/R-04/R-05 low-severity residuals listed above remain.
- Python 3.11/CI and live Telegram/OpenHands integration are unverified locally.
- This is an implementation report, not an independent review. A fresh read-only independent
  review is required before owner acceptance.

---

## 10. Verdict

`DONE`

R-01 is fixed for persisted `newchat`/`reposearch` selection states, with both handler prechecks
and transaction-internal DB guards. R-02 now sends an explicit response for a clear-to-None CAS
race and does not create a false acceptance. All required local checks pass. The next step is a
fresh, read-only independent review of the resulting diff.
