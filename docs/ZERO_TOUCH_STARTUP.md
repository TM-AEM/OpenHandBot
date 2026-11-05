# OHB2-N10-22 — Zero-Touch Startup Contract

> **Scope:** application readiness for a genuinely zero-touch startup (upload project files +
> configured runtime environment → the app validates, prepares, initializes, and starts by itself).
> **NOT** a deployment. This document is the *explicit* contract derived from the actual repository —
> it describes what the code does and the exact boundaries of it.
>
> The runtime core has **no backup subsystem**: there is no backup module, no backup config, and no
> backup component anywhere in the tree.

---

## 0. What "zero-touch" means here (and what it does NOT)

The operator does exactly two things:

1. Upload the **runtime file set** (see §6) to the hosting working directory.
2. Set the **required environment variables** in the hosting panel (see §2).

Everything else is automatic at the startup entry point: environment validation, runtime-directory
preparation, database open/initialize/integrity-safety, application + worker wiring, and Telegram
long-polling startup.

**Entry point (OHB2-N10-23):** the recommended single entry point is **`sh start.sh`** — a thin
wrapper that (1) runs from the script directory, (2) validates Python ≥ 3.11, (3) validates that the
runtime dependencies are importable, (4) optionally installs them only when `OPENHANDBOT_AUTO_INSTALL=1`
and something is actually missing, and (5) `exec`s `python main.py` (same process, signals + exit code
propagated). `python main.py` remains a fully supported direct entry point with identical behavior.

**Dependency installation is NOT claimed as automatic.** The repository *can* install dependencies via
`start.sh` when explicitly enabled, but whether the hosting platform installs `requirements.txt`
itself is an unverified platform fact (§5.3).

---

## 1. Startup sequence (implementation-level)

Entry point: `main.py::main()` (run as `python main.py`).

| # | Step | Code | Failure behavior |
| --- | --- | --- | --- |
| 1 | **Process entry** | `main.main()` | — |
| 2 | **Early logging + secret redaction** (before any check) | `bot.bootstrap.setup_logging()` | never fatal |
| 3 | **Runtime/dependency validation** — Python ≥ 3.11 | `bot.bootstrap.check_python()` | `BootstrapError` → clear message, exit 1 |
| 4 | **Config load + validation** (no secret values printed) | `bot.config.load_config()` | `ConfigError` → clear message, exit 1 |
| 5 | **Runtime dir + DB path preparation** (idempotent) | `bot.bootstrap._check_db_path()` | `BootstrapError` → exit 1 |
| 6 | **Application build** (one `Application`, DB open, Mini App wire) | `bot.app.build_application()` | `ConfigError` on Mini App misconfig; else fatal only on real programming errors |
| 7 | **Worker lifecycle start** (outbox, creation, watcher, notifier) | `bot.app._post_init()` | isolated per-worker guards; failures logged |
| 8 | **Telegram polling start** (single owner) | `main.main()` → `app.run_polling(drop_pending_updates=True)` | platform-supervised |
| 9 | **Graceful shutdown** | `bot.app._post_shutdown()` | closes workers, HTTP client, checkpoints + closes DB |

Health/readiness reporting today is the **bootstrap status log line** (`bootstrap status: ...`, INFO,
no secrets). The public `/health` route of the Mini App is unrelated and unchanged (§2).

---

## 2. Configuration contract

Derived from `bot/config.py::load_config`. "Required" = startup fails cleanly if absent/malformed.

### 2.1 Required for startup

| Variable | Notes |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Must match `123456:ABC…` shape; the single polling owner's token. |
| `OPENHANDS_API_KEY` | ≥ 8 chars, no whitespace/control chars. |
| `ALLOWED_TELEGRAM_ID` | Exactly one positive integer (Decision 5). Becomes `owner_id`. |

### 2.2 Optional (safe defaults; never block startup)

