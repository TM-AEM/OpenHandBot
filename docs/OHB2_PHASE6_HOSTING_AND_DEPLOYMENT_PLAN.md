# OHB2 Phase 6 — Hosting Compatibility & Deployment Plan

**Type:** plan + evidence checklist only. Nothing was deployed, published, or executed against any
provider. No Git write action was performed. No provider account or infrastructure was created.

| Item | Value |
|---|---|
| Repository | `TM-AEM/OpenHandBot` (local path `/workspace/project/OpenHandBot`) |
| Branch | `agent/ohb2-audit-remediation` |
| HEAD | `c41a57ca30558289918cb6883a2872d0826fbfee` |
| Working tree | clean before and after this task |
| Code readiness | verified locally (see §10) |
| Production-hosting readiness | **NOT READY** — H1 (SQLite persistence) is UNVERIFIED |
| Phase 6 verdict | `READY_WITH_NOTES` (code) / `NOT_READY` (production hosting) |

Verdict legend used throughout: `VERIFIED` = proven from source or command output in this
repository; `DOCUMENTED` = stated by an operator-facing doc but not proven here; `UNVERIFIED` =
no evidence; `N/A` = not applicable.

---

## 1. Actual state (Phase 0)

Established from the local repository only (no `fetch`/`pull`, no branch switch):

- Branch: `agent/ohb2-audit-remediation`; HEAD `c41a57c` = `origin/agent/ohb2-audit-remediation`.
- `git status`: clean (`nothing to commit, working tree clean`).
- `c41a57c` exists locally; it is the Phase-5 follow-up commit.
- Phase-4/5 implementation commits present: `b1dd979` (WP1–WP6), `0e2ab56` (PROGRESS), `c41a57c`.
- Merge base with `main`: `c3d5fe8` (main is 5 behind, i.e. the agent branch is ahead).
- Diff vs merge base: 25 files, +1822 / −32 (see `git diff --stat c3d5fe8..HEAD`).
- Ignored/untracked paths that must stay untouched: `.venv/`, `.openhands/`, `.pytest_cache/`,
  `**/__pycache__/` (all `.gitignore`d).

---

## 2. Phase-5 follow-up review (commit `c41a57c`)

Reviewed statically and with focused tests; **no files were modified**.

| # | Review item | Finding |
|---|---|---|
| 1 | Ordering by `updated_at` | `collect_conversations` sorts the **merged** list once, desc, `key=updated_at or ""` (`bot/openhands_client.py`). Missing timestamps sort last. Stable across pages. ✅ |
| 2 | Dedup by stable id | `_dedupe_by_id` keys on `str(id)`, keeps **first occurrence** (newest page), order-preserving. Items without `id` are not merged. ✅ |
| 3 | First-occurrence semantics | Preserved: `seen` guard + `out.append` on first sight. ✅ |
| 4 | Cursor / truncation | Loop follows `next_page_id` bounded by `CONVERSATIONS_MAX_PAGES = 20`; `truncated = bool(page_id)` after the loop — i.e. True only when a further page exists past the cap. No unbounded loop (cap enforced). ✅ |
| 5 | Tombstone filtering across pages | Both list paths apply `_without_deleted` **after** collection, before pagination (`bot/handlers.py`, `bot/web/services.py`). ~~fails closed (returns `[]`) on a DB read error~~ **SUPERSEDED by OHB2-SW03** (see O-2 below): a DB read error now propagates after bounded BUSY/LOCKED retries. ✅ |
| 6 | Mini App deletion/re-engagement docs | `docs/MINI_APP.md` §10 corrected: only `watch` clears the tombstone; `POST …/prompt` is refused `409 conversation_deleted`. Matches `bot/db.py::add_or_group_outbox`. ✅ |
| 7 | Fail-closed then recovery tests | `test_miniapp_list_recovers_after_transient_db_failure` and `test_bot_list_recovers_after_transient_db_failure` assert **explicit failure then recovery** (superseded by OHB2-SW03: the failure is now a 500 / generic message, not an empty list). ✅ |
| 8 | `MINI_APP_TRUSTED_PROXIES` docs/consistency | Validated in `bot/config.py` (`_parse_trusted_proxies`, empty = trust nothing), honoured in `bot/web/clientip.py`; now documented in `.env.example` and `docs/MINI_APP.md` §11. ✅ |

