# OHB2-WP01 — Stage 1 Owner Acceptance and Publication Strategy

- **Task:** `OHB2-WP01-STAGE1-OWNER-ACCEPTANCE-AND-PUBLICATION-STRATEGY`
- **Date:** 2026-11-21
- **Repository:** `/workspace/project/OpenHandBot`
- **Status:** `PROPOSED — OWNER DECISION REQUIRED`
- **Implementation:** **NO CODE CHANGE AUTHORIZED BY THIS PACKAGE**
- **Owner acceptance:** **NONE RECORDED**
- **Independent review:** **NOT PERFORMED**
- **WP-01:** **NOT CLOSED**
- **Completion:** **COMPLETE_WITH_NOTES** (dependency/attribution limitations remain)

> This is a design and decision-preparation document only. It does not modify application code,
> tests, configuration, schema, Mini App files, existing reports, or owner-decision fields. It does
> not stage, commit, push, fetch, create a branch/worktree, open a PR, merge, deploy, or activate
> Autopush.

## 1. Executive recommendation

**Do not publish the current working tree as an isolated Stage 1 unit.**

The technical Stage 1 behavior is `PASS_WITH_NOTES`, but publication readiness is `NOT_READY`
because Stage 1 is intermingled with prerequisite WP-01 lifecycle work and unrelated changes in the
same files, and no explicit Stage 1 owner acceptance is recorded.

**Recommended immediate strategy: Option C — keep the work uncommitted until a clean reconstruction
is possible.** Use a future isolated reconstruction task to build a reviewed prerequisite and Stage 1
patch from a clean base; then prefer **Option B** (prerequisite first, Stage 1 second) if the
prerequisite can be extracted cleanly. Option A is a fallback if the owner prefers one combined
WP-01 unit, but it has the largest review and attribution surface.

This recommendation is conservative and reversible. It does not close WP-01, does not accept Stage 2,
and does not authorize publication.

## 2. Current verified status

### 2.1 Actual Git state at this package

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Staged entries | 0 |
| Tracked modifications | 23 |
| Untracked files before this package | 30 |
| Full working-tree diff SHA-256 | `25a53aaad27eeaaffcaa47e95b1c650be2c457f67bb12a92906d395e3e1a648f` |
| Relevant ignored files | `.openhands/`, `.pytest_cache/`, `__pycache__/` trees |

The current state matches the final acceptance audit's state (23 modified + 30 untracked after its
report; 29 before it). The working tree is not clean and is not equal to `HEAD`.

### 2.2 Evidence and limitations

| Evidence | Status |
|---|---|
| Stage 1 technical acceptance | `PASS_WITH_NOTES` in `docs/reviews/OHB2-WP01-STAGE1-FINAL-ACCEPTANCE-AND-COMMIT-READINESS-REPORT.md` |
| Scope isolation | `NOT_ESTABLISHED` in the same audit |
| Publication readiness | `NOT_READY` in the same audit |
| Stage 1 source hashes | Match the Stage 1 and N1/N2 reports |
| Current focused/full test rerun | **NOT AVAILABLE**: no `/tmp/ohb2-venv`, no system `pytest`, no Docker daemon |
| Static syntax/whitespace | `python3 -m py_compile` exit 0; `git diff --check` exit 0 in the prior audit |
| Independent review | **NOT PERFORMED** |
| Stage 1 owner approval | **NOT RECORDED** |
| Stage 2 approval | **NOT RECORDED** |

Documented prior results (39 Stage 1 tests, 44 N1/N2 tests, 3584/3628 full-suite passes, 280 Node
passes) have provenance through matching source hashes, but they are not a current independent
rerun and are not independent review.

### 2.3 What is actually committed vs working-tree only

`HEAD` contains the pre-existing attachment staging/acceptance/reaper foundation and the old
attachment lifecycle code. The following are **absent at HEAD** and present only in the working tree:

- `ATTACHMENT_BATCH_CANCELLED`
- `attachments_cancel`
- `cancel_pending_attachment_batch`
- `ATTACHMENT_BATCH_CLEARABLE_STATUSES`
- `clear_attachment_terminal_batch`
- `attachments_clear`
- `ATTACHMENT_BATCH_REAPABLE_STATUSES`
- OD-03 default-off behavior (`HEAD` still defaults intake to `True`)

No Stage 1 or prerequisite WP-01 code is committed or published.

## 3. Dependency graph

### D1 — OD-03 document intake configuration and opt-in

