# katabump-sqlite-canary

An isolated, standalone SQLite persistence **canary** for H1 validation on Katabump.

It is completely independent of OpenHandBot: no application code, no configuration, no
credentials, no network. It exists only to answer one question:

> Does the provider keep a SQLite file — **and its WAL sidecars** — across a process restart,
> a server/container restart, and a redeployment?

**H1 remains UNVERIFIED until this canary is actually run on the provider and the results are
recorded.** Provider documentation alone is not proof.

---

## Files

| File | Purpose |
|---|---|
| `canary.py` | The canary (Python standard library only). |
| `requirements.txt` | Intentionally empty (comment only) — zero third-party dependencies. It exists so the platform recognises the project as a Python project. |
| `README.md` | This file. |

No other files are needed. Do **not** upload OpenHandBot files to this server.

---

## Design (what it does and does not do)

- Standard library only: `argparse`, `os`, `sqlite3`, `uuid`, `pathlib`.
- Commands: `write`, `read`, `inspect`.
- Requires an **explicit absolute** `--db` path (e.g. `/home/container/h1_canary.sqlite3`).
- **Rejects** a database path inside the OpenHandBot repository.
- **Never** defaults to `bot_state.sqlite3`.
- **Never** reads application environment variables or `.env`.
- **Never** needs Telegram/OpenHands credentials.
- **Never** performs network requests.
- Enables **WAL** and verifies the resulting journal mode is `wal`.
- Uses a **committed** transaction.
- Prints only non-secret diagnostics (path, marker, journal mode, file existence).
- Returns **non-zero** on any failed verification.
- **Never deletes** a database.
- **Never overwrites** an existing database without the explicit `--confirm-overwrite` flag.
- Uses a **unique UUID marker** per `write` so a stale row cannot masquerade as success.
- Handles missing / read-only / inaccessible storage with a clear non-zero error.

Exit codes: `0` = success, `1` = verification/usage failure, `2` = argument error (argparse).

---

## Local smoke test (optional, outside the repository)

```sh
tmp="$(mktemp -d)"
python3 canary.py write   --db "$tmp/h1_canary.sqlite3"
python3 canary.py read    --db "$tmp/h1_canary.sqlite3"
python3 canary.py inspect --db "$tmp/h1_canary.sqlite3"
rm -rf "$tmp"
```

Expected: `write` prints `OK wrote marker=<hex> journal_mode=wal` and `FILES db=True wal=True shm=True`;
`read` prints the same marker(s). Clean up only your own temporary directory.

---

## Katabump manual setup steps

> This is a **manual operator procedure**. The repository agent has **no** Katabump account and
> creates nothing. Never paste tokens, passwords, or credentials into a chat or a log.

### A. Create the test environment (separate from OpenHandBot)

1. **Create or sign in to a Katabump account** at `katabump.com` (login with Discord or email).
   This canary needs **no** Discord bot token and **no** Telegram token.
2. **Confirm the plan is Free** and read its policy: Free = 308 MB RAM / 716 MB storage / 25% CPU /
   I/O 100, **manual renewal every 4 days**; if you miss it, the server is suspended and its **files
   are permanently deleted 1 day later**.
3. **Create a NEW Python server** dedicated to this canary. Do **not** reuse or replace any
   OpenHandBot server.
4. **Confirm the Python runtime is >= 3.11** on the "Startup" tab (select it and Save). If no
   >= 3.11 runtime is available, stop and report the test as **BLOCKED** — do not downgrade
   OpenHandBot to fit the platform.
5. **Upload only this canary package** (`canary.py`, `requirements.txt`, `README.md`) to
   `/home/container` (Web ZIP upload or SFTP). Do not upload OpenHandBot files.
6. **Set the entry point file** on the "Startup" tab to `canary.py`.

### B. Persistence test 1 — process restart

7. In the server console, run (use the provider's writable working directory):
   ```sh
   python canary.py write --db /home/container/h1_canary.sqlite3
   ```
   Record the printed `marker`, `journal_mode` (must be `wal`), and `FILES` line.
8. Click **Stop** (graceful, SIGTERM), then click **Start**.
9. Run:
   ```sh
   python canary.py read --db /home/container/h1_canary.sqlite3
   ```
   The **same marker** must appear → persistence across a **process restart** PASSES.

### C. Persistence test 2 — server/container restart

10. Click **Restart** (full container restart).
11. Run `read` again → the **same marker** must appear → **container restart** PASSES.

### D. Persistence test 3 — redeployment (the decisive test)

12. **Redeploy the same canary package** (re-upload/replace the canary files) **while keeping the
    same storage** (do not wipe `/home/container`, do not create a new server).
13. Run `read` again → the **same marker** must appear → **redeployment** PASSES.
    If the database is gone here, the redeployment test **FAILS** — record it.

### E. Record the evidence

14. Record the following **non-secret** items (no credentials, no tokens):
    - Katabump plan name and confirmation it is Free.
    - Confirmed Python runtime version (>= 3.11?).
    - The **mount path / working directory** used (e.g. `/home/container`) and whether the panel
      exposes an explicit persistent-volume/disk configuration for this server.
    - The `write` marker, and the `read` output after each of the three tests.
    - Timestamps of each step (to correlate with the 4-day renewal window).

### Distinguishing the three tests

| Test | Action | What it proves |
|---|---|---|
| **Process restart** | Stop → Start the process | The DB survives a graceful process restart on the same storage. |
| **Server/container restart** | Restart the whole server | The DB survives a full container restart on the same storage. |
| **Redeployment** | Re-upload/replace the package, same storage | The DB survives a redeployment (the decisive persistence guarantee). |

### If there is no explicit persistent volume

If Katabump does **not** provide an explicit persistent-volume/disk configuration and the panel
gives no way to pin a stable writable directory, then the three tests above cannot be trusted to
prove durability. In that case mark the result **BLOCKED** and report it — do **not** assume the
ordinary working directory is persistent.

---

## What NOT to do

- Do not upload OpenHandBot or any production files/credentials to this server.
- Do not use a production database path.
- Do not use this canary as a Backup mechanism (it is not one, and Backup is permanently excluded).
- Do not paste credentials into chat or logs.
- Do not delete the canary database unless you intentionally want to reset the test.

---

## Result interpretation

- All three tests PASS + WAL confirmed + explicit writable persistent location + renewal risk
  accepted → the operator can submit this as **H1 evidence** for review.
- Any test FAILS, or WAL is not `wal`, or there is no explicit persistent storage, or the renewal
  routine is unacceptable → **H1 stays UNVERIFIED / BLOCKED**; record the exact failure.
