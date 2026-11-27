# OHB2-REMOVE-EXPORT-BUTTON-AND-EXPLANATORY-TEXT — Independent Review

**Task ID:** `OHB2-REMOVE-EXPORT-BUTTON-AND-EXPLANATORY-TEXT-INDEPENDENT-REVIEW`
**Review mode:** READ-ONLY independent review
**Review date:** 2026-11-27
**Reviewer workspace:** `/workspace/project/OpenHandBot`
**Reviewer runtime:** Python 3.13.15, Node v24.22.2
**Verdict:** `PASS_WITH_NOTES`
**Parent recommendation:** `ACCEPTABLE WITH FOLLOW-UP NOTES`

## 1. Scope

This review independently checked whether commit `bb244f2` completely removes the dedicated
chat-export button/feature and the explanatory paragraph shown when a conversation has a reply,
while preserving manual-copy, Mini App one-click copy, and unrelated features.

The review was read-only. No application source, tests, configuration, documentation, migrations,
or existing reports were modified. Exactly one new report was created at the path required by the
task. No Git staging, commit, push, fetch, pull, merge, rebase, cherry-pick, reset, clean, branch,
worktree, PR, release, or deployment action was performed. No production Telegram or OpenHands API
was called.

## 2. Repository Identity and Verified Baseline

Commands used:

```text
pwd
git rev-parse --show-toplevel
git remote -v
git branch --show-current
git rev-parse HEAD
git rev-parse HEAD^{tree}
git status --porcelain=v1 -uall
git diff --cached --name-status
git branch -a --no-color
git log --oneline --decorate -8
```

Verified state:

| Item | Verified value |
| --- | --- |
| Repository root | `/workspace/project/OpenHandBot` |
| Remote | `origin https://github.com/TM-AEM/OpenHandBot.git` |
| Current branch | `main` |
| HEAD | `bb244f22476971212398d684501550a0d2658678` |
| HEAD tree | `66b8b95f0f56973646f431b20e70e83166462c2b` |
| Working tree | Clean (`git status --porcelain` empty) |
| Staged changes | None |
| Modified/deleted/untracked files | None at baseline |
| Relevant ignored files | `.openhands/`, `.pytest_cache/`, `.venv/`, `__pycache__/`, `dist/`, `node_modules/` |

Local branches included `main`, `agent/r6-review-delivery`, and
`openhands-workspace-11liARbsA7OSSoFJOM2RDr`. `origin/main` pointed at `12bd852`, so the two
reviewed commits existed only locally at the start of the review.

## 3. Commit Ancestry and Diff Reviewed

Both reported commits exist and are ancestors of current `main`:

```text
46622dacbd626e141d54dd6b8e006f75a279af6c  parent 12bd85291c02fcadb9203538f1b67fbd7498070a
bb244f22476971212398d684501550a0d2658678  parent 46622dacbd626e141d54dd6b8e006f75a279af6c
```

`git merge-base --is-ancestor 46622da HEAD` and
`git merge-base --is-ancestor bb244f2 HEAD` both returned exit code 0.

### 3.1 R-01/R-02 commit: `46622da`

Tree: `f3c0d38f8dc1f202e4d8833f2d06d2c183d36fa9`.

Files: `.agent/PROGRESS.md`, `bot/attachments.py`, `bot/db.py`, `bot/handlers.py`,
`tests/test_remove_chat_forwarding_r01_r02_remediation.py`, and three review documents under
`docs/reviews/`.

This commit is separate from the export removal. It adds pending-selection guards and the
clear-to-None routing-CAS response. The export-removal commit does not touch `bot/db.py` or
`bot/attachments.py`; R-01/R-02 markers remain present in current HEAD.

### 3.2 Export-removal commit: `bb244f2`

Tree: `66b8b95f0f56973646f431b20e70e83166462c2b`.
Range reviewed: `git diff 46622da bb244f2`.

Diff size: 40 files, 354 insertions, 1678 deletions.

Production files:

- `bot/app.py`, `bot/features.py`, `bot/files.py`, `bot/handlers.py`, `bot/keyboards.py`,
  `bot/openhands_client.py`
- `bot/web/app.py`, `bot/web/download.py`, `bot/web/services.py`
- `bot/web/static/app.js`, `bot/web/static/attachments.js`, `bot/web/static/index.html`
- Deleted: `bot/web/static/export.js`

Test files:

- Deleted: `tests/frontend/export.test.js`, `tests/test_a2_export_auth.py`,
  `tests/test_miniapp_export_reply.py`
- Renamed: `tests/frontend/export_copy_ui.test.js` → `tests/frontend/copy_ui.test.js`
- Added: `tests/test_export_removal.py`, `tests/test_miniapp_full_reply.py`
- Updated: `tests/_mutation_harness.py`, `tests/frontend/dom_stub.js`,
  `tests/test_audit_remediation_f01_f07.py`, `tests/test_b06_file_routing.py`,
  `tests/test_bot_file_browser.py`, `tests/test_f1_tombstone_enforcement.py`,
  `tests/test_features_hidden.py`, `tests/test_files_negative.py`, `tests/test_handlers.py`,
  `tests/test_keyboards.py`, `tests/test_miniapp_files.py`, `tests/test_n1005_operational.py`,
  `tests/test_openhands_client.py`, `tests/test_real_http_file_download.py`,
  `tests/test_real_http_miniapp_download.py`,
  `tests/test_sw04_sw05_authz_upstream_and_delivery.py`,
  `tests/test_wp03_handler_outcome_and_send_guards.py`

Documentation: `.agent/PROGRESS.md`, `README.md`, `docs/API_NOTES.md`, `docs/MINI_APP.md`.

`git diff --check 46622da bb244f2` returned exit code 0. The working-tree `git diff --check`
returned exit code 0. `git diff --check 12bd852 46622da` reported trailing whitespace only in
R-01/R-02 review documents; that is outside the export-removal commit and is listed as an
informational note below.

## 4. Export-Removal Findings by Layer

### 4.1 Telegram bot

Verified absent:

- `EXPORT` label constant: `bot/keyboards.py` has no `EXPORT`; current labels include
  `COPY_REPLY`, `COPY_MINI_APP`, `FULL_REPLY`, and `TXT_REPLY` at lines 45-49.
- Export keyboard row: `bot/keyboards.py` `conversation_actions()` lines 140-166 no longer adds
  any `export:<id>` button.
- Export callback registration: `bot/app.py` lines 143-181 register `open`, `copy`, `full`,
  `review`, `txt`, `status`, `reply`, `newchat`, `norepo`, delete, repository, files, cost, watch,
  and other callbacks; no `^export:` pattern is present.
- Export handler: `bot/handlers.py` has no `export_conversation` function. `git grep` for
  `export_conversation` in current `bot/` returns no production match.
- Export client method/constant: `bot/openhands_client.py` has no
  `OpenHandsClient.export_conversation` and no `MAX_EXPORT_BYTES`.
- User-facing export action/message: current `bot/` grep for `export` returns only JavaScript
  `module.exports` wrappers, Python module-export comments, and the secret-redaction regex. No
  user-facing export action remains.

Independent runtime probes:

```text
handlers.export_conversation False
keyboards.EXPORT False
client.export_conversation False
client.MAX_EXPORT_BYTES False
service.conversation_export False
service.export_filename False
service.EXPORT_CONTENT_TYPE False
web_app._attachment False
```

Registered callback patterns from a real `build_application()`:

```text
export patterns: []
copy patterns: ['^copy:']
txt patterns: ['^txt:']
```

An old `export:<id>` callback therefore has no registered handler. This is stronger than merely
hiding the button.

### 4.2 Mini App

Verified absent:

- Route `/api/v1/conversations/{conversation_id}/export`: absent from the Starlette route table.
  Current conversation routes are:
  `/conversations`, `/conversations/{id}`, `/status`, `/cost`, `/reply`, `/attachments`,
  `/attachments/{item_id}/download`, `/files`, `/file`, `/prompt`, `/repository`, and `/watch`.
- `MiniAppService.conversation_export`, `export_filename`, and `EXPORT_CONTENT_TYPE`: absent.
- `_attachment()` export response helper in `bot/web/app.py`: absent.
- `bot/web/static/export.js`: absent from the filesystem.
- `export.js` script tag and `RecovoExport` reference: absent from `index.html` and `app.js`.
- `app.js` cache version was bumped from `v=8` to `v=9`; `index.html` lists the remaining
  `jobs.js`, `ops.js`, `inbox.js`, `files.js`, `cost.js`, `copy.js`, `attachments.js`, and
  `app.js` scripts.

Independent HTTP probes with the existing Mini App test harness:

```text
unauthenticated export: 404 {"error":"not_found","message":"المسار مش موجود."}
authenticated export:   404 {"error":"not_found","message":"المسار مش موجود."}
/mini/export.js:        200 text/html (SPA index fallback; no export code)
```

The `/mini/export.js` 200 response is the existing SPA fallback for any missing static path
(`bot/web/app.py:1158-1163`), not a surviving export bundle. It is recorded as informational only.

### 4.3 Backend and shared components

The following shared items were intentionally retained and are still used by non-export features:

- `ResponseTooLargeError` remains in `bot/errors.py` and is used by bounded file reads
  (`bot/files.py`, `bot/openhands_client.py`, and file tests). It is not export-only.
- `_HEADER_SAFE_NAME` remains in `bot/web/app.py` and is used by authenticated attachment
  downloads at lines 777-780.
- `_HEADER_SAFE_NAME` and filename sanitization remain in `bot/web/download.py` for attachment
  downloads.
- `send_text_document` remains for the separate `.txt` reply control.

No remaining reachable dedicated zip-export path was found in bot, Mini App, client, services, or
frontend code.

## 5. Explanatory Text Search Evidence

The removed paragraph existed in `46622da:bot/handlers.py` in `_open_conversation_view` and was
removed by `bb244f2`:

```text
if reply is not None:
    text += (
        "\n\n📋 زر «عرض للنسخ اليدوي» بيبعتلك الرد جوه code block عشان تنسخه يدويًا "
        "(بوتات تيليجرام ما بتكتبش في الحافظة تلقائيًا) — أو انسخ بضغطة من الـ Mini App "
        "أو نزّله كـ «ملف النص» (.txt)."
    )
```

Current `_open_conversation_view` has no `if reply is not None: text += ...` block. The exact
fragments were searched in active bot, tests, README, `docs/API_NOTES.md`, and `docs/MINI_APP.md`:

- `بيبعتلك الرد` — only `tests/test_export_removal.py` (guard assertion).
- `code block` — handler/sender docstrings describing the manual-copy mechanism, plus the guard
  test; no explanatory paragraph.
- `عرض للنسخ اليدوي` — keyboard label and docs describing the preserved manual-copy button.
- `نزّله` — only an unrelated database comment.
- `بوتات تيليجرام` — no active match.

The regression test
`test_open_with_reply_has_manual_copy_without_explanatory_text` passed and asserts that the old
paragraph fragments are absent from the opened-conversation message while the manual-copy button
and Mini App web button remain.

Historical review/audit files under `docs/reviews/`, `docs/audits/`, `docs/decisions/`,
`docs/design/`, and `docs/proposals/` still mention export. They were treated as historical
records, not active user-facing functionality.

## 6. Manual-Copy Preservation

Current bot code retains:

- `bot/keyboards.py:45` `COPY_REPLY = "📄 عرض للنسخ اليدوي"`.
- `bot/keyboards.py:143-147` adds the `copy:<id>` button whenever a reply exists.
- `bot/app.py:144` registers `^copy:`.
- `bot/handlers.py:1351` `copy_reply` performs authorization, reads the last exchange, and sends
  the reply through `send_copyable`.
