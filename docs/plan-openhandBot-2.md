# OpenHandBot 2 — Implementation Plan

**Plan ID:** `plan-openhandBot-2`  
**Repository:** `TM-AEM/OpenHandBot`  
**Target branch:** `main` (verify the actual branch and HEAD before starting)  
**Product direction:** Keep the Telegram bot fully functional, expose its commands in Telegram's command menu beside the message field, and add a lightweight Telegram Mini App that provides the bot's complete feature set.  
**Primary constraint:** The Mini App must remain usable on weak mobile internet and low-end Android devices.

---

## 1. Product Goals

1. Preserve all current OpenHandBot Telegram workflows and their existing safety guarantees.
2. Make every supported Telegram slash command discoverable from the command menu next to the message composer. Users should not have to remember command names.
3. Add a Telegram Mini App that exposes the same capabilities as the bot, including features currently hidden behind the deferred-feature flag.
4. Keep the Mini App fast on slow connections, low-memory Android devices, and older Telegram WebViews.
5. Improve security and API-response validation before expanding the public-facing surface.
6. Keep one authoritative application state, one SQLite database, and one set of background workers. Do not create a second independent bot runtime.
7. Avoid unnecessary dependencies, duplicate business logic, dead code, and speculative rewrites.

## 2. Current Baseline Observed on GitHub

The current `main` source has the following relevant characteristics. Re-check the exact HEAD and working tree before implementation; do not assume these observations are still unchanged.

- `main.py` starts the Telegram bot with long polling using `run_polling(drop_pending_updates=True)`.
- `bot/app.py` registers these seven slash commands:
  - `/start`
  - `/cancel`
  - `/notifications`
  - `/outbox`
  - `/outbox_status`
  - `/outbox_discard`
  - `/outbox_mark_sent`
- The current source does not register a documented Bot API command list through `set_my_commands`; adding handlers alone does not guarantee that Telegram shows the commands in its menu.
- The bot is owner-only and private-chat-only. Preserve that restriction in both Telegram handlers and every Mini App API route.
- The bot already uses a single SQLite database, an OpenHands API client, an outbox worker, a creation worker, a conversation watcher, and a global notifier.
- `bot/features.py` currently hides `files`, `export`, `cost`, and `followups`. Their code and data still exist. The Mini App must restore them deliberately, not by blindly switching off the global feature flag before each feature is tested.
- `bot/handlers.py` already contains implementations for conversation browsing, status, prompts/replies, repositories, file browsing, export, cost, followups, and outbox operations.
- `bot/notifier.py` currently loads all notification states to determine whether the first run is occurring. This is an optimization candidate, not an emergency correctness bug.
- `bot/config.py` accepts both `http://` and `https://` for `OPENHANDS_BASE_URL`, while `bot/openhands_client.py` sends the OpenHands API key as a Bearer token. Plain HTTP to a non-local host must be prevented.
- `bot/openhands_client.py` has useful response checks in some methods (for example, `get_conversations`), but other API response shapes still need explicit validation and regression tests.
- The current deployment guide describes a long-polling service and does not establish that the existing host exposes a public HTTPS port for a Mini App backend. This is a deployment gate, not an assumption.

## 3. Important Telegram UI Decision

Telegram's menu button beside the message field has two alternative behaviours:

- show the bot's command list; or
- open a Mini App.

It cannot perform both behaviours from that same button simultaneously. This plan therefore preserves the command-list behaviour and launches the Mini App using a dedicated `web_app` inline button in `/start` and through a new `/app` command. This gives the user both features without replacing the command menu.

Use an inline Mini App button, not a simple reply-keyboard Web App button, for the full personalized app flow. Telegram documents that inline-button Mini Apps receive basic user information and a session query ID. The server must still validate the raw `Telegram.WebApp.initData`; never trust `initDataUnsafe`.

Do not configure the bot menu button as `MenuButtonWebApp` as part of this plan, because that would replace the command-list shortcut the user explicitly requested.

## 4. Architecture and Non-Negotiable Constraints

### 4.1 One backend and one state owner

