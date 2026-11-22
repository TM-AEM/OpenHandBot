# OHB2 — WP-07 NAV Owner Decision Package (D-A′)

**Task ID:** `OHB2-WP07-NAV-OWNER-DECISION-PACKAGE`
**Date:** 2026-11-21 (prepared); decision recorded 2026-11-22
**Status:** `DECIDED — OPTION A`
**Owner decision recorded:** **YES — 2026-11-22**
**Mode:** documentation and acceptance-record update only; no implementation, test, configuration, staging, commit, push, PR, merge, deployment, or Autopush change.

## 1. Executive summary

The independent review `REV-IND-01-WP-07` found that NAV-01 through NAV-06 are implemented and
covered by passing tests, but remain **unaccepted by the owner**. The review’s overall verdict was
`BLOCKED` for that reason.

The prior owner acceptance (`NEW-DEF-03_NON_CONCURRENCY_OWNER_ACCEPTED`) covers exactly **A-1 through
A-5**. It does **not** cover the six navigation handlers. The final stabilization audit and the S3
acceptance reconciliation both require a separate owner decision, `D-A′`, for NAV.

This package was prepared before the decision. On **2026-11-22**, the project owner explicitly selected
**Option A — Accept all six NAV items as currently implemented**. The decision is recorded in §8 and in
`.agent/PROGRESS.md`; this package does not authorize any new implementation.

## 2. Repository and publication-state verification

### 2.1 Current repository state

| Item | Value |
|---|---|
| Repository path | `/workspace/project/OpenHandBot` |
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| `origin/main` local ref | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| `origin/main` tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| `origin/main` freshness | Local ref only; **no fetch or pull was performed** |
| `30dfa0d` ancestor of `main`? | **YES** (`git merge-base --is-ancestor`) |
| NAV markers in `HEAD:bot/handlers.py` | **YES** — lines 926, 987, 1104, 1129, 1228, 1416, 3091 |
| Candidate state | Committed in `main`; not merely a branch or working-tree diff |

The current uncommitted changes in the implementation workspace are unrelated pre-existing
concurrency work:

```text
 M bot/app.py
 M tests/test_u04_concurrency.py
```

They are outside this NAV decision package and were not modified.

### 2.2 WP-07 candidate commit

