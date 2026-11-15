# OHB2-MT-2 — Authenticated Mini App Attachment Download — Implementation Report

**Status:** `IMPLEMENTED_LOCALLY` (backend + frontend + tests), **adversarially re-verified 2026-11-14**.
**No** commit/push/PR/merge/deploy/activation.
**Date:** 2026-11-15 (impl) · 2026-11-14 (adversarial verification pass) · **Baseline HEAD:** `facf1f42578a20a4a37e220eca016ce3d534e750` (branch `main`).

> This report was created by an AI agent (OpenHands) on behalf of the repository owner.

---

## 1. Task identity (resolved)

The task string references `OHB2-REPAIR-PLAN-01-RESOURCE-STAGING` (FIX-01..FIX-04). Per the owner's
explicit resolution, the **actual** authorized task is **`OHB2-IMPLEMENT-MT2-AUTHENTICATED-ATTACHMENT-DOWNLOAD`**.
The Repair Plan 01 work is **already implemented at HEAD** (see §3) and must **not** be re-implemented.
This report therefore covers MT-2. The Repair Plan 01 framing is treated as the recurring task-identity
collision documented in `.agent/PROGRESS.md`.

---

## 2. Acceptance criteria (MT-2)

1. An authenticated Mini App user can **download a staged attachment** for a conversation they own. — **MET**
2. The download path is **read-only**, **fail-closed**, and never discloses another user's/other
   conversation's data (IDOR-safe). — **MET**
3. The staging file is opened **safely** (`O_NOFOLLOW`, `fstat`, regular-file, size-bound, stored-size match). — **MET**
4. Streaming is **non-blocking** (worker thread) and **bounded** (no full-file buffering, fd always closed). — **MET**
5. No remote delivery/upload to OpenHands; no false "delivered" claim in the UI. — **MET**
6. Focused backend + frontend tests; full suite green. — **MET**

**Out of scope / not authorized:** production enablement (`MINI_APP_ENABLED` unchanged), deployment,
release, Autopush, remote attachment upload/delivery, any change to `concurrent_updates`, DB schema, or
attachment policy.

---

## 3. Repair Plan 01 (FIX-01..FIX-04) — verified already present at HEAD

Commit `f6c0f24` (`feat: OHB2 Repair Plan 01 — resource and staging safety (FIX-01..FIX-04)`) is an
**ancestor of HEAD** (`facf1f4`). Verified in current code:

- **FIX-01** (hard byte cap on streaming download): `bot/attachments.py` `_write_to_path` enforces the cap
  and raises `_TooLargeError`; no `download_to_memory`.
- **FIX-02** (bounded concurrent downloads): `MAX_CONCURRENT_DOWNLOADS` semaphore wired to the loop.
- **FIX-03** (per-batch / total staging quotas): `StagingStore(max_items_per_batch=…, max_total_bytes=…)`
  (defaults **disabled** per owner decision D-12, still unresolved).
- **FIX-04** (staging-directory permission fail-closed): `ensure_staging_root` enforces `0700`.

`pytest tests/test_repair_plan_01_*.py tests/test_attachment_staging_a1.py
tests/test_attachment_cleanup_expiration_a4.py` ⇒ **135 passed**. No re-implementation performed.

---

## 4. Changes

### 4.1 `bot/web/download.py` (NEW)
Resource-bounded, fail-closed read helpers for the local staging store:
- `resolve_staged_path(root, token, *, expected_size, max_bytes)` — validates the opaque
  `token_hex(16)` token, `realpath`s the root once, `lstat`s (no symlink follow), requires a regular
  file with size in `(0, max_bytes]` equal to the stored size.
- `open_staged_file(path, expected_size, *, max_bytes)` — `O_NOFOLLOW` open + `fstat` re-check
  (regular file, size match) so there is no check↔open race.
- `iter_file_chunks(fd, expected_size, *, chunk_size=64KiB)` — **async generator** reading via
  `starlette.concurrency.run_in_threadpool` (i.e. `anyio.to_thread.run_sync`), closing the fd in
  `finally` on success/exception/cancellation, and detecting truncation (early EOF ⇒ error).
- `OwnedStreamingResponse` (NEW, 2026-11-14 verification) — a `StreamingResponse` subclass that awaits
  `aclose()` on the body iterator in a `finally`. **Defect found and fixed:** on ASGI ≥ 2.4 (uvicorn's
  default), Starlette raises `ClientDisconnect` on a client disconnect and does **not** close the async
  generator, so the fd closed only on garbage collection (non-deterministic) — a violation of design §10
  step 6 / F-01. The subclass makes the fd close **deterministically** on every exit path.
- `safe_download_filename`, `AttachmentDownload`, `AttachmentDownloadError`.

### 4.2 `bot/web/services.py` (MODIFIED)
- `MiniAppService.download_attachment(conversation_id, item_id, telegram_id)` — authorization first
  (`_authorize_conversation`), then: item must exist and be `stored`; its batch must belong to the same
  user **and** conversation and be `pending`; `T0 + 15min > now` (no extension, D-15). All failures are
  fail-closed (404 `not_found` / 410 `expired` / 503). Resolves the staging path from the opaque token
  (no client-supplied path).
- `MiniAppService.list_staged_attachments(conversation_id, telegram_id)` — safe metadata only
  (`item_id`, sanitized `display_name`, `size_bytes`, remaining seconds). No `staging_token`, path, or
  content.

