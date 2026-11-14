# OHB2-P0-A1 — Independent Adversarial Review (read-only)

> Prepared by an AI agent (OpenHands) on behalf of the owner. **Read-only, independent review**: the
> reviewer did not author the A1 code, the A1 tests, or the A1 retrospective evidence report, and treats
> the retrospective report as a **claim to verify**, not as evidence. All work is read-only; the only
> repository write is this report at `docs/reviews/`. No implementation/test change, no commit, push,
> PR, merge, deployment, release, publication, production call, or Autopush activation.

- **Task ID:** OHB2-P0-EXECUTE-MISSING-A0-A1-R4-EVIDENCE (Phase Five; originally authored under OHB2-P0-A0-A1-R4-REVIEW-AND-FINAL-CLOSURE).
- **Date (UTC):** 2026-11-11.
- **Reviewed:** P0 **A1** — local staging store + secure validation.
- **Reviewed artifacts:** `bot/attachments.py` (A1 sections), `bot/files.py` (reused validators),
  `tests/test_attachment_staging_a1.py`, `.gitignore`.
- **Reference report (treated as claim):** `docs/reviews/OHB2-P0-A1-IMPLEMENTATION-EVIDENCE-REPORT.md`.
- **Verdict:** **`A1_REVIEW_PASS_WITH_NOTES`**.

---

## 1. Verification of each acceptance criterion against actual code

| # | Criterion (plan §6 A1) | Method | Result |
|---|---|---|---|
| 1 | Adversarial validation tests pass | Read the 34 tests + run them | ✅ PASS (34 passed) |
| 2 | No file remains after rejection | Read `store()` control flow + tests + inline probe | ✅ PASS (see §2 nuance) |
| 3 | Every incomplete item reachable by the sweep | Read A4 sweep + A4 tests (44 pass) | ✅ PASS |
| 4 | `0700` staging dir, opaque names | `ensure_staging_root` + `new_staging_token`; probe: dir `0o700`, file `0o600` | ✅ PASS |
| 5 | Size cap enforced (declared + actual) | `precheck_rejection` + `_TooLargeError` mid-write | ✅ PASS |
| 6 | Type allowlist (policy: reject executable/script) | `_DENIED_EXTENSIONS` + `_DENIED_MAGIC`; probe: ELF-without-extension rejected | ✅ PASS |
| 7 | Never trust the original filename as a path | `sanitize_display_name` (metadata only) + opaque token path | ✅ PASS |
| 8 | No path traversal; no symlink following; root confinement | `is_safe_workspace_path(token)`, `_is_within`, `O_NOFOLLOW`, symlinked-root rejection | ✅ PASS |
| 9 | Row-first write ordering (F5) | `store()` order + `test_row_first_...` | ✅ PASS |
| 10 | No `stored` on failure; no dispatch | status transitions only on success; A1 has no dispatch | ✅ PASS |
| 11 | `.gitignore` ignores the staging path (F3) | `.gitignore` L12 `attachment_staging/`; `test_gitignore_ignores_staging_dir` | ✅ PASS |
| 12 | Rollback: "disable via the new flag (F7)" | Searched for an attachment flag | ⚠️ **NOT IMPLEMENTED** (see §5) |

No acceptance criterion is unverified; criterion 12 is a **plan-deviation note**, not an acceptance
failure (see §5).

---

## 2. Control flow, persistence, validation, failure handling (independent reading)

`StagingStore.store()` order (read from source, `bot/attachments.py` L397–L516):

1. **(0) Ownership/binding guard** — `get_attachment_batch(batch_id, telegram_id=...)`; `None` or
   invalid `conversation_id` ⇒ `REJECTED_BATCH`. DB exception ⇒ `DB_FAILED` (fail-closed).
2. **(0b) Declared size** — `declared_size > max_bytes` ⇒ `REJECTED_SIZE` (before any disk use).
3. **(0c) Extension** — `_is_denied_extension` ⇒ `REJECTED_TYPE` (before any write).
4. **Token** — `staging_token or new_staging_token()`; `is_safe_workspace_path(token)` guard ⇒
   `WRITE_FAILED` if the token is not a safe relative path (defense).
5. **Root** — `ensure_root()` (creates `0700`, rejects symlink/non-dir); `_is_within(root, path)`
   double defense.
6. **(1) ROW-FIRST** — `add_attachment_item(status='pending')` before any byte (skipped only when
   `row_created=True`, the A2 path where the row was already written atomically). DB exception ⇒
   `DB_FAILED`.
