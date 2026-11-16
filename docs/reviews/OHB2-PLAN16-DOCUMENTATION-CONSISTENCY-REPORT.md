# OHB2-PLAN-16-DOCUMENTATION-CONSISTENCY — Execution & Verification Report

- **Task ID:** `OHB2-PLAN-16-DOCUMENTATION-CONSISTENCY-EXECUTION-01`
- **Plan ID:** `OHB2-PLAN-16-DOCUMENTATION-CONSISTENCY` (OpenHandBot Plan 06)
- **Date:** 2026-11-16
- **Outcome Summary:** `DOC-01: RESOLVED` | `DOC-02: PARTIALLY RESOLVED` | `INDEPENDENT_REVIEW_NOT_AVAILABLE`

---

## 1. Baseline & Environment State

- **Workspace root:** `/app/applet`
- **Git status / HEAD:** `.git` directory is **absent** (`git status` and `git rev-parse HEAD` exit `128`: `fatal: not a git repository (or any of the parent directories): .git`). Relationship to historical baseline `facf1f42578a20a4a37e220eca016ce3d534e750` cannot be established locally; no Git repo was created or modified.
- **Runtimes available:** `Python 3.10.12` (`/usr/bin/python3`), `Node v22.23.2`.
- **Environment limitations:** `pip`, `ensurepip`, and third-party Python packages (`pytest`, `pytest-asyncio`, `pyflakes`, `bandit`, `pip_audit`, `starlette`, `uvicorn`, `anyio`, `httpx`, `python-telegram-bot`, `python-dotenv`) are **not installed** in this container (`ModuleNotFoundError`). Note that production runtime and CI target Python `>= 3.11` (`bot/bootstrap.py::MIN_PYTHON = (3, 11)`, `.github/workflows/ci.yml` matrix `["3.11", "3.13"]`).
- **Pre-existing architecture & security state preserved:**
  - Single-process architecture (`main.py` / `bot/app.py`) with single authoritative SQLite `Database` owner (`bot/db.py`).
  - `MINI_APP_ENABLED` remains `False` by default (`bot/config.py`), gated in `bot/app.py::_wire_mini_app`.
  - Autopush (`automation/autopush/`) remains disabled/inactive and unimported by runtime code.
  - Prior Plan 05 (`OHB2-PLAN-15`) deliverables and `.agent/PROGRESS.md` history preserved untouched.

---

## 2. DOC-01 Findings — Mini App Session Persistence (`docs/MINI_APP.md`)

### 2.1 Code & Schema Reality
Inspected `bot/web/sessions.py`, `bot/db.py`, `bot/web/app.py`, `bot/app.py`, `bot/config.py`, `bot/web/services.py`, `bot/web/ratelimit.py`, and `tests/test_miniapp_session_persistence.py`:

- **SQLite table (`bot/db.py:732–739`):** `web_sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL, profile TEXT NOT NULL DEFAULT '{}')` with index `idx_web_sessions_expires`, created via non-destructive `CREATE TABLE IF NOT EXISTS`.
- **Single-owner DB methods (`bot/db.py:2536–2573`):** `add_web_session`, `get_web_session` (enforcing `expires_at > now` server-side), `delete_web_session`, `prune_web_sessions`, `count_web_sessions`. Best-effort cleanup also runs on `SessionStore.create()` (`bot/web/sessions.py:86`) and startup maintenance (`bot/db.py::run_startup_maintenance`).
- **Token handling & fail-closed guarantees (`bot/web/sessions.py:30–141`, `bot/web/app.py:133, 211–224, 455–469, 512–610`):**
  - Random 32-byte opaque token (`secrets.token_urlsafe(32)`) sent only in `HttpOnly; SameSite=Strict; Path=/` cookie (`ohb_session`, `Secure` configurable via `MINI_APP_COOKIE_SECURE`).
  - Only SHA-256 hex digest (`hash_token`) is stored in SQLite (`web_sessions`); raw tokens are never persisted or logged.
  - `MiniApp.__init__` (`bot/web/app.py:133`) always initializes `SessionStore(config.mini_app_session_ttl, db)`.
  - `SessionStore._mem: dict[str, Session]` (`bot/web/sessions.py:61`) is **only** a standalone/test fallback when `db is None` (`bot/web/sessions.py:13–14, 55, 74, 93, 130, 143`), never used when `Database` is wired in production.
  - Rate-limit buckets (`bot/web/ratelimit.py::SlidingWindowLimiter`) remain per-process in-memory sliding windows (keyed by `hash_token(session.token)` or client IP) and hold no session auth state.
  - Logout deletes the `web_sessions` row; on DB failure `SessionStore.revoke()` returns `False` and `logout` fails explicitly (`503 logout_failed`) rather than faking revocation.

