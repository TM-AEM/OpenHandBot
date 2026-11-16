# OHB2 Plan 04 — HOST-01 Free/No-Card Hosting Qualification (Enzonic first-class)

> Prepared by an AI agent (OpenHands) on behalf of the repository owner. **Investigation +
> documentation only.** No account created, no resource provisioned, no deployment, no DNS/Telegram
> change, no production call, no payment/card, no provider configuration change. No secret is
> recorded. Provider facts are quoted from official pages and dated.

- **Task ID:** `OHB2-PLAN04-HOSTING-QUALIFICATION-AND-MINIAPP-GATES-EXECUTION-02`
- **Date (UTC):** 2026-11-16
- **Repository:** `TM-AEM/OpenHandBot` · **Workspace:** `/workspace/project/OpenHandBot`
- **Baseline:** branch `main`, HEAD `56a58124f5cd677ca39e1dad19b5e3fa94b0fbc1`
- **Verdict (HOST-01):** **`BLOCKED`** — no candidate has **actual required persistence/runtime
  proof** (all remote persistence tests are `NOT_RUN`). Several candidates are *promising but
  unproven*; Enzonic's Python panel is the best free/no-card fit on paper.

Status legend: **PASS** = directly evidenced and satisfies the requirement · **FAIL** = evidence shows
it does not · **UNKNOWN** = evidence missing/ambiguous/outdated · **NOT_TESTED** = requires a test not
run. A provider marketing claim is **never** upgraded to PASS.

---

## 0. Mandatory requirements a candidate must satisfy (acceptance bar)

Derived from the application's real architecture (`main.py` → `bot.app.build_application` →
`bot.polling.run_bot`; ASGI `bot/web/app.py`; SQLite `bot/db.py`):

1. **Free and no bank card** at signup and later.
2. **Permanent free allowance** (not a trial that converts to paid).
3. **24/7 persistent process** (no request-triggered invocation, no scale-to-zero, no hibernation).
4. **Exactly one coordinated bot + ASGI process** (single `getUpdates` owner; no duplicate pollers).
5. **Stable public HTTPS origin** with a publicly trusted certificate (Telegram WebView requires it).
6. **Persistent filesystem** that survives restart, container recreation, and redeploy.
7. **SQLite locking compatibility** (WAL + POSIX locks + `busy_timeout`) on that filesystem.
8. **Restart persistence** of a committed row.
9. **Redeploy/rebuild persistence** of a committed row.
10. **RAM/CPU sufficiency** for the real dependency set.
11. **Safe secrets handling** (env vars, masked; no secret in logs).
12. **Rollback** capability.
13. **Reproducible deployment** (entry point + `requirements.txt` + start command).

---

## 1. Application facts (measured locally, 2026-11-16)

| Fact | Evidence |
|---|---|
| Entry point / single process | `main.py` → `bot.app.build_application` → `bot.polling.run_bot`; docstring "مفيش عملية تانية ومفيش exec". `start.sh` uses `exec "$PY" main.py`. |
| Long polling (no inbound port for the bot) | custom `getUpdates` loop (`bot/polling.py::TelegramPoller`), `updater(None)`; `deleteWebhook(drop_pending_updates=False)`. |
| Mini App ASGI | Starlette `bot/web/app.py` + `uvicorn` (pinned `requirements.txt`); runs **inside the same process** when `MINI_APP_ENABLED=1` (`bot/app.py::_wire_mini_app`). Off by default. |
| DB | `bot/config.py` `db_path = DB_PATH or "bot_state.sqlite3"`; `bot/bootstrap.py::_check_db_path` auto-creates the parent dir; `bot/db.py` uses one `sqlite3` connection, `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`. |
| Python | repo `MIN_PYTHON=(3,11)`; CI matrix 3.11 & 3.13; local 3.13.15. |
| **Measured peak RSS after full import** | **58.4 MiB** (baseline 8.1 MiB) — 2026-11-16, `resource.getrusage`. |
| Runtime site-packages | ≈ 71 MB (user-site, includes dev tools). |
| Tracked source tree | 7.1 MB. |
| Required env vars | `TELEGRAM_BOT_TOKEN`, `OPENHANDS_API_KEY`, `ALLOWED_TELEGRAM_ID` (+ optional `DB_PATH`, `MINI_APP_*`). |

**Local persistence proof (performed, synthetic, outside the repo, no secrets):**
`/tmp/ohb2_host01_proof/proof.py` created `app.db`, wrote a sentinel row, and re-read it from a **new
interpreter** (process restart):

