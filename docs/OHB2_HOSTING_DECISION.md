# OHB2-04 — Mini App Hosting Feasibility Gate (Decision Report)

**Status:** investigation + documentation only. No production code changed, nothing deployed,
no external service created, no commit/push performed by hand (the separate autopush daemon
was left running and untouched — see §10).

| Item | Value |
|---|---|
| Repository | `TM-AEM/OpenHandBot` (public) |
| Branch | `main` |
| HEAD at investigation | `3cd48e6361998f573bacb2162349b104ade3378f` (`origin/main` in sync) |
| Working tree | clean (no staged/unstaged/untracked changes from this task) |
| Gate | pyflakes clean · `pytest -q` **621 passed** · `git diff --check` clean |

---

## 1. Verified hosting capabilities

All findings below were measured in this runtime, not assumed. Probes started a throwaway
`http.server` on the candidate port and stopped it afterwards; no repository file was touched.

### 1.1 This runtime is a Kubernetes pod, not a bare VPS

- Hostname `runtime-kivosuogpgofjcub-7cd9fb4f59-7v9tp`; OS Debian 13 (trixie); kernel 6.8 (GKE).
- `KUBERNETES_SERVICE_HOST=10.3.0.1` and a mounted service-account are present → it is a managed
  pod inside an OpenHands runtime cluster.
- `RUNTIME_URL=https://kivosuogpgofjcub.prod-runtime.all-hands.dev`.

### 1.2 Public HTTPS ingress is REAL and reachable (verified)

Two ports are published as HTTPS hostnames (injected via repository `work_hosts` context and
present in the environment as `WORKER_1=12000`, `WORKER_2=12001`):

| Local port | Public HTTPS URL | Probe result |
|---|---|---|
| 12000 | `https://work-1-kivosuogpgofjcub.prod-runtime.all-hands.dev/` | `200` while a server listened on 12000; `502` when it did not |
| 12001 | `https://work-2-kivosuogpgofjcub.prod-runtime.all-hands.dev/` | `200` while a server listened on 12001; `502` when it did not |

Evidence (exact commands and results):

```
$ python3 -m http.server 12000 --bind 0.0.0.0 &   # throwaway probe
$ curl -sS -m8 -o /dev/null -w "%{http_code}" http://127.0.0.1:12000/           -> 200
$ curl -sS -m15 -o /dev/null -w "%{http_code}" https://work-1-.../             -> 200 (t=0.02s)
$ curl -sS -m15 -o /dev/null -w "%{http_code}" https://work-2-.../             -> 502
# same test with a server on 12001:
$ curl ... https://work-2-.../                                                  -> 200
$ curl ... https://work-1-.../                                                  -> 502
```

This proves the ingress → local-port mapping is **live and 1:1** (work-1 ⇄ 12000, work-2 ⇄ 12001).

### 1.3 The ingress is a TLS-terminating reverse proxy (Traefik)

Request headers captured at the origin behind the proxy:

```
Host: work-1-kivosuogpgofjcub.prod-runtime.all-hands.dev
X-Forwarded-For: 10.1.1.26
X-Forwarded-Host: work-1-kivosuogpgofjcub.prod-runtime.all-hands.dev
X-Forwarded-Port: 443
X-Forwarded-Proto: https
X-Forwarded-Server: traefik-5f77c6945b-ngwqm
X-Real-Ip: 10.1.1.26
```

- Path forwarding is exact: `/api/v1/health.json?q=1` arrived verbatim.
- Method forwarding works: `POST` reached the origin (origin answered `501`, i.e. the method was
  delivered, not stripped by the proxy).
- TLS certificate: issuer `Let's Encrypt`, subject `CN=*.prod-runtime.all-hands.dev`,
  valid `Sep 21 2026 → Dec 20 2026` → **a trusted public CA**, which Telegram WebView requires.

### 1.4 Static assets and a persistent web server are both supported

- A plain HTTP server bound to `0.0.0.0:12000` was served publicly over HTTPS → the host can
  serve **static Mini App assets** and a **persistent web server** behind the proxy.
- HTTPS is terminated at the ingress; the app process only speaks HTTP locally, which matches the
  plan's guidance ("keep the public URL HTTPS at the ingress layer").

### 1.5 The existing bot does not own the public port

- `ss -tlnp` showed **no listening sockets** at investigation time; the Telegram bot is **not
  running in this sandbox** (only the tmux agent session and the autopush daemon are).
- The bot uses long polling (`main.py` → `run_polling(drop_pending_updates=True)`), so it needs
  **no inbound port**. Ports 12000/12001 are free for the Mini App HTTP server.
- Therefore running the bot's polling loop and a small ASGI server in **one asyncio process**
  (§4.1 of the plan) is possible without port conflict.

### 1.6 No web framework is installed yet

