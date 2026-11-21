# OHB2 — WP-07 / DEF-011 / F-02 — Owner Review Evidence Package

**Prepared:** 2026-11-21
**Review target:** `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18`
**Evidence run:** `44881727141` (success, both Python versions)
**Status: EVIDENCE READY — NO JUDGMENT MADE**

---

## Read this first

**This is an owner review, not an independent review.**

The workflow that produced this package collects evidence. It does **not** evaluate the change, does
not assert that F-02 is correct, and does not contain an instruction to approve. A green run is not a
verdict. **You may reject this change even though every check below passed.**

Nothing here closes F-02. F-02 remains open until you record an explicit technical decision.

---

## 1. What was tested, and what was not

| Item | Value |
|---|---|
| Review target (exact) | `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` |
| Base / merge-base | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Target branch | `review/ohb2-wp07-def011-f02-isolated` (PR #8, **open, unmerged**) |
| Changed files | exactly 3 — scope guard passed |
| `bot/handlers.py` hunks | **3** |
| F-02 tests | **45** |
| Python versions tested | **3.11.18** and **3.13.18** |

**Important distinction.** The workflow was published on a *separate* branch and PR (#9). That PR adds
**only** `.github/workflows/f02-review.yml`. The F-02 candidate itself (`6a1ca2e`) is unchanged and
untouched — the workflow is tooling, not part of the change under review.

---

## 2. Exact hashes — verify these yourself

```bash
git fetch origin 6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18
git cat-file blob 6a1ca2e:bot/attachments.py | sha256sum
```

| Path | SHA-256 at `6a1ca2e` | Matches artifact? |
|---|---|---|
| `bot/attachments.py` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` | **YES** |
| `bot/handlers.py` | `82d9c4b8e0fa0e005f2a7c9494a57903a94e7f79eb45d08babe5ebd9dbd57525` | **YES** |
| `bot/db.py` (unchanged) | `472fa573142ee4265cdb2a26ec882906d743d798300e73ad16a9583ef5343314` | **YES** |
| `tests/test_def011_fs_offload.py` | `3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea` | **YES** |
| `evidence/full.diff` | `cb3da6526d536dddf1eca23ba1d8b94a01b86aaf360507838d0eb10c81b02ab0` | **identical in both runs** |

I independently re-derived all four file hashes from the real commit with `git show 6a1ca2e:<path> |
sha256sum` and they match the artifact byte for byte.

`bot/db.py` is listed deliberately: it is **unchanged**, which is evidence that no schema moved.

---

## 3. Where the evidence lives

| Item | Identifier |
|---|---|
| Workflow PR | **#9** — https://github.com/TM-AEM/OpenHandBot/pull/9 |
| Branch | `f02-owner-review-workflow` |
| Workflow head commit | `1a84cad` (the workflow file only) |
| **Final evidence run** | **`44881727141`** — https://github.com/TM-AEM/OpenHandBot/actions/runs/44881727141 |
| Artifacts | `f02-review-evidence-6a1ca2e…-py3.11`, `…-py3.13` (30-day retention) |
| Earlier failed run | `44881209033` — see §7, kept for honesty |

```bash
gh run download 44881727141 --repo TM-AEM/OpenHandBot -D evidence-package
```

Both artifacts contain 22 files including `full.diff`, `code-only.diff`, `file-sha256.txt`,
`pytest-f02.txt`, `pytest-full.txt`, `negative-control.txt`, `named-cancellation-tests.txt`,
`bandit.txt`, `pyflakes.txt`, `changed-files.txt`, `scope.txt`, and the two templates below.

---

## 4. Test results

### 4.1 The F-02 regression suite — 45 tests

| Python | Result | Time |
|---|---|---|
| 3.11.18 | **45 passed** | 2.15 s |
| 3.13.18 | **45 passed** | 2.58 s |

### 4.2 Cancellation and lock-drain tests, by name

Recorded explicitly (`-v`) so you can see *which* tests ran, not just a count:

```
test_F02_lock_held_while_worker_writes_after_raw_cancel              PASSED
test_F02_worker_failure_after_cancel_releases_lock_and_never_stores  PASSED
test_f02_case05_cancel_after_worker_start                            PASSED
test_f02_case06_cancel_during_filesystem_write                       PASSED
test_f02_case15_lock_released_on_every_exit_path                     PASSED
test_f02_case07_worker_success_after_cancellation                    PASSED
test_f02_case08_oserror_during_cancellation_path                     PASSED
test_f02_case13_anyio_scope_already_cancelled_at_drain               PASSED
test_f02_case16_shutdown_completion_with_pending_cancellation        PASSED
test_f02_REV01_abandoned_worker_must_not_write_and_must_not_overlap  PASSED
→ 10 passed, 35 deselected
```

### 4.3 Full test suite — no regressions

| Python | Result | Time |
|---|---|---|
| 3.11.18 | **3330 passed**, 74 warnings | 90.98 s |
| 3.13.18 | **3330 passed**, 74 warnings | 98.89 s |

The count matches the published CI baseline of 3330 exactly, so F-02 introduced no regression.

### 4.4 Attachment module and guard tests

Covered inside the 45: T-1…T-14 matrix, `T4b` sweep throttle, `T5`/`T6`/`T6b` SQLite ownership,
`T7`/`T9`/`T10`/`T10b` cancellation, error mapping and size limits, `T11`/`T11b` quota defaults,
`T12` 17-table schema unchanged, `T13`/`T13b`/`T14` semantic parity and serialization.

---

## 5. Negative control — does the fix actually matter?

This is the most important piece of evidence, because it tests the *test*.

The workflow reverts the `bot/handlers.py` hunk to the base version, asserts the reverted blob matches
the base blob exactly, re-runs only `T8b` and `T8c`, then restores the file.

| Outcome | Observed (both Pythons) |
|---|---|
| Revert succeeded and blob matched base | **YES** (fail-closed: otherwise the step aborts) |
| `T8b_local_capped_read_runs_off_event_loop_thread` | **FAILED** — `AssertionError: القراءة حصلت على خيط الحلقة` |
| `T8c_local_capped_read_enforces_cap` | **PASSED** |
| Summary | `negative_control=T8b_fails_as_expected,T8c_still_passes` |

**What this proves:** `T8b` genuinely discriminates the F-02 fix — with the fix removed, the local
capped read runs on the event-loop thread and the test catches it. `T8c` correctly still passes
because it tests the byte cap, not the offload, which shows the 45 tests are not redundant copies.

**What it does not prove:** that every one of the 45 tests is non-vacuous. Only `T8b` was
mutation-tested here. Judging the rest is your call (see §8).

---

## 6. Static and security checks

| Check | Python 3.11 | Python 3.13 |
|---|---|---|
| `pyflakes bot/ automation/ tools/ main.py tests/` | **0 output lines** (clean) | **0 output lines** (clean) |
| `bandit -r … -lll -s B613` severity High | **0** | **0** |
| bandit severity Low / Medium | 5 / 19 | 5 / 19 |

The Low/Medium counts are unchanged from the pre-existing baseline; no new high-severity finding was
introduced. Note for transparency: bandit also reports a *confidence* breakdown (High: 6). That is
**confidence, not severity** — severity High is 0.

`pip-audit` is **not** part of this workflow. It remains covered by the existing `ci.yml`; I did not
add it here to avoid duplicating dependency scanning, and I am not claiming it passed in this run.

---

## 7. Known limitations and unresolved risks

Read these before judging.

1. **Not an independent review.** The workflow has no reviewer identity and no reasoning step. It runs
   on a separate host; it does not supply independent judgment.
2. **D6 is NOT fixed.** Repeated raw cancellation is explicitly deferred. `bot/attachments.py` lines
   ~916/966 still carry the D6 deferral markers. Do not read this package as covering D6.
3. **Only `T8b` was mutation-tested.** The negative control proves one test discriminates. The other
   44 are asserted only by passing.
4. **`T8c` passes in the control by design** — it is not a mutation target. That is correct, not a gap.
5. **No exactly-once delivery and no SQLite-Telegram atomicity** may be inferred. Neither is claimed
   by the implementation or by this package.
6. **`pip-audit` was not run** in this workflow (see §6).
7. **One earlier run failed** (`44881209033`) on my own assertion bug: the negative-control check
   grepped for a passing test name in `-q` output, which omits it. The control itself behaved
   correctly in that run (T8b failed, T8c passed) — only my *assertion* was wrong. Fixed and re-run;
   the fix is commit `9d9dc51`. Reported here rather than hidden.
8. **`workflow_dispatch` is unavailable** for this workflow until it reaches the default branch; the
   evidence came from the `pull_request` trigger. Not a defect, but it means you cannot re-dispatch
   from the Actions UI yet.
9. **Evidence retention is 30 days.** Re-run if it expires.

---

## 8. What you must decide — four separate things

Keep these distinct; conflating them is how weak reviews get mistaken for strong ones.

| # | Dimension | Status | Whose call |
|---|---|---|---|
| 1 | **Execution-host isolation** | **PROVEN** — GitHub-hosted VM (`runnervm0hi8g`, `ubuntu26`, image `20261116.202.1`), separate from the development host | nobody — this is a fact |
| 2 | **Technical evidence** | **COMPLETE** — hashes, 45 tests ×2 Pythons, 3330 full suite, named cancellation tests, negative control, static analysis | nobody — this is a fact |
| 3 | **Owner judgment** | **PENDING** | **YOU** |
| 4 | **Independent review** | **NOT AVAILABLE** — no second human, no qualified automated reviewer (GitHub Models retired; Copilot unpaid; NVIDIA unreliable and needs a secret) | not available |

### Your review checklist

1. Read `full.diff` and `code-only.diff` yourself.
2. Assess cancellation safety: the atomic `threading.Lock` gate, `_done` in `finally`, the drain under
   an outer shield, `abandoned=True` at the pre-start boundary.
3. Judge whether the 45 tests are *meaningful* — would each fail if its defect returned?
4. Check that `AttachmentTooLargeError`/`OSError` still propagate rather than being masked by the new
   `to_thread.run_sync` wrapper.
5. Confirm the scope guards: exactly 3 files, 0 NEW-DEF-03/NAV markers, no schema/Mini App/API change.
6. Identify what is untested, and whether the D6 deferral is acceptable.
7. Reproduce the focused suite yourself (needs only four packages):

```bash
pip install pytest anyio httpx python-telegram-bot
python -m pytest tests/test_def011_fs_offload.py -q     # expect 45 passed
```

8. Fill in `FINDINGS-TEMPLATE.md` yourself — it is deliberately blank.

### Decision

- [ ] **Accept** — F-02 is correct as published
- [ ] **Accept with follow-ups** — correct, with recorded non-blocking findings
- [ ] **Reject** — a blocking defect exists

---

## 9. Reproducing this yourself

```bash
# 1. exact target
git clone https://github.com/TM-AEM/OpenHandBot.git && cd OpenHandBot
git checkout 6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18
git rev-parse HEAD        # must print 6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18

# 2. hashes must match §2
sha256sum bot/attachments.py bot/handlers.py bot/db.py tests/test_def011_fs_offload.py

# 3. the focused suite
pip install pytest anyio httpx python-telegram-bot
python -m pytest tests/test_def011_fs_offload.py -q     # expect 45 passed

# 4. the evidence from the run
gh run download 44881727141 --repo TM-AEM/OpenHandBot -D evidence-package
sha256sum evidence-package/*/evidence/full.diff         # expect cb3da652…
```

If your numbers differ from §2/§4, stop and report it — that would mean the target moved.

---

## 10. Statement

No verdict is recorded here. The workflow asserted none, this package asserts none, and F-02 is **not**
closed. WP-07 and DEF-011 are **not** complete. The technical judgment belongs to the repository owner.