- Keep the existing Telegram bot, `OpenHandsClient`, `Database`, `OutboxWorker`, `CreationWorker`, `Watcher`, and `Notifier` as the single owners of their respective resources.
- Add an HTTP API for the Mini App that calls the same underlying application services and database. It must not create a second independent set of workers or a second SQLite connection owner that competes with the bot.
- Prefer running the Telegram polling lifecycle and the HTTP server in one coordinated asyncio process. If the current hosting platform cannot support that safely, stop and document the hosting limitation before choosing a different deployment topology.
- Do not move secrets, the OpenHands API key, or the Telegram bot token into browser JavaScript, HTML, local storage, or downloadable configuration.
- Do not call OpenHands directly from the Mini App. All requests must pass through the authenticated backend.

### 4.2 Lightweight frontend

- Default to plain TypeScript/JavaScript, semantic HTML, and small CSS. Do not introduce React, Next.js, a component framework, a charting framework, or a large UI kit without measured evidence that it is needed.
- Use the existing Arabic-first product language and proper RTL layout. Keep room for a future English locale without duplicating every component.
- Use Telegram theme values and safe-area information where supported, with a usable fallback when those APIs are unavailable.
- Use system fonts and small inline SVG icons. Avoid remote font downloads, large images, autoplay media, decorative animation, and heavy dependencies.
- The first meaningful interface must render before the app waits for OpenHands data. Show cached or loading state clearly and never leave the user with an indefinite blank screen.

### 4.3 Preserve existing behaviour

- Keep existing Telegram inline keyboards and command workflows working while the Mini App is introduced.
- Extract shared business logic only where needed to avoid maintaining two implementations of the same operation. Do not conduct a broad architectural rewrite.
- Keep durable prompt/creation handling in the existing outbox system. A frontend retry must not cause duplicate prompts or duplicate conversation creation.
- Preserve the documented notification distinction: global proactive notifications are controlled by the notification preference; explicitly watched conversations retain their own notification behaviour.
- Preserve the existing owner-only, private-chat-only policy. Do not silently turn this into a multi-user service.

---

## 5. Work Breakdown

## Phase 0 — Baseline, Feasibility, and Scope Lock

**Goal:** Establish the true implementation baseline and prove the hosting path before changing the application.

Tasks:

- Record repository URL, default branch, current HEAD SHA, commit status, working-tree state, and the exact files changed by any existing work.
- Read `README.md`, `main.py`, all `bot/` modules, all tests, requirements, CI workflows, and deployment/runbook documentation.
- Build a feature inventory from registered handlers, keyboard callbacks, feature flags, service methods, database operations, and tests. Do not infer functionality from README text alone.
- Record every currently hidden feature and its required data/API operations.
- Verify whether the current hosting platform provides a stable public HTTPS URL and an inbound application port that can serve the Mini App API and static assets.
- Preserve the project's free/no-bank-card hosting constraint unless the owner explicitly changes it. Verify actual limits and free-tier eligibility rather than relying on marketing labels.
- Measure the actual memory/storage limits and startup/shutdown behaviour of the current deployment. Confirm that the added HTTP server can coexist with the polling bot within those limits.
- If the host cannot provide public HTTPS ingress within the accepted budget, compare viable no-card hosting or tunnel options and document the selected approach before implementing the web backend. Do not silently require a paid upgrade, payment card, or unsupported host.

Deliverables:

- `docs/PLAN2_BASELINE.md` with exact HEAD SHA, source inventory, feature matrix, test baseline, hosting findings, and unresolved risks.
- A decision record for the backend hosting topology.

Acceptance criteria:

- No production code changed in this phase.
- All existing tests and CI baseline results are recorded accurately.
- The project has a proven route to a public HTTPS Mini App URL, or a documented blocker and alternative.

## Phase 1 — Security and OpenHands API Reliability

**Goal:** Resolve high-impact risks before exposing more operations through an HTTP API.

### 1.1 Enforce safe OpenHands transport

- Reject `http://` `OPENHANDS_BASE_URL` values for non-loopback hosts.
- Prefer HTTPS-only configuration. Permit plain HTTP only for explicitly recognized loopback development addresses if there is a documented local-development need.
- Add tests proving that an external HTTP URL is rejected and a valid HTTPS URL is accepted.
- Ensure logs and exception messages never include Authorization headers, bot tokens, API keys, or full secret-bearing URLs.

### 1.2 Validate OpenHands response schemas