7. **(2) Write** — `_write_to_path` opens with `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW` and mode `0600`;
   `FileExistsError` ⇒ `_CollisionError` ⇒ `WRITE_FAILED` (no silent overwrite); over-cap ⇒
   `_TooLargeError` ⇒ `REJECTED_SIZE`; any `OSError` ⇒ `WRITE_FAILED`; on any exception the partial
   file is unlinked.
8. **(3) Content validation** — `written <= 0` ⇒ `REJECTED_EMPTY` (file unlinked); `_read_head` failure
   ⇒ `WRITE_FAILED`; `_is_denied_magic` ⇒ `REJECTED_TYPE` (file unlinked).
9. **(4) Transition** — `set_attachment_item_status('stored', size_bytes=written)`; DB exception or
   `ok is False` ⇒ `DB_FAILED` (file unlinked). **`stored` is set only after a complete, validated
   write.**

**Nuance on criterion 2 ("no file created on rejection"):** for **declared-oversize** and
**denied-extension**, rejection happens **before any write** — truly no file. For **actual-mid-write
oversize** and **empty payload**, a partial/zero-byte file is created and then **unlinked**, so **no
file remains**. The plan's own A1 test expectation ("no file created on rejection") and the tests
assert the observable invariant `staged_files(store) == []`, which is satisfied. This is an accurate
and safe realization of the intent.

**Persistence:** the row is written via `add_attachment_item` (single `INSERT`+`commit`); the status
update is a separate `UPDATE`+`commit`. There is **no cross-store atomicity claim** (the plan's F5
explicitly disclaims it). The ordering guarantees that recovery can always find an incomplete item.

---

## 3. Meaningful positive and negative test coverage

- **Positive:** successful storage + `stored` status + real size; exact-max-size accepted; root mode
  0700; traversal/absolute display names stored under the token only (name is metadata).
- **Negative (extensive):** denied extensions (parametrized 6 types); denied magic bytes with a safe
  extension; shebang; declared oversize; actual oversize mid-write; empty; unknown batch; wrong owner;
  invalid conversation id; symlinked root; token collision (no overwrite); partial write failure; DB
  failure on row insert; DB failure on status update; DB failure on batch read.
- **Row-first proof:** `test_row_first_db_row_exists_before_bytes_are_written` intercepts `os.open` and
  captures the item list at file-open time — genuine proof, not a tautology.

**Mutation testing (this session, isolated `/tmp/mut`):** 5/5 mutations caught — skip row-first (13
failures), remove size cap (2), remove `_is_within` (1), allow overwrite (2), remove symlink-root
rejection (2). The security invariants are load-bearing.

---

## 4. Missing edge cases and false-positive tests

- **No false-positive pattern found.** Tests assert real filesystem/DB effects (`staged_files`,
  `read_bytes`, item status), not tautologies.
- **Edge cases assessed (non-blocking):**
  - **Unicode/`.`-prefixed names:** probe shows `sanitize_display_name("ملف.pdf") == "ملف.pdf"` and
    `.bashrc` ⇒ `bashrc`; benign (name is metadata only).
  - **No-extension executable:** covered by magic-byte check (probe: `noext` + ELF ⇒ `REJECTED_TYPE`).
  - **`extension_of("a.tar.gz") == "gz"`:** documented behavior; `.gz` is not a denied executable type.
  - **TOCTOU between `_is_within` (realpath) and `os.open`:** `O_NOFOLLOW` on the final component plus
    the `0700` root limits this; the root itself is re-validated (non-symlink) at `ensure_root`. No
    exploitable path found; recorded as INFO.
  - **`_DENIED_EXTENSIONS` is a deny-list, not a strict allow-list.** The plan says
    "extension/MIME allowlist"; the implementation is a conservative deny-list of executable/script
    types (matching proposal §5.7 "any, except executable/script types") **plus** a magic-byte check.
    This is a **policy realization note**, not a safety defect (the deny-list is broad and the
    magic-byte check catches extensionless executables).

---

## 5. Rollback-flag deviation (F7)

The plan (§3.3, §6 A1 "Rollback") states a rollback flag "**must be added**". Verified this session:
**no** attachment/upload flag exists in `bot/features.py` (`HIDDEN_FEATURES = {files, export, cost,
followups}`), `config.py`, `.env.example`, or `bot/app.py`. Therefore A1's planned rollback-by-flag is
**not implemented**.