```
journal_mode = wal
busy_timeout = 5000
sidecar files: ['app.db', 'app.db-shm', 'app.db-wal']
rows_after_restart = [('synthetic-record-1', '2026-11-16 12:44:35')]
LOCK: second writer blocked -> OperationalError database is locked
```

This proves the app's **WAL + single-owner locking pattern works on a local filesystem**. It does
**not** prove behaviour on any provider's remote volume — that requires the canary in §5 (NOT_RUN).

---

## 2. Enzonic — four distinct service paths assessed separately

Enzonic advertises several **different products**. They are **not** merged below, and the same
resource entitlement is **not** counted twice.

### 2A. Enzonic Python Hosting (panel server) — the primary candidate

Official pages: `https://enzonic.com/python` (accessed **2026-11-16**); panel entry
`https://panel.enzonic.com/` (returns a minimal sign-in shell — no product detail without an account).

Provider claims (quoted, attributed — **not** independently verified):
- "512 MB RAM · 50% CPU · 10 GB Storage · 24/7 Always on" and "**One free server per account, subject
  to capacity. No card required.**" (`/python`).
- FAQ: "The **Free Forever** tier gives you one free server per account, subject to capacity, with
  512 MB RAM, a 50% CPU allocation, 10 GB storage and 24/7 uptime. **No payment details needed.**"
- FAQ: "**Python 3.10, 3.11 and 3.12**, with pip, Poetry and virtualenv. `requirements.txt` is
  installed automatically."
- FAQ: "You can run **Uvicorn, Gunicorn, Hypercorn**, or standard Python scripts with **custom
  startup command arguments in the panel**."
- FAQ: "Does my Python app sleep when inactive? **No.** Bot workers, cron tasks and API services
  stay online 24/7."
- Supported runtimes listed: FastAPI, Flask, Django, discord.py/disnake, PyTorch/AI services, and a
  "Custom Git Repository … with `requirements.txt` installed automatically".

Assessment:

| Requirement | Status | Evidence / note |
|---|---|---|
| Free/no-card | **PASS** | `/python` "No card required"; FAQ "No payment details needed". |
| Permanent free allowance | **PASS (claim)** | "Free Forever tier" — provider claim, no expiry stated. |
| 24/7 persistent process | **PASS (claim)** | FAQ "app does not sleep"; "24/7 uptime". |
| One coordinated bot + ASGI process | **PASS in principle** | Single panel server = one process; the app already runs bot+ASGI in one process. Supervisor restarts the **same** process (see 2B note). |
| Stable HTTPS origin | **PASS (panel product)** | Free subdomain documented on the sibling panel page `https://enzonic.com/nodejs` ("Free tier apps get a free subdomain `*.us.free.enzonic.com` or `*.spain.free.enzonic.com`"). The `/python` page itself does not print the suffix. |
| Persistent filesystem | **UNKNOWN** | "10 GB storage" is advertised, but persistence across restart/recreation/redeploy is **not documented**. |
| SQLite locking compatibility | **UNKNOWN** | Provider documents nothing about SQLite/WAL/POSIX locks. |
| Restart persistence | **UNKNOWN** | Not documented; canary NOT_RUN. |
| Redeploy/rebuild persistence | **UNKNOWN** | Not documented; canary NOT_RUN. |
| RAM/CPU sufficiency | **PASS** | Measured 58.4 MiB import RSS vs 512 MB → large headroom; light polling CPU. |
| Safe secrets/logging | **PASS** | Provider stores env vars masked (`/discord-bots`: "Tokens are masked and injected…"); app redacts secrets. |
| Rollback | **UNKNOWN** | Panel offers backups on paid/game tiers; app-tier rollback not documented. |
| Reproducible deployment | **PASS** | `start.sh` + `requirements.txt` + `docs/DEPLOY_KATABUMP.md`; startup command is configurable. |

**Runtime/entry-point note (resolved by config):** the older Enzonic preflight
(`docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md`, 2026-11) recorded a default `python3 app.py` start
command; this repo has **no root `app.py`** (entry point is `main.py`). Because the current `/python`
page advertises a **custom startup command**, this is resolved by setting `sh start.sh` (or
`python3 main.py`) — **not** a code change.

**Version note:** the current official `/python` page lists **Python 3.10/3.11/3.12**. The repo needs
≥ 3.11, so **3.11/3.12 are compatible**; 3.13 (the local interpreter) is **not** listed — use 3.12.

### 2B. Enzonic Web Hosting (panel server, generic runtime)

Official page: `https://enzonic.com/web-hosting` (accessed **2026-11-16**).

