# OHB2 Plan 04 — HOST-02 Mini App Activation-Readiness Audit

> Prepared by an AI agent (OpenHands) on behalf of the repository owner. **Audit + documentation
> only.** The Mini App was **not** enabled; `MINI_APP_ENABLED` default is unchanged (off); no
> deployment, no Telegram change, no production call, no secret recorded.

- **Task ID:** `OHB2-PLAN04-HOSTING-QUALIFICATION-AND-MINIAPP-GATES-EXECUTION-02`
- **Date (UTC):** 2026-11-16
- **Baseline:** branch `main`, HEAD `56a58124f5cd677ca39e1dad19b5e3fa94b0fbc1`
- **Verdict (HOST-02):** **`BLOCKED`** — required gates remain unresolved and **no owner activation
  approval is recorded** (and none is implied by this task).

---

## Phase A — Safety default and configuration (verified, no change)

| Check | Result | Evidence |
|---|---|---|
| Default value of `MINI_APP_ENABLED` | **False (off)** | `bot/config.py:262` `_parse_bool(env, "MINI_APP_ENABLED", False)`; runtime: `load_config(base).mini_app_enabled is False`. |
| Env override parsing | Strict | `_parse_bool` accepts `1/true/yes/on/y` & `0/false/no/off/n`; **empty ⇒ default**; **unknown non-empty ⇒ `ConfigError`** (fail-closed). |
| Malformed/missing value behaviour | Fail-closed | `load_config({...,"MINI_APP_ENABLED":"garbage"})` → **`ConfigError`** (verified). |
| Enabled without URL | Fail-closed | `MINI_APP_ENABLED=1` with empty `MINI_APP_URL` → **`ConfigError`** at load (`bot/config.py:266`) and **`RuntimeError`** at build (`bot/app.py:343`). |
| Disabled-mode route/feature behaviour | No HTTP surface | `bot/app.py::_wire_mini_app` returns immediately when off; verified `build_application(default_cfg)` → `bot_data` has **no** `mini_app` / `mini_app_server`. |
| Alternate activation path | **None found** | Only reader of the flag is `config.py`; activation happens only via `_wire_mini_app`. No `MINI_APP_ENABLED` read in `start.sh`, `main.py`, or `bot/web/*`. |
| Startup logging & secret redaction | Present | `bot/bootstrap.py::setup_logging(level, secrets)`; `Config.__repr__` omits secrets; bootstrap prints names/flags only. |

