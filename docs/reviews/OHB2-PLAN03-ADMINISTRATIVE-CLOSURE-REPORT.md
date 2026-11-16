# OHB2 Plan 03 — ADMINISTRATIVE CLOSURE REPORT (Workspace Navigation & Individual File Download)

> Prepared by an AI agent (OpenHands) on behalf of the owner. **Closure-only task** — the only
> repository writes are documentation (this report + the two status labels in `docs/MINI_APP.md`).
> **No functional source code change.** No schema/API/dependency/config/architecture change, no new
> endpoint, no GitHub Token use, no production call, no commit/push/PR/merge/release/deploy/Autopush
> change. The SSRF remediation patch and the prior-session WS-01 implementation are preserved
> byte-for-byte (see §9).

- **Task ID:** OHB2-PLAN03-FINAL-ADMINISTRATIVE-CLOSURE-01
- **Date (UTC):** 2026-11-16
- **Repository:** `TM-AEM/OpenHandBot` · **Workspace:** `/workspace/project/OpenHandBot`
- **Plan:** OHB2-PLAN-13-WORKSPACE-FILE-BROWSER (a.k.a. "Plan 03")
- **FINAL VERDICT:** **PLAN 03 — ADMINISTRATIVELY CLOSED WITH DOCUMENTED PROVIDER BLOCKER**

---

## 1. Final Plan 03 administrative status

| Workstream | Status | Notes |
| --- | --- | --- |
| WS-01 — hierarchical workspace folder navigation | **DONE** | Implemented, tested, documented (this is **not** a claim that the whole Plan is fully implemented). |
| WS-02 — individual workspace file download | **`BLOCKED_BY_PROVIDER_CAPABILITY`** | Not implemented, on purpose; no invented endpoint, no shell/write substitute. |
| **Plan 03 overall** | **CLOSED WITH DOCUMENTED PROVIDER BLOCKER** | No further Plan 03 coding task is open. |

This is an **administrative closure**, not a claim that both features are fully implemented. The WS-02
blocker is **not hidden**.

## 2. WS-01 closure evidence (verified against the live workspace, read-only)

The existing implementation and documentation support every required WS-01 property:

| Required property | Evidence |
| --- | --- |
| Hierarchical folder navigation | `bot/web/static/files.js::buildTree` + `entryRows` build a tree from the server's flat relative-path list; `app.js::renderFilesSection` renders folder rows (trailing `/`) that descend. Tests: `tests/frontend/files.test.js`, `tests/frontend/files_watch.test.js`. |
| Parent/root navigation and breadcrumbs | `files.js::breadcrumbs` (root label «الرئيسية») + `parentPath`; `app.js` renders clickable `.crumb` buttons + the «⬆️ لأعلى» button (hidden at root). |
| Per-conversation navigation state | `files.js::readDir`/`writeDir` with key `ohb2.files.dir.<conversation_id>` in `localStorage`; restore is fail-safe (missing folder → root). |
| Correct full relative paths when opening files | `files.js::childPath(dir, name)`; file click calls `loadPreview(full)` → `GET /api/v1/conversations/{id}/file?path=<full relative path>`. |
| Fail-closed handling of invalid/nonexistent directories | `files.js::buildTree` validates the **whole** path before any insert (a bad path leaves no partial empty folder); `safeDir` accepts only a folder that exists in the tree. Tests: `tests/frontend/files.test.js` (navigation unit tests). |
| Arabic RTL conventions | `<html lang="ar" dir="rtl">` (`bot/web/static/index.html`); Arabic UI strings retained; no LTR regression. |

Backend contract is unchanged: `GET /api/v1/conversations/{id}/files` still returns the flat
relative-path list (`bot/web/services.py::FileService.list_files`, allowlist `is_safe_workspace_path`
+ conversation ownership). The hierarchy is built **client-side** — no new route, no extra read.

## 3. WS-02 external blocker and security rationale

WS-02 status stays exactly **`BLOCKED_BY_PROVIDER_CAPABILITY`**. It is **not** implemented, completed,
or delivered. The closure record states all of the following (sources verified at implementation time
and recorded in `docs/MINI_APP.md` §13و):

1. **The Cloud V1 text-reading endpoint is not a general binary file-download endpoint.**
   `GET /api/v1/app-conversations/{id}/file` ("Read Conversation File") returns `application/json`
   string content, bounded (256 KiB) and rejecting binary/non-UTF-8 — text preview, not file bytes.
   (Cloud V1 spec `https://app.all-hands.dev/openapi.json`, v1.92.0.)
