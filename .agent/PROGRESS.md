# PROGRESS — OHB2 overall-audit remediation (WP1–WP6)

## Goal
Remediate the six findings from the OHB2 overall audit, on top of origin/main @ c1aef66
(tree 2a97b15f…). Do not break working behaviour; smallest safe change; verified truth.

## Acceptance criteria
1. WP1 — a Mini App prompt whose POST returns after a local delete cannot resurrect the
   deleted conversation (no tombstone clear, no outbox row, honest 409).
2. WP2 — autopush never forwards `GIT_SSL_NO_VERIFY` to child git (TLS verification kept).
3. WP3 — the rate limiter enforces each window independently (minute vs hour).
4. WP4 — tombstone filtering fails closed on a DB read error (no unfiltered list).
5. WP5 — the bot and Mini App list paths follow `next_page_id` with a bound and report
   truncation, so conversations past the first page stay reachable.
6. WP6 — docs stop claiming "no data loss if the SQLite file is deleted" and stop claiming
   the bot keeps running when the startup integrity check fails.
7. Full `python -m pytest -q` and `node --test tests/frontend/*.test.js` pass; pyflakes clean.

Out of scope: unrelated refactors, dependency/version changes, main-branch pushes.

## Plan (all done)
- WP1 `bot/db.py::add_or_group_outbox` — reject `client_ref` enqueues on a tombstoned
  conversation; Mini App `send_prompt` uses `reengage=False` and raises 409 on rejection.
- WP2 `automation/autopush/main.py` — drop `GIT_SSL_NO_VERIFY` from the allowlist and strip
  denied keys in `_child_env()`.
- WP3 `bot/web/ratelimit.py` — per-window independent counting.
- WP4 `bot/handlers.py` + `bot/web/services.py` `_without_deleted` — return `[]` on error.
- WP5 `bot/openhands_client.py::collect_conversations` + list paths — follow `next_page_id`
  (max 20 pages) and surface `truncated`.
- WP6 `docs/DEPLOY_KATABUMP.md`, `docs/OPERATIONS_RUNBOOK.md` — correct the false claims.

## Baseline vs now
- Python: 1538 passed (baseline) → 1570 passed, 0 failed.
- Frontend: 143 passed → 143 passed.
- pyflakes `bot/ main.py tests/`: clean → clean.

