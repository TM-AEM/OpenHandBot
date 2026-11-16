# OHB2-PLAN10 — MT-2 Pre-Implementation Readiness Plan

**Task:** `OHB2-PLAN10-MT2-PRE-IMPLEMENTATION-READINESS`
**Date:** 2026-11-15
**Type:** Investigation + verification planning + documentation only. **NOT implementation.**
**Subject:** MT-2 — Authenticated Mini App Attachment Download (Plan 09 design study, closed
`PASS_WITH_NOTES`).

> Evidence labels: **[F]** verified this session from source/installed packages · **[I]** inference ·
> **[U]** unverified · **[R]** recommendation · **[OWNER]** owner decision.
> This report does **not** authorize implementation. It does not modify Plan 09 or its closure record.
>
> **Dated decision sync (2026-11-16, Plan 07 / `DOC-04`):** Historical sections below (`Date: 2026-11-15`)
> were written *before* the owner's subsequent **2026-11-15 approval of D-15 Option A** (fixed 15-minute
> expiry, staging-only reclaim, no C2 change, server does not model batch, no non-terminal batch state
> after expiry). See `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` (§5 → D-15, §9, §13.5) and
> `docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md`. This note is a dated sync only;
> historical investigation text below is preserved verbatim, and D-15 confirmation alone does **not**
> authorize MT-2 activation or deployment (`HOST-02` remains `BLOCKED`).

---

## 1. Executive summary and verdict

**Verdict: `READY_FOR_OWNER_GATE — NOT IMPLEMENTATION-READY`.**

- The Plan 09 design study stands; nothing in the current tree contradicts it. **[F]**
- **F-01** (nonblocking streaming) is the one open *technical* item. This report resolves it at the
  **design level** with a source-grounded recommendation (§3). No code is written.
- **F-02…F-06** are dispositioned in §4 (design clarifications / safeguards / tests / doc fix); none
  changes the accepted architecture.
- **D-15** remains **unresolved**; a decision brief is prepared in §5. It does **not** block the
  *design*, but it **must be confirmed before implementation** (it governs expiry handling).
- **Real Android 12 Telegram WebView verification** remains `UNVERIFIED`. A reproducible protocol is
  in §6; it **cannot** be executed in the repository alone.
- **Four implementation entry criteria** remain (§9). **No implementation authorization is implied.**

**[F] No implementation, frontend/backend change, schema change, dependency change, activation, or
deployment was performed.** `MINI_APP_ENABLED=False`; Autopush inactive.

---

## 2. Fresh baseline evidence (2026-11-15)

**Git state [F]:**

| Item | Value |
| --- | --- |
| Branch | `main` |
| HEAD = `main` = `origin/main` | `facf1f42578a20a4a37e220eca016ce3d534e750` |
| Divergence | `0 0` |
| Staged | none |
| Unstaged | `.agent/PROGRESS.md` (` M`) |
| Untracked | 9 files (Plan 05/06/07-A/07-A2/08, Plan 09 report, decision doc, 2 reviews) |
| Ignored | `.openhands/` (mtime `2026-11-14 16:27:11`, untouched), `.pytest_cache/` |

**Runtime/config [F]:** `MINI_APP_ENABLED=False` (`bot/config.py:262`); Autopush inactive (no process);
`concurrent_updates(True)` (`bot/app.py:86`); single process, single SQLite owner.

**Installed versions (authoritative for §3) [F]:**

| Package | Version | Note |
| --- | --- | --- |
| Python | 3.13.15 | runtime |
| `starlette` | **1.3.1** | pinned `requirements.txt:4`; `StreamingResponse` importable |
| `anyio` | **4.16.0** | transitive (via starlette/httpx); **not pinned in `requirements.txt`** |
| `uvicorn` | 0.34.0 | pinned `requirements.txt:5` |
| `httpx` | 0.28.1 | pinned |
| `python-telegram-bot` | 22.8 | pinned (`[all]`) |

**Architecture facts re-verified [F]:**
- The bot polling loop and the uvicorn ASGI server run as **tasks on the same asyncio event loop**
  (`bot/web/runner.py:87` `asyncio.create_task(server.serve(...))`; `bot/polling.py`; `main.py:23`).
  There is **no** second process/loop and **no** `to_thread`/`run_in_executor` anywhere in `bot/`.