| Variable | Default | Notes |
| --- | --- | --- |
| `OPENHANDS_BASE_URL` | `https://app.all-hands.dev` | Must be `https://` unless loopback (local dev). |
| `LOG_LEVEL` | `INFO` | One of DEBUG/INFO/WARNING/ERROR/CRITICAL. |
| `WATCHER_INTERVAL` | `25` | 5..3600 seconds. |
| `DB_PATH` | `bot_state.sqlite3` | **Set an absolute path in production** (see §4). |

### 2.3 Feature-specific (only validated when the feature is enabled)

| Variable | Default | Notes |
| --- | --- | --- |
| `MINI_APP_ENABLED` | `0` (off) | When `0`/absent, none of the Mini App settings matter. |
| `MINI_APP_URL` | (empty) | **Required when `MINI_APP_ENABLED=1`** — must be a public non-loopback `https://` URL (OHB2-N10-22 fix). |
| `MINI_APP_PORT` | `12000` | 1..65535. |
| `MINI_APP_INITDATA_MAX_AGE` | `300` | positive int (seconds). |
| `MINI_APP_SESSION_TTL` | `3600` | positive int (seconds). |
| `MINI_APP_COOKIE_SECURE` | `1` | bool. |
| `MINI_APP_ALLOWED_ORIGINS` | (derived) | comma list of `scheme://host[:port]`. |
| `MINI_APP_AUTH_RATE_PER_MINUTE` / `_PER_HOUR` / `MINI_APP_API_RATE_PER_MINUTE` / `MINI_APP_RATE_MAX_KEYS` | `10` / `30` / `60` / `4096` | positive ints. |

### 2.4 No backup configuration

The core reads **no** backup configuration. `BACKUP_*` / `SFTP_*` / `GDRIVE_*` variables are ignored by
the startup path (their presence or absence cannot affect startup), and no backup source exists in the
repository.

### 2.5 Unsupported / intentionally deferred