- Audit every public `OpenHandsClient` method and document its expected success payload, nullable fields, error payload, and maximum response size where relevant.
- Validate container types before calling `.get`, iterating, sorting, or indexing.
- Validate list members as dictionaries where appropriate; explicitly preserve documented nullable array elements where the API permits them.
- Reject malformed or unexpected payloads with a safe `ApiError`; do not convert malformed API responses into misleading empty results.
- Keep endpoint-specific compatibility handling documented in `docs/API_NOTES.md`.
- Add MockTransport tests for malformed JSON, wrong top-level types, wrong `items` type, non-object list entries, missing required IDs, nullable fields, and normal API responses.
- Do not alter known API semantics based on assumptions. In particular, `get_conversations` may receive an array containing `null` entries; retain the verified handling.

### 1.3 Improve notifier startup detection

- Replace loading all notification-state rows just to test whether the table is empty with a small database-level `EXISTS`/count query.
- Add a focused database and notifier regression test.
- Preserve first-run baseline semantics exactly: the first poll records a baseline and does not send notifications for old terminal states.

### 1.4 Review pending Telegram updates

- Explicitly decide whether `drop_pending_updates=True` is intentional for this product.
- Document the operational consequence: pending updates may be discarded on restart.
- Change the policy only with tests for stale update handling and duplicate-command safety. Do not change it merely as cleanup.

Acceptance criteria:

- All security and API-contract tests pass.
- Existing first-run notification behaviour is unchanged.
- No API key can be sent over external plaintext HTTP.

## Phase 2 — Make Telegram Commands Discoverable Beside the Composer

**Goal:** Make supported commands visible from Telegram's built-in menu and slash suggestions.

### 2.1 Register the existing commands

Register the actual supported command list through `Application.bot.set_my_commands(...)` during startup (`post_init`) using the existing `python-telegram-bot` dependency.

Initial command inventory from the current handler registration:

| Command | Purpose | Notes |
|---|---|---|
| `/start` | Open the main bot menu | Add the Mini App launch button here. |
| `/cancel` | Cancel the current routing/input state | Keep existing semantics. |
| `/notifications` | View/manage proactive notifications | Must not disable explicitly watched conversation delivery. |
| `/outbox` | List unresolved outgoing prompt/creation records | Keep sensitive prompt text out of output. |
| `/outbox_status` | Inspect one outbox/creation record | Preserve argument validation. |
| `/outbox_discard` | Mark a record discarded | Keep the explicit `confirm` requirement and explain the action is final. |
| `/outbox_mark_sent` | Owner confirms an ambiguous operation succeeded | Keep the explicit `confirm` requirement and explain this is owner confirmation, not API proof. |
| `/help` | Explain the bot and list available commands | New handler; descriptions must be accurate. |
| `/app` | Return the Mini App launch button | New handler; must not replace the command menu. |

- Verify the command registry against the actual `CommandHandler` registration at startup or through a test so that commands cannot silently drift out of sync.
- Use an owner-specific command scope (`BotCommandScopeChat` for the allowed owner chat) and Arabic descriptions. If language-scoped registration is used, test both the Arabic scope and fallback behaviour.
- Explicitly keep the menu button in command-list mode for the owner (for example, `MenuButtonCommands` via `set_chat_menu_button`), so a previous BotFather/Web App menu-button setting cannot silently replace the command menu.
- Do not set the menu button to a Web App menu button.
- Keep command handlers guarded. Telegram command scopes are presentation only, not authorization.
- Do not expose internal or dangerous operations to any user other than the configured owner.
- Consider grouping or clearly labelling the outbox maintenance commands in `/help`; do not hide them from the owner if the requirement is that all available commands are discoverable.

### 2.2 Add the Mini App launcher

- Add an inline `web_app` button to the `/start` main menu.
- Add `/app`, which sends the same dedicated inline Mini App launch button.
- Use the configured public HTTPS Mini App URL; validate it at startup and fail clearly if the Mini App is enabled without a valid URL.
- Keep `/start` and all existing inline menu actions functional when the web service is disabled or temporarily unavailable. The bot should show a clear unavailable message rather than crash.

Acceptance criteria:

- The command button next to the message composer shows the registered command list in Telegram.
- Typing `/` suggests the supported commands with their descriptions.
- Selecting each command reaches its existing handler and preserves its behaviour.
- `/start` and `/app` expose a working Mini App inline button.
- The menu button still opens commands, not the Mini App.

