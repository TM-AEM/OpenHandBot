# OHB2 — WP-07 / DEF-011 / F-02 — Owner Review Evidence Audit Report

**Task:** `OHB2-WP07-DEF011-F02-OWNER-REVIEW-EVIDENCE-AUDIT`
**Date:** 2026-11-21
**Type:** evidence audit + owner-decision preparation. No source, test, workflow, branch, PR or
repository setting was modified.

---

## Verdict

# `F02_OWNER_BRIEFING_READY`

The evidence package holds up under independent re-verification. Every headline number was reproduced
from the actual GitHub run and from the candidate commit itself. No implementation defect was
confirmed. Several limitations are real and are stated plainly. The owner briefing is ready and
contains no recommendation and no pre-selected outcome.

---

## 1. Refs and hashes inspected

All re-verified against GitHub at audit time — not inherited from prior reports.

| Ref | Value | Verified |
|---|---|---|
| `refs/pull/8/head` | `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` | **unchanged**, still the candidate |
| `refs/pull/9/head` | `1a84cad1841f6b92725c623fca3b35de7ef156e5` | unchanged |
| `main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` | unchanged |
| `9d9dc51` | `9d9dc51a1f293bb803977292e91c926c03aa146b` | exists, ancestor of `pr9` |
| PR #8 | OPEN, `mergedAt=null`, 0 reviews, 3 files | verified |
| PR #9 | OPEN, `mergedAt=null`, 1 file (`.github/workflows/f02-review.yml`) | verified |
| PR #9 adds only the workflow on top of `6a1ca2e` | `git diff --name-only 6a1ca2e pr9` → 1 path | verified |

### File hashes — recomputed by me from the commit

| Path | SHA-256 | Matches artifact |
|---|---|---|
| `bot/attachments.py` | `b98d561f…818356` | **YES** |
| `bot/handlers.py` | `82d9c4b8…d57525` | **YES** |
| `bot/db.py` (unchanged) | `472fa573…343314` | **YES** |
| `tests/test_def011_fs_offload.py` | `3d3b3a2a…f503ea` | **YES** |
| `full.diff` | `cb3da6526d536dddf1eca23ba1d8b94a01b86aaf360507838d0eb10c81b02ab0` | **YES** |

`full.diff` was independently reproduced: my own `git diff 52e7789 6a1ca2e` hashed to `cb3da652…`,
identical to the artifact.

---

## 2. Evidence verified directly

| Claim in the package | Verified how | Result |
|---|---|---|
| Run `44881727141` tested `6a1ca2e` | run log `expected=6a1ca2e…` **and** `actual  =6a1ca2e…`, `parent=f37a3f5…`; artifact `review-target-sha.txt` | **CONFIRMED** |
| Hosted runner | log: `Runner Image Provisioner`, `Hosted Compute Agent`, `Image: ubuntu-26.04`, `image_version=20261116.202.1`, `kernel=Linux 7.0.0-1020-azure` | **CONFIRMED** |
| py3.11 / py3.13 results | artifact `python-version.txt` → `3.11.18` / `3.13.18`; `pytest-f02.txt` → `45 passed` both | **CONFIRMED** |
| 3330 full suite on both | `pytest-full.txt` → `3330 passed, 74 warnings` on both | **CONFIRMED** |
| 10 named cancellation/lock tests | `named-cancellation-tests.txt` → exactly 10 `PASSED`, `10 passed, 35 deselected` | **CONFIRMED** |
| Negative control genuine | raw `negative-control.txt` contains a real traceback with a real thread id (`[126936305281920]`), `1 failed, 1 passed, 43 deselected` | **CONFIRMED — executed output, not an assertion** |
| Earlier failed run disclosed | run `44881209033` = `failure`, failing step = `Negative control (…)`; correction `9d9dc51` changes `-q`→`-v` and greps for `FAILED`/`PASSED` | **CONFIRMED accurate** |
| `pip-audit` not claimed | 0 occurrences in the workflow; package says "not run" twice | **CONFIRMED honest** |
| No independent-review claim | every mention is a negation | **CONFIRMED** |
| No exactly-once / atomicity claim | explicitly disclaimed | **CONFIRMED** |
| `FINDINGS-TEMPLATE.md` blank | read from artifact; no pre-filled verdict; identical across both Pythons | **CONFIRMED blank** |

---

## 3. Evidence unavailable or incomplete

| Item | Status |
|---|---|
| `…ISOLATED-CANDIDATE-PUBLICATION-CI-INDEPENDENT-REVIEW-CLOSURE-REPORT.md` | **DOES NOT EXIST** in the repository. The nearest published artifacts are `…FINAL-CI-INDEPENDENT-REVIEW-AND-CLOSURE-REPORT.md` and `…ISOLATED-FINAL-CLOSURE-REPORT.md`. I did not infer the missing document's contents. |
| `pip-audit` result | **UNAVAILABLE in this run** — not executed. Not inferred. |
| Mutation coverage beyond 2 mutants | **UNAVAILABLE** — never claimed, never performed |
| Independent review | **UNAVAILABLE** — structurally, not a tooling gap |

---

## 4. Technical assessment

Full per-criterion table with citations is in
`docs/reviews/OHB2-WP07-DEF011-F02-OWNER-DECISION-BRIEFING.md` §3. Summary:

| Classification | Count | Criteria |
|---|---|---|
| **VERIFIED** | 7 | gate + mutual exclusion; cancel-before-gate; cancel-after-start; lock retention; no overlap; unconditional completion signal; error propagation |
| **VERIFIED_WITH_LIMITATION** | 3 | AnyIO shielding/drain (D6 not covered); regression-test quality (2 mutants only); D6 known limitation |
| **NOT_VERIFIED** | 0 | — |
| **FAILED** | 0 | — |

### Mutation testing I performed

To test whether the tests are meaningful rather than merely green, I applied two mutants to a throwaway
copy of the candidate:

| Mutant | Change | Caught by | Reason |
|---|---|---|---|
| **M4′** | Removed the `abandoned` check in `_worker` (gate left intact) | **`REV01` only** — 1 failed, 44 passed | failure was `writes_i1 == 0` violated — the intended defect, not an incidental error |
| **M-gate** | Caller never sets `abandoned`; always drains | **8 tests** | `case02`, `case04`, `case03`, `case15`, `case11`, `M3`, `case17`, `REV01` |

**Conclusion:** the tests genuinely discriminate — they are not vacuous. But `REV01` is the **single**
catcher of the most important mutant, which is a real coverage observation worth the owner's attention.

I also observed that under M-gate the suite reported `8 failed, 37 passed` and then a lingering
non-daemon thread kept the process alive until a hard kill. This is a test-harness property (no
`pytest-timeout`), not an implementation defect, and it does not affect the candidate.

### Implementation read

- Gate: `threading.Lock` `_gate` guards only flag reads/writes; no `await`, no disk, no DB inside it —
  statically enforced by `test_f02_case18_no_await_while_holding_gate`.
- Worker: whole body in `try/except BaseException/finally: _done.set()`, so completion is unconditional.
- Drain: outer `anyio.CancelScope(shield=True)` around `run_sync(_done.wait)`, then re-raise.
- Errors: captured to `_box["error"]` and re-raised to the caller — not swallowed.
- `handlers.py`: `_read_local_capped` moved into `to_thread.run_sync`, with
  `except AttachmentTooLargeError: raise` and `except OSError` preserved.

No defect confirmed in any of these paths.

---

## 5. Findings I could not support, and did not invent

- **No implementation defect found.** I looked specifically at the gate, drain, error propagation and
  lock-release paths. Absence of a finding is reported as absence, not padded with speculation.
- **One cosmetic documentation error**: the evidence package describes `runnervm0hi8g` as the runner;
  it is the **hostname**. `RUNNER_NAME` is `GitHub Actions 1000000341` / `1000000342`. The isolation
  claim is unaffected — it rests on the provisioner/image evidence, which is correct.

---

## 6. Files created

| File | Purpose |
|---|---|
| `docs/reviews/OHB2-WP07-DEF011-F02-OWNER-DECISION-BRIEFING.md` | Owner briefing: verified state, criteria table, findings, questions, evidence list, blank outcomes |
| `docs/reviews/OHB2-WP07-DEF011-F02-OWNER-REVIEW-EVIDENCE-AUDIT-REPORT.md` | This report |

**Nothing modified.** Not `bot/attachments.py`, not `bot/handlers.py`, not any test, not
`.github/workflows/f02-review.yml`, not `ci.yml`, not any branch, PR, setting, secret or permission.
`FINDINGS-TEMPLATE.md` was read from the artifact and left untouched.

Workspace at completion: `HEAD 52e7789`, 8 pre-existing modifications preserved, **0 staged**,
`.openhands/` and `.agent/` intact.

### Pre-existing working-tree state (not mine, preserved)

The main workspace carries uncommitted work from **before** this session — mtimes are
`2026-11-20 15:53`, this audit ran on `2026-11-21`. Worth recording so it is not mistaken for audit
activity:

- `bot/attachments.py` in the working tree is **byte-identical to the F-02 candidate blob**
  (`b98d561f…`), while `HEAD` (main) has `7e448b52…`.
- `bot/handlers.py` in the working tree is `40dd8902…`, which differs from **both** main
  (`96325cf2…`) and the candidate (`82d9c4b8…`) — i.e. F-02 plus further local work on top. It does
  contain the F-02 `to_thread.run_sync(functools.partial(_read_local_capped, …))` change at line 2087.
- 7 tracked modifications and 10 untracked test files sit under `bot/`, `tests/`, `.github/`.

I read these only. Nothing under `bot/`, `tests/` or `.github/` was written by this audit.

---

## 7. Is the owner briefing ready?

**Yes.** It is ready because:

1. Every number in it was reproduced from the live run and the live commit.
2. It contains no recommendation and no selected outcome — all five outcomes are listed with blank
   fields.
3. It separates execution-host isolation, technical evidence, owner judgment, and independent review
   (unavailable) into distinct rows.
4. Its limitations section names D6, the 2-mutant ceiling, the absent `pip-audit`, and the
   single-point mutation coverage of `REV01`.
5. It tells the owner exactly what to inspect and how to reproduce the focused suite with four
   packages.

---

## 8. Status

**F-02 is open. WP-07 is open. DEF-011 is open.** PR #8 and PR #9 are open and unmerged. D6 remains
deferred. No independent review exists or is claimed.

**The technical decision remains with the repository owner.** My role ended at producing a verifiable
evidence briefing.