**Observations (non-blocking, accepted as-is):**

- **O-1 (accepted):** with >20 pages the oldest conversations remain unreachable, but this is now
  *visible* (`truncated=True` → the bot prints "(القايمة طويلة…)" and the API returns
  `truncated: true`). Single-owner usage keeps the real count far below the cap. Documented
  behaviour, not a defect.
- **O-2 (accepted, then SUPERSEDED by OHB2-SW03):** `_without_deleted` catches broad `Exception`
  and returns `[]` (fail-closed). The broad catch was a deliberate safety choice, was commented,
  and was covered by tests; the alternative (letting it raise) would surface a 500 and hide less
  safely.

### Superseding decision — OHB2-SW03 (explicit failure + bounded retry)

The user **explicitly authorized superseding** the O-2 / OHB2-AUDIT-FIX-04 / WP4 decision above.
The former behaviour is kept here as the historical record; it is **superseded**, not deleted.

| Aspect | Former (WP4 / OHB2-AUDIT-FIX-04 / O-2) | Current (OHB2-SW03) |
|---|---|---|
| Tombstone DB read error | silently converted to `[]` (fail-closed to empty) | propagates after bounded retries |
| Transient SQLite BUSY (5) / LOCKED (6) | no retry | retried **bounded**: 1 initial + 3 retries, delays `(0.25, 0.5, 1.0)` s |
| Permanent / non-transient error | `[]` | propagated immediately, **no retry** |
| Original exception after exhaustion | discarded | propagated unchanged |
| Mini App response on failure | `200` with `items: []` | `500` `server_error` (generic, no internal detail) |
| Bot response on failure | misleading «ما فيهاش شاتات.» | generic «تعذّر عرض الشاتات دلوقتي، جرّب تاني.» |
| Genuine empty result | `[]` | `[]` (unchanged) |
| All-tombstoned list | `[]` | `[]` (unchanged) |
| F-1 tombstone enforcement | active tombstones excluded | **unchanged** |

- **Shared policy:** the classifier and delays live in `bot/db.py`
  (`is_transient_sqlite_error`, `DEDUPE_RETRY_DELAYS`) and are used by
  `Database.is_deleted_with_retry`; `bot/handlers.py` re-exports them for back-compat.
- **Scope:** limited to the two `_without_deleted` paths (`bot/handlers.py`,
  `bot/web/services.py`), the shared database read/retry helper, and the Mini App route's
  error mapping (`bot/web/app.py`).
- **Not solved here:** Telegram polling acknowledgement and PTB 22.8
  `Application.process_update()` exception swallowing remain a **separate, unresolved**
  architectural issue. This decision does **not** establish that a polling controller can
  observe the failure.
- **Dedupe retry:** `_check_update_processed_with_retry` reuses the shared policy with
  **unchanged** semantics (attempt count, delays, fail-closed, exception handling).


**Verdict — Phase-5 code-level follow-up: ACCEPTED.** No ordering instability, no unbounded
behaviour, no incorrect truncation metadata, no docs/config/runtime inconsistency found.

Focused tests: 194 passed (`tests/test_openhands_client.py`, `tests/test_handlers.py`,
`tests/test_conversation_deletion.py`, `tests/test_resurrection_fix.py`).

---

## 3. Application hosting requirements (from real code)

Every item below cites the exact source that defines it.