| Aspect | Evidence |
|---|---|
| Source | `bot/config.py:39-44` (`Config.attachment_document_intake_enabled = False`); `bot/config.py:315-318` (`_parse_bool(..., False)`) |
| Runtime behavior | `bot/handlers.py:2574-2584` rejects document intake before `get_file`/download/row/file when disabled; `bot/handlers.py:2698-2715` selects truthful unsupported-media text |
| Configuration/docs | `.env.example:2`; `README.md:92`; `docs/OPERATIONS_RUNBOOK.md:67`; `docs/ZERO_TOUCH_STARTUP.md:94` |
| Tests | `tests/test_repair_plan_02_life03_intake_kill_switch.py:52-234` (disabled, no rows/files/network/outbox, explicit enable, default false); `tests/test_wp01_attachment_lifecycle.py:421-440` (truthful media text) |
| Status | **Working tree only; absent at HEAD** |
| Schema/state assumption | No schema change; existing `Config` field and existing attachment path |
| Can Stage 1 work without it? | **Partially.** Cancellation and storage logic can run with intake default `True`, but the owner-approved WP-01 policy (OD-03) and the combined lifecycle behavior require it. It is a prerequisite for a coherent WP-01 publication, not for the isolated Stage 1 CAS algorithm. |

### D2 — OD-01 terminal clearance and routing

| Aspect | Evidence |
|---|---|
| Source | `bot/db.py:174-183` (`ATTACHMENT_BATCH_CLEARABLE_STATUSES`, settings key prefix); `bot/db.py:1544-1645` (`list_terminal_attachment_batches`, `list_attachment_batches_for_owner`, `is_attachment_terminal_cleared`, `clear_attachment_terminal_batch`); `bot/db.py:1760-1852` (`classify_attachment_routing`) |
| Runtime behavior | `bot/handlers.py:3019-3088` (`/attachments`, `/attachments_clear`); `bot/app.py:56-57,118-119` registration; `docs/OPERATIONS_RUNBOOK.md:318-319` |
| Tests | `tests/test_wp01_attachment_lifecycle.py:100-298` (clearance eligibility, ownership, idempotency, rollback, reopen, terminal routing); `tests/test_wp01_attachment_lifecycle.py:321-403` (command/ownership) |
| Status | **Working tree only; absent at HEAD** |
| Schema/state assumption | Existing `settings` table stores `attachment_terminal_clearance:<batch_id>`; no new table/column; `attachment_message_identity` remains untouched |
| Can Stage 1 work without it? | **No for the actual Stage 1 routing code.** Stage 1 `classify_attachment_routing` calls `list_terminal_attachment_batches` and `is_attachment_terminal_cleared` (`bot/db.py:1823-1849`), and T4 depends on `clear_attachment_terminal_batch`. The prerequisite must be present before Stage 1 is applied. |

### D3 — `/attachments` and `/attachments_clear`

| Aspect | Evidence |
|---|---|
| Source | `bot/handlers.py:3019-3088`; `bot/app.py:56-57,118-119`; `bot/db.py` clearance methods in D2 |
| Tests | `tests/test_wp01_attachment_lifecycle.py:321-403`; `/attachments` owner-scoped list tests |
| Status | **Working tree only; absent at HEAD** |
| Schema/state assumption | Metadata only; clearance marker in `settings`; no file/row deletion |
| Can Stage 1 work without it? | **No for a coherent WP-01 package.** Stage 1 adds the list hint (`bot/handlers.py:3039`), and the T4 test/behavior uses `/attachments_clear` to prove cancelled is not clearable. |

### D4 — Attachment staging, acceptance, and reaper lifecycle

| Aspect | Evidence |
|---|---|
| Source | `bot/attachments.py` — `StagingStore` (`~500-1015`), `AttachmentService.accept` (`1071-1199`), `AttachmentReaper` (`1297-...`); `bot/db.py` schema `attachment_batches`/`attachment_items`/`attachment_message_identity` (`~807-839`), item/batch methods |
| Runtime behavior | Row-first acceptance, staging writes, TTL expiry, terminal reaping, identity evidence |
| Tests | `tests/test_attachment_batch_lifecycle_a2.py` (first batch/append/TTL/auth/duplicate); `tests/test_attachment_staging_a1.py`; `tests/test_attachment_cleanup_expiration_a4.py`; `tests/test_repair_plan_02_life01_f2_race.py`; `tests/test_repair_plan_02_life02_crash_recovery.py` |
| Status | **Foundation present at HEAD; lifecycle/OD-03 changes working-tree only** |
| Schema/state assumption | Existing SQLite schema; statuses are text values; no migration required for `cancelled`; identity evidence preserved |
| Can Stage 1 work without it? | **No.** Stage 1 extends the existing staging/reaper lifecycle and relies on its row-first, TTL, ownership, and identity semantics. |

