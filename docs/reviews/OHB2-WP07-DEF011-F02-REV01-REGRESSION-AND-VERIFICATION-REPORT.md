# OHB2 — WP-07 / DEF-011 / F-02-REV-01 — Regression Test and Verification Report

**Task:** `OHB2-WP07-DEF011-F02-REV01-REGRESSION-TEST-AND-VERIFICATION`
**Date:** 2026-11-18
**Resolves:** `F-02-REV-01 (Medium)` — the `abandoned`-state guard lacked behavioural regression coverage
**Predecessor:** `OHB2-WP07-DEF011-F02-INDEPENDENT-REVIEW-AND-CLOSURE` (verdict `INDEPENDENCE_NOT_ESTABLISHED`)

---

## FINAL VERDICT

```
F02_REV01_FIXED_AND_VERIFIED
```

The new behavioural regression test **passes** against the correct implementation and **fails** against
the exact M4′ mutation, deterministically, for the expected behavioural reason, with the loaded
module identity proven by SHA-256 in both directions. The production implementation is byte-identical
to the Phase 1 baseline.

---

## 1. Baseline (Phase 1)

### 1.1 Git state — captured before any change

| Property | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Divergence | `0 0` |
| Staged | 0 |
| Modified | 8 |
| Untracked | 66 |
| Ignored | 8 |

### 1.2 Baseline hashes

