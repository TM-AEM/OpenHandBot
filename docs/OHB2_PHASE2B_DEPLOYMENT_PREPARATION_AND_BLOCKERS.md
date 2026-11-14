# OHB2 Phase 2B — Deployment Preparation & Blocker Report

**Task ID:** `OHB2-PHASE2B-AUTHORIZED-HOSTING-DEPLOYMENT-AND-OPERATIONAL-VALIDATION`
**Status (final classification):** **`BLOCKED_PENDING_EXPLICIT_AUTHORIZATION`**
**Secondary blockers:** also `BLOCKED_PENDING_REQUIRED_EVIDENCE` (Phase 1 review = HIGH; no CI on
the candidate revision; Phase 2A qualified **no** host).
**Date:** 2026-11-08
**Result:** **No deployment action was taken.** No provider account/resource was created, no DNS
change, no Mini App enablement, no production credential set, no commit/push.

---

## 0. Why nothing was deployed (summary)

The task's own precondition is an **explicit deployment authorization** from the user in the
current instruction context, plus a set of **mandatory prerequisites**. Neither is present:

1. **No explicit deployment authorization exists.** The task text explicitly says a task
   *template*, prior attempts, or provider access are **not** authorization. Nothing in the
   current context authorizes deployment, resource creation, DNS change, Mini App enablement, or
   production credentials. ⇒ the task's own rule applies: complete only non-destructive
   preparation and report `BLOCKED_PENDING_EXPLICIT_DEPLOYMENT_AUTHORIZATION`.
2. **Phase 1 is not complete/approved for Phase 2.** The independent review of the current
   revision returned **VERDICT: HIGH** (unresolved HIGH + MEDIUM). Phase 1's own gate requires a
   clean review with no unresolved Critical/High.
3. **The exact source revision is not a reviewed revision.** HEAD `5b10850` has **no CI run** (CI
   only triggers on `main`), and the working tree additionally carries **uncommitted** changes
   (including a partial, in-progress fix set). Deploying that would be deploying an unreviewed,
   uncommitted state.
4. **No host is qualified to deploy to.** Phase 2A concluded `NO_QUALIFIED_FREE_NO_CARD_HOST`
   (Northflank Free is the strongest candidate but its free-tier persistent-volume entitlement is
   UNVERIFIED; every other free/no-card option fails the durability bar). The task forbids
   substituting a different provider without a new qualification decision.

Per the task ("If any of these prerequisites cannot be proven, stop and report the blocker") and
AGENTS.md §9, the correct action is to stop and report — not to deploy.

---

## 1. Mandatory prerequisite verification (task §2) — item by item

| # | Prerequisite | Result | Evidence |
|---|---|---|---|
| 1 | Read `AGENTS.md` fully | ✅ DONE | 165 lines, 14 sections; sha256 `f86f189c…8ad3` (unchanged) |
| 2 | Phase 1 complete & approved for Phase 2 | ❌ **FAIL** | Phase 1 review = HIGH; Phase 1 gate open (`.agent/PROGRESS.md:699-701`) |
| 3 | Final Phase 1 review has no unresolved CRITICAL/HIGH/MEDIUM | ❌ **FAIL** | 1×HIGH + 2×MEDIUM unresolved |
| 4 | Exact source revision identified | ⚠️ PARTIAL | HEAD `5b108503d182e3db28aa720df930a3344c8b4c8a` — but **uncommitted** changes present ⇒ not deployable |
| 5 | Branch & remote state verified | ✅ DONE | branch `agent/ohb2-phase1c-inbox-filter-archive-delete`; HEAD == `origin/<branch>` (in sync) |
| 6 | All required CI checks passed for that revision | ❌ **FAIL** | `gh run list --commit 5b10850…` ⇒ **0 runs**; CI triggers only on `main` |
| 7 | No unintended files / unrelated changes included | ❌ **FAIL** | 7 modified + 4 untracked paths in the working tree |
| 8 | Phase 2A hosting qualification report verified | ✅ DONE | `docs/OHB2_PHASE2A_FREE_HOSTING_QUALIFICATION.md` (classification `NO_QUALIFIED_FREE_NO_CARD_HOST`) |
| 9 | Selected provider + exact plan verified | ❌ **FAIL** | no qualified plan exists to select |
| 10 | Plan is free & needs no card/paid subscription | ⚠️ PARTIAL | Northflank Free = free/no-card (checked 2026-11-08) but **not qualified** |
| 11 | Provider storage requirements & limitations verified | ⚠️ PARTIAL | free-tier volume entitlement UNVERIFIED |
| 12 | Provider is the same candidate qualified in Phase 2A | ➖ N/A | Phase 2A qualified none |
| 13 | No substitution of a different provider | ✅ DONE | none attempted |