2. **The trajectory ZIP export is not an individual workspace-file download operation.**
   `GET /api/v1/app-conversations/{id}/download` ("Export Conversation") exports the conversation
   trajectory as a ZIP — not a workspace file.
3. **The Agent Server download endpoint requires a broad session-level API key and does not establish
   the required workspace-root confinement.** `GET /api/file/download/{path}` (Agent Server,
   `https://docs.openhands.dev/openapi/agent-sdk.json`, v0.1.0) requires the `X-Session-API-Key`
   header — a **server-wide, full-privilege** key (the same key reaches
   `POST /api/bash/execute_bash_command` and `/api/conversations/{id}/secrets`), and the route is
   **not** confined to the workspace root (any absolute path). This is documented risk **B1** in
   `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md`.
4. **Using that endpoint would violate the project's security requirements** (least privilege +
   workspace confinement). The bot also does **not** store `session_api_key` (documented policy).
5. **No shell, write, upload, or invented endpoint may be used as a substitute.** Consequently there
   is **no local byte-download route**, and any download-like path returns **404**. Regression guard:
   `tests/test_miniapp_files.py::test_no_workspace_file_download_route_exists` asserts 404 for
   `.../file/download`, `.../files/download`, and `.../download`.

## 4. Documentation files changed (this closure task)

Exactly **two** documentation writes were necessary; all other Plan 03 records already existed and
were accurate:

1. `docs/MINI_APP.md` — §13و status label set to `BLOCKED_BY_PROVIDER_CAPABILITY` (was
   `BLOCKED_BY_PROVIDER`; same taxonomy, closure-accurate wording) + a pointer to this report; §15
   known-limitations bullet updated to the same label. **Status text only** — no behavior change.
2. `docs/reviews/OHB2-PLAN03-ADMINISTRATIVE-CLOSURE-REPORT.md` — this report (new).

`.agent/PROGRESS.md` already records the Plan 03 execution session and its outcome (WS-01 DONE /
WS-02 blocked); it was **not** modified merely to create a diff.

## 5. Exact final diff file count and names

The working tree contains **11 modified files** (no untracked non-ignored files). The previous
implementation report claimed "11 changed files" but enumerated only 10 — it **omitted
`.agent/PROGRESS.md`**. The complete, actual list is:

```
.agent/PROGRESS.md
bot/web/static/app.js
bot/web/static/files.js
bot/web/static/index.html
bot/web/static/styles.css
docs/MINI_APP.md
tests/frontend/dom_stub.js
tests/frontend/files.test.js
tests/frontend/files_watch.test.js
tests/frontend/keyboard_rows.test.js
tests/test_miniapp_files.py
```

Verified with `git diff --name-only | wc -l` → **11**. This closure task adds one new report file
(`docs/reviews/OHB2-PLAN03-ADMINISTRATIVE-CLOSURE-REPORT.md`), which is **untracked** and is the only
addition. **No functional source file is modified** (see §8).

## 6. Resolved / unresolved discrepancies from the previous report

1. **Changed-file count (11 vs 10 enumerated).** **RESOLVED** — the count is **11**; the missing
   entry was `.agent/PROGRESS.md`. Full list in §5.
2. **280 Node tests vs 148 focused tests — overlapping?** **RESOLVED — they are disjoint toolchains,
   not the same set.** The **280** figure is `node --test tests/frontend/*.test.js` (JavaScript DOM
   tests). The **148** figure is a **pytest** subset (`tests/test_miniapp_files.py`,
   `tests/test_files_service.py`, `tests/test_files_bounded.py`, `tests/test_files_negative.py`).
   They must **not** be added together as one total. Both are subsets of the two full suites below.
3. **The single pytest failure.** **RESOLVED (root cause identified and reproduced).**
   `tests/test_deploy_manifest.py::test_documented_manifest_is_import_sufficient` runs
   `python -c "import main"` in an isolated copy with an overridden environment
   (`HOME=str(tmp_path)`, `PATH=/usr/bin:/bin`). In this container `python-telegram-bot` 22.8 is
   installed **only in user-site** (`/home/openhands/.local/lib/python3.13/site-packages`). Overriding
   `HOME` makes user-site unreachable, so the subprocess raises `ModuleNotFoundError: No module named
   'telegram'`. **Reproduced both ways:** with `HOME=<tmp>` → exit 1 (`ModuleNotFoundError: telegram`);
   with `HOME=<real user home>` on the identical isolated copy → exit 0. This failure is **pre-existing
   and independent of Plan 03** — none of the files the test reads (`main.py`, `bot/**`, `requirements.txt`,
   `docs/DEPLOY_KATABUMP.md`) are touched by this Plan (Plan 03 changes only static front-end assets,
   tests, and docs).