- `bot/sender.py:42` `send_copyable` sends the text inside `<pre>` so Telegram's code block is
  copyable.

Independent tests:

```text
pytest -q tests/test_handlers.py -k 'copy or open_with_reply' -v
9 passed, 81 deselected
```

This includes the manual-copy behavior, no-reply handling, non-owner rejection, API-error
handling, long-reply document fallback, and the open-with-reply explanatory-text assertion.

## 7. Mini App One-Click Copy Preservation

Current Mini App code retains:

- `bot/web/static/copy.js` with `RecovoCopy.copyText()` and `feedback()`, including Clipboard API
  and `execCommand` fallback with no false-success path.
- `bot/web/static/app.js:147-148` loads `RecovoCopy`; lines 963-982 render the
  “📋 نسخ الرد الكامل” button and call `COPY.copyText(full, ...)`.
- `bot/web/app.py:338-341` keeps `GET /api/v1/conversations/{conversation_id}/reply`.
- `bot/web/services.py:688` keeps `get_full_reply()`, returning
  `{"conversation_id", "reply", "reply_truncated"}`.

Independent tests:

```text
node --test tests/frontend/copy_ui.test.js
7 pass, 0 fail

pytest -q tests/test_miniapp_full_reply.py
8 pass
```

The Mini App copy path does not depend on the deleted `export.js`, `RecovoExport`, export route,
export service, or export filename helper.

## 8. Other-Feature Regression Review

The focused regression set covered files, cost, followups, deletion, notifications, attachments,
pending selection, and ordinary conversation behavior:

```text
tests/test_export_removal.py
tests/test_miniapp_full_reply.py
tests/test_reply_txt_file_button.py
tests/test_handlers.py
tests/test_keyboards.py
tests/test_features_hidden.py
tests/test_bot_file_browser.py
tests/test_b06_file_routing.py
tests/test_f1_tombstone_enforcement.py
tests/test_files_negative.py
tests/test_openhands_client.py
tests/test_remove_chat_forwarding_r01_r02_remediation.py
tests/test_miniapp_files.py
tests/test_miniapp_cost.py
tests/test_miniapp_inbox_manage.py
tests/test_miniapp_integration.py
tests/test_miniapp_http_journeys.py
tests/test_sw04_sw05_authz_upstream_and_delivery.py
tests/test_wp03_handler_outcome_and_send_guards.py
tests/test_real_http_file_download.py
tests/test_real_http_miniapp_download.py
```

Result: 634 passed, 0 failed in 55.25s.

R-01/R-02 pending-selection handling is preserved in current code (`AttachmentSelectionPending`,
`_reject_pending_selection`, `selection_cleared`, and related tests). The export-removal commit
does not touch `bot/db.py` or `bot/attachments.py`.

## 9. Independently Executed Tests and Results

All commands were run in `/workspace/project/OpenHandBot` using the repository virtual environment.

| Command | Result |
| --- | --- |
| `pytest -q tests/test_export_removal.py tests/test_miniapp_full_reply.py -v` | 13 passed, 2 warnings, exit 0 |
| `pytest -q tests/test_handlers.py -k 'copy or open_with_reply' -v` | 9 passed, 81 deselected, exit 0 |
| `pytest -q tests/test_reply_txt_file_button.py` | 35 passed, exit 0 |
| Focused 21-file preservation run | 634 passed, 0 failed, 55.25s, exit 0 |
| Full `pytest -q` | 4343 passed, 0 failed, 74 warnings, 341.22s, exit 0 |
| `node --test tests/frontend/*.test.js` | 272 pass, 0 fail, 0 cancelled, exit 0 |
| `node --test tests/frontend/copy_ui.test.js` | 7 pass, 0 fail, exit 0 |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit 0 |
| `python -m bandit -q -r bot/ automation/ tools/ main.py -lll -s B613` | exit 0 |
| `python -m pip_audit -r requirements-dev.txt` | exit 0, “No known vulnerabilities found” |
| `npm run lint` (`tsc --noEmit`) | exit 0 |
| `git diff --check` (working tree) | exit 0 |
| `git diff --check 46622da bb244f2` | exit 0 |

