# OHB2 — WP-05 Owner Acceptance Record

**Decision ID:** `OD-WP05-ACCEPT-01`
**Decision:** **`ACCEPT_WITH_NOTES`**
**Date:** 2026-11-19
**Decided by:** Project owner
**Recorded by:** AI agent (OpenHands) on behalf of the owner
**Baseline commit:** `52e7789cc8cc97a7f7c09c9592226ab117db99a2`

> This record documents an **owner governance decision**. It is not a technical review, not an
> independent verification, and not a claim that WP-05 was independently reviewed.

---

## 1. Decision

**`ACCEPT_WITH_NOTES`** — WP-05 is accepted for the five findings listed in §2, with the explicit
reservations in §4 and subject to the conditions in §5.

---

## 2. Accepted scope — exactly five findings

| # | Finding | Description | Baseline severity |
|---|---|---|---|
| 1 | `DEF-007` | Missing `continue` / `return` after `clear_retry_not_before` failure (`Watcher.tick`, `Notifier._process`) | MEDIUM |
| 2 | `DEF-008` | `deliver_outbox(outbox_id)` ignored its target `outbox_id` and `mature_before` | MEDIUM |
| 3 | `DEF-012` | `wait_for_start` branches missing non-`ApiError` and resumed `CancelledError` fallbacks | MEDIUM |
| 4 | `NEW-DEF-02` | Production conversation creation never invalidated `list_cache` | MEDIUM |
| 5 | `NEW-DEF-05` | `collect_conversations` lacked a repeated-cursor (`seen_pages`) guard | LOW |

**Acceptance applies ONLY to these five findings.** It does **not** extend to:

- any other defect in the remediation baseline,
- `WP-06` (status normalization / `callback_refs`),
- `WP-07` (watch/unwatch atomicity — currently uncommitted in the working tree),
- `WP-01`–`WP-04`, `WP-09`, `WP-10`, or any owner-decision-blocked item.

---

## 3. Basis of the decision

The owner relied on the following, **as reported rather than independently reproduced**:

1. **The implementation report** — `docs/reviews/OHB2-WP05-COMPLETE-REMEDIATION-REPORT.md`
   (an **unttracked** working-tree artifact, not part of commit `52e7789`).
2. **Available regression evidence** — 18 focused WP-05 tests passing, and a full suite reported at
   **3383 passed / 0 failed**.
3. **Reported 8/8 mutation checks** — M1, M2, M3, M4a, M4b, M4c, M5, M6 all reported killed.
4. **Verified clean review snapshot and artifact integrity** — independently re-verified during the
   review attempts and the handoff tasks:
   - archive SHA-256 `be9e42a8ab033eb63ee802f2d6b69ab8522c8bbaa35fa707c014e6f2c594ccc3`
   - **357 / 357** manifest entries OK
   - **0 mismatches / 0 missing** against `git show 52e7789:<path>`
   - WP-07 working-tree content proven absent.

---

## 4. Explicit reservation — unchanged and binding

These reservations are part of the decision and must travel with any citation of it:

| # | Reservation |
|---|---|
| R1 | **Independent technical review was NOT completed.** No independent reviewer session or host was ever available. |
| R2 | **The verdict `INDEPENDENCE_NOT_ESTABLISHED` remains unchanged** and is not superseded by this acceptance. |
| R3 | **Implementation test results were NOT independently reproduced.** The 3383-passed figure is the implementer's self-report. |
| R4 | **Mutation results were NOT independently reproduced.** The 8/8 kill rate is the implementer's self-report. |
| R5 | The **17-table** schema claim and other compatibility assertions were **not independently verified**. |

**Consequence of R1–R5:** this is acceptance **by owner risk decision**, not acceptance on the strength of
independent evidence. The implementation agent authored both the code and its verification, so that
verification carries no independent evidential weight.

---

## 5. Conditions of acceptance

1. **Preserve the independent-review handoff package.**
   `/workspace/review-packages/OHB2-WP05-INDEPENDENT-REVIEW-HANDOFF-20261119/` must not be deleted,
   altered, or overwritten. It is the input for any future independent review.

2. **Do not describe WP-05 as independently reviewed.**
   In any document, report, commit message, or external communication, WP-05 must be described as
   **owner-accepted with reservations**, never as independently reviewed, independently verified, or
   independently passed.

3. **Reopen WP-05 if a later independent review discovers a material defect.**
   Acceptance is conditional on no material defect being found. If one is found, this acceptance is
   automatically void for the affected finding(s) and WP-05 must be reopened.

4. **This acceptance authorises no version-control or deployment action.**
   No commit, push, PR, merge, deployment, release, or Autopush activation is authorised by it.

---

## 6. Resulting project state

| Dimension | State |
|---|---|
| WP-05 implementation | Complete (self-reported) |
| WP-05 self-verification | Complete (self-reported) |
| Clean review snapshot | Verified — `52e7789`, 357/357 |
| Independent technical review | **NOT COMPLETED** |
| Independent PASS / FAIL | **NONE ISSUED** |
| **WP-05 owner acceptance** | **ACCEPTED WITH NOTES** (this record) |
| Formal closure / archiving | Not implied by this record |

---

## 7. What this record does NOT do

- It does **not** convert the self-verification into independent evidence.
- It does **not** close WP-05 as independently validated.
- It does **not** authorise any Git publication or deployment action.
- It does **not** extend acceptance beyond the five findings in §2.

---

## 8. Recommended next step

Commission a genuinely independent review using the preserved handoff package, when a separate reviewer
session and host become available (funded Cloud sandbox, external machine, or approved third-party
reviewer). If it finds a material defect, reopen WP-05 under condition 3.