| Item | Value |
|---|---|
| Candidate commit | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` |
| Parent/baseline | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Commit date | 2026-11-21T09:40:48Z |
| Commit subject | `feat: sync complete OHB2 WP-05/WP-06/WP-07 remediation work to main` |
| Relationship to current `main` | Ancestor; included in `0774c9c` |

The NAV implementation is therefore present in current `main`, not only in another branch, a
candidate commit, or the working tree.

**Reviewed-candidate delta:** comparing the six NAV function bodies between `30dfa0d` and current
`HEAD`, `start`, `show_menu`, `list_conversations`, `list_watches`, and `start_new_chat` are identical.
`open_conversation` differs by one added `files_cb=_files_open_cb(...)` keyboard callback from the
unrelated REV-01/file-browser work; its NAV atomic state/outcome logic is unchanged. The WP-07 NAV
test files are unchanged, and current NAV-focused tests pass 51/51.

### 2.3 Independent review report

| Item | Value |
|---|---|
| Path | `docs/reviews/REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md` |
| Size | 22,098 bytes |
| SHA-256 | `11f7ff10e59cd964edd1d8007b83eca43f4cd1d30358285d20d7cc136a33da92` |
| Expected hash | `11f7ff10e59cd964edd1d8007b83eca43f4cd1d30358285d20d7cc136a33da92` |
| Hash match | **YES** |
| Review verdict | `BLOCKED` overall; NAV items `BLOCKED` for acceptance |

## 3. What the owner already accepted: A-1..A-5

Source: `.agent/PROGRESS.md:4277` — `NEW-DEF-03_NON_CONCURRENCY_OWNER_ACCEPTED`.

The accepted scope is exactly:

1. `watch_conversation` atomicity: watch row + `last_state` + durable outcome in one SQLite transaction.
2. `unwatch_conversation` atomicity, both hint and normal branches: removal + pending-delivery reconciliation + outcome in one transaction.
3. Awaiting-state atomicity: `clear_awaiting_and_record_outcome` and `set_awaiting_and_record_outcome`.
4. Backward compatibility for legacy callers: optional keyword-only arguments; single-argument remover preserved.
5. Preservation of F-1 Option C behavior in the six reply/routing paths.

The same record states that this is **not** `WP-07_COMPLETE` and **not** `NEW-DEF-03_COMPLETE`.

## 4. Historical basis for D-A′: NAV-01..06 were unaccepted before 2026-11-22

The owner record explicitly said at `.agent/PROGRESS.md:4441`:

> `NAV-01..06` = **نطاق فرعي من NEW-DEF-03**، مش بنود register مستقلة، و**غير مقبولة**.

**Current status (2026-11-22):** NAV-01..06 have been explicitly accepted under `D-A′` **Option A**.
This section is preserved as the pre-decision evidence; the current decision is recorded in §10 and
in `.agent/PROGRESS.md` (`OHB2-WP07-NAV-OWNER-ACCEPTANCE-RECORD`).

Supporting evidence:

- `docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md:180-185` marks NAV-01..06 as not in the
  accepted five items.
- `docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md:205-209` says the working tree contains more
  NEW-DEF-03 work than the accepted five items and that the additional NAV work is unaccepted.
- `docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md:33,78` marks NAV as
  `REQUIRES_SEPARATE_OWNER_DECISION` and says the S3 delivery excludes NAV.
- `docs/reviews/REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md` (`REV-NAV-ACC-01`) records the same
  blocking gap.

Therefore `D-A′` was required because the prior acceptance was deliberately bounded to A-1..A-5.
Passing NAV tests did not extend that acceptance; only the explicit owner decision of 2026-11-22 did.

## 5. Individual NAV evidence

The current `HEAD` NAV-focused tests were re-run in a clean clone:

```sh
pytest -q \
  tests/test_wp07_nav01_nav03_nav04_atomic.py \
  tests/test_wp07_nav02_nav05_simple_clear_atomic.py \
  tests/test_wp07_nav06_open_conversation_atomic.py