### 4.3 `bot/web/app.py` (MODIFIED)
- Two routes: `GET /api/v1/conversations/{id}/attachments` and
  `GET /api/v1/conversations/{id}/attachments/{item_id}/download`.
- `conversation_attachments` handler (JSON metadata).
- `attachment_download` handler: session auth → service → `open_staged_file` (after authorization) →
  `StreamingResponse` with security headers, sanitized `Content-Disposition`, explicit `Content-Length`.

### 4.4 `bot/web/static/attachments.js` (NEW) + `bot/web/static/app.js` (MODIFIED) + `index.html` (MODIFIED)
- `attachments.js`: DOM-independent logic (safe filename from `Content-Disposition`, error labels,
  `humanSize`, `remainingLabel`, `listItems` that drops unexpected fields) — shared and Node-testable.
- `app.js`: "local attachments ready to download" section in the conversation detail view; download via
  `fetch` → `blob` → object URL (revoked after use), same-origin + no-store.
- `index.html`: loads `attachments.js?v=1`; `app.js?v=7`.

### 4.5 `requirements.txt` (MODIFIED)
Explicit `anyio==4.16.0` pin (previously transitive/unpinned). `starlette 1.3.1` requires
`anyio<5,>=3.6.2` (verified via `importlib.metadata`). The streaming path depends on
`anyio.to_thread.run_sync`.

### 4.6 Tests (NEW) + `tests/frontend/dom_stub.js` (MODIFIED)
- `tests/test_miniapp_attachment_download_mt2.py` (34 tests): auth, IDOR (cross-user, cross-conversation),
  unknown/expired/reaped/non-pending, missing file, symlink, non-regular file, size mismatch, oversize,
  DB failure fail-closed, exact-bytes integrity, unit tests for the download helpers (bad token,
  symlink, fd close on completion/cancellation, truncation, non-blocking event loop), `batch_deadline`
  no-extension, **fd close on disconnect (ASGI 2.4)** + a documentary test pinning the leak in plain
  `StreamingResponse`, and a **mid-stream unlink** race test.
- `tests/frontend/attachments.test.js` (10 tests) — DOM-independent logic.
- `tests/frontend/attachments_ui.test.js` (7 tests, NEW 2026-11-14) — DOM integration: section renders
  safe items, download sends a same-origin request and performs a blob download with honest toasts,
  double-click ⇒ single request, expiry/session/network failures ⇒ clear Arabic message with no
  download, empty list state.
- `dom_stub.js` updated to load `attachments.js`.
- `bot/web/static/styles.css`: added the `.attachments-section` rule (matching `.files-section`) so the
  section gets the standard top border/spacing and toolbar layout.

### 4.7 Adversarial verification (2026-11-14)

A 20-point adversarial pass was run against the live code. One **real defect** was found and fixed (the
non-deterministic fd close on disconnect, §4.1) with two regression tests plus a documentary leak test.
All other checks passed or were already handled; no other code change was required. The full checklist and
evidence are in the task report `docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md`.

---

## 5. Verification (commands + real results)

| Command | Result |
| --- | --- |
| `python -m pytest -q` (baseline) | **3091 passed, 0 failed** (156.19s) |
| `python -m pytest -q` (after 2026-11-14 verification + fix) | **3094 passed, 0 failed** (139.42s) |
| `node --test tests/frontend/*.test.js` | **267 passed, 0 failed** (baseline 260; +7 new UI tests) |
| `python -m pyflakes bot/ automation/ main.py tests/` | **exit 0** (clean) |
| `pytest tests/test_miniapp_attachment_download_mt2.py` | **34 passed** |
| `python -m pytest -q tests/ -k "miniapp or attachment or staging or web"` | **850 passed, 0 failed** |
| `python -m bandit -r bot/ automation/ main.py -lll -s B613` | **0 high** (unchanged; Medium 17 pre-existing, none in `web/download.py`) |
| `python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities found** |

Error count before → after: **0 → 0** (no regression). The three new backend tests and seven new frontend
tests all pass.

---

## 6. Not verified / not implemented

- **Real Android 12 device / Telegram WebView gate:** `NOT_RUN` (Plan 10 §6). No device-compatibility claim.
- **Remote upload/delivery to OpenHands:** out of scope, blocked (P0 `BLOCKED`).
- **Content integrity / hashing:** not implemented and not claimed (size-change detection only).
- **`MINI_APP_ENABLED`:** unchanged (no production enablement).

---

## 7. Assumptions and decisions

- Task identity = MT-2 (owner-resolved); Repair Plan 01 not re-implemented.
- The attachment list endpoint (`GET …/attachments`) was added because the frontend needs to discover
  staged items; it exposes only safe metadata. This is a minimal, reversible addition within the MT-2
  scope.
- `anyio` pinned to the already-installed, already-tested version (no dependency upgrade).
- Streaming uses an explicit async generator rather than `iterate_in_threadpool` because the latter does
  not close a sync iterator's fd on cancellation.

---

## 8. Branch and commits

- Branch: `main` (no branch switch; pre-existing working-tree changes preserved).
- **No commits made.** Working tree contains MT-2 changes + pre-existing unrelated doc changes.

---

## 9. Suggested next step

Owner review of this report and the diff, then (if approved) the real Android 12 / Telegram WebView gate
(Plan 10 §6) before any enablement.
