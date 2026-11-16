# OHB2-PLAN-16-DOCUMENTATION-CONSISTENCY — Independent Read-Only Review

- **Review Task ID:** `OHB2-PLAN-16-DOCUMENTATION-CONSISTENCY-INDEPENDENT-REVIEW-01`
- **Reviewed Execution Task ID:** `OHB2-PLAN-16-DOCUMENTATION-CONSISTENCY-EXECUTION-01`
- **Parent Plan ID:** `OHB2-PLAN-16-DOCUMENTATION-CONSISTENCY` (OpenHandBot Plan 06)
- **Reviewed Report:** `docs/reviews/OHB2-PLAN16-DOCUMENTATION-CONSISTENCY-REPORT.md`
- **Date:** 2026-11-16
- **Overall Review Verdict:** `PASS_WITH_NOTES` (`DOC-01: PASS_WITH_NOTES` | `DOC-02: PASS_WITH_NOTES`)

---

## A. Review Baseline

- **Repository / Workspace Root:** `/app/applet`
- **Git Metadata (`Branch` / `HEAD` / `Working-tree diff`):** **Unavailable** — `.git` is absent (`ls: cannot access '.git': No such file or directory`; `git status` and `git rev-parse HEAD` exit `128`: `fatal: not a git repository (or any of the parent directories): .git`). No Git repository was initialized or modified.
- **Relationship to Audited Snapshot (`facf1f42578a20a4a37e220eca016ce3d534e750`):** Cannot be independently established due to missing Git metadata.
- **Working-tree & Changed-File Visibility:** Absence of Git does not prove the rest of the tree is clean. Independent inspection confirmed the three files declared in the execution report (`docs/MINI_APP.md`, `docs/reviews/OHB2-PLAN16-DOCUMENTATION-CONSISTENCY-REPORT.md`, `.agent/PROGRESS.md` lines `4163–4176`) exist and contain the described changes/records, and `ast.parse` + `compileall` across all `165` Python files show no syntax breaks or new unused imports.
- **Environment Runtimes & Tooling:** `Python 3.10.12`, `Node v22.23.2`. `pip`, `pip3`, `uv`, `pytest`, `pyflakes`, `bandit`, `pip_audit`, `starlette`, `uvicorn`, and `anyio` are **not installed** in this environment.

---

## B. DOC-01 Findings — Mini App Session Persistence

### B.1 Direct Implementation & Lifecycle Verification
Direct inspection of `bot/db.py`, `bot/web/sessions.py`, `bot/web/app.py`, `bot/app.py`, `bot/config.py`, `main.py`, and `tests/test_miniapp_session_persistence.py` confirms:

