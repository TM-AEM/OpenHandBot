# OHB2-P0-A0 — Independent Adversarial Review (read-only)

> Prepared by an AI agent (OpenHands) on behalf of the owner. **Read-only, independent review**: the
> reviewer did not author the A0 code, the A0 tests, or the A0 retrospective evidence report, and treats
> the retrospective report as a **claim to verify**, not as evidence. All work is read-only; the only
> repository write is this report at `docs/reviews/`. No implementation/test change, no commit, push,
> PR, merge, deployment, release, publication, production call, or Autopush activation.

- **Task ID:** OHB2-P0-EXECUTE-MISSING-A0-A1-R4-EVIDENCE (Phase Three; originally authored under OHB2-P0-A0-A1-R4-REVIEW-AND-FINAL-CLOSURE).
- **Date (UTC):** 2026-11-11.
- **Reviewed:** P0 **A0** — local attachment batch schema + migration.
- **Reviewed artifacts:** `bot/db.py` (A0 sections), `tests/test_attachment_batch_schema.py`.
- **Reference report (treated as claim):** `docs/reviews/OHB2-P0-A0-IMPLEMENTATION-EVIDENCE-REPORT.md`.
- **Verdict:** **`A0_REVIEW_PASS`**.

---

## 1. Verification of each acceptance criterion against actual code

| # | Criterion (plan §6 A0) | Method | Result |
|---|---|---|---|
| 1 | Two new tables exist after init | Read DDL (`bot/db.py` L776, L790) + `test_fresh_db_creates_both_tables` + live `PRAGMA` | ✅ PASS |
| 2 | Two new tables exist after **re-init** | `test_reinit_is_idempotent_and_preserves_attachment_rows` (re-opens same path) + `CREATE TABLE IF NOT EXISTS` | ✅ PASS |
| 3 | Additive migration; **no** change to existing tables/columns | Read `_migrate()`: only `ALTER TABLE ... ADD COLUMN` and `CREATE TABLE IF NOT EXISTS`; `test_migration_adds_tables_to_old_database_non_destructively`, `test_existing_rows_survive_upgrade` | ✅ PASS |
| 4 | Batch keyed by `telegram_id`; ownership enforced | `get_attachment_batch(..., telegram_id=...)` adds `AND telegram_id=?`; `test_owner_scope_hides_batch_from_other_user` | ✅ PASS |
| 5 | `conversation_id` validated with `files.is_valid_conversation_id` | Schema stores it; validation is A2/A3 scope (documented in test docstring); `test_conversation_id_validation_hook_accepts_stored_ids` confirms stored ids pass the standard validator | ✅ PASS (validation correctly deferred, not falsely claimed) |
| 6 | No secrets stored | Column inspection: only ids, `telegram_id`, `conversation_id`, timestamps, optional `intent_text` | ✅ PASS |
| 7 | `ATTACHMENT_BATCH_TTL = 15min`, distinct from `AWAITING_TTL (10min)` | `bot/db.py` L260/L266; `test_ttl_constant_is_15_minutes_and_distinct_from_awaiting_ttl` | ✅ PASS |
| 8 | Single-transaction writes; no partial writes | A0 writes are single `INSERT` + `commit()`; A0 writes no files | ✅ PASS |
| 9 | Status set = documented set | `ATTACHMENT_BATCH_STATUSES`; `test_status_constants_are_the_documented_set` | ✅ PASS |
| 10 | `python -m pytest -q` green | Full suite executed this session | ✅ PASS (2884 passed) |

No acceptance criterion is unverified.

---

## 2. Do the tests exercise meaningful behavior and failure cases?

Independently read `tests/test_attachment_batch_schema.py` (17 tests). Assessment:

- **Schema-shape assertions are concrete:** exact column-set equality (`set(info) == {...}`), NOT NULL
  flags (`info[col][3] == 1`), DEFAULT (`info["status"][4] == "'pending'"`), PK (`info["batch_id"][5]
  == 1`), and index-name membership. These are **not** vacuous (`!= None`) checks.