- **No attachment download/retrieval route exists** today; no route reads `attachment_staging`.
- The only existing file-download path is the **buffered** export (`_attachment`, `bot/web/app.py:95`;
  `export_conversation`, `bot/web/services.py:711`) which buffers the whole body and sets an explicit
  `Content-Length`. It is **not** streaming.
- The reaper (`AttachmentReaper._remove_file`, `bot/attachments.py:1316`) uses **`os.unlink` only**;
  `grep` confirms **no `truncate`/`O_TRUNC`** anywhere in `bot/` ⇒ a file is never truncated in place.
- Staging perms: dir `0700`, file `0600` (`bot/attachments.py:109–111`); `ensure_staging_root` enforces
  `0700` fail-closed (FIX-04).
- `size_bytes` is written from the **actual bytes written** (`bot/attachments.py:750`,
  `size_bytes=written`) ⇒ it is an authoritative *size*, not a content hash.

**Unresolved / assumptions:**
- **[U]** `anyio` is not pinned; its version is resolved transitively. The recommendation in §3 depends
  on anyio ≥ 4.x behavior (`abandon_on_cancel` default `False`; default thread limiter = 40).
- **[U]** Real Telegram Android 12 WebView behavior (download trigger, filename, save location).
- **[I]** The future route would be added to the existing `MiniApp._routes()` (`bot/web/app.py:295`),
  reusing `_guarded`.

---

## 3. F-01 — Nonblocking streaming strategy comparison and recommendation

**Finding (restated).** Plan 09 §10 step 5 proposes `StreamingResponse` with bounded chunks but does
**not** specify whether the chunk producer is synchronous or asynchronous. **[F]** The bot polling
loop and the ASGI app share **one event loop** (`bot/web/runner.py:87`). A chunk producer that performs
blocking file reads **on the loop** would stall polling, the watcher, and all other requests.

### 3.1 Installed-version facts that constrain the choice [F]

1. **Starlette wraps sync iterables for you.** `StreamingResponse.__init__` does:
   `if isinstance(content, AsyncIterable): body_iterator = content else: body_iterator = iterate_in_threadpool(content)`.
   `iterate_in_threadpool` calls `await anyio.to_thread.run_sync(_next, iterator)` **once per chunk**.
   ⇒ A **plain sync generator** is off-loaded to a worker thread automatically.
2. **`iterate_in_threadpool` does NOT close the source iterator.** Source inspected: no `finally`, no
   `.close()` call. ⇒ relying on a sync generator's `finally` to close the fd is **not guaranteed** on
   early termination; it would depend on garbage collection.
3. **anyio default thread limiter = 40 tokens** (`anyio.to_thread.current_default_thread_limiter()`).
   Both strategies share this single limiter (no per-call limiter is set today).
4. **`run_sync` default `abandon_on_cancel=False`** (`anyio.to_thread.py`): if the host task is
   cancelled mid-read, the in-flight thread read **completes** before cancellation is delivered. The
   window is bounded by **one chunk read** (e.g. 64 KiB), not the whole file.
5. **uvicorn advertises ASGI `spec_version = 2.3`** (`uvicorn/protocols/http/h11_impl.py:203`, and the
   same in `httptools_impl.py`). Since `2.3 < 2.4`, `StreamingResponse.__call__` takes the
   **`create_collapsing_task_group` + `listen_for_disconnect`** path ⇒ on `http.disconnect` the
   streaming task is **cancelled**. ⇒ **Client disconnect reaches the producer** as cancellation (for
   an async producer) or as task cancellation of the threadpool await (for the sync path).
6. **Async iterables are used as-is** (no threadpool wrapper). ⇒ an async generator controls its own
   fd lifecycle and can close deterministically in `finally`.

### 3.2 Strategy A — sync iterator via Starlette's threadpool

Design: handler opens the fd; a plain generator yields bounded reads; `StreamingResponse(gen)` wraps it
with `iterate_in_threadpool`.

