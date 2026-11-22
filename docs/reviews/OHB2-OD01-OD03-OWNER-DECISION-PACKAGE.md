# OHB2 — OD-01 and OD-03 Owner Decision Package

> **STATUS: `PROPOSED — OWNER DECISION REQUIRED`.** This document prepares two owner
> decisions. It does **not** select, record, or approve either decision on the owner's behalf.
> No implementation is authorized. The unchecked boxes in §13 remain the owner's exclusive
> choice.

**Task ID:** `OHB2-OD01-OD03-OWNER-DECISION-ANALYSIS`
**Date:** 2026-11-22
**Repository:** `/workspace/project/OpenHandBot`
**Baseline branch:** `main`
**Baseline HEAD:** `0774c9cff923a2ed02da36a1111a283a61600ea5`
**Baseline tree:** `faa7a3f03aa361698c6854281c162358bf38b84f`
**Master reconciliation:** `docs/reviews/OHB2-MASTER-BACKLOG-RECONCILIATION-AND-NEXT-TASK-REPORT.md`
**Master reconciliation SHA-256:** `0a2f771178bfc52e69f924a68b90956390e430191f8e07088ed6082d58dfdc9d`

---

## 1. Executive recommendation

### 1.1 Recommended OD-01 option

**Option C — Hybrid: explicit owner terminal clearance, with all ambiguous/uncertain states
remaining fail-closed.**

This is preferred over Option A because Option A leaves the CRITICAL `DEF-001` owner-wide text-prompt
block in place even after `/cancel`. It is preferred over Option B because Option B can silently pass
a delayed accompanying text into normal prompt routing after passive expiry; Option C requires an
explicit, durable owner action before normal text is allowed.

### 1.2 Recommended OD-03 option

**Option A — Change the default of `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` to `False` (`0`), with
explicit `=1` opt-in for local `MT-2` staging.**

This is preferred because:

- `MINI_APP_ENABLED` already defaults to `False`;
- Stage B remote upload is blocked;
- local staging has no user-facing value when the Mini App is off;
- default-off prevents fresh installations from accidentally creating attachment batches and
  exposing users to `DEF-001`;
- `MT-2` operators can opt in with one documented variable once `WP-01` is verified.

### 1.3 Recommended combined outcome

**OD-01 Option C + OD-03 Option A.**

This is a coherent pair:

- default installs do not stage Telegram documents and therefore do not create new terminal
  attachment batches;
- operators who explicitly enable `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1` get local `MT-2` staging;
- those opted-in users can recover from a terminal batch only through an explicit owner clearance
  action;
- no passive reaper or timeout silently turns a possibly-accompanying text into a new prompt;
- all unresolved, ambiguous, corrupt, identity-matched, and live states remain fail-closed.

This package does not claim that the owner has approved this pair.

---

## 2. Authoritative sources and evidence

### 2.1 Decision definitions

| Source | Role |
|---|---|
| `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` §4 (`OD-01`) | Original OD-01 decision statement, current behavior, Options A/B/C, and consequences. |
| `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` §6 (`OD-03`) | Original OD-03 decision statement, current behavior, Options A/B, and consequences. |
| `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` §`DEF-001`, §`DEF-014`, §`DEF-015`, §`WP-01` | Defect definitions, WP-01 scope, state-by-state preservation matrix, and owner-approval requirements. |
| `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` D-34, D-35, D-15 | Approved prior policy: `TERMINAL_UNPROVEN` fail-closed; identity-evidence retention; fixed 15-minute staging window. |
| `docs/reviews/OHB2-MASTER-BACKLOG-RECONCILIATION-AND-NEXT-TASK-REPORT.md` | Current backlog status; confirms WP-01 blocked on OD-01/OD-03 and no eligible next implementation task. |

### 2.2 Current implementation evidence