| Requirement | Value | Source |
|---|---|---|
| Python | **≥ 3.11** (dev/CI run 3.13) | `bot/bootstrap.py::MIN_PYTHON = (3, 11)`; `start.sh` step 3; CI matrix `["3.11","3.13"]` |
| Install | `pip install -r requirements-dev.txt` (pulls `requirements.txt`) | `AGENTS.md` §1; `requirements-dev.txt` |
| Runtime deps | `python-telegram-bot[all]==22.8`, `httpx==0.28.1`, `python-dotenv==1.2.4`, `starlette==0.41.3`, `uvicorn==0.34.0` | `requirements.txt` |
| Start command | `python main.py` (or `sh start.sh`) | `main.py`; `start.sh` |
| Bot lifecycle | Telegram **long polling** (`run_polling(drop_pending_updates=True)`) | `main.py` |
| Mini App lifecycle | Starlette + Uvicorn started as an **asyncio task in the same process**, gated by `MINI_APP_ENABLED` | `bot/app.py` (`web_server_lifespan`), `bot/web/runner.py` |
| Process count | **exactly one** (one poller, in-process workers). Multi-replica **not supported** | `bot/app.py` (worker guards), `docs/ZERO_TOUCH_STARTUP.md` §3.3 |
| Host bind | `0.0.0.0` (all interfaces) | `bot/app.py`: `web_server_lifespan(web_app, "0.0.0.0", config.mini_app_port)` |
| Port | `MINI_APP_PORT`, default `12000` | `bot/config.py` |
| Health path | `GET /health` → liveness (constant `200`, no DB/worker claim) | `bot/web/app.py::health` |
| Readiness path | `GET /ready` → `200`/`503` (DB integrity + no startup blocker + workers running) | `bot/web/app.py::readiness`, `::ready` |
| Required env names | `TELEGRAM_BOT_TOKEN`, `OPENHANDS_API_KEY`, `ALLOWED_TELEGRAM_ID` | `bot/config.py::load_config` |
| Optional env names + defaults | `OPENHANDS_BASE_URL` (`https://app.all-hands.dev`), `LOG_LEVEL` (`INFO`), `WATCHER_INTERVAL` (`25`, 5–3600), `DB_PATH` (`bot_state.sqlite3`), `MINI_APP_URL` (``), `MINI_APP_ENABLED` (`0`), `MINI_APP_PORT` (`12000`), `MINI_APP_INITDATA_MAX_AGE` (`300`), `MINI_APP_SESSION_TTL` (`3600`), `MINI_APP_COOKIE_SECURE` (`1`), `MINI_APP_ALLOWED_ORIGINS` (``), `MINI_APP_AUTH_RATE_PER_MINUTE` (`10`), `MINI_APP_AUTH_RATE_PER_HOUR` (`30`), `MINI_APP_API_RATE_PER_MINUTE` (`60`), `MINI_APP_RATE_MAX_KEYS` (`4096`), `MINI_APP_TRUSTED_PROXIES` (``) | `bot/config.py`, `.env.example` |
| DB path | `DB_PATH`; relative → resolved against the **process CWD**; absolute recommended for production | `bot/config.py`; `docs/ZERO_TOUCH_STARTUP.md` §4 |
| DB dir creation | Parent dir auto-created (`mkdir(parents=True, exist_ok=True)`), never deletes data | `bot/bootstrap.py::_check_db_path` |
| WAL behaviour | `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000`; needs `-wal`/`-shm` siblings on the **same** filesystem | `bot/db.py::Database.__init__` |
| Persistent FS | Required for durable state (the SQLite file + sidecars) | `bot/db.py`; `docs/DEPLOY_KATABUMP.md` |
| Writable dirs | The DB parent dir must be writable; `.env` is read from CWD if present | `bot/bootstrap.py::_check_db_path`, `::prepare_runtime` |
| CPU / memory | Small: one process, no heavy compute. Platform free tiers of 256–512 MB RAM are enough (measured host needs are tiny) | `docs/ZERO_TOUCH_STARTUP.md` §5.3 |
| Network egress | HTTPS to `api.telegram.org` (Telegram Bot API) and `https://app.all-hands.dev` (OpenHands API). No inbound port needed for the bot; inbound HTTPS only if the Mini App is enabled | `bot/config.py`, `bot/notifier.py`, `bot/openhands_client.py` |
| Graceful shutdown | `wal_checkpoint(TRUNCATE)` then `db.close()`; Mini App server closed in `post_shutdown` | `docs/OPERATIONS_RUNBOOK.md`; `bot/app.py` |
| Runtime limitations | No backup subsystem (permanent); no second process; no `exec` (single PID) | `docs/ZERO_TOUCH_STARTUP.md` §5b; `main.py` |

