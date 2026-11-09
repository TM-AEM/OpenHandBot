# OHB2 Phase 2A — Free Hosting Qualification & Persistence Verification Plan

**Task ID:** `OHB2-PHASE2A-FREE-HOSTING-QUALIFICATION-AND-PERSISTENCE-VERIFICATION-PLAN`
**Status:** research + documentation only. No account created, no resource provisioned, no code
deployed, no DNS/Telegram change, no production call, no commit/push by hand.
**Final classification:** **`NO_QUALIFIED_FREE_NO_CARD_HOST`**
**Research date:** 2026-11-08 (all provider facts below were re-checked on this date from the
provider's own official pages; the "checked" date is stated per claim).

---

## 0. Phase 1 readiness gate (checked FIRST, per the task)

| Item | Value |
|---|---|
| Repository | `TM-AEM/OpenHandBot` (public), local `/workspace/project/OpenHandBot` |
| Branch | `agent/ohb2-phase1c-inbox-filter-archive-delete` |
| HEAD | `5b108503d182e3db28aa720df930a3344c8b4c8a` |
| Upstream | `origin/agent/ohb2-phase1c-inbox-filter-archive-delete` (in sync with HEAD) |
| Working tree at task start | modified: `bot/web/app.py`, `bot/web/services.py`, 4 test files; untracked: `docs/OHB2_*.md`, `tools/` — **pre-existing, not created by this task** |
| Autopush | **DISABLED / INACTIVE** — no `main.py --daemon` process, no `autopush.log`; repo default branch for Autopush is `main`, so it would not touch this `agent/*` branch anyway |
| Backup subsystem | absent / out of scope (not inspected as a hosting dependency) |

### 0.1 Phase 1 review verdict — **BLOCKED (not ready for Phase 2)**

An independent adversarial review of the exact HEAD (`5b10850`) exists and returned
**VERDICT: HIGH** (highest unresolved severity = HIGH). Its report is preserved on disk under
`/workspace/conversations/b4588fc18a40463487d6c4d75580ebf1/` (the final assistant message,
event `…0294`, carries the verdict). The unresolved findings are:

1. **HIGH** — `bot/web/services.py::MiniAppService._wake` calls `worker.wake()` on
   `bot_data["watcher"]` and `bot_data["notifier"]`, which have **no** `wake()` method. In
   production (`bot/app.py` registers the real `Watcher`/`Notifier`, and the Mini App is built
   with `application=…`), **every** Mini App conversation delete performs the remote delete and
   then raises `AttributeError` → HTTP 500. The delete actually succeeded; the client is told it
   failed.
2. **MEDIUM** — unhandled `OverflowError` → HTTP 500 for out-of-range integers on
   `GET /notifications?page=`, `POST /notifications/<id>/read|archive|unarchive`,
   `DELETE /notifications/<id>`, `GET /operations/outbox?id=`, and `POST /operations/outbox/reconcile`
   (the `MAX_SQLITE_INT` bound was applied to creation routes only).
3. **MEDIUM** — unhandled `AttributeError` → HTTP 500 for non-string JSON body fields
   (`outbox reconcile action`, `chats text/client_ref`, `prompt text/client_ref`,
   `repository repository`); the F3 guard was applied to `creation_reconcile` only.
4. **LOW** — doc/comment truthfulness nits (a comment claims the `MAX_SQLITE_INT` guard covers
   "ids/pagination" generally; `ratelimit.py` says keys are "aliases, not tokens" while the key
   is the raw session token; `docs/MINI_APP.md` line ~206 repeats the same claim).

**Per AGENTS.md §7 the Phase 1 acceptance criterion "independent review shows no unresolved
Critical/High" is NOT met, so Phase 1 is not closed.** Per the task's section 2 instruction
("If Phase 1 is not ready, stop hosting selection and report the blocking engineering issues"),
the hosting *selection* is intentionally not completed here — the deliverable is the
qualification research + the blockers.

> Note: at task start the working tree already contained uncommitted edits that appear to be a
> partial, in-progress fix for findings #1–#3 (`_wake` guard, `MAX_SQLITE_INT` bounds on
> notifications/outbox, `_as_str` for JSON fields) plus regression tests. That work is **not
> mine**; this task must not touch it (AGENTS.md §3 rule 5), so it is left exactly as found.