Provider claims: "Free to start, **storage on every server**"; "**No cold starts: processes stay
running**"; "24/7 uptime on free tier"; "SFTP + web file manager + live console"; runtime cards include
"**python generic** — A generic Python environment for bots, scripts and apps"; "Long-running Node.js,
Python, … processes instead of lambda functions. WebSockets, **cron loops and stateful apps work
without changes**"; "Disk + object storage — Every server runs on storage."

**This is the same underlying panel server product as 2A** (the page explicitly says "panel servers
with files, a console and backups are still here"; the "python generic" card is the same runtime). The
free entitlement is therefore **one** free server per account, **not** two. → **Not double-counted.**

Assessment: identical to 2A for the panel product. The web-hosting page adds explicit "stateful apps
work without changes" and "storage on every server", which **strengthens** the 24/7/process claim but
still **does not document cross-recreation durability or SQLite locking** → those remain **UNKNOWN**.

### 2C. Enzonic Deploy / Cloud (serverless, git-push)

Official pages: `https://enzonic.com/cloud` and `https://deploy.enzonic.com/` (accessed **2026-11-16**).

Provider claims: "Push to GitHub … builds every commit into a live deployment"; "API routes run as
**functions that start on demand and scale to zero** when traffic stops"; "**Sleeps when idle on
Hobby** — Hobby servers sleep after 15 quiet minutes and wake on the next request. Pro keeps them
on."; Free plan = 200 projects, 150 GB bandwidth, 2M function invocations, 3,000 build minutes.

Assessment: **FAIL for this project's architecture.** Deploy's Hobby tier is **request-driven /
scale-to-zero** and **sleeps after 15 quiet minutes** — it cannot host a **continuously active**
Telegram long-polling bot + ASGI process. "Pro" keeps servers on but is **paid**. Using Deploy would
require either an always-on paid plan or a process-architecture change — both forbidden. (The
project also must **not** migrate to a managed external database.)

### 2D. Enzonic Game Hosting product

Official page: `https://enzonic.com/free` (accessed **2026-11-16**).

Provider claims: free game tier = **3.5 GB RAM / 200% CPU / 5 GB storage**, but "**hibernates when no
players are online**" (≈15 min idle), "Supported bots and runtimes: 512 MB, always on".

Assessment: **FAIL as a Python application host.** A game-server template is **not** equivalent to
Python Hosting; the free game tier **hibernates on idle** and there is **no evidence** it offers a
supported custom Python runtime with a stable process, custom startup command, port mapping, and
HTTPS for an arbitrary application. Marked **FAIL/UNKNOWN** — the project must **not** be forced into
a game-server template. (Note: this page also confirms the app/bot free tier is "512 MB, always on",
i.e. distinct from the hibernating game tier.)

### 2E. Cross-cutting Enzonic constraints (official, `/free` + `/legal/terms`, accessed 2026-11-16)

- **Card:** "No payment method required" / "No card required" (free tiers).
- **Capacity:** free servers are "subject to available capacity" / "best-effort subject to node
  availability". **What happens when capacity is unavailable is not documented** → **UNKNOWN**.
- **Idle policy (game tier only):** "Free servers idle longer than 14 consecutive days may be pruned
  after an email warning; paid plans are never auto-purged." (This is the **game** tier; the app/bot
  tier is documented as always-on.)
- **Abuse rules:** "Keeping a free server awake … with bots, fake players or scripted joins is abuse"
  (game tier); "remote monitoring agents and agent farms … are not allowed" on free servers. → A
  long-polling Telegram bot is a legitimate 24/7 app (the `/discord-bots` page advertises exactly
  this), but the account must not be run as an agent farm.
- **Billing:** paid plans renew monthly; the **free** tier "is permanent and never asks for a card"
  (`enzonic.dev`). The advertised **free** Python/bot server is documented as free/no-card; a
  *separate* paid "Dirt" tier ($0.99/mo, always-on, 512 MB) exists but is **not** required for the
  free tier → **no card risk** for free use. Any later upgrade to keep a process on would be **paid**.
- **Company:** Enzonic LLC (Kentucky, USA); ToS last updated 2026-11. **One** free server per account.

---

## 3. Other candidates (official pages, accessed 2026-11-16)

