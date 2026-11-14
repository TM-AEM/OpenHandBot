# OHB2-P0-A3 — Independent Adversarial Review (read-only)

- Reviewer: separate OpenHands Cloud conversations (fresh context), repository `TM-AEM/OpenHandBot`,
  `selected_branch=main`. The A3 change set is **not committed and not pushed**, so the reviewer
  could not `git diff` it; the verbatim diff + the D-27…D-31 decision text were embedded in the task,
  and the reviewer reconstructed the A3 modules in a scratch copy, ran them, and mutation-tested them.
  The real repo was left untouched (read-only; no commit/push/PR).
- Scope reviewed: P0 Stage A3 only — **local accompanying-text intent** (`bot/attachment_text.py`,
  `bot/attachments.py`, the A3 branch in `bot/handlers.py`, `bot/db.py` A3 methods,
  `bot/update_outcomes.py`, and the A3 tests).
- Conversation 1 (round 1): `dd43624e59624165b87964ca90746a5a`.
- Conversation 2 (round 2, after F-1/F-3 fixes): `b2cfeacc644e49cba532410e2f1ca7c9`.

## Round 1 — verdict: NEEDS_REVISION

Independently **confirmed true by execution**: no remote send / no `outbox` row on the eligible path;
the intent write is genuinely atomic (`BEGIN IMMEDIATE`, one commit — fault injection between the two
writes rolled both back); all fail-closed cases (multi-live, route-mismatch, no-route, deleted,
expired, ineligible) → `rejected_ineligible` with the batch untouched; D-28 normalization/limits
exactly (6144 raw → 4096 → eligible; +1 → 4097 → rejected); ack semantics (`rejected_ineligible`
eligible, failures not). Reconstructed suite 18/18 + 26/26 pass.

| # | Sev | Summary | Disposition |
|---|-----|---------|-------------|
| F-1 | MEDIUM (blocking) | A `pending` batch with an invalid/empty `t0` was counted as **neither live nor expired**, so the text **fell through to the normal prompt path** (→ `outbox`, remote send). Reproduced end-to-end. Violates D-29 items 4/5/7 (no silent fallback). | **FIXED** — `Database.has_expired_pending_attachment_batch` is now fail-closed: an unusable `t0` (or unusable `now`) counts as "not live", so the handler rejects with `rejected_ineligible`. Guarded by `if not rows: return False` so a batch-less user is never wrongly rejected. Regression: `test_pending_batch_with_invalid_t0_does_not_fall_through_to_prompt` (mutation-proved). |
| F-2 | MEDIUM | The diff bundles out-of-scope ack-semantics changes (`mark_operational_failure`, `show_status`/`show_cost`/open/copy/full). | Out of A3 scope — pre-existing branch state (OHB2-STAGE4-F1), **not** part of the A3 change set. Not modified. |
| F-3 | MEDIUM | The atomicity + CAS invariant was **not locked by any test** (split commit / dropped CAS / reordered outcome all left the suite green). | **FIXED** — `test_intent_write_is_atomic_on_failure` injects a failure between the batch UPDATE and the outcome write and asserts full rollback (batch stays `pending`, no `intent_text`, outcome non-ack-eligible, no `outbox`). Mutation-proved. |
| F-4 | MEDIUM | `bot/attachments.py` (A2) is imported but absent from the embedded diff, so the reviewer could not run the full handler path. | Review-setup limitation — the file exists in the working tree (A2, untracked) and is registered in `bot/app.py`. Not an A3 defect. |
| F-5/F-6/F-7/F-8 | LOW | DEL/ZWSP/BOM accepted as content; expired/other-conversation batches block normal prompts with no reaper; `record_rejected_ineligible` silently no-ops without `update_id`; `_INELIGIBLE` doc set not updated. | Deferred/covered — see notes below. |

## Round 2 — verdict: NEEDS_REVISION (after F-1/F-3 fixes)