## Phase 3 — Shared Application Services and Authenticated Mini App API

**Goal:** Expose bot capabilities through a secure API without duplicating business logic.

### 3.1 Define a small service boundary

- Identify operations currently embedded in Telegram handlers and move only the reusable business operations into small service functions/classes where necessary.
- Keep Telegram-specific concerns (Update objects, CallbackQuery editing, reply markup, Telegram send calls) in the Telegram adapter layer.
- Keep persistence and OpenHands access behind the existing database and client abstractions.
- Have Telegram handlers and Mini App routes call the same operation layer for prompt submission, conversation creation, notification preferences, followups, and outbox inspection/actions.
- Do not duplicate outbox state transitions in the HTTP routes.

### 3.2 Add a minimal HTTP server

- Select the smallest stable ASGI option compatible with the hosting environment (prefer a minimal Starlette application plus Uvicorn if an ASGI server is required; do not add FastAPI unless its functionality is justified).
- Serve versioned static Mini App assets and a small JSON API.
- Coordinate HTTP and Telegram lifecycle in one asyncio process where supported.
- Respect the deployment platform's assigned port/environment variable. Bind only as required by the host; keep the public URL HTTPS at the ingress layer.
- Expose a minimal health endpoint that returns no secrets, internal configuration, or private user data.
- Do not launch a second worker set or a second copy of the bot.

### 3.3 Authenticate every Mini App request

- The frontend sends the raw `Telegram.WebApp.initData` value to a dedicated backend authentication endpoint.
- Validate the Telegram HMAC signature on the server using the official Web Apps algorithm and the bot token.
- Reject missing, malformed, tampered, expired, or replayed initialization data according to a documented freshness/session policy.
- Parse the authenticated Telegram user ID only after signature validation; then enforce the existing `ALLOWED_TELEGRAM_ID` allowlist.
- Never trust `initDataUnsafe`, query parameters, browser-supplied user IDs, or frontend role flags.
- Issue a short-lived server-authenticated session for subsequent API calls. Keep the session in a secure same-site cookie or an equivalently protected mechanism supported by the Telegram WebView; document the chosen CSRF protections.
- Enforce HTTPS, same-origin policy, strict CORS (same origin only unless explicitly justified), request size limits, input validation, and bounded rate limits.
- Validate conversation IDs, repository names, file paths, file sizes, and command arguments server-side.
- Do not provide generic proxy endpoints that accept arbitrary URLs or arbitrary OpenHands paths.
- Return safe user-facing errors; keep detailed diagnostics in redacted logs only.

### 3.4 Define a small, versioned API contract

At minimum, design and document endpoints for:

- bootstrap/profile and current settings;
- paginated conversation list and conversation detail/status;
- latest exchange and prompt/reply submission;
- repository list/search and new conversation creation;
- global notification preference read/update;
- watched conversations list/add/remove;
- cost/usage details;
- workspace file listing and bounded file preview/download;
- conversation export;
- outbox list, record status, and the two explicit-confirmation owner actions.

Use response DTOs containing only the fields the Mini App needs. Do not expose raw OpenHands objects, secrets, internal database rows, or raw exception traces.

Acceptance criteria:

- Unauthenticated and non-owner requests receive a safe denial.
- Tampered and stale `initData` is rejected.
- API routes call the same service logic as the Telegram bot.
- No duplicate background worker or independent database owner is created.
- API contract tests cover every read and write operation.

## Phase 4 — Mini App UI and Full Feature Parity

**Goal:** Give the owner a coherent mobile-first interface containing all bot capabilities.

### 4.1 Main navigation

Use a small, persistent navigation structure with clear sections:

1. **Dashboard** — recent activity, active/finished/error counts where available, and quick actions.
2. **Conversations** — paginated/searchable list, status labels, repository/branch metadata, and last updated time.
3. **Conversation view** — status, last user/agent exchange, prompt composer, send/reply action, refresh, and copy/full-text actions.
4. **New conversation** — repository search/selection, initial prompt, creation progress, and retry-safe status.
5. **Followups** — list watched conversations, add/remove followup, and show current state.
6. **Notifications** — global proactive notification preference with an explicit explanation of what it affects and what it does not affect.
7. **Files** — workspace file listing, directory navigation where supported, bounded text preview, and safe download handling.
8. **Cost and usage** — cost, tokens, and model metadata when returned by OpenHands.
9. **Exports** — conversation export download with clear file-size and network warnings.
10. **Outbox** — pending/unknown prompt and creation operations, safe status details, and explicit-confirmation actions matching Telegram command semantics.