4. **Rerun the affected test in an existing isolated environment.** **NOT POSSIBLE / NOT DONE.** No
   isolated environment with system-level `telegram` exists (no `/tmp/ohb2_venv`, no `venv`/`.venv`,
   no `pyvenv.cfg`). Per the task rules, dependencies were **not** installed and dependency manifests
   were **not** modified merely to obtain a green result. The test result therefore stays **FAIL** in
   this environment; it was **not** changed to PASS.
5. **Telegram Android/WebView vs Chromium.** **RESOLVED / kept honest.** Real **Telegram Android/WebView
   verification remains UNVERIFIED** (no real Telegram client available; outside CI). A **Chromium
   (headless) DOM run was performed** in the prior session as a WebView-equivalent engine check only —
   it is **not** a real Telegram client and does not change the UNVERIFIED status (see §7).

## 7. Actual verification results (exact commands)

All commands run at `/workspace/project/OpenHandBot` on 2026-11-16.

| Command | Result |
| --- | --- |
| `python -m pytest -q` | **1 failed, 3117 passed** in 162.39s — the single failure is the pre-existing, unrelated `test_deploy_manifest::test_documented_manifest_is_import_sufficient` (see §6.3). |
| `node --test tests/frontend/*.test.js` | **tests 280 / pass 280 / fail 0**. |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **0 issues** (exit 0). |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High: 0**. |
| `python -m pytest tests/test_miniapp_files.py tests/test_files_service.py tests/test_files_bounded.py tests/test_files_negative.py -q` | **148 passed** (a **pytest** subset — disjoint from the 280 Node tests). |

**Android / Telegram verification limitation:** **UNVERIFIED** — real Telegram Android / WebView
behavior was **not** tested (no real Telegram client in this environment). The prior-session Chromium
headless run exercised the same `index.html`/`styles.css`/`files.js`/`app.js` in a Chromium engine and
verified the full nav + preview + per-chat persistence flow, but Chromium is **not** the Telegram
client, so the WebView-only status stays **UNVERIFIED**. The full pytest suite was rerun (result above);
it is **not** claimed green.

## 8. Preservation evidence (prior work + SSRF remediation)

- **HEAD:** `0d644e8` (branch `openhands-workspace-kPgFEhoMiLQANCdCk2NGD`, also `origin/main`).
- The SSRF/local-file-access remediation and the prior-session WS-01 work live in committed backend
  files (`bot/handlers.py`, `bot/attachments.py`, `bot/files.py`, `bot/web/*.py`). **None of those
  files appear in the working-tree diff** — confirmed by
  `git diff --name-only | grep -E "bot/(handlers|attachments|files)\.py|bot/web/(app|services|download)\.py"`
  → **no match**. So the SSRF patch and the backend implementation are preserved byte-for-byte.
- The only Plan 03 changes are static front-end assets (`bot/web/static/*`), tests, and docs. This
  closure task changed **only documentation**.
- No `git reset`/`git clean`/force operation, no broad staging, no `git add .`/`-A`.

## 9. Confirmation: no implementation, publication, or deployment

- **No functional code change** in this closure task (documentation only).
- **No schema/API/dependency/config/architecture change**, no new endpoint, no provider workaround.
- **No GitHub Token inspection/use; no production credentials/API calls.**
- **No** branch creation, commit, push, PR, merge, release, deployment, or workflow operation.
- `MINI_APP_ENABLED` remains **off**; Autopush state unchanged.

## 10. Explicit closure statement

- **No further WS-01 implementation work is currently required.**
- **WS-02 is externally blocked and is not authorized for workaround implementation.**
- **No additional Plan 03 coding task is open.**
- **Reopening WS-02 requires new provider-capability evidence AND separate explicit authorization.**
- **The documented blocker does not authorize broadening Agent Server credentials or weakening
  workspace isolation.**

**Condition for reopening WS-02 (no deadline, no provider commitment):** availability of a documented,
**workspace-confined, read-only binary download API** using **appropriately scoped authentication**
(not a server-wide full-privilege session key). If and when that exists, a local bounded streaming
download route may be added (mirroring `bot/web/download.py`) subject to the path allowlist and a size
cap — as a **new, separately authorized** task, not part of this closure.

---

**FINAL VERDICT: PLAN 03 — ADMINISTRATIVELY CLOSED WITH DOCUMENTED PROVIDER BLOCKER**