Confirmed by execution: F-3 tests **do** fail under their mutants (split-commit leaks the batch as
`intent_recorded`; reverting the `t0` fix makes the invalid-`t0` test fail). F-1 is closed for the
`pending` status. The reviewer then enumerated the full status matrix and raised:

| # | Sev | Summary | Disposition |
|---|-----|---------|-------------|
| F1-1a | MEDIUM | A batch in a **non-`pending`** status (`intent_recorded`, `dispatching`, `uncertain`, `delivered`, `expired`, `rejected`, `failed`) is matched by neither `list_live_pending_attachment_batches` nor `has_expired_pending_attachment_batch` (both filter `status=pending`), so a following text **falls through to the normal prompt path**. | **OPEN — material owner-policy question. Not changed (STOP + document).** See below. |
| F1-1b | MEDIUM (latent) | Same fall-through for the B-stage statuses (`dispatching`/`uncertain`/`delivered`), which are defined in A0 but have no transition logic yet (B not authorized). | Same as F1-1a — the behavior will matter once B is implemented. |
| F1-2 | LOW | `has_expired_pending_attachment_batch` returned `True` for an invalid `now` **even with no rows**, so a batch-less user could be wrongly rejected. | **FIXED** — added `if not rows: return False`. |
| F1-3 | LOW | The new invalid-`t0` test covers `status=pending` only. | Accepted — the other statuses are the F1-1a policy question. |
| INFO | — | D-28 says "presence is measured on the raw text before any normalization"; the code measures `normalized.strip()`. | Equivalent in practice (normalization only maps `\r`↔`\n`, both stripped); the reviewer flagged it as a wording-level deviation, not a behavior bug. No change. |

### Why F1-1a/F1-1b is an owner-policy question, not a mechanical fix

- D-29 governs "a **live pending** batch" (= `status=pending` within the 15-minute window) and "an
  **expired** batch". The other statuses belong to the **A3↔B boundary** (`dispatching`/`uncertain`/
  `delivered` are Stage-B states, **not authorized**; `expired` is the A4 sweep tag).
- Blocking **all** non-`pending` statuses would be wrong: terminal states (`delivered`/`expired`/
  `rejected`/`failed`) carry no ambiguity, and blocking them would wedge the user permanently while B
  is unimplemented.
- Deciding which "active, not-yet-dispatched" states must block a normal prompt requires Stage-B policy
  (D-10/D-11, **not authorized**) — implementing it would be **inventing owner policy**.
- The current behavior (text after an intent is recorded → normal prompt) is consistent with the staged
  plan ("A3 routes the text when a **live** batch exists", live = `pending`) and avoids wedging users.

**Requested decision (one):** which non-`pending` `attachment_batches` statuses must block the normal
prompt (fail-closed) instead of falling through? Reviewer's suggestion: block
`intent_recorded`/`dispatching`/`uncertain`/`delivered`; leave `expired`/`rejected`/`failed` unblocked.

## Could not verify

- Running the **actual** test files against the reviewer's reconstructed modules (the files are not on
  any branch/PR); the reviewer ran an equivalent mirror instead.
- Real PTB `Application.process_update` behavior for the fault-injection test (reconstructed logically).
- Full `pytest` on an A3-only tree (the diff cannot be applied standalone because `bot/db.py` /
  `bot/handlers.py` context depends on A0–A2, which are also unpushed).

## Verification after the fixes (in this workspace)

- `python -m pytest -q` → **2741 passed**, 72 warnings.
- `python -m pyflakes bot/ automation/ tools/ main.py tests/` → exit 0.
- `python -m bandit -r bot/ automation/ main.py -lll -s B613` → exit 0 (High = 0).
- `node --test tests/frontend/*.test.js` → 219 pass / 0 fail.
- New tests are mutation-proved: reverting the F-1 fix fails the invalid-`t0` test; splitting the
  intent transaction fails the atomicity test.

_This review was produced by an AI agent (OpenHands) on behalf of the repository owner._
