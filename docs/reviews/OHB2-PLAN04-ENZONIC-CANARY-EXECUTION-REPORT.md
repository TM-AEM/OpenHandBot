# OHB2 Plan 04 — Enzonic Python Hosting Canary — Execution Report

> Prepared by an AI agent (OpenHands) on behalf of the repository owner. **This report was created by an
> AI agent (OpenHands) on behalf of the repository owner.**
>
> **Status: `BLOCKED`.** No canary was provisioned; **no experiment (C1–C9) was run.** The reason is a
> **preflight gate failure**: there is **no authenticated Enzonic account or session** in this
> environment, and both account sign-in and account registration are **explicitly out of scope** for this
> task (authorization boundary §1). Nothing was created, uploaded, executed, or deleted; no secret was
> entered, requested, printed, or stored; no OpenHandBot code/config/schema/dependency changed.

- **Task ID:** `OHB2-PLAN04-ENZONIC-PYTHON-HOSTING-CANARY-EXECUTION-01`
- **Date/time (UTC):** 2026-11-16, ~13:00–13:30 UTC (all timestamps below are UTC unless stated)
- **Repository:** `TM-AEM/OpenHandBot` · **Baseline:** branch `main`, HEAD `56a58124f5cd677ca39e1dad19b5e3fa94b0fbc1`
- **Follow-up to (not a rewrite of):** `docs/reviews/OHB2-PLAN04-HOST01-HOSTING-QUALIFICATION.md`

---

## 1. Scope and authorization boundary

Executed strictly inside the owner-approved boundary (option A: one disposable, isolated Enzonic Python
Hosting canary). Authorized: inspect an **existing** account/entitlement; provision **one** disposable
free canary **if** no payment/card/trial/subscription is required; upload/run a **minimal independent**
Python app; perform controlled persistence/SQLite/HTTPS/runtime/resource tests; delete **only** the
disposable canary if safe.

**Not authorized and not performed:** creating a new account or submitting personal registration
details; adding a payment method or accepting any billing obligation; deploying/importing OpenHandBot
code, data, config, or secrets; configuring Telegram/OpenHands/real tokens/webhooks; enabling
`MINI_APP_ENABLED` or changing activation settings; changing OpenHandBot code/deps/schema/architecture;
creating a production service; any Git commit/push/PR/merge/release/deploy.

Per §1, the task mandates: *"Creating a new Enzonic account or submitting personal registration details.
**Stop and report if this is required.**"* — this condition is **met** (see §2).

---

## 2. Account and entitlement preflight — **GATE FAILED**

| Preflight item (§2) | Result | Evidence | Verified vs. claimed |
|---|---|---|---|
| (1) Already authenticated account available | **FAIL — none** | Panel `https://panel.enzonic.com/` and `/dashboard` render a JS shell with **no account, no server list, no username**. Clerk auth cookies show **`__client_uat = 0`** (signed-out); the only client JWT is an anonymous `client_…` token. | **Verified** (browser storage + panel) |
| (2) Python Hosting available to *this* account | **UNKNOWN** | Cannot be determined without an authenticated session. | n/a |
| (3) Selected entitlement is free, no card | **UNKNOWN (account-specific)** | Provider pages claim free/no-card (§3), but the **account's own billing state cannot be read** without sign-in. | Claimed by provider only |
| (4) No paid trial / auto-upgrade / recurring charge | **UNKNOWN (account-specific)** | Same as (3). | Claimed by provider only |
| (5) Python version + startup config | **Claimed (docs)** | `/python` (2026-11-16): Python **3.10/3.11/3.12**; "Configure dependencies, environment variables, and the **startup command** in your panel". | Provider claim, **not verified** |
| (6) Assigned storage path + persistence limits | **UNKNOWN** | Not documented; cannot inspect without a server. | — |
| (7) HTTPS hostname + certificate behavior | **UNKNOWN (account-specific)** | Provider markets a free subdomain; the account's hostname cannot be read without sign-in. | Provider claim, **not verified** |
| (8) Remains active without scale-to-zero/suspension | **UNKNOWN** | Provider claims "24/7 Always on"; cannot observe without a running canary. | Provider claim, **not verified** |
| (9) Resource/process/storage/runtime limits | **UNKNOWN** | Only provider marketing (512 MB RAM / 50% CPU / 10 GB) is available; no account-level limits visible. | Provider claim, **not verified** |

**Sign-in / registration gate (observed 2026-11-16):** `https://accounts.enzonic.com/sign-in` loads a
**Cloudflare "Just a moment…" / Turnstile** bot-verification interstitial; the panel SPA also did not
present any authenticated UI. Completing a CAPTCHA and/or signing in would require **credentials that do
not exist in this environment**, and **registering** a new account is **explicitly not authorized**.