**Deployment model implication:** the safe hosting shape is **one always-on process** that owns the
only SQLite connection. Any platform that runs *N* replicas of the service, or that resets the
filesystem between restarts, is incompatible unless the DB is pinned to a persistent volume.

---

## 4. SQLite persistence contract (H1)

`H1` = "can SQLite state be guaranteed to survive restart and redeployment on the chosen host?"
This section is **design + local evidence only**; the provider-side half is the H1 checklist (§8).

### 4.1 Path resolution
- `DB_PATH` env (default `bot_state.sqlite3`). Relative paths resolve against the **process working
  directory** (`bot/config.py`), so the CWD must be stable and identical on every start.
  `start.sh` `cd`s to the script directory first, making relative paths deterministic.
- Production recommendation: an **absolute** path on the persistent mount
  (e.g. `/home/container/bot_state.sqlite3`).

### 4.2 Directory creation / availability
- `_check_db_path` creates the parent dir (idempotent) and fails with a clear `BootstrapError` if the
  parent cannot be created or is not writable (`os.access(parent, os.W_OK)`). A path pointing at a
  directory is rejected. There is **no** silent fallback.

### 4.3 Connection ownership
- One `Database` instance, one `sqlite3.connect(path, check_same_thread=False)` connection, created
  once in `build_application` (`bot/db.py`, `bot/app.py`). **One process only** — multiple replicas
  would mean multiple writers on a single-file DB (unsupported).

### 4.4 WAL / shared-memory implications
- `journal_mode=WAL` produces `bot_state.sqlite3`, `bot_state.sqlite3-wal`, `bot_state.sqlite3-shm`.
  All three must live on a filesystem that supports WAL's shared-memory semantics. Network filesystems
  that do not implement proper POSIX locking/`mmap` (some NFS/object-store mounts) are **incompatible**.
- A normal local block volume (ext4/overlayfs/NVMe) is compatible. This is the compatibility test the
  operator must run (checklist item: "proof the DB is on persistent storage").

### 4.5 Unavailable / read-only / full filesystem
- Unavailable parent dir → startup refuses with a clear message (no silent run).
- Read-only or full disk → `sqlite3` raises; `run_startup_maintenance` returns `False`, `/ready`
  stays `503`, and `main.py` exits non-zero **before** polling. There is **no** auto-repair, no
  auto-delete, and no rebuild of a bad DB (deliberate).

### 4.6 Restart / container restart / redeploy
- **Process restart (same filesystem):** state survives (file + WAL are on disk). WAL is checkpointed
  on graceful shutdown.
- **Container restart (same volume):** survives **iff** the volume is re-attached at the same mount.
- **Redeploy:** survives **iff** the DB lives on a persistent volume that is not recreated on deploy.
  On an ephemeral filesystem it is **lost**.

### 4.7 Local state that lives only in SQLite (13 tables)
`watched`, `user_state` (awaiting/threading), `outbox` (incl. **undelivered** prompts), `creation_jobs`,
`completion_pending`, `settings` (e.g. notification preference), `notification_state`,
`notifier_pending`, `notifier_retry_not_before`, `notification_inbox`, `deleted_conversations`
(durable delete tombstones). If SQLite is lost, all of the above are lost: watch list, pending
outbox/creation work, completion intents, tombstones (a deleted conversation could then reappear),
notification state. Remote OpenHands conversations are **not** affected.

### 4.8 Evidence separation
- **Code-level design:** VERIFIED (§4.1–4.7, cited symbols).
- **Local test evidence:** VERIFIED (full suite green in `.venv`; DB maintenance/security tests pass).
- **Provider-documented filesystem behaviour:** see §5 (official docs).
- **Actual deployed hosting evidence:** **NONE** ⇒ H1 remains **UNVERIFIED**.

