# OHB2-REPAIR-PLAN-02-LIFE-01 (F1 + F2) — INDEPENDENT ADVERSARIAL REVIEW PROMPT

> Handoff for a **read-only** independent adversarial review (same style as the LIFE-01 review).
> The reviewer must NOT modify, commit, push, or open a PR. Evidence over assertion.

## Repository / scope

- Repo: `TM-AEM/OpenHandBot`.
- Branch under review: `agent/ohb2-plan02-life01-race-retry-fix`
  (base = `25ec46b654b8c2ab3a32f06a1d3be34d3dbf6be8`; `main` untouched; no push/PR).
- Artifacts to inspect (uncommitted on the branch):
  - `bot/db.py` — new `try_mark_attachment_item_stored` (atomic CAS).
  - `bot/attachments.py` — `OpportunisticSweeper` (F1) + `StagingStore.store()` step (4) (F2).
  - `tests/test_repair_plan_02_life01_f1_retry.py` (10), `tests/test_repair_plan_02_life01_f2_race.py` (13),
    `tests/test_repair_plan_02_life01_app_wiring.py` (3).
  - Updated: `tests/test_attachment_staging_a1.py`, `tests/test_repair_plan_02_life02_crash_recovery.py`,
    `tests/test_repair_plan_02_life01_opportunistic_cleanup.py`.
  - `.agent/PROGRESS.md` (results + gate).

## Claims to falsify (do not accept them on faith)

**F1 — failed sweeps must not be treated as success.**
- `maybe_sweep()` must NOT advance the *last-success* stamp when (a) `sweep()` raises, or
  (b) `sweep()` returns `SweepReport(errors>0)`.
- Only `errors==0` advances last-success.
- Retry must be **bounded** (no per-tick tight loop) and documented; the last-attempt throttle
  must still apply.
- `Watcher` with no sweeper must keep prior behavior.

**F2 — no resurrection of an expired/reaped item.**
- The final `pending ⇒ stored` transition must be **atomic** and conditional on the item being
  `pending` AND the parent batch being `pending` (single SQL evaluation on the single DB connection).
- A late store into an `expired`/terminal batch, or onto a `reaped` item, must be **rejected**
  (fail closed), the owned artifact unlinked, and **no success** reported.
- `t0` must not be extended; identity evidence unchanged; no outbox/prompt side effects.

## Required adversarial checks (attack each; cite file:line)

1. **Atomicity, for real.** Is the check truly inside the same `UPDATE` (no read-then-write across
   `await`)? Is it on the **same** connection (`db._conn`)? Any window between the `BEGIN IMMEDIATE`
   and the `UPDATE`? Any nested-transaction / "cannot start a transaction within a transaction" hazard
   given the single connection?
2. **Status-only vs deadline.** The fix checks parent `status`, not `t0`. Prove or refute that
   "parent `status == pending`" is the correct and sufficient condition (reaper sets `expired` before
   `reaped`). Find any interleaving where an item ends up `stored` inside an `expired`/terminal batch,
   or where a legitimate live store is wrongly rejected.
3. **Reaper ordering.** Verify `AttachmentReaper.sweep` marks the batch `expired` (row-first) before
   reaping items and deleting files — the whole argument depends on it.
4. **F1 error semantics.** Confirm `AttachmentReaper.sweep` really returns `errors>0` (rather than
   raising) on partial DB/FS failures — otherwise F1's fix has no effect on the real failure path.
   Check `SweepReport` fields used.
5. **Retry bound.** Prove there is no path where a failing sweep is retried every tick (throttle must
   apply to attempts, not only successes). Look for the `_running` guard and `finally` ordering.
6. **Test fidelity.** Are the new tests deterministic (no real sleeps/network)? Do they assert
   *behavior* (states, files, outbox) not implementation? Does Race A genuinely reproduce the old
   defect (i.e., would it fail on the pre-fix code)? Are the 3 updated tests' changes faithful
   (same intent, only the renamed method / corrected retry expectation)?
7. **Regression surface.** Any caller of the removed/renamed transition? Confirm
   `set_attachment_item_status` is still correct for its remaining callers. Any new fail-closed path
   that could delete an *unowned* file or delete on a benign race?
8. **Protected invariants.** R-3 (no intake cleanup on the accept path), A4 boot sweep, Plan 01
   findings, extension/magic/ownership checks, row-first ordering, safe rejection — all still intact?
9. **Scope.** Confirm no `concurrent_updates(True)` change, no new worker/scheduler/DB/owner, no remote
   delivery/upload, no architecture change.

## Environment note for reproduction

- Install: `pip install -r requirements-dev.txt`.
- Full suite: `python -m pytest -q` → expect **1 pre-existing** failure,
  `tests/test_deploy_manifest.py::test_documented_manifest_is_import_sufficient` (environmental:
  deps are user-site and the test strips `HOME` ⇒ `ModuleNotFoundError: telegram`). Reproduce with a
  real `HOME` to confirm it is not a regression.
- Lint: `python -m pyflakes bot/ automation/ main.py tests/` (expect clean).
- SCA/SAST: `python -m pip_audit -r requirements-dev.txt`; `python -m bandit -r bot/ automation/ main.py -lll -s B613`.

## Output format

- Verdict: `PASS` | `PASS_WITH_NOTES` | `NEEDS_REVISION` | `BLOCKED`.
- Findings, each with severity (INFO/LOW/MEDIUM/HIGH), file:line, a concrete counterexample or
  reproduction, and a minimal fix. State explicitly which claims you verified TRUE and which you could
  not verify (UNVERIFIED + why). No success claims from reading code alone.