| File | SHA-256 | Matches reviewed snapshot? |
|---|---|---|
| `bot/attachments.py` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` | **yes** (`b98d561f…`) |
| `tests/test_def011_fs_offload.py` | `61babf0d77ff283e40f50b0d67448906c1ed6165849490b33bcb3ad579a160e4` | **yes** (`61babf0d…`) |

Both hashes match the reviewed F-02 snapshot exactly, so the work started from the reviewed state.

### 1.3 Preservation

No `reset`, `clean`, `stash`, checkout, or deletion was performed. All unrelated working-tree content
was preserved: `.openhands/`, `.agent/`, the 8 pre-existing modified files, the 66 pre-existing
untracked files (including the `docs/audits/*` records), and the 8 ignored files. All mutation and
probe work happened **outside** the repository, under `/tmp/rev01/`.

### 1.4 Synchronisation points identified in the existing suite

The existing helpers in `tests/test_def011_fs_offload.py`:

- `_f02_make(tmp_path)` — store + batch fixture
- `_f02_plain_writer(store, counter)` — counting writer
- `_f02_blocking_writer(store)` — blocking writer returning `(entered, release, state)` where
  `state = {"active", "max", "writes"}`
- `_f02_cancel_after_ticks(store, ticks)` — raw cancel after N event-loop ticks, bounded by
  `_F02_TIMEOUT = 2.0`

The exact M4′ window is **between the caller's `_gate` acquisition and the worker's `_gate`
acquisition**. None of the existing 23 tests force that ordering: `case12` and `case17(b)` cancel
*while the worker is already writing*, and `case17(a)` cancels *before the worker is dispatched*.
Neither pins the worker at the gate while the caller wins it — which is precisely the M4′ window.

---

## 2. Test design (Phase 2)

**Added:** one test, `test_f02_REV01_abandoned_worker_must_not_write_and_must_not_overlap`, appended
to `tests/test_def011_fs_offload.py`. **Purely additive: +149 lines, 0 lines removed or modified**
(byte-prefix verified in §5.2).

### 2.1 The problem with a timing-based test

The M4′ window is a narrow race: the caller must set `_state["abandoned"] = True` *before* the worker
reads it. A test that merely cancels at some tick would be flaky — the worker might read `started`
first, and then the correct code and the mutant behave identically. Sleeps cannot fix this: they
widen a window without closing it.

### 2.2 Deterministic forcing — wrap the gate itself

The test replaces `bot.attachments.threading` with a shim whose `Lock` returns a controlled gate:

```python
def acquire(self, *args, **kwargs):
    if threading.get_ident() != main_ident:      # worker thread
        worker_gate_acquisitions.append(1)
        worker_at_gate.set()                     # tell the caller: worker is AT the gate
        worker_may_proceed.wait(timeout=_F02_TIMEOUT * 3)   # bounded hold
    return self._real.acquire(*args, **kwargs)
```

Consequence: the worker thread is **held before it can acquire the gate**. The caller therefore
wins the gate deterministically — no reliance on scheduler luck, and no sleep as the primary
synchronisation mechanism. The ordering is established by an event handshake
(`worker_at_gate` → caller cancels → `worker_may_proceed`), not by elapsed time.

The shim delegates to a real `threading.Lock` for actual mutual exclusion, so the gate's real
semantics are preserved; only the *ordering* is controlled.

### 2.3 The scenario

1. Start `store_async(item_id="i1")`; wait (bounded) for `worker_at_gate`.
2. `t1.cancel()` — the caller takes the gate, observes `started == False`, sets
   `abandoned = True`, `_needs_drain = False`, releases `_accept_lock`.
3. Await `t1` (bounded) → expect `CancelledError`.
4. Assert `_accept_lock` is **free**.
5. Set `worker_may_proceed` — the worker now proceeds past the gate.
6. Start a **competing** `store_async(item_id="i2")`; wait (bounded) for it to reach the writer.
7. Read `max_concurrent_writers` and the per-item write counts.
8. Release the writer, drain, assert.

Items are distinguished by chunk payload (`chunks=[b"i1"]` / `[b"i2"]`), so "did the abandoned
operation write?" is measured directly rather than inferred.

### 2.4 Assertions

| # | Assertion | Purpose |
|---|---|---|
| 1 | `reached_gate is True` | The scenario actually occurred |
| 2 | `outcome == "cancelled"` | The caller was genuinely cancelled |
| 3 | `lock_free_after_abandon is True` | The lock is released on the abandon path |
| 4 | `len(worker_gate_acquisitions) >= 1` | The worker genuinely reached the gate — **anti-false-pass** |
| 5 | `second_started is True` | The competing writer genuinely ran — measurement is valid |
| 6 | `writes_i1 == 0` | **The abandoned worker performed no filesystem write** |
| 7 | `max_conc == 1` | **No overlapping filesystem writers** |

Assertions 4 and 5 are the anti-false-pass guards: without them the test could pass by measuring
nothing. Assertions 1–7 are behavioural; **no assertion counts source blocks or inspects
formatting**.

### 2.5 Bounded waits

Every wait is bounded: `_F02_TIMEOUT * 3` on the gate hold and the writer block, `_F02_TIMEOUT` on
`asyncio.wait_for`, and a `loop.time()` deadline in the `_wait_event` helper. A regression produces
an assertion failure, never a hung test process. A `finally` block always sets `release` and
`worker_may_proceed`, so a failed assertion cannot strand a thread.

---

## 3. Mutation validation (Phase 3) — mandatory

### 3.1 The exact M4′ mutation

Applied to an **out-of-tree copy** (`/tmp/rev01/mut`), removing **only** the abandoned early-return
and keeping the gate and all other logic intact:

```diff
                     with _gate:
-                        if _state["abandoned"]:
-                            return  # المستدعي تخلّى الأول ⇒ مفيش كتابة إطلاقًا
                         _state["started"] = True
```

Verified properties of the mutant:

| Check | Value |
|---|---|
| `with _gate:` blocks remaining | **2** (unchanged) |
| `_state["abandoned"]` references remaining | **1** (only the caller's write) |
| Mutant SHA-256 | `407878573d66d112aa5e1416de059450cbe7ee793f25210d60fcf8f0040e4f67` |
| Correct SHA-256 | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` |

Because 2 gate blocks remain, the pre-existing structural test `case18` (`checked >= 2`) **still
passes** on this mutant. That is exactly why the earlier review found M4′ surviving the whole suite —
and it is why the new test must be behavioural.

### 3.2 Loaded-module identity proof — both directions

The prior review nearly produced a false PASS because `/workspace/project/OpenHandBot` won `sys.path`
resolution. This run hard-asserts the SHA-256 of the **loaded module's file** in every run.

**Mutant run** (`-p conftest_guard`, which strips the repo from `sys.path` and asserts the mutant hash):

```
[guard] bot.attachments = /tmp/rev01/mut/bot/attachments.py sha=407878573d66d112
```

**Correct run** (guard asserting the baseline hash):

```
[guard] bot.attachments = /workspace/project/OpenHandBot/bot/attachments.py sha=b98d561f0ba0ab27
```

Both guards executed and printed; neither could silently load the other tree.

### 3.3 Results

**Correct implementation — PASS**

```
1 passed, 44 deselected
```

**M4′ mutant — FAIL, for the expected behavioural reason**

```
>       assert writes_i1 == 0, (
            "العامل المهجور كتب على القرص — فحص `abandoned` مش شغّال (عيب M4′)"
        )
E       AssertionError: العامل المهجور كتب على القرص — فحص `abandoned` مش شغّال (عيب M4′)
E       assert 1 == 0
tests/test_def011_fs_offload.py:1572: AssertionError
```

The failure is the **forbidden write**, not a structural or formatting complaint.

### 3.4 Independent metric confirmation

A standalone probe (same forcing, no pytest) reported both quantities:

| Tree | Loaded SHA | `writes_i1` | `max_concurrent_writers` | Verdict |
|---|---|---|---|---|
| Correct | `b98d561f…` | **0** | **1** | clean — single writer, no abandoned write |
| M4′ mutant | `407878573d…` | **1** | **2** | **OVERLAP + FORBIDDEN WRITE** |

This reproduces the review's finding exactly (`2` vs `1`) and adds the direct per-item write
measurement.

### 3.5 Determinism

| Target | Runs | Result |
|---|---|---|
| Correct implementation | 15 | **15 / 15 passed** (0 failures) |
| M4′ mutant | 15 | **15 / 15 detected** (0 misses) |

No flakiness in either direction.

---

## 4. Full validation (Phase 4)

Environment: **Python 3.13.15** (GCC 14.2.0), **pytest 9.0.3**, **anyio 4.16.0**, Node (frontend).

| # | Check | Command | Result | Exit |
|---|---|---|---|---|
| 1 | New test, repeated | `pytest -k REV01` ×15 | **15/15 pass** | 0 |
| 1b | New test vs mutant | `pytest -k REV01` ×15 | **15/15 fail (detected)** | 1 (expected) |
| 2 | Focused F-02 + REV-01 | `pytest -k "f02 or REV01"` | **24 passed**, 21 deselected | 0 |
| 3 | Full module | `pytest tests/test_def011_fs_offload.py` | **45 passed** | 0 |
| 4 | Architectural guards | `pytest test_repair_plan_01_review_findings.py test_attachment_cleanup_expiration_a4.py` | **101 passed** | 0 |
| 5 | Full Python suite | `pytest -q` | **3443 passed, 0 failed** (187.13 s) | 0 |
| 6 | Frontend | `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** | 0 |
| 7 | pyflakes | `pyflakes bot/ automation/ tools/ main.py tests/` | **clean** | 0 |
| 8 | bandit | `bandit -r … -lll -s B613` | **Severity High: 0** | 0 |
| 9 | pip-audit | `pip_audit -r requirements-dev.txt` | **No known vulnerabilities** | 0 |

Counts moved exactly as expected: focused 23→**24**, module 44→**45**, full suite 3442→**3443**, all
by exactly one. No test regressed.

### 4.1 bandit — severity vs confidence reported separately

```
Total issues (by severity):
        Undefined: 0
        Low: 5
        Medium: 19
        High: 0            <-- authoritative gate
```

The output also prints a *confidence* breakdown containing "High: 6". That is **confidence**, not
severity. **Severity High = 0**, which is the project gate.

---

## 5. Scope and architecture preservation (Phase 5)

### 5.1 Production implementation — byte-identical

```
baseline : b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356
final    : b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356
```

**No production change was needed or made.** The reference behaviour was correct; only its
regression coverage was missing.

### 5.2 Only the test file changed — append-only, proven at byte level

| Evidence | Result |
|---|---|
| `diff` baseline-archive vs current | `1426a1427,1575` — **0 deletions**, 149 additions |
| `current_bytes.startswith(baseline_bytes)` | **True** |
| Baseline bytes → current bytes | 58 180 → 64 237 |

So the pre-existing 1 426 lines are untouched byte-for-byte; the new test is purely appended.

| File | Baseline | Final |
|---|---|---|
| `bot/attachments.py` | `b98d561f…` | `b98d561f…` **(unchanged)** |
| `tests/test_def011_fs_offload.py` | `61babf0d…` | `3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea` |

### 5.3 Git totals unchanged

| Property | Baseline | After test edit | Final (incl. this report) |
|---|---|---|---|
| HEAD | `52e7789` | `52e7789` | `52e7789` |
| Staged | 0 | 0 | 0 |
| Modified | 8 | 8 | 8 |
| Untracked | 66 | 66 | **67** |
| Ignored | 8 | 8 | 8 |

The test file was **already untracked at baseline**, so editing it did not change the untracked
count (66 before and after the edit). The count rises to 67 only because this report is a new
untracked file; it is the single new path, confirmed by `git status --porcelain`. The pre-existing
`docs/audits/*` untracked records are untouched. No stray files were left in the repository
(`conftest_guard*.py` were created under `/tmp/rev01/` or removed immediately after use — verified
absent).

### 5.4 Architecture checks

| Token in `bot/attachments.py` | Count | Requirement |
|---|---|---|
| `asyncio` | **0** | PASS |
| `create_task` | **0** | PASS |
| `create_task_group` / `TaskGroup` | **0** / **0** | PASS |
| `Thread(` | **0** | PASS |
| `opportunistic_cleanup` | **0** | PASS |

- **No schema change.** No migration, no table, no column.
- **No Mini App change.** No Mini App source, UI, asset, config, test, or doc was touched.
- **No API change.** No endpoint, payload, or contract.
- **No database-ownership change.** SQLite access stays on the event-loop owner path.
- **No worker-lifecycle change.** The test *observes* the existing gate; it does not add a worker,
  queue, background service, thread pool, or process.
- **No new dependency.** `git status` shows no change to `requirements*.txt`, `pyproject.toml`,
  `setup.py`, or `package.json`. The test uses only `asyncio`, `threading`, `anyio`, `pytest` — all
  already imported at the top of the file (`imports unchanged`, verified by diff).
- **No staging / commit / branch / push / PR / merge / deploy / Autopush.** Repository visibility and
  settings unchanged. No external CI triggered.

---

## 6. Technical review of the new test (Phase 6)

| Review question | Answer | Evidence |
|---|---|---|
| Does it genuinely fail against M4′? | **Yes** | §3.3 — `assert 1 == 0` on `writes_i1`, 15/15 detected |
| Does it pass against the correct implementation? | **Yes** | §3.3 — 1 passed; 15/15 stable |
| Is the race forced deterministically? | **Yes** | Gate wrapper holds the worker *before* acquisition; event handshake, not sleeps |
| Does it measure actual concurrent writes? | **Yes** | `state["max"]` and per-item `state["writes"][tag]` under a real `threading.Lock` |
| Can it pass accidentally because the worker was never scheduled? | **No** | Assertions 4 and 5 (`worker_gate_acquisitions >= 1`, `second_started is True`). Proven live in §6.1 |
| Are all waits bounded? | **Yes** | `_F02_TIMEOUT * 3` / `_F02_TIMEOUT` / `loop.time()` deadlines; `finally` releases both events |
| Is it stable across repeated runs? | **Yes** | 15/15 both directions |

### 6.1 Anti-false-pass guard proven live

I disabled the `worker_at_gate.set()` signal in a **copy** and re-ran:

```
>       assert reached_gate is True, "خيط العامل ما وصلش للبوّابة — السيناريو ما اتحققش"
E       AssertionError: خيط العامل ما وصلش للبوّابة — السيناريو ما اتحققش
E       assert False is True
1 failed
```

The test fails rather than passing vacuously, so the guard is genuinely load-bearing.

### 6.2 No shim leakage

- Full module in fixed order: **45 passed**
- New test first, then the whole module: **45 passed** (order-insensitive)
- After the run: `bot.attachments.threading is threading` → **True**, and
  `threading.Lock is threading.Lock` → **True**

`monkeypatch.setattr` restores the module attribute at teardown, so the shim cannot leak into other
tests or into later test sessions.

### 6.3 Independence status

```
INDEPENDENCE_NOT_ESTABLISHED
```

Measured in this environment:

| Isolation mechanism | Status |
|---|---|
| Docker socket | **ABSENT** |
| podman | **ABSENT** |
| bwrap | **ABSENT** |
| firejail | **ABSENT** |
| lxc-start | **ABSENT** |
| systemd-nspawn | **ABSENT** |
| Second agent server | only `:60000`, which hosts **this** session |

A second directory or a second agent on the same host, filesystem, and uid is **not** independent and
is not described as such. Publishing code or changing repository settings to manufacture an
environment is forbidden by the task and was not done. The mutation evidence in §3 is a same-agent
verification, clearly labelled as such.

---

## 7. Python 3.11 and CI status

| Item | Status |
|---|---|
| Python 3.11 | **UNVERIFIED** — `python3.11`, `python3.12`, `python3.10` all absent; no pyenv/conda. All results are Python **3.13.15** only. |
| CI | **NOT RUN** — no push, no PR, no `workflow_dispatch` (CI has none). No claim of a CI pass is made. |

The new test uses only `threading.Lock`/`Event` wrappers, `asyncio.ensure_future`,
`asyncio.wait_for`, and `monkeypatch` — all identical on 3.11 — but compatibility is **not** inferred
from source inspection. CI (3.11 & 3.13) must confirm it.

---

## 8. D6 status

**D6 remains DEFERRED and OPEN.** Repeated raw cancellation is **not** safe and this task does not
address it or claim otherwise. D6 was out of scope; no code or test for it was added. The earlier
review's live reproduction (second raw cancel ⇒ lock released under an active writer ⇒
`max_concurrent_writers=2`) still stands unchanged.

---

## 9. Remaining limitations

1. **Independence not established** — this is a same-agent verification. F-02's independent-review
   requirement is still outstanding.
2. **Python 3.11 unverified** — only 3.13.15 available locally.
3. **CI not run** — no evidence of a CI pass; triggering it was out of scope.
4. **D6 open** — repeated raw cancellation remains unsafe; deferred by owner decision.
5. **Owner acceptance** — must be tracked separately; not granted or implied by this report.
6. The test controls ordering via a `threading` shim. This is a deliberate, documented white-box
   technique: it pins the interleaving without altering production semantics, and it is the only
   reliable way to exercise a window that is otherwise microseconds wide. It does not weaken the
   behavioural nature of the assertions, which are all about writes and concurrency counts.

---

## 10. Acceptance criteria

| # | Criterion | Met | Evidence |
|---|---|---|---|
| 1 | New test passes against correct implementation | **YES** | §3.3, §3.5 (15/15) |
| 2 | Exact M4′ mutation fails for the expected behavioural reason | **YES** | §3.3 (`writes_i1 == 1`), §3.4, §3.5 (15/15) |
| 3 | Test is deterministic across repeated runs | **YES** | §3.5 — 15/15 both directions |
| 4 | Focused and full regression suites pass | **YES** | §4 — 24 / 45 / 101 / 3443 / 280 |
| 5 | Production implementation remains unchanged | **YES** | §5.1 — `b98d561f…` byte-identical |
| 6 | No unrelated file modified | **YES** | §5.2, §5.3 — append-only; git totals unchanged |

**All six criteria met.**

---

## 11. Changed files

| File | Change | Reason |
|---|---|---|
| `tests/test_def011_fs_offload.py` | **+149 lines appended** (0 removed) | Adds the behavioural regression test for `F-02-REV-01` |
| `docs/reviews/OHB2-WP07-DEF011-F02-REV01-REGRESSION-AND-VERIFICATION-REPORT.md` | **new** | This report |

**`bot/attachments.py` — not modified.** No other file was modified.

---

## 12. Recommended next action

1. Add CI coverage: let the real CI workflow run on Python 3.11 **and** 3.13 to close the
   UNVERIFIED item.
2. Obtain the still-outstanding **genuinely independent** review of F-02 (implementation + this
   test), in an environment that actually provides isolation.
3. Keep **D6 deferred and open** until a separate, authorised task addresses repeated raw
   cancellation.
4. Track **owner acceptance** separately.

**This report does not claim that F-02 is closed, that WP-07 or DEF-011 is complete, that an
independent review occurred, or that Python 3.11 or CI passed.**