### 2.2 Documentation Defect & Resolution
- **`docs/MINI_APP.md` §7 (`lines 170–172`, `207–232`)** accurately documented persistent SQLite sessions (`OHB2-PHASE1A`).
- **`docs/MINI_APP.md` §14 (`line 713`)** contained a stale contradictory backlog bullet:
  `- جلسات **ثابتة عبر إعادة التشغيل** (المخزن الحالي في الذاكرة ⇒ أي restart بيلغي الجلسات).`
- **Fix applied (`docs/MINI_APP.md:714`):** Replaced the stale bullet with an accurate status entry matching §7 and `bot/web/sessions.py`: durable sessions are already implemented in SQLite `web_sessions` via the single `Database` owner, survive process restart when `DB_PATH` resides on persistent storage, and `_mem` in `SessionStore` is fallback-only when `db=None` in standalone tests.

---

## 3. DOC-02 Findings — Starlette Version Mismatch

### 3.1 Dependency Inventory
- **`requirements.txt`:**
  - `python-telegram-bot[all]==22.8`
  - `httpx==0.28.1`
  - `python-dotenv==1.2.4`
  - `starlette==1.3.1` (line 4)
  - `uvicorn==0.34.0` (line 5)
  - `anyio==4.16.0` (line 9, explicitly pinned for `starlette 1.3.1` / `starlette.concurrency.run_in_threadpool` in `bot/web/download.py`)
- **`requirements-dev.txt`:** `-r requirements.txt`, `pytest==9.0.3`, `pytest-asyncio==1.3.0`, `pyflakes==4.0.3`, `pip-audit==2.10.1`, `bandit==1.9.4`.
- **`tools/katabump-sqlite-canary/requirements.txt`:** Intentionally empty (stdlib-only canary).
- **`pyproject.toml` / `setup.py` / `constraints.txt` / `Dockerfile`:** None present.
- **`.github/workflows/ci.yml`:** Installs `requirements-dev.txt` on Python `["3.11", "3.13"]`; enforces `pyflakes`, `pip_audit`, `bandit`, and `pytest`.
- **`tests/test_ci_workflow_security.py`:** Enforces exact `==` pinning in `requirements.txt` (`test_runtime_dependencies_are_exactly_pinned`) and CI security checks.

### 3.2 Historical Context & Documentation Alignment
- `.agent/PROGRESS.md` (`OHB2-PHASE1E`, lines 288–309) records that `starlette` was upgraded from `0.41.3` to `1.3.1` to resolve 8 security advisories (clearing 14 `pip-audit` advisories), alongside `pytest 9.0.3` and `pytest-asyncio 1.3.0`.
- **Active conflict fixed (`docs/MINI_APP.md:42–44`):** Updated the §2 dependency table from stale `0.41.3` to `1.3.1` (and documented pinned `anyio` `4.16.0` per `requirements.txt:6–9`). No pin in `requirements.txt` or `requirements-dev.txt` was altered.
- **Historical snapshots preserved untouched:**
  - `docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md:77` (`starlette==0.41.3`, `pytest==8.4.2`, `pytest-asyncio==1.1.0`) — historical Phase 8 preflight snapshot against commit `c41a57ca30558289918cb6883a2872d0826fbfee`.
  - `docs/OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md:110` (`starlette==0.41.3`) — historical Phase 6 snapshot against commit `c41a57ca30558289918cb6883a2872d0826fbfee`.
  - Preserved as historical evidence per `AGENTS.md` and Plan 06 non-rewriting rules.