### 4.2 Feature restoration policy

- Restore `files`, `export`, `cost`, and `followups` through the Mini App only after their service paths and API tests pass.
- Do not switch `DEFERRED_FEATURES_HIDDEN` off globally until the Telegram UI, Mini App, and all tests are ready for those features.
- Make the feature matrix explicit: Telegram support, Mini App support, enabled/disabled state, and test coverage.
- Preserve existing stored followups, notification state, outbox records, and migrations. Do not reset or recreate user data.

### 4.3 Interaction safety

- Every mutation displays a clear pending/success/failure state.
- Disable duplicate submission while a request is in flight.
- Use an idempotency/request ID for prompt and conversation-creation submissions, backed by the existing outbox where possible.
- Dangerous operations (`discard`, `mark sent`) require an explicit second confirmation in the Mini App and must use the same backend transition rules as Telegram.
- Show whether a status is current, cached, or stale.
- Long agent responses and file contents must be truncated/lazy-loaded with a deliberate “load more” action.

Acceptance criteria:

- The feature matrix shows parity for every current and deferred bot feature.
- Existing Telegram interaction tests still pass.
- The Mini App cannot create duplicate prompts or conversations during retries, double taps, reloads, or connection drops.

## Phase 5 — Weak-Internet and Low-End Android Performance

**Goal:** Make the app practical over slow mobile data, not merely visually small.

### 5.1 Transfer-size budgets

Use measurable budgets and record actual build output in CI:

- Initial JavaScript plus CSS: target at or below **100 KiB compressed**.
- No hero images, video, remote fonts, or chart libraries in the initial route.
- Lazy-loaded route code should be split by feature and remain small; do not load Files, Export, Cost, and Outbox code until those sections are opened.
- The first bootstrap response should contain only the minimum shell data and a small first conversation page; do not send full event histories or file contents at startup.
- Compress HTTP responses with gzip or Brotli where the host supports it.
- Use immutable caching for fingerprinted static assets.

If a budget cannot be met, measure and document the reason before increasing it.

### 5.2 Network request strategy

- Use paginated lists and bounded payloads. Never download every conversation's event history or every workspace file on app startup.
- Reuse existing short-lived server caches where their correctness has been verified; add ETag/conditional requests where supported and useful.
- Prefer manual refresh and restrained background refresh. Pause refresh when the Mini App is hidden/inactive; do not poll every few seconds from the browser.
- Implement request timeouts, exponential backoff with jitter, and `Retry-After` handling for rate limits.
- Do not automatically retry non-idempotent writes unless the idempotency key proves the retry is safe.
- Keep the interface usable when one API request fails: render previously loaded sections and show a small retry action instead of replacing the entire page with an error.
- Do not make the user reload the entire app to recover from a temporary network failure.

### 5.3 Offline and cache policy

- Cache only the static application shell and fingerprinted public assets in the service worker.
- Optionally retain a small, explicitly bounded recent-conversation summary cache for read-only display. Clearly label it as stale/offline data.
- Do not cache API keys, bot tokens, authentication payloads, private file contents, export archives, or sensitive prompt bodies in the service worker cache.
- Do not silently queue a prompt while offline. Either use the existing durable server-side outbox after a confirmed server response, or tell the user that the prompt was not submitted.
- Clear owner-specific cached summaries when the user signs out or the authenticated session is invalidated.
- State clearly that first launch and live operations require an internet connection; cached shell access after a successful first load is a resilience feature, not a promise of full offline operation.

### 5.4 Device and interaction performance

- Design mobile-first for narrow Android screens and support older Telegram WebViews.
- Avoid large DOM trees; paginate or window long lists.
- Respect reduced-motion preferences and disable nonessential animation on low-performance devices.
- Use native browser controls where practical, simple skeletons, and text-first loading.
- Keep touch targets usable and all form fields labelled.
- Test the actual Telegram Android WebView, not only desktop Chrome.

Acceptance criteria:

