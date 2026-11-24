# OHB2 — DEF-011 F-03 Stale C Correction

**Task ID:** `OHB2-DEF011-F03-STALE-C-CORRECTION`
**Date:** 2026-11-24
**Mode:** documentation + focused test correction only.
**Repository:** `/workspace/project/OpenHandBot`
**Final verdict:** **`READY — AWAITING BATCH INDEPENDENT REVIEW`**

> This is implementation and local verification evidence only. It is not an independent review,
> owner acceptance, or DEF-011 closure.

---

## 1. Actual baseline and final Git state

| Item | Baseline | Final |
|---|---|---|
| Branch | `main` | `main` (unchanged) |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` | same |
| `HEAD` tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` | same |
| Local `origin/main` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` | same |
| Staged | none | none |
| Worktree | dirty with pre-existing WP-03/WP-08/WP-09/A4-F5 work | preserved |

Pre-existing changes were preserved. In particular:

- prior WP-08 changes in `tests/test_doc_code_parity.py` (`APP_SRC` and the Runbook poller
  test) were already present before this task and were not rewritten;
- `.agent/PROGRESS.md`, `.github/workflows/ci.yml`, `bot/attachments.py`, `bot/db.py`,
  `bot/handlers.py`, `bun.lock`, `docs/OPERATIONS_RUNBOOK.md`,
  `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md`, `package.json`, `package-lock.json`, and all
  pre-existing tests/untracked reports were preserved;
- no reset, clean, stash, checkout, force operation, branch switch, or history change was used.

---

## 2. Evidence reviewed

| Artifact | Observation |
|---|---|
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md:292-315` | Historical §9 rows and the 2026-11-21 correction notice. The notice’s lines 312-313 said `DEF-011-C` remained `NOT IMPLEMENTED`. |
| `tests/test_doc_code_parity.py:219-241` | Existing `_correction_notice` helper; it selects the first correction notice. |
| `tests/test_doc_code_parity.py:377-400` | Existing `test_t5_batch04_f01_report_correction_notice`; it protected the historical F-03 row and the first notice but did not assert the current C status. |
| `bot/handlers.py:2400-2406` | `ATTACHMENT_ACCEPTED_TEXT` says the file is stored locally and is not uploaded to OpenHands. |
| `bot/handlers.py:2773-2776` | `ATTACHMENT_ACCEPTED_TEXT` is selected only when `result.outcome is AcceptOutcome.STORED`. |
| `docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md:277-290` | Current later correction records C as implemented and A as not implemented. |
| `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md:33-49` | Current proposal notice records B implemented, A not implemented, C implemented, DEF-011 open. |

The current code confirms the safe assertion: **C is implemented as a local-only acceptance copy,
and that copy is sent only after `STORED`**. The old `NOT IMPLEMENTED` wording is stale.

---

## 3. Documentation correction

Appended a new dated correction to
`docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` after the existing
2026-11-21 notice and before “Unchanged blockers carried forward”:

```text
> **⚠ LATER CORRECTION — 2026-11-24 (append-only; the earlier notice above and all historical rows are unchanged).**
> The earlier `DEF-011-C` statement in the 2026-11-21 notice is **STALE** for the current tree. It
> recorded C as `NOT IMPLEMENTED` at that time; that is no longer a current-state claim.
>
> **Verified current status (2026-11-24):** `DEF-011-C` is **IMPLEMENTED** as the local-only
> acceptance copy. `bot/handlers.py::ATTACHMENT_ACCEPTED_TEXT` states that the file is stored locally
> and is not uploaded to OpenHands, and `handle_attachment` selects that text only when
> `result.outcome is AcceptOutcome.STORED`. `DEF-011-A` (quota reservation ledger) remains **NOT IMPLEMENTED**
> and `DEF-011` remains **OPEN**; this correction does not close `DEF-011`,
> change `OD-04`/`D-12`, or implement A.
>
> This is a new dated correction; the earlier notice and all historical rows above are preserved
> unchanged as historical records.
```

The historical row `DEF-011 C ... OPEN / NOT IMPLEMENTED` and the earlier 2026-11-21 notice remain
intact. The new notice is additive only.

---

## 4. Regression test change

Added a narrow `_latest_correction_notice()` helper and extended
`test_t5_batch04_f01_report_correction_notice` to assert:

- the latest correction contains the date `2026-11-24`;
- `DEF-011-C` is `IMPLEMENTED` in that latest notice;
- `DEF-011-A` remains `NOT IMPLEMENTED`;
- the notice references `ATTACHMENT_ACCEPTED_TEXT` and `STORED`.

The existing first-notice assertions (F-03 pass reference, historical F-03 row, `DEF-011` remains
open/not closed) were kept unchanged. The new assertions target the latest correction only.

---

