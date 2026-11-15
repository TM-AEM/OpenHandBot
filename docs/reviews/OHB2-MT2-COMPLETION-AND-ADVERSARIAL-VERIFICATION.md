# OHB2-MT-2 — Completion & Independent Adversarial Verification

**Task ID:** `OHB2-COMPLETE-MT2-AUTHENTICATED-ATTACHMENT-DOWNLOAD`
**Date:** 2026-11-14 · **Baseline HEAD:** `facf1f42578a20a4a37e220eca016ce3d534e750` (branch `main`)
**Status:** `DONE` (local implementation verified; one defect found and fixed). **No** commit/push/PR/merge/deploy/activation.

> This report was created by an AI agent (OpenHands) on behalf of the repository owner.

---

## 1. Task identity

The task string references `OHB2-REPAIR-PLAN-01-RESOURCE-STAGING` (FIX-01..FIX-04). Per the owner's
explicit resolution, the authorized task is **`OHB2-COMPLETE-MT2-AUTHENTICATED-ATTACHMENT-DOWNLOAD`**.
Repair Plan 01 is **already implemented at HEAD** (verified, §4) and was **not** re-implemented. This
report covers the MT-2 completion and its adversarial verification.

---

## 2. Baseline audit (before editing)

- **Branch / HEAD:** `main` @ `facf1f42578a20a4a37e220eca016ce3d534e750` (equals `origin/main`).
- **Working tree:** pre-existing uncommitted MT-2 work (backend `bot/web/{app,services,download}.py`,
  frontend `bot/web/static/{app.js,attachments.js,index.html,styles.css}`, tests, docs, `requirements.txt`).
  All preserved; nothing reverted or discarded. No destructive git operation was used.
- **Baseline checks:** `pytest -q` **3091 passed / 0 failed**; `node --test tests/frontend/*.test.js`
  **260 passed**; `pyflakes` **exit 0**; `bandit -lll` **0 high**; `pip_audit` **clean**. No pre-existing
  failures.
- **Approved decisions checked:** D-15 Option A (fixed 15-minute deadline, no extension) is recorded in
  `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md`; attachment A0–A4 decisions are respected. No
  contradiction introduced.
- **Dependency trace:** `python-telegram-bot==22.8` and `starlette==1.3.1` are installed; the download
  path uses only Starlette (`StreamingResponse`, `run_in_threadpool`) — no PTB streaming assumption.
- **SQLite owner:** the single production `Database` connection (`check_same_thread=False`, WAL); the
  download path is **read-only** and adds no new owner, worker, scheduler, or transaction boundary.

---

## 3. Acceptance criteria — result

| # | Criterion | Result |
| --- | --- | --- |
| 1 | Authenticated owner can download a staged attachment | **MET** — `test_download_success_returns_exact_bytes` |
| 2 | Read-only, fail-closed, IDOR-safe (no cross-user / cross-conversation leak) | **MET** — auth/IDOR tests |
| 3 | Safe open (`O_NOFOLLOW`, `fstat`, regular file, size bound + stored-size match) | **MET** — symlink/non-regular/size tests |
| 4 | Non-blocking, bounded streaming; fd always closed | **MET (after fix)** — §5 F-1 |
| 5 | No remote delivery/upload; no false "delivered" claim | **MET** — honest-text tests |
| 6 | Focused backend + frontend tests; full suite green | **MET** — §6 |

---

## 4. Repair Plan 01 (FIX-01..FIX-04) — verified present at HEAD (not re-implemented)

Commit `f6c0f24` (`feat: OHB2 Repair Plan 01 — resource and staging safety`) is an **ancestor of HEAD**.
Verified in the current code:

- **FIX-01** hard byte cap on the streaming write path (`bot/attachments.py` `_write_to_path` ⇒ `_TooLargeError`).
- **FIX-02** bounded concurrent downloads (`MAX_CONCURRENT_DOWNLOADS` semaphore wired to the loop).
- **FIX-03** per-batch / total staging quotas (`StagingStore(max_items_per_batch=…, max_total_bytes=…)`;
  defaults disabled per unresolved owner decision D-12).
- **FIX-04** staging-directory permission enforcement fail-closed (`ensure_staging_root` ⇒ `0700`).

`pytest tests/test_repair_plan_01_*.py tests/test_attachment_staging_a1.py
tests/test_attachment_cleanup_expiration_a4.py` ⇒ **135 passed**. No re-implementation performed.

---

## 5. Adversarial verification (20-point checklist)

Method: run the real code paths (real ASGI app + real SQLite + real staging root + a real ASGI event-loop
harness for streaming), inspect the source of the installed dependencies, and reproduce each finding.