| Provider | Free terms (official, 2026-11-16) | Card? | Persistent FS | 24/7 process | HTTPS | Verdict |
|---|---|---|---|---|---|---|
| **Katabump** (`docs.katabump.com/`) | 308 MB RAM, 716 MB storage, "no credit card required" | No | Files on server; **must renew every 4 days** (miss ⇒ suspend, then deletion) | Yes (within renewal window) | **No inbound port/URL documented** | **REJECTED** (4-day renewal + no documented HTTPS ingress) |
| **Render Free** (`render.com/docs/free`) | 750 h/mo, 512 MB | No | **Ephemeral FS** — "local SQLite databases … are lost every time"; persistent disks are **paid-only** | **Spins down after 15 min idle** | Yes | **REJECTED** (ephemeral FS + spin-down) |
| **Northflank Sandbox Free** (`northflank.com/pricing`) | 2 services, 2 jobs, 1 DB; "**up to $20/mo of resources**"; "No card needed"; "Always on, no sleeping" | No | Volumes exist ("Easily attach, scale and mount persistent disks"), but pricing lists persistent disk at **$0.11657/GiB/mo** and "Ephemeral storage … Not persisted" | Yes (always on) | Yes (TLS) | **STRONGEST NON-ENZONIC — durability UNVERIFIED** ($20/mo cap could be exceeded; free volume entitlement not stated) |
| **Railway** (`railway.com/pricing`) | 30-day trial $5, then **$1/mo**; 0.5 GB volume | No (paid only) | 0.5 GB volume | Yes | Yes | **REJECTED** (trial → paid) |
| **Fly.io** (`fly.io/docs/about/free-trial/`) | **$1 credit, 7 days** | No (card lifts limits) | Volumes exist but trial time-boxed | No (trial) | Yes | **REJECTED** (trial only) |
| **Koyeb** (`koyeb.com/pricing`) | **No durable free tier** — only a "Free 5h" sandbox ($0/mo, 0.25 vCPU, 1 GB) that **scales to zero on inactivity**; paid from ~$29/mo | — | 1 GB (paid) | **No** (scale-to-zero) | Yes | **REJECTED** (no durable free tier) |
| **Oracle Cloud Always Free** (`oracle.com/cloud/free/faq/`) | 2 AMD micro VMs, 200 GB block storage | **Yes — credit/debit card required at signup** ("Why do I need to provide credit or debit card information…") | Durable block storage | Yes | Yes (you configure TLS) | **REJECTED** (card required) |

---

## 4. Comparison matrix

| Requirement | Enzonic Python Panel (2A) | Enzonic Web Hosting (2B) | Enzonic Deploy (2C) | Other Candidates |
|---|---|---|---|---|
| Free / no-card | **PASS** | **PASS** (same product) | **PASS** (Hobby) | Katabump PASS; Northflank PASS; Render PASS; Railway/Fly/Oracle **FAIL** (card/trial); Koyeb **FAIL** |
| Permanent free allowance | **PASS (claim)** | **PASS (claim)** | **PASS (claim)** | Katabump PASS; Northflank PASS; Render PASS; Railway **FAIL**; Fly **FAIL**; Koyeb **FAIL**; Oracle PASS |
| 24/7 persistent process | **PASS (claim)** | **PASS (claim)** | **FAIL** (scale-to-zero + 15-min sleep on Hobby) | Katabump PASS; Northflank PASS; Render **FAIL** (spin-down); Railway/Fly PASS-ish; Oracle PASS |
| One coordinated bot + ASGI process | **PASS in principle** | **PASS in principle** | **FAIL** (functions) | Katabump PASS; Northflank PASS (1 instance); Render PASS; others PASS |
| Stable HTTPS origin | **PASS** (free subdomain, sibling page) | **PASS** | **PASS** | Katabump **FAIL**; Northflank PASS; Render PASS; Railway PASS; Fly PASS; Oracle PASS |
| Persistent filesystem | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | Katabump **FAIL** (4-day); Render **FAIL** (ephemeral); Northflank **UNKNOWN** (free volume); Railway/Fly PASS-ish; Oracle PASS |
| SQLite locking compatibility | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | Katabump UNKNOWN; Render **FAIL**; Northflank UNKNOWN; Oracle UNKNOWN |
| Restart persistence | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | Katabump UNKNOWN; Render **FAIL**; Northflank UNKNOWN |
| Redeploy/rebuild persistence | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | Katabump UNKNOWN; Render **FAIL**; Northflank UNKNOWN |
| RAM/CPU sufficiency | **PASS** (58 MiB ≪ 512 MB) | **PASS** | **PASS** | Katabump PASS (308 MB); Northflank PASS; Render PASS; others PASS |
| Safe secrets/logging | **PASS** | **PASS** | **PASS** | Katabump PASS; Northflank PASS; Render PASS |
| Rollback | **UNKNOWN** | **UNKNOWN** | **PASS** (one-click rollback) | Katabump UNKNOWN; Northflank UNKNOWN; Render PASS |
| Reproducible deployment | **PASS** | **PASS** | **PASS** | Katabump PASS; Northflank PASS |