**Outcome:** prerequisites #2, #3, #6, #7, #9 are unproven ⇒ stop and report (task §2).

---

## 2. Provider re-check (2026-11-08, official pages)

Re-confirmed today; nothing changed that would qualify a host:

- **Northflank Sandbox Free** — free, **"No card needed"**, **always on, no sleeping**, 2 services
  / 2 jobs / 1 database, up to $20/mo of free resources; persistent volumes "persist data across
  restarts"; Single Read/Write volume **forces 1 instance**; generated subdomain + automatic
  Let's Encrypt TLS. **The one open question remains: whether a persistent volume is included in
  the *free* allowance — official pages do not state it (UNVERIFIED).**
- **Katabump Free** — free/no-card, but **files deleted permanently 1 day after a missed 4-day
  renewal**, and no documented inbound port / HTTPS ingress. Rejected.
- **Enzonic** — current free tier is a **hibernating game server** (R2-archived ⇒ ephemeral).
  Rejected.
- **Render / Railway / Fly / Koyeb / Oracle** — ephemeral FS / trial→paid / no free tier / card
  required. Rejected.

**No provider may be substituted without a new qualification decision.**

---

## 3. Non-destructive preparation performed (allowed by the task)

### 3.1 Deployment scope guardrails (to honour once authorized)

- One application process; one SQLite owner; existing workers/outbox only; existing startup
  arrangement; existing migration mechanism.
- **No** duplicate bot/web process, **no** second SQLite owner, **no** horizontal replicas,
  **no** separate scheduler, **no** external DB replacement.
- **No** new hosting services or paid resources; **no** paid upgrade; **no** trial that
  auto-converts to paid.
- **Backup is permanently out of scope** — no Backup feature, provider, cloud drive, SFTP, or
  dependency. The consequence is explicit and not concealed: **loss of the local SQLite file means
  loss of local operational state.**

### 3.2 Storage / SQLite preparation rules (to apply once a host is qualified)

- Identify the provider's **durable** storage location; verify mounted + writable.
- Set an **explicit, stable, absolute** `DB_PATH` on that durable filesystem (never the ephemeral
  container FS).
- Confirm only the single approved process owns the DB; keep `PRAGMA journal_mode=WAL` +
  `busy_timeout=5000` (verified in `bot/db.py:330-335`) and the startup integrity gate
  (`main.py` refuses to start on a bad DB).
- **Never** reset/delete/replace the DB or change `DB_PATH` in a way that silently creates a new
  empty DB. If a DB already exists, verify its identity/state before starting.
- Confirm sufficient disk for the current DB + reasonable growth (measured: 200 inbox rows
  < 10 KB; earlier populated DB ≈ 1.5 MB).
- Confirm logs/temp files never contain secrets (`main.py` sets up log redaction of
  `config.secrets`).

### 3.3 Environment-variable inventory (names only — from actual code)

Source of truth: `bot/config.py` (+ `automation/autopush/main.py`).

**Mandatory (ConfigError if missing):**
- `TELEGRAM_BOT_TOKEN` — must match `123456:ABC…`
- `OPENHANDS_API_KEY` — ≥ 8 chars, no spaces/control chars
- `ALLOWED_TELEGRAM_ID` — ≥ 1 numeric id

**Storage / runtime:**
- `DB_PATH` (default `bot_state.sqlite3`) — set to an absolute path on the durable volume
- `OPENHANDS_BASE_URL` (default `https://app.all-hands.dev`; HTTP only allowed for loopback)
- `WATCHER_INTERVAL` (default 25)
- `LOG_LEVEL` (default INFO)

**Mini App (must stay disabled until gates pass):**
- `MINI_APP_ENABLED` (default **False** — keep disabled)
- `MINI_APP_URL` (only after HTTPS stability is established)
- `MINI_APP_PORT` (default 12000)
- `MINI_APP_COOKIE_SECURE` (default True)
- `MINI_APP_TRUSTED_PROXIES`, `MINI_APP_ALLOWED_ORIGINS`
- `MINI_APP_SESSION_TTL`, `MINI_APP_INITDATA_MAX_AGE`
- `MINI_APP_AUTH_RATE_PER_MINUTE`, `MINI_APP_AUTH_RATE_PER_HOUR`, `MINI_APP_API_RATE_PER_MINUTE`,
  `MINI_APP_RATE_MAX_KEYS`

**Autopush (must remain DISABLED/INACTIVE — do not set/activate):**
- `AUTOPUSH_REPO_DIR`, `AUTOPUSH_REPO_URL`, `AUTOPUSH_BRANCH`, `AUTOPUSH_REMOTE`,
  `AUTOPUSH_INTERVAL`, `AUTOPUSH_AUTHOR_NAME`, `AUTOPUSH_AUTHOR_EMAIL`

**Do not introduce any env var not present in the code above.**

### 3.4 Secrets handling rules

