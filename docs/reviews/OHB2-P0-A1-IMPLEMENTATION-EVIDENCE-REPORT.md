# OHB2-P0-A1 — Implementation Evidence Report (RETROSPECTIVE reconstruction)

> Prepared by an AI agent (OpenHands) on behalf of the owner. **This is a RETROSPECTIVE
> RECONSTRUCTION, not a contemporaneous implementation report.** No contemporaneous A1 report was ever
> produced (established by exhaustive search; re-confirmed here). It traces the A1 acceptance criteria
> to the **actual, current** source and tests, and reports only commands **executed during this task**
> with their real results. No historical dates, agent actions, test results, or approvals are
> fabricated. The only repository write is this report at `docs/reviews/`; no implementation/test
> change, no commit/push/PR/merge/deploy/release/publication, no production call, no Autopush activation.

- **Task ID:** OHB2-P0-EXECUTE-MISSING-A0-A1-R4-EVIDENCE (Phase Four; originally authored under OHB2-P0-A0-A1-R4-REVIEW-AND-FINAL-CLOSURE).
- **Date (UTC):** 2026-11-11.
- **Stage:** P0 **A1** — Local staging store + secure validation.
- **Verdict:** **`A1_EVIDENCE_SUFFICIENT`** (implementation present, acceptance criteria met by
  executable evidence; one LOW plan-deviation documented).

---

## 1. Scope and acceptance criteria (from the authoritative plan)

Source: `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` (R4,
SHA-256 `06be7ea850c0f605ab6c23a161b19da0733143adaba852ddae6650f0836de868`), §6 "Stage A1", §3.3, §5.

- **Objective:** store accepted attachment bytes locally, safely.
- **Scope/files (planned):** `bot/attachments.py` (new), `bot/files.py` (reuse validators), config
  (optional size/type knobs), **`.gitignore`** (add the staging path — F3).
- **Intended behavior:** download to a `0700` staging dir with opaque names; enforce size cap +
  extension/MIME allowlist; never trust the original filename as a path.
- **DB impact:** item rows reference staging tokens.
- **Security invariants:** no path traversal (opaque names, no user path components); bounded size;
  allowlist; no symlink following.
- **Crash-safe write ordering (F5, row-first):** (1) durable item row `pending` **before** bytes;
  (2) write bytes under the opaque token; (3) validate against written bytes; (4) transition to
  `stored` only after validation. No cross-store atomicity claimed.
- **Failure/crash:** staging write failure ⇒ item stays `pending`, no `stored`, no dispatch.
- **Tests (planned):** oversized rejected; disallowed type rejected; traversal filename neutralized;
  staging dir mode; download failure ⇒ not `stored`; crash-before/after-write recovery (row-first).
- **Acceptance (planned):** adversarial validation tests pass; **no file created on rejection**;
  **every incomplete item is reachable by the sweep**.
- **Rollback (planned):** delete staging dir contents; **disable via the new flag** (F7 — the flag does
  not exist yet and must be added; see §3.3).

---

## 2. Implementation — file paths and symbols (verified against current source)

File: `bot/attachments.py` (1,095 lines). A1-relevant symbols:

| Item | Location | Verified |
|---|---|---|
| Size cap | L55 `MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024` (3 MiB; matches proposal §5.7) | ✅ |
| Staging dir name / modes | L57–L59 `STAGING_DIRNAME="attachment_staging"`, `STAGING_DIR_MODE=0o700`, `STAGING_FILE_MODE=0o600` | ✅ |
| Token scheme | L60 `_TOKEN_HEX_BYTES=16`; L134 `new_staging_token()` = `secrets.token_hex(16)` ⇒ 32 hex chars | ✅ |
| Denied extensions allowlist | L65 `_DENIED_EXTENSIONS` (executable/script types) | ✅ |
| Denied magic bytes | L84 `_DENIED_MAGIC` (ELF, MZ, `#!`, Mach-O, Java) | ✅ |
| `StageStatus` / `StageResult` | L99 / L113 (STORED, REJECTED_SIZE, REJECTED_TYPE, REJECTED_NAME, REJECTED_EMPTY, REJECTED_BATCH, WRITE_FAILED, DB_FAILED) | ✅ |
| `staging_root_for(db_path)` | L139 — subdir of the DB dir | ✅ |
| `sanitize_display_name` | L147 — strips path components, control chars, NUL, edge dots; caps length 200 | ✅ |
| `extension_of` | L161 | ✅ |
| `ensure_staging_root` | L172 — creates `0700`, rejects symlink/non-dir, re-chmods | ✅ |
| `_is_within` | L200 — realpath containment | ✅ |
| `_is_denied_extension` / `_is_denied_magic` / `_read_head` | L206 / L210 / L214 | ✅ |
| `precheck_rejection` | L219 — cheap extension+declared-size checks (single policy source) | ✅ |
| `StagingStore` | L348; `_write_to_path` L371 (`O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW`); `store(...)` L397 | ✅ |
| Reused validators | `bot/files.py` `is_valid_conversation_id` (L70), `is_safe_workspace_path` (L75) | ✅ |
| `.gitignore` entry | `.gitignore` L12 `attachment_staging/` | ✅ |