1. **Single Authoritative SQLite Owner:**
   - `bot/app.py:90` (`build_application`) instantiates a single `Database(config.db_path)` shared across bot handlers, workers, and (when `MINI_APP_ENABLED=True`) `_wire_mini_app` (`bot/app.py:337–350` -> `build_web_app` -> `MiniApp(config, db, client, application)`).
   - `bot/db.py:550–565` configures `sqlite3.connect(path, check_same_thread=False)` with `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, and `PRAGMA foreign_keys=ON` (fail-closed).
2. **Schema & CRUD (`bot/db.py`):**
   - `web_sessions` (`bot/db.py:732–739`) stores `(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL, profile TEXT NOT NULL DEFAULT '{}')` plus `idx_web_sessions_expires` via non-destructive `CREATE TABLE IF NOT EXISTS`.
   - Single-owner operations (`bot/db.py:2536–2573`): `add_web_session`, `get_web_session` (filtering `expires_at > ?` server-side), `delete_web_session`, `prune_web_sessions`, `count_web_sessions`.
3. **Token Generation, Hashing & HTTP Session Lifecycle (`bot/web/sessions.py`, `bot/web/app.py`):**
   - `SessionStore.create()` (`bot/web/sessions.py:64–87`) generates `secrets.token_urlsafe(32)`, computes SHA-256 hex (`hash_token`, lines `30–35`), writes `token_hash` to SQLite **before** returning `Session`, and runs best-effort expired-row pruning (`_prune_best_effort`, lines `157–161`). Raw tokens are never written to SQLite or logs.
   - `MiniApp.auth()` (`bot/web/app.py:512–549`) validates `initData`, enforces `ALLOWED_TELEGRAM_ID`, creates the SQLite session, and sets cookie `ohb_session` (`HttpOnly; SameSite=Strict; Path=/`; `Secure` controlled by `MINI_APP_COOKIE_SECURE`).
   - `MiniApp._guarded()` (`bot/web/app.py:450–469`) resolves cookie via `SessionStore.get()` (`bot/web/sessions.py:89–120`, returning `None` fail-closed on missing/expired/invalid tokens or DB errors), enforces `is_allowed`, and checks `Origin`/`Sec-Fetch-Site` on state-changing requests.
   - `MiniApp.logout()` (`bot/web/app.py:551–562`) calls `SessionStore.revoke()` (`bot/web/sessions.py:122–140`). On DB failure, `revoke()` returns `False` and `logout()` returns `503 logout_failed` without deleting the client cookie (avoiding false logout confirmation).
4. **Startup Cleanup (`bot/db.py`, `main.py`, `bot/app.py`):**
   - `Database.run_startup_maintenance()` (`bot/db.py:5279–5307`, called in `main.py:52` and `bot/app.py:182`) runs `quick_check()`, `optimize()`, `checkpoint()`, and `prune_web_sessions(time.time())`. No separate background scheduler or cleanup worker exists.
5. **`SessionStore._mem` Fallback & Other In-Memory Structures:**
   - `SessionStore._mem: dict[str, Session]` (`bot/web/sessions.py:61`) is used **strictly** when `self._db is None` (standalone/test contexts: lines `13–14, 55, 74, 93, 130, 143`). In production, `_wire_mini_app` always passes the `Database` instance (`bot/app.py:349` -> `bot/web/app.py:133`), so `_mem` cannot become authoritative in production.
   - `SlidingWindowLimiter` (`bot/web/ratelimit.py`) stores ephemeral in-memory rate-limit timestamps keyed by `hash_token(session.token)` or client IP (`bot/web/app.py:458`) — not session authentication state.

### B.2 Critical Restart-Test Audit
1. **Execution Agent's Reported Experiment (Artifact Limitation):** `docs/reviews/OHB2-PLAN16-DOCUMENTATION-CONSISTENCY-REPORT.md` (§4, line 84) reports an inline 3-process Python stdlib check against `bot/db.py` + `bot/web/sessions.py`, **but does not embed the executed Python snippet/commands**. From the execution report alone, that specific run is **report-only evidence** (not directly inspectable on disk).
2. **Independent Reproduction & Boundary Analysis:**
   - Note that a direct `import bot.web.sessions` fails in this environment (`ModuleNotFoundError: No module named 'starlette'`) because `bot/web/__init__.py:4` eagerly imports `build_web_app` from `bot/web/app.py`.
   - This review ran a read-only 3-OS-process (`subprocess.run`) verification using minimal `types.ModuleType` package stubs (`bot`, `bot.web` with `__path__`) so each process loaded the **unmodified production modules** `bot/db.py` (`Database`) and `bot/web/sessions.py` (`SessionStore`, `hash_token`) against a shared temporary SQLite file:
     - **Process 1:** Created active session (`ttl=3600`, `now=1000.0`) and short-lived session (`ttl=10`, `now=1000.0`) via `SessionStore.create()`.
     - **Process 2 (fresh OS process, fresh `Database` + `SessionStore`):** Verified active session authenticated at `now=1500.0`, expired short session returned `None`, and `SessionStore.revoke()` returned `True`.
     - **Process 3 (second fresh OS process):** Verified revoked session remained `None` at `now=1500.0`, and direct SQLite scan of `web_sessions` confirmed neither raw token existed anywhere in the table.
   - **What this proves vs what it does NOT prove:**
     - **Proven:** Real production `SessionStore` + `Database` persistence, deterministic server-side expiry rejection, permanent revocation, and absence of raw tokens across genuine OS process restarts.
     - **Not exercised by this stdlib check:** The Starlette/HTTP layer (`MiniApp.auth`, `MiniApp._guarded`, `MiniApp.logout`, cookie flags/deletion, `initData` signature validation) and full `build_application` startup maintenance (`run_startup_maintenance`), because `starlette` and `pytest` are absent here.
     - **Test suite note:** `tests/test_miniapp_session_persistence.py` covers those ASGI flows (`test_app_session_survives_restart` lines `218–232`, `test_app_logout_survives_restart` lines `234–248`, `test_logout_retry_after_503_revokes_and_persists_across_restart` lines `516–543`) using **process-equivalent reconstruction** (`Database(path)` + `TestClient` re-instantiation in-process), and is currently **BLOCKED** locally (`pytest` / `starlette` missing).

### B.3 DOC-01 Independent Verdict
- **Verdict:** **`PASS_WITH_NOTES`**
- **Rationale vs Execution Report:** The execution report marked `DOC-01: RESOLVED`. The code reality, SQLite persistence contract, documentation fix in `docs/MINI_APP.md`, and 3-process `Database` + `SessionStore` restart persistence are all confirmed. However, the execution report omitted its inline script text, and full HTTP/ASGI `TestClient` persistence tests (`tests/test_miniapp_session_persistence.py`) remain blocked locally, making **`PASS_WITH_NOTES`** the strictly accurate independent verdict.

---

## C. DOC-02 Findings — Starlette Version Alignment

### C.1 Dependency Manifest Inventory & Configured Versions
- **`requirements.txt`:**
  - `python-telegram-bot[all]==22.8`
  - `httpx==0.28.1`
  - `python-dotenv==1.2.4`
  - `starlette==1.3.1` (line 4)
  - `uvicorn==0.34.0` (line 5)
  - `anyio==4.16.0` (line 9, explicitly documented on lines `6–8` as required for `starlette.concurrency.run_in_threadpool` under `starlette 1.3.1`, which specifies `anyio >=3.6.2,<5`)
- **`requirements-dev.txt`:** `-r requirements.txt`, `pytest==9.0.3`, `pytest-asyncio==1.3.0`, `pyflakes==4.0.3`, `pip-audit==2.10.1`, `bandit==1.9.4`.
- **`tools/katabump-sqlite-canary/requirements.txt`:** Empty (intentionally stdlib-only).
- **`pyproject.toml` / `setup.py` / `setup.cfg` / `constraints.txt` / `Dockerfile`:** None present.
- **Deployment / Startup scripts:** `start.sh` (`42, 56`) checks Python `>= 3.11` and imports `("telegram", "httpx", "dotenv", "starlette", "uvicorn")`; `bot/bootstrap.py:23` enforces `MIN_PYTHON = (3, 11)`.

### C.2 CI Workflow & Matrix Verification
- Directly verified in `.github/workflows/ci.yml`:
  - Job `test` (`lines 17–54`): `strategy.matrix.python-version: ["3.11", "3.13"]` (confirms the execution report's statement), installs `requirements-dev.txt`, and executes `pyflakes`, `pip_audit`, `bandit`, and `pytest`.
  - Job `frontend` (`lines 56–67`): `node-version: "24"`, runs `node --test tests/frontend/*.test.js`.
  - `tests/test_ci_workflow_security.py` (`lines 108–124`) guards both the `["3.11", "3.13"]` matrix and exact `==` pinning in `requirements.txt`.

### C.3 Static Starlette API Review & Blocked Runtime Checks
- **Static API inspection (`bot/web/app.py`, `bot/web/download.py`, `bot/web/runner.py`, `tests/`):**
  - Route registration & dispatch: `Starlette(routes=[Route(...)])`, `JSONResponse`, `Response` (`bot/web/app.py:19–21, 144, 303–447`). No custom ASGI middleware wrappers are registered.
  - Streaming downloads: `OwnedStreamingResponse(StreamingResponse)` + `starlette.concurrency.run_in_threadpool` (`bot/web/download.py:28–29, 170–223`).
  - Lifespan handling: managed explicitly via `bot/web/runner.py::web_server_lifespan` (`uvicorn.Config(..., lifespan="on", proxy_headers=False)`) wired into PTB `post_init` / `post_shutdown` (`bot/app.py:337–383`).
  - Tests: `starlette.testclient.TestClient` imported across Mini App test modules.
- **Installed versions & runtime compatibility (BLOCKED / UNVERIFIED locally):**
  - `python3 -c 'import starlette; print(starlette.__version__)'` → `ModuleNotFoundError: No module named 'starlette'` (exit `1`).
  - `python3 -c 'import anyio; print(anyio.__version__)'` → `ModuleNotFoundError: No module named 'anyio'` (exit `1`).
  - Dependency resolution (`pip install -r requirements-dev.txt`), `pytest`, and `pip_audit` did not run in this container. Manifest consistency **is** established; installed version, dependency resolution, and runtime compatibility against `starlette==1.3.1` are **not** established locally and must be verified by CI job `test` (`Python 3.11` & `3.13`).

### C.4 DOC-02 Independent Verdict
- **Verdict:** **`PASS_WITH_NOTES`**
- **Rationale:** Matches the execution report's cautious finding (`PARTIALLY RESOLVED`): the active documentation mismatch (`docs/MINI_APP.md` §2 `0.41.3` -> `1.3.1` + `anyio 4.16.0`) is accurately aligned to `requirements.txt` without altering pins, while runtime installation, `TestClient`/`pytest`, and `pip-audit` remain explicitly unverified/blocked in this container.

---

## D. Documentation Findings (`docs/MINI_APP.md` & Scope)

1. **`docs/MINI_APP.md` §2 (`lines 40–46`):** Now lists `starlette` `1.3.1`, `uvicorn` `0.34.0`, and `anyio` `4.16.0` matching `requirements.txt:4–9`, accurately describing `anyio`'s role (`run_in_threadpool` for streaming downloads).
2. **`docs/MINI_APP.md` §7 (`lines 170–172`, `207–232`) and §14 (`line 714`):** Both sections now agree completely: sessions are persisted in SQLite `web_sessions` via the single `Database` owner, store only SHA-256 token hashes, enforce server-side expiry and revocation (not permanent session validity; `MINI_APP_SESSION_TTL` defaults to `3600`s, and `DB_PATH` must sit on persistent storage across restarts), and `_mem` in `SessionStore` is fallback-only when `db=None`.
3. **Historical Documentation Preserved:** `grep` across `docs/` confirms only the two historical pre-`OHB2-PHASE1E` snapshots (`docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md:77` and `docs/OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md:110`, both pinned to commit `c41a57ca30558289918cb6883a2872d0826fbfee`) retain `starlette==0.41.3` as historical records. No unrelated docs were altered.
4. **Report Accuracy Check:** `docs/reviews/OHB2-PLAN16-DOCUMENTATION-CONSISTENCY-REPORT.md` honestly separates completed checks from blocked checks (`pytest`, `pyflakes`, `bandit`, `pip_audit`, `starlette`/`anyio` imports, and `INDEPENDENT_REVIEW_NOT_AVAILABLE` at the time of execution).

---

## E. Verification Matrix

| Check | Execution Report Result | Independent Review Result | Evidence Classification & Limitation |
| --- | --- | --- | --- |
| `python3 -m compileall -q bot automation tools main.py tests` | PASS (exit `0`) | **PASS** (exit `0`) | **Independently reproduced.** |
| Python AST parse (`165` files) & unused-import scan | PASS (`AST_OK:165`, zero new unused imports) | **PASS** (`AST_OK:165`; pre-existing re-exports in `bot/web/__init__.py` and `Iterable` in `tests/_real_http.py` only) | **Independently reproduced.** |
| `node --test tests/frontend/*.test.js` | PASS (`280 pass / 0 fail`) | **PASS** (`280 pass / 0 fail`) | **Independently reproduced** (`Node v22.23.2`). |
| Documentation grep (`0.41.3`, `المخزن الحالي في الذاكرة`, `ثابتة عبر إعادة التشغيل`) | PASS (`docs/MINI_APP.md` clean; historical snapshots preserved) | **PASS** | **Independently reproduced.** |
| 3-process SQLite `SessionStore` + `Database` restart check | PASS (`Inline 3-process Python stdlib check`) | **PASS** (`INDEPENDENT_3PROC_SESSIONSTORE_CHECK: PASS`) | Execution report's exact snippet was **report-only evidence**; independently reproduced via 3-OS-process `Database` + `SessionStore` script using package stubs to bypass `bot/web/__init__.py`'s Starlette import. Does **not** cover HTTP/cookie/`MiniApp` routes. |
| `python3 -m pytest -q` | BLOCKED (exit `1`) | **BLOCKED** (exit `1`: `No module named pytest`) | **Blocked in current environment.** Includes `tests/test_miniapp_session_persistence.py` and `tests/test_ci_workflow_security.py`. |
| `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | BLOCKED (exit `1`) | **BLOCKED** (exit `1`: `No module named pyflakes`) | **Blocked in current environment.** |
| `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | BLOCKED (exit `1`) | **BLOCKED** (exit `1`: `No module named bandit`) | **Blocked in current environment.** |
| `python3 -m pip_audit -r requirements-dev.txt` | BLOCKED (exit `1`) | **BLOCKED** (exit `1`: `No module named pip_audit`) | **Blocked in current environment.** |
| Installed `starlette` / `anyio` version check | BLOCKED (exit `1`) | **BLOCKED** (exit `1`: `ModuleNotFoundError`) | **Blocked in current environment.** Manifest consistency verified; runtime compatibility unverified locally. |
| Git status / baseline lineage (`facf1f425...`) | Absent (`.git` missing) | Absent (`.git` missing, exit `128`) | **Blocked / Not applicable** in non-Git container snapshot. |

---

## F. Final Verdict & Closure Suitability

- **Overall Verdict:** **`PASS_WITH_NOTES`**
- **Administrative Closure Assessment:** Plan 06 (`OHB2-PLAN-16-DOCUMENTATION-CONSISTENCY`) is **ready for conditional administrative closure** as a documentation-consistency task (`docs/MINI_APP.md` defects DOC-01 and DOC-02 are accurately fixed against `bot/web/sessions.py`, `bot/db.py`, and `requirements.txt`, with no regressions in `compileall`, AST, or Node frontend tests).
- **Remaining Conditions (to complete full runtime/security verification outside this container):**
  1. Run CI job `test` (`.github/workflows/ci.yml`, Python `3.11` and `3.13` with `requirements-dev.txt`) to verify `starlette==1.3.1` + `anyio==4.16.0` resolution, `pyflakes`, `bandit`, `pip_audit`, and full `pytest` (including `tests/test_miniapp_session_persistence.py` ASGI `TestClient` flows and `tests/test_ci_workflow_security.py`).
  2. In any Git-backed workspace, verify exact working-tree diff against baseline before committing/publishing.

---

## G. Safety Confirmation

- No application source code, tests, dependency manifests (`requirements*.txt`), `docs/MINI_APP.md`, `docs/reviews/OHB2-PLAN16-DOCUMENTATION-CONSISTENCY-REPORT.md`, or `.agent/PROGRESS.md` were modified by this review.
- No existing files were overwritten, deleted, renamed, or reformatted; only this review report (`docs/reviews/OHB2-PLAN16-DOCUMENTATION-CONSISTENCY-INDEPENDENT-REVIEW.md`) was created.
- No Python or Node packages were installed, and the Python environment was not altered.
- No Git write (`init`/`commit`/`push`/`merge`/PR), deployment, production API call, or `MINI_APP_ENABLED` / Autopush activation occurred.
