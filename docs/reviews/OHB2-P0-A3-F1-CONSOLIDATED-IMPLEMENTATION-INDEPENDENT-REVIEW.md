# OHB2-P0-A3-F1-CONSOLIDATED-IMPLEMENTATION — Independent Adversarial Review

> Prepared by an AI agent (OpenHands) on behalf of the owner. **Read-only review**: the only
> repository write is this report at the exact `docs/reviews/` path (an authorized review artifact).
> No A3/F1 code, test, `.agent/PROGRESS.md`, `.openhands/memory/*`, owner-decision register, or
> approved design was modified. No commit/push/PR/merge/deploy.

- **Task ID:** OHB2-P0-A3-F1-FINAL-INDEPENDENT-IMPLEMENTATION-REVIEW
- **Date (UTC):** 2026-11-14
- **Scope reviewed:** the already-implemented A3/F1 work in the current (uncommitted) working tree,
  against **D-09-R2** and **D-25…D-35**.
- **Verdict:** **`PASS_WITH_NOTES`** (no BLOCKER/HIGH/MEDIUM; only LOW/INFO).
- **A3/F1 → A4 readiness:** **SAFE TO PROCEED** to the A4 entry gate.

---

## 1. Verdict

**`PASS_WITH_NOTES`.**

The implementation faithfully realizes the approved consolidated design R2 and the owner decisions
D-33 (durable message↔batch identity), D-34 (`TERMINAL_UNPROVEN` fail-closed routing), and D-35
(identity-evidence retention independent of `processed_updates`). SQLite foreign-key enforcement is
active and verified on the single production connection; identity+intent are persisted atomically;
terminal-associated and terminal-unproven text cannot reach `_send_prompt` or ordinary outbox
creation; durable decisions precede acknowledgement and unresolved failures do not advance the update
boundary. All seven formerly strict-`xfail` tests are active, un-weakened, and mutation-proven
load-bearing.

No BLOCKER/HIGH/MEDIUM finding was identified. Findings F-1…F-3 are LOW/INFO documentation-hygiene
items only (stale docstrings/comments and one dead enum member); none affects behaviour, safety, or
D-33/D-34/D-35 conformance.

---

## 2. Repository baseline and preservation findings