---

## 1. Application facts verified from real code (2026-11-08)

| Fact | Evidence |
|---|---|
| Entry point / single process | `main.py` → `bot.app.build_application` → `app.run_polling(drop_pending_updates=True)`; docstring: "مفيش عملية تانية ومفيش exec". `start.sh` uses `exec "$PY" main.py` (same process). |
| Long polling (no inbound port needed for the bot) | `run_polling`; documented in `docs/OHB2_HOSTING_DECISION.md` §1.5. |
| Mini App ASGI | Starlette `bot/web/app.py` + `uvicorn` (both pinned in `requirements.txt`). |
| DB path | `bot/config.py:235` `db_path = DB_PATH or "bot_state.sqlite3"`; relative path is resolved against CWD (`start.sh` cd's to the script dir). |
| DB parent auto-create | `bot/bootstrap.py::_check_db_path` → `parent.mkdir(parents=True, exist_ok=True)`; raises `BootstrapError` if the parent is a file or not writable. |
| SQLite durability settings | `bot/db.py:330-335` `sqlite3.connect(path, check_same_thread=False)` + `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000`. One connection owned by one process. |
| Startup integrity gate | `main.py` runs `db.run_startup_maintenance()` before polling; on failure it refuses to start (no auto-delete/repair). |
| Health/readiness | Mini App health endpoint (no secrets) — see `bot/web/app.py`; `MINI_APP_ENABLED` stays **off** for this task. |
| Runtime resource need (measured locally 2026-11-08) | baseline interpreter **10.9 MiB**; after importing full app + all runtime deps **58.0 MiB** peak RSS. SQLite file grows ~KB (200 inbox rows ⇒ <10 KB; earlier measurement 1.5 MB for a populated DB). |
| Python | repo supports 3.11+; local venv 3.13.15; CI matrix 3.11 & 3.13. |

---

## 2. SQLite persistence requirements (Deliverable B)

For a free/no-card host to be *qualified* to own the production SQLite state, it must satisfy
**all** of the following. (These are the acceptance tests for a later authorized run; none were
executed against a real provider here.)

1. **Durable, writable filesystem** available on the free tier — not ephemeral container storage.
2. The DB directory is configurable via `DB_PATH` to an **absolute path on that durable
   filesystem**, and the app's parent-dir auto-create + write check succeeds there.
3. A committed row **survives a full process restart** (stop → start).
4. A committed row **survives container replacement/recreation** (reschedule onto a fresh
   container), not only an in-place restart.
5. A committed row **survives application redeployment** (new image/code, same service).
6. A committed row **survives a suspend/resume** cycle of the free service.
7. **WAL is safe** on the volume: `-wal`/`-shm` sidecar files coexist with `app.db`; the
   filesystem supports the locking `busy_timeout=5000` expects; `PRAGMA journal_mode=WAL`
   reports `wal`.
8. **Exactly one** application process owns the DB at all times (no horizontal scaling, no
   second replica, no separate bot/web processes).
9. A **stable public HTTPS URL** (unchanged across restarts/redeploys) reaches the app port,
   with a publicly trusted certificate (Telegram WebView requires a real CA).
10. The free plan does not silently delete or reclaim data after inactivity without a documented,
    survivable window.

A provider that only guarantees items 3 (process restart) is **insufficient**.

---

## 3. Candidate comparison (Deliverable A)

All limits/quotes were read from the provider's own pages on **2026-11-08**. "Card" = bank card
required at signup or to keep the service alive.

| Provider / plan | Free limits (2026-11-08) | Card? | Stable HTTPS URL | Python/ASGI | Durable storage evidence | Survives process restart | Survives container recreation | Survives redeploy | Free suspension/deletion terms | Major risks | Evidence (checked 2026-11-08) | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Katabump Free** | 308 MB RAM, 716 MB disk, 25% CPU, I/O 100 | **No** ("no credit card required") | **Not documented** — polling-only bot host; no published inbound port / public URL | Python 3.8+ + `pip install -r requirements.txt` | Files live on the server; **deleted permanently** if renewal missed | Yes (within a renewal window) | UNKNOWN | UNKNOWN | **Must renew every 4 days**; miss it ⇒ suspend, then **permanent deletion 1 day later** | Data-loss by 4-day timer; no inbound port for the Mini App; no HTTPS ingress documented | `docs.katabump.com/` (free tier), `/faq` (no card), `/hosting/renew-your-server` (4-day + deletion) | **REJECTED** |
| **Enzonic Free (Brave Grove class)** | *Current* free = **3.5 GB RAM / 200% CPU / 5 GB SSD**, but a **game server that hibernates after ~15 min idle**; files archived to **Cloudflare R2** before container shutdown. Panel app hosting claims **512 MB RAM / 50% CPU / 10 GB SSD / 24/7**. | No ("No credit card") | Yes — provider gives a URL | Python 3.10–3.12, Uvicorn/Gunicorn supported; `requirements.txt` auto-installed | **ToS implies container files are ephemeral** (why R2 archival exists); no documented durable *volume* | UNKNOWN (not documented) | UNKNOWN | UNKNOWN | Free game servers idle >14 days may be pruned after email warning | Architecture mismatch (app host = game-server plan with 15-min hibernate); durability unproven | `enzonic.com/free`, `/pricing`, `/python`, `/discord-bots`, `/legal/terms` (§3 Free Tier and Hibernation Policy) | **REJECTED** (unproven durability; mismatch) |
| **Northflank Sandbox Free** | **Always on, no sleeping**; 2 services, 2 jobs, 1 database; **up to $20/mo of free resources**; "no card needed" | **No** ("No card needed") | Yes — generated subdomain on the `code.run` domain, **automatic TLS** (Let's Encrypt) | Docker container; any Python/ASGI; persistent volume (NVMe) attachable | Persistent volumes exist and "persist data across restarts"; **not stated as free-tier-included** | Yes (documented) | Likely yes (volume is a network disk) | Likely yes | Not documented | Whether a **free** plan includes a persistent volume is UNVERIFIED; $20/mo resource cap could be exceeded | `northflank.com/pricing`, `/docs/…/databases-and-persistence/add-a-volume`, `/docs/…/domains/certificate-generation` | **STRONGEST CANDIDATE — durability UNVERIFIED** |
| **Render Free** | 750 instance-hours/mo, 512 MB | No | Yes | Python/ASGI | **Ephemeral filesystem**; persistent disks are **paid-only**; free web service **spins down after 15 min idle and local files are lost**; Postgres free DB expires after 30 days | No | No | No | Suspended when 750 h exhausted | Loses the DB on every spin-down/redeploy | `render.com/docs/free` | **REJECTED** |
| **Railway Free** | 30-day trial $5, then **$1/mo**; 0.5 GB RAM, 0.5 GB volume | No (card only for paid) | Yes | Python/ASGI | 0.5 GB volume | Yes | Likely | Likely | N/A | Post-trial $1/mo is a **paid** requirement | `railway.com/pricing` | **REJECTED** (trial→paid) |
| **Fly.io** | **$1 credit, 7 days**; trial Machines **stop after 5 min** | Card needed to lift limits | Yes | Python/ASGI | Volumes exist but trial is time-boxed | No (trial) | No | No | Trial expires | Not a free-forever host; machines stop | `fly.io/docs/about/free-trial/` | **REJECTED** (trial) |
| **Koyeb** | No free tier (plans start at **$29/mo**) | — | — | — | — | — | — | — | — | Paid only | `koyeb.com/pricing` | **REJECTED** (no free tier, 2026) |
| **Oracle Cloud Always Free** | 2 AMD micro VMs, 200 GB block storage, 2 Always-Free DBs | **Yes — credit/debit card required at signup** (identity verification) | Yes (you configure TLS) | Full VM, Python/ASGI | Block storage is durable | Yes | Yes | Yes | Idle ≥30 days may be reclaimed | Violates "no bank card"; card-authorization hold | `oracle.com/cloud/free/faq/` | **REJECTED** (card required) |

---

## 4. SQLite durability assessment (Deliverable B detail)

The application already uses the **safe single-owner pattern**: one `sqlite3` connection, WAL,
`busy_timeout=5000`, parent-dir auto-create, and a startup integrity gate. Locally verified
2026-11-08: `PRAGMA journal_mode` returns **`wal`**; a 200-row DB is <10 KB; peak import RSS
58 MiB. **The only missing piece for production is a durable filesystem on a free host.**

Mapping the lifecycle events required by the task to what each candidate proves:

| Lifecycle event | Katabump | Enzonic | Northflank |
|---|---|---|---|
| Process restart | Yes (within renewal window) | UNKNOWN | Yes |
| Container restart | UNKNOWN | UNKNOWN | Likely (volume) |
| Container recreation | UNKNOWN | UNKNOWN | Likely (volume) |
| Application redeploy | UNKNOWN | UNKNOWN | Likely (volume) |
| Suspend/resume | Files survive until the 1-day deletion deadline | UNKNOWN | N/A (never sleeps) |
| Provider maintenance / reclamation | **4-day renewal; permanent delete 1 day after miss** | prune after 14 idle days (game tier) | not documented |

**Conclusion:** no candidate provides *documented* evidence of durable storage across all the
required events. Northflank is the only one where the mechanism exists and the plan is free and
always-on; the free-tier volume entitlement must be proven by a real test before it can qualify.
Katabump and Enzonic are rejected on durability/architecture grounds. External DBs, cloud-drive
storage, a second DB owner, or a Backup subsystem are **not** introduced as workarounds (per the
task).

---

## 5. Architecture & resource compatibility (Deliverable C-support)

- **One process, one SQLite owner, no horizontal scaling** — every candidate must run exactly one
  replica; Northflank's Single-Read/Write volume *forces* 1 instance (documented: "Services are
  limited to 1 instance"), which matches the app's design.
- **Resource need:** ~58 MiB RSS at import, small DB, no heavy compute. 256 MB is enough;
  Northflank's free allowance (up to $20/mo of resources) is far above this; Katabump's 308 MB
  is enough **for the bot only** (it has no inbound port for the Mini App).
- **Stable HTTPS URL:** Northflank provides a generated subdomain with automatic Let's Encrypt
  TLS — the only candidate that documents both a free public URL *and* TLS. Katabump documents
  neither. Enzonic gives a URL but on a hibernating game plan.
- No separate bot/web processes, no scheduler, no Autopush, no Backup are proposed.

---

## 6. Risk assessment (Deliverable: §9)

| Risk | Katabump | Enzonic | Northflank |
|---|---|---|---|
| Cost | LOW ($0) | LOW ($0) | MEDIUM (free cap $20/mo; could be exceeded → pay) |
| Card/payment | LOW (none) | LOW (none) | LOW (no card) |
| Data persistence | **HIGH** (4-day delete) | **HIGH** (unproven) | **UNKNOWN** (free volume entitlement unverified) |
| Service suspension | **HIGH** (renewal) | MEDIUM | LOW (always-on) |
| URL stability | **HIGH** (no URL) | MEDIUM | LOW |
| Resource exhaustion | MEDIUM (308 MB, I/O 100) | MEDIUM | LOW |
| Operational maintenance | **HIGH** (renew every 4 days) | LOW | LOW |
| Vendor lock-in | LOW | LOW | MEDIUM |
| Security/config | MEDIUM (no HTTPS ingress) | MEDIUM | MEDIUM |

UNKNOWN is **not** downgraded to LOW anywhere.

---

## 7. Recommendation (Deliverable C)

**No candidate is qualified.** Final classification: **`NO_QUALIFIED_FREE_NO_CARD_HOST`**.

- **Katabump Free** — rejected: 4-day renewal with **permanent file deletion** 1 day after a miss,
  and **no documented inbound port / HTTPS ingress** for the Mini App (polling-only bot host).
- **Enzonic (Brave Grove class)** — rejected: the current free tier is a **hibernating game
  server**; app hosting durability is unproven and the ToS implies container-local files are
  archived away (ephemeral), not durably mounted.
- **Northflank Sandbox Free** — **strongest candidate** (free, no card, always-on, single-instance
  volumes, generated HTTPS subdomain + Let's Encrypt). It is **not yet qualified** because the
  official pages do **not** state that a *persistent volume* is included in the free Sandbox
  allowance (UNVERIFIED).
- **Render / Railway / Fly / Koyeb / Oracle** — rejected (ephemeral FS, trial→paid, no free tier,
  or card required).

**Why no recommendation is made:** the task forbids treating a documentation claim as proof, and
forbids provisioning. Northflank can only move to
`HOSTING_CANDIDATE_QUALIFIED_FOR_CONTROLLED_TEST` after a later **authorized** canary proves the
persistence requirements in §2. Until then, the honest answer is "none qualified".

---

## 8. Deployment preparation checklist (Deliverable D — later, authorized only)

1. Close Phase 1 first: resolve the review findings #1–#3 and obtain a clean re-review
   (no unresolved Critical/High) — **prerequisite**.
2. Create a Northflank account (owner action; no card) and a project.
3. Add the repo as the build source (or a Dockerfile); set the start command to `sh start.sh`.
4. Attach a **persistent volume** (Single Read/Write, so exactly 1 instance) and mount it, e.g.
   `/var/data`; set `DB_PATH=/var/data/bot_state.sqlite3`.
5. Set the required env vars **names only** in the panel (values entered by the owner in the UI):
   `TELEGRAM_BOT_TOKEN`, `OPENHANDS_API_KEY`, `ALLOWED_TELEGRAM_ID`, `DB_PATH`, and Mini App vars
   **only after** approval (`MINI_APP_ENABLED` stays off until then).
6. Set instance count to **1**; disable autoscaling; confirm no second replica.
7. Link the generated subdomain/port; confirm HTTPS + certificate.
8. Keep Autopush disabled; do not install any Backup feature.

---

## 9. Required proof tests (Deliverable E — design only, do NOT run now)

Run on the **canary** (a throwaway service), never against the real user DB or production
Telegram/OpenHands operations. Each test writes a sentinel row with a timestamp and asserts it is
still present after the event.

| # | Test | How | Pass condition |
|---|---|---|---|
| T1 | DB on durable storage | After start, `PRAGMA journal_mode` = `wal`; `DB_PATH` resolves to the mounted volume; `-wal`/`-shm` appear next to `app.db` | path under the volume; `wal` |
| T2 | Survives process restart | Stop service → start; re-read the sentinel | sentinel present |
| T3 | Survives container recreation | Force reschedule/recreate (delete pod, not the volume) → read | sentinel present |
| T4 | Survives redeploy | Push a new build → read | sentinel present |
| T5 | Survives suspend/resume | Suspend the free service → resume → read (Northflank is always-on, so this may be N/A; do it on any candidate that sleeps) | sentinel present |
| T6 | Exactly one DB owner | Confirm instance count = 1; confirm a Single-Read/Write volume is attached; no second replica | 1 instance, no duplicate workers |
| T7 | Stable HTTPS URL | Compare the public URL before/after T2–T4; `curl -sSI` shows a valid Let's Encrypt cert | URL unchanged; cert trusted |
| T8 | Start & recovery | Cold start after T2–T4; app reaches ready and recovers watched state | app starts, no integrity-gate failure |

A canary script scaffold already exists at `tools/katabump-sqlite-canary/` (stdlib-only, no
secrets, no network) and can be adapted for a generic host.

---

## 10. Governance compliance

- No provider account created; no resource provisioned/deleted; no egg-switch/reinstall; no
  destructive provider action.
- No deployment; no DNS change; no Telegram Bot change; `MINI_APP_ENABLED` not enabled; no
  production credentials set; no production API call; no Telegram message; no real OpenHands
  conversation create/delete; no Autopush; no Backup.
- No commit, push, merge, PR, or release performed by hand.
- The pre-existing working-tree changes (including the untracked `docs/OHB2_*.md`, `tools/`) were
  left untouched.
- Provider facts are quoted from official pages and dated 2026-11-08; anything not stated
  officially is marked UNVERIFIED.