### D5 — Stage 1 cancellation state, command, synchronization, N1/N2

| Aspect | Evidence |
|---|---|
| Source | `bot/db.py:132-155` (`cancelled`, reaping set), `:195-200` (`AttachmentBatchStateChanged`), `:554-556` (`AttachmentRoutingState.CANCELLED`), `:1349-1443` (CAS + cancel), `:1512-1523` (cancelled list), `:1717-1750` (N2), `:1847-1851` (routing), `:2051-2085` (conditional item insert) |
| Source | `bot/attachments.py:531-555` (guard), `:710-714` (N1), `:894-911` (sync store), `:955-1015` (async store), `:1116-1149` (expiry CAS), `:1201-1218` (cancel service), `:1316-1318,1428-1436,1582-1594` (reaper exclusion) |
| Source | `bot/handlers.py:2301-2305,2653-2670,2839-2842,3090-3133`; `bot/app.py:58,120`; `docs/OPERATIONS_RUNBOOK.md:320` |
| Tests | `tests/test_wp01_stage1_cancellation.py:133-702`; `tests/test_wp01_stage1_n1_n2_remediation.py:135-568` |
| Status | **Working tree only; no Stage 1 commit** |
| Schema/state assumption | `cancelled` is a text status in the existing `attachment_batches.status`; no new column/table; no file/row/identity deletion; `cancelled` is non-terminal/non-reapable |
| Can Stage 1 work without prerequisite D1-D4? | **No.** D2/D3 are referenced by routing/handlers/tests; D4 supplies the storage/reaper contract. D1 is required for the combined WP-01 policy. |

### D6 — Tests, documentation, and operational instructions

| Aspect | Evidence |
|---|---|
| Stage 1 tests | `tests/test_wp01_stage1_cancellation.py` (702 lines, 39 tests per implementation report); `tests/test_wp01_stage1_n1_n2_remediation.py` (576 lines, 44 tests) |
| Prerequisite tests | `tests/test_wp01_attachment_lifecycle.py` (444 lines); `tests/test_attachment_batch_lifecycle_a2.py`; `tests/test_repair_plan_02_life03_intake_kill_switch.py` |
| Docs | `docs/OPERATIONS_RUNBOOK.md:320` (Stage 1); `:67,318-319` (OD-03/OD-01); `README.md:92`; `docs/ZERO_TOUCH_STARTUP.md:94` |
| Reports | Stage 1 design/report, implementation/addendum, verification, N1/N2, final audit; WP-01 lifecycle report; OD decision record |
| Status | Tests/docs are working-tree or untracked; none are in `HEAD` |
| Can Stage 1 work without them? | **No for a publishable unit.** Tests prove behavior; docs/parity must match the code; the full suite is a publication gate. |

### Dependency conclusion

The dependency graph is a **WP-01 lifecycle chain**, not a standalone Stage 1 chain:

```text
OD-03 config/intake ─┐
OD-01 clearance/routing ─┼─> /attachments + /attachments_clear ─┐
Staging/acceptance/reaper (HEAD foundation) ─────────────────────┼─> Stage 1 cancellation + N1/N2
Stage 1 tests/docs/parity ───────────────────────────────────────┘
```

Stage 1 must be published **on top of** the prerequisite WP-01 lifecycle, or as part of a combined
WP-01 unit. File separation alone does not make it independently publishable.

## 4. Publication options

### Option A — Combined WP-01 lifecycle and Stage 1 publication

Publish the prerequisite lifecycle (OD-01/OD-03 and `/attachments`/`/attachments_clear`) plus
Stage 1 as one coherent unit.

**Advantages**

- Dependency-complete in one review unit.
- No intermediate release without cancellation.
- One owner acceptance and one rollback unit.
- Avoids a state where the prerequisite is published but Stage 1 is left behind.

**Risks**

- Largest scope and review burden.
- Mixed files still need hunk-level attribution; the current tree also contains unrelated poller,
  WP-07, WP-08, and WP-09 work.
- A single unit makes rollback broader.
- Exact Stage 1-vs-prerequisite attribution is not currently established.
- Requires explicit owner approval for the combined scope.