**Severity: LOW.** Rationale: (a) the plan itself flagged F7 as "a design/implementation detail
requiring verification at implementation time (and is **not** implemented by this document)";
(b) rollback remains achievable operationally by unregistering the attachment handler
(`bot/app.py`) and/or removing the staging directory — A1 stores no data outside the DB and the
staging dir; (c) the deviation has **no** correctness, safety, or data-integrity impact (the staging
area is local-only and ignored by git). It is recorded for closure, not treated as blocking.

---

## 6. Interaction with A0 and later P0 stages

| Stage | Interaction | Verified |
|---|---|---|
| A0 | Uses `attachment_items` (`status` default `pending`), `add_attachment_item`, `set_attachment_item_status` | ✅ (`test_a0_ttl_and_tables_still_intact`, `test_a0_owner_scope_unchanged`) |
| A2 | `store(row_created=True, batch_acceptance=..., staging_token=...)` preserves row-first while avoiding a double insert; the persisted `staging_token` (F-1 fix) lets A4 reclaim bytes | ✅ (A2 review; F-1 regression tests) |
| A3 | None direct (A3 is text/intent) | ✅ |
| A4 | Sweep reaches A1's incomplete items (pending with/without file; orphan items; untracked root files) | ✅ (A4 review; 44 tests) |

No regression to A0; no later-stage contradiction.

---

## 7. Approved-architecture / owner-decision compliance

- **Local-only, single DB owner, single process, no new worker/scheduler** — A1 is a module over the
  existing `Database`; no async/threading/timer; consistent with plan §3.8 / §5 items 7 & 12. ✅
- **No remote calls / no production contact** — A1 never calls OpenHands or any network. ✅
- **Staging beside the DB, git-ignored** (F3) — verified `.gitignore` L12. ✅
- **No secrets stored** — only opaque tokens, sanitized display names, sizes, statuses. ✅
- **D-12 (size/type bounds)** is PROVISIONAL per the plan; the implementation uses a conservative
  default. ✅ (No owner decision violated.)

---

## 8. Regressions and unverified assumptions

- **No regression** to A0 or the full suite (2884 passed this session).
- **Unverified assumptions:** none material. The `staging_root_for` derives the root from the DB path;
  tests confirm it is beside the DB. The root's existence across process restarts is handled by
  `ensure_root()` (idempotent `mkdir(exist_ok=True)`).

---

## 9. Verified evidence vs. historical assertions

- **Verified directly (this session):** the `store()` control flow; the `O_EXCL|O_NOFOLLOW` open
  flags; mode `0600`/`0700`; `sanitize_display_name` behavior; 34 tests passing; 5 mutations caught;
  the `.gitignore` entry; the absence of an attachment feature flag.
- **Historical assertion (not independently attested):** the original A1 authoring date/agent/test
  count. The retrospective report labels itself as a reconstruction; the count **34** is current.

---

## 10. Findings

| ID | Severity | Finding | Impact | Blocking? |
|---|---|---|---|---|
| **A1-F1** | **LOW** | Rollback-by-flag (F7) not implemented; no attachment feature flag exists. | Operational rollback is coarser (unregister handler / delete dir); no correctness/safety impact. | **No** |
| **A1-F2** | INFO | Policy is a deny-list of executable/script types + magic bytes, not a strict allow-list. | Conservative; matches proposal §5.7. | No |
| **A1-F3** | INFO | `_is_within` realpath check + `os.open` TOCTOU window. | Bounded by `O_NOFOLLOW` + `0700` root; no exploit found. | No |
| **A1-F4** | INFO | `extension_of("a.tar.gz") == "gz"` (last component only). | `.gz` not a denied type; benign. | No |

**No BLOCKER/HIGH/MEDIUM finding. No unverified critical acceptance criterion.**

---

## 11. Verdict

**`A1_REVIEW_PASS_WITH_NOTES`.**

Every A1 acceptance criterion is verified against the actual code and executable tests; the control
flow implements row-first ordering, root confinement, no-overwrite, bounded size, type policy, and
fail-closed DB handling; tests are meaningful, mutation-proven, and free of false-positive patterns;
the sweep reaches every incomplete item; and no approved architecture or owner decision is violated.
The only substantive note is **A1-F1 (LOW)** — the plan's rollback-by-flag (F7) was not implemented —
which has no correctness or safety impact and does not block closure.

---

## 12. Report integrity

- Durable path: `docs/reviews/OHB2-P0-A1-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- `/tmp` path: `/tmp/OHB2-P0-A1-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- Byte-identical (`cmp` verified); full-file SHA-256 recorded in the final consolidated report.