| Dimension | Assessment |
| --- | --- |
| Event-loop blocking | **None** — each `next()` runs via `anyio.to_thread.run_sync` [F] |
| Thread-pool behavior | Shares default limiter (40); **one thread-hop per chunk**; a slow *client* does **not** hold a thread (thread is held only during the read syscall) |
| FD lifecycle | **Weak** — `iterate_in_threadpool` never calls `.close()` [F]; fd close must be forced by the **handler** (`try/finally`) or a `background` task, not by the generator |
| Disconnect/cancel | Producer cancelled via task group; in-flight read finishes (≤1 chunk) then stops [F] |
| Expiry/cleanup race | Unchanged: `open` → `ENOENT` clean failure; unlink-during-stream reads full content (see §3.4) |
| Bounded memory | Yes — one chunk at a time |
| Version compatibility | Native, zero custom thread code |
| Testability | Good (`TestClient`); fd-close ordering harder to assert |
| WebView implication | None (server-side only) |

### 3.3 Strategy B — async generator delegating reads to a worker thread (AnyIO)

Design: `async def` generator opens the fd once (`O_RDONLY|O_NOFOLLOW`), `os.fstat`-verifies, then
`chunk = await anyio.to_thread.run_sync(os.read, fd, CHUNK)` in a loop, `yield chunk`; `finally:
os.close(fd)`. Passed directly to `StreamingResponse` (used as-is, **not** threadpool-wrapped).

| Dimension | Assessment |
| --- | --- |
| Event-loop blocking | **None** — reads run in a worker thread via `anyio.to_thread.run_sync` [F] |
| Thread-pool behavior | Shares default limiter (40); **one in-flight read per stream**; slow client holds **no** thread (thread only during the read syscall) |
| FD lifecycle | **Strong** — async generator's `finally` runs on cancellation [F] ⇒ deterministic `os.close` |
| Disconnect/cancel | Cancellation delivered at the `await` point; `abandon_on_cancel=False` finishes the current read (≤1 chunk) then the generator unwinds and closes the fd [F] |
| Expiry/cleanup race | Same as A; plus deterministic fd release reduces fd-leak risk under repeated races |
| Bounded memory | Yes — one `CHUNK` (e.g. 64 KiB) at a time |
| Version compatibility | anyio 4.16.0 + starlette 1.3.1 (async-iterable path) [F]; **depends on unpinned anyio** |
| Testability | **Best** — `anyio.run` + `TestClient`; fd close is assertable in `finally` |
| WebView implication | None (server-side only) |

### 3.4 Shared behavior (both strategies) [F]

- **Open-then-verify:** open with `O_NOFOLLOW`, `fstat`, require `S_ISREG`, compare `st_size` to
  `size_bytes`; mismatch ⇒ clean failure before headers.
- **Race with the reaper:** the reaper **unlinks** (never truncates) [F]. On POSIX an already-open fd
  continues to read the **full** file after unlink ⇒ a mid-stream unlink does **not** truncate the
  response. If unlink happens **before** open ⇒ `ENOENT` ⇒ clean 404/410.
- **Honest failure:** any read error or short read aborts the response; **never** a claimed success.
- **Memory:** bounded by `CHUNK`, not by file size (unlike the buffered export path).

### 3.5 Recommendation [R]

**Adopt Strategy B** (async generator + `anyio.to_thread.run_sync(os.read, fd, CHUNK)`, fd closed in
`finally`), with **Strategy A as an acceptable fallback** only if the fd is owned and closed by the
route handler (never by the generator alone).

Rationale, tied to the inspected source:
1. **Deterministic fd lifecycle** — Starlette's `iterate_in_threadpool` does **not** close sync
   iterators [F]; an async generator's `finally` **does** run on the cancellation that Starlette
   raises on disconnect (spec 2.3 path) [F].
2. **No event-loop blocking** — identical thread off-load to Strategy A, via supported AnyIO [F].
3. **Bounded resources** — one chunk in memory and at most one worker-thread hop per stream; slow
   clients consume connections, **not** threads, mitigating T12/T13 thread-pool concerns.
4. **Testability** — the fd-close and cancel behavior are directly assertable.

**Constraints (must not be violated):** no new worker/process/scheduler/event loop; reuse the default
AnyIO limiter (do not add a private limiter unless an owner decision says so); keep the 3 MiB cap and
the `O_NOFOLLOW`/`_is_within` checks.