The full-suite warnings are the existing Starlette/httpx, PTB deprecation, and anyio alias
warnings; no new failures were observed.

Python 3.11 CI was not verified. The workflow `.github/workflows/ci.yml` defines Python 3.11 and
3.13 jobs, but only Python 3.13.15 is installed locally, `python3.11` is unavailable, `gh` is not
authenticated, and the reviewed commits are local-only. Triggering CI would require a remote write
or push, which this review did not perform. Live Telegram and OpenHands integrations were not
tested.

## 10. Findings

### M-01 — `.txt` reply-download control remains active; scope needs owner confirmation

**Severity:** MEDIUM (scope ambiguity; would become HIGH if `.txt` is confirmed in scope)
**Files/lines:** `bot/keyboards.py:48-50`, `bot/keyboards.py:148-153`,
`bot/app.py:148-149`, `bot/handlers.py:1549`, `bot/sender.py` `send_text_document`,
`docs/MINI_APP.md:544-545`.
**Evidence:** The bot still renders a “ملف النص” button with callback `txt:<id>`, registers
`^txt:`, and `send_reply_txt` sends the full reply as a `.txt` document. `docs/MINI_APP.md` still
documents this control. The dedicated `export:` button, `export_conversation`, client method,
Mini App export route, service, and `export.js` are gone.
**Actual impact:** If “export/download removal” includes the `.txt` reply document, one
user-facing reply-download path remains reachable. If `.txt` is intentionally a copy-related
feature separate from chat zip export, the implementation is consistent and no functional defect
exists.
**Introduced by export removal?** No; it was preserved intentionally. The export-removal commit
message explicitly says `.txt` remains unchanged.
**Required remediation:** Owner must confirm the scope. If `.txt` is in scope, remove
`TXT_REPLY`, the `txt:` keyboard row, `^txt:` registration, `send_reply_txt`, related tests, and
the `.txt` documentation; otherwise record it as an explicitly preserved copy feature.

### L-01 — Stale comment says deferred-feature code/data is never deleted

**Severity:** LOW
**Files/lines:** `bot/app.py:160-162`.
**Evidence:** The comment says deferred features’ “code and data are still present (we do not
delete anything)” after the export implementation was deleted. The comment’s list now names only
files/cost/followups, but the absolute wording is no longer true for export.
**Actual impact:** Documentation/comment drift only; no runtime effect.
**Introduced by export removal?** Yes, the comment was not narrowed when export code was deleted.
**Required remediation:** Scope the sentence to the remaining deferred features or update it to
state that export was removed.

### L-02 — Permanent guard test does not assert route/callback registration

**Severity:** LOW
**Files/lines:** `tests/test_export_removal.py:17-56`.
**Evidence:** The guard checks absent symbols, keyboard labels, feature flag, explanatory text,
and frontend files, but it does not assert that the Mini App route table has no `/export` route or
that the bot app registers no `^export:` callback. Independent probes did verify both.
**Actual impact:** A future regression could re-add a route or callback while this guard test
still passes. The current code is correct.
**Introduced by export removal?** The test gap is new with the guard test.
**Required remediation:** Add a route-table assertion and a registered-pattern assertion to the
permanent guard test.

### I-01 — Historical docs still mention export

**Severity:** INFORMATIONAL
**Files:** `docs/PLAN2_BASELINE.md`, `docs/design/OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-SPEC.md`,
`docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md`, and review/audit records.
**Evidence:** These documents describe the old export feature or the old baseline. They are
historical/design/proposal records, not current user-facing surfaces or current operational docs.
**Impact:** None for runtime. Current `README.md`, `docs/API_NOTES.md`, and `docs/MINI_APP.md` no
longer mention export.
**Introduced by export removal?** No; these are historical records.
**Required remediation:** None required for this task; optionally mark them as superseded if the
owner wants a clean documentation index.