- The initial route meets the transfer-size budget or has a documented, approved exception.
- The app remains navigable with slow responses, failed requests, and temporary loss of connectivity.
- No duplicate mutation is triggered by a timeout/retry scenario.
- No sensitive response is persisted in an uncontrolled browser cache.

## Phase 6 — Testing, CI, and Observability

**Goal:** Verify parity, security, reliability, and performance before enabling the Mini App for normal use.

### 6.1 Backend and regression tests

- Retain all existing Python test coverage and CI matrix.
- Add tests for command registration, owner-specific command scope, `/help`, `/app`, and the inline Mini App button.
- Add tests for Telegram `initData` signature validation, invalid hash, altered user ID, stale `auth_date`, replay/session expiry, and unauthorized owner IDs.
- Add API tests for every endpoint, malformed request bodies, oversized payloads, invalid IDs/paths, rate limits, and safe error responses.
- Add tests for all feature-flag combinations during rollout.
- Add tests to prove the HTTP server does not start a second watcher, notifier, database owner, outbox worker, or creation worker.
- Add tests for clean coordinated shutdown and startup failure handling.

### 6.2 Frontend tests

- Test navigation, loading, error, empty, stale-cache, offline, and retry states.
- Test prompt submission, new conversation creation, duplicate taps, and ambiguous network outcomes.
- Test RTL layout, Telegram light/dark themes, small screens, safe areas, and accessibility labels.
- Use browser end-to-end tests for critical user flows; keep browser tooling in development dependencies only.

### 6.3 Weak-network tests

- Run a repeatable throttled-network profile representative of weak mobile data (for example, slow 3G/2G bandwidth and added latency).
- Test cold first load, warm cached load, opening a conversation, submitting a prompt, returning from offline to online, and recovering from HTTP 429/5xx.
- Record initial asset transfer size, bootstrap payload size, API request count, time to first useful interface, and recovery behaviour.
- Test on a low-memory Android device or emulator (including Android 12-class hardware) and inside the Telegram WebView.

### 6.4 Monitoring and redaction

- Add request IDs and structured logs for Mini App API calls, without logging tokens, raw `initData`, prompt bodies, file contents, or secret-bearing headers.
- Track API latency, status classes, payload sizes, cache hit rate, and outbox acceptance/failure counts.
- Health checks must not disclose sensitive configuration or owner identifiers.

Acceptance criteria:

- Existing and new backend tests pass in CI.
- Frontend build and end-to-end smoke tests pass.
- Weak-network measurements are attached to the release report.
- Logs are verified for secret and private-content redaction.

## Phase 7 — Deployment, Rollout, and Documentation

**Goal:** Release safely without interrupting the existing bot.

- Add documented HTTPS Mini App URL and backend port settings as validated environment configuration.
- Keep existing required secrets and database path unchanged unless a migration is explicitly required.
- Update the deployment guide with the selected platform, HTTPS routing, port binding, startup command, health check, service-worker behaviour, and rollback procedure.
- Back up the SQLite database before any schema migration. Migrations must be additive, transactional, tested against old database fixtures, and safe to rerun.
- Deploy with the Mini App feature disabled initially; verify the existing Telegram bot still runs normally.
- Enable the Mini App only after HTTPS, authentication, command menu, and API health checks pass.
- Roll out features incrementally: core conversations first, then prompt/new-chat, notifications/followups, then Files/Export/Cost/Outbox.
- Keep the original Telegram UI available as a fallback throughout rollout.
- Document how to disable the Mini App without disabling the Telegram bot.

Acceptance criteria:

- The public Mini App loads only over HTTPS.
- The existing Telegram bot remains operational if the Mini App server is unavailable.
- Rollback does not delete or rewrite user data.
- The final deployment and recovery instructions have been tested.

## Phase 8 — Dead-Code and Complexity Cleanup

**Goal:** Reduce project weight only after feature parity is established.

- Trace references to each function, class, constant, handler, feature flag, migration, and test before proposing removal.
- Do not delete deferred-feature implementations merely because they are currently hidden.
- Remove only code proven unreachable and no longer required for migrations, compatibility, tests, recovery, or operations.
- Remove dependencies only after checking runtime and development usage.
- Avoid reorganizing unrelated modules or renaming stable public interfaces during the Mini App delivery.
- Provide a before/after report of dependency count, production bundle size, source footprint, and removed symbols with evidence.

Acceptance criteria:

- Every removal has reference-trace evidence and a test proving no supported behaviour was removed.
- The final test suite and static checks pass after cleanup.

---

## 6. Suggested Implementation Task IDs

| Task | Scope | Depends on |
|---|---|---|
| `OHB2-00` | Baseline, feature inventory, host feasibility | None |
| `OHB2-01` | HTTPS enforcement and OpenHands response validation | `OHB2-00` |
| `OHB2-02` | Notifier `EXISTS` optimization and pending-update policy | `OHB2-00` |
| `OHB2-03` | Telegram command registration, `/help`, `/app`, launcher button | `OHB2-00` |
| `OHB2-04` | Shared service boundary and HTTP server lifecycle | `OHB2-00`, `OHB2-01` |
| `OHB2-05` | Telegram Mini App authentication and API contract | `OHB2-04` |
| `OHB2-06` | Lightweight Mini App shell and conversation browsing | `OHB2-05` |
| `OHB2-07` | Prompt/reply and new conversation flows | `OHB2-06` |
| `OHB2-08` | Notifications and followups parity | `OHB2-06` |
| `OHB2-09` | Files, Export, Cost, and Outbox parity | `OHB2-06` |
| `OHB2-10` | Weak-network caching, retry, payload, and performance work | `OHB2-06` through `OHB2-09` |
| `OHB2-11` | CI, Telegram WebView, security, and weak-network verification | All implementation tasks |
| `OHB2-12` | Deployment, gradual enablement, and documentation | `OHB2-11` |
| `OHB2-13` | Evidence-based dead-code/dependency cleanup | `OHB2-12` |

Do not start all tasks in parallel. Complete the dependencies and acceptance gates in order.

## 7. Definition of Done

OpenHandBot 2 is complete only when all of the following are true:

- The seven existing commands are visible from Telegram's command menu for the authorized owner, with accurate Arabic descriptions.
- `/help` and `/app` work, and the Mini App launch button is available without replacing the command menu.
- Existing Telegram bot features and safety semantics remain intact.
- The Mini App exposes conversations, prompts/replies, new chat/repository selection, notifications, followups, files, export, cost/usage, and outbox operations.
- Hidden features are restored only after their tests pass; existing database records are preserved.
- Every Mini App request is authenticated using validated Telegram `initData` and the existing owner allowlist.
- The OpenHands API key and Telegram bot token never reach the frontend.
- No second copy of the bot workers or independent state owner exists.
- The Mini App is served over HTTPS from a proven hosting configuration.
- Weak-network budgets and throttled-network tests pass or have explicitly approved, measured exceptions.
- Existing and new tests, static checks, and CI pass.
- Deployment, rollback, backup, and recovery instructions are complete.
- Dead-code removal is evidence-based; no deferred feature, migration, recovery path, or operational tool is deleted by guesswork.

## 8. Agent Execution Rules

- Start every task with a read-only inspection of the current HEAD, working tree, relevant source, tests, and CI state.
- Treat the current repository as the source of truth; re-check all line numbers and previous findings before editing.
- Preserve unrelated user changes. Do not overwrite or discard existing work.
- Do not use destructive Git commands (`reset --hard`, `clean`, force push, or broad deletion commands).
- Do not modify `.openhands/`.
- Keep autopush disabled. Do not commit, push, create a PR, or deploy unless the owner explicitly authorizes that exact action.
- Do not claim tests passed unless they were actually executed and their output was inspected.
- Work in small task-sized changes. For each task, report files changed, behaviour changed, tests run, test results, risks, and remaining blockers.
- If hosting, Telegram launch behaviour, or a source API contract cannot be verified, stop at that decision gate and report the exact evidence instead of inventing a workaround.

## 9. Official Telegram References

- Telegram Bot Features — commands, scopes, command menu, and Mini App entry points: https://core.telegram.org/bots/features
- Telegram Mini Apps — launch modes, inline Mini App buttons, initialization, theme/safe-area support, and `initData` validation: https://core.telegram.org/bots/webapps
- Telegram Bot API — `setMyCommands` and command scopes: https://core.telegram.org/bots/api
- python-telegram-bot v22.8 — MenuButtonWebApp and menu-button API reference (for comparison only; this plan intentionally keeps the command menu): https://docs.python-telegram-bot.org/en/latest/telegram.menubuttonwebapp.html