### Option B — Prerequisite lifecycle first, Stage 1 second

Extract and publish the prerequisite WP-01 lifecycle/OD-01/OD-03 unit, verify that baseline, then
apply and publish Stage 1.

**Advantages**

- Smaller, more reviewable prerequisite unit.
- Stage 1 can be isolated after the prerequisite baseline is fixed.
- Independent rollback: Stage 1 can be reverted without reverting the lifecycle prerequisite.
- Intermediate release has no cancellation support but also no cancellation-related deletion risk.

**Risks**

- The prerequisite itself is mixed in the current tree; a clean extraction is not yet established.
- Requires an intermediate release/verification cycle.
- Users lack active-batch cancellation until Stage 1 lands.
- Needs explicit owner approval for the intermediate state and for the prerequisite boundary.

### Option C — Keep everything uncommitted until a clean reconstruction is possible

Do not publish now. Preserve the working tree and reconstruct an isolated patch in a future task.

**Advantages**

- Most conservative; no risk of publishing unrelated work.
- No intermediate release with incomplete WP-01 behavior.
- Allows exact attribution and independent review before any publication.
- Preserves all existing changes and owner decisions.

**Risks**

- WP-01 remains uncommitted and unreleased.
- Requires a future reconstruction task and repeat verification.
- The working tree remains large and mixed until then.
- Does not by itself resolve owner acceptance or Stage 2 policy.

### 4.1 Decision matrix

| Criterion | Option A | Option B | Option C |
|---|---|---|---|
| Dependency completeness | High if combined | High after prerequisite extraction | N/A (no publication) |
| Scope size / review burden | High | Medium (two units) | Low immediate, future work |
| Exact isolation confidence today | Low | Low until prerequisite extracted | High (no publication) |
| Risk of unrelated work | High unless hunked | Medium unless hunked | None now |
| Rollback simplicity | One broad unit | Two independent units | N/A |
| Intermediate release risk | None | Feature gap without cancellation | None |
| Test/gate burden | One full combined gate | Two staged gates | Future reconstruction gate |
| Owner decision complexity | One broad approval | Two approvals/boundaries | One deferral + future task |
| Fit with current NOT_READY audit | Weak | Conditional | **Strongest** |

## 5. Recommended strategy and rationale

### 5.1 Immediate recommendation

**Choose Option C now.** The current tree is not safely isolatable, and publishing it would risk
including unrelated poller/WP-07/WP-08 work. Keep all changes uncommitted; do not stage or create a
branch/worktree in this task.

### 5.2 Preferred future publication path

Once a clean reconstruction is available, prefer **Option B** over Option A:

1. Build a clean prerequisite patch for OD-01/OD-03 and `/attachments`/`/attachments_clear` from a
   clean base, with exact file/hunk attribution.
2. Verify the prerequisite in a fresh environment (focused + full tests, lint, security, docs parity).
3. Publish/record the prerequisite only if the owner authorizes that intermediate unit.
4. Reconstruct Stage 1 on top of that fixed prerequisite, including N1/N2 and T1-T7.
5. Run the full combined verification and obtain owner acceptance.
6. Publish Stage 1 separately if authorized.

Option A remains a fallback if the owner prefers one combined WP-01 unit and accepts the larger
review/rollback surface. Option C remains the default until either prerequisite extraction or
combined hunk attribution is proven.

### 5.3 Safe future reconstruction procedure (not executed)

- Start from a clean clone/worktree of `HEAD` in a separate directory; do not use the current dirty
  tree as the publication source.
- Preserve the current tree read-only; do not reset/clean/restore it.
- Apply prerequisite hunks first, then Stage 1/N1/N2 hunks, using a reviewed allowlist.
- Run focused tests after each layer and the full suite on the final patch.
- Verify no unrelated files, secrets, debug code, Mini App, Stage 2 cleanup, or dependency changes
  are included.
- Obtain owner approval of the exact patch before any commit.
- If a genuinely independent review is separately authorized, use a separate session and clone; this
  package does not claim one.

## 6. Owner decision register

> **OWNER ONLY. NONE OF THESE FIELDS IS FILLED.** This package does not record approval on the
> owner's behalf.

### 6.1 Decisions already approved

