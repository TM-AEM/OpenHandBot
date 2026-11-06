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