### 3.3 Starlette Runtime Usage & Local Verification Boundary
- **Source inspection (`bot/web/app.py`, `bot/web/download.py`, `bot/web/runner.py`):** Uses `starlette.applications.Starlette`, `starlette.routing.Route`, `starlette.responses.{JSONResponse, Response, StreamingResponse}`, `starlette.concurrency.run_in_threadpool`, and `starlette.testclient.TestClient` in tests.
- **Unverified locally (blocked by container environment):** `starlette` and `anyio` are not installed in this container (`ModuleNotFoundError`), so installed package versions, `TestClient` ASGI suites, `pip-audit` advisory resolution, and live `uvicorn`/`starlette` startup were **not** executed locally and remain `UNVERIFIED` in this container.

---

## 4. Verification Results

| Check | Command | Result | Notes |
| --- | --- | --- | --- |
| Bytecode compilation | `python3 -m compileall -q bot automation tools main.py tests` | **PASS** (exit `0`) | 0 syntax/compile failures |
| Python AST parse & unused imports | Inline Python `ast.parse` across all `.py` files | **PASS** (`AST_OK:165`) | Zero new unused imports introduced |
| Frontend tests | `node --test tests/frontend/*.test.js` | **PASS** (`280 pass / 0 fail`) | Full JS suite clean |
| Real 3-subprocess SQLite session restart | Inline 3-process Python stdlib check against `bot/db.py` + `bot/web/sessions.py` | **PASS** | Process 1 creates active + short-TTL sessions -> Process 2 (fresh OS process) verifies active survives, short expires, `revoke()` succeeds -> Process 3 verifies revocation persists & zero raw tokens in SQLite |
| Documentation grep check | `grep -rnE "0\.41\.3\|المخزن الحالي في الذاكرة\|ثابتة عبر إعادة التشغيل" docs/ README.md requirements*.txt .github/workflows/ci.yml` | **PASS** | `docs/MINI_APP.md` clean; only historical snapshots (`OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md`, `OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md`) remain |
| Python test suite | `python3 -m pytest -q` | **BLOCKED** (exit `1`) | `No module named pytest` (includes `tests/test_miniapp_session_persistence.py` ASGI `TestClient` tests and `tests/test_ci_workflow_security.py`) |
| Static lint | `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | **BLOCKED** (exit `1`) | `No module named pyflakes` |
| SAST | `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **BLOCKED** (exit `1`) | `No module named bandit` |
| Dependency audit | `python3 -m pip_audit -r requirements-dev.txt` | **BLOCKED** (exit `1`) | `No module named pip_audit` |
| Installed Starlette/Anyio check | `python3 -c 'import starlette; print(starlette.__version__)'` | **BLOCKED** (exit `1`) | `ModuleNotFoundError: No module named 'starlette'` (`anyio` likewise absent) |
| Independent review | — | `INDEPENDENT_REVIEW_NOT_AVAILABLE` | Self-review only |

---

## 5. Changed Files & Final Assessment

- **Modified files:**
  1. `docs/MINI_APP.md` (§2 lines 42–44 Starlette `1.3.1` + Anyio `4.16.0`; §14 line 714 session persistence status)
  2. `docs/reviews/OHB2-PLAN16-DOCUMENTATION-CONSISTENCY-REPORT.md` (this report, created)
  3. `.agent/PROGRESS.md` (Plan 06 entry appended; all prior history preserved)
- **No changes made to:** runtime Python/JS code, database schema, `requirements.txt`, `requirements-dev.txt`, `MINI_APP_ENABLED` (`False`), or historical preflight/Phase 6 reports.
- **No Git or deployment actions performed:** no `git commit`, `git push`, PR, merge, deploy, or Mini App / Autopush activation.

### Final Issue Verdicts
- **`DOC-01: RESOLVED`** — Documentation contradiction in `docs/MINI_APP.md` §14 resolved to match §7 and actual `web_sessions` SQLite persistence; real 3-subprocess OS restart verification passed for `Database` + `SessionStore`. Note: full HTTP/ASGI `TestClient` tests in `tests/test_miniapp_session_persistence.py` require `pytest` + `starlette` in CI (Python 3.11 / 3.13).
- **`DOC-02: PARTIALLY RESOLVED`** — `docs/MINI_APP.md` §2 updated to `starlette` `1.3.1` (plus `anyio` `4.16.0`) matching `requirements.txt` without changing dependency pins; however, local runtime package presence, `starlette==1.3.1` API execution, `pytest`, and `pip-audit` verification remain **BLOCKED** in this container and require CI / Python 3.11+ venv execution.