`requirements.txt` = `python-telegram-bot[all]==22.8`, `httpx==0.28.1`, `python-dotenv==1.2.4`.
`uvicorn`, `starlette`, `fastapi`, `aiohttp`, `flask`, `sanic`, `hypercorn` are all **MISSING**
in `.venv`. The Mini App backend will need one small ASGI dependency added (plan prefers minimal
Starlette + Uvicorn).

---

## 2. Resource limits and free-tier restrictions

### 2.1 This runtime (measured)

| Resource | Value | Notes |
|---|---|---|
| CPU | 4 vCPU (AMD EPYC 9B14) | `cpu.max = max 100000` → **no CPU quota cap** |
| RAM | 15 GiB total, ~13 GiB available | `memory.max = max` → **no cgroup memory cap** |
| Storage | 72 GB overlay, 56 GB free | shared root overlay |
| PIDs | `pids.max = 629145` | effectively unbounded for our use |
| Swap | 0 | no swap headroom |

→ The runtime is **generously provisioned**; the Mini App backend is tiny next to these limits.

### 2.2 The documented production host is much smaller — and not this runtime

`docs/DEPLOY_KATABUMP.md` targets **Katabump free**: 308 MB RAM, 716 MB storage, 25% CPU, and
**the free server renews every 4 days** (if forgotten, the bot stops). That host documents
**long polling only, no inbound port**. The Katabump plan is a *deployment guide*, not proof that
the Mini App backend is currently served anywhere.

### 2.3 Free-tier / no-card status of the options in scope

| Host | Card required? | Public HTTPS | Inbound port | Persistent? |
|---|---|---|---|---|
| This OpenHands runtime (work host) | No (already provisioned) | **Yes (verified)** | Yes (12000/12001) | **Ephemeral** — dies when the sandbox is re-provisioned |
| Katabump free (documented) | No | No ingress documented | No (polling only) | Free server expires every 4 days |
| GitHub Pages (static only) | No | Yes | n/a (static) | Yes |
| Free backend PaaS (Render/Fly/Koyeb free tiers) | **Usually yes** for a web service | Yes | Yes | Varies; sleep/scale-to-zero on free |

No paid service and no bank card is used or required by the recommended option (§4).

---

## 3. Architecture comparison

Legend: ✅ good · ⚠️ acceptable with caveats · ❌ blocking concern.

### A. Existing host serves both the bot and the Mini App

One asyncio process runs the Telegram polling loop **and** a minimal ASGI app (static + JSON API)
bound to the runtime's published port; the ingress exposes it over HTTPS.