## Assumptions / decisions
- Working on branch `agent/ohb2-audit-remediation` (AGENTS.md §6: push only agent/*).
- Mini App prompt path is treated as NOT an explicit re-engagement (re-watch goes through
  `watch`), so any prompt for a tombstoned conversation is refused.
- Bounded pagination cap = 20 pages (no unbounded loop if the server repeats `next_page_id`).

## Known issues
- None open. WP6 RUNBOOK §4 manual copy/restore text is accurate and left as-is.

## Branch and commits
- Branch: `agent/ohb2-audit-remediation`
- Commit: `b1dd979` — fix: remediate OHB2 audit findings (WP1-WP6)
- Pushed to origin; CI runs only on push/PR to main, so CI was verified locally with the
  exact workflow commands (pytest, node --test, pyflakes) — all green.

## Working commands
- Install: `pip install -r requirements-dev.txt`
- Test: `python -m pytest -q` ; `node --test tests/frontend/*.test.js`
- Lint: `python -m pyflakes bot/ main.py tests/`

## Phase 5 — Operational readiness audit (OHB2-PHASE5-OPERATIONAL-READINESS-AUDIT-AND-VERIFICATION)

Acceptance criteria: audit operational readiness (config, persistence, runtime, security,
hosting compatibility); resolve the open Phase-4 review notes; keep the full suite green;
make the smallest safe change only.

### Resolved from Phase 4 review
- P2-01 + P3-01: `bot/openhands_client.py::collect_conversations` now sorts merged pages by
  `updated_at` (desc) and de-duplicates by conversation id; fixed the misleading handler
  comment; added tests (unsorted pages + duplicate ids).
- P2-02: corrected the re-engagement description in `docs/MINI_APP.md`.
- P3-02: added fail-closed **then recovery** tests for both the bot list
  (`tests/test_handlers.py`) and the Mini App list (`tests/test_conversation_deletion.py`).

### Audit findings (Phase 2)
- P3-03: `MINI_APP_TRUSTED_PROXIES` was validated by `bot/config.py` and honoured by
  `bot/web/clientip.py` but was **missing** from `.env.example` and the `docs/MINI_APP.md`
  env block. Documented in both (behaviour unchanged; default stays fail-closed).

### Readiness notes
- Persistence: single SQLite file at `DB_PATH` with WAL + `busy_timeout=5000`; integrity is
  checked before polling (`Database.run_startup_maintenance`). No durable volume is documented
  for the free tier ⇒ **data-loss risk (H1 UNVERIFIED)** — see `docs/ZERO_TOUCH_STARTUP.md` §5b.
- Runtime: one process (bot polling + optional in-process Mini App ASGI); no `exec`, no second
  worker, no backup/SFTP/paramiko in runtime.
- Security: server-side initData verification, opaque in-memory sessions, Origin checks,
  body-size caps, per-IP/per-session rate limits, durable delete tombstone.
- CI: workflow `CI` runs `pyflakes` + `pytest` (3.11 & 3.13) and Node frontend tests; it runs
  only on push/PR to `main`, so on this branch it is verified locally with the exact commands.

### Phase 5 verification
- `python -m pyflakes bot/ main.py tests/` → clean (exit 0).
- `python -m pytest -q` → 1576 passed (in a venv; see note below).
- `node --test tests/frontend/*.test.js` → 143 passed.
- Focused: 431 passed (client, handlers, deletion, resurrection, config, bootstrap, ratelimit, authz, db).
- Note: `tests/test_deploy_manifest.py::test_documented_manifest_is_import_sufficient` fails
  when run against the sandbox's user-site packages (the subprocess is given a synthetic `HOME`
  and `PATH=/usr/bin:/bin`, so user-site deps are invisible). Proven environmental, not a code
  defect: with the same deps visible on the child's `PYTHONPATH`, `import main` returns 0, and
  the whole suite is green inside `.venv` (as CI installs into a normal site-packages).

### Branch and commits
- Branch: `agent/ohb2-audit-remediation` (push only agent/* per AGENTS.md §6).

## Phase 6 — Hosting compatibility & deployment plan (OHB2-PHASE6-HOSTING-COMPATIBILITY-AND-DEPLOYMENT-PLAN)

Acceptance criteria (testable):
1. Actual repo state established (branch/HEAD/clean tree/refs/merge-base) without fetch/switch.
2. Phase-5 follow-up commit `c41a57c` reviewed (ordering, dedup, cursor/truncation, tombstone
   filtering, recovery tests, trusted-proxies docs) — with a verdict.
3. Hosting requirements derived from real code (cited files/symbols), no invented config.
4. Provider comparison grounded in current official docs; unknowns labelled.
5. ≥1 technically suitable hosting recommendation justified, or its absence explained.
6. Explicit SQLite persistence contract (path, WAL, owner, restart/redeploy, lost state).
7. H1 stays UNVERIFIED unless real hosting evidence proves it.
8. Documentation-only deployment runbook (no execution).
9. Precise H1 evidence checklist.
10. All local verification reported honestly; independent-review status disclosed.
Out of scope: any code/config change, deployment, Git write, production access.

Plan (steps): (1) state+refs, (2) review c41a57c + focused/full tests, (3) requirements extraction,
(4) official provider research, (5) persistence contract, (6) write `docs/OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md`,
(7) report.

Result: DONE (code-level review + documentation). H1 remains UNVERIFIED (no hosting evidence).
Independent review: BLOCKED (no local reviewer session; contacting production is forbidden).
Artifact: `docs/OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md` (documentation only, uncommitted).

## Phase 6b — Katabump preflight & H1 validation (OHB2-KATABUMP-PREFLIGHT-AND-H1-VALIDATION)

Acceptance criteria (testable):
1. Current Katabump official docs reviewed (docs.katabump.com + katabump.com/terms), each claim
   cited with URL + date + confidence.
2. Katabump compatibility assessed against real OpenHandBot requirements (PASS/CONDITIONAL/FAIL/UNKNOWN).
3. Renewal + permanent-deletion risk assessed explicitly; no Backup/snapshot workaround proposed.
4. A safe, isolated SQLite canary procedure documented (no OpenHandBot config/services).
5. No deployment, no production polling, no provider infra created, no secrets.
6. H1 remains UNVERIFIED (docs are not proof of mounted-volume persistence).
7. Only `docs/OHB2_KATABUMP_H1_VALIDATION.md` created; no code/config/script edits.
Out of scope: running the canary, creating a Katabump account/server, any Git write.

Result: DONE (documentation only). H1 = UNVERIFIED. Katabump = provisional candidate.

## Phase 6c — Katabump isolated SQLite canary package (OHB2-KATABUMP-ISOLATED-SQLITE-CANARY-PACKAGE)

Acceptance criteria (testable):
1. Package independent of OpenHandBot runtime (stdlib only; no app imports/env/.env).
2. No application code or configuration changed.
3. No production service accessed; no network in the canary.
4. Local canary checks pass (write/read/inspect + guardrails).
5. Instructions distinguish process restart vs server restart vs redeployment.
6. No automatic deletion or overwrite of existing data.
7. No provider account/server created by this task.
8. H1 remains UNVERIFIED until actual provider tests pass.

Result: DONE (package + docs only). Created `tools/katabump-sqlite-canary/{canary.py,README.md,requirements.txt}`.
Local tests: write/read/inspect OK (WAL confirmed, markers persist, 2nd process reads); guardrails OK
(relative path, repo-local path, bot_state.sqlite3, missing parent, existing DB w/o --confirm-overwrite,
missing DB ⇒ non-zero; no --db ⇒ exit 2); socket-blocked write/read ⇒ no network.
H1 = UNVERIFIED. Autopush INACTIVE. No Git write.

## Phase 7 — Final release gate (OHB2-PHASE7-FINAL-RELEASE-GATE)

Acceptance criteria (testable):
1. Repo identity/branch/HEAD/upstream/tree recorded; baseline vs origin/main established read-only.
2. Full release-readiness audit of the app (architecture, handlers, Mini App, OpenHands client, DB,
   workers, deletion lifecycle, security, RTL/a11y, deps, docs, tests) with severities.
3. All documented checks run; exact commands + exit codes + counts recorded; blockers classified.
4. Only clear in-scope defects fixed, each with a regression test; full suite re-run.
5. Independent-review package prepared (baseline/candidate hashes, diff, evidence, risks).
6. Final decision (PASS/PASS_WITH_NOTES/BLOCKED/FAIL) + Phase 8 recommendation.
Out of scope: deploy, publish, merge, push, PR, Telegram/OpenHands production calls, autopush,
Backup, architecture change, Enzonic Backups/Reinstall/Delete/Egg-switch.
Constraints: Enzonic canary = SKIPPED/UNVERIFIED (persistent SQLite across container recreation
unverified); autopush DISABLED/INACTIVE; preserve unrelated changes/protected paths.

Result: PASS_WITH_NOTES. Baseline = origin/main c1aef66 (tree == ac35877, the branch merged by PR #4);
candidate = HEAD c41a57c (3 commits ahead, linear). Audited: lifecycle (main.py/bootstrap/app/web),
handlers, Mini App auth/ownership/CSRF/CORS, OpenHands client, DB schema/WAL/tombstones/deletion,
workers/recovery, security invariants, RTL/a11y, deps, docs. No Backup in operational code.
Verification (local, .venv py3.13): pyflakes exit 0; pytest 1576 passed / 0 skipped; node 143 pass;
high-risk subset 335 passed; compileall OK; no TODO/bare-except/hardcoded-secret. No code fixed
(no P0/P1 found). No Git write; tree unchanged except this file. Enzonic canary = SKIPPED/UNVERIFIED.
Phase 8: NOT_ELIGIBLE until H1 (SQLite persistence across container recreation) is verified.

## Phase 8 — Enzonic controlled-deployment PREFLIGHT (OHB2-PHASE8-ENZONIC-CONTROLLED-DEPLOYMENT-PREFLIGHT)

Acceptance criteria (testable):
1. Baseline re-verified (repo/branch/HEAD/upstream/tree) without fetch or branch change.
2. Enzonic compatibility assessed (esp. Python 3.14) with real evidence, not provider claims.
3. Exact deployment config documented (env names only, files, startup cmd, DB path, WAL, single-instance).
4. Personal single-user risk assessment incl. what SQLite holds and what is lost if it disappears.
5. Local checks run (py + frontend + static + compile + manifest/config + py3.14) with real output.
6. Autopush DISABLED/INACTIVE and no Backup subsystem; H1 recorded SKIPPED/UNVERIFIED.
7. Final preflight report + ordered manual procedure + recommendation; NO deployment performed.

Result: DONE (preflight only, docs only). Python 3.14.9 installed locally via uv and verified:
pytest 1576 passed / 0 skipped, pyflakes 0, compileall 0 (also green on repo venv 3.13); node 143 pass;
deploy-manifest/config/bootstrap/zero-touch/security subset 86 passed. Peak import RSS ~57 MiB,
site-packages ~47 MB. WAL+busy_timeout OK on nested abs path; parent dir auto-created (bootstrap READY).
Key blocker found: Enzonic default `python3 app.py` fails (no root app.py) ⇒ set `sh start.sh`/`python3 main.py`.
H1 = SKIPPED/UNVERIFIED. Autopush INACTIVE. No Backup. No Git write; no upload/deploy. Doc:
`docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md`. Recommendation: PREFLIGHT_READY_WITH_RISKS.

## Phase 8 — Enzonic PRODUCTION deployment (OHB2-PHASE8-ENZONIC-PRODUCTION-DEPLOYMENT)

Result: BLOCKED at the server-side step (environment lacks Enzonic panel/SFTP credentials and the
app secrets TELEGRAM_BOT_TOKEN / ALLOWED_TELEGRAM_ID). Per policy: did not guess, did not request
secrets in chat, did not perform account recovery. No file uploaded, no server configured, no
process started, no Telegram/OpenHands production call.
Pre-deployment work DONE and verified:
- HEAD == candidate c41a57ca30558289918cb6883a2872d0826fbfee; runtime files identical to that commit.
- Local: pyflakes 0; pytest 1576 passed/0 skipped; node 143 pass; compileall 0.
- Verified exact runtime bundle built from tracked tree at HEAD (36 entries, zero forbidden files):
  main.py, start.sh, requirements.txt, README.md, full bot/ incl. bot/web/static/.
- Bundle self-sufficient: extracted ZIP, repo off sys.path → import main OK, bootstrap READY,
  DB healthy, journal_mode=wal, busy_timeout=5000, parent dir auto-created; single-instance proven.
- Bundle artifacts (outside repo): /workspace/ohb2-phase8-enzonic-deployment/
  ohb2-runtime-c41a57ca3055.zip (sha256 d85ae1840fb9e05995d8dd2625ccfd2e318261d7f1bc9c67652689fb056cc676),
  CHECKSUMS.sha256, DEPLOYMENT-RUNBOOK.md.
H1 = SKIPPED/UNVERIFIED. Autopush INACTIVE. No Backup. No Git write.

## Publish approved candidate to origin/main (OHB2-PUBLISH-APPROVED-CANDIDATE-TO-GITHUB-MAIN)

Result: STOPPED — not published. Gate failure: candidate is NOT a fast-forward of origin/main.
Evidence (read-only, after `git fetch --prune origin`):
- origin/main = c1aef66c5838f2216fef9ba4c096a73dbfaea374 (unchanged from historical value).
- candidate HEAD = c41a57ca30558289918cb6883a2872d0826fbfee (branch agent/ohb2-audit-remediation).
- merge-base(HEAD, origin/main) = ac358775edc23bdc38e428430776eaccba8b92eb.
- `git merge-base --is-ancestor origin/main HEAD` -> NO  ⇒ not a fast-forward.
- origin/main has 1 commit the candidate lacks: c1aef66 (merge of PR #4 from openhands-workspace-...).
- candidate has 3 commits origin/main lacks: b1dd979, 0e2ab56, c41a57c.
- tree(c1aef66) == tree(ac35877)  ⇒ divergence is TOPOLOGY ONLY (no content conflict expected).
- `git push --dry-run origin HEAD:main` would be rejected (non-fast-forward); also hit a password
  prompt (interactive credential path), so it was not used.
Per the task STOP condition: did NOT rebase/reset/merge/overwrite; did NOT push. No PR, no deploy.
Verification still run (read-only): pyflakes 0; compileall 0; pytest 1576 passed; node 143 pass.
Gates: no .env / no *.sqlite3 tracked; no operational Backup; autopush INACTIVE; user work preserved
(.agent/PROGRESS.md, docs/* untracked, tools/, .openhands/) — nothing staged or committed.
Safest next step (needs explicit user approval): rebase the 3 candidate commits onto origin/main
(`git rebase origin/main`) then push FF-only; expected clean because the trees are identical.

## Rebase and publish to origin/main (OHB2-REBASE-AND-PUBLISH-TO-GITHUB-MAIN)

Result: COMPLETE — published and independently verified.
- Original candidate HEAD: c41a57ca30558289918cb6883a2872d0826fbfee.
- Rebased HEAD: 4468eab833c510a34be6833d8399f290f395e6f8 (branch agent/ohb2-audit-remediation).
- origin/main: c1aef66c5838f2216fef9ba4c096a73dbfaea374 -> 4468eab833c510a34be6833d8399f290f395e6f8 (fast-forward).
- Rebased commits: b1dd979->b372c12, 0e2ab56->705464f, c41a57c->4468eab (order preserved, no conflicts).
- tree(rebased HEAD) == tree(old candidate c41a57c) => content fully preserved; only topology changed.
- Rebase used --autostash so my uncommitted .agent/PROGRESS.md notes were reapplied uncommitted (NOT published).
- Verification on rebased tree: pyflakes 0; compileall 0; pytest 1576 passed; node 143 pass.
- Gates: no .env/sqlite/wal/shm/pyc/venv/credentials in published tree (155 files); no operational Backup;
  autopush INACTIVE; untracked docs/* and tools/ NOT published.
- Independent check via GitHub API: remote main commit 4468eab, tree f0bf1617... == local HEAD tree.
- Auth: non-interactive GitHub HTTPS with ephemeral credential helper from GITHUB_TOKEN (no persistence).

## TASK: OHB2-TELEGRAM-MINI-APP-ACTIVATION-AND-REMOTE-OPENHANDS-DELETION
Branch: agent/ohb2-miniapp-remote-delete (from 4468eab = origin/main).

### Acceptance criteria (testable)
A1. index.html loads the official Telegram WebApp SDK so `Telegram.WebApp` exists inside the Mini App (current: SDK missing ⇒ initData empty ⇒ "افتح من جوه تيليجرام").
A2. /app + menu show a real `web_app` button when config valid; when invalid, ordinary commands keep working and a non-secret diagnostic explains why (ConfigError message via bootstrap/health), not a silent generic "unavailable".
A3. MINI_APP_URL rejects credentials, fragments, query, and non-https; ASGI routes reachable (already mounted); static assets load.
A4. initData validated server-side (already correct); ownership/ALLOWED_TELEGRAM_ID enforced.
B1. Delete removes the conversation from OpenHands via the verified endpoint `DELETE /api/v1/app-conversations/{conversation_id}` (Bearer), then finalizes local deletion. Confirmed remote success required before reporting success.
B2. Confirmation text explains remote deletion; Cancel changes nothing.
B3. Ownership enforced server-side; other users cannot delete.
B4. Durable deletion-in-progress marker; idempotent across retries/duplicate callbacks/restarts/timeouts.
B5. Timeout/lost response ⇒ uncertain outcome, NOT success; reconcile (verify absence) before deciding.
B6. Explicit handling of 401/403/404/429/5xx/malformed; no silent local-only fallback; no false success.
B7. No resurrection after success (tombstone already blocks).
Out of scope: Enzonic deployment, GitHub push/PR, production calls, Autopush, Backup.

### Phase 1 root causes (evidence)
- /app unavailable: handlers.app_command returns MINI_APP_UNAVAILABLE when `config.mini_app_url` is empty; MINI_APP_ENABLED defaults 0 ⇒ feature off by default. Not a bug in the handler; it is an activation/config gap.
- REAL frontend bug: bot/web/static/index.html never loads https://telegram.org/js/telegram-web-app.js, so window.Telegram.WebApp is undefined in real Telegram; app.js `tg` is null ⇒ initData "" ⇒ 401 "افتح من جوه تيليجرام". The whole flow cannot work.
- Deletion: bot/handlers.py delete_conversation_confirm + bot/web/services.py delete_conversation call db.delete_conversation (local only). openhands_client has NO delete method. Local-only by design.
- Tombstone + is_deleted guards block resurrection (kept).
- Verified API (Phase 3 gate PASS): live OpenAPI v1.79.0 has DELETE /api/v1/app-conversations/{conversation_id}; auth X-Access-Token (Bearer works; app uses Authorization: Bearer); 200 {"success":true}; 404 not found; 422 validation. Confirmed implemented in OpenHands source (deleteCloudConversation + official test conversation-delete.test.ts).

### Plan
1. index.html: add Telegram WebApp SDK script (before app.js, no defer issues).
2. Bootstrap diagnostics: surface Mini App config state (enabled/configured) without secrets.
3. Client: add delete_conversation(conversation_id) + get_conversation_status.
4. db: add deletion state machine (deleting/uncertain) columns + tombstone on delete start.
5. Mini App service + route: remote-first deletion with confirmations.
6. Bot handler: remote-first deletion.
7. Frontend: update delete UX + messages.
8. Tests: mini app + remote deletion; update existing local-only tests.
9. Full verification + docs.

### Phase 4 implementation — DONE (branch agent/ohb2-miniapp-remote-delete)
- A1: index.html loads telegram-web-app.js before /mini/app.js; CSP already allows telegram.org.
- A2: /app + menu button gated by MINI_APP_ENABLED AND valid MINI_APP_URL; non-secret diagnostic
  (_mini_app_diagnostic) when unavailable; ordinary commands unaffected.
- A3: MINI_APP_URL now rejects userinfo/fragment/query (config.py), https-only + public host.
- B1-B7: bot/deletion.py = single shared orchestration (bot + Mini App).
  - client.delete_conversation → DELETE /app-conversations/{id}, success only on {"success": true}.
  - client.conversation_exists → GET ?ids= for reconciliation.
  - db: deleted_conversations.remote_state/remote_updated_at (+migration), states
    deleting/uncertain/confirmed, begin_remote_deletion (durable pre-call marker),
    list_pending_remote_deletions, clear_remote_deletion; delete_conversation(remote_confirmed=).
  - Outcomes: 200/404 ⇒ confirmed+local delete; 401/403/422 ⇒ definite failure (no local delete);
    429/5xx/timeout/malformed ⇒ verify existence (absent⇒success, present⇒failure, unknown⇒pending 503).
  - Startup reconcile (bot/app.py _post_init) finalizes/undoes pending deletions; survives restart.
  - No resurrection (tombstone written before remote call); idempotent repeated delete.
- Frontend: delete confirm/success text says "from OpenHands"; retryable on failure.
- Docs: README, docs/MINI_APP.md, docs/API_NOTES.md updated.
- Tests added: tests/test_remote_deletion.py (17), client delete tests (5),
  miniapp activation tests (4), frontend remote-delete UX (2); existing local-only tests updated.
- VERIFIED: pytest 1602 passed; node --test 145 pass/0 fail; pyflakes 0; compileall 0.

## OHB2-REMOTE-DELETE-404-SEMANTICS — DONE (branch agent/ohb2-miniapp-remote-delete)

Goal: 404 من `DELETE /app-conversations/{id}` **مبهم** (غياب أو فشل خدمة داخلي) ⇒ ممنوع
اعتباره حذفًا مؤكّدًا. لازم يمرّ بتسوية التحقق من الوجود.

Acceptance criteria (كلها متحققة):
1. 404 مش نجاح تلقائي. 2. مدعوم بسلوك upstream موثّق. 3. المبهم يفضل pending/uncertain.
4. الوجود المؤكّد مايؤدّيش لحذف محلي. 5. المعمارية/الضمانات سليمة. 6. كل الاختبارات/الفحوص تمر.
7. المراجعة المستقلة معلّقة (مفيش backend reviewer) + handoff جاهز. 8. مفيش نشر/حذف حقيقي.

Evidence (upstream, OpenHands/enterprise@main):
- `app_conversation_router.py` DELETE: 404 في حالتين — `'Conversation not found'` (مش موجود)
  و`'Failed to delete conversation'` (فشل داخلي). ⇒ 404 مش دليل حذف.
- `GET /app-conversations?ids=`: نفس جلسة الكتابة (مفيش replica)، soft-delete بيتفلتر
  (`deleted_at IS NULL`)، الكتابة commit قبل الرد ⇒ قراءة قوية.

Changes:
- bot/deletion.py: 404 اتشال من auto-success و`_is_definite_failure` استثناه؛ أضفنا
  `_establish_absence` (قراءتين متتاليتين، bounded) و`_reconcile` المشترك؛ التسوية استخدمت
  `_establish_absence`. الحالات: غايب⇒confirmed+حذف محلي، موجود⇒failed+رجوع، تعذّر⇒uncertain.
- bot/openhands_client.py, bot/web/services.py: توثيق 404 المبهم.
- tests: test_remote_deletion.py (+6 حالات 404/reconcile)، test_conversation_deletion.py
  (+4 عبر المسار الحقيقي)، test_batch_c_integration.py (تحضير حذف محلي مباشرة)،
  tests/frontend/delete.test.js (local_only→remote_deleted).
- docs: README, docs/API_NOTES.md, docs/MINI_APP.md.

VERIFIED: pytest 1612 passed; node 145/145; pyflakes 0; compileall 0; focused deletion 252 passed.
NOT VERIFIED: live behavior against real OpenHands (no real API calls). Independent review pending.
No commit/push/PR/deploy/real deletion.

## OHB2-PHASE1A-PERSISTENT-MINIAPP-SESSIONS — IN PROGRESS (branch agent/ohb2-phase1a-persistent-sessions)

Goal: جلسات Telegram Mini App **دائمة** تنجو من إعادة تشغيل العملية/الخدمة، **بدون** إضعاف
أي ضمان مصادقة/تفويض/جلسة، وبدون كسر المعمارية (نفس مالك العملية/اتصال SQLite الواحد).

Acceptance criteria:
1. جلسة صالحة تفضل تصادق بعد إعادة بناء الخدمة/القاعدة (مثبت باختبار).
2. الانتهاء (TTL) والإلغاء (logout/رفض مستخدم) يفضلوا فعّالين بعد إعادة التشغيل.
3. الأمان ما اتضعّفش: توكن عشوائي opaque؛ القاعدة تخزّن **هاش SHA-256** بس (مفيش توكن خام)؛
   كوكي HttpOnly/Secure/SameSite=Strict؛ ملكية المستخدم مفروضة؛ فشل مغلق عند أي خطأ؛ مفيش تسجيل أسرار.
4. المعمارية محفوظة: نفس كائن Database/الاتصال الواحد؛ مفيش worker أو مخزن خارجي أو اتصال جديد.
5. الترحيل إضافي وغير مدمّر (CREATE TABLE IF NOT EXISTS) للقواعد القديمة.
6. كل الفحوص تمر: pytest كامل، pyflakes، node (بدون انخفاض عن baseline 1692).
7. مراجعة مستقلة معلّقة (مفيش backend reviewer متاح) + handoff جاهز.
8. مفيش نشر/دمج/force-push.

Out of scope: تغيير TTL الافتراضي أو خصائص الكوكي، إضافة تبعيات، تغيير بروتوكول initData،
تغيير تصميم التفويض، أي نشر/دمج.

Plan: (1) عمود/جدول web_sessions + دوال DB. (2) SessionStore دائم (هاش + fail closed).
(3) ربط app.py + FakeDb. (4) اختبارات. (5) توثيق MINI_APP.md. (6) تحقق كامل + مراجعة.

Baseline (before): pytest 1692 passed / pyflakes 0 / node 145 pass 0 fail.
After: pytest 1721 passed / pyflakes 0 / node 145 pass 0 fail.

Done: كل الكود والاختبارات والتوثيق (اختبارات الجلسات الجديدة 29).
Next: مراجعة مستقلة على SHA محدّد، ثم تقرير.