| ID | Decision | Status | Evidence |
|---|---|---|---|
| OD-01 | Terminal clearance: Option C, exact batch, `expired`/`rejected` only, no deletion | **OWNER-APPROVED** | `docs/decisions/OHB2-WP01-OD01-OD03-OWNER-DECISION-RECORD.md` |
| OD-03 | Document intake default off, explicit opt-in `=1` | **OWNER-APPROVED** | Same record |
| WP-01 implementation scope | Safe active-batch abandonment without unlink/delete; no Stage 2 cleanup | **OWNER-APPROVED for the recorded WP-01 scope** | Same record; this does not by itself fill the Stage 1 §15 fields |

### 6.2 Decisions recommended but not approved

| ID | Question | Options | Owner selection | Signature/date |
|---|---|---|---|---|
| OD-S1-01 | Accept Stage 1 technically with the documented `row_created=True` residual? | ACCEPT / ACCEPT_WITH_NOTES / REJECT / DEFER | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S1-02 | Treat the `row_created=True` pending-row residual as accepted, or require a separate remediation task? | ACCEPT RESIDUAL / REQUIRE REMEDIATION / DEFER | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S1-03 | Publication strategy | A combined / B prerequisite-first / C keep uncommitted | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S1-04 | Adopt Stage 2 Option A (permanent retention)? | ADOPT OPTION A / DEFER / OTHER | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S1-05 | Authorize a future isolated publication-preparation task? | YES / NO; task ID: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S1-06 | Authorize any future branch/commit/PR/merge/deploy action? | YES / NO; exact action/scope: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |

### 6.3 Explicitly requiring separate authorization

- Stage 1 design acceptance and implementation/publication authorization.
- The prerequisite WP-01 boundary and intermediate release, if Option B.
- Stage 2 Option A adoption or any future cleanup.
- Any branch, commit, push, PR, merge, deployment, or Autopush action.
- Any genuinely independent review, if desired.

Technical `PASS_WITH_NOTES` is **not** owner acceptance. No field above is filled by this package.

## 7. Future publication gates

None of these gates has passed merely because this package was created.

| Gate | Required evidence | Current status |
|---|---|---|
| G1 — Owner decisions recorded | OD-S1-01..06 and existing OD fields completed by owner | **NOT MET** |
| G2 — Dependency baseline identified | Clean base tree/commit and prerequisite boundary | **NOT MET** |
| G3 — Exact file/hunk attribution | Allowlisted patch manifest; no mixed unrelated hunks | **NOT MET** |
| G4 — No unrelated changes | Diff review confirms no poller/WP-07/WP-08/Stage 2/Mini App/dependency changes | **NOT MET** |
| G5 — Focused and full tests in actual environment | Fresh venv; focused + full Python, Node, lint, security results | **NOT MET** in current environment |
| G6 — Docs/schema compatibility | Runbook/README/help/parity pass; no unintended migration | **NOT MET** for publication |
| G7 — Stage 1 + prerequisite review together | Combined lifecycle/cancellation/reaper review | **NOT MET** |
| G8 — Independent review (if separately authorized) | Separate session/clone; report | **NOT AUTHORIZED / NOT MET** |
| G9 — Final diff/scope approved by owner | Owner approval of exact patch | **NOT MET** |

## 8. Exclusions and unresolved risks

### 8.1 Excluded from this task

- No application code, tests, config, schema, runtime data, Mini App, or Stage 2 cleanup changes.
- No edits to existing reports or owner-decision fields.
- No branch/worktree creation.
- No stage/commit/push/fetch/PR/merge/deploy/Autopush.
- No deletion/move/restore/overwrite of existing files.

### 8.2 Unresolved risks

- Exact Stage 1 hunk attribution is not established.
- Prerequisite WP-01 changes are themselves mixed with unrelated work.
- Stage 1 depends on prerequisite code and cannot be applied alone to `HEAD`.
- The `row_created=True` residual leaves a pre-existing pending row; no false success, but owner
  acceptance or remediation is required.
- No explicit Stage 1 owner approval is recorded.
- No independent review is performed.
- No current test rerun is available in this environment.
- Stage 2 Option A is recommended but not owner-approved; Stage 2 fields remain blank.
- The working tree remains large and mixed; future reconstruction must preserve it.

## 9. Conclusion

Stage 1 is technically `PASS_WITH_NOTES`, but the complete WP-01 lifecycle is **not publication-ready**
as an isolated unit. The safe decision is to keep the work uncommitted (Option C) while preparing a
clean prerequisite-first reconstruction (Option B). Option A is a valid combined fallback only with
explicit owner approval and exact hunk attribution.

**No owner approval, no independent review, and no publication are claimed.**