## 5. Verification

### 5.1 Targeted test

```sh
python -m pytest -q tests/test_doc_code_parity.py::test_t5_batch04_f01_report_correction_notice
```

Result: **1 passed**, exit `0`.

### 5.2 Full parity file

```sh
python -m pytest -q tests/test_doc_code_parity.py
```

Result: **16 passed**, exit `0`.

### 5.3 Relevant F-01 / DEF-011 focused tests

```sh
python -m pytest -q \
  tests/test_def011_fs_offload.py \
  tests/test_def011_a_option_b_limits.py \
  tests/test_def011_review_remediation.py \
  tests/test_f03_status_label_end_to_end.py \
  tests/test_f03_watch_conversation_status_normalization.py
```

Result: **74 passed**, exit `0`.

### 5.4 Relevant C/routing/cleanup tests

```sh
python -m pytest -q \
  tests/test_wp01_attachment_lifecycle.py \
  tests/test_persistent_ready_sticky_routing.py \
  tests/test_telegram_prompt_cleanup_durable.py
```

Result: **71 passed**, exit `0`.

### 5.5 Full Python suite

```sh
python -m pytest -q
```

Result: **3824 passed, 0 failed, 74 warnings**, exit `0`.

The full suite includes pre-existing uncommitted WP-03/WP-08/WP-09/A4-F5 work; those changes are not
part of this task.

### 5.6 Static and diff checks

| Check | Result | Exit |
|---|---|---|
| `pyflakes tests/test_doc_code_parity.py` | no diagnostics | 0 |
| `compileall -q tests/test_doc_code_parity.py` | clean | 0 |
| `git diff --check` | clean | 0 |
| `git diff --stat -- docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md tests/test_doc_code_parity.py` | 2 files, 58 insertions, 0 deletions | 0 |

The test-file diff includes pre-existing WP-08 additions (`APP_SRC` and the Runbook poller test);
this task’s new portion is the `_latest_correction_notice` helper plus the FOLLOW-01 assertions.

---

## 6. Negative control

A disposable copy was created under `/tmp/ohb2-def011-stale-c-negative` from `git archive HEAD`,
then the current report and parity test were copied in. The temp copy’s latest correction was changed
back to `DEF-011-C ... NOT IMPLEMENTED`.

```sh
cd /tmp/ohb2-def011-stale-c-negative
python -m pytest -q tests/test_doc_code_parity.py::test_t5_batch04_f01_report_correction_notice
```

Result: **1 failed**, exit `1`:

```text
AssertionError: إشعار FOLLOW-01 لازم يسجّل DEF-011-C كـ IMPLEMENTED
assert 'NOT IMPLEMENTED' == 'IMPLEMENTED'
```

The real repository was not modified by the negative control.

---

## 7. Scope-boundary confirmation

| Boundary | Confirmation |
|---|---|
| Runtime code | **not modified**; `bot/handlers.py` SHA-256 unchanged at `966d1d5ecac3b67eb02a516b153df87a5fa4fba79e5a51ae978cd27db402e568` |
| `bot/attachments.py` | not modified; SHA-256 `c1c7b2f43ce1364f11fb7ea8c33ee8cd86d8d6166773f4941adf1882f967eb5f` |
| `OD-04` / `D-12` | untouched; no owner decision changed |
| DEF-011-A | not implemented; no quota reservation logic added |
| Mini App / `bot/web/` | untouched |
| Other reports/verdicts | untouched |
| CI/dependencies/schema | untouched |
| Commit/push/PR/merge/deploy/release/Autopush | none |
| Independent review | not performed |
| Owner acceptance | not granted |

---

## 8. Changed files and hashes

| File | Change | Final SHA-256 |
|---|---|---|
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | Appended dated 2026-11-24 correction | `cbeb85fd8602d2296e84ce2cdce59622a59b1d15a5334868dbc95cd76444da81` |
| `tests/test_doc_code_parity.py` | Added latest-notice helper and FOLLOW-01 assertions | `2f65ea835b87470658edb7296e51b661bab096946eb98035680e414ee5130cef` |
| `docs/reviews/OHB2-DEF011-F03-STALE-C-CORRECTION-REPORT-20261124.md` | This report | see §9 |

---

## 9. Limitations and report integrity

- **Not run:** GitHub Actions/CI, Node/frontend tests, live Telegram/OpenHands/Enzonic calls.
- **Not performed:** independent review, owner acceptance, commit, push, PR, merge, deployment,
  release, or Autopush activation.
- The correction documents current behavior only; it does not close F-03 or DEF-011.
- The F-03 closure evidence gap remains for a later independent review.

**Report body SHA-256 (excluding this footer):** `fc97deca826bedc794f858fd4a9884ca54987f8cf656caf38906792e42d404dc`