**Credential/session sweep (filenames only; no values read or printed):** no Enzonic credential,
token, cookie, or profile exists anywhere in the environment. `~/.openhands/` contains only
`git-credentials/github.token`, `profiles/{Default,Perform}.json`, and the git credential helper; the
repo has only `.env.example` (no real `.env`); no environment variable mentions Enzonic. A filesystem
search for `*enzonic*` outside this repo's `docs/` returned nothing.

**Preflight verdict:** mandatory precondition (1) — an already authenticated account — **cannot be
verified**. Per §2 ("If any mandatory precondition cannot be verified, **do not provision**. Report the
exact blocker and mark the relevant tests `NOT_RUN`."), **no provisioning was performed.**

---

## 3. Canary architecture and exact runtime configuration

**Not instantiated.** The canary was designed (see below) but never deployed, because the preflight gate
failed. No URL, hostname, storage path, or runtime was assigned.

**Designed canary (for the record; never deployed):** a single, minimal, standalone Python process using
**only the standard library** (`http.server` or `wsgiref`), synthetic data only, no OpenHandBot code or
config, SQLite with `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000`, exactly **one** long-running
process, no worker/scheduler/daemon, minimal diagnostic endpoints that expose **no** filesystem paths,
DB contents, environment variables, or internal diagnostics, and a random non-sensitive canary id (e.g.
`canary-<8 hex>`) to distinguish the experiment. It would have been created **outside** the OpenHandBot
repository (e.g. `/workspace/ohb2-enzonic-canary/`), never committed.

---

## 4. Experiment results C1–C9

All experiments are **`NOT_RUN`**. **Reason (common):** the canary was never provisioned because the
preflight gate (§2) failed — there is no authenticated Enzonic account, and creating one is not
authorized. No provider interaction, upload, execution, or deletion occurred.

| Test | Description | Status | Reason |
|---|---|---|---|
| **C1** | Runtime and startup | **NOT_RUN** | No canary; no account to read the actual runtime or startup command. |
| **C2** | Writable storage (marker + DB) | **NOT_RUN** | No canary; storage path is account-specific and unknown. |
| **C3** | SQLite WAL + locking | **NOT_RUN** | No canary; cannot test remotely. (Local synthetic WAL/lock behaviour was proven earlier — see §11 — and is **not** evidence of Enzonic behaviour.) |
| **C4** | Process restart persistence | **NOT_RUN** | No canary; no restart mechanism accessible. |
| **C5** | Rebuild/redeploy persistence | **NOT_RUN** | No canary; operation not inspectable, so it was **not** executed (per §4/C5: do not run an ambiguous destructive operation). |
| **C6** | HTTPS and origin | **NOT_RUN** | No canary; no assigned hostname/certificate. |
| **C7** | Continuous runtime suitability | **NOT_RUN** | No canary; cannot observe sleep/scale-to-zero behaviour. |
| **C8** | Resource and operational limits | **NOT_RUN** | No canary; no observable memory/CPU/storage/process metrics. |
| **C9** | Cleanup and isolation | **PASS (trivially)** | Nothing was created, uploaded, or modified on any provider; no pre-existing Enzonic resource exists to touch; no OpenHandBot source/data/credential was introduced anywhere. |

---

## 5. Evidence and timestamps

| ID | Operation | Timestamp (UTC) | Observed result | Evidence source | Verified? |
|---|---|---|---|---|---|
| E-1 | Navigate `panel.enzonic.com/` and `/dashboard` | 2026-11-16 ~13:05 | JS shell; no authenticated UI | Browser (panel) | **Verified** |
| E-2 | Read panel cookies/localStorage | 2026-11-16 ~13:06 | `__client_uat=0` (signed-out); anonymous `client_…` JWT only | Browser storage | **Verified** |
| E-3 | Navigate `accounts.enzonic.com/sign-in` | 2026-11-16 ~13:07 | Cloudflare Turnstile "Just a moment…" challenge | Browser | **Verified** |
| E-4 | Environment credential/session sweep | 2026-11-16 ~13:10 | No Enzonic credential/session anywhere | Shell (`find`/`ls`/`env`, names only) | **Verified** |
| E-5 | Re-fetch Enzonic `/python` and `/free` | 2026-11-16 **13:15:49Z** | Free-tier claims (512 MB / 50% CPU / 10 GB / 24-7; no card; one free server per account, subject to capacity) | Provider pages (HTTP 200) | **Claimed by provider only** |

Provider-page claims are **marketing claims**; they are **not** upgraded to PASS in this report.

---

## 6. Resource measurements

**None obtained.** No canary ran, so there are no provider-side memory/CPU/storage/process measurements.
(For context only, and explicitly **not** a provider capacity guarantee: an earlier local measurement of
the OpenHandBot import footprint was 58.4 MiB peak RSS — local, not provider-side.)

---

## 7. Failed, blocked, and unrun tests

- **Failed:** none (nothing was executed, so nothing failed).
- **Blocked:** the **entire canary** is `BLOCKED` at the preflight gate (no authenticated account;
  account creation not authorized).
- **Unrun:** C1, C2, C3, C4, C5, C6, C7, C8 (all `NOT_RUN`).
- **Trivially passed:** C9 (cleanup/isolation — nothing created, so nothing to clean).

---

## 8. Cleanup outcome

**Nothing to clean up.** No Enzonic resource was created, modified, or deleted. No pre-existing Enzonic
resource was accessed or altered (none is reachable without authentication). No file was uploaded to any
provider. No OpenHandBot artifact was introduced outside the repository.

---

## 9. HOST-01 final verdict (this canary)

**`BLOCKED`.**

The canary could **not be run**, so Enzonic Python Hosting **cannot be qualified or disqualified** on
technical evidence from this task. This is a **test that could not be run** (authorization/precondition
blocker), **not** a technical failure of Enzonic.

### Requirement qualification matrix (from §6 of the task)

| Mandatory requirement | Status | Evidence |
|---|---|---|
| Free with no card/payment | **UNVERIFIED** (provider claim only) | E-5 (provider pages) |
| Supported Python runtime | **UNVERIFIED** | Provider claims 3.10–3.12 (E-5); no actual runtime test |
| Persistent writable filesystem | **UNVERIFIED** | No marker/DB survival test |
| SQLite WAL support | **UNVERIFIED** | No actual SQLite test on the host |
| SQLite locking behavior | **UNVERIFIED** | No contention test on the host |
| Process restart survival | **UNVERIFIED** | No remote restart test |
| Rebuild/redeploy survival | **UNVERIFIED / NOT_RUN** | Operation not inspectable |
| Stable HTTPS origin | **UNVERIFIED** | No assigned URL/certificate |
| Continuous process suitability | **UNVERIFIED** | No observation of sleep/scale-to-zero |
| Single-process architecture | **UNVERIFIED** | No runtime/process inspection |
| Resource sufficiency | **UNVERIFIED** | No provider measurements |
| Operational visibility | **UNVERIFIED** | No logs/restart controls observed |

**Rule applied:** *"Do not qualify the host if any mandatory requirement remains unverified."* → Enzonic
Python Hosting is **not qualified** here; the outcome is **`BLOCKED`**, not `NOT_QUALIFIED` (the latter
would require technical evidence of failure, which does not exist).

---

## 10. HOST-02 status (kept separate)

**`BLOCKED` — unchanged and independent.** This canary **does not** authorize Mini App activation or
OpenHandBot deployment. HOST-02 remains blocked until its activation gates are separately satisfied
(`docs/reviews/OHB2-PLAN04-HOST02-ACTIVATION-READINESS.md`). Verified in this session:

- `MINI_APP_ENABLED` default is still **`False`** (`bot/config.py:262`).
- No activation setting or production URL was changed.
- Autopush remains **disabled/inactive** (no process).
- No OpenHandBot deployment or production service was created.
- No OpenHandBot code, schema, dependency, or configuration changed (working tree = docs/ + `.agent/`
  only).
- Plan 03 remains administratively closed with its existing provider blocker
  (`WS-02 = BLOCKED_BY_PROVIDER_CAPABILITY`).

---

## 11. Precise recommendation for the next owner decision

**Blocker to clear:** there is no authenticated Enzonic account available to this agent, and account
creation/sign-in is out of scope. The canary cannot proceed without an owner action.

**Owner action required (choose exactly one):**

- **(A)** **Sign in** to the existing Enzonic account in this browser session (or provide a supported,
  non-secret session the agent may use), and confirm the account has a **free, no-card** Python Hosting
  entitlement. Then this exact task can be re-run and C1–C9 executed.
- **(B)** If **no** account exists, the owner must either (i) create one **personally** (registration is
  not authorized for the agent), or (ii) authorize a different free/no-card host (e.g. Northflank
  Sandbox) for the same canary protocol.
- **(C)** Accept the status quo (app stays local-only) until a host is chosen.

**Explicitly not recommended / not done:** creating an account, adding a payment method, entering any
paid trial, or deploying OpenHandBot.

**Definition of done for a future canary run:** provision one disposable free Python Hosting instance
(no card), deploy the minimal stdlib canary, execute C1–C9 with recorded evidence, then delete only the
canary. Only if **every** mandatory requirement is directly verified may HOST-01 be `QUALIFIED`.

---

## 12. Governance compliance (final)

- No account created; no payment/card/trial/subscription; no billing obligation.
- No canary provisioned; nothing uploaded or executed on any provider; nothing deleted.
- No OpenHandBot code/data/config/secret imported anywhere; no Telegram/OpenHands/webhook configured.
- `MINI_APP_ENABLED` untouched (off); no activation; Autopush inactive.
- No OpenHandBot code/deps/schema/architecture change; **no commit/push/PR/merge/release/deploy**.
- This is a **new dated follow-up report**; historical reports were **not** rewritten and their original
  findings are unchanged.