- A second Telegram polling owner: the design is single-process/single-poller (§3.3).
- Self-installation of Python packages (platform's responsibility — §5.3).

---

## 3. Guarantees

### 3.1 Idempotent startup
`prepare_runtime()` is pure aside from creating the DB parent dir (`exist_ok=True`). Repeated calls /
restarts are safe. Verified: `tests/test_zero_touch_lifecycle.py`, `tests/test_env_precedence.py`.

### 3.2 Database safety (no destructive init)
`bot.db.Database.__init__` opens the path with `check_same_thread=False`, sets
`PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`, then `CREATE TABLE IF NOT EXISTS` +
additive `ALTER TABLE ADD COLUMN` migrations. There is **no `DROP`/`DELETE`/recreate** of the DB or
tables. An existing DB is opened in place and its rows preserved. `run_startup_maintenance()`
(`quick_check` → `optimize` → `wal_checkpoint(TRUNCATE)`) is non-destructive and never raises.
Verified: `tests/test_zero_touch_lifecycle.py::test_database_new_init_and_restart_preserves_data`,
`tests/test_security_invariants.py::test_db_wal_and_busy_timeout_intact`.

### 3.3 Single application process / single polling owner
`main.py` builds exactly one `telegram.ext.Application` and calls `run_polling` once. All background
workers (outbox, creation, watcher, notifier) are **in-process `asyncio` tasks** with `bot_data`
"create-once" guards — no `subprocess`, `os.exec*`, `multiprocessing`, or thread spawning anywhere in
`main.py`, `bot/` (verified by
`tests/test_security_invariants.py::test_no_second_process_or_exec_in_startup_path`). Duplicate
`post_init` calls do **not** create duplicate workers (verified: `test_zero_touch_lifecycle.py`).

### 3.4 Single SQLite owner
One `Database` instance per process (created in `build_application`, stored in `bot_data["db"]`,
closed in `_post_shutdown`). WAL + `busy_timeout=5000` allow concurrent in-process access without
`database is locked`.

### 3.5 Secret safety
`bot.errors.register_secrets()` + `RedactingFilter` scrub registered secrets from every log record
(message, args, and traceback). `load_config` and the bootstrap status emit **names/flags only** —
never values. Verified: `tests/test_security_invariants.py::test_bootstrap_status_has_no_secret`,
`tests/test_env_precedence.py::test_no_secret_from_dotenv_leaks_into_status`,
`tests/test_bootstrap_logging.py`.

### 3.6 Mini App stays in-process
When `MINI_APP_ENABLED=1`, `bot.app._wire_mini_app` runs a Uvicorn task inside the **same** process
(`bot/web/runner.py`), sharing the same DB; it never starts a second `main.py`. When disabled
(default), no server task is created. Verified: `tests/test_miniapp_integration.py`.

### 3.7 No backup subsystem in the core
`main.py`, `bot/bootstrap.py`, and `bot/app.py` import **no** backup module and construct **no**
backup component, and the repository contains no backup source at all. Verified by an
import-check (`tests/test_zero_touch_contract.py::test_core_has_no_backup_references`) and the
isolated manifest test (`tests/test_deploy_manifest.py`).

---

## 4. DB path guidance

`DB_PATH` defaults to the relative `bot_state.sqlite3` (resolved against the working directory). For
a stable zero-touch deployment, set an **absolute** path (e.g. `/home/container/bot_state.sqlite3`)
so the bot and any operator tooling refer to the same file regardless of cwd.

---

## 5. Hosting compatibility assessment (Katabump Free)

The selected target is **Katabump Free**, bot-only, Telegram long-polling, `MINI_APP_ENABLED=0`,
one process. Distinguish carefully:

### 5.1 Repository implementation — VERIFIED
- One process, one poller, in-process workers (§3.3).
- No inbound port needed for long-polling; Mini App disabled by default.
- Safe DB init + WAL + busy_timeout (§3.2).
- No reliance on persistent storage for correctness of startup (a fresh DB is initialized if absent).
- No second process for the Mini App.
- Core startup has no backup subsystem (§3.7).

### 5.2 Hosting configuration — DOCUMENTED (operator-facing)
- Upload list and env vars: `docs/DEPLOY_KATABUMP.md`.
- Startup command: `sh start.sh` (or `python main.py`).

### 5.3 Hosting behavior — REQUIRES AN OPERATOR-SIDE TEST (unverified here)
- **Dependency installation:** Katabump is *documented* to install from `requirements.txt` on start,
  but this has **not** been verified against a live server. `requirements.txt` pins
  `python-telegram-bot[all]`, `httpx`, `python-dotenv`, `starlette`, `uvicorn`. **Uploading files alone
  is NOT sufficient** unless the platform actually installs these.
- **Process supervision / restart:** that the platform restarts the single process after a crash or
  host renewal is a platform behavior, not verified from the repository.
- **Filesystem persistence:** the free tier has no documented durable volume — the DB may be lost on
  host deletion.
- **Port/ingress:** only relevant when `MINI_APP_ENABLED=1`; not used in the bot-only target.

> **Readiness statement:** the *application* is zero-touch-ready. **Production readiness is not
> claimed** until §5.3 is confirmed by a real operator-side deploy.

---

## 6. Required runtime file set

Per `docs/DEPLOY_KATABUMP.md` and enforced by `tests/test_deploy_manifest.py` (AST import closure
from `main.py` + an isolated `import main` with only these files):

```
main.py
start.sh        (recommended single entry point — OHB2-N10-23)
requirements.txt
bot/            (all *.py + bot/web/static/)
docs/           (reference only)
```

Excluded: `.env`, `.venv/`, `*.sqlite3` (+ `-wal`/`-shm`), `.git/`, `tests/`, `automation*/`,
`automations/`, `__pycache__/`, `.github/`, `.openhands/`.

---

## 7. Verification (this task)

- Full pytest, pyflakes, Node tests — see the publication report for exact commands/results.
- Key tests: `tests/test_zero_touch_contract.py` (fresh env-only startup, feature-neutral status,
  core has no backup references, single app/no second process, Mini App off, DB preserved, secrets
  safe), `tests/test_zero_touch_lifecycle.py` (core worker lifecycle + shutdown), and
  `tests/test_deploy_manifest.py` (import closure is sufficient).
