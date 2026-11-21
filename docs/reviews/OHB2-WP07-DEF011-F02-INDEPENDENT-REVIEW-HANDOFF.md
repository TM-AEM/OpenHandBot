# OHB2 — WP-07 / DEF-011 / F-02 — Independent Review Handoff

**Prepared:** 2026-11-18 · **Updated for publication:** 2026-11-20
**Review status: NOT PERFORMED.** This document is a *request* for review, not evidence that one
occurred. Preparing this package does **not** constitute, imply, or substitute for an independent review.

---

## PUBLICATION RECORD — immutable revision now available

The six-file candidate has been **published and CI-verified**. A reviewer must review **this exact
commit**, not a local snapshot.

| Item | Value |
|---|---|
| **Publication commit SHA** | `31dec52289142d0d0dc2bd16604d88644ba3baba` |
| Parent (verified base) | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Branch | `review/ohb2-wp07-def011-f02-six-file-ci` |
| **PR** | https://github.com/TM-AEM/OpenHandBot/pull/7 (**OPEN, unmerged**) |
| **CI run** | https://github.com/TM-AEM/OpenHandBot/actions/runs/44767282994 (ID `44767282994`) |
| CI event / workflow | `pull_request` / `CI` |
| CI `headSha` | `31dec52289142d0d0dc2bd16604d88644ba3baba` — **matches the publication commit** |
| Original patch SHA-256 | `59b701369a3b6d2bf70f8028d3ffc8d22831b2f3eedba8cc4de16997246ebe94` |
| Commit diffstat | 6 files, **+2445 / −224** |

### CI results — actual GitHub Actions, both matrix versions

| Job | Python | Result | Test count |
|---|---|---|---|
| `Tests & lint (3.11)` | 3.11.18 | **success** | **3330 passed, 0 failed** (92.15 s) |
| `Tests & lint (3.13)` | 3.13.18 | **success** | **3330 passed, 0 failed** (97.84 s) |
| `Frontend tests (Node)` | Node | **success** | **280 pass, 0 fail** |

Static and security steps inside both Python jobs: `pyflakes` **clean**, `pip-audit` → *No known
vulnerabilities found*, `bandit -lll -s B613` → **High: 0** (5 Low / 19 Medium, unchanged).

**The CI counts match the local runs exactly (3330), and the run checked `31dec52`, not `52e7789`.**
Proof the candidate was in the CI checkout: `tests/test_def011_fs_offload.py` exists at that ref at
**64237 bytes** — identical to the local file — and contains **45 tests** including
`test_f02_REV01_abandoned_worker_must_not_write_and_must_not_overlap`.

### Exact published blob hashes (verify these)

```bash
git fetch origin 31dec52289142d0d0dc2bd16604d88644ba3baba
git cat-file blob 31dec52:bot/attachments.py | sha256sum   # b98d561f…
```

| Path | SHA-256 at `31dec52` |
|---|---|
| `bot/attachments.py` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` |
| `bot/db.py` | `205f1363aaf0b1f8173b74285e263891d333928ba480d478b6b525d4369c694b` |
| `bot/handlers.py` | `40dd8902595c1a63875f8c9d37d4fed4a454be15e1390e5386dcfa9bce058014` |
| `tests/test_def011_fs_offload.py` | `3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea` |
| `tests/test_handlers.py` | `2b1f978091f45c695803a73845065073690f58f1b1c8d2f41fa38d04c1fa8ea8` |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | `ba2633113424432467edeff6cb74f656bb4b5fe9b762dbcc8a251799b33e07ef` |

### Reviewer must review the published commit, not a snapshot

```bash
git clone https://github.com/TM-AEM/OpenHandBot.git && cd OpenHandBot
git checkout 31dec52289142d0d0dc2bd16604d88644ba3baba
git rev-parse HEAD          # must equal 31dec52289142d0d0dc2bd16604d88644ba3baba
sha256sum bot/attachments.py bot/db.py bot/handlers.py \
          tests/test_def011_fs_offload.py tests/test_handlers.py \
          tests/test_sw06_unwatch_db_failure_propagation.py   # must match the table above