**Decisive gap:** **no candidate documents durable persistence + SQLite locking across recreation and
redeploy**, and none has been proven by a real test (all canaries `NOT_RUN`).

---

## 5. Persistence proof: what was done vs. not run

**Done (safe, local, no provisioning):**
- Local synthetic SQLite proof (§1): WAL + `busy_timeout=5000` + sidecar files + survives a **process
  restart** + single-owner lock enforced. This validates the **application's** pattern only.

**NOT_RUN (requires a disposable deployment + separate owner approval):** remote durability on any
provider. Exact future procedure (to run only after explicit owner approval, on a **throwaway**
canary, never the real DB/Telegram/OpenHands):

1. Create an empty disposable test deployment (owner action; no card).
2. Start with an empty synthetic SQLite DB.
3. Write a known synthetic record.
4. Restart the service → verify the record remains.
5. Rebuild/redeploy (if supported) → verify the record again.
6. Verify file ownership/permissions.
7. Verify SQLite locking + single-owner behaviour (no second writer/instance).
8. Verify graceful shutdown + restart.
9. Verify **exactly one** bot poller and one coordinated lifecycle.
10. Verify stable HTTPS ingress after restart.
11. Verify no secrets or synthetic file contents leak into logs.

A stdlib-only scaffold exists at `tools/katabump-sqlite-canary/canary.py` (no network, no secrets)
and can be adapted.

---

## 6. HOST-01 verdict and exact blockers

**Verdict: `BLOCKED`.** Rationale: the definition of `QUALIFIED` requires evidence for **every**
mandatory requirement, **including actual persistence/runtime proof**. No candidate has that; the
remote persistence canary is `NOT_RUN` (provisioning is out of scope for this task).

**Exact missing evidence (blockers):**

1. **Enzonic Python Panel** — persistence across restart/recreation/redeploy: **UNKNOWN**; SQLite
   locking on the volume: **UNKNOWN**; free capacity behaviour when full: **UNKNOWN**; whether the
   free app server and free game server are **one** entitlement or two: **ambiguous** ("one free
   server per account" on both pages).
2. **Northflank Sandbox Free** — whether a **persistent volume** is included in the free allowance
   (pricing lists persistent disk as a metered add-on and "ephemeral storage not persisted"): **UNKNOWN**.
3. **Katabump** — no documented inbound HTTPS ingress for the Mini App: **FAIL**.
4. **Render** — ephemeral FS + spin-down: **FAIL**.
5. **Railway / Fly.io** — trial → paid / time-boxed: **FAIL**.
6. **Koyeb** — no durable free tier: **FAIL**.
7. **Oracle** — card required: **FAIL**.

**Realistic owner-approved next options (not selected here):**
- **(A)** Authorize a **throwaway Enzonic Python-panel canary** (no card) and run §5 — the cheapest
  path to a possible `QUALIFIED`. Owner action: create the account/server.
- **(B)** Authorize a **Northflank Sandbox** canary and confirm whether a free persistent volume is
  available.
- **(C)** Accept **no free host** and keep the app local-only (status quo) until a paid/always-on host
  is approved.

No option is chosen on the owner's behalf; each requires explicit authorization and (for A/B) an owner
account action.

---

## 7. Governance compliance

- No account created; no resource provisioned/deleted; no deployment; no DNS/Telegram change; no
  production credential; no production API call; `MINI_APP_ENABLED` untouched (off); no Autopush; no
  Backup subsystem; no new process/worker/DB owner.
- No payment details entered; no bank card used; no paid trial accepted.
- No secret requested, printed, or stored.
- No commit/push/PR/merge/release/deploy performed.
- Provider facts quoted from official pages and dated **2026-11-16**; every unproven item is marked
  `UNKNOWN`/`NOT_RUN` rather than upgraded to PASS.

---

## 8. Dated follow-up (2026-11-16) — canary execution attempt

> Added by `OHB2-PLAN04-ENZONIC-PYTHON-HOSTING-CANARY-EXECUTION-01`. This section is a **new dated
> record**; it does **not** alter any finding above.

The owner approved **option A** (an isolated disposable Enzonic Python Hosting canary). The canary could
**not** be provisioned: there is **no authenticated Enzonic account/session** in this environment, and
account sign-in/registration is **out of scope**. Preflight gate **failed**; all experiments C1–C9 are
**`NOT_RUN`**; the canary verdict is **`BLOCKED`** (not `NOT_QUALIFIED` — no technical failure was
observed). Full evidence: `docs/reviews/OHB2-PLAN04-ENZONIC-CANARY-EXECUTION-REPORT.md`. The HOST-01
verdict in §6 above therefore **remains `BLOCKED`**.
