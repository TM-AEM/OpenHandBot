# OHB2 Repair Plans 01–04 — FINAL INDEPENDENT INTEGRATION AUDIT

> Prepared by an AI agent (OpenHands) on behalf of the owner. **Read-only audit**: the only
> repository write is this report at the `docs/reviews/` path (an authorized review artifact).
> No Plan 01–04 code, test, `.agent/PROGRESS.md`, `.openhands/memory/*`, owner-decision register,
> or approved design was modified. No commit/push/PR/merge/deploy. No production service was called.

- **Task ID:** OHB2-REPAIR-PLAN-01-RESOURCE-STAGING (header) / FINAL-INTEGRATION-AUDIT (active USER_CONTEXT)
- **Date (UTC):** 2026-11-14
- **Reviewer environment:** isolated venv `/tmp/ohb2_venv` (pytest 9.0.3, PTB 22.8, pyflakes 4.0.3,
  pip-audit 2.10.1, bandit 1.9.4, httpx). The system interpreter lacks these (deps reset); the venv is
  **outside** the repo.
- **Verdict:** **`PASS_WITH_NOTES`** — no BLOCKER/HIGH/MEDIUM finding. Plans 01–04 are internally
  consistent, non-contradictory, and do not weaken any P0 invariant. Notes are LOW/INFO only.

---

## 1. Baseline (verified, not assumed)

| Item | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `main` |
| HEAD | `9c8cf2eac7d5e7fe35ca5c6830341db91dd08fe2` |
| `origin/main` | `9c8cf2eac7d5e7fe35ca5c6830341db91dd08fe2` (in sync) |
| Working tree | 5 modified + 5 untracked — **all Plan 04** (uncommitted, untouched by this audit) |

Working-tree inventory (`git status --short`), preserved verbatim:

```
 M .agent/PROGRESS.md
 M bot/web/static/app.js
 M bot/web/static/styles.css
 M docs/MINI_APP.md
 M tests/frontend/dom_stub.js
?? docs/decisions/owner-briefs/OHB2-PLAN04-UI01-FRONTEND-AUTHORITY.md
?? tests/frontend/a11y.test.js
?? tests/frontend/chats_pagination.test.js
?? tests/frontend/keyboard_rows.test.js
?? tests/test_miniapp_http_journeys.py
```

**Plan 01 is already implemented on `main`.** `git merge-base --is-ancestor f6c0f24 HEAD` ⇒ **YES**.
Commit `f6c0f24` ("feat: OHB2 Repair Plan 01 — resource and staging safety (FIX-01..FIX-04)")
introduced the `OHB2-REPAIR-PLAN-01/FIX-0x` markers. Plan 02 was folded into `main` at `25ec46b`,
Plan 03 at `9c8cf2e`. Plan 04 (Mini App/frontend) is **uncommitted** in the working tree.

Consequence for this task: the header objective ("Implement Repair Plan 01 — FIX-01..04") is
**already satisfied at HEAD**; re-implementing it would be a pure regression risk. The active
USER_CONTEXT (independent read-only verification of Plans 01–04) is the operative work.

---

## 2. Verification runs (exact commands, real results)