```

Then run the tests yourself on a **separate host** (§5). Do not trust the CI result or the author's
local runs — reproduce them.

---

## 0. What the reviewer is being asked to do

Perform a **read-only** technical review of the F-02 candidate and report findings.

**Independence requirement — mandatory.** The reviewer must operate on a genuinely separate host or
isolated execution environment with:

- a separate host **or** genuine isolation boundary (VM, separate machine, separate container host);
- a separate filesystem;
- a separate process/session;
- independent access to the candidate snapshot;
- the ability to compute hashes and run tests themselves.

**Not acceptable as independence:** a different directory, worktree, `git worktree`, named "review"
folder, second process, second agent session, or second user on the **same host**. This environment
already determined that such setups are same-host and same-kernel, and therefore not independent.

If genuine separation is unavailable, the reviewer must record `INDEPENDENCE_NOT_ESTABLISHED` and
must not describe the work as an independent review.

---

## 1. Candidate identity — verify these first

| Item | Value |
|---|---|
| **Published commit (review this)** | `31dec52289142d0d0dc2bd16604d88644ba3baba` |
| Base commit (parent) | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Branch (published) | `review/ohb2-wp07-def011-f02-six-file-ci` |
| Branch (authoring) | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| PR | https://github.com/TM-AEM/OpenHandBot/pull/7 |
| CI run | https://github.com/TM-AEM/OpenHandBot/actions/runs/44767282994 |
| Patch SHA-256 (provenance) | `59b701369a3b6d2bf70f8028d3ffc8d22831b2f3eedba8cc4de16997246ebe94` |

| File | Expected SHA-256 at `31dec52` |
|---|---|
| `bot/attachments.py` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` |
| `bot/db.py` | `205f1363aaf0b1f8173b74285e263891d333928ba480d478b6b525d4369c694b` |
| `bot/handlers.py` | `40dd8902595c1a63875f8c9d37d4fed4a454be15e1390e5386dcfa9bce058014` |
| `tests/test_def011_fs_offload.py` | `3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea` |
| `tests/test_handlers.py` | `2b1f978091f45c695803a73845065073690f58f1b1c8d2f41fa38d04c1fa8ea8` |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | `ba2633113424432467edeff6cb74f656bb4b5fe9b762dbcc8a251799b33e07ef` |

**Recompute all six from the published commit. If any differs, stop and report the discrepancy — do
not review a different snapshot.**

```bash
git clone https://github.com/TM-AEM/OpenHandBot.git && cd OpenHandBot
git checkout 31dec52289142d0d0dc2bd16604d88644ba3baba
git rev-parse HEAD        # must be 31dec52289142d0d0dc2bd16604d88644ba3baba
sha256sum bot/attachments.py bot/db.py bot/handlers.py \
          tests/test_def011_fs_offload.py tests/test_handlers.py \
          tests/test_sw06_unwatch_db_failure_propagation.py
```

The patch file itself is **no longer required** — the published commit is authoritative. It is
retained only as provenance tying the commit back to the verified six-file patch.

---

## 2. Scope of the candidate

**6 files** — the minimum self-consistent set that passes the full suite on a clean base.

| File | Role in F-02 |
|---|---|
| `bot/attachments.py` | **The F-02 fix**: atomic gate, `started`/`abandoned` transitions, drain, worker |
| `bot/handlers.py` | Off-loop `to_thread` local read (asserted by T-8b) |
| `bot/db.py` | Atomic watch/unwatch helpers used by handlers |
| `tests/test_def011_fs_offload.py` | DEF-011 matrix, 45 tests, includes **REV-01** |
| `tests/test_handlers.py` | Updated expectations for the new outcome API |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | Updated cancellation/outcome expectations |

**Excluded:** `.agent/PROGRESS.md`, `bot/app.py`, `bot/watcher.py` (not required), all other untracked
tests, `.openhands/`, `.agent/`, `docs/`.

> **Note for the reviewer:** the original task premise was a *two-file* patch. That was tested and
> **fails CI** (1 failure) because the suite requires the `handlers.py` offload. The 6-file set is the
> corrected unit. Please verify this claim independently — it is central to the publication decision.

---

## 3. F-02 design summary