- Use the provider's secret/env interface; **never** ask the user to paste credentials in chat.
- Never place credentials in tracked files, deploy scripts, shell history, URLs/query strings,
  logs, error reports, screenshots, commit messages, or PR descriptions.
- Verify only **presence/validity** at a high level; never print secret values.
- Repo hygiene verified: `.env` is git-ignored and absent locally; no `.env`/`*.sqlite3` tracked;
  only `.env.example` is tracked. No provider CLI credential state present.

### 3.5 Safety gates (task §6)

- `MINI_APP_URL` set only after HTTPS stability is proven.
- `MINI_APP_ENABLED` stays **off** until deployed + reachable + auth correct + persistence gates
  pass.
- Autopush stays **DISABLED/INACTIVE**; no scheduled execution; no Backup settings.
- Preserve auth/Origin/CSRF/rate-limit/cookie/proxy/ownership protections; do not weaken security
  for provider limitations.

### 3.6 Persistence proof-test plan (design only — NOT executed)

T1 DB on durable storage (`journal_mode=wal`, `-wal`/`-shm` beside `app.db`, path under the
volume) · T2 survives process restart · T3 survives container recreation (only if volume retention
is documented) · T4 survives redeploy · T5 survives suspend/resume · T6 exactly one DB owner ·
T7 stable HTTPS URL + trusted cert · T8 cold start/recovery. All use a harmless sentinel record on
an isolated canary — never a real user record. **Do not claim durable storage proven by
process-restart testing alone.**

### 3.7 Rollback plan (design only)

Application-code rollback to a previously approved revision that **preserves** the DB and is
migration-compatible; **never** delete/recreate the volume, reset the DB, erase records, run two
owners simultaneously, re-enable automation, or trigger duplicate delivery/creation. If a schema
migration is not safely reversible, document the recovery implications before proceeding. No
destructive rollback without explicit approval.

### 3.8 Monitoring & handoff checklist (to complete after a real deploy)

Public HTTPS URL · exact deployed revision · provider + plan · DB path (non-sensitive) · durable
volume identity · process/memory limits · restart procedure · deploy procedure · env-var names ·
health/readiness endpoints · free-tier restrictions & suspension behaviour · persistence evidence
· remaining unverified lifecycle events · manual recovery procedures · delivery/reconciliation
limitations. **No HA/uptime/permanence claims without provider evidence + real tests.**

---

## 4. Acceptance criteria (task §15) — status

| # | Criterion | Status |
|---|---|---|
| 1 | Explicit deployment authorization verified | ❌ not present |
| 2 | Exact approved revision deployed | ❌ not deployed |
| 3 | Provider + free/no-card plan remain valid | ❌ no qualified plan |
| 4 | HTTPS + stable Mini App URL work | ❌ not deployed |
| 5 | SQLite on qualified durable storage | ❌ not deployed |
| 6 | Persistence tests passed / unverified documented | ❌ not run (documented as unverified) |
| 7 | Single-process / single-owner preserved | ➖ design preserved; not deployed |
| 8 | Required env settings installed securely | ❌ not installed |
| 9 | Mini App enabled only after gates pass | ➖ stays disabled (correct) |
| 10 | Autopush disabled/inactive | ✅ verified disabled |
| 11 | No Backup functionality introduced | ✅ none introduced |
| 12 | No unauthorized Telegram/OpenHands production ops | ✅ none performed |
| 13 | Deployment smoke tests pass | ❌ not run (not deployed) |
| 14 | Remaining limitations documented accurately | ✅ this document |

---

## 5. Governance compliance

- No provider account/resource created; no paid resource; no trial accepted.
- No deployment; no DNS change; no Telegram Bot change; `MINI_APP_ENABLED` not enabled; no
  production credentials set; no production API call; no Telegram message; no real OpenHands
  conversation create/delete; no Autopush; no Backup.
- No commit, push, merge, PR, release, force-push, `git reset --hard`, or `git clean`.
- Git remotes unchanged; branch history unchanged; unrelated local work preserved.
- Provider facts quoted from official pages and dated 2026-11-08; anything not stated officially
  is marked UNVERIFIED.

## 6. What unblocks this task

1. Owner fixes the Phase 1 review findings (HIGH + MEDIUM) and obtains a clean re-review.
2. Owner authorizes the exact revision to deploy, and that revision is committed/pushed and
   passes CI (or CI is extended to cover the deploy branch) — or the owner explicitly accepts a
   non-CI-verified revision in writing.
3. Owner either (a) authorizes a **Northflank canary** to prove free-tier volume durability
   (tests T1–T8), or (b) approves a different qualified free/no-card provider via a new
   qualification decision.
4. Owner gives **explicit deployment authorization** in the task context, and separately
   authorizes any restricted production functional actions (real Telegram/OpenHands operations).