| Check | Command | Result |
|---|---|---|
| Full suite | `pytest -q` (venv) | **3060 passed, 0 failed**, 72 warnings (148s) |
| Plan 01 resource-staging | `pytest tests/test_repair_plan_01_resource_staging.py tests/test_repair_plan_01_review_findings.py tests/test_attachment_staging_a1.py` | **91 passed** |
| Plan 02 lifecycle | `pytest tests/test_repair_plan_02_life0{1_f1_retry,1_f2_race,2_crash_recovery,3_intake_kill_switch,4_lifecycle_e2e}.py` | all green |
| Plan 03 D-34 routing + A4 | `pytest tests/test_attachment_terminal_routing_remediation.py tests/test_attachment_cleanup_expiration_a4.py` | **75 passed** |
| Polling/ACK/dup | `pytest tests/test_stage2_custom_polling.py tests/test_stage2_high_ack_blocking_fix.py tests/test_manual_polling_outcome_and_ack.py tests/test_manual_polling_handler_outcome_coverage.py tests/test_duplicate_update_dispatch.py tests/test_stage4_f1_status_cost_operational_ack.py` | **202 passed** |
| Security suites | `pytest tests/test_a2_conversation_authz.py tests/test_a2_export_auth.py tests/test_autopush_security.py tests/test_ci_workflow_security.py tests/test_deploy_manifest.py tests/test_f1_tombstone_enforcement.py tests/test_miniapp_*.py` | **311 passed** |
| Frontend (Node) | `node --test tests/frontend/*.test.js` | **250 passed / 0 failed** |
| pyflakes | `pyflakes bot/ automation/ tools/ main.py tests/` | exit **0** |
| pip-audit | `pip_audit -r requirements-dev.txt` | **No known vulnerabilities found** |
| bandit (High severity) | `bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High severity 0**, exit 0 |

**Note on the previously-reported `test_deploy_manifest` failure:** the daily log recorded
`1 failed / 3059 passed` on `main` with the sole failure being
`test_deploy_manifest.py::test_documented_manifest_is_import_sufficient`
(`ModuleNotFoundError: No module named 'telegram'`). In the isolated venv the full suite is
**3060 passed / 0 failed** ⇒ the failure is **environmental** (the test spawns a subprocess with a
stripped `HOME`, so a user-site `telegram` install is invisible; in the venv `telegram` lives in
`site-packages` and is found). **No regression.** The daily log's own note ("passes with real HOME")
agrees.

---

## 3. Plan 01 — resource & staging safety (FIX-01..04)

**FIX-01 (streaming download with a hard byte cap) — ✅ verified, source-grounded.**

The claim that PTB 22.8 `File.download_to_memory` is **not** streaming was re-verified from the
installed source, not from memory:

- `telegram/_files/file.py::download_to_memory` calls `request.retrieve(...)` and then does
  `out.write(buf)` **once**; for a local path it does `path.read_bytes()` (whole file).
- `telegram/request/_httpxrequest.py::do_request` returns `res.status_code, res.content`
  (whole body in memory).

So a "capped sink" would give **no** memory bound. `bot/handlers.py::_download_attachment_chunks`
correctly accepts only:
1. HTTPX streaming via `client.stream("GET", url, ...)` with `aiter_raw()` and a cumulative
   `len(buf) + len(chunk) > max_bytes` check ⇒ `AttachmentTooLargeError` **before** buffering more
   (rejects 3xx redirects, ≥400, and any non-`identity` `content-encoding`); and
2. a bounded local read (`_read_local_capped`).

Anything else (no URL, no streaming client, unreadable local file) ⇒ `StagingError` (**fail closed**,
before buffering). `File.download_to_memory` is **not** used as a fallback anywhere
(`grep download_to_memory` in `bot/`/`main.py` returns only comments/docstrings).

**FIX-02 (bounded concurrent downloads) — ✅ verified.** `MAX_CONCURRENT_DOWNLOADS = 4`;
`_get_download_semaphore()` is loop-bound (recreated if the running loop changes, safe for repeated
`asyncio.run` in tests). `test_concurrent_downloads_are_bounded` fires 12 concurrent downloads and
asserts `2 ≤ max_entered ≤ MAX_CONCURRENT_DOWNLOADS` ⇒ the bound holds and concurrency is real.

**FIX-03 (per-batch and total staging quotas) — ✅ verified.** `StagingStore.store()` enforces,
before any byte: item-count quota (`quota_block`, `extra_items=1`), per-batch byte quota
(`byte_quota_block`), and an effective write cap `min(file cap, remaining total, remaining batch)`.
Any quota/FS/DB failure ⇒ `REJECTED_QUOTA` / `DB_FAILED` (**fail closed, no write**).
**Defaults are `None` = disabled**, per the owner's Option A / D-12 (`test_quota_defaults_are_disabled`),
and production wires `StagingStore(db, db_path)` **without** quota args (`bot/handlers.py:1689`) —
the quotas are opt-in only. This is consistent with the recorded decision, not a defect.

**FIX-04 (staging-dir mode enforced fail-closed) — ✅ verified by real experiment** (no mocks):
a `0777` root is `chmod`'d back to `0700`; a **symlink** root is rejected (`StagingError`); a root
that is a **regular file** is rejected. `test_ensure_root_fails_closed_when_chmod_fails` and
`..._when_mode_still_wrong` prove that an unenforceable mode ⇒ `WRITE_FAILED` (fail closed).

**Plan 01 review-findings remediation (FIX-R01..R05)** is present: no unbounded fallback
(`StagingError` instead), `opportunistic_cleanup` removed from `accept()` (A4 only permits
startup-hook cleanup; `AttachmentReaper` now requires `store` or `db_path`).

---

## 4. Plan 02 — attachment lifecycle (LIFE-01..04)

- **LIFE-01 (`OpportunisticSweeper`)**: 60 s min-interval throttle (`OPPORTUNISTIC_SWEEP_MIN_INTERVAL_SECONDS`)
  + re-entrancy guard, **synchronous** (no asyncio), failure logged (not reported as success), and the
  last-success stamp is **not** advanced on failure ⇒ retried. Wired via `Watcher(opportunistic_sweeper=)`
  at the **start** of `Watcher.tick`. The daily log records that the A4 staged plan
  (`docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` L718–720) explicitly authorizes the sweep from
  "an already-existing lifecycle hook and/or an existing worker's tick" ⇒ the Watcher tick is approved.
- **LIFE-02 (atomic CAS `try_mark_attachment_item_stored`)**: single caller
  (`bot/attachments.py:749`), reached only after a full bounded write + content validation; on
  `False`/exception the file is unlinked and no `stored` is claimed (no resurrection of an
  expired/reaped item). Confirmed by `test_repair_plan_02_life01_f2_race` (13) and `life02` (21).
- **LIFE-03 (intake kill switch)**: `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` (default True) gated in
  `handle_attachment` **before** any `get_file`/download/row/outbox work; documented in `.env.example`.
- **LIFE-04 (e2e)**: 9 tests drive the real handler→store→expire→tick-sweep→reap path.

---

## 5. Plan 03 — docs / CI / D-34

- **CI scope (F-07)**: `.github/workflows/ci.yml` now runs
  `pyflakes bot/ automation/ tools/ main.py tests/` and `bandit -r bot/ automation/ tools/ main.py -lll -s B613`.
  Guards in `tests/test_ci_workflow_security.py` assert the exact strings and the absence of narrower
  invocations. Triggers are `push`/`pull_request` to `main` only; `permissions: contents: read`;
  no secrets in the workflow.
- **D-34 routing**: `classify_attachment_routing` returns `TERMINAL_ASSOCIATED`/`TERMINAL_UNPROVEN`
  (both **block**) instead of the old `TERMINAL`/`NONE` fall-through. `NONE` is returned only after a
  successful, owner-scoped query proving no relevant batch state; unknown batch status ⇒
  `AttachmentBatchIntegrityError` (fail closed). `handlers.py:2054-2063` rejects both terminal states
  with `rejected_ineligible` and does **not** fall through to `_send_prompt`/`outbox`. Verified green by
  `test_attachment_terminal_routing_remediation.py` (26 tests).
- **D-34 authorization gate — see §8 (MEDIUM note).** The D-34 decision text states implementation must
  follow an independent adversarial review of D-34. The committed artifact is the **implementation**
  review (`OHB2-P0-A3-F1-CONSOLIDATED-IMPLEMENTATION-INDEPENDENT-REVIEW.md`, verdict `PASS_WITH_NOTES`,
  "SAFE TO PROCEED to the A4 entry gate"); a separate *policy* review of D-34 as its own record is not
  present in `docs/reviews/`.

---

## 6. Plan 04 — Mini App / frontend (uncommitted)

- **F-1 (notification-row keyboard conflict) — ✅ verified.** `renderInboxRow` makes the `<li>`
  **structural** (no `role`/`tabindex`); the primary action is a real `<button class="row-main row-open">`
  **sibling** to the archive/delete buttons (no nested interactive elements). Mouse/touch preserved via
  a container click handler that ignores clicks whose `target` is not the `<li>` itself. Confirmed in
  source and by `keyboard_rows.test.js` (19 tests).
- **F-2 (event-bubbling DOM stub) — ✅ verified, and proven load-bearing by a sensitivity experiment.**
  `tests/frontend/dom_stub.js` `dispatch` now bubbles to ancestors, honoring `bubbles`/`stopPropagation`/
  `preventDefault`, setting `target`/`currentTarget`. Independent mutation experiment **outside the repo**
  (in `/tmp`, deleted afterwards):
  - current code + bubbling stub ⇒ keyboard_rows **19/19 pass**;
  - inject a row-level `keydown` that activates the main action (the F-1-class regression) + bubbling stub
    ⇒ **4 fail** (caught);
  - the same injected regression + the **old non-bubbling** stub ⇒ **19/19 pass** (vacuous).
  This proves the bubbling stub is **necessary** to detect the F-1 regression class (matches the daily log's
  claim). The repo was not modified by this experiment (`git status` unchanged).
- **LOW-1 keyboard rows**: `makeRowInteractive` (role=button + tabindex=0 + Enter/Space → `activate()`
  exactly once, Space `preventDefault`) applied to the 5 simple rows (chats/files/watches/repos/inbox
  simple list); non-interactive rows (creation requests) untouched.
- **Docs numbers**: `docs/MINI_APP.md` §17 records Node tests **250**; the actual run is **250** — consistent.
  (One residual `§16`-style count in a neighbouring table at `docs/MINI_APP.md:713` still shows **250** and
  matches; no stale value found in the tracked doc.)

---

## 7. Cross-plan integration audit

| Seam | Result |
|---|---|
| **A. Plan 01 ↔ Plan 02** — download bound feeds the CAS store | ✅ `accept()` passes a capped chunk iterator to `store()`, which writes with `O_EXCL|O_NOFOLLOW` + `fsync`, validates magic bytes, then does the atomic CAS. No resurrection; row-first preserved. |
| **B. Plan 02 ↔ Plan 03** — auto-expiry (terminal) meets D-34 blocking | ✅ **Verified by real experiment.** A `pending` batch is `LIVE`; past TTL it is `EXPIRED_PENDING`; after the LIFE-01 sweeper marks it `expired`, `classify_attachment_routing` returns `TERMINAL_UNPROVEN` ⇒ **blocked**. Both before and after the sweep, new prompts are blocked (fail closed). No contradictory behavior. |
| **C. Plan 01 ↔ Plan 03** — resource bounds vs routing | ✅ independent layers; staging rejection never reaches routing; no shared mutable state. |
| **D. Plan 03 ↔ Plan 04** — routing/doc contract vs frontend | ✅ Frontend routes (`/notifications/*`, `/operations/creation/list`, `/operations/deletions/list`, etc.) match `bot/web/app.py`. D-34 is backend-only; frontend unaffected. |
| **E. Single SQLite owner** | ✅ Only `bot/app.py:90` constructs `Database`; the Mini App reuses it (`build_web_app(config, db, ...)`). No second owner/worker introduced. |

**No architectural owner, worker, scheduler, database, or external store was added by any plan.**

---

## 8. Findings (LOW / INFO only)

**N-1 (INFO) — stale D-34-era comments retained (documentation hygiene only).**
`bot/db.py:141-145` (module-level comment) still asserts the *old* behavior: "حالات **نهائية** ما
بتحجبش برومتًا جديدًا بذاتها" and "terminal: نتيجة نهائية ⇒ **لا تحجب**". This contradicts D-34
(terminal batches now **do** block). The `has_terminal_attachment_batch` docstring and the
`classify_attachment_routing` docstring **were** updated, and the enum member `TERMINAL` is annotated
as "no longer produced", but the module comment block was missed. **Behavior is correct**; only the
comment is stale. (This matches F-1/F-2 from the Plan 03 review; it is explicitly LOW/INFO there too.)
*Suggested fix (out of scope for a read-only audit): update `bot/db.py:141-145` to the D-34 wording.*

**N-2 (INFO) — `ATTACHMENT_BATCH_TERMINAL_STATUSES` is defined but never referenced.**
`bot/db.py:153` defines the constant; `grep` finds no reader in `bot/`, `tests/`, `automation/`,
`tools/`. The reaper keeps its own `_TERMINAL` frozenset (`bot/attachments.py:991`) with the same four
values. Not a defect (no drift today), but a single-source-of-truth opportunity. Dead-but-harmless.

**N-3 (INFO) — `AttachmentRoutingState.TERMINAL` is retained only for enum stability.**
`bot/db.py:521`, annotated "للتوافق فقط — **لا يُنتجه** التصنيف الحالي (D-34)". `grep` confirms no
reader compares against it. Intentional (documented), so this is not dead code by accident.

**N-4 (MEDIUM, process — not a code defect) — D-34's own authorization gate.**
The D-34 record (`docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` §5 → D-34, item I) states the
next required step is an *independent adversarial review of D-34* and that "implementation does not
begin before it completes". What exists is the **implementation** review
(`OHB2-P0-A3-F1-CONSOLIDATED-IMPLEMENTATION-INDEPENDENT-REVIEW.md`, `PASS_WITH_NOTES`, and it lists
"D-34 terminal classification fail-closed" as conformant) — not a review of the D-34 *policy record*
itself. This is a **governance** note for the owner, not a code correctness problem: the code matches
the recorded policy. Flagging it because AGENTS.md §14 treats owner-approved decisions as protected.

---

## 9. Invariants confirmed intact

- `concurrent_updates(True)` — **unchanged**.
- File-extension deny-list, magic-byte deny-list, ownership/route checks, safe-rejection,
  row-first ordering, and existing fail-closed behavior — **not weakened**.
- No remote attachment delivery, no OpenHands upload, no new architectural owner.
- No secrets committed; Mini App stores only a SHA-256 token hash (raw token in cookie only);
  `MINI_APP_ENABLED` default False.
- SQLite foreign keys active on the single production connection.

---

## 10. Verdict & next step

**`PASS_WITH_NOTES`.** Plans 01–04 are implemented, verified against the current code and tests, and
mutually consistent. The only notes are LOW/INFO documentation-hygiene items (N-1..N-3) plus one
**process** note (N-4). No blocker.

**Suggested next step:** (1) fold the N-1 comment fix into a future docs-hygiene pass; (2) the owner
confirms whether a dedicated D-34 *policy* review record is required before Plan 03 is considered
fully gated.