**Defect:** a raw `Task.cancel()` arriving before the worker starts could leave an abandoned operation
that still wrote to disk, or release the acceptance lock while a writer was active, producing
**two concurrent filesystem writers** for the same item.

**Fix shape (single-cancellation scope):**

- A single `_gate` (`threading.Lock`) serialises the caller's pre-start work against the worker's
  start.
- The caller records `_state["started"] = False` and, on cancellation before start, sets
  `_state["abandoned"] = True` and `_needs_drain = False`, then releases `_accept_lock`.
- The worker, on acquiring `_gate`, **checks `_state["abandoned"]` and returns without writing**.
- Otherwise it sets `_state["started"] = True` and proceeds.
- Completion signalling is unconditional (`_done.set()` in a `finally`), so a waiting caller cannot
  hang.
- The drain runs inside `anyio.CancelScope(shield=True)`.

**What F-02 does NOT claim:** exactly-once Telegram delivery, SQLite↔Telegram atomicity, or safety
under *repeated* raw cancellation (that is D6 — see §6).

---

## 4. REV-01 regression evidence — M4′ mutation

`F-02-REV-01` added one behavioural test:

`tests/test_def011_fs_offload.py::test_f02_REV01_abandoned_worker_must_not_write_and_must_not_overlap`

**Deterministic forcing:** `bot.attachments.threading` is monkeypatched with a shim whose `Lock`
returns a wrapper that, on a **non-main** thread, sets `worker_at_gate` and then blocks on
`worker_may_proceed` **before** acquiring the real lock. The caller therefore always wins the gate —
an event handshake, not a sleep. The wrapper delegates to a real `threading.Lock`, so mutual exclusion
semantics are preserved.

**Assertions:** `writes_i1 == 0` and `max_concurrent_writers == 1`, plus anti-false-pass guards
(`worker_gate_acquisitions >= 1`, `second_started is True`).

**M4′ mutation** removes **only** the abandoned-state early return, keeping `with _gate:` intact:

```diff
                     with _gate:
-                        if _state["abandoned"]:
-                            return
                         _state["started"] = True
```

| Target | 3.13 | 3.11 |
|---|---|---|
| Correct implementation | **pass** (`writes_i1=0`, `max=1`) | **pass** |
| M4′ mutant | **fail** — `assert 1 == 0` (`writes_i1=1`, `max=2`) | **fail** — `assert 1 == 0` |

Because 2 `with _gate:` blocks remain, the older **structural** test (`case18`, `checked >= 2`) still
passes on M4′ — which is exactly why a behavioural test was required.

**Please verify:** apply M4′ yourself, run REV-01, and confirm it fails for the *behavioural* reason,
not a structural or formatting one.

---

## 5. How to reproduce

```bash
git clone https://github.com/TM-AEM/OpenHandBot.git && cd OpenHandBot
git checkout 31dec52289142d0d0dc2bd16604d88644ba3baba
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

# static + full suite (the same command set CI runs)
python -m pyflakes bot/ automation/ tools/ main.py tests/
python -m pytest -q
python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
python -m pip_audit -r requirements-dev.txt
node --test tests/frontend/*.test.js
```

**Expected at `31dec52`** — confirmed both by the author locally (3.11.18 / 3.13.15) **and by actual
GitHub Actions run `44767282994`** on the same commit:

| Check | Expected | CI confirmed |
|---|---|---|
| pyflakes | clean, exit 0 | **yes** |
| `pytest -q` | **3330 passed, 0 failed** | **yes** (3.11: 3330; 3.13: 3330) |
| bandit | Severity **High: 0** | **yes** (5 Low / 19 Medium / 0 High) |
| pip-audit | no known vulnerabilities | **yes** |
| frontend | **280 pass, 0 fail** | **yes** |

**Note:** 3330, not 3443. The authoring worktree reports 3443 because it contains 8 additional
**untracked** test files from other work packages that are not part of this publication set.

**Do not treat the CI result as the review.** Reproduce the run yourself on your own host; a reviewer
who merely cites run `44767282994` has not reviewed anything.

---

## 6. D6 — deferred and open (do not mark safe)

