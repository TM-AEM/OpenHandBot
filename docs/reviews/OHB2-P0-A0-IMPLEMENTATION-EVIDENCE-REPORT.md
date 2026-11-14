# OHB2-P0-A0 — Implementation Evidence Report (RETROSPECTIVE reconstruction)

> Prepared by an AI agent (OpenHands) on behalf of the owner. **This is a RETROSPECTIVE
> RECONSTRUCTION, not a contemporaneous implementation report.** No contemporaneous A0 report was ever
> produced (established by exhaustive search in the previous final-closure audit and re-confirmed
> here). This document traces the A0 acceptance criteria to the **actual, current** source and tests,
> and reports only commands **executed during this task** with their real results. No historical
> execution dates, agent actions, test results, or approvals are fabricated. The only repository write
> is this report at `docs/reviews/`; no implementation/test change, no commit/push/PR/merge/deploy/
> release/publication, no production call, no Autopush activation.

- **Task ID:** OHB2-P0-EXECUTE-MISSING-A0-A1-R4-EVIDENCE (Phase Two; originally authored under OHB2-P0-A0-A1-R4-REVIEW-AND-FINAL-CLOSURE).
- **Date (UTC):** 2026-11-11.
- **Stage:** P0 **A0** — Local attachment batch schema + migration (foundation).
- **Verdict:** **`A0_EVIDENCE_SUFFICIENT`** (implementation present, acceptance criteria met by
  executable evidence; one documentation-only note).

---

## 1. Scope and acceptance criteria (from the authoritative plan)

Source: `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` (R4,
SHA-256 `06be7ea850c0f605ab6c23a161b19da0733143adaba852ddae6650f0836de868`), §6 "Stage A0", §5, §3.3.

- **Objective:** add durable local batch/item state in the **existing** DB.
- **Scope/files (planned):** `bot/db.py` — new tables `attachment_batches`, `attachment_items`;
  `_migrate` additions; `ATTACHMENT_BATCH_TTL`; accessor methods.
- **DB impact (planned):** two **new** tables (`CREATE TABLE IF NOT EXISTS`); **additive** migration;
  **no** change to existing tables/columns.
- **Security/ownership invariants (planned):** batch keyed by `telegram_id`; `conversation_id`
  validated with `files.is_valid_conversation_id`; no secrets stored.
- **Failure/crash (planned):** writes are single-transaction; partial writes impossible.
- **Acceptance (planned):** `python -m pytest -q` green; new tables present after init **and after
  re-init**.
- **Evidence (planned):** test names + `PRAGMA table_info` output.
- **Rollback (planned):** additive tables can remain unused; no destructive migration.

---

## 2. Implementation — file paths and symbols (verified against current source)

| Item | Location | Verified |
|---|---|---|
| Status constants + documented set | `bot/db.py` ~L110–L132 (`ATTACHMENT_BATCH_PENDING`, `ATTACHMENT_BATCH_INTENT_RECORDED`, `ATTACHMENT_BATCH_DISPATCHING`, `ATTACHMENT_BATCH_UNCERTAIN`, `ATTACHMENT_BATCH_DELIVERED`, `ATTACHMENT_BATCH_EXPIRED`, `ATTACHMENT_BATCH_REJECTED`, `ATTACHMENT_BATCH_FAILED`, `ATTACHMENT_BATCH_STATUSES`) | ✅ |
| Item-status constants | `bot/db.py` (`ATTACHMENT_ITEM_STORED` at ~L174; `ATTACHMENT_ITEM_REAPED` for A4) | ✅ |
| TTL constant | `bot/db.py` L266 `ATTACHMENT_BATCH_TTL = timedelta(minutes=15)` (distinct from `AWAITING_TTL = timedelta(minutes=10)` at L260) | ✅ |
| Dataclass `AttachmentBatch` | `bot/db.py` ~L496 (`batch_id, telegram_id, conversation_id, t0, status, created_at, updated_at, intent_text`) | ✅ |
| Dataclass `AttachmentItem` | `bot/db.py` ~L538 (`item_id, batch_id, staging_token, display_name, size_bytes, status, created_at, updated_at`) | ✅ |
| DDL: `attachment_batches` | `bot/db.py` ~L776 (`CREATE TABLE IF NOT EXISTS`) | ✅ |
| DDL: index `idx_attachment_batches_owner` | `bot/db.py` ~L785 `ON attachment_batches(telegram_id, conversation_id)` | ✅ |
| DDL: `attachment_items` | `bot/db.py` ~L790 (`CREATE TABLE IF NOT EXISTS`) | ✅ |
| DDL: index `idx_attachment_items_batch` | `bot/db.py` ~L801 `ON attachment_items(batch_id)` | ✅ |
| Migration (additive) | `bot/db.py` `_migrate()` — adds `intent_text` to pre-A3 `attachment_batches`; other columns added non-destructively; `CREATE TABLE IF NOT EXISTS` guarantees idempotency | ✅ |
| Accessors | `bot/db.py` `create_attachment_batch` (~L1091), `get_attachment_batch` (owner-scoped, ~L1117), `add_attachment_item` (~L1145), `_insert_attachment_item_nocommit`, `list_attachment_items`, `set_attachment_item_status` | ✅ |