**Conclusion:** no in-scope safety defect found. Per the task rule ("If a concrete in-scope safety
defect is found, implement only a narrowly scoped fail-safe correction"), **no code change is made** —
the disabled default and fail-closed parsing are already correct.

---

## Phase B — Activation prerequisites (gate checklist)

| # | Gate | Status | Evidence / remaining work | Owner approval? |
|---|---|---|---|---|
| 1 | HOST-01 has a qualified host | **FAIL** | HOST-01 verdict `BLOCKED` (see `OHB2-PLAN04-HOST01-HOSTING-QUALIFICATION.md`). | Yes |
| 2 | Stable HTTPS origin configured | **FAIL** | No production `MINI_APP_URL`; no host chosen. | Yes |
| 3 | Telegram Mini App configuration correct | **NOT_RUN** | `MINI_APP_URL` must be a clean public `https://` URL (no userinfo/fragment/query; non-loopback) — enforced by `bot/config.py`; not yet set. | Yes |
| 4 | Session authentication secure | **PASS (local)** | `initData` validation + session cookie + TTL + `MINI_APP_COOKIE_SECURE=1` default; covered by `tests/test_miniapp_*` (~370 HTTP tests). | No |
| 5 | Owner authorization checks enforced | **PASS (local)** | Single allowed owner id; `_authorize_conversation` server-side ownership before any write; negative cases (401/403/404/409) tested. | No |
| 6 | Intended features exist in the exact deployment SHA | **PASS (local)** | Feature matrix `docs/MINI_APP.md` §15 — 12 rows `IMPLEMENTED_AND_TESTED`; files navigation (WS-01) implemented. | No |
| 7 | MT-2 authenticated file download verified to the extent exposed by UI | **BLOCKED (provider)** | MT-2 attachment download is implemented locally (`docs/reviews/OHB2-MT2-IMPLEMENTATION-REPORT.md`) but its **provider-side** limitation stands; see §MT-2 below. | Yes |
| 8 | Real Android 12 Telegram WebView behaviour tested | **NOT_RUN** | No real Telegram client/device available (outside CI). Chromium ≠ Telegram. | Yes |
| 9 | Operational logging & safe error handling verified | **PASS (local)** | Secret redaction; bounded diagnostics; no silent start. | No |
| 10 | Restart & persistence behaviour verified | **FAIL** | Remote persistence is `NOT_RUN` (HOST-01 §5). | Yes |
| 11 | Rollback & disable procedures documented & testable | **PASS (documented)** | See Phase C (disable = set `MINI_APP_ENABLED=0` and restart; no data migration). | No |
| 12 | Explicit owner approval to activate recorded | **FAIL** | Not present, and **not** part of this task's authorization. | Yes |

---

## MT-2 status (preserved exactly)

- MT-2 (authenticated Mini App **attachment** download) is **implemented locally** and
  adversarially re-verified (`docs/reviews/OHB2-MT2-IMPLEMENTATION-REPORT.md`), but its
  **provider-side limitation is unresolved**: remote upload/delivery to OpenHands is **`BLOCKED` /
  P0** (see `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` and
  `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md`). This report does **not** claim MT-2
  complete.
- **WS-02** (individual **workspace** file download) is separately **`BLOCKED_BY_PROVIDER_CAPABILITY`**
  (`docs/MINI_APP.md` §13و) — no workspace-confined, scoped-auth binary read route exists. No local
  download route exists; download-like paths return **404**.
- **Plan 10 entry criteria for MT-2 remain unmet:** (1) resolve F-01 + strategy review, (2) real
  Android 12 device verification, (3) owner confirmation of **D-15**, (4) separate explicit owner
  authorization. Until all four hold, MT-2 is **not implementation-ready and not authorized**.

## Android 12 Telegram WebView status

**`NOT_RUN` / UNVERIFIED.** No real Telegram Android client or device is available in this environment
or in CI. The Chromium headless run recorded in earlier Plan 03/04 work exercises the same
`index.html`/`styles.css`/`app.js` in a Chromium engine, but **Chromium is not the Telegram WebView**;
WebView-only behaviour remains explicitly unverified. A reproducible manual protocol exists in
`docs/reviews/OHB2-PLAN10-MT2-PRE-IMPLEMENTATION-READINESS.md` §6.

---

## Phase C — Activation and rollback procedure (documented, NOT executed)

> **This procedure must not be run until every gate above passes AND the owner gives separate,
> explicit activation approval.** It is a plan, not an authorization.

1. **Verify source/deployment SHA** — record the exact `main` SHA deployed; confirm the runtime file
   set matches `docs/DEPLOY_KATABUMP.md` (no `.env`, no `*.sqlite3*`, no `tests/`, no `automation*/`).
2. **Verify host qualification** — confirm the chosen host passed the HOST-01 canary (persistence +
   locking + stable HTTPS).
3. **HTTPS + Telegram config checks** — set `MINI_APP_URL` to a clean public `https://` URL
   (non-loopback, no userinfo/fragment/query); confirm `MINI_APP_ALLOWED_ORIGINS` derives correctly;
   leave `MINI_APP_TRUSTED_PROXIES` empty unless a real reverse proxy exists.
4. **Feature-flag change** — set `MINI_APP_ENABLED=1` (and keep `MINI_APP_COOKIE_SECURE=1`).
5. **Pre-activation checks** — confirm single process/single DB owner; confirm Autopush disabled;
   confirm `MINI_APP_PORT` reachable only through the intended ingress.
6. **Runtime verification** — `/health` = 200; `/ready` = 200 (DB verified + workers up);
   exactly one poller.
7. **User-visible behaviour** — owner-only: open the Mini App from Telegram, load chats/files, run a
   read action.
8. **Safe logging checks** — confirm no secret appears in logs.
9. **Rollback triggers** — auth failures, duplicate pollers, DB lock errors, `/ready` 503, or any
   secret leak.
10. **Immediate disable** — set `MINI_APP_ENABLED=0` and restart; the bot keeps working (no HTTP
    surface). **No data migration is needed** (the DB is untouched by enable/disable).
11. **Post-rollback verification** — confirm polling still works and no HTTP surface is exposed.

---

## Phase D — HOST-02 verdict

**`BLOCKED`.** Gates 1, 2, 7, 8, 10, 12 fail or are unresolved. The Mini App **must remain disabled**
until all gates pass **and** the owner records explicit activation approval. No activation was
performed during this task.

---

## Governance compliance

- Mini App left **disabled**; `MINI_APP_ENABLED` default unchanged; no activation.
- Autopush unchanged (inactive); no new process/worker/scheduler/DB owner/backup feature.
- No deployment, no external provisioning, no production call, no secret exposed.
- No commit/push/PR/merge/release/deploy.