**D6 is explicitly deferred and remains an open defect.** Repeated raw `Task.cancel()` during the drain
is **not** safe: a second raw cancel interrupts the drain, `_accept_lock` is released under an active
writer, and `max_concurrent_writers` reaches 2. `anyio.CancelScope(shield=True)` does not prevent this,
and the implementation does not claim it does.

F-02 addresses **single** cancellation only. Any review statement implying repeated raw cancellation is
safe would be incorrect.

---

## 7. Architecture and scope constraints the review must respect

| Constraint | Requirement |
|---|---|
| Process model | One bot + ASGI process, one authoritative SQLite owner |
| Concurrency | No new worker system, no parallel polling, no concurrency added for F-02 |
| Mini App | **Unchanged** — no source, UI, assets, config, tests or docs |
| Schema | **Unchanged** — no migration, table, or column |
| API | **Unchanged** |
| Dependencies | **No new dependency** |
| SQLite ownership | Filesystem work off the loop; DB work stays on the owner path; no DB handle passed to the worker |
| Delivery claims | No exactly-once Telegram delivery; no SQLite↔Telegram atomicity |

Architectural markers in `bot/attachments.py` that must stay at **zero**: `asyncio`,
`create_task`, `create_task_group`, `TaskGroup`, `Thread(`, `opportunistic_cleanup`.

---

## 8. Review checklist

Please answer each explicitly with evidence.

### Cancellation timing
1. Is the `_gate` acquisition ordering correct — can the caller and worker both proceed, or is exactly one guaranteed to win?
2. Is the `abandoned` check performed **inside** the gate, and before any write?
3. What happens if cancellation lands **after** `started = True`? Is that path defined and safe for a single cancel?
4. Is there any window where `_accept_lock` is released while a writer is still active?

### Gate atomicity
5. Is `_state` access properly serialised by `_gate`? Any read/write outside the gate?
6. Can two callers both observe `started == False` and both set `abandoned`?

### Worker completion
7. Is completion signalling unconditional (i.e. `_done.set()` in `finally`)?
8. Can a caller wait forever if the worker raises before signalling?

### Lock release
9. Is `_accept_lock` released on every path — success, cancellation, and exception?
10. Is the drain shielded, and is the shielding claim limited to what it actually guarantees?

### Exception handling
11. Are exceptions propagated meaningfully rather than swallowed?
12. Does a writer failure leave state consistent for the next operation?

### Regression coverage
13. Does REV-01 fail on M4′ for a **behavioural** reason? (Verify by applying M4′ yourself.)
14. Does M4′ remove **only** the abandoned guard? (Confirm `with _gate:` count is still 2.)
15. Is the test's forcing deterministic (event handshake) rather than sleep-based?
16. Do the anti-false-pass guards actually fail when the scenario does not occur?
17. Is the test free of cross-test leakage (monkeypatch restored)?

### Scope
18. Are all 6 files required? Verify the two-file set fails and the 6-file set passes.
19. Any unrelated change, secret, or scope violation in the patch?
20. Are the architecture markers still at zero and the constraints in §7 respected?

---

## 9. Reporting

Please report, with the exact snapshot hashes you verified:

- Verdict: `PASS` / `PASS_WITH_NOTES` / `FAIL`
- Independence: `INDEPENDENCE_ESTABLISHED` **or** `INDEPENDENCE_NOT_ESTABLISHED`
- Findings, each with severity (Critical / High / Medium / Low) and evidence
- Any claim in this handoff you could **not** reproduce — state it plainly

**Do not** modify implementation files. This is a read-only review.

---

## 10. Honest status statement

| Item | Status |
|---|---|
| Package prepared | **yes** (this document) |
| Candidate published | **YES** — commit `31dec52`, PR #7 (open, unmerged) |
| CI executed for this candidate | **YES** — run `44767282994` on `31dec52`, 3.11 + 3.13 + frontend all success |
| Independent review performed | **NO** |
| F-02 closed | **NO** |
| D6 resolved | **NO** — deferred and open |
| Owner acceptance | **NOT GRANTED** |

F-02 remains **open** until a genuinely independent review is completed with
`INDEPENDENCE_ESTABLISHED`. CI is now done; review is the only remaining gate.