| Item | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` |
| HEAD | `907b20de3fa6627795c14f29677e9f39c68e82f4` |
| origin/main | `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` |
| upstream | none configured for the branch |
| `git status --short` | **60 entries** = 46 untracked (`??`) + 14 modified (` M`) |
| staged | 0 |
| stash | 0 |

- The working tree **still contains the A3/F1 implementation** described by the implementation
  report: `bot/db.py` (identity schema, FK pragma, validator, atomic write, classification,
  retention-independent lookup), `bot/handlers.py` (terminal fail-closed routing, identity plumbing),
  and the four A3/F1 test files.
- The `HEAD` is unchanged from the implementation report (`907b20de…`); the reflog's two most recent
  `reset: moving to HEAD` entries are **pre-existing** (dated 2026-11-13 10:19, before this review
  session which began 2026-11-14 ≈08:4x). This review created **no** commit.
- **Preservation:** no `git reset` / `git clean` / force op / broad restore / revert / delete was run;
  no `git add .`/`-A`; nothing committed/pushed. The only repository write is this report file.
- **Protected files untouched:** `.agent/PROGRESS.md` (mtime 2026-11-13 21:15), `.openhands/memory/*`
  (mtime 2026-11-13), owner-decision register (hash unchanged — see §3). Verified by `ls`/`sha256sum`.

### 2.1 Exact changed-file list and diff statistics (tracked, `git diff --numstat`)

| File | + | − |
|---|---|---|
| `.agent/PROGRESS.md` | 1217 | 0 |
| `.gitignore` | 3 | 0 |
| `bot/app.py` | 16 | 13 |
| `bot/db.py` | 875 | 1 |
| `bot/handlers.py` | 458 | 5 |
| `bot/update_outcomes.py` | 5 | 1 |
| `bot/web/app.py` | 5 | 1 |
| `bot/web/ratelimit.py` | 14 | 4 |
| `bot/web/sessions.py` | 11 | 4 |
| `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` | 72 | 3 |
| `docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md` | 49 | 0 |
| `tests/test_miniapp_ratelimit.py` | 43 | 0 |
| `tests/test_miniapp_session_persistence.py` | 92 | 0 |
| `tests/test_unsupported_attachment_rejection.py` | 21 | 6 |

New untracked artifacts relevant to A3/F1: `tests/test_attachment_message_identity_a3.py` (380 lines).
(`bot/attachments.py` 653 lines and `bot/attachment_text.py` 108 lines are earlier-stage A0–A3
modules, not A3/F1.)

> Note: the diff above includes earlier-stage A0–A3 and unrelated Mini-App work that pre-dates this
> task's implementation report; the A3/F1-specific delta is concentrated in `bot/db.py`,
> `bot/handlers.py`, and the four A3/F1 test files.

---

## 3. Reference hashes and verification status

| # | Reference | Expected SHA-256 | Observed | Status |
|---|---|---|---|---|
| 1 | `AGENTS.md` | (n/a) | `d6ceda4e890681aa8c50f8fb8052de810ab8320d0ee7e0b20a6476d7f6565bc4` | present |
| 2 | `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` | `1eca72c1c3a6e9962719b59d7ba0d7eff02d5b76e6464f7d052d0d9ea967471c` | `1eca72c1…967471c` | **MATCH** |
| 3 | A3/F1 consolidated technical design R2 | `a9a38dfffcb8f191437d8a24384db3c40fc311cef52872f4c2c086c634f81067` | `a9a38dff…34f81067` | **MATCH (recovered)** |
| 4 | A3/F1 implementation report | `8bffa43aab0e82d78a2d43dc12dbf8b7507328a39b538e69848bb4dcc8a778a8` | `8bffa43a…cc8a778a8` | **MATCH (recovered)** |
| — | `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` | `06be7ea8…` | `06be7ea850c0f605ab6c23a161b19da0733143adaba852ddae6650f0836de868` | **MATCH** |

**Recovery note (transparency):** the two `/tmp` references (design R2 #3 and implementation report #4)
were **absent from disk** in this session — `/tmp` is reset between sessions in this environment. They
were reconstructed from the durable conversation event log (replaying the `file_editor` create/
str_replace operations in order) and the reconstructed bytes were confirmed to hash to the exact
expected values above. **No missing reference was fabricated or silently substituted**; both recovered
artifacts match their authoritative hashes byte-for-byte. The design R2 verdict read from the recovered
text is `IMPLEMENTATION_READY`.

Because references #1–#4 all verified, the review reaches a defensible verdict.

---

## 4. D-33 / D-34 / D-35 conformance matrix

Legend: ✅ conforms · ⚠️ conforms with a non-blocking note.

### D-33 — durable message↔batch identity

| Requirement | Evidence | Result |
|---|---|---|
| Canonical identity = `(telegram_id, chat_id, message_id)` | `attachment_message_identity` PK `(telegram_id, chat_id, message_id)` (`bot/db.py:805`); `normalize_message_identity` (`bot/db.py:297`) | ✅ |
| `update_id` is a **separate** delivery identity (not part of the key) | PK excludes `update_id`; `update_id` only used for `processed_updates`/ACK | ✅ |
| `conversation_id` is separate routing context | stored as its own column, re-validated in-transaction | ✅ |
| Missing/malformed/conflicting/ambiguous identity fails closed | `normalize_message_identity` returns `None` on missing/`bool`/non-`int`/`0`/negative (`bot/db.py:315-319`); `record_attachment_intent` rolls back with no intent (`bot/db.py:1497-1500`) | ✅ |
| Uniqueness/conflict handling correct | PK ⇒ second binding raises `IntegrityError` ⇒ rollback; original preserved (`bot/db.py:1501-1511`) | ✅ |

### D-34 — terminal classification fail-closed

| Requirement | Evidence | Result |
|---|---|---|
| `TERMINAL_UNPROVEN` cannot fall through to ordinary prompt | `bot/handlers.py:1893-1906` rejects `TERMINAL_ASSOCIATED`/`TERMINAL_UNPROVEN` with `rejected_ineligible` and `return True` | ✅ |
| Missing identity evidence ≠ "new message" | `classify_attachment_routing` returns `TERMINAL_UNPROVEN` when a terminal batch exists and no identity row is found (`bot/db.py:1411-1418`) | ✅ |
| Text-equality / timestamps / latest-batch / inferred context not used for newness | no such comparison anywhere; classification uses only owner-scoped batch status + identity lookup | ✅ |
| `NONE` only after a successful, complete, owner-scoped query proving no relevant batch state | `NONE` returned only at the final `return` after unknown-status check, unresolved, live, expired-pending, and terminal checks all pass (`bot/db.py:1351-1425`); query failure raises | ✅ |
| Ordinary prompt requires positive evidence + independent owner/route/conversation validation | `NONE` ⇒ `return False`; `handle_text` then applies route/owner/`awaiting` checks (`bot/handlers.py:2040,2051-2071`) | ✅ |
| D-34 supersedes earlier D-32 terminal behaviour exactly as recorded | terminal branch blocks (was `return False`); stale docstrings remain — see F-1/F-2 | ⚠️ |
| N-2 owner-scoped cross-conversation tradeoff intact and disclosed | `has_terminal_attachment_batch` has no `conversation_id` filter (`bot/db.py:1321-1334`); test `test_terminal_other_conversation_still_blocks_n2` | ✅ |

### D-35 — identity-evidence retention

| Requirement | Evidence | Result |
|---|---|---|
| Identity evidence independent of `processed_updates` retention/pruning | `prune_processed_updates` only `DELETE FROM processed_updates` (`bot/db.py:2829-2863`); identity table separate | ✅ |
| Terminal transitions / batch cleanup cannot silently delete identity | no `DELETE FROM attachment_message_identity` in production code; no `DELETE FROM attachment_batches` in production code | ✅ |
| FK prevents deletion of a referenced batch | `FOREIGN KEY (batch_id) REFERENCES attachment_batches(batch_id) ON DELETE RESTRICT` (`bot/db.py:813-814`) | ✅ |
| No cascade deletion | `grep CASCADE` in `bot/db.py` → none | ✅ |
| No unapproved numeric retention policy | no retention duration constant for identity; comment "بلا مدّة احتفاظ" | ✅ |

---

## 5. SQLite FK, identity, transaction, and retention findings

- **`PRAGMA foreign_keys=ON` placement:** executed in `Database.__init__` immediately after
  `sqlite3.connect(...)` and before any transaction (`bot/db.py:562`). The pragma is then **read back**
  and required to be `1`, else a `RuntimeError` is raised (fail-closed) (`bot/db.py:563-566`). ✅
- **Single production connection:** `sqlite3.connect` in `bot/`/`main.py`/`automation/` occurs only in
  `bot/db.py:552`. The one other occurrence is `tools/katabump-sqlite-canary/canary.py` — a standalone
  operator canary that is **not imported by the runtime**, writes only its own `TABLE`, and never
  touches attachment tables. No production connection bypasses FK enforcement. ✅
- **Identity table PK + RESTRICT:** `PRIMARY KEY (telegram_id, chat_id, message_id)` and
  `ON DELETE RESTRICT` (no cascade) (`bot/db.py:805-816`). ✅
- **Atomic identity+intent:** `record_attachment_intent` opens `BEGIN IMMEDIATE`, re-validates
  owner/conversation/status/deadline in-transaction, CASes `pending→intent_recorded`, inserts the
  identity row, records the durable outcome, then commits once (`bot/db.py:1427-1517`). Rollback on
  any failure leaves neither an orphan identity nor an intent without its identity. ✅
- **BUSY/LOCKED & permanent errors:** the `except Exception: conn.rollback(); raise`
  (`bot/db.py:1514-1517`) propagates all SQLite errors (incl. `IntegrityError`, `OperationalError`);
  the handler catches, records a **non-ack-eligible** failure, and re-raises — never mistaken for
  success. ✅
- **No silent identity loss:** if identity is invalid the intent is rolled back (`bot/db.py:1497-1500`);
  no code path writes an intent without identity evidence. ✅
- **Retention:** identity evidence is never pruned; `prune_processed_updates` is bounded to
  `update_id <= boundary` only. ✅

---

## 6. Handler routing and ACK findings

Call path traced: `handle_text` (`bot/handlers.py:2032`) → `_handle_accompanying_text`
(`:1847`, invoked unconditionally before any ordinary-prompt/route-expiry path) →
`classify_attachment_routing` (`bot/db.py:1351`) → intent persistence (`record_attachment_intent`) or
rejection (`_reject_accompanying_text`, `bot/handlers.py:2001`) → ordinary prompt only on verified
`NONE` (`_send_prompt`, `:2061`).

- **Terminal text cannot reach `_send_prompt`/outbox:** the terminal branch rejects and returns before
  the ordinary path (`bot/handlers.py:1893-1906`). Mutation-proven (see §9). ✅
- **No implicit conversion / batch substitution / conversation substitution:** `LIVE` requires the
  route to match the batch conversation exactly, else `rejected_ineligible`; no "latest batch"
  fallback (`bot/handlers.py:1930-1938`). ✅
- **Genuinely new prompts remain possible:** `NONE` (verified) ⇒ `return False` ⇒ ordinary prompt,
  subject to independent route/owner/`awaiting` checks. Test `test_verified_none_preserves_ordinary_prompt`. ✅
- **Unknown/ambiguous/query-failure fail closed:** unknown status ⇒ `AttachmentBatchIntegrityError`
  before any classification (`bot/db.py:1352-1356`); query failure propagates ⇒ recorded
  non-ack-eligible failure. ✅
- **Durable decision precedes acknowledgement:** the rejection outcome / durable intent is committed
  before the (best-effort) reply; `record_rejected_ineligible` commits the outcome (`bot/db.py:1543`),
  and `_reject_accompanying_text` writes it **before** `reply_text`. ✅
- **Unresolved failures do not advance the boundary:** `acknowledgment_boundary` is computed from
  committed eligible outcomes and stops at the first non-eligible update; `record_update_failure`
  records a non-eligible outcome. Test `test_ack_does_not_advance_on_db_failure`. ✅
- **No exactly-once claim:** the design and code explicitly disclaim it. ✅

---

## 7. Seven former strict-xfail tests

Reconstructed the pre-A3 version of `tests/test_attachment_terminal_routing_remediation.py` from the
event log and diffed each target test body against the on-disk version.

| # | Test (now) | Disposition | Integrity |
|---|---|---|---|
| 1 | `test_f1_terminal_associated_text_must_not_reach_outbox[expired]` | active, PASS | body **identical** to pre-A3 (only marker removed) |
| 2 | `…[rejected]` | active, PASS | identical |
| 3 | `…[failed]` | active, PASS | identical |
| 4 | `test_f1_delivered_duplicate_text_must_not_be_replayed` | active, PASS | identical |
| 5 | `test_f1_terminal_other_conversation_must_not_auto_route` | active, PASS | identical |
| 6 | `test_f1_multiple_terminal_batches_must_not_auto_route` | active, PASS | identical |
| 7 | `test_race_classification_to_ordinary_prompt_is_fail_closed` (was `…_documented`) | active, PASS | **strengthened** |

- All seven were `@pytest.mark.xfail(reason=F1_BLOCKED, strict=True)`; only the marker was removed (and
  the now-unused `F1_BLOCKED` constant). **No assertion was weakened or removed**; each original
  failure scenario is still exercised.
- Test #7 was strengthened: it now additionally asserts `a.h.client.sends == []` and
  `a.db.update_outcome(...) == uo.REJECTED_INELIGIBLE` (the pre-A3 `_documented` variant asserted only
  `count_outbox() == 0`).
- **D-32 test updates are justified by D-34 and retain equivalent-or-stronger assertions:**
  - `test_classify_terminal_states`: expectation changed `TERMINAL` → `TERMINAL_UNPROVEN` (the approved
    D-34 contract; the state name changed, not the safety property).
  - `test_terminal_state_does_not_block_new_prompt` → **renamed** to
    `test_terminal_state_blocks_unproven_new_prompt` with a stricter contract (asserts
    `rejected_ineligible`, no sends, empty outbox, batch untouched). This is an owner-decision-driven
    expectation change (D-34 overrides the superseded D-32 "terminal → ordinary prompt" behaviour), not
    a weakening.
  - `test_terminal_batch_other_conversation_does_not_associate_new_text` → **renamed** to
    `test_terminal_batch_other_conversation_blocks_new_text` (same reasoning; adds batch-untouched
    assertion).
  - `test_delivered_batch_text_is_not_replayed`: re-asserts fail-closed (`rejected_ineligible`,
    no sends, empty outbox) — stronger than the old "ordinary prompt sent" expectation.

No test was deleted, skipped, broadly relaxed, or made order-dependent (a reversed-order run of the
three focused files passed 99/99).

---

## 8. New identity tests (34) and the production-factory FK test

`tests/test_attachment_message_identity_a3.py` — **34 test cases** (24 functions; one parametrized
over 11 invalid identities). Independently observed: **34 passed**.

Coverage verified: real SQLite FK behaviour (`DELETE` of a referenced batch raises
`sqlite3.IntegrityError`; insert of a non-existent batch reference raises); pragma read-back equals `1`;
init-failure propagates (fail-closed) via a transparent connection proxy; invalid-identity rejection
matrix; missing identity blocks intent persistence; durable binding; identity survives
`processed_updates` pruning; owner scoping; same-message-different-chat distinctness; rebinding
rejection (IntegrityError + rollback); terminal associated/unproven; end-to-end fail-closed; N-2;
cross-conversation new message blocked; ACK advance on rejection / no advance on DB failure; duplicate
delivery does not duplicate identity; expired-pending; verified `NONE` preserves ordinary prompt;
missing `message_id` does not crash and fails closed.

- **The production-factory FK integration test** (`test_production_connection_enables_foreign_keys`,
  `test_fk_pragma_set_before_transactions_on_all_paths`) opens the DB via the **real production path**
  (`bot.db.Database`), not a hand-rolled connection, and asserts on **actual SQLite behaviour**.
- **No mocked-away behaviour:** the FK tests exercise real `sqlite3` constraints. The only monkeypatch
  is the init-failure proxy (intentionally simulating a pragma failure) and `record_attachment_intent`
  in the ACK-failure test (intentionally simulating a DB failure). No weak assertions, no missing
  side-effect checks, no hidden skips.

---

## 9. Independently observed test commands and results

All commands were run by this reviewer in this session (not copied from the implementation report).

| Command | Result | Exit |
|---|---|---|
| `.venv/bin/python -m pytest tests/test_attachment_message_identity_a3.py -q` | **34 passed** | 0 |
| `.venv/bin/python -m pytest tests/test_attachment_terminal_routing_remediation.py tests/test_attachment_intent_a3.py tests/test_attachment_batch_state_routing_f1_1a.py -q` | **93 passed** | 0 |
| `.venv/bin/python -m pytest <the 7 former xfail test IDs> -q` | **7 passed** | 0 |
| `.venv/bin/python -m pytest -q` (full suite) | **2840 passed, 0 failed, 0 xfailed, 0 skipped** (72 warnings, ~147 s) | 0 |
| `node --test tests/frontend/*.test.js` | **219 pass, 0 fail** | 0 |
| `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | clean | 0 |
| `.venv/bin/python -m bandit -r bot/ automation/ main.py -lll -s B613` | **High: 0** (Low 5, Medium 17 — pre-existing) | 0 |
| `.venv/bin/python -m pip_audit -r requirements-dev.txt` | No known vulnerabilities found | 0 |

**Mutation proofs (reviewer-run, then restored):**
- Reverting the `TERMINAL_ASSOCIATED`/`TERMINAL_UNPROVEN` branch in `bot/handlers.py` to `return False`
  ⇒ **12 tests fail** (terminal/associated/unproven/N-2/end-to-end). Restored; `git diff --stat` for
  `bot/handlers.py` returned to the baseline 458/5.
- Removing the `PRAGMA foreign_keys=ON` line from `bot/db.py` ⇒ **3 FK tests fail**. Restored;
  `grep -c "PRAGMA foreign_keys=ON" bot/db.py` = 3 and `bot/db.py` diff returned to baseline 875/1.

These mutation results are **newly observed** by this reviewer and corroborate the implementation
report's claims. The implementation report's own numbers (2840 passed; 34; 93; 219; bandit High 0) were
independently reproduced.

---

## 10. Findings

| ID | Severity | Finding | Exact reference |
|---|---|---|---|
| **F-1** | **LOW** (doc) | `classify_attachment_routing` docstring step 5 still says a terminal batch ⇒ `TERMINAL` "does not block a new prompt", contradicting the implemented D-34 behaviour. Code is correct; the docstring is stale. | `bot/db.py:1370` |
| **F-2** | **LOW** (doc) | `has_terminal_attachment_batch` docstring still states terminal batches "do not block a new prompt by themselves (D-32 clause 2)". Superseded by D-34. Behaviour is correct. | `bot/db.py:1326` |
| **F-3** | **INFO** (dead code) | The `AttachmentRoutingState.TERMINAL` member is retained with a now-inaccurate comment and is **never produced** by `classify_attachment_routing` nor referenced in code. Kept (reasonably) for enum stability; harmless. | `bot/db.py:517` |
| **F-4** | **INFO** (doc) | The leading comment on the strengthened race test still says "F1 is broken (disabled) ⇒ we document it", stale after the fix. | `tests/test_attachment_terminal_routing_remediation.py:440` |

No BLOCKER, HIGH, or MEDIUM finding. F-1…F-4 are non-blocking documentation-hygiene items and do not
affect behaviour, safety, or D-33/D-34/D-35 conformance. They are recorded for the A4/cleanup stage to
tidy (they are **not** to be fixed in this read-only review).

**No genuine data-loss, routing, identity, transaction, or ACK-safety defect was downgraded.**

---

## 11. Scope and preservation audit

- A0/A1/A2 implementation behaviour unchanged: full suite green (2840 passed), including A0/A1/A2
  attachment tests (`test_attachment_staging_a1.py`, `test_attachment_batch_lifecycle_a2.py`,
  `test_attachment_batch_schema.py` present and passing).
- **No A4 (or later) implementation started:** no sweep/reaper/cleanup module or function exists in
  `bot/`; no new worker/scheduler/process; `bot/` module list unchanged.
- **No protected file modified:** register hash unchanged; `.agent/PROGRESS.md` and
  `.openhands/memory/*` mtimes unchanged (2026-11-13).
- No unrelated work overwritten or removed.
- **No commit/push/PR/merge/deploy:** HEAD unchanged (`907b20de…`); `git status` remains 60 entries.

---

## 12. A3/F1 → A4 readiness decision

**SAFE TO PROCEED.** The A3/F1 implementation conforms to D-33/D-34/D-35 and to design R2; the seven
formerly strict-xfail tests are active and mutation-proven; SQLite FK enforcement is active on the
production connection; identity+intent are atomic; terminal text cannot reach the ordinary prompt/outbox
path; and ACK safety holds. The remaining notes are LOW/INFO documentation items only.

The next action is to re-run the **A4 entry gate** using this durable review report (this file), and
only then begin A4 per `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` §6 "Stage A4". This review
does not perform the gate and does not start A4.

---

## 13. Report integrity

- `/tmp` path: `/tmp/OHB2-P0-A3-F1-CONSOLIDATED-IMPLEMENTATION-INDEPENDENT-REVIEW.md`
- Durable repository path: `docs/reviews/OHB2-P0-A3-F1-CONSOLIDATED-IMPLEMENTATION-INDEPENDENT-REVIEW.md`
- Both copies are byte-identical; the shared SHA-256 / line / byte counts are recorded in the task
  delivery message (a self-referential embedded hash cannot be stable).