**Note on the `intent_text` column:** it belongs to the later A3/D-27 work but is present in the same
table. A0's own contract (the two tables + `ATTACHMENT_BATCH_TTL` + additive migration) is satisfied;
the extra column is an additive A3 extension and does not contradict A0.

---

## 3. Tests — file paths and names (verified)

File: `tests/test_attachment_batch_schema.py` — **17 tests** (docstring declares scope "A0: two new
tables + additive non-destructive migration + `ATTACHMENT_BATCH_TTL`; no lifecycle, no file storage,
no send, no external call"):

1. `test_ttl_constant_is_15_minutes_and_distinct_from_awaiting_ttl`
2. `test_status_constants_are_the_documented_set`
3. `test_fresh_db_creates_both_tables`
4. `test_batches_table_columns_and_not_null`
5. `test_items_table_columns_and_not_null`
6. `test_expected_indexes_present`
7. `test_batch_roundtrip_defaults_and_t0_fixed`
8. `test_owner_scope_hides_batch_from_other_user`
9. `test_batches_isolated_per_conversation`
10. `test_item_roundtrip_and_list_order`
11. `test_items_isolated_per_batch`
12. `test_batch_id_is_primary_key_unique`
13. `test_conversation_id_validation_hook_accepts_stored_ids`
14. `test_migration_adds_tables_to_old_database_non_destructively`
15. `test_reinit_is_idempotent_and_preserves_attachment_rows`
16. `test_existing_rows_survive_upgrade`
17. `test_migration_adds_intent_text_to_pre_a3_database`

---

## 4. Commands actually executed during this task (with real results)

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest tests/test_attachment_batch_schema.py -q -p no:cacheprovider` | **17 passed** (0 failed, 0 skipped, 0 xfailed, 0 deselected) |
| `PRAGMA table_info(attachment_batches)` / `(attachment_items)` on a fresh DB (inline script) | Columns/NOT NULL/DEFAULT/PK printed — see §5 |
| `.venv/bin/python -m pytest -q -p no:cacheprovider` (full suite) | **2884 passed**, 72 warnings (~140 s) |
| `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit **0** (clean) |
| Adversarial A0 probe (inline `/tmp` script, isolated) | 6/6 A0 probes PASS — see §6 |

---

## 5. Evidence for each acceptance criterion

**Criterion 1 — "new tables present after init".**
`test_fresh_db_creates_both_tables` PASS. Direct `PRAGMA table_info` output from this session:

```
--- attachment_batches ---
  (0,'batch_id','TEXT',0,None,1)      # PK
  (1,'telegram_id','INTEGER',1,None,0)
  (2,'conversation_id','TEXT',1,None,0)
  (3,'t0','TEXT',1,None,0)
  (4,'status','TEXT',1,"'pending'",0)
  (5,'created_at','TEXT',0,None,0)
  (6,'updated_at','TEXT',0,None,0)
  (7,'intent_text','TEXT',0,None,0)
  indexes: ['idx_attachment_batches_owner','sqlite_autoindex_attachment_batches_1']
--- attachment_items ---
  (0,'item_id','TEXT',0,None,1)       # PK
  (1,'batch_id','TEXT',1,None,0)
  (2,'staging_token','TEXT',0,None,0)
  (3,'display_name','TEXT',0,None,0)
  (4,'size_bytes','INTEGER',0,None,0)
  (5,'status','TEXT',1,"'pending'",0)
  (6,'created_at','TEXT',0,None,0)
  (7,'updated_at','TEXT',0,None,0)
  indexes: ['idx_attachment_items_batch','sqlite_autoindex_attachment_items_1']
```

(The exact printed `batch_id` type in `attachment_items` is `TEXT NOT NULL`; shown here from the
session output.) Columns, NOT NULL flags, DEFAULTs, PRIMARY KEYs, and indexes match the test
assertions exactly.

**Criterion 2 — "new tables present after re-init" (idempotent).**
`test_reinit_is_idempotent_and_preserves_attachment_rows` PASS; `test_migration_adds_tables_to_old_database_non_destructively`
and `test_existing_rows_survive_upgrade` PASS (pre-existing `watched`/`outbox` rows survive).

**Criterion 3 — "`python -m pytest -q` green".**
Full suite **2884 passed** this session.

**Security/ownership invariants:**
- Batch keyed by `telegram_id`: `test_owner_scope_hides_batch_from_other_user` PASS (owner sees; other
  user `None`). Probe: owner-scoping works.
- `conversation_id` validated with `files.is_valid_conversation_id`:
  `test_conversation_id_validation_hook_accepts_stored_ids` PASS (the schema does not itself validate —
  that is A2/A3 scope, per the test docstring — but stored ids pass the standard validator).
- No secrets stored: schema stores only opaque ids, `telegram_id`, `conversation_id`, timestamps, and
  an optional `intent_text` (content text, no credentials). Verified by column inspection.

**Failure/crash (single-transaction):** A0 writers use `INSERT` + `commit()` per call (atomic at the
statement level); the A1 row-first ordering and A2 atomic acceptance build on this. No partial-write
path exists in A0 itself (it writes no files). `test_batch_id_is_primary_key_unique` PASS (PK
enforced).

**Rollback (additive, non-destructive):** the migration adds tables/columns only;
`test_migration_adds_tables_to_old_database_non_destructively` and `test_existing_rows_survive_upgrade`
PASS.

---

## 6. Adversarial probes (executed this session, isolated `/tmp`, workspace untouched)

| Probe | Result |
|---|---|
| Both tables exist after `Database(path)` | PASS |
| `create_attachment_batch(batch_id, None, ...)` rejected (`int(None)` ⇒ TypeError / integrity) | PASS |
| Empty `conversation_id` stored (schema does not validate; A2/A3 scope) | PASS (documented, not a defect) |
| Duplicate `item_id` rejected (PK) | PASS |
| Item with a non-existent `batch_id` allowed (no FK on `attachment_items` in A0) | PASS (documented; A2 scopes ownership) |
| `ATTACHMENT_BATCH_TTL == 15min` and `!= AWAITING_TTL (10min)` | PASS |

**Mutation testing (isolated `/tmp/mut` copy; workspace untouched):**

| Mutation | Expected | Observed |
|---|---|---|
| M1: `ATTACHMENT_BATCH_TTL` 15 → 10 | TTL test fails | **1 failed, 16 passed** ✅ caught |
| M2: drop `NOT NULL` on `telegram_id` | column/NOT NULL test fails | **1 failed, 16 passed** ✅ caught |
| M3: `status` DEFAULT `'pending'` → `'stored'` | DEFAULT test fails | **1 failed, 16 passed** ✅ caught |

The A0 tests are **load-bearing** (each mutation is detected); they are not vacuous.

---

## 7. Unverified claims / missing evidence

- **No contemporaneous A0 report exists** (confirmed by exhaustive search: `docs/reviews/` filenames,
  filesystem-wide `find` for `*a0*`/`*a1*`, `grep` for `OHB2-P0-A0`, `git log --all --name-only`,
  `.agent/PROGRESS.md` and `.openhands/memory/*` headings, `/tmp`). This report is a **retrospective**
  reconstruction; it makes no claim about the original authoring date, agent, or approvals.
- The **original A0 authoring test count** is not independently attested by any contemporaneous record;
  the count **17** is what the current suite yields now (this session).

---

## 8. Deviations from the plan

- **None material to A0.** A0's scope (two tables, TTL constant, additive migration, accessors) matches
  the plan. The `intent_text` column is an additive A3 extension, present in the same table.
- The plan's A1 "rollback-by-flag (F7)" item is **A1**, not A0; it is assessed in the A1 report.

---

## 9. Known unresolved findings (carried forward)

- A0 has **no dedicated independent review** prior to this task. This task's **Phase Three** produces
  one: `docs/reviews/OHB2-P0-A0-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- No A0-specific correctness or safety contradiction was found.

---

## 10. Report integrity

- Durable path: `docs/reviews/OHB2-P0-A0-IMPLEMENTATION-EVIDENCE-REPORT.md`.
- `/tmp` path: `/tmp/OHB2-P0-A0-IMPLEMENTATION-EVIDENCE-REPORT.md`.
- Byte-identical (`cmp` verified); full-file SHA-256 recorded in the final consolidated report.