| # | Attack / property | Method | Result |
| --- | --- | --- | --- |
| 1 | No session ⇒ 401 | request without cookie | **PASS** |
| 2 | Authorization **before** touching local data | source review (`_authorize_conversation` first) | **PASS** |
| 3 | Cross-user IDOR (other user requests owner's item) | login as `OTHER` | **PASS** — 404 |
| 4 | Cross-conversation IDOR (item's batch on another chat) | request via wrong `cid` | **PASS** — 404 |
| 5 | Unknown / reaped / non-pending item | mutate DB | **PASS** — 404 |
| 6 | Expired batch (`T0 + 15m < now`) | past `T0` | **PASS** — 410, no extension |
| 7 | Symlink substituted for the staged file | replace with symlink | **PASS** — rejected (`O_NOFOLLOW`/`lstat`) |
| 8 | Non-regular file (directory) at the token path | mkdir over the file | **PASS** — rejected |
| 9 | Size mismatch on disk vs stored | append bytes | **PASS** — 500, no stream |
| 10 | Mid-stream unlink (cleanup races the open fd) | unlink after first chunk | **PASS** — full body, fd closed (new test) |
| 11 | Oversize file (> `MAX_ATTACHMENT_BYTES`) | 3 MiB + 1 | **PASS** — rejected |
| 12 | Path traversal via `staging_token` | malformed tokens | **PASS** — `^[0-9a-f]{32}$` + single-component join |
| 13 | Client-supplied path/token in request or response | source review + response body scan | **PASS** — opaque `item_id` only; metadata-only list |
| 14 | Streaming blocks the shared event loop | responsiveness counter during a 1 MiB stream | **PASS** — reads on a worker thread |
| 15 | Unbounded memory (full-file buffering) | source review | **PASS** — 64 KiB chunks |
| 16 | fd closed on completion / cancellation / truncation | unit tests | **PASS** |
| 17 | **fd closed on client disconnect (ASGI ≥ 2.4)** | real ASGI harness, spec 2.4 | **FIXED** — see F-1 |
| 18 | Response-header injection via filename | CR/LF/quote names | **PASS** — ASCII allowlist |
| 19 | DB error ⇒ fail-closed | monkeypatch DB | **PASS** — 503 / empty list |
| 20 | False "delivered" claim in the UI | text review + tests | **PASS** — honest, distinct messages |

**CSRF/origin:** the download is a read-only `GET` (`state_changing=False`), same-origin, cookie
`SameSite=Strict`. No weakening; no public/bearer URL introduced.

### F-1 (found & fixed) — non-deterministic fd close on client disconnect

**Finding:** `iter_file_chunks` closes the fd in a `finally`, which fires on normal completion,
exception, and generator cancellation. But on **ASGI ≥ 2.4** (uvicorn's default) a client disconnect
raises `OSError` inside `StreamingResponse.stream_response`; Starlette converts it to `ClientDisconnect`
and **does not** call `aclose()` on the async generator (verified by reading the installed
`starlette/responses.py` and by a live ASGI-harness experiment). The fd therefore closed only on garbage
collection — **non-deterministic**, contradicting design §10 step 6 and F-01 ("close the fd in a
`finally` including on client disconnect").

**Fix:** `OwnedStreamingResponse(StreamingResponse)` wraps `__call__` and awaits `aclose()` on the body
iterator in a `finally`, guaranteeing closure on every exit path. `bot/web/app.py` uses it for the
download response. Regression tests: `test_owned_streaming_response_closes_fd_on_disconnect` and the
documentary `test_plain_streaming_response_leaks_until_gc` (pins the leak so a future Starlette change is
detected). Experiment before the fix: fd open until GC; after: closed before GC.

No other defect required a code change. One cosmetic consistency fix was made: added the missing
`.attachments-section` CSS rule so the new section matches `.files-section` (border/spacing/toolbar).

---

## 6. Verification (commands + real results)

| Command | Result |
| --- | --- |
| `python -m pytest -q` (baseline) | **3091 passed, 0 failed** (156.19s) |
| `python -m pytest -q` (after fix) | **3094 passed, 0 failed** (139.42s) |
| `node --test tests/frontend/*.test.js` | **267 passed, 0 failed** (baseline 260; +7) |
| `pytest tests/test_miniapp_attachment_download_mt2.py` | **34 passed** |
| `pytest tests/ -k "miniapp or attachment or staging or web"` | **850 passed, 0 failed** |
| `python -m pyflakes bot/ automation/ main.py tests/` | **exit 0** |
| `python -m bandit -r bot/ automation/ main.py -lll -s B613` | **0 high** (Medium 17 pre-existing; none in `web/download.py`) |
| `python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities found** |

Error count before → after: **0 → 0** (no regression).

---

## 7. Not verified / not implemented / still broken

- **Real Android 12 device / Telegram WebView gate — `NOT_RUN` (UNVERIFIED).** No device is available in
  this environment; the manual real-device procedure is Plan 10 §6. No device-compatibility claim is made.
- **Remote upload/delivery to OpenHands — not implemented** (out of scope; P0 `BLOCKED`).
- **Content integrity / hashing — not implemented and not claimed** (size-change detection only).
- **`MINI_APP_ENABLED` — unchanged** (no production enablement).
- **Repair Plan 01 FIX-03 quotas — implemented but disabled by default** (owner decision D-12 unresolved);
  unchanged by this task.

---

## 8. Assumptions and decisions

- Task identity = MT-2 (owner-resolved); Repair Plan 01 not re-implemented.
- The list endpoint (`GET …/attachments`) is a minimal, reversible addition needed by the frontend; it
  exposes safe metadata only.
- The disconnect fix uses a small `StreamingResponse` subclass rather than relying on GC; this is the
  smallest change that makes fd closure deterministic without changing the approved architecture.
- `anyio==4.16.0` pinned to the already-installed, already-tested version (no upgrade).
- Streaming uses an explicit async generator (not `iterate_in_threadpool`, which does not close a sync
  iterator's fd on cancellation).

---

## 9. Branch and commits

- Branch: `main` (no branch switch; all pre-existing working-tree changes preserved).
- **No commits made.** The working tree holds the MT-2 changes, this session's fix + tests, and
  pre-existing unrelated doc changes.

---

## 10. Suggested next step

Owner review of the diff and this report, then the real Android 12 / Telegram WebView gate (Plan 10 §6)
before any enablement.