### I-02 — Missing `/mini/export.js` falls back to the SPA index with HTTP 200

**Severity:** INFORMATIONAL
**Files/lines:** `bot/web/app.py:1158-1163`.
**Evidence:** A request for `/mini/export.js` returns `200 text/html` containing the Mini App
index because the existing SPA fallback serves the index for missing static paths. The response
contains no export JavaScript. The same behavior applies to any missing `/mini/*` asset.
**Impact:** A stale browser tab requesting the old script would receive HTML instead of JavaScript
and fail with a MIME error; it cannot execute export code. No export functionality is reachable.
**Introduced by export removal?** No; the SPA fallback predates this change.
**Required remediation:** None for this task.

### I-03 — R-01/R-02 review documents contain trailing whitespace

**Severity:** INFORMATIONAL
**Files:** `docs/reviews/OHB2-REMOVE-CHAT-FORWARDING-AND-CANCEL-INDEPENDENT-REVIEW-20261127.md`,
`docs/reviews/OHB2-REMOVE-CHAT-FORWARDING-R01-R02-INDEPENDENT-REVIEW-20261127.md`,
`docs/reviews/OHB2-REMOVE-CHAT-FORWARDING-R01-R02-REMEDIATION-REPORT-20261127.md`.
**Evidence:** `git diff --check 12bd852 46622da` reports trailing whitespace on metadata/header
lines. The export-removal range and working tree are clean.
**Impact:** None on runtime; cosmetic review-artifact issue.
**Introduced by export removal?** No; it belongs to the separate R-01/R-02 commit.
**Required remediation:** Optional cleanup in a separate documentation change.

## 11. Verdict and Parent Recommendation

**Verdict:** `PASS_WITH_NOTES`

The dedicated chat zip-export feature is removed across the Telegram bot, Mini App, client,
services, frontend bundle, and tests. The explanatory paragraph is absent from active
user-facing output. Manual-copy and Mini App one-click copy are intact, and the independent
focused/full tests pass.

**Parent recommendation:** `ACCEPTABLE WITH FOLLOW-UP NOTES`

The owner should confirm whether the separate `.txt` reply-download control is in scope. If it is,
M-01 is blocking and the verdict should change to `FAIL` until it is removed. If `.txt` is an
intentionally preserved copy-related feature, M-01 is a documentation/scope note only.

## 12. Unverified Areas and Limitations

- Python 3.11 CI was not verified; only Python 3.13.15 was available locally. CI matrix is
  configured for 3.11 and 3.13, but the reviewed commits are local-only and no remote write was
  allowed.
- No live Telegram, Telegram WebView, or OpenHands production API calls were made.
- No real browser or Telegram WebView test was run; Mini App frontend behavior was verified with
  the repository’s Node DOM stub and the Starlette test harness.
- No Python 3.11 runtime, Android/Termux runtime, or deployment environment was exercised.
- The `.txt` scope ambiguity in M-01 was not resolved by repository instructions; the owner must
  decide it.

## 13. Final Git State

After the independent review and report creation:

- Current branch: `main`
- HEAD: `bb244f22476971212398d684501550a0d2658678`
- HEAD tree: `66b8b95f0f56973646f431b20e70e83166462c2b`
- Tracked source/test/config/doc changes: none
- Staged changes: none
- Untracked files: exactly one new review report at
  `docs/reviews/OHB2-REMOVE-EXPORT-BUTTON-AND-EXPLANATORY-TEXT-INDEPENDENT-REVIEW-20261127.md`
- No commit, push, pull, fetch, merge, rebase, cherry-pick, reset, clean, branch, worktree, PR,
  release, or deployment action was performed.

## 14. Read-Only Confirmation

No application source, test, configuration, migration, or existing documentation/report file was
modified. The only new file is the review report above. No Git publication or deployment action
occurred. No production secret was accessed and no live integration was called.