**Open dependency:** `anyio` is **not pinned**. Before implementation, pin it to the tested minor
(≥4.16,<5) so `run_sync`/limiter semantics are guaranteed. **[R]**

---

## 4. F-02 … F-06 — dispositions

| ID | Severity | Accurate restatement | Needs | Smallest compatible mitigation | Changes accepted architecture? |
| --- | --- | --- | --- | --- | --- |
| **F-02** | LOW | `O_NOFOLLOW` protects only the **final** path component; the staging **root** is resolved via `_is_within` (`os.path.realpath`, `bot/attachments.py:284`). A parent-dir swap between check and `open` is a TOCTOU. | Design clarification + implementation safeguard | After `os.open`, verify the **opened** object with `os.fstat` (`S_ISREG`), and treat the `0700` process-owned root as the trust boundary; document that parent-component TOCTOU is not separately defended. | No |
| **F-03** | LOW | `size_bytes` = actual bytes written [F] (`bot/attachments.py:750`), but the check detects only a **size change**; a **same-size** content swap is not detected, and there is **no content hash**. | Design clarification | Correct the wording ("detect size change", not "detect replacement"); do **not** claim integrity; optionally compare `fstat().st_size` to `size_bytes` as a cheap consistency check. No hashing unless the owner asks. | No |
| **F-04** | LOW | The export button uses `fetch → blob → objectURL → <a download>` (`bot/web/static/app.js:1031`). With `SameSite=Strict`, a **top-level navigation** triggered from outside the site may not carry the session cookie; a **same-origin `fetch`** does. | Design clarification + real-device test | Keep the **same-origin `fetch`+blob** pattern (cookie is sent) rather than direct navigation; add a real-device test (§6). | No |
| **F-05** | DOC ERROR | Plan 09 §3 says "6 Plan 05/06/07-A/07-A2/08 review docs"; the actual count is **7** (verify: 9 untracked − decision doc − Plan 09 report). | Documentation correction | Record the discrepancy here; **do not** edit Plan 09 (out of scope). Fold into any future Plan 09 erratum. | No |
| **F-06** | INFO | The reaper uses `os.unlink` only (no truncate) [F]; on POSIX an open fd reads the full file after unlink ⇒ the "partial bytes" concern (Plan 09 case 4) is **weaker** than stated. | None | None — strengthens the "abort on read error" invariant; no action. | No |

**Summary:** F-02/F-03/F-04 → design clarifications (+ one real-device test); F-05 → doc erratum;
F-06 → informational. **None** requires a schema, session, token, or architectural change.

---

## 5. D-15 — owner-decision brief

**Exact unresolved decision [F] (register `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md:868–894`):**
Confirm that `expires_at` is a **fixed 15-minute** window from first file (**not extended**), that it
reclaims **staging only** (not the materialized copy C2), that the **server does not model the batch**
(batch is client-side), and that after `expires_at` **no non-terminal state is shown**. Status:
**unresolved (confirmation)**. Type: **owner decision (confirmation)**.

**Existing options (register):**
- **A — confirm the current model** (15 min fixed; no server-side batch).
- **B — model the batch server-side** (upstream scope expansion).
- **C — a different window** (not 15 min).

**Consequences:**
- **A:** matches shipped behavior (`ATTACHMENT_BATCH_TTL = 15 min`, `bot/db.py:261`); zero code change;
  MT-2 expiry handling stays as designed (410/404 honest rejection after expiry).
- **B:** larger scope; introduces server-side batch state ⇒ **schema** decision ⇒ new owner/architecture
  gate; not required by MT-2.
- **C:** changes the reconciliation window; requires re-deriving expiry tests and UX copy.

**Recommendation [R]:** **Option A** (confirm). Rationale: it reflects the shipped constant and the
Plan 09 design; MT-2 adds no server-side batch concept. Trade-off: none material.

**Does it block implementation?** **Yes — before implementation**, not before design. It governs
expiry/retention handling and UX (T9/case-1/case-10 in Plan 09 §11). **Not decided here.**

---

## 6. Android 12 Telegram WebView verification protocol

**Status: `NOT_RUN`** — requires a real device + activation/deployment, which are **out of scope** here.

