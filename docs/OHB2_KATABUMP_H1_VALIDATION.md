# OHB2 — Katabump Preflight & H1 SQLite Persistence Validation

**Type:** documentation only (preflight + procedure). **Nothing was deployed, created, or executed
against Katabump.** No account or infrastructure was created. No secrets were entered, requested,
printed, or stored. No application code, configuration, test, or deployment script was modified.

| Item | Value |
|---|---|
| Repository | `TM-AEM/OpenHandBot` (local `/workspace/project/OpenHandBot`) |
| Branch | `agent/ohb2-audit-remediation` |
| HEAD | `c41a57ca30558289918cb6883a2872d0826fbfee` |
| Phase 6 plan | `docs/OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md` (present, 408 lines) |
| Katabump status | **provisional candidate only — NOT approved for production** |
| H1 (SQLite persistence) | **UNVERIFIED** |
| Autopush | DISABLED / INACTIVE |
| Production deployment | NOT AUTHORIZED |

---

## 1. Scope and authorization boundaries

In scope: review current Katabump official documentation; assess compatibility against the real
OpenHandBot requirements (from `docs/OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md` §3); assess renewal
and data-loss risk; design an **isolated** H1 canary and write an operator procedure; define H1
closure criteria.

Out of scope / forbidden (and **not done**): deploying OpenHandBot; starting production Telegram
polling; contacting production Telegram/OpenHands; creating a Katabump account or server; entering
or printing secrets; any Git write action; any Backup/snapshot/export mechanism; changing application
code or runtime configuration; changing the architecture to fit Katabump.

> **H1 is not closed by this document.** Provider documentation is **not** proof that a mounted
> volume persists. H1 closes only with the §10 evidence from an actual canary run on the provider.

---

## 2. Current Katabump official documentation findings

All findings below were retrieved on **2026-11-06** from Katabump's own documentation
(`docs.katabump.com`) and legal pages (`katabump.com/en/terms`). Confidence: **CONFIRMED** = stated
plainly in an official source; **PARTIAL** = implied/adjacent statement only; **UNKNOWN** = not
documented.