- **Migration tests use a genuine old DB:** they build a pre-A0 `sqlite3` file with `watched`/`user_state`
  /`outbox` rows, then open `Database(path)` and assert both the new tables and the survival of old
  rows. `test_migration_adds_intent_text_to_pre_a3_database` builds a pre-A3 `attachment_batches`
  **without** `intent_text` and asserts the column is added and old rows keep `NULL`.
- **Isolation tests are real:** owner-scope (`telegram_id=222` ⇒ `None`), per-conversation, and
  per-batch isolation.
- **Negative cases present:** duplicate `batch_id` ⇒ `sqlite3.IntegrityError`; re-init must not silently
  duplicate rows.

**Mutation testing (executed this session in an isolated `/tmp` copy; workspace untouched):**

| Mutation | Caught? |
|---|---|
| `ATTACHMENT_BATCH_TTL` 15 → 10 | ✅ 1 failed, 16 passed |
| Drop `NOT NULL` on `telegram_id` | ✅ 1 failed, 16 passed |
| `status` DEFAULT `'pending'` → `'stored'` | ✅ 1 failed, 16 passed |

The tests are **load-bearing**: the core schema invariants cannot be silently broken without failing.

---

## 3. False-positive tests and missing negative cases

- **No false-positive pattern found.** The uniqueness test uses `try/except/else: raise AssertionError`,
  which fails if no exception is raised — correct. No test asserts a tautology.
- **Missing negative cases (assessed, not blocking):**
  - No test asserts that the schema **itself** rejects an invalid `conversation_id` — because A0's
    contract deliberately does not validate at the schema layer (validation is A2/A3). This is an
    accurate boundary, not a gap.
  - No test covers `batch_id = NULL` (SQLite `TEXT PRIMARY KEY` without `NOT NULL` permits NULL). See
    §4 — theoretical, not reachable through the real API, and consistent with the repo convention.
- The plan's A0 evidence expectation ("`PRAGMA table_info` output") is satisfied by the tests'
  `_table_info` helper, which queries real `PRAGMA table_info`.

---

## 4. Fail-open / fail-closed behavior where relevant

- **A0 is schema-only** — it has no dispatch, no send, and no fail-open decision surface. The relevant
  fail-closed behavior begins at A1/A2.
- **Ownership fail-closed:** `get_attachment_batch(batch_id, telegram_id=X)` returns `None` for a
  non-owner ⇒ callers treat as "no batch" (A1 `store` ⇒ `REJECTED_BATCH`; A2/A3 fail-closed). Verified
  in code and by the A1/A2/A3 reviews.
- **NULL `batch_id` observation (INFO, not a defect):** `batch_id TEXT PRIMARY KEY` (without `NOT
  NULL`) technically permits a NULL `batch_id`, and SQLite allows multiple NULLs in a PK. This was
  reproduced directly (`2` NULL rows inserted). **Impact: none in practice** — the sole production
  producer is `new_batch_id()` = `secrets.token_hex(16)` (never NULL), and `create_attachment_batch`
  is only reached with that opaque id (A2 `AttachmentService.accept`). The pattern matches the existing
  repository convention (`watched`, session tables use `TEXT PRIMARY KEY` without `NOT NULL`). Recorded
  as INFO; it does not affect any acceptance criterion.

---

## 5. Transaction and persistence assumptions

- Connection: `sqlite3.connect(path, check_same_thread=False)`, `row_factory=sqlite3.Row`, `PRAGMA
  journal_mode=WAL` (verified at `Database.__init__`). **One** connection/owner.
- A0 writers (`create_attachment_batch`, `add_attachment_item`) each execute one `INSERT` then
  `commit()` — atomic at statement level; a failure raises (no partial row).
- `_migrate()` runs inside `_init_schema` before the single `commit()`; the additive `ALTER TABLE`s and
  `CREATE TABLE IF NOT EXISTS` are idempotent across re-opens.
- **No cross-store atomicity is claimed** (A0 has no filesystem side); the F5 row-first ordering is an
  A1 concern and is verified in the A1 review.