| Path / line | Verified fact |
|---|---|
| `bot/config.py:43` | `attachment_document_intake_enabled: bool = True`. |
| `bot/config.py:315-317` | Env parsing defaults to `True`; invalid non-empty values raise `ConfigError` through `_parse_bool`. |
| `bot/config.py:23,262` | `mini_app_enabled` defaults to `False`. |
| `.env.example:2` | `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=` is blank, so the default `True` applies. |
| `bot/handlers.py:2538-2558` | `handle_attachment` checks the intake flag **before** `get_file`, download, staging rows, or OpenHands calls; disabled intake replies with `ATTACHMENT_INTAKE_DISABLED_TEXT` and records `explicitly_ignored`. |
| `bot/handlers.py:2723-2805` | `_handle_accompanying_text` classifies the owner's attachment state and rejects terminal/unresolved/live-mismatch cases. |
| `bot/handlers.py:2908-2917` | `handle_text` always calls `_handle_accompanying_text` before ordinary prompt dispatch; the intake flag does not bypass this path. |
| `bot/db.py:1379-1386` | `has_terminal_attachment_batch` checks `delivered`, `expired`, `rejected`, or `failed` across **all conversations of the owner**. |
| `bot/db.py:1493-1585` | `classify_attachment_routing` returns `TERMINAL_UNPROVEN` when a terminal batch exists and no identity match; both terminal states block normal text. |
| `bot/db.py:1313-1361` | Live/expired pending checks are owner-wide and use the fixed 15-minute deadline. |
| `bot/db.py:1364-1377` | `intent_recorded`, `dispatching`, and `uncertain` are unresolved and fail-closed. |
| `bot/attachments.py:1349-1355` | The reaper deliberately skips unresolved states (`intent_recorded`/`dispatching`/`uncertain`). |
| `bot/handlers.py:2254-2257` | `UNSUPPORTED_ATTACHMENT_TEXT` always advertises “or send a document” even when intake is disabled. |
| `bot/handlers.py:2260-2262` | `ATTACHMENT_ACCEPTED_TEXT` says the text must arrive within 15 minutes but does not clearly say the files are local-only. |
| `bot/handlers.py:2663-2679` | `handle_unsupported_attachment` does not consult `attachment_document_intake_enabled`. |
| `bot/web/services.py:758-870` | `MT-2` lists/downloads only `pending` batches with `stored` items inside the fixed 15-minute window; expired/absent/invalid states fail closed. |
| `README.md:92` | Documents `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default `1`. |
| `docs/OPERATIONS_RUNBOOK.md:67` | Documents default `1`. |
| `docs/ZERO_TOUCH_STARTUP.md:94` | Documents default `1` and that `0` disables intake only. |

### 2.3 Test evidence available

Existing tests that encode current behavior:

- `tests/test_repair_plan_02_life03_intake_kill_switch.py`
  - disabled intake has no `get_file`, rows, files, outbox, or OpenHands calls;
  - enabled default stores a document;
  - config default is `True`;
  - `.env.example` contains the flag.
- `tests/test_attachment_batch_state_routing_f1_1a.py`
  - terminal states produce `TERMINAL_UNPROVEN`;
  - terminal state in another conversation blocks new text;
  - unresolved/live/expired/invalid cases fail closed.
- `tests/test_attachment_terminal_routing_remediation.py`
  - terminal text cannot reach outbox/remote calls;
  - unknown status raises `AttachmentBatchIntegrityError`;
  - rejection remains acknowledgement-eligible.
- `tests/test_unsupported_attachment_rejection.py`
  - unsupported media rejection has no side effects;
  - plain text still uses the text path.

**Test execution status in this task:** the host environment has no `pytest`, `telegram`, `anyio`, or
`httpx`, and no disposable verification container/venv was available. The attachment-focused tests
were **NOT RUN** here. This package relies on source inspection and the existing test intent; it does
not claim a fresh behavioral pass.

---

## 3. Exact decision definitions

### 3.1 OD-01

**Question:** What routing, classification, and recovery policy must govern subsequent owner text
prompts and unresolved or terminal attachment batches under `classify_attachment_routing`,
`_handle_accompanying_text`, and external-outcome tracking, given that the historical `D-34 Option A`
rule causes a permanent cross-conversation text-prompt deadlock (`DEF-001`) once any document batch
reaches a terminal state?

**Why required:** `D-34 Option A` is an approved owner policy; changing it requires explicit owner
authorization under `AGENTS.md` §14. Without a decision, WP-01 cannot change terminal routing, and
`/cancel` alone cannot unblock normal text because the rejected batch remains terminal and
`TERMINAL_UNPROVEN` remains global.

**Current behavior:**

1. A terminal batch (`delivered`/`expired`/`rejected`/`failed`) anywhere for the owner makes
   `has_terminal_attachment_batch` true.
2. If the incoming message has no `attachment_message_identity` match,
   `classify_attachment_routing` returns `TERMINAL_UNPROVEN`.
3. `_handle_accompanying_text` rejects the update as `REJECTED_INELIGIBLE`; `handle_text` never
   reaches `_send_prompt`/outbox.
4. `/cancel` currently clears only `user_state`; it does not abandon attachment batches and does not
   remove the global terminal block.
5. The reaper marks expired pending batches `expired`, skips unresolved states, and never deletes
   `attachment_batches` or `attachment_message_identity` (D-35).

**Approved constraints that cannot be silently changed:**

- `D-34 Option A` (`TERMINAL_UNPROVEN` fail-closed) is owner-approved policy, not merely code.
- `D-35` requires durable message-identity evidence independent of `processed_updates` pruning and
  forbids cascading deletion.
- `D-15` fixes the staging window at 15 minutes with no extension.
- No automatic poison skipping, no text/timestamp guessing, and no exactly-once delivery claim.

### 3.2 OD-03

**Question:** Should the default value of `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` change from `True` to
`False`, accepting that default `MT-2` staging becomes empty unless explicitly opted into, or remain
`True` contingent on WP-01 (`OD-01` + `/cancel` + policy-aware copy) mitigating `DEF-001`?

**Why required:** Changing the default alters the excluded Mini App `MT-2` out-of-the-box behavior
without editing Mini App code. The baseline explicitly requires owner approval for that behavioral
change.

**Current behavior:**

1. Default is `True`; blank `.env.example` means enabled.
2. When enabled, `handle_attachment` can stage supported documents under an open `route`; this creates
   `attachment_batches` and `attachment_items`.
3. When disabled, `handle_attachment` replies with `ATTACHMENT_INTAKE_DISABLED_TEXT`, records
   `explicitly_ignored`, and creates no rows/files/OpenHands calls.
4. Disabling intake does **not** change `handle_text` or `_handle_accompanying_text`; pre-existing
   batches still block text.
5. `MT-2` requires `pending` batches with `stored` items inside the 15-minute window; with intake
   disabled, its list is empty unless `=1`.
6. `MINI_APP_ENABLED` defaults to `False`, so `MT-2` is not active out of the box even today.

---

## 4. Available options

### 4.1 OD-01 options (preserved meanings)

#### Option A — Preserve `D-34` global fail-closed

Keep `classify_attachment_routing`, `has_terminal_attachment_batch`, `TERMINAL_UNPROVEN`,
`TERMINAL_ASSOCIATED`, and D-35 unchanged. Add `/cancel` for `pending`/`intent_recorded`, but terminal
batches continue to block all future text until a separate manual/authorized reconciliation.

- **Benefit:** no weakening of the approved fail-closed policy; no new clearance state.
- **Cost:** `DEF-001` remains: after any terminal batch, normal text is permanently blocked until
  manual intervention; `/cancel` alone does not help.

#### Option B — Verified terminal pass-through

Amend D-34 so `classify_attachment_routing` returns `NONE` only when:

1. no out-of-enum/NULL status exists;
2. no `UNRESOLVED` batch exists;
3. no live or expired-pending batch exists;
4. no `attachment_message_identity` match exists for the incoming message;
5. terminal batches have valid schema state and verified `t0`.

`TERMINAL_ASSOCIATED` remains fail-closed. Terminal pass-through may apply to all four terminal
statuses or only `expired`/`rejected`; that variant is an explicit owner choice.

- **Benefit:** automatic recovery after `/cancel`/reaper; no new command or clearance state.
- **Cost:** reverses D-34's availability trade-off. A delayed accompanying text arriving after
  passive expiry, without an identity record, can enter normal prompt/outbox routing as unattached.

#### Option C — Hybrid explicit clearance

Keep passive terminal/uncertain/ambiguous states fail-closed. Permit normal text only after an
explicit owner action that records durable clearance for a specific verified terminal batch. Keep
`TERMINAL_ASSOCIATED`, D-35, unresolved/live/expired/corrupt/ambiguous states fail-closed. Manual
reconciliation remains for `dispatching`, `uncertain`, `invalid_t0`, out-of-enum, and ambiguous
ownership.

- **Benefit:** fixes `DEF-001` without silent late-text routing; gives the owner a bot/operator path
  instead of raw SQLite edits.
- **Cost:** adds an explicit clearance state/command and operational friction; may require a small
  schema addition and additional tests.

### 4.2 OD-03 options (preserved meanings)

#### Option A — Default `False` (explicit opt-in)

Change `bot/config.py:43` and `:315-317` to default `False`; document `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0`
as the default and `=1` as the `MT-2` opt-in. No Mini App edits.

- **Benefit:** fresh installs cannot accidentally stage documents; reduces new `DEF-001` exposure;
  aligns with `MINI_APP_ENABLED=False` and blocked Stage B.
- **Cost:** `MT-2` is empty by default; operators must set `=1`; existing default-true tests/docs
  must change.

#### Option B — Keep default `True`

Keep the current default and rely on WP-01 (`OD-01` + `/cancel` + honest copy) to prevent bricks.

- **Benefit:** preserves zero-config `MT-2` staging and existing behavior.
- **Cost:** every fresh install can stage documents even when Mini App is off; `DEF-001` exposure
  remains until WP-01 and the selected OD-01 policy are fully implemented and verified.

---

## 5. Comparative analysis

### 5.1 OD-01 comparison

| Criterion | Option A | Option B | Option C |
|---|---|---|---|
| Fixes `DEF-001` | **No** — permanent until manual DB work | **Yes**, after terminal/clear conditions | **Yes**, after explicit owner clearance |
| Preserves D-34 fail-closed intent | **Yes** | **Partially** — amends it | **Yes**, with explicit exception |
| Silent late-text misrouting risk | **None** | **Yes** (bounded but real) | **None** |
| Recovery path in bot | No | Automatic | Explicit owner action |
| Data integrity / D-35 | Preserved | Preserved | Preserved; clearance must be separate from identity |
| UX | **Poor** — permanent lock | **Best** — automatic | **Medium** — one explicit action |
| Implementation complexity | Low | Medium | **High** (clearance state/command/tests) |
| Compatibility with current code | High | Medium (D-34 amendment) | Medium–high (new state, no Mini App edits) |
| Testability | High | High | High but larger matrix |
| Owner decision impact | Keeps old policy | Reverses old policy | Amends old policy narrowly |

**Why Option C is recommended:** `DEF-001` is CRITICAL and the owner is the only operator. Option A
does not actually solve the user-facing defect. Option B solves it but reintroduces the exact
ambiguity D-34 was approved to avoid. Option C preserves fail-closed behavior for ambiguous cases and
provides a controlled recovery path. The added complexity is justified by the data-integrity and
misrouting risk.

**Trade-offs of Option C:**

- The owner must perform an explicit action after a terminal batch.
- A durable clearance record must be designed without weakening D-35.
- `expired`/`rejected` versus `delivered`/`failed` clearance policy must be explicit.
- The clearance command must be idempotent, owner-scoped, and crash-safe.
- It does not automatically clear `intent_recorded`/`dispatching`/`uncertain`; those still need
  `/cancel` or manual reconciliation.

### 5.2 OD-03 comparison

| Criterion | Option A (`False`) | Option B (`True`) |
|---|---|---|
| Fresh-install `DEF-001` exposure | **Lower** — no new batches | **Higher** until WP-01 verified |
| `MT-2` zero-config | **Broken** — requires `=1` | **Preserved** |
| Consistency with `MINI_APP_ENABLED=False` | **High** | Low — stages files for an off Mini App |
| Consistency with blocked Stage B | **High** — local-only staging is opt-in | Lower — default staging without delivery |
| User/operator clarity | **Good** — explicit opt-in | Good only if docs explain local-only |
| Implementation complexity | Low | Low |
| Reversibility | High via `=1` | High via `=0` |
| Existing tests | Must update default assertions | No default change |

**Why Option A is recommended:** the current default stages documents even when the Mini App is off,
and Stage B cannot deliver them. Default-off is the safer operational baseline. `MT-2` remains
available through an explicit opt-in once WP-01 is implemented.

**Trade-off:** an operator who enables the Mini App but forgets `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1`
will see an empty `MT-2` attachment list. This must be documented prominently in README, Runbook,
ZERO_TOUCH, and the startup warning path.

---

## 6. Current implementation findings

1. **Kill switch is real and early.** `handle_attachment` checks the flag before `get_file`, download,
   staging rows, files, or OpenHands calls (`bot/handlers.py:2556-2568`). Existing tests encode this.
2. **Kill switch is not a cure for pre-existing batches.** `handle_text` always calls
   `_handle_accompanying_text` (`bot/handlers.py:2916`), and `classify_attachment_routing` is
   owner-wide (`bot/db.py:1493-1585`). Setting `=0` does not unblock an already affected owner.
3. **D-34 global block is active.** Any terminal batch for the owner yields `TERMINAL_UNPROVEN`
   when no identity match exists; both terminal states reject ordinary text.
4. **`/cancel` does not abandon batches.** Current `/cancel` clears awaiting state only
   (`bot/handlers.py:2982-3009`); it does not transition `pending`/`intent_recorded` batches to
   `rejected` or record terminal clearance.
5. **MT-2 is tightly coupled.** It only serves `pending` batches with `stored` items inside 15
   minutes (`bot/web/services.py:758-870`); intake off means empty MT-2.
6. **Copy is not policy-aware.** `UNSUPPORTED_ATTACHMENT_TEXT` still advertises document upload when
   intake is disabled (`bot/handlers.py:2254-2257`); `handle_unsupported_attachment` does not consult
   the flag (`bot/handlers.py:2663-2679`). This is `NEW-DEF-06`.
7. **No operator recovery surface.** There is no implemented command to clear a terminal batch or
   inspect attachment state; this is the core gap behind Option C.

---

## 7. Recommended option for each decision

### 7.1 OD-01 recommendation

**Select Option C.**

Exact recommended policy:

- Keep `TERMINAL_ASSOCIATED` fail-closed permanently.
- Keep `UNRESOLVED` (`intent_recorded`, `dispatching`, `uncertain`), `MULTI_LIVE`,
  `EXPIRED_PENDING`, `invalid_t0`, out-of-enum/NULL, and ambiguous ownership fail-closed.
- Keep passive terminal batches fail-closed until explicit owner clearance.
- Allow normal text only after a durable, owner-scoped, per-batch clearance for a verified terminal
  batch.
- Do not auto-clear on reaper expiry, timeout, duplicate delivery, or startup.
- Do not clear `attachment_message_identity`; D-35 remains binding.
- Recommended terminal subset: **`expired` and `rejected`** only. `delivered`/`failed` remain
  fail-closed pending Stage B/manual reconciliation; the owner may expand this later explicitly.
- No text/timestamp inference, no newest-batch selection, no conversation-context guessing.

### 7.2 OD-03 recommendation

**Select Option A.**

Exact recommended policy:

- `Config.attachment_document_intake_enabled` default becomes `False`.
- `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` in `.env.example` is documented as `0` by default, `1` to
  enable local staging for `MT-2`.
- `README.md`, `docs/OPERATIONS_RUNBOOK.md`, and `docs/ZERO_TOUCH_STARTUP.md` reflect the new default.
- `handle_attachment` keeps its existing early kill-switch behavior.
- `MT-2` remains available only when the operator sets `=1` and `MINI_APP_ENABLED=1`.
- No Mini App files, `Config.mini_app_*`, or `docs/MINI_APP.md` are modified.

---

## 8. Recommended combined outcome

**OD-01 Option C + OD-03 Option A.**

| Scenario | Combined behavior |
|---|---|
| Fresh install, Mini App off, intake unset | No document staging; no attachment batches; no `DEF-001` exposure. |
| Operator wants MT-2 | Set `MINI_APP_ENABLED=1`, `MINI_APP_URL`, and `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1`; local staging works. |
| Opted-in user uploads and sends text within 15m | Live single batch path records intent; no ordinary prompt fallback. |
| Batch expires unused | `EXPIRED_PENDING` blocks until reaper marks it `expired`; then terminal batch remains blocked until explicit clearance. |
| Owner cancels live batch | `/cancel` transitions batch to `rejected`/`reaped`/unlink; explicit clearance is recorded as part of the same owner action, so normal text can resume. |
| Owner has an already-terminal expired/rejected batch | A dedicated per-batch clearance command (or an explicitly approved equivalent) records clearance; normal text resumes. |
| `delivered`/`failed` batch | Remains fail-closed; manual/Stage B reconciliation only. |
| Corrupt/out-of-enum/ambiguous row | Remains fail-closed; manual reconciliation; no blanket deletion. |
| Reaper runs | Never auto-clears a terminal block; it only finalizes expired pending batches and reaps bytes. |

**Internal consistency:** default-off prevents new accidental batches; Option C ensures opted-in
users are not permanently bricked and are not silently misrouted. The pair preserves D-35, D-15,
Mini App exclusion, single-owner SQLite, and Stage B deferral.

---

## 9. Trade-offs and residual risks

1. **MT-2 opt-in surprise.** Default `False` means `MT-2` shows no staged files unless the operator
   sets `=1`. Mitigation: prominent docs and a startup/runtime warning when `MINI_APP_ENABLED=1` and
   intake is off.
2. **Explicit clearance friction.** Option C requires the owner to act after terminal batches.
   Mitigation: `/cancel` covers active batches; a clear, discoverable terminal-clearance command is
   required.
3. **Clearance persistence design.** A new column/table may be needed. It must not delete or weaken
   `attachment_message_identity`; D-35 applies. If schema changes, runbook/parity tests must update.
4. **Delivered/failed ambiguity.** Keeping them fail-closed avoids silently treating unknown remote
   outcomes as safe. Stage B remains blocked; no current producer exists.
5. **Existing batches.** Neither decision repairs pre-existing SQLite rows. WP-01 must still perform
   the pre-change read-only inventory and conservative state-by-state handling.
6. **Test environment gap.** This analysis could not run the attachment tests because the host lacks
   the project dependencies. The implementation task must run them in the declared environment.

---

## 10. Proposed implementation scope after approval

This section is a proposal only. It does not authorize implementation.

### 10.1 OD-03 implementation scope

- `bot/config.py:43`: default `False`.
- `bot/config.py:315-317`: `_parse_bool(..., default=False)`.
- `.env.example:2`: document `0` as default, `1` as opt-in.
- `README.md:92`, `docs/OPERATIONS_RUNBOOK.md:67`, `docs/ZERO_TOUCH_STARTUP.md:94`: update defaults
  and explain `MT-2` opt-in.
- `tests/test_repair_plan_02_life03_intake_kill_switch.py`:
  - default assertion becomes `False`;
  - explicit `=1` test covers staging;
  - disabled intake still proves no `get_file`/rows/files/outbox/OpenHands calls.
- No Mini App code or `docs/MINI_APP.md` changes.

### 10.2 OD-01 Option C implementation scope

- Add a durable, owner-scoped, per-batch terminal-clearance record. Recommended minimal design:
  a nullable `terminal_cleared_at` on `attachment_batches` (no new table count), subject to a
  separate schema review; do not delete rows or identity evidence.
- Update `classify_attachment_routing` / terminal query so only **uncleared** terminal batches
  block; `TERMINAL_ASSOCIATED` remains blocking regardless of clearance.
- Keep all unresolved, live, expired-pending, invalid, out-of-enum, and ambiguous states fail-closed.
- Add an explicit owner action for terminal clearance. Recommended: a dedicated per-batch command
  (e.g. `/attachments_clear <batch_id> confirm`) rather than an implicit owner-wide clear.
- Extend `/cancel` (`bot/handlers.py:2982-3009`) to abandon `pending`/`intent_recorded` batches
  DB-first, idempotently, crash-safely: batch -> `rejected`, item -> `reaped`, then unlink; preserve
  `attachment_message_identity`.
- Record clearance only for the specific batch; no auto-clear on reaper/startup.
- Make `UNSUPPORTED_ATTACHMENT_TEXT` and `ATTACHMENT_ACCEPTED_TEXT` policy-aware (`NEW-DEF-06`).
- Update `WP-08` docs/parity; no Mini App changes.
- Add tests listed in §12.

### 10.3 Explicitly not in scope

- No Stage B remote upload.
- No Mini App edits.
- No deletion of `attachment_batches` or `attachment_message_identity`.
- No automatic clearing of terminal batches.
- No automatic poison skipping.
- No exactly-once claim.
- No change to D-35 or D-15 semantics.
- No cleanup of pre-existing batches without inventory and explicit authorization.

---

## 11. Explicit exclusions and protected behavior

- `bot/web/*`, `bot/web/static/*`, `tests/test_miniapp_*.py`,
  `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`, and
  `Config.mini_app_*` remain untouched.
- AI Studio scaffold files remain untouched.
- `attachment_message_identity` remains `ON DELETE RESTRICT` and is never pruned by this work.
- `processed_updates` pruning remains independent of identity evidence (D-35).
- `outbox`/`creation_jobs` `OUTBOX_UNKNOWN`/`CREATION_UNKNOWN`/`PARTIAL_OR_UNKNOWN` semantics remain
  fail-closed.
- No owner decision is recorded by this package.

---

## 12. Acceptance criteria and required tests

### 12.1 OD-03 acceptance criteria

1. `load_config()` with no `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` yields `False`.
2. Explicit `=1` yields `True`; explicit `=0` yields `False`; invalid values raise `ConfigError`
   without leaking the value.
3. Disabled intake creates no batch/item/identity rows, no staging files, no outbox rows, no
   `get_file` call, and no OpenHands call.
4. Enabled intake still stages a supported document and returns the accepted copy.
5. README/Runbook/ZERO_TOUCH document `0` default and `1` opt-in; no env-count drift.
6. No Mini App file changes.

### 12.2 OD-01 Option C acceptance criteria

1. Terminal batch with no clearance and no identity match -> `TERMINAL_UNPROVEN` -> rejected; no
   outbox/remote call.
2. Terminal batch with identity match -> `TERMINAL_ASSOCIATED` -> rejected even if a clearance
   exists.
3. Terminal batch with valid per-batch clearance -> normal text proceeds only after independent
   route/ownership/tombstone checks.
4. Clearance is owner-scoped and batch-scoped; a clearance for one batch does not clear another.
5. Clearance is idempotent; repeated delivery does not duplicate effects or reset state.
6. Reaper expiry does not clear the terminal block; no silent unblocking.
7. `intent_recorded`/`dispatching`/`uncertain` remain fail-closed even after a terminal clearance.
8. `MULTI_LIVE`, `EXPIRED_PENDING`, `invalid_t0`, out-of-enum/NULL, and ambiguous ownership remain
   fail-closed.
9. `/cancel` for a live `pending`/`intent_recorded` batch is DB-first, crash-recoverable, and
   preserves `attachment_message_identity`.
10. `UNSUPPORTED_ATTACHMENT_TEXT` never advertises document intake when disabled; accepted copy
    clearly says local-only when enabled.
11. No Mini App changes; D-35 FK integrity holds.
12. Full WP-01 regression suite and a multi-turn E2E test pass in the declared environment.

---

## 13. Owner approval section

> **The owner must explicitly select options. Silence is not approval. This section is intentionally
> unchecked.**

### OD-01

- [ ] **Option A** — Preserve `D-34` `TERMINAL_UNPROVEN` global fail-closed behavior; `/cancel` does
  not unblock future text; manual reconciliation required.
- [ ] **Option B** — Amend `D-34` to permit verified terminal pass-through under the five conditions
  in §4.1; `TERMINAL_ASSOCIATED` remains fail-closed.
- [ ] **Option C (recommended)** — Hybrid explicit terminal clearance; passive terminal/uncertain
  states remain fail-closed; owner must explicitly clear a verified terminal batch.

If Option C: which terminal statuses may be cleared?

- [ ] `expired` and `rejected` only (recommended)
- [ ] all four terminal statuses (`expired`, `rejected`, `delivered`, `failed`)
- [ ] other: ______________________________

### OD-03

- [ ] **Option A (recommended)** — Default `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=False`; `MT-2` requires
  explicit `=1`.
- [ ] **Option B** — Keep default `True`; rely on WP-01 + OD-01 mitigation.

### Combined approval

- [ ] Approve **OD-01 Option C + OD-03 Option A** (recommended pair).
- [ ] Approve OD-01 Option C + OD-03 Option B.
- [ ] Approve OD-01 Option B + OD-03 Option A.
- [ ] Approve another combination: ______________________________

### Required confirmations

- [ ] I authorize a **separate implementation task** for WP-01 after this decision; this package
  itself does not implement anything.
- [ ] I authorize the pre-change read-only inventory of existing `attachment_batches`,
  `attachment_items`, and staging files before any cleanup.
- [ ] I confirm no Mini App files or `docs/MINI_APP.md` may be modified.
- [ ] I confirm D-35 identity evidence must be preserved and never pruned by this work.
- [ ] I confirm no automatic terminal clearing or poison skipping is authorized.
- [ ] I understand that any unlinked staging bytes are irreversible without an external backup.

**Owner signature / date:** ______________________________

---

## 14. Evidence and limitations

- This package is based on current source inspection at the baseline `HEAD` above, not on a fresh
  behavioral test run. The host lacks project test dependencies; attachment-focused tests were not
  run.
- Historical reports were treated as historical. Current code was checked directly for the kill
  switch, global terminal query, handler ordering, `MT-2` pending-only behavior, and copy.
- The exact terminal-clearance persistence mechanism and command name are implementation design
  choices, not owner decisions; they require a separate implementation task after approval.
- No production calls, credentials, Git fetch/pull, staging, commit, push, PR, merge, deployment, or
  Autopush occurred.