---

## 3. Tests — file paths and names (verified)

File: `tests/test_attachment_staging_a1.py` — **34 tests** (docstring: "scope A1: local staging root
(0700) beside the DB, size/type validation, opaque names, root confinement, row-first ordering; **no**
batch lifecycle (A2), no accompanying text (A3), no sweep/cleanup (A4), no remote transfer (B)"):

- **A. Successful storage:** `test_valid_attachment_is_stored_and_item_marked_stored`,
  `test_staging_root_is_0700_and_beside_db`.
- **B. Type rejection:** `test_denied_extension_rejected_without_file` (parametrized: exe/sh/py/bat/ps1/so),
  `test_denied_magic_bytes_rejected_even_with_safe_extension`, `test_shebang_script_rejected`.
- **C. Size cap:** `test_declared_oversize_rejected_before_any_row_or_file`,
  `test_actual_oversize_rejected_midwrite_leaves_pending_no_file`, `test_exact_max_size_accepted`,
  `test_empty_payload_rejected`.
- **D. Safe names / traversal / absolute path:** `test_display_name_normalization_strips_path_components`,
  `test_traversal_display_name_stored_under_token_only`,
  `test_absolute_path_display_name_does_not_control_storage_path`.
- **E. Root confinement / symlink / no-overwrite:** `test_symlinked_staging_root_is_rejected`,
  `test_no_silent_overwrite_on_token_collision`,
  `test_staging_root_confinement_token_has_no_separators`.
- **F. Ownership + batch link:** `test_store_rejects_unknown_batch`, `test_store_rejects_wrong_owner`,
  `test_store_rejects_invalid_conversation_id_on_batch`.
- **G. Row-first (proven):** `test_row_first_db_row_exists_before_bytes_are_written`,
  `test_stored_only_after_write_completes`.
- **H. Partial / DB failure:** `test_partial_write_failure_leaves_pending_and_no_file`,
  `test_db_failure_on_row_insert_is_fail_closed`, `test_db_failure_on_status_update_unlinks_file`,
  `test_get_batch_db_error_is_fail_closed`.
- **I. No container escape:** `test_staging_token_is_opaque_and_not_derived_from_input`,
  `test_item_without_token_or_missing_file_is_not_stored`.
- **J. A0 preservation:** `test_a0_ttl_and_tables_still_intact`, `test_a0_owner_scope_unchanged`,
  `test_gitignore_ignores_staging_dir`.

---

## 4. Commands actually executed during this task (with real results)

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest tests/test_attachment_staging_a1.py -q -p no:cacheprovider` | **34 passed** (0 failed, 0 skipped, 0 xfailed, 0 deselected) |
| Inline mode/edge-case probe (isolated `/tmp`) | file mode `0o600`, dir mode `0o700`, ELF-without-extension ⇒ REJECTED_TYPE |
| `.venv/bin/python -m pytest -q -p no:cacheprovider` (full suite) | **2884 passed** |
| `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit **0** |
| Adversarial A1 probe (isolated `/tmp`) | 11/11 A1 probes PASS — see §6 |
| Mutation harness (isolated `/tmp/mut`) | 5/5 mutations caught — see §6 |

---

## 5. Evidence for each acceptance criterion

**Criterion 1 — "adversarial validation tests pass".** 34 tests pass; the set covers extension,
magic-byte, shebang, declared-size, actual-mid-write-size, empty, traversal, absolute path, symlink
root, token collision, unknown batch, wrong owner, invalid conversation id, partial write, and DB
failures.

**Criterion 2 — "no file created on rejection".**
- `test_denied_extension_rejected_without_file`: `staged_files(store) == []` and no item row.
- `test_declared_oversize_rejected_before_any_row_or_file`: no file, no row.
- `test_symlinked_staging_root_is_rejected`: `list(outside.iterdir()) == []` (nothing written outside).
- `test_partial_write_failure_leaves_pending_and_no_file`: partial file removed.
- `test_no_silent_overwrite_on_token_collision`: victim bytes preserved.
Verified by direct execution and by the inline probe (oversize mid-write left no partial; staged
listing matched only the accepted items).

**Criterion 3 — "every incomplete item is reachable by the sweep".**
- The plan's model: a crash leaves an item `pending` (with or without a file). A4's sweep scans
  `pending`/`stored`/`reaped` items and orphan items with no batch, plus untracked root files
  (`_sweep_orphan_items`, `_scan_root_untracked`).
- Verified in this session: `tests/test_attachment_cleanup_expiration_a4.py` includes
  `test_interrupted_creation_pending_item_no_file`, `test_orphan_item_without_batch_is_reaped`,
  `test_orphan_reaped_item_with_remaining_bytes_is_reaped`, and root-untracked counting — all pass
  (44 A4 tests). So every A1-created incomplete state is reachable by the sweep. ✅

**Security invariants:**
- **No path traversal:** opaque token (`secrets.token_hex`), `is_safe_workspace_path(token)` guard,
  `_is_within(root, path)` defense, `O_NOFOLLOW`; `sanitize_display_name` strips components.
- **Bounded size:** declared-size precheck + mid-write `_TooLargeError` (no partial file).
- **Allowlist:** denied extension set + denied magic bytes.
- **No symlink following:** `O_NOFOLLOW` + `ensure_staging_root` rejects a symlinked root + `_is_within`
  realpath check.

**Crash-safe row-first (F5):**
- `store()` performs: (0) batch/owner/conversation check; (0b) declared size; (0c) extension; then
  (1) `add_attachment_item(status='pending')` **before** any byte; (2) `_write_to_path`; (3) content
  validation (`written>0`, magic); (4) `set_attachment_item_status('stored')` only on success.
- `test_row_first_db_row_exists_before_bytes_are_written` observes the row (status `pending`) at the
  instant the staging file is opened — **row-first proven**, not asserted.
- `test_stored_only_after_write_completes`: status is `pending` before the first byte and `stored`
  after completion.

**Failure/crash:** `test_db_failure_on_row_insert_is_fail_closed` (row insert fails ⇒ `DB_FAILED`, no
bytes), `test_db_failure_on_status_update_unlinks_file` (status update fails ⇒ file unlinked,
`DB_FAILED`), `test_partial_write_failure_leaves_pending_and_no_file`.

---

## 6. Adversarial probes and mutation testing (executed this session, isolated; workspace untouched)

**Probes (11/11 PASS):** traversal token (`../evil`) rejected; token with separator (`a/b`) rejected;
control-only display name stored with `display_name=None`; negative declared size not falsely rejected;
wrong owner rejected; tokens opaque 32-hex & unique; `sanitize('..')=None`; `sanitize('../../etc/passwd')='passwd'`;
`sanitize('a\x00b')='ab'`; oversize mid-write leaves no partial file; oversize file ≤ cap.

**Mutations (isolated `/tmp/mut` copy):**

| Mutation | Caught? |
|---|---|
| Skip the row-first insert (bytes written without a durable row) | ✅ 13 failed |
| Remove the mid-write size cap | ✅ 2 failed |
| Remove the `_is_within` confinement check | ✅ 1 failed |
| Remove `O_EXCL`/`O_NOFOLLOW` (allow overwrite) | ✅ 2 failed |
| Remove the symlinked-root rejection | ✅ 2 failed |

A1's security-critical invariants are **load-bearing**: none can be silently broken without failing
tests.

---

## 7. Unverified claims / missing evidence

- **No contemporaneous A1 report exists** (confirmed by exhaustive search). This report is a
  retrospective reconstruction and makes no claim about original authoring date/agent/approvals.
- The original A1 authoring test count is not independently attested; the count **34** is what the
  current suite yields now.

---

## 8. Deviations from the plan

| Deviation | Severity | Detail |
|---|---|---|
| **A1 rollback-by-flag (F7) not implemented** | **LOW** | The plan §3.3/§6 A1 says a rollback flag "**must be added**". Verified this session: **no** attachment/upload flag exists in `bot/features.py` (`HIDDEN_FEATURES = {files, export, cost, followups}`), `config.py`, `.env.example`, or `bot/app.py`. Rollback remains possible by unregistering the handler / deleting the staging dir, but not by a dedicated flag. |
| **Size/type bounds** | INFO | Bounds are **D-12 PROVISIONAL** (as the plan anticipates); the implementation uses a conservative 3 MiB cap + a denied-executable policy. This matches the plan's expectation and is not a deviation. |
| **`_DENIED_EXTENSIONS` vs. strict allowlist** | INFO | The plan says "extension/MIME allowlist". The implementation is a **deny-list** of executable/script types (policy: "any, except executable/script types", per proposal §5.7) plus a **magic-byte** deny check. This is a conservative realization of the stated policy; recorded as a note, not a defect. |

---

## 9. Known unresolved findings (carried forward)

- A1 had **no dedicated independent review** prior to this task. This task's **Phase Five** produces
  one: `docs/reviews/OHB2-P0-A1-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- The F7 rollback-flag deviation (LOW) is carried forward to the final consolidated report; it does not
  block closure (rollback is achievable; no correctness/safety impact).

---

## 10. Report integrity

- Durable path: `docs/reviews/OHB2-P0-A1-IMPLEMENTATION-EVIDENCE-REPORT.md`.
- `/tmp` path: `/tmp/OHB2-P0-A1-IMPLEMENTATION-EVIDENCE-REPORT.md`.
- Byte-identical (`cmp` verified); full-file SHA-256 recorded in the final consolidated report.