---

## 6. Interaction with later stages (regression check)

| Later stage | Dependency on A0 | Verified |
|---|---|---|
| A1 | Relies on `attachment_items.status` default `'pending'`, `add_attachment_item` row-first, `set_attachment_item_status` | ✅ (`test_a0_ttl_and_tables_still_intact`, `test_a0_owner_scope_unchanged`) |
| A2 | Relies on `attachment_batches.t0`, status set, owner-scoped reads | ✅ (A2 review; 50 tests pass) |
| A3 | Adds `intent_text` additively; relies on status set | ✅ (`test_migration_adds_intent_text_to_pre_a3_database`) |
| A4 | Relies on item statuses + orphan items (no FK on `attachment_items.batch_id`) | ✅ (A4 review; orphan sweep covers items with no batch) |

**Design note (intentional, not a defect):** `attachment_items.batch_id` has **no** FK to
`attachment_batches`. This is consistent with the plan's A1 crash-recovery model ("orphaned temporary
bytes … bounded by the sweep scanning the staging dir for tokens with no live `pending`/`stored`
row") and with A4's orphan-item handling. Adding an FK would be a **behavior change** and is out of
scope. No regression observed.

---

## 7. Regressions, hidden dependencies, untested edge cases

- **No regression** to pre-A0 tables/behavior: the migration is additive; the full suite (2884) passes.
- **Hidden dependency:** none beyond the intentional A1/A2/A3/A4 dependencies above.
- **Untested edge cases (assessed):** NULL `batch_id` (§4, INFO); empty `conversation_id` accepted at
  the schema layer (A2/A3 scope). Neither affects A0 acceptance.
- **Naming/behavioral coupling:** `ATTACHMENT_ITEM_STORED` is defined near the A0/A1 boundary but is
  consumed by A1; harmless.

---

## 8. Unauthorized architectural changes

**None.** A0 adds two tables + one index pair + one constant to the **existing** `Database` class; it
introduces **no** new process, worker, scheduler, DB owner, or second database. `bot/features.py`,
`config.py`, and the handler wiring are untouched by A0. Consistent with plan §3.8 / §5 items 7 & 12.

---

## 9. Verified facts vs. historical assertions

- **Verified directly (this session):** DDL text, constants, accessor SQL, `PRAGMA` output, 17 tests
  passing, 3 mutations caught, NULL-PK behavior, no-FK behavior, additive migration.
- **Historical assertion (not independently attested):** the original A0 authoring date/agent/test
  count. The retrospective report correctly labels itself as a reconstruction and does not fabricate
  these. The count **17** is what the current suite yields now.

---

## 10. Findings

| ID | Severity | Finding | Impact on A0 | Blocking? |
|---|---|---|---|---|
| **A0-F1** | INFO | `batch_id TEXT PRIMARY KEY` (no `NOT NULL`) technically allows NULL/duplicate-NULL keys; not reachable via the real API; matches repo convention. | None | No |
| **A0-F2** | INFO | Schema does not validate `conversation_id` (deferred to A2/A3 by design). | None | No |
| **A0-F3** | INFO | `attachment_items.batch_id` has no FK (intentional; enables A4 orphan sweep). | None | No |

**No BLOCKER/HIGH/MEDIUM finding. No unverified critical acceptance criterion.**

---

## 11. Verdict

**`A0_REVIEW_PASS`.**

Every A0 acceptance criterion is verified against the actual code and executable tests; the tests are
meaningful, mutation-proven, and free of false-positive patterns; fail-closed ownership behavior is
correct; transactions/persistence are sound; interactions with A1–A4 are consistent; no unauthorized
architectural change exists; and no correctness or safety contradiction was found. The three findings
are INFO-only and do not affect any acceptance criterion.

---

## 12. Report integrity

- Durable path: `docs/reviews/OHB2-P0-A0-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- `/tmp` path: `/tmp/OHB2-P0-A0-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- Byte-identical (`cmp` verified); full-file SHA-256 recorded in the final consolidated report.