> **H1 statement:** H1 is **UNVERIFIED**. Nothing in this repository proves that any real host keeps
> the SQLite file across restart and redeploy. That proof is exactly the §8 checklist.

---

## 5. Hosting provider comparison (official sources, Nov 2026)

Facts below come from each provider's own documentation (URLs in §5.1). "Free/no-card" means the
free offering is usable **without** entering a payment card, as documented.

| Provider (plan) | Free / no-card | Persistent storage | Restart persist | Redeploy persist | Python | Long-running | Resource limits | Egress | SQLite compat | Ops complexity | Cost | Main risks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Oracle Cloud — Always Free** (Ampere A1 VM + Block Volume) | Free tier exists; **card required at signup** (identity check) | Yes — Block Volume (Always Free allowance) | Yes | Yes (volume independent of instance) | Yes (any Linux VM) | Yes (always-on VM) | Ampere A1 Always Free allowance; block volume allowance | Outbound free allowance | **Compatible** (local block volume, ext4) | **High** (VM, systemd, firewall, SSH) | $0 within Always Free | Idle accounts may be reclaimed; A1 capacity shortages; card needed |
| **Google Cloud — Always Free** (e2-micro VM) | Free tier exists; **card required at signup** | Yes — 30 GB standard persistent disk | Yes | Yes | Yes | Yes | 1 e2-micro/mo, 30 GB disk (3 US regions) | Generous egress allowance | **Compatible** | **High** | $0 within Always Free | Billing setup + card; must stay within limits; region-limited |
| **Katabump — Free** (Python bot host, the repo's documented target) | Free, **no credit card required** (documented) | Files persist **only between renewals**; no durable volume | Yes (within a renewal window) | Yes (same window) | Yes (Python + `requirements.txt`) | Yes (always-on bot) | 308 MB RAM, 716 MB storage | Outbound OK | **Conditional** | **Low** | $0 | **Renew every 4 days or the server AND files are permanently deleted** (official FAQ); no SLA |
| **Render — Free web service** | Free tier; **no card needed** to start (services suspended if 750 h/mo exceeded and no card) | **Ephemeral** — no persistent disks on Free | No | No | Yes | Spins down after 15 min idle; ~1 min cold start | 750 instance-hours/mo | 100 GB/mo included | **Incompatible** | Low | $0 | Ephemeral FS loses SQLite on every restart/redeploy/spin-down; idle spin-down |
| **Railway — Free/Trial** | Trial ($5/30 days) no card; then **$1/mo Free plan requires card** | 0.5 GB volume (Free) | Yes (with volume) | Yes (with volume) | Yes | Yes | 1 vCPU / 0.5 GB RAM, 1 volume | usage-based egress | Compatible (with volume) | Medium | $0 trial, then $1/mo + usage | Free plan needs a card after trial; usage-based cost |
| **Northflank — Sandbox Free** | Free, **no card needed** (documented) | **Persistent disks** available (paid feature tier); free tier is credit-limited | Conditional | Conditional | Yes | **Always on, no sleeping** | Up to $20/mo of resources; 2 services, 2 jobs, 1 DB | egress billed beyond allowance | Conditional | Medium | $0 within $20 credit | Persistence beyond the free credit window unverified; egress/credit limits |
| **Fly.io — Pay As You Go** | **No free tier** (only a 7-day $1 trial, no card) | Fly Volumes (paid, $0.15/GB/mo) | Yes (with volume) | Yes (with volume) | Yes | Yes | shared-cpu 256 MB from $2.19/mo | paid | Compatible | Medium | Paid (~$2.19+/mo) | Card required after trial; not free |

### 5.1 Official sources consulted
- Oracle Cloud Free Tier: `https://www.oracle.com/cloud/free/` (Always Free = Ampere A1 + Block
  Volume; card required for identity verification; idle accounts may be reclaimed).
- Google Cloud Free Tier: `https://cloud.google.com/free/docs/free-cloud-features` (card required;
  always-free compute = 1 `e2-micro`, 30 GB disk, 3 US regions).
- Katabump Docs: `https://docs.katabump.com/` and `/faq` (free = 308 MB RAM / 716 MB storage, no
  credit card; **renew every 4 days**; "1 day after expiration: server and files permanently
  deleted"; free servers renew only in the last 2 days).
- Render Free: `https://render.com/docs/free` (free web services: 15-min idle spin-down, **ephemeral
  filesystem**, no persistent disks, 750 h/mo).
- Railway Pricing: `https://railway.com/pricing` (Free: $1/mo, 0.5 GB volume, 1 vCPU/0.5 GB RAM;
  trial no card; Free plan requires card).
- Northflank Pricing: `https://northflank.com/pricing` (Sandbox Free: no card needed, up to $20/mo
  resources, 2 services, "always on, no sleeping"; persistent NVMe disks are a paid line item).
- Fly.io Pricing: `https://fly.io/docs/about/pricing/` (no free tier; $1 trial for 7 days; Volumes
  $0.15/GB/mo; smallest always-on Machine $2.19/mo).

### 5.2 Rejected options
- **Render Free** — rejected: ephemeral filesystem (SQLite lost on every restart/redeploy/spin-down)
  and 15-minute idle spin-down make it incompatible with a single always-on, stateful process.
- **Fly.io** — rejected for the free/no-card requirement: no free tier and a card is required after
  the trial; it is otherwise technically suitable but **not free**.
- **Vercel / Netlify / GitHub Pages** — rejected: serverless/static only; cannot host a long-running
  Telegram long-polling process with a local SQLite file.
- **Cloudflare Workers** — rejected: no long-running process and no local persistent SQLite file
  (D1 is a managed service, not the app's file, and would require an architecture change).

### 5.3 Unknowns / not verified
- Katabump: whether `requirements.txt` is auto-installed on start; whether auto-restart exists;
  whether "no card" holds for every signup path. (Documented, not verified against a live signup.)
- Northflank: whether a persistent disk can be attached on the **free** credit window, and whether
  the free service persists across a redeploy.
- Oracle/GCP: whether the free VM/volume is available in the operator's region without capacity
  wait; whether the operator can supply a card for identity verification.
- All: actual mounted-filesystem WAL compatibility on the specific host.

---

## 6. Recommendation

Ranking is by **technical suitability for this single-process, SQLite-owned architecture** under the
no-card preference, then by operational simplicity.

### 6.1 Preferred — Katabump Free (bot-only, `MINI_APP_ENABLED=0`)
Why it fits: it is the repo's documented target, requires **no card**, is a long-running Python host,
runs one process with no inbound port (long polling), and its storage (716 MB) comfortably holds the
SQLite file. The repo already ships `start.sh` and `docs/DEPLOY_KATABUMP.md` for it.
**Decisive caveat (must be accepted):** the free server must be **renewed every 4 days**, or the
server **and its files are permanently deleted** (official FAQ). This makes it suitable for a
**hobby/personal** deployment with a reliable 3-day reminder, **not** for a "set and forget"
production system. If the operator wants durability without manual renewals, prefer a VM option.

### 6.2 Fallback — a free-tier VM with a persistent volume (Oracle Always Free, else GCP Always Free)
A small always-on Linux VM (Ampere A1 / `e2-micro`) with a block/persistent disk gives the strongest
SQLite durability: the DB lives on a real block volume that survives restart and redeploy, and the
process is a normal systemd service. **Cost:** $0 within the always-free allowance. **Blockers to
confirm:** a **payment card is required at signup** (identity verification) and A1/region capacity
may be limited. This is the recommended option **if** the operator can provide a card and wants
durable persistence.

### 6.3 Conditional — Northflank Sandbox Free
No card, always-on, and it advertises persistent disks — attractive on paper. But the free tier is a
**credit-limited sandbox** ($20/mo, 2 services), and whether a persistent disk can be attached within
the free credit window (and whether it survives redeploys) is **not verified**. Use only after the
operator confirms persistent-disk availability on the free tier.

> **No provider is recommended that requires a Backup service or a Backup subsystem.** All three
> recommendations rely on the provider's ordinary persistent storage; none require configuring
> snapshots as a functional dependency. (Fly's/others' *optional* snapshots are infrastructure
> features, not the app's Backup feature, and are **not** to be configured by this project.)

---

## 7. Deployment runbook (DOCUMENTATION ONLY — do not execute)

> **Do not run any step below without explicit, separate approval.** This task performs none of it.

### 7.1 Pre-deployment approval gates
1. Operator explicitly approves the target provider and plan.
2. H1 evidence (§8) is collected and reviewed; H1 moves from UNVERIFIED to VERIFIED.
3. A release candidate commit is frozen (see 7.2) and its SHA recorded.
4. A maintenance window is agreed; no production DB migration/replacement happens implicitly.

### 7.2 Release candidate identification
- Freeze `agent/ohb2-audit-remediation` at the reviewed HEAD SHA; record it.
- Push/PR/merge/deploy require **separate explicit approval** (AGENTS.md §6). None is authorised here.

### 7.3 Runtime version
- Python **≥ 3.11** (target 3.13, matching CI). Confirm on the host: `python3 --version`.

### 7.4 Dependency installation
- Preferred: the platform installs `requirements.txt` on start.
- If it does not: set `OPENHANDBOT_AUTO_INSTALL=1` (needs `pip` + network) or run
  `pip install -r requirements.txt` once. Do **not** enable auto-install on a platform that already
  installs, to avoid redundant installs.

### 7.5 Required environment variables (names only — values entered in the provider UI)
- `TELEGRAM_BOT_TOKEN`, `OPENHANDS_API_KEY`, `ALLOWED_TELEGRAM_ID`.
- Recommended: `DB_PATH` (absolute, on the persistent mount), `LOG_LEVEL=INFO`.
- Mini App (only if enabled): `MINI_APP_ENABLED=1`, `MINI_APP_URL` (public https), `MINI_APP_PORT`.
- **Secrets are entered only through the provider's environment/secrets UI.** Never in chat, logs,
  files, or the repo. The app registers secrets for redaction (`bot/errors.py`), but that is
  defence-in-depth, not permission to log them.

### 7.6 Persistent volume + database path
1. Create the persistent volume/disk in the provider UI.
2. Mount it (e.g. `/home/container` or `/data`).
3. Set `DB_PATH=/<mount>/bot_state.sqlite3` (absolute).
4. Verify the mount is a real block volume (supports WAL), not a network/object mount.

### 7.7 Process / replica count
- **Exactly one** process/replica. Disable any autoscaling or "N replicas" setting.

### 7.8 Start command
- `sh start.sh` (unified entry point; checks Python + deps, then `exec python main.py`), or
  `python main.py`. Same single process.

### 7.9 Health / readiness configuration
- Liveness: `GET /health` (expect `200`). Readiness: `GET /ready` (expect `200` when DB integrity is
  OK and workers are running; `503` otherwise). Only relevant when `MINI_APP_ENABLED=1`; the bot-only
  target needs no inbound port.
- Enable the platform's auto-restart/always-on policy if available.

### 7.10 First-start behaviour
- Bootstrap: Python check → config validation (no secrets printed) → DB dir prep → DB open/WAL →
  integrity check → build app → start workers → long polling. A fresh DB is created automatically.
- Watch the log for `bootstrap status: bootstrap=READY …` and the Mini App bind line (if enabled).

### 7.11 Controlled restart verification (evidence for H1)
- Note the DB file size + a known row (e.g. a watched conversation).
- Restart the process from the provider UI.
- Confirm the same DB file (same path, non-zero size) and the same row are present after restart.

### 7.12 Controlled redeployment verification (evidence for H1)
- Redeploy/re-push the same release candidate.
- Confirm the DB file and rows are **unchanged** (proves the volume is not recreated on deploy).

### 7.13 Log review and secret redaction
- Confirm no token/key appears in logs (redaction is active). Review startup + first poll cycle.

### 7.14 Rollback boundaries
- Rollback = stop the process and redeploy the previous release candidate. Do **not** delete the
  volume, do **not** run destructive DB operations, do **not** force-push. Keep the previous
  release SHA.

### 7.15 Operator acceptance checklist (runbook)
- [ ] Provider + plan recorded; H1 evidence (§8) complete and reviewed.
- [ ] Volume mounted; `DB_PATH` absolute on the mount.
- [ ] Single process/replica confirmed.
- [ ] Start command + Python version confirmed.
- [ ] Health/readiness endpoints return expected codes (if Mini App enabled).
- [ ] Restart-persistence and redeploy-persistence both demonstrated.
- [ ] Logs free of secrets.
- [ ] Monthly cost confirmed by the operator.

### 7.16 Mandatory statements
- **Autopush remains DISABLED / INACTIVE.** Not executed, activated, scheduled, or configured.
- **Any future push, PR, merge, or deployment requires separate explicit user approval.**
- **No production data migration or DB replacement may happen implicitly.**
- **No automatic exactly-once delivery guarantee exists** (the outbox is at-least-once; a Telegram
  message already in flight before a delete may still arrive).
- **No Backup feature is to be introduced**, and no external Backup workflow is to be configured as
  a substitute.

---

## 8. H1 evidence checklist (required to close H1)

Provide **evidence** (screenshots/logs/commands), **no secret values**:

- [ ] Hosting provider and exact plan name.
- [ ] Persistent volume/disk identifier (non-secret) and size.
- [ ] Mount path on the host.
- [ ] Application `DB_PATH` value (the path only — not any secret).
- [ ] Proof the DB file is on the persistent mount (e.g. `df <mount>` + `ls -l <DB_PATH>` showing the
      same device).
- [ ] Proof of persistence across a **controlled restart** (row/file unchanged before→after).
- [ ] Proof of persistence across a **controlled redeployment** (row/file unchanged before→after).
- [ ] Confirmation of a **single** application process/replica.
- [ ] Actual Python runtime version on the host (`python3 --version`).
- [ ] Actual start command used.
- [ ] Health/readiness configuration (endpoint + expected codes), if Mini App enabled.
- [ ] Resource limits of the chosen plan (CPU/RAM/storage).
- [ ] Network egress capability (Telegram + OpenHands reachable).
- [ ] Operator confirmation of expected monthly cost (e.g. "$0 within always-free" or "free, renew
      every 4 days").

> **H1 remains UNVERIFIED until the above is supplied and reviewed.** No source-inspection or
> marketing page substitutes for it.

---

## 9. Governance compliance

- Backup feature/subsystem: **none** introduced; none required by any recommendation. (Verified: no
  backup module/route/dep; `requirements.txt` has no `paramiko`/SFTP/cloud dependency.)
- Autopush: **inactive**; untouched.
- Production Telegram/OpenHands: **not contacted**.
- Deployment/publishing/DB ops: **none**.
- Git write actions: **none** (no commit/push/fetch/pull/merge/rebase/cherry-pick/PR/branch switch).
- Secrets: **none** printed or requested.
- Protected paths (`.openhands/`, `.agent/`, `automation/`): preserved; only this doc + PROGRESS.md
  were written.

---

## 10. Local verification (this task, Phase 8)

Commands and real results:

| Command | Result |
|---|---|
| `python -m pyflakes bot/ main.py tests/` | clean, exit 0 |
| `python -m pytest -q` (inside `.venv`) | **1576 passed**, 71 warnings, exit 0 |
| `node --test tests/frontend/*.test.js` | **143 pass / 0 fail**, exit 0 |
| focused: `pytest tests/test_openhands_client.py tests/test_handlers.py tests/test_conversation_deletion.py tests/test_resurrection_fix.py -q` | **194 passed** |

CI note: the `CI` workflow runs only on push/PR to `main`; this branch has **no** CI run, so CI is
**not** claimed as passed. Local commands mirror the workflow exactly.

---

## 11. Independent review status

A genuinely independent reviewer session is **not available** in this environment (no local
agent-server/API; contacting OpenHands production is forbidden by the task's governance rules).
Independent review is therefore reported **BLOCKED**; the review in §2 is a **self-review** and is
labelled as such. It must not be presented as independent.
