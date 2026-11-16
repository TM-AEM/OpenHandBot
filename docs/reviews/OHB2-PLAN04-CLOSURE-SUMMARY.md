# OHB2 Plan 04 — Closure / Progress Summary (HOST-01 + HOST-02)

> Prepared by an AI agent (OpenHands) on behalf of the repository owner. **Documentation only.**
> No account, no provisioning, no deployment, no Mini App activation, no secret recorded, no Git
> publication.

- **Task ID:** `OHB2-PLAN04-HOSTING-QUALIFICATION-AND-MINIAPP-GATES-EXECUTION-02`
- **Date (UTC):** 2026-11-16
- **Repository:** `TM-AEM/OpenHandBot` · **Baseline:** `main` @ `56a58124f5cd677ca39e1dad19b5e3fa94b0fbc1`
- **Deliverables:** `docs/reviews/OHB2-PLAN04-HOST01-HOSTING-QUALIFICATION.md`,
  `docs/reviews/OHB2-PLAN04-HOST02-ACTIVATION-READINESS.md`, this summary.

## Verdicts

| Workstream | Verdict | One-line reason |
|---|---|---|
| **HOST-01** — free/no-card host qualification | **`BLOCKED`** | No candidate has actual persistence/runtime proof; all remote canaries `NOT_RUN`. Enzonic Python panel is the best free/no-card fit on paper but persistence + SQLite locking are `UNKNOWN`. |
| **HOST-02** — Mini App activation readiness | **`BLOCKED`** | Gates 1, 2, 7, 8, 10, 12 fail/unresolved; no owner activation approval. Mini App stays **disabled**. |

## What was verified (not just documented)

- Application architecture facts + measured peak import RSS **58.4 MiB** vs Enzonic's 512 MB free tier.
- **Local synthetic SQLite proof** (`/tmp/ohb2_host01_proof/proof.py`): WAL + `busy_timeout=5000` +
  sidecar files + survives a process restart + single-owner lock enforced.
- `MINI_APP_ENABLED` default is **False**; malformed value ⇒ `ConfigError`; enabled-without-URL ⇒
  fail-closed; no alternate activation path; disabled build exposes no HTTP surface.

## Enzonic — the four service paths are distinct

- **Python Hosting (panel)** — free 512 MB / 50% CPU / 10 GB / 24/7, no card; Python 3.10–3.12 +
  `requirements.txt` + custom startup command (Uvicorn/Gunicorn). **Persistence UNKNOWN.**
- **Web Hosting (panel)** — **same underlying product**; not a second entitlement.
- **Deploy / Cloud** — **FAIL** for this architecture (serverless scale-to-zero; Hobby sleeps 15 min).
- **Game Hosting** — **FAIL** (hibernates; not a supported Python app runtime).

## Plan 03 baseline preservation (re-verified 2026-11-16, not re-done)

The task header named `OHB2-PLAN03-WS01-WS02-EXECUTION-ONLY-05`, but Plan 03 is **already complete and
committed** (`56a5812`); it was **not** reverted, overwritten, or recreated.

- **WS-01 (hierarchical folder navigation) — `DONE`.** Artifacts present and intact:
  `bot/web/static/files.js` (9,472 bytes), `app.js::renderFilesSection` (crumbs + "⬆️ لأعلى" + rows),
  `index.html` (`/mini/files.js?v=7`), `styles.css`; tests `tests/frontend/files.test.js`,
  `tests/frontend/files_watch.test.js`, `tests/test_miniapp_files.py`.
- **WS-02 (individual workspace file download) — `BLOCKED_BY_PROVIDER_CAPABILITY` (re-confirmed live).**
  Fetched 2026-11-16: Cloud V1 `openapi.json` = **v1.92.0, 257 paths, 0** `octet-stream`/binary/
  multipart responses (no workspace byte-download route); Agent SDK = **v0.1.0, 40 paths**, with exactly
  **one** byte route `GET /api/file/download/{path}` that requires the server-wide `X-Session-API-Key`
  (risk B1, rejected). No local download route exists; download-like paths return **404**. Unchanged.

## Remaining blockers

1. Remote persistence + SQLite locking on the chosen host — **NOT_RUN** (needs a disposable canary +
   owner approval).
2. Enzonic free capacity behaviour when full — **UNKNOWN**.
3. Northflank free persistent-volume entitlement — **UNKNOWN**.
4. Real Android 12 Telegram WebView verification — **NOT_RUN**.
5. MT-2 provider-side limitation — **BLOCKED** (P0); WS-02 — **`BLOCKED_BY_PROVIDER_CAPABILITY`**.
6. Owner activation approval — **not recorded**.

## Owner approvals required next (one item)

Choose **one** next step (no selection made here): **(A)** authorize an Enzonic Python-panel canary,
**(B)** authorize a Northflank Sandbox canary, or **(C)** stay local-only.
