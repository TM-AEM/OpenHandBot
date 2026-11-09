# OHB2 — Enzonic Deployment Preflight (Personal Single-User)

**Type:** documentation only (preflight + procedure). **Nothing was deployed, uploaded, or executed
against Enzonic.** No file was uploaded, no production secret was configured, no production process
was started, and no Enzonic server/panel control was used (no Back up now, Backups, Reinstall,
Delete, or Egg-switch). No secrets were entered, requested, printed, or stored. No application code,
configuration, test, or deployment script was modified by this task.

| Item | Value |
|---|---|
| TASK_ID | `OHB2-PHASE8-ENZONIC-CONTROLLED-DEPLOYMENT-PREFLIGHT` |
| Repository | `TM-AEM/OpenHandBot` (local `/workspace/project/OpenHandBot`) |
| Branch | `agent/ohb2-audit-remediation` |
| HEAD (candidate) | `c41a57ca30558289918cb6883a2872d0826fbfee` |
| Release baseline | `origin/main` `c1aef66` (tree == `ac35877`, the PR #4 merge) |
| Candidate vs baseline | 3 commits ahead, linear (no divergence) |
| Target host | Enzonic panel — server **Brave Grove** |
| Usage model | Personal, single user (owner only) |
| H1 (SQLite persistence across container recreation) | **SKIPPED / UNVERIFIED** (by user decision) |
| Autopush | **DISABLED / INACTIVE** |
| Production deployment | **NOT AUTHORIZED** (preflight only) |

---

## 1. Scope and authorization boundaries

In scope: verify the release baseline; assess OpenHandBot compatibility with the Enzonic environment
**as asserted by the provider**; document the exact deployment configuration; run local validation
only; and write an operator procedure for a later, separately-approved deployment.

Out of scope and not performed: uploading files; configuring production secrets; starting Telegram
polling or sending Telegram messages; calling OpenHands production APIs; creating/modifying/deleting
production database files; any Enzonic control operation; publish/push/merge/PR.

Provider statements (Python 3.14, persistent volume, restart behavior, reinstall wipe, egg-switch
wipe, `python3 app.py`, WAL/locking support, `/home/container/data/app.db`, always-on) are treated
as **provider assertions, not independently verified behavior**. The user has explicitly chosen to
skip the SQLite canary, so **persistence remains unverified** (see §9).

---

## 2. Release baseline (Phase 1)

- `git rev-parse --show-toplevel` → `/workspace/project/OpenHandBot`.
- Branch `agent/ohb2-audit-remediation`; upstream `origin/agent/ohb2-audit-remediation`.
- HEAD `c41a57ca30558289918cb6883a2872d0826fbfee`.
- `git merge-base HEAD origin/main` → `ac358775edc23bdc38e428430776eaccba8b92eb`.
- `git rev-list --left-right --count origin/main...HEAD` → `1  3` (baseline 1 ahead via the merge
  commit; candidate 3 ahead, linear).
- Working tree: ` M .agent/PROGRESS.md` plus untracked `docs/OHB2_KATABUMP_H1_VALIDATION.md`,
  `docs/OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md`, `tools/`. These are prior-task artifacts and
  are preserved untouched. Ignored: `.openhands/`, `.venv/`, `__pycache__/`, `.pytest_cache/`.
- Autopush: no process running, no crontab entry, `automation/` not imported by the app
  (`grep -rn automation bot/ main.py` → none). **DISABLED / INACTIVE.**
- No fetch, no branch change, no Git write was performed.

The application remains consistent with the approved architectural decisions recorded in
`docs/ZERO_TOUCH_STARTUP.md` §5b and `docs/DEPLOY_KATABUMP.md` (single process, single DB owner,
long polling, no Backup subsystem, tombstones prevent resurrection).

---

## 3. Enzonic compatibility review (Phase 2)

### 3.1 Python 3.14

Verified locally (strongest available evidence, not a provider claim):

- Python **3.14.9** installed via `uv`; all pinned dependencies installed cleanly from
  `requirements.txt` / `requirements-dev.txt` (no build errors, no version conflicts):
  `python-telegram-bot==22.8`, `httpx==0.28.1`, `python-dotenv==1.2.4`, `starlette==0.41.3`,
  `uvicorn==0.34.0`, `pytest==8.4.2`, `pytest-asyncio==1.1.0`, `pyflakes==4.0.3`.
- Full test suite on 3.14.9: **1576 passed, 0 failed, 0 skipped**; `pyflakes` exit 0;
  `compileall` exit 0.
- Dependency metadata `Requires-Python`: `python-telegram-bot>=3.10` (classifiers include 3.14),
  `python-dotenv>=3.10` (3.14 classifier), `starlette>=3.8`, `uvicorn>=3.9`, `httpx>=3.8`,
  `pytest>=3.9` (3.14 classifier), `pytest-asyncio>=3.9` (3.14 classifier), `pyflakes>=3.10`.
  `anyio 4.16.0` requires `>=3.10`.
- No Python 3.12+/3.13-removed/3.14-removed APIs are used: no PEP 594 modules (`cgi`, `crypt`,
  `imghdr`, `telnetlib`, `distutils`, `imp`, …), no `pkgutil.find_loader`/`get_loader`, no
  `asyncio.AbstractChildWatcher` family, no `typing.ByteString`, no legacy `ast` nodes.
- The app's own `MIN_PYTHON = (3, 11)` gate accepts 3.14.

Residual 3.14 risk (LOW): 3.14 emits deprecation warnings from **third-party** libraries only
(`uvicorn` and `starlette` use `asyncio.iscoroutinefunction`, slated for removal in 3.16;
`starlette.testclient` uses a deprecated `anyio.abc.BlockingPortal` alias; `python-telegram-bot`
warns about a future `retry_after` type change). None originate in OpenHandBot code and none are
runtime failures on 3.14. No pinned dependency declares incompatibility with 3.14.

> Note: `pyflakes`/`pytest` are dev-only; production needs only `requirements.txt`.

### 3.2 Resource limits vs. actual panel

Measured locally: peak RSS after importing the full app and all runtime dependencies ≈ **57 MiB**;
installed runtime `site-packages` ≈ **47 MB**; source tree (excluding `.git`, `.venv`, caches)
≈ **1.5 MB**. Against the panel's **1 GiB** disk this is comfortable. Telegram long polling needs
**no inbound port**; the Mini App backend (ASGI/uvicorn) is **off by default** (`MINI_APP_ENABLED=0`),
so no port is required for the initial single-user deployment.

### 3.3 SQLite WAL and locking

OpenHandBot sets `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` at connect
(`bot/db.py`). Verified locally on a nested absolute path (mirroring `/home/container/data/app.db`):
WAL is accepted and `busy_timeout` is set. Whether Enzonic's volume genuinely preserves WAL and
POSIX locks **across container recreation is asserted by the provider and is NOT verified** (H1
skipped).

### 3.4 Entry-point mismatch — **blocker if left unaddressed (P1)**

Enzonic's documented Python startup is **`python3 app.py`**. This repository has **no root
`app.py`**; its entry point is **`main.py`** (with `start.sh` as the unified wrapper). If the panel's
startup command is left at the default `python3 app.py`, startup fails immediately.
**Required action:** set the startup command explicitly (see §6).

---

## 4. Deployment configuration (Phase 3)

### 4.1 Files to upload (exact runtime set)

The runtime import closure from `main.py` (computed by the AST, per `tests/test_deploy_manifest.py`):

```
main.py
bot/__init__.py
bot/app.py  bot/bootstrap.py  bot/config.py  bot/db.py  bot/errors.py
bot/features.py  bot/file_cache.py  bot/files.py  bot/handlers.py
bot/keyboards.py  bot/messages.py  bot/notifier.py  bot/openhands_client.py
bot/outbox.py  bot/sender.py  bot/watcher.py
bot/web/__init__.py  bot/web/app.py  bot/web/clientip.py  bot/web/initdata.py
bot/web/ratelimit.py  bot/web/runner.py  bot/web/services.py  bot/web/sessions.py
bot/web/static/   (index.html, app.js, cost.js, files.js, inbox.js, ops.js, styles.css)
requirements.txt
```

**Upload:** the items above, plus optional reference material (`start.sh`, `README.md`, `docs/`).
**Do NOT upload:** `.env`, `.venv/`, any `*.sqlite3`/`-wal`/`-shm`, `.git/`, `tests/`, `.github/`,
`.openhands/`, `.agent/`, `automation*/` and `automations/`, `tools/`, `__pycache__/`, `*.pyc`.

`start.sh` is optional when the panel installs `requirements.txt` itself; it is recommended because
it re-checks the Python version and package availability before `exec`-ing `main.py` in the same
process (same signals/exit code, single polling owner).

### 4.2 Required environment variables (names only — values never stored here)

Mandatory:

- `TELEGRAM_BOT_TOKEN`
- `OPENHANDS_API_KEY`
- `ALLOWED_TELEGRAM_ID` (owner's numeric Telegram user id; single value for single-user)

Recommended for this deployment:

- `DB_PATH=/home/container/data/app.db` (absolute path on the persistent volume)
- `OPENHANDBOT_AUTO_INSTALL=1` **only if** the panel does not install `requirements.txt` itself
  (needs `pip` + network; do not set it on a panel that already installs).

Optional (leave at defaults unless needed):

- `OPENHANDS_BASE_URL` (default `https://app.all-hands.dev`; must be `https://` for a non-loopback host)
- `LOG_LEVEL` (default `INFO`)
- `WATCHER_INTERVAL` (default `25`, allowed range enforced by config)
- `MINI_APP_ENABLED` (default `0` — leave off for the initial single-user deployment)
- If the Mini App is later enabled: `MINI_APP_URL` (required, public `https://`), `MINI_APP_PORT`,
  `MINI_APP_COOKIE_SECURE=1`, `MINI_APP_ALLOWED_ORIGINS`, `MINI_APP_TRUSTED_PROXIES` (empty = trust
  no forwarding header, fail closed), and the `MINI_APP_*_RATE_*` limits.

### 4.3 Startup command and working directory

- **Recommended startup command:** `sh start.sh` (unified wrapper; version + package checks, then
  `exec python main.py`).
- **Equivalent:** `python3 main.py` (or `python main.py`).
- **Working directory:** the directory that contains `main.py` (Enzonic's container root, e.g.
  `/home/container`). `start.sh` `cd`s to its own directory, so it is safe regardless.
- **Do not** leave the default `python3 app.py` — there is no `app.py`.

### 4.4 Database path and parent-directory creation

- Default is relative `bot_state.sqlite3` (working directory). **For production, set an absolute
  `DB_PATH`** on the persistent volume: `/home/container/data/app.db`.
- `bot/bootstrap.py::_check_db_path` creates the parent directory (`mkdir(parents=True,
  exist_ok=True)`, idempotent, non-destructive), rejects a `DB_PATH` that points at a directory, and
  fails clearly if the parent is not writable. It does **not** create or delete the DB file itself.
- Verified locally on a nested path (`…/data/app.db`): parent auto-created, `bootstrap=READY`.

### 4.5 SQLite WAL and locking configuration

- Set in code: `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`; single connection, single
  process → single writer. Startup runs `PRAGMA quick_check` + `PRAGMA optimize` +
  `wal_checkpoint(TRUNCATE)`; shutdown checkpoints then closes.
- Because the provider asserts (but does not prove) WAL/POSIX-lock support, keep the DB on the
  **local/persistent volume** (not a network mount). H1 remains unverified.

### 4.6 Process count and single-instance requirement

- **Exactly one process** must own Telegram `getUpdates`. The app never spawns children
  (no `subprocess`/`multiprocessing`/`os.exec` in the startup path). `main.py` runs one
  `run_polling(drop_pending_updates=True)` loop; the Mini App backend, if enabled, runs inside the
  **same** process (no second worker). Do not run two instances against the same token/DB.

### 4.7 ASGI and Telegram polling startup behavior

- Telegram long polling starts immediately after `_post_init` (recovery → workers → polling).
- Mini App backend (ASGI/uvicorn) starts **only** when `MINI_APP_ENABLED=1`; it shares the same DB
  and process. Off by default.
- `drop_pending_updates=True` is intentional: updates accumulated while the bot was down are
  dropped (accepted for single-user use; prevents stale-command floods and duplicate orders).

### 4.8 Graceful shutdown

`_post_shutdown` stops workers/watcher/notifier, closes the httpx client, checkpoints WAL
(`wal_checkpoint(TRUNCATE)`), then closes the DB. A clean stop/start therefore returns WAL data to
the main DB and truncates the WAL file.

### 4.9 Logging and error reporting

Log level from `LOG_LEVEL`. Secrets are registered and redacted; the bootstrap status line prints
names/flags only. Prompt text is not fully logged. A startup failure exits non-zero with a clear
message (no silent start).

### 4.10 Health / readiness checks

Available **only when the Mini App is enabled** (`MINI_APP_ENABLED=1`), on `MINI_APP_PORT`:
`GET /health` (liveness, fixed 200), `GET /ready` (200 when DB verified + workers up, else 503),
`GET /status` (bounded diagnostics). With the Mini App off (recommended initially), there is no HTTP
surface — monitor via process liveness and panel logs.

### 4.11 Safe handling of missing/malformed configuration

`bot/config.py` fails fast with a clear `ConfigError` for missing `TELEGRAM_BOT_TOKEN`,
`OPENHANDS_API_KEY`, `ALLOWED_TELEGRAM_ID`; malformed token/key shape; non-`https` external
`OPENHANDS_BASE_URL`; out-of-range `WATCHER_INTERVAL`; bad `LOG_LEVEL`/`MINI_APP_PORT`; and
`MINI_APP_ENABLED=1` without `MINI_APP_URL`. No silent startup.

### 4.12 Autopush / Backup cannot be silently activated (verified)

- The application reads **no** `AUTOPUSH_*` / `BACKUP*` / `SNAPSHOT` / `RESTORE` environment
  variables (`grep` over `bot/`, `main.py`, `start.sh` → none). Those keys exist only inside the
  standalone `automation/autopush/main.py`, which the app does not import.
- No Backup feature/sub-system exists in operational code, routes, startup, workers, config,
  dependencies, or UI. `tests/test_security_invariants.py` enforces that the core does not import a
  backup module.

---

## 5. Personal single-user risk assessment (Phase 4)

### 5.1 What is stored in SQLite (personal data)

The single DB file (`app.db`) holds: watched-conversation list; per-user routing state (`user_state`,
including `awaiting_*` prompt routing); the prompt outbox (`outbox`, including not-yet-delivered
prompts and their text); chat-creation jobs (`creation_jobs`); local completion tracking
(`completion_pending`); notification state/preferences (`notification_state`, `notifier_pending`,
`notifier_retry_not_before`); a notification audit inbox (`notification_inbox`); settings
(`settings`); and deletion tombstones (`deleted_conversations`). The **conversation content itself
lives on OpenHands**, not locally.

### 5.2 What is lost if the database disappears

If `app.db` is lost, the following local state is lost: the watched list; pending/routed prompts
(including undelivered outbox text); pending chat-creation jobs; notification preferences and
delivery bookkeeping; local settings; and the deletion tombstones (so previously deleted chats could
reappear in the local list until deleted again). Conversations on OpenHands are unaffected, but the
bot's local follow-ups/settings must be reconfigured from scratch. **The user acknowledges this
risk explicitly.**

### 5.3 Risks reduced by single-user operation

- Only one trusted principal (the owner) authenticates; no multi-tenant data isolation to get wrong.
- No public write surface when the Mini App is disabled; no inbound port required.
- Lower exposure to abuse/rate-limit pressure; smaller data footprint.

### 5.4 Risks unchanged by single-user operation

- **Data durability**: single-user does not make persistence unimportant — losing `app.db` still
  loses the owner's own state. H1 (SQLite persistence across container recreation) remains
  **SKIPPED / UNVERIFIED**.
- **Reinstall / egg-switch** can wipe files (provider assertion) → total local-state loss.
- **Single-instance discipline**: running two instances against one token/DB causes duplicate polling
  and DB contention.
- **Secret handling**, **ownership/authorization checks**, and **data-integrity safeguards** remain
  fully required and are **not** weakened.
- **H1 gap**: normal stop/start is asserted to preserve files, but this is not independently proven.

### 5.5 Constraints honored

- H1 remains SKIPPED / UNVERIFIED — no claim of verified persistence is made anywhere here.
- **No Backup or alternative backup subsystem** was introduced (permanent decision). The only
  durability guidance is ordinary OS-level practice on the persistent volume, and it is explicitly
  **not** an application feature.

---

## 6. Local validation results (Phase 5)

All commands run locally; no production credentials or external production services were used.

| Check | Command | Result |
|---|---|---|
| Python 3.13 (repo venv) pytest | `.venv/bin/python -m pytest -q` | **1576 passed**, 0 failed, 0 skipped, exit 0 |
| Python 3.14.9 pytest | `/tmp/py314venv/bin/python -m pytest -q` | **1576 passed**, 0 failed, 0 skipped, exit 0 |
| Python 3.13 pyflakes | `.venv/bin/python -m pyflakes bot/ main.py tests/` | exit **0** |
| Python 3.14.9 pyflakes | `/tmp/py314venv/bin/python -m pyflakes bot/ main.py tests/` | exit **0** |
| Compile (3.14.9) | `… -m compileall -q bot/ main.py` | exit **0** |
| Frontend (Node v24.21.0) | `node --test tests/frontend/*.test.js` | **143 pass**, 0 fail, exit 0 |
| Deploy manifest + config + bootstrap + zero-touch + security (3.14.9) | `… -m pytest -q tests/test_deploy_manifest.py tests/test_config.py tests/test_bootstrap.py tests/test_bootstrap_logging.py tests/test_start_script.py tests/test_zero_touch_contract.py tests/test_zero_touch_lifecycle.py tests/test_env_precedence.py tests/test_security_invariants.py` | **86 passed**, exit 0 |
| WAL/locking on nested absolute path | sqlite3 on `…/data/app.db` | `journal_mode=wal`, `busy_timeout=5000` |
| Parent-dir auto-create | `prepare_runtime` with `…/data/app.db` | `bootstrap=READY`, parent created |
| Memory footprint | import full app + deps | peak RSS ≈ **57 MiB** |

Environment limitations (honest):

- **Python 3.11 not installed locally** → 3.11 is covered by CI only (declared, not re-run here).
- **Python 3.14 was installed locally via `uv`** for verification; this is a local interpreter, not
  the Enzonic runtime. It is strong evidence but not a substitute for a smoke test on the host.
- No SAST/SCA tooling in the repo → NOT RUN.
- Enzonic-specific behavior (persistence, egg switching, panel install) is **not testable from here**
  → UNVERIFIED.

---

## 7. H1 status

**SKIPPED / UNVERIFIED.** The SQLite canary was intentionally not run. Persistence of `app.db`
across container recreation on Enzonic is **not** verified. Provider statements are assertions, not
evidence. Nothing in this document claims verified persistence.

## 8. Autopush status

**DISABLED / INACTIVE.** No process, no schedule, not imported by the app, and no deployment
configuration activates it.

---

## 9. Deployment blockers and risks

| # | Severity | Item | Status / mitigation |
|---|---|---|---|
| B1 | **P1 (blocker if unaddressed)** | Enzonic default `python3 app.py` fails — no `app.py` | Set startup command to `sh start.sh` (or `python3 main.py`). |
| B2 | P2 | H1 persistence across container recreation unverified | Accepted by user for personal single-user use; keep DB on the persistent volume; do not use Reinstall/egg-switch. |
| B3 | P2 | Provider asserts WAL/POSIX locking | Keep DB on local/persistent volume; no network mounts; single instance. |
| B4 | P2 | Reinstall / egg-switch can wipe files | Never use those controls; if used, local state is lost (no Backup subsystem by design). |
| B5 | P3 | Mini App off ⇒ no `/health` endpoint | Monitor via process liveness + panel logs; enable Mini App later only with `MINI_APP_URL`. |
| B6 | P3 | 3.14 deprecation warnings from third-party libs | Non-blocking; no OpenHandBot code affected. |

No P0 blocker. B1 is resolved by configuration, not by code.

---

## 10. Ordered manual deployment procedure (for the user, later)

> Prerequisite: separate explicit approval to deploy. Do not use Reinstall, Delete, or egg-switch.
> Never enter secrets anywhere except the panel's Environment Variables UI.

1. In the Enzonic panel, open server **Brave Grove** and confirm the runtime is Python (3.14).
2. Upload the **runtime set** from §4.1 (ZIP or SFTP): `main.py`, the full `bot/` tree including
   `bot/web/static/`, and `requirements.txt`. Optionally also `start.sh`, `README.md`, `docs/`.
   Do **not** upload `.env`, `*.sqlite3`, `.git/`, `tests/`, `automation*/`, `tools/`, caches.
3. Set the **startup command** to `sh start.sh` (or `python3 main.py`). Do **not** keep `python3 app.py`.
4. Create the DB directory: ensure `/home/container/data` exists (the app also creates it
   automatically, but pre-creating avoids ambiguity).
5. In **Environment Variables**, add (values are yours; they are not recorded here):
   `TELEGRAM_BOT_TOKEN`, `OPENHANDS_API_KEY`, `ALLOWED_TELEGRAM_ID`,
   `DB_PATH=/home/container/data/app.db`. Leave `MINI_APP_ENABLED=0` for now.
6. Ensure dependency installation: if the panel installs `requirements.txt` automatically, do
   nothing; otherwise add `OPENHANDBOT_AUTO_INSTALL=1` (needs `pip` + network) or install once
   manually.
7. Enable **Always-On / Auto-Restart** if the panel offers it (platform setting, not a repo change).
8. Start the server and read the logs. Expect a `bootstrap status: bootstrap=READY …` INFO line and
   Telegram polling to begin; no secrets should appear in the log.
9. Verify with the owner account only: send `/start` in Telegram and confirm a reply. (This is the
   first moment any Telegram production traffic occurs — it requires the user's own action.)
10. Record the exact deployment outcome (host, panel version, Python version, DB path) for the
    post-deployment record. Do **not** use Back up now / Backups / Reinstall / Delete / egg-switch.

---

## 11. Governance compliance

- No file uploaded, no production secret configured, no production process started, no Enzonic
  control used. No publish/push/merge/PR. No secrets requested, printed, or stored.
- Existing repository work and protected paths (`.openhands/`, `.agent/`, `automation/`) preserved
  untouched; only this documentation file and `.agent/PROGRESS.md` were written.
- Architecture unchanged. No Backup subsystem added. Autopush left DISABLED / INACTIVE.
- H1 recorded as SKIPPED / UNVERIFIED; no verified-persistence claim is made.

---

## 12. Final recommendation

**PREFLIGHT_READY_WITH_RISKS** — configuration is fully specified and locally validated (including
Python 3.14), and the only true configuration blocker (B1, the `app.py` entry point) is resolved by
setting the startup command. The residual risk is data durability: **H1 is SKIPPED / UNVERIFIED**,
and reinstall/egg-switch can wipe files. This is acceptable for a personal single-user deployment
**only** with the user's explicit acknowledgement, and it does **not** mean the deployment is
approved. Actual deployment requires a separate, explicit approval.