```

Result: **51 passed in 2.54s**, exit 0.

The independent review also recorded:

- WP-07 focused suite: **100 passed**.
- Relevant integration/regression suite: **395 passed**.
- Full Python suite: **3450 passed**.
- Node suite: **280 passed / 0 failed**.
- No known code-correctness defect in the NAV target code.

These are test and review facts, **not** owner acceptance.

### 5.1 NAV-01 — `start`

| Field | Evidence |
|---|---|
| Handler | `handlers.start` — `bot/handlers.py:918`; NAV marker at `:926` |
| Original problem | Clear awaiting state and record the outcome in separate commits; a failure between them could clear state without an outcome |
| Intended behavior | Send welcome first; then clear awaiting state + record `explicitly_ignored` atomically; a send failure must leave state untouched |
| Actual behavior | `reply_text` first, then `db.clear_awaiting_and_record_outcome(...)`; send failure raises before the DB call; outcome-write failure rolls back the clear |
| Tests | `test_start_clears_state_and_records_outcome_atomically`, `test_start_rollback_leaves_state_and_outcome_untouched`, `test_start_send_failure_does_not_qualify_update`, `test_start_update_id_none_clears_without_outcome`, `test_start_unauthorized_clears_nothing`; repeated-delivery case in the shared file |
| Independent review | Technical implementation verified; acceptance `BLOCKED` |
| Known limitations / gaps | No known code defect. Send failure is covered. No separate NAV-01-specific display-failure test beyond the send-failure test |
| Reason acceptance may be withheld | Owner acceptance missing; any owner concern about display failure or scope can justify withholding |

### 5.2 NAV-02 — `show_menu`

| Field | Evidence |
|---|---|
| Handler | `handlers.show_menu` — `bot/handlers.py:977`; NAV marker at `:987` |
| Original problem | Clear state and record outcome separately; a failure between them could leave state cleared without an outcome |
| Intended behavior | Display menu, then clear state + record `explicitly_ignored` atomically |
| Actual behavior | `_safe_edit_noop(...)` then `db.clear_awaiting_and_record_outcome(...)` |
| Tests | `test_show_menu_clears_state_and_records_outcome_atomically`, `test_show_menu_rollback_leaves_state_and_outcome_untouched`, `test_show_menu_update_id_none_clears_without_outcome`, `test_show_menu_display_failure_still_records_ignored`, `test_show_menu_unexpected_exception_leaves_state_untouched`, `test_show_menu_unauthorized_touches_nothing`; repeated-delivery case |
| Independent review | Technical implementation verified; acceptance `BLOCKED` |
| Known limitations / gaps | `_safe_edit_noop` catches all `TelegramError`/`TimeoutError` and returns False; a real display failure is then recorded as `explicitly_ignored`, not as durable failure evidence. This is existing WP-02 policy and is explicitly tested (`REV-NAV02-01`) |
| Reason acceptance may be withheld | Owner acceptance missing; owner may require fail-closed display semantics or explicitly accept the WP-02 no-op policy |

### 5.3 NAV-03 — `list_conversations`

| Field | Evidence |
|---|---|
| Handler | `handlers.list_conversations` — `bot/handlers.py:1077`; NAV markers at `:1104` and `:1129` |
| Original problem | Clear/outcome were separate across five exits; operational failure after a premature clear could be acknowledged as success |
| Intended behavior | Success/empty/expected 4xx: clear + `explicitly_ignored` atomically; operational failure: raise before clear; DB filter failure: clear + failure outcome atomically |
| Actual behavior | Five exits are handled as above; `_safe_edit` raises on display failure before clear; DB filter failure records `_classify_failure(exc)` |
| Tests | `test_nav03_exit_success_display`, `test_nav03_exit_empty_list`, `test_nav03_exit_expected_4xx_rejection`, `test_nav03_exit_operational_failure_never_qualifies` (500/503/429/None), `test_nav03_exit_db_filter_failure_records_failure_not_ignored`, `test_nav03_rollback_leaves_state_untouched`, `test_nav03_update_id_none_clears_without_outcome`, `test_nav03_unauthorized_clears_nothing`; repeated-delivery case |
| Independent review | Technical implementation verified; acceptance `BLOCKED` |
| Known limitations / gaps | No explicit Telegram display-failure test on the success path (`REV-NAV-TEST-01`); current `_safe_edit` raises before clear, so behavior is fail-closed |
| Reason acceptance may be withheld | Owner acceptance missing; owner may require the missing display-failure test |

### 5.4 NAV-04 — `list_watches`

| Field | Evidence |
|---|---|
| Handler | `handlers.list_watches` — `bot/handlers.py:1405`; NAV marker at `:1416` |
| Original problem | Clear/outcome were separate; a DB read or display failure could clear state prematurely |
| Intended behavior | Read watch list first; display; then clear + `explicitly_ignored` atomically; DB read failure leaves state untouched |
| Actual behavior | `db.list_watched()` first, `_safe_edit` next, then atomic clear/outcome on both empty and non-empty branches |
| Tests | `test_list_watches_empty_clears_and_records_atomically`, `test_list_watches_items_clears_and_records_atomically`, `test_list_watches_rollback_leaves_state_untouched`, `test_list_watches_db_read_failure_does_not_clear_state`, `test_list_watches_update_id_none_clears_without_outcome`; repeated-delivery case |
| Independent review | Technical implementation verified; acceptance `BLOCKED` |
| Known limitations / gaps | No explicit Telegram display-failure test on the success path (`REV-NAV-TEST-01`); `_safe_edit` currently raises before clear |
| Reason acceptance may be withheld | Owner acceptance missing; owner may require the missing display-failure test |

### 5.5 NAV-05 — `start_new_chat`

| Field | Evidence |
|---|---|
| Handler | `handlers.start_new_chat` — `bot/handlers.py:3083`; NAV marker at `:3091` |
| Original problem | Clear/outcome were separate; an operational API failure could be recorded as an acknowledged success |
| Intended behavior | Run `_show_repos` first; operational failure raises before any write; success or expected 4xx then clears + records `explicitly_ignored` atomically |
| Actual behavior | `_show_repos(...)` then `db.clear_awaiting_and_record_outcome(...)`; operational failure propagates before clear |
| Tests | `test_start_new_chat_clears_state_and_records_outcome_atomically`, `test_start_new_chat_rollback_leaves_state_and_outcome_untouched`, `test_start_new_chat_update_id_none_clears_without_outcome`, `test_operational_failure_does_not_record_ack_eligible`, `test_start_new_chat_unauthorized_touches_nothing`; repeated-delivery case |
| Independent review | Technical implementation verified; acceptance `BLOCKED` |
| Known limitations / gaps | No explicit Telegram display-failure test on the success path (`REV-NAV-TEST-01`); operational API failure is covered |
| Reason acceptance may be withheld | Owner acceptance missing; owner may require the missing display-failure test |

### 5.6 NAV-06 — `open_conversation`

| Field | Evidence |
|---|---|
| Handler | `handlers.open_conversation` — `bot/handlers.py:1171`; NAV marker at `:1228` |
| Original problem | Route activation and outcome were separate; a failure between them could activate a 10-minute route without a durable outcome |
| Intended behavior | Display conversation first; only after successful display, set awaiting route + record `explicitly_ignored` atomically; display failure must activate nothing and record a transient failure |
| Actual behavior | `_edit_or_send` result is checked; success calls `db.set_awaiting_and_record_outcome(...)`; failure calls `mark_display_failed(...)` |
| Tests | `test_display_success_commits_state_and_outcome_together`, `test_title_and_ttl_semantics_preserved`, `test_empty_title_still_stored_as_empty_string`, `test_failure_cannot_leave_awaiting_without_outcome`, `test_handler_rolls_back_on_outcome_write_failure`, `test_previous_route_survives_failed_transaction`, `test_update_id_none_activates_route_without_outcome`, `test_display_failure_activates_nothing_and_records_transient`, `test_telegram_display_text_unchanged`, `test_repeated_delivery_keeps_outcome_and_state_consistent`, `test_helper_rolls_back_activation_when_outcome_write_fails`, `test_helper_without_update_id_activates_only` |
| Independent review | Technical implementation verified; acceptance `BLOCKED` |
| Known limitations / gaps | No known code-correctness defect; display failure and rollback are covered |
| Reason acceptance may be withheld | Owner acceptance missing; no technical blocker identified |

## 6. Known limitations, test gaps, and documentation inconsistencies

1. **Owner acceptance missing for all NAV items** — the primary and blocking gap.
2. **NAV-03/04/05 display-failure test gap** — the current code appears fail-closed, but there is no
   explicit test that a Telegram display failure leaves state untouched (`REV-NAV-TEST-01`).
3. **NAV-02 display-failure policy** — `_safe_edit_noop` treats all Telegram/Timeout failures as a
   no-op and the handler records `explicitly_ignored`; this preserves WP-02 behavior but is a bounded
   limitation (`REV-NAV02-01`).
4. **Broad sync commit** — `30dfa0d` also contains WP-05/WP-06/DEF-011-B and documentation changes;
   WP-07 NAV is not isolated in a dedicated commit (`REV-SCOPE-01`).
5. **Stale historical documentation** — `OHB2-WP07-FINAL-STABILIZATION-AUDIT.md:165,180-185,262-266`
   says NAV is not in HEAD/uncommitted; current `main` includes NAV. The historical audit was accurate
   at `52e7789`; current Git history is authoritative (`REV-DOC-01`).
6. **No owner decision exists** — no acceptance, rejection, or deferral is recorded for NAV.

## 7. Decision options

The owner must choose one overall route, and may record a separate outcome for each NAV item. The
agent does **not** select any option below.

### Option A — Accept all six NAV items as currently implemented

- **Meaning:** D-A′ accepts NAV-01..06 on the current code and test evidence.
- **Current implementation:** remains in place; no code change required.
- **Further implementation/testing:** none required for acceptance; optional remediation of the
  NAV-03/04/05 display-failure tests and a decision on the NAV-02 no-op policy are recommended.
- **Records to update after the owner decides:** a new owner decision entry in `.agent/PROGRESS.md`;
  a decision record under `docs/audits/` if the owner requires one; this package’s decision fields.
- **WP-07 effect:** NAV sub-scope becomes accepted, but WP-07 remains open for DEF-006/DEF-011 and
  other open items.

### Option B — Accept selected NAV items individually

- **Meaning:** the owner names exactly which of NAV-01..06 are accepted; the others remain open.
- **Current implementation:** accepted items remain; unaccepted items remain in place but not accepted.
- **Further implementation/testing:** depends on the selected items. For any selected item, the owner
  should confirm the evidence in §5. For NAV-02, explicitly confirm the no-op display policy. For
  NAV-03/04/05, the owner may require the missing display-failure tests before acceptance.
- **Records to update after the owner decides:** one per-item decision entry, not a blanket NAV
  acceptance; update `.agent/PROGRESS.md` and any decision register with the exact accepted IDs.
- **WP-07 effect:** only the named subset is accepted; WP-07 remains open.

### Option C — Reject specified NAV items and require corrections/tests

- **Meaning:** the owner rejects named items and defines the required correction or additional
  evidence.
- **Current implementation:** remains in place until a separate authorized correction task; the agent
  must not revert or modify it under this package.
- **Further implementation/testing:** required for the rejected items. Candidate requirements:
  - NAV-01: add/confirm a display-failure test if that is the rejection reason; send-failure is
    already covered.
  - NAV-02: decide whether to replace the no-op policy with fail-closed display behavior; add tests.
  - NAV-03: add an explicit Telegram display-failure test and verify state/outcome remain untouched.
  - NAV-04: add an explicit Telegram display-failure test and verify state/outcome remain untouched.
  - NAV-05: add an explicit Telegram display-failure test and verify state/outcome remain untouched.
  - NAV-06: define the exact defect; no known code-correctness defect is currently identified.
- **Records to update after the owner decides:** record rejection and required correction per item;
  no acceptance record for rejected items.
- **WP-07 effect:** rejected items remain open/blocked; WP-07 remains open.

### Option D — Defer all or selected NAV items

- **Meaning:** the owner keeps all or named items open and records the reason.
- **Current implementation:** remains in place but unaccepted; no new implementation work is
  authorized by this package.
- **Further implementation/testing:** none unless the owner later authorizes it.
- **Records to update after the owner decides:** record `DEFERRED` per item and the reason; keep the
  prior A-1..A-5 acceptance unchanged.
- **WP-07 effect:** NAV remains unaccepted; WP-07 remains blocked on this sub-scope until a later
  decision.

## 8. Exact owner decision fields

### 8.1 Overall D-A′ route

Complete exactly one:

- [x] **Option A — Accept all six**
- [ ] **Option B — Accept selected items**
- [ ] **Option C — Reject specified items**
- [ ] **Option D — Defer all or selected items**

Owner: Project owner — explicit authorization in task `OHB2-WP07-NAV-OWNER-ACCEPTANCE-RECORD-UPDATE` (no separate signature supplied)
Date: 2026-11-22
Rationale: Accept all six NAV items as currently implemented; no new implementation, refactoring, or unrelated cleanup.

### 8.2 Per-item decisions

For each item, select exactly one outcome and record conditions:

| Item | Handler | ACCEPT | ACCEPT_WITH_CONDITIONS | REJECT | DEFER | Conditions / reason | Owner initials | Date |
|---|---|---|---|---|---|---|---|---|
| NAV-01 | `start` | [x] | [ ] | [ ] | [ ] | Option A; reviewed implementation | — | 2026-11-22 |
| NAV-02 | `show_menu` | [x] | [ ] | [ ] | [ ] | Option A; reviewed implementation; WP-02 no-op display policy noted | — | 2026-11-22 |
| NAV-03 | `list_conversations` | [x] | [ ] | [ ] | [ ] | Option A; reviewed implementation; display-failure test gap noted | — | 2026-11-22 |
| NAV-04 | `list_watches` | [x] | [ ] | [ ] | [ ] | Option A; reviewed implementation; display-failure test gap noted | — | 2026-11-22 |
| NAV-05 | `start_new_chat` | [x] | [ ] | [ ] | [ ] | Option A; reviewed implementation; display-failure test gap noted | — | 2026-11-22 |
| NAV-06 | `open_conversation` | [x] | [ ] | [ ] | [ ] | Option A; reviewed implementation | — | 2026-11-22 |

### 8.3 Recorded decision fields

The recorded decision includes:

- Decision ID: `D-A′`
- Selected overall route: **Option A — Accept all six**
- Exact accepted NAV IDs: **NAV-01, NAV-02, NAV-03, NAV-04, NAV-05, NAV-06**
- Conditions: none beyond the documented limitations
- Owner identity and date: project owner — explicit authorization in this task; 2026-11-22
- Evidence reviewed: this package, `REV-IND-01`, current NAV-focused tests, historical A-1..A-5 record
- Required follow-up tests or code changes: none required for acceptance; optional display-failure tests
- WP-07 / NEW-DEF-03 status: **WP-07 remains open; NEW-DEF-03 remains partial; neither is complete**
- Record paths updated: this package; `.agent/PROGRESS.md`; S3 reconciliation §10; final-audit post-decision note

The fields above are filled only from the explicit owner authorization in this task. No signature,
personal identity, or approval metadata beyond that authorization was invented. **The owner decision is
now recorded as Option A on 2026-11-22.**

## 9. Consequences of each decision

| Decision | WP-07 effect | Current implementation | Further work | Records |
|---|---|---|---|---|
| A — Accept all | NAV sub-scope accepted; WP-07 still open | Stays as-is | Optional test/policy follow-ups | New NAV acceptance record; no WP-07 completion claim |
| B — Accept selected | Named subset accepted; others open | Stays as-is | Per selected/unselected item | Per-item acceptance/open records |
| C — Reject specified | Named items open/blocked; WP-07 open | Stays until authorized correction | Required corrections/tests for rejected items | Rejection and correction record |
| D — Defer | NAV remains unaccepted; WP-07 blocked on NAV | Stays as-is | None unless later authorized | Deferral record with reason |

## 10. Owner decision statement

**Owner decision recorded:** Option A — Accept all six NAV items as currently implemented.
**Decision date:** 2026-11-22.
**Scope:** NAV-01..06 only; the reviewed implementation; no new implementation or refactoring.
**Evidence:** `REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md` (SHA-256 `11f7ff10...`), this package,
the current NAV-focused tests, and the historical A-1..A-5 acceptance record.

This decision does not close WP-07, NEW-DEF-03 durable-intent paths, DEF-006/poller concurrency, or
DEF-011. The prior A-1..A-5 acceptance is unchanged. The historical pre-decision state of this package
was `DECISION_PENDING`; the recorded decision supersedes it for current status.

## Appendix A — Verification commands used

Read-only repository checks:

```sh
git branch --show-current
git rev-parse HEAD
git rev-parse HEAD^{tree}
git rev-parse origin/main
git merge-base --is-ancestor 30dfa0d6432cdb8f7787edde38f48fb482b6ced6 main
git grep -n 'NAV-0[1-6]' HEAD -- bot/handlers.py
sha256sum docs/reviews/REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md
```

NAV-focused tests in the clean review clone:

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pytest -q \
  tests/test_wp07_nav01_nav03_nav04_atomic.py \
  tests/test_wp07_nav02_nav05_simple_clear_atomic.py \
  tests/test_wp07_nav06_open_conversation_atomic.py
```

Result: **51 passed in 2.54s**, exit 0.

No fetch, pull, switch, reset, clean, stage, commit, push, merge, PR, deployment, or Autopush action
was performed. No production Telegram or OpenHands call was made.