| Dimension | Assessment |
|---|---|
| Cost | ✅ Free (runtime already provisioned, no card) |
| Public HTTPS | ✅ Verified (Let's Encrypt via Traefik) |
| Single state owner | ✅ Same process → one `Database`, one worker set |
| Business-logic reuse | ✅ API routes call the same services/handlers |
| Security | ✅ Same process can enforce owner allowlist; secrets never leave the server |
| Deployment complexity | ✅ Lowest — no second host, no cross-host auth |
| Weak-network behaviour | ✅ Same-origin; no third-party hop; static assets cached by the client |
| Reliability | ⚠️ **Tied to the ephemeral runtime**; URL changes on re-provision; a public URL exposes the sandbox's port |

### B. Existing host runs the bot and API; a free static host serves the frontend

Frontend on GitHub Pages (free, no card); backend stays on the runtime.

| Dimension | Assessment |
|---|---|
| Cost | ✅ Free (Pages + runtime) |
| Public HTTPS | ✅ Pages for static; runtime for API |
| Single state owner | ✅ Backend unchanged (one owner) |
| Deployment complexity | ⚠️ Two deploy targets; **cross-origin** API → needs CORS + cookie `SameSite=None; Secure` |
| Security | ⚠️ Cross-site cookies are fragile in Telegram WebView; broader CORS surface; more moving parts |
| Weak-network behaviour | ❌ **Worst** — two origins/hosts means two TLS handshakes and two failure domains on a flaky link |
| Reliability | ⚠️ Backend still tied to the ephemeral runtime |

### C. A separate free backend host runs the Mini App API

Backend on a free PaaS; frontend wherever.

| Dimension | Assessment |
|---|---|
| Cost | ⚠️ Free tiers often **require a card** or auto-sleep |
| Single state owner | ❌ **Two SQLite owners** (bot on one host, API on another) — directly violates plan §4.1 |
| Business-logic reuse | ❌ Requires extracting/duplicating services; outbox/watcher coordination across hosts |
| Deployment complexity | ❌ Highest — new host, new secrets, cross-host DB, cold starts |
| Weak-network behaviour | ❌ Extra hop; cold-start latency on free tiers |
| Reliability | ❌ Duplicate workers risk; conflicts with "no second worker set" |

### Verdict

**A is the only option that satisfies the non-negotiable constraints** (one process, one state
owner, one origin, no card, verified HTTPS). B adds a second origin for no benefit; C violates the
single-owner rule outright.

---

## 4. Recommended architecture

**Option A — one coordinated asyncio process on the existing runtime, served through the
existing HTTPS ingress.**

```
Telegram client ──HTTPS──▶ ingress (Traefik, LE cert) ──HTTP──▶ pod:12000
                                                                 │
                                     ┌───────────────────────────┴──────────────────────────┐
                                     │  single asyncio process                               │
                                     │  • python-telegram-bot long polling (existing)        │
                                     │  • minimal ASGI app (Starlette + Uvicorn):            │
                                     │      GET  /mini/…            static assets (versioned)│
                                     │      POST /api/v1/auth       validate initData HMAC   │
                                     │      GET/POST /api/v1/…      JSON API → same services  │
                                     │      GET  /api/v1/health     no secrets               │
                                     │  • one Database, one OutboxWorker/CreationWorker,     │
                                     │    one Watcher/Notifier                               │
                                     └───────────────────────────────────────────────────────┘
```

Concrete shape for OHB2-05 (not implemented here):

- Add **Starlette + Uvicorn** (smallest stable ASGI pair; plan §3.2). Do **not** add FastAPI.
- Bind the ASGI app to the host-assigned port (the published work-host port, e.g. 12000) on
  `0.0.0.0`; keep the public URL HTTPS at the ingress.
- Start both the Telegram polling lifecycle and the ASGI server from the same process/event loop
  (Uvicorn `Server.serve()` as a task alongside `Application.run_polling`), so there is exactly one
  `Database`, one outbox worker set, one watcher/notifier.
- `MINI_APP_URL` (already added in OHB2-03) is set to the work-host HTTPS URL, e.g.
  `https://work-1-kivosuogpgofjcub.prod-runtime.all-hands.dev/mini/`.
- Serve the frontend **same-origin** under `/mini/` (Option A) rather than GitHub Pages (Option B).

---

## 5. Security implications

Mapped to the task's security requirements and plan §3.3:

| Requirement | How Option A satisfies it |
|---|---|
| Validate `initData` server-side | `POST /api/v1/auth` recomputes the HMAC-SHA256 signature with the bot token per the official Web Apps algorithm; only `Telegram.WebApp.initData` is accepted, never `initDataUnsafe`. |
| Never trust frontend-supplied user IDs | The user id is parsed **only after** signature validation; role/owner flags from the browser are ignored. |
| Enforce single-owner policy | After signature validation, the id must equal `ALLOWED_TELEGRAM_ID`; otherwise a safe denial. Same allowlist as the bot. |
| Don't expose secrets to the browser | The bot token and `OPENHANDS_API_KEY` stay in the server process; the browser receives only short-lived session material and DTOs. No OpenHands/Telegram credentials are ever sent to the client. |
| HTTPS mandatory | Ingress is HTTPS-only with a Let's Encrypt cert (verified). `MINI_APP_URL` already requires `https://` and a non-loopback host. |
| No duplicate workers / single DB owner | One process ⇒ one `Database` instance and one worker set; API routes call existing services (no second outbox/watcher). |
| Reuse existing DB + logic | API routes call the same service layer as the Telegram handlers (plan §3.1). |
| Sessions / CSRF | Same-origin deployment allows a `Secure; HttpOnly; SameSite=Lax` cookie (no cross-site cookie needed, unlike Option B). Issue a short-lived signed session after `initData` validation; document a freshness/session TTL and reject replayed/stale `initData`. |
| Input validation / no open proxy | Validate conversation ids, repo names, paths, sizes, command args server-side; no generic URL/path proxy endpoints; bounded rate limits and request-size caps. |
| Error hygiene | Return safe user-facing errors; keep diagnostics in redacted logs only. |

Additional exposure note: publishing port 12000/12001 makes the sandbox reachable from the public
internet. All routes must therefore be authenticated; the health endpoint must return no secrets,
config, or private data. Cross-origin access should be restricted to the same origin (no wildcard
CORS).

---

## 6. Weak-network performance implications

- **Single origin (Option A)** minimises handshakes: one TLS connection to one host for both the
  static shell and the API. Option B would double this (two hosts) and is the worst for flaky links.
- **Static assets**: versioned filenames + long cache headers; keep the bundle tiny (plain
  HTML/CSS/JS, no heavy framework) so first paint survives a weak link.
- **No polling**: plan §4.3/§7 asks for manual refresh and restrained background refresh; pause
  refresh when the Mini App is hidden. Avoid per-second polling from the browser.
- **Ingress latency** measured at ~0.02 s for a small response — the hop is not a bottleneck.
- **Telegram WebView on Android 12 / low-end devices**: same-origin and a small payload reduce
  memory pressure; keep the app usable if a fetch fails (optimistic UI + retry), since the
  connection is expected to drop.

---

## 7. Deployment requirements

1. **Dependency**: add `starlette` and `uvicorn` (smallest stable ASGI pair) to `requirements.txt`.
2. **Single-process wiring**: start the ASGI server as an asyncio task inside the same process as
   `run_polling`; bind to the host-assigned port on `0.0.0.0`; never start a second bot/worker.
3. **URL**: set `MINI_APP_URL` to the work-host HTTPS URL of the Mini App (`…/mini/`).
4. **Auth**: implement the `initData` HMAC validation endpoint and the short-lived session cookie.
5. **Static**: serve versioned assets under `/mini/` from the same app.
6. **Host**: the runtime already provides the pod, TLS cert, and ingress — **no signup, no card,
   no manual account verification**.
7. **Persistence caveat**: the runtime is ephemeral (see §8/§9); treat the work-host URL as
   per-session unless the owner pins a stable URL.

---

## 8. Remaining unknowns

1. **Runtime lifetime / URL stability** — the sandbox is re-provisioned periodically and the work
   host is session-scoped; whether the URL survives long-term was **not** proven. A stable,
   long-lived public URL is the one property not verified.
2. **Production host for the bot** — the repo documents Katabump free (polling only, 4-day
   renewal); it is unknown whether the owner intends the Mini App to run on the same host as the
   deployed bot or only in the OpenHands runtime.
3. **Ingress restrictions** — request-size limits, timeouts, and any ingress-level rate limiting
   were not measured; these affect large file preview/download endpoints.
4. **Port assignment** — only ports 12000/12001 were exercised; whether other ports are published
   is unknown.
5. **Whether the runtime already runs the bot** — the bot was not running in this sandbox; the
   actual production bot's host/port availability was not inspected.

---

## 9. Explicit GO / NO-GO decision

### Recommendation: **GO** — with one explicit caveat about URL stability.

**Evidence supporting GO:**

- Public HTTPS ingress to the runtime **is proven**: `work-1 → :12000` and `work-2 → :12001`,
  both returning `200` when a local server listened and `502` otherwise.
- TLS uses a **Let's Encrypt** cert for `*.prod-runtime.all-hands.dev` (valid to 2026-12-20) —
  a public CA, which Telegram Mini Apps require.
- The ingress forwards **paths, methods, and headers** (Traefik; `X-Forwarded-Proto: https`).
- Ports 12000/12001 are **free** (bot is long-polling, no inbound port), so a single asyncio
  process can host both the bot and the Mini App backend without conflict.
- The host has ample resources (4 vCPU uncapped, ~13 GiB RAM free, 56 GB disk, high PID cap).
- Option A needs **no signup, no card, no manual verification**, and satisfies the single-owner /
  single-DB constraint that Options B and C break.

**Caveat that must be carried into OHB2-05:**

- The runtime is **ephemeral**: the work-host URL is session-scoped and may change when the sandbox
  is re-provisioned. If a *stable* public URL is required for a persistent Mini App, that specific
  property is **not yet proven** and would need either a pinned runtime/URL or a free static
  frontend host (Option B) for the shell. This does not block implementation in the runtime; it
  blocks promising a permanent URL.

### Completion gate

- **Do not begin OHB2-05** or implement the Mini App in this task. (Honoured — this document is the
  only artifact produced.)

### Quality gate (exact results)

```
$ .venv/bin/python -m pyflakes bot/ main.py tests/
pyflakes: clean (exit 0)

$ .venv/bin/python -m pytest -q
621 passed in 11.71s

$ git diff --check
diffcheck: clean
```

---

## 10. Preservation compliance (explicit)

- **Autopush daemon**: left running and untouched (PID 2830, `main.py --daemon`); no restart,
  reconfiguration, or replacement.
- **Published commits**: none reverted or rewritten; `origin/main` still `3cd48e6`.
- **`.openhands/`**: not modified.
- **Secrets / production env**: not changed.
- **Deployment**: nothing deployed; no external service created; no paid/card service introduced.
- **Manual commit/push**: none. (`git status` shows a clean tree; the report file is created but
  not committed by hand — the separate autopush daemon owns any push, per its 300 s cadence.)
- **Unrelated working-tree changes**: none existed at start; none introduced.

---

**OHB2_04_STATUS=GO**

Supporting evidence (one line): `curl https://work-1-kivosuogpgofjcub.prod-runtime.all-hands.dev/`
returned `200` with a local server on port 12000 and `502` without it, and the served certificate
is `Let's Encrypt` for `*.prod-runtime.all-hands.dev` — proving a free, no-card, public HTTPS
ingress to a port this single-process backend can bind.