### 6.1 Repository-executable tests (no device) [F]

These can run in CI/repo and **must not** be confused with device evidence:
- **Backend (future) unit/integration:** the route's authz/IDOR/expiry/race behavior via Starlette
  `TestClient` against `build_web_app` (patterns exist: `tests/test_miniapp_http_journeys.py`,
  `tests/test_real_http_miniapp_download.py`).
- **Streaming correctness (future):** assert chunking, `Content-Length` consistency, fd close in
  `finally`, and cancel-on-disconnect using `anyio` + `TestClient`.
- **Frontend logic (Node):** filename/`Content-Disposition` parsing and error mapping
  (`tests/frontend/*.test.js`; `dom_stub.js` provides `Blob`/`URL` stubs — **simulated only**).
- **[F] Existing baseline that already passes:** the 6 miniapp/export/session/initdata/authz pytest
  files (**119 passed**) and `node --test tests/frontend/*.test.js` (**fail 0**). These are **not**
  device evidence.

### 6.2 Real Android 12 device tests (mandatory before implementation)

**Prerequisites [F/U]:**
- Real **Android 12** device with the **official Telegram** app (record Telegram version + WebView
  provider/version, e.g. from `chrome://version` inside the in-app browser or Telegram's about).
- `MINI_APP_ENABLED=1` with a **public HTTPS** `MINI_APP_URL` (`bot/config.py:242–266`).
- An allowlisted owner account; a bot instance reachable from the device.
- A staged, `stored` attachment with known content (for SHA-256 comparison).

**Evidence to capture per test [F convention]:** screen recording/screenshot **+** app/server logs
(no secrets) **+** file hash where applicable.

| # | Test | Steps | Expected | Failure criteria |
| --- | --- | --- | --- | --- |
| 1 | Small valid file | tap download | downloads; correct bytes | no download / corrupt |
| 2 | 3 MiB boundary | tap download (exactly 3 MiB) | full download; size correct | truncation |
| 3 | Oversized rejection | attempt > 3 MiB | honest rejection (413), no partial file | false success |
| 4 | Filename/extension | known name | saved name = safe name; correct ext | wrong/missing ext |
| 5 | MIME type | known type | handled per `Content-Type`/`Content-Disposition` | wrong type / forced inline |
| 6 | Content integrity | download + compare SHA-256 | hashes match | mismatch |
| 7 | Expired attachment (>15 min) | tap download | honest 410/404 message | false availability |
| 8 | Unauthorized conversation | craft request | 403/404, no data | data leak |
| 9 | Expired session / logout | after logout, tap download | 401 → re-auth prompt | wrong success |
| 10 | Network interruption | interrupt mid-download | incomplete → retry guidance | false success |
| 11 | Retry/repeat | tap twice | both idempotent | error/dup |
| 12 | Save-location discoverability | find file on device | file discoverable | cannot locate |
| 13 | Open/share saved file | open/share | opens/shares | fails |
| 14 | WebView blocks download | tap download | defined failure surfaced honestly | silent no-op |
| 15 | Arabic RTL messages/errors | observe UI | RTL correct; error states clear | broken RTL / unclear |
| 16 | **No false delivery claim** | download a staged file | UI says "sent to browser", **not** "OpenHands received it" | any delivery/save claim |

**[R]** Tests 1, 2, 6, 7, 9, 10, 16 are the **gating** ones for the core guarantee (correct bytes +
honest non-delivery). **[F] A successful HTTP response alone is not proof** the user can locate the
file (test 12). **Do not claim WebView compatibility until real-device evidence exists.**

---

## 7. Security and race-condition considerations

- **Authz before FS:** authenticate → authorize → verify item/batch/expiry → **then** open (Plan 09 §9/§10). **[R]** keep this order.
- **Path confinement:** opaque `item_id` only; server derives the path; `is_safe_workspace_path` +
  `_is_within` + `O_NOFOLLOW` + post-open `fstat`. **[F]**
- **Cleanup race:** the reaper is DB-first and **unlinks only** [F]; mid-stream unlink does not truncate
  an open fd (POSIX) [I]; pre-open unlink ⇒ clean 404/410. **Honest failure** on any error.
- **Resource bounds:** bounded chunk memory; one worker-thread hop per stream; slow clients consume
  connections, not threads. **[R]** consider a per-session concurrent-download bound reusing the
  existing `SlidingWindowLimiter` (`bot/web/ratelimit.py`) — **owner decision**, not implemented.
- **CSRF/caching:** `SameSite=Strict` retained; `Cache-Control: no-store`, `nosniff`,
  `Referrer-Policy: no-referrer` on the response. **[F]** existing header set.
- **No new secrets/state:** no token, no schema, no lifecycle state, no public URL. **[F]**

---

## 8. Dependencies and implementation sequence (design-level, not authorized)

**Dependencies [F/R]:**
- `starlette==1.3.1` (pinned) provides `StreamingResponse`; **anyio must be pinned** (currently
  transitive, unpinned) before implementation. **[R]**
- No new runtime dependency is required for Strategy B beyond the already-present anyio.

**Proposed sequence (each step gated; nothing here is authorized):**
1. **Owner gates** (§9): F-01 strategy approved, D-15 confirmed, WebView plan accepted, **explicit
   implementation authorization**.
2. **Design freeze:** F-02/F-03/F-04 clarifications folded into the design (no code).
3. **Repo tests first** (backend authz/streaming + frontend logic) — red→green.
4. **Backend route + streaming** (Strategy B), reusing `_guarded`/ownership; no schema change.
5. **Frontend control** (fetch+blob pattern; Arabic copy `[OWNER]`-approved).
6. **Real Android 12 device verification** (§6.2) — **before** any activation claim.
7. **Activation** — separate authorization; `MINI_APP_ENABLED` stays `False` until then.

---

## 9. Explicit implementation entry criteria (all must hold)

1. **F-01 resolved** — a nonblocking streaming strategy specified **and reviewed** (this report
   recommends Strategy B; it is a proposal, not an approval).
2. **Real Android 12 Telegram WebView verification passed** (or an owner-accepted alternative) — DOM
   stubs/simulated tests are insufficient.
3. **D-15 explicitly confirmed by the owner.**
4. **Separate explicit owner authorization** naming the option, scope, and permitted files.

**Until all four hold: MT-2 remains NOT implementation-ready and NOT authorized.**

---

## 10. Outstanding owner decisions

| ID | Decision | Status | Blocks |
| --- | --- | --- | --- |
| **D-15** | Confirm fixed 15-min window / no server-side batch (Option A) | unresolved | implementation |
| F-01 strategy | Approve nonblocking streaming strategy (recommend Strategy B) | proposed | implementation |
| WebView | Accept the §6 real-device protocol / run it | not run | implementation/activation |
| Arabic copy | Approve MT-2 UX wording (Plan 09 §19) | not approved | implementation |
| Scope | Individual attachments only vs broader | not decided | implementation |
| Concurrency | Per-session concurrent-download bound | optional | hardening |
| anyio pin | Pin `anyio` before implementation | recommended | implementation |
| Authorization | Explicit implementation authorization | **not granted** | implementation |

---

## 11. Exact scope exclusions

This task (and this report) does **NOT** authorize: backend/frontend implementation; adding a download
endpoint; changing authentication/session behavior; changing the database schema or token storage;
adding dependencies; MT-1 or MT-3; Secure Pull or remote attachment upload; automatic attachment
delivery; enabling `MINI_APP_ENABLED`; activating Autopush; production testing or deployment. The
existing **3 MiB limit**, **staging lifecycle**, **single SQLite owner**, and **single bot/ASGI
process** remain unchanged. **No architecture change is proposed or approved.**

---

## 12. Self-verification (this task)

- **Files changed:** created this report; appended one entry to `.agent/PROGRESS.md` (append-only).
- **[F] No** source/test/schema/config/dependency/frontend change; `MINI_APP_ENABLED=False`; Autopush
  inactive; `.openhands/` untouched.
- **No** commit/push/PR/merge/release/deployment. **No** implementation authorization implied.
- **Evidence gaps (honest):** no real-device WebView test was run; `anyio` version is transitive and
  unpinned; F-05 is a Plan 09 documentation erratum recorded but not fixed (Plan 09 must not be
  rewritten here).