| # | Claim | Official statement (quoted/short) | Source URL | Confidence |
|---|---|---|---|---|
| 1 | Free plan eligibility | "The basic hosting plan is entirely free" — 308 MB RAM, 716 MB storage; 25% CPU, I/O 100; one free service per account/household | `https://docs.katabump.com/faq` (§General, §Resources and Limits); `https://docs.katabump.com/hosting/premium`; `https://katabump.com/en/terms` (§Access, free-service limitation) | CONFIRMED |
| 2 | No payment card required | "no credit card required" | `https://docs.katabump.com/faq` (§Is it really free?); `https://docs.katabump.com/getting-started/what-is-katabump` | CONFIRMED |
| 3 | Renewal interval | "Free servers must be renewed every 4 days" | `https://docs.katabump.com/hosting/renew-your-server` (§Renewal Policy) | CONFIRMED |
| 4 | Missed-renewal consequence | "Expiration: Server suspended"; "1 day after expiration: Server and files permanently deleted" | `https://docs.katabump.com/faq` (§What happens if I don't renew?); `https://docs.katabump.com/hosting/renew-your-server` | CONFIRMED |
| 5 | Files deleted after missed renewal | "Your server and its files are permanently deleted"; "once a server is deleted, all data is irreversibly lost" | `https://docs.katabump.com/hosting/renew-your-server`; `https://docs.katabump.com/faq` | CONFIRMED |
| 6 | Supported Python + install mechanism | Python runtime; docs reference "Python 3.8+" and a version selector on the "Startup" tab; `requirements.txt` **required**; "Runs `pip install -r requirements.txt` automatically" | `https://docs.katabump.com/guides/python`; `https://docs.katabump.com/faq` (§Files and Deployment); `https://docs.katabump.com/launch-your-bot/environment-variables` | PARTIAL (no published list of selectable versions; 3.8+ ≠ 3.11+ guarantee) |
| 7 | Startup command / process model | Entry point file (e.g. `main.py`) + runtime version set on the "Startup" tab; `package.json`/`requirements.txt` drive install. No shell-command startup documented; the platform runs the entry file | `https://docs.katabump.com/getting-started/first-steps`; `https://docs.katabump.com/launch-your-bot/environment-variables` | PARTIAL (`sh start.sh` is **not** documented; unknown whether the platform installs pip itself in the venv/global) |
| 8 | Long-running process | "We provide the infrastructure needed to host your bot 24/7" | `https://docs.katabump.com/getting-started/what-is-katabump` | CONFIRMED |
| 9 | Persistent writable filesystem | Files live under `/home/container` ("Always upload to /home/container … This is your application's working directory"); free disk = 716 MB; "renewal does not touch your files" | `https://docs.katabump.com/launch-your-bot/upload-via-sftp`; `https://docs.katabump.com/hosting/renew-your-server` | CONFIRMED (files persist between renewals; not a documented durable volume) |
| 10 | Persistence across **process restart** | Implied by Stop/Restart controls (files are not re-extracted) | `https://docs.katabump.com/hosting/manage-your-server` | PARTIAL (not explicitly stated for data) |
| 11 | Persistence across **server/container restart** | Renewal "does not touch your files"; files persist between renewals | `https://docs.katabump.com/hosting/renew-your-server` | PARTIAL |
| 12 | Persistence across **redeployment / re-upload** | Not documented. File manager exposes Delete/Edit; re-uploading/unarchiving can overwrite. No documented guarantee that a re-deploy preserves `/home/container` contents beyond "renewal doesn't touch files" | `https://docs.katabump.com/launch-your-bot/upload-via-web` | **UNKNOWN** |
| 13 | Filesystem locking / SQLite WAL compatibility | "SQLite: Yes, included in all plans" | `https://docs.katabump.com/faq` (§Can I use a database?) | PARTIAL (SQLite allowed; **no** statement about WAL, `-wal`/`-shm`, POSIX locking, or the mount's filesystem type) |
| 14 | Memory / CPU / storage / I/O limits | Free: 308 MB RAM, 716 MB disk, 25% CPU, I/O 100 ("up to 100 read/write operations per second on the disk"). RAM overrun ⇒ OOM kill + auto-restart (exit 137) | `https://docs.katabump.com/hosting/premium`; `https://docs.katabump.com/troubleshooting/out-of-memory` | CONFIRMED |
| 15 | Sleep / idle restrictions | None documented. The platform describes bots running 24/7; OOM or a crash causes an auto-restart (not idle sleep) | `https://docs.katabump.com/troubleshooting/out-of-memory` | PARTIAL (absence of a documented idle policy; not an explicit "no idle sleep" statement) |
| 16 | Outbound HTTPS to Telegram + OpenHands | Outbound is needed for the bot's own Discord API calls; the platform is a general app host ("web applications, backend services, APIs, scripts"). Discord API egress is rate-limited to 250 req/min/account | `https://katabump.com/en/terms` (§Services, §Purpose); `https://docs.katabump.com/limitations-and-rules/discord-rate-limit` | PARTIAL (general outbound assumed; **Telegram/OpenHands reachability not explicitly documented**) |
| 17 | Renewal reminders | "You will receive reminders by email and on Discord"; enable Discord Alerts; add `noreply@katabump.com` to contacts | `https://docs.katabump.com/hosting/renew-your-server` (§Enable Reminders); `https://docs.katabump.com/faq` | CONFIRMED (mechanism exists; reliability not guaranteed) |
| 18 | Platform scope (not Discord-only) | "hosting of online applications of any type (including but not limited to Discord bots, **web applications, backend services, APIs, scripts**, and other compatible applications)" | `https://katabump.com/en/terms` (§Services, §Purpose) | CONFIRMED |
| 19 | Graceful shutdown | "Stop – Graceful shutdown (sends SIGTERM to the process)" | `https://docs.katabump.com/hosting/manage-your-server` | CONFIRMED |
| 20 | Automatic renewal | "Automatic renewal is available for paid plans… For free servers, all renewals are manual." | `https://docs.katabump.com/hosting/renew-your-server` | CONFIRMED |
| 21 | Early renewal window | Free servers: "You can only renew within the 2 days before expiration (due date included)." | `https://docs.katabump.com/faq`; `https://docs.katabump.com/hosting/renew-your-server` | CONFIRMED |
| 22 | Backups on free plan | Plan table: Free **Backups = 0** (paid plans get 2–10) | `https://docs.katabump.com/hosting/premium` | CONFIRMED (this is a provider feature count, **not** used by OpenHandBot) |

> Note on #22: the provider lists a "Backups" column on its plans. OpenHandBot does **not** use and
> must **not** introduce any Backup feature or substitute (§12). This row is recorded only to show
> the free plan has none — it is not a recommendation to use it.

---

## 3. Katabump compatibility matrix

Assessed against the real requirements in `docs/OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md` §3.
Result legend: **PASS / CONDITIONAL / FAIL / UNKNOWN**.

| Requirement (source) | Katabump capability | Result | Basis |
|---|---|---|---|
| Python ≥ 3.11 (`bot/bootstrap.py::MIN_PYTHON`; CI 3.11/3.13) | Docs mention "Python 3.8+" and a version selector; no published list of versions | **UNKNOWN** | Must confirm a ≥ 3.11 runtime is selectable before committing |
| Single long-running process (`bot/app.py`) | 24/7 bot hosting; one entry point | **PASS** | `what-is-katabump`, `first-steps` |
| Telegram **long polling** (no inbound port) | Outbound-only networking assumed; no inbound port needed | **CONDITIONAL** | Telegram reachability not explicitly documented (#16) |
| Optional ASGI server (`MINI_APP_ENABLED=1`, bind `0.0.0.0:$MINI_APP_PORT`) | No documented inbound/public port exposure | **UNKNOWN / not needed** | Only relevant if the Mini App is enabled; the bot-only target avoids it |
| Writable persistent storage | `/home/container`, 716 MB, persists between renewals | **CONDITIONAL** | Writable + renewal-safe (#9–#11); redeploy persistence UNKNOWN (#12) |
| Absolute SQLite DB path (`DB_PATH`) | Absolute path under `/home/container` is settable | **PASS** | `upload-via-sftp` (working dir) + config docs |
| WAL + `-wal`/`-shm` behavior (`bot/db.py`) | SQLite allowed; WAL/locking not documented | **UNKNOWN** | Must be proven by the canary (#13) |
| Filesystem locking (POSIX `flock`/`mmap`) | Not documented | **UNKNOWN** | Same as above |
| Graceful shutdown (`SIGTERM` → `wal_checkpoint(TRUNCATE)` → close) | "Stop – Graceful shutdown (sends SIGTERM)" | **PASS** | `manage-your-server` |
| Restart behavior | Start/Stop/Restart controls; auto-restart on OOM | **CONDITIONAL** | `manage-your-server`, `out-of-memory` |
| Resource limits | 308 MB RAM, 716 MB disk, 25% CPU, I/O 100 | **CONDITIONAL** | RAM is adequate for the bot; **I/O 100 ops/s** needs verification for SQLite WAL |
| Network egress (Telegram + OpenHands HTTPS) | General outbound; explicit Telegram/OpenHands not documented | **CONDITIONAL** | #16 |
| Dependency install (`requirements.txt`) | Auto `pip install -r requirements.txt` | **PASS** | `faq` (§dependency installation) |
| Start command `sh start.sh` | Only an entry-file/version startup model is documented | **CONDITIONAL** | Use `main.py` as the entry file; `start.sh` is not a documented start command |

**Architecture note:** no change to OpenHandBot is required or proposed to fit Katabump. The
bot-only target (`MINI_APP_ENABLED=0`, one process, long polling, `main.py` entry) matches the
platform's documented model. If the Mini App is later enabled, an inbound/public port would be
needed and is **not** documented — treat that as a separate, unverified requirement.

---

## 4. SQLite WAL compatibility assessment

OpenHandBot uses `sqlite3.connect(path, check_same_thread=False)` with
`PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` (`bot/db.py`), a single connection owned by
one process, and `PRAGMA wal_checkpoint(TRUNCATE)` + `close()` on graceful shutdown.

Implications for Katabump:

- WAL creates sidecar files `bot_state.sqlite3-wal` and `bot_state.sqlite3-shm` next to the database.
  They must live on the **same** filesystem as the DB (they do, when `DB_PATH` is under
  `/home/container`).
- WAL requires working POSIX advisory locking and `mmap`/shared memory on the host filesystem.
  A normal local block volume/overlayfs satisfies this; some network/overlay mounts do not.
  **Katabump does not document its filesystem type or locking semantics** ⇒ **UNKNOWN**.
- The free plan's **I/O 100 (≈100 read/write ops/s)** is a shared node limit. WAL checkpoints and
  normal writes must fit within it; this is a performance/robustness risk to **verify**, not assume.
- Because only one process owns the DB, the multi-writer problem WAL guards against is minimal here;
  the main risk is the **mount**, not concurrency.

**Conclusion:** SQLite is *allowed* by Katabump ("SQLite: Yes, included in all plans"), but WAL
compatibility on the actual mount is **UNVERIFIED**. It must be proven by the §6 canary (create the
DB with WAL, confirm the `-wal`/`-shm` sidecars appear, commit, restart, and read the row back).

---

## 5. Renewal and data-loss risk

| Aspect | Finding | Source | Confidence |
|---|---|---|---|
| Interval | Every **4 days** (free) | renew-your-server | CONFIRMED |
| Manual or automatic | Free = **manual** (button in dashboard or via Discord); paid = automatic | renew-your-server | CONFIRMED |
| Early-renew window | Only within the **2 days before** expiration (free) | faq / renew-your-server | CONFIRMED |
| Missed renewal | **Suspended** at expiration; **files permanently deleted 1 day later** | faq / renew-your-server | CONFIRMED |
| Grace period | **~1 day** (free); "very short grace period" | renew-your-server | CONFIRMED |
| Reminders | Email + Discord alerts (opt-in); add `noreply@katabump.com` to contacts | renew-your-server | CONFIRMED (mechanism exists; delivery not guaranteed) |
| Recovery after deletion | "No, once a server is deleted, all data is irreversibly lost" | faq / renew-your-server | CONFIRMED |

**Consequences for OpenHandBot local state if the server is deleted:** the entire SQLite file is
lost, including `watched`, `user_state`, `outbox` (incl. undelivered prompts), `creation_jobs`,
`completion_pending`, `settings`, notification state/inbox, and `deleted_conversations` tombstones.
Remote OpenHands conversations are unaffected; local follow-ups/settings must be reconfigured.

**Assessment:** an unattended production deployment on Katabump Free requires a **reliable 3-day
renewal routine**. A single missed window (2-day early window + 1-day grace) means irreversible data
loss. This is a **material operational risk**. No Backup system, snapshot, or export may be proposed
as a workaround (permanent exclusion). Therefore:

- **Katabump Free is suitable only for a hobby/personal deployment** with an operator who reliably
  performs the manual renewal (and can tolerate full local-state loss if missed).
- **If a reliable renewal process cannot be established, Katabump is unsuitable for unattended
  production operation** (classification: NOT_READY for unattended production).

---

## 6. Isolated H1 canary design

The canary is **independent of OpenHandBot**: a tiny standalone script using only the Python standard
library (`sqlite3`, `uuid`, `time`, `os`). It uses **no** Telegram token, **no** OpenHands key,
**no** external API calls, **no** production DB path, and **no** Telegram polling. It is a *separate*
server/project on Katabump, not OpenHandBot.

**Design principles**
- Disposable DB file: `h1_canary.sqlite3` under the canary project dir (e.g. `/home/container`).
- Unique marker per run so a stale row cannot masquerade as success: `marker = uuid4().hex`.
- Deterministic modes so the operator can re-run after each restart/redeploy:
  - `python canary.py write`  → create DB (WAL), insert `(marker, created_utc)`, commit, print the
    marker, then list the DB directory to show `-wal`/`-shm` sidecars.
  - `python canary.py read`   → open the same DB, print the stored marker and its `journal_mode`.
- No secrets, no network, no OpenHandBot imports.

**Canary script (to be created on the Katabump server only — not in this repository):**

```python
#!/usr/bin/env python3
# Isolated H1 canary: stdlib only. No OpenHandBot code, no secrets, no network.
import os, sqlite3, sys, uuid, datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "h1_canary.sqlite3")

def connect():
    con = sqlite3.connect(DB, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")       # mirror OpenHandBot's WAL requirement
    con.execute("PRAGMA busy_timeout=5000")
    return con

def write():
    marker = uuid.uuid4().hex
    con = connect()
    with con:
        con.execute("CREATE TABLE IF NOT EXISTS canary (marker TEXT PRIMARY KEY, created_utc TEXT)")
        con.execute("INSERT INTO canary (marker, created_utc) VALUES (?, ?)",
                    (marker, datetime.datetime.now(datetime.timezone.utc).isoformat()))
    mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    con.close()
    print("WROTE", marker, "journal_mode=", mode)
    print("DIR", os.path.dirname(DB), "FILES", sorted(os.listdir(os.path.dirname(DB))))

def read():
    if not os.path.exists(DB):
        print("MISSING_DB"); return
    con = connect()
    rows = con.execute("SELECT marker, created_utc FROM canary ORDER BY created_utc").fetchall()
    mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    con.close()
    print("journal_mode=", mode)
    for m, c in rows:
        print("ROW", m, c)

if __name__ == "__main__":
    (write if (len(sys.argv) > 1 and sys.argv[1] == "write") else read)()
```

**What each step proves**
1. `write` → the DB is created on the mount; `journal_mode=wal` proves WAL is accepted; the `DIR`
   listing shows `h1_canary.sqlite3`, `-wal`, `-shm`.
2. Graceful **Stop** (SIGTERM) → the process ends cleanly.
3. **Start** again → `read` shows the same marker ⇒ survives a **process restart**.
4. **Restart** from the panel → `read` again ⇒ survives a **container restart**.
5. Re-upload/redeploy the canary project (same server) → `read` ⇒ survives a **redeployment**
   (this is the step Katabump does **not** document; it is the decisive H1 test).
6. Record the mount identity/path from the panel (non-secret).

---

## 7. Step-by-step operator procedure

> Documentation only. Do **not** execute without the separate explicit authorization required to
> create a Katabump account/server. Never paste secrets into a chat or a log.

**Preconditions**
- [ ] A Katabump account exists and one **free** Python server is available (account creation is a
      separate, user-authorized action — **not** part of this task).
- [ ] The selectable Python runtime is confirmed **≥ 3.11** (else stop — the app requires it).
- [ ] You accept the **4-day manual renewal** obligation (3-day reminder routine).
- [ ] No OpenHandBot files, tokens, or config are placed on the canary server.

**Required non-secret configuration**
- Canary project files only: `canary.py` (+ the auto-created `h1_canary.sqlite3`).
- Startup: entry file = `canary.py` (not `main.py`); Python version = the confirmed ≥ 3.11 runtime.
- **No** environment variables are needed for the canary (no tokens/keys).

**Disposable test data**
- A single row: `(marker=<uuid4 hex>, created_utc=<iso>)`. Fully disposable.

**Exact verification steps**
1. Upload `canary.py` to `/home/container` (Web ZIP or SFTP).
2. In the console run: `python canary.py write` → capture `WROTE <marker>` and the `DIR … FILES …`
   listing (expect the `-wal`/`-shm` sidecars).
3. Click **Stop** (graceful, SIGTERM). Confirm the process stopped.
4. Click **Start**; run `python canary.py read` → the same `<marker>` must appear ⇒ **restart OK**.
5. Click **Restart**; run `python canary.py read` → same marker ⇒ **container restart OK**.
6. Redeploy: re-upload/replace the canary project (same server, same path); run
   `python canary.py read` → same marker ⇒ **redeploy OK** (or **FAIL** if the DB is gone).
7. Record from the panel (non-secret): plan name, disk quota, and the mount/working path
   (`/home/container`).

**Evidence to capture**
- Screenshot/log of `write` (marker + sidecar listing).
- Screenshot/log of each `read` (marker present) after restart, container restart, redeploy.
- Panel screenshot of the mount/working path and plan resources.
- Date/time of each step (to correlate with renewal windows).

**Failure handling**
- `MISSING_DB` after a restart/redeploy ⇒ **H1 FAIL** for that scenario; record it and stop.
- `journal_mode` ≠ `wal` ⇒ WAL not honored on the mount; record as a blocker.
- Runtime < 3.11 ⇒ stop; Katabump is incompatible as-is (no architecture change permitted).

**Cleanup boundaries**
- Delete only the canary project (and its disposable DB) **after** all evidence is captured and
  stored off-platform (locally). Do not touch any OpenHandBot data (none exists here).

**Conditions that invalidate the test**
- Using OpenHandBot's config/services, a real token/key, or a production DB path.
- Any network call to Telegram/OpenHands.
- Treating a documentation claim as evidence (only observed canary behavior counts).
- A canary run on a paid plan when the target is the free plan (or vice versa).

---

## 8. Evidence checklist (to capture during the canary run)

- [ ] Katabump plan name + account eligibility (free, no card) confirmed.
- [ ] Selectable Python runtime version (≥ 3.11) confirmed.
- [ ] Working/mount path recorded (non-secret), e.g. `/home/container`.
- [ ] Disposable DB file shown to reside on that path (file listing + `PRAGMA journal_mode=wal`).
- [ ] `-wal` and `-shm` sidecars observed on the same path.
- [ ] Marker survives a **controlled process Stop → Start**.
- [ ] Marker survives a **controlled container Restart**.
- [ ] Marker survives a **controlled redeployment** (re-upload).
- [ ] Single-process constraint respected (one server, one entry point).
- [ ] Renewal/deletion risk reviewed and accepted by the operator (4-day manual renewal).
- [ ] Evidence is reproducible (same commands, same result) and stored locally.

---

## 9. H1 closure criteria

H1 remains **UNVERIFIED** until **all** of the following are available:

1. Actual Katabump plan and account eligibility confirmed.
2. Actual persistent storage capability confirmed.
3. Actual mounted volume identity and path recorded (non-secret).
4. Disposable SQLite database shown to reside on that volume.
5. Record survives a controlled process restart.
6. Record survives a controlled server/container restart.
7. Record survives a controlled redeployment.
8. WAL behavior verified compatible with the actual filesystem.
9. Single-process constraint enforced.
10. Renewal/deletion risk assessed as operationally acceptable.
11. Operator has reviewed and accepted the recurring (4-day) renewal requirement.
12. Evidence reviewed and reproducible.

**Provider documentation alone is insufficient to close H1.**

---

## 10. Explicit limitations and unknowns

- **Persistence across redeployment is UNKNOWN** (the decisive H1 scenario). Katabump documents that
  *renewal* does not touch files, but says nothing about re-upload/redeploy.
- **Filesystem type, locking semantics, and WAL compatibility are UNKNOWN** (no documentation).
- **The selectable Python runtime list is UNKNOWN**; "Python 3.8+" is a floor, not a guarantee of
  ≥ 3.11. This must be confirmed before any deployment attempt.
- **`sh start.sh` is not a documented Katabump start command**; the documented model is an entry
  file. Use `main.py` as the entry point (same single process).
- **Outbound reachability to Telegram and OpenHands is not explicitly documented** (only general
  outbound and Discord rate limits).
- **I/O 100 (≈100 ops/s)** may constrain SQLite WAL under load; verify during the canary and monitor.
- **Reminder delivery is not guaranteed**; the operator must own a 3-day renewal routine.
- **Free service limits:** one free service per account/household; VPN/multi-account circumvention
  risks suspension.
- **Mini App (ASGI) is out of scope** for the bot-only target; inbound port exposure is undocumented.

---

## 11. Governance compliance

- Backup feature/subsystem: **none** introduced or recommended; no snapshot/export/restore mechanism
  proposed; the provider's "Backups" plan column is **not** used (§2 #22).
- Autopush: DISABLED / INACTIVE; untouched.
- Production Telegram/OpenHands: not contacted; no polling.
- Katabump account/infrastructure: **not created**.
- Secrets: none entered, requested, printed, or stored.
- Application code/config/tests/scripts: **unchanged**.
- Git: no write action.
- Protected paths (`.openhands/`, `.agent/`, `automation/`): preserved.
