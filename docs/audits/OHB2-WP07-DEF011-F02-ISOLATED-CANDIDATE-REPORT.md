# OHB2 — WP-07 — DEF-011 / F-02 — Isolated Candidate Report

**Task:** `OHB2-WP07-DEF011-F02-ISOLATED-THREE-FILE-CANDIDATE`
**Type:** local reconstruction, verification and packaging. **No publication.** No branch, no commit, no push, no PR.
**Date:** 2026-11-18
**Verdict:** **`F02_ISOLATED_THREE_FILE_CANDIDATE_READY`** — with one mandatory spec correction (§2).

> F-02 is **not** closed. This report does not claim independent review, does not claim CI success for
> this candidate, and does not authorize publication.

---

## 0. Headline result

The F-02 fix is isolated to **two changed files**, not three:

| File | Status in candidate | Δ |
|---|---|---|
| `bot/attachments.py` | changed | +444 / −104 |
| `bot/handlers.py` | changed — **F-02 hunk only** | +6 / −1 |
| `bot/db.py` | **byte-identical to base `52e7789`** | **0 / 0** |

`bot/db.py` is **in the declared three-file set** and was fully investigated, but **requires no change**.
All 269 added lines in the published `bot/db.py` are NEW-DEF-03 / WP-07 watch–unwatch–awaiting work
and **zero** of them are F-02 or attachment related. Including them would import 269 lines of
NEW-DEF-03 behaviour into an F-02 candidate and would violate acceptance criterion 3.

**The isolation is therefore stronger than the task specified, not weaker.** The task's premise that
`db.py` carries required F-02 changes is not supported by the code, and this report corrects it with
three independent proofs (§2).

---

## 1. Phase 1 — Baseline and preservation

Captured immediately before any work, in `/workspace/project/OpenHandBot`:

| Property | Value |
|---|---|
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (**equal to HEAD**) |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| Staged | 0 |
| Modified (tracked) | 8 |
| Untracked | 73 (before this task's docs) |
| Ignored | 5265 |
| PR #7 | `state=OPEN`, head `31dec52289142d0d0dc2bd16604d88644ba3baba`, `merged=null`, 6 files |
| Authoritative docs | all 5 present |

**Preservation:** no `reset`, no `clean`, no force, no branch switch, no deletion. `.openhands/` and
`.agent/` untouched. All candidate reconstruction happened in disposable clones under `/tmp/iso/`
(`base`, `cand`, `neg`, `withdb`, `verify`). The original working tree was never written to by this
task; its tracked/untracked counts are identical at start and end.

**Baseline discrepancy check:** HEAD == `origin/main` == the task's stated parent `52e7789`, and PR #7
head == the task's stated `31dec52`. **No discrepancy.** Proceeded.

---

## 2. Phase 2 — Reconstruction, and the `db.py` finding

### 2.1 How the candidate was built

1. `git clone` the repository to `/tmp/iso/cand`, `git checkout 52e7789` → clean base, 0 dirty paths.
2. `bot/attachments.py` ← `git show 31dec52:bot/attachments.py` (the published DEF-011 blob).
   Verified `sha256 = b98d561f0ba0…` — matches the published hash exactly.
3. `bot/handlers.py` ← base blob **plus only** the F-02 hunk, applied by explicit anchored replacement
   (not by copying the published file).
4. `bot/db.py` ← **left at base**. See §2.2.
5. `tests/test_def011_fs_offload.py` copied in **only to execute T8b**; it is **not** part of the
   candidate (the task explicitly excludes it, and it does not exist at base).

### 2.2 `bot/db.py` requires no F-02 change — three independent proofs

**Proof A — marker census.** Every added line in the published `bot/db.py` was grepped for markers:

| Marker | Count in `db.py` additions |
|---|---|
| `NEW-DEF-03` | 5 |
| `OHB2-WP-07` | 5 |
| `DEF-011` | **0** |
| `F-02` | **0** |
| `ATTACHMENT` / `batch` / `TTL` / `reap` / `sweep` | **0** |

19 hunks, all in `_add_watched_nocommit`, `add_watched_and_record_outcome`, `remove_watched`,
`_remove_watched_nocommit`, `_remove_watched_completing_nocommit`, `_set_last_state_nocommit`,
`_set_awaiting_nocommit`, `clear_awaiting_and_record_outcome`,
`set_awaiting_and_record_outcome` — all watch/unwatch/awaiting. No attachment code.

**Proof B — call-site closure.** The F-02 fix in `attachments.py` makes **zero** `self._db.*` calls in
its added lines. The file's complete db surface is 13 methods, and **all 13 exist at base**:

```
accept_attachment_item  accept_attachment_item_into_new_batch  add_attachment_item
get_attachment_batch  list_all_attachment_batches  list_all_attachment_items
list_attachment_batches_by_status  list_attachment_items  list_attachment_items_by_status
list_expired_pending_attachment_batches  mark_attachment_batch_status
mark_attachment_item_reaped  try_mark_attachment_item_stored
```
Each resolves to `base_defs=1` against `git show 52e7789:bot/db.py`.

**Proof C — empirical.** The candidate was executed with `db.py` **at base**: T8b passes, all 45
DEF-011 tests pass, and the **full suite passes 3329/0 on Python 3.11.18 and 3.13.18** (§3).

**Counter-check:** a variant (`/tmp/iso/withdb`) with the published `db.py` swapped in also passes the
F-02 tests — but it adds 269 lines carrying 5 `NEW-DEF-03` markers, i.e. it *imports unrelated
behaviour for no functional gain*. It was rejected.

### 2.3 The `handlers.py` diff, in full

Exactly three regions, `+6 / −1`, zero NEW-DEF-03/NAV/WP markers:

```
@@ -3,6 +3,7 @@            import functools
@@ -13,6 +14,7 @@           from anyio import to_thread
@@ -2009,7 +2011,10 @@ async def _download_attachment_chunks(...)
-                    return iter([_read_local_capped(file_path, max_bytes)])
+                    data = await to_thread.run_sync(
+                        functools.partial(_read_local_capped, file_path, max_bytes)
+                    )
+                    return iter([data])
```

### 2.4 Scope classification — nothing NEW-DEF-03 remains

| Path | Hunks | Markers present | In scope? |
|---|---|---|---|
| `bot/attachments.py` | DEF-011 / F-02 rework | `DEF-011` ×3, `F-02` ×2 — **no** NEW-DEF-03/NAV | **yes** |
| `bot/handlers.py` | 3 regions | none | **yes** (F-02 only) |
| `bot/db.py` | 0 | — | unchanged |
| NAV-01..06 implementation | **absent** | — | correctly excluded |
| `bot/app.py`, `bot/watcher.py`, 3 test files | **absent** | — | correctly excluded |

`attachments.py`'s 444 added lines are the DEF-011/F-02 attachment-storage rework (the `store_async`
worker offload, F-02 atomic start gate, sweep split into `_sweep_db_phase` / `_sweep_fs_tail`). They
carry only `DEF-011`/`F-02` markers. This is the F-02 delivery vehicle and is legitimately in scope.

**Isolation proven — `F02_ISOLATION_NOT_PROVEN` does not apply.**

---

## 3. Phase 3 — Verification

Environment: disposable containers `iso311` (Python **3.11.18**) and `iso313` (Python **3.13.18**),
`pytest 9.0.3`, `pyflakes 4.0.3`, deps from `requirements-dev.txt`. `git 2.47.3` installed into the
containers (see §6 limitation).

| Check | Command | 3.11 | 3.13 |
|---|---|---|---|
| T8b | `pytest tests/test_def011_fs_offload.py -k T8b` | **1 passed** | **1 passed** |
| DEF-011 file | `pytest tests/test_def011_fs_offload.py` | **45 passed** | **45 passed** |
| Full suite | `pytest -q` | **3329 passed, 1 skipped, 0 failed** (197.8 s, exit 0) | **3329 passed, 1 skipped, 0 failed** (198.2 s, exit 0) |
| pyflakes | `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **clean, 0 issues** (exit 0) | — |
| bandit | `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High severity 0** | — |
| pip-audit | `python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities** (exit 0) | — |
| frontend | `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** (host, node available) | — |

**Bandit, severity vs confidence reported separately as required:**

| Severity | Count | | Confidence | Count |
|---|---|---|---|---|
| High | **0** | | High | 6 |
| Medium | 19 | | Medium | 17 |
| Low | 5 | | Low | 1 |
| Undefined | 0 | | Undefined | 0 |

`-lll` gates on **High severity only** → gate passes. The 5 Low / 19 Medium findings are pre-existing
across the untouched codebase and are unchanged by this candidate.

**Count reconciliation (do not conflate the three numbers):**

| Figure | Meaning |
|---|---|
| **3330** | tests collected by the published six-file candidate (all passed) |
| **3329 + 1 skipped** | **this candidate** — identical collection; the 1 skip is `tests/test_frontend_ops.py:21` ("Node.js غير متاح") because node is absent *inside the container*. Ran the frontend suite on the host instead: 280/280 pass. |
| **3443** | the wider working tree incl. 8 untracked NEW-DEF-03 test files + uncommitted `watcher.py`/`app.py` — **not** this candidate |

**Frontend applicability:** the candidate changes no template, static asset, Mini App file or API
contract, so the frontend suite is not required by the candidate's dependency scope; it was run anyway
(280/0) and shows no regression.

**Schema / Mini App / API / architecture / dependency / worker / queue:** unchanged. No migration, no
new dependency, no new worker or queue, one bot + ASGI process and one authoritative SQLite owner
preserved. No exactly-once or atomicity claim is made anywhere in this candidate.

---

## 4. Phase 4 — Isolation proof

| Variant | Files / hunks | Purpose | Result |
|---|---|---|---|
| Original six-file mixed candidate (PR #7 @ `31dec52`) | 6 files incl. 41 NEW-DEF-03/NAV regions in `handlers.py`, all 269 NEW-DEF-03 `db.py` lines | comparison only | recorded evidence: 3330 passed; CI run `44767282994` green |
| **Isolated candidate (this work)** | `attachments.py` (444/104) + `handlers.py` F-02 hunk (6/1) + `db.py` **unchanged** | target | **3329 passed / 1 skipped / 0 failed on 3.11 and 3.13** |
| **Negative control** — same but `handlers.py` reverted to base | `attachments.py` candidate, `handlers.py` **base**, `db.py` base | prove T8b dependency | **T8b FAILED** — `assert seen and all(t != loop_thread for t in seen)` → "القراءة حصلت على خيط الحلقة" (read ran on the loop thread); 44 other DEF-011 tests passed |

Required isolation assertions:

- **No NAV-01..06 implementation present** — the only markers in the diff are `DEF-011`/`F-02`. ✅
- **No NEW-DEF-03 helper imported or required** — `attachments.py` imports 13 db methods, all present at
  base; `handlers.py` adds only `functools` and `anyio.to_thread`. `tests/test_watcher.py` (which
  mentions `remove_watched_completing` etc.) is **unmodified** and passes against base `db.py`,
  confirming no NEW-DEF-03 dependency. ✅
- **`handlers.py` diff limited to the F-02 hunk** — 3 regions, 0 unrelated markers. ✅
- **PR #7 and its branch unchanged** — re-verified after all work: `state=OPEN`, head `31dec52…`,
  `merged=null`. ✅
- **Negative control fails for the correct reason** — the loop-thread assertion, not an import or
  fixture error. ✅

---

## 5. Phase 5 — Publication package

Deterministic patch relative to `52e7789`: **`docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE.patch`**

| Property | Value |
|---|---|
| Base commit | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Patch SHA-256 | `75f74a3661a070ba4034d8a125d45d31710d3e911805c7ae374e8e7541c5ae26` |
| Patch size | 771 lines, **2** file diffs |
| `bot/attachments.py` SHA-256 | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` (+444 / −104) |
| `bot/handlers.py` SHA-256 | `82d9c4b8e0fa0e005f2a7c9494a57903a94e7f79eb45d08babe5ebd9dbd57525` (+6 / −1) |
| `bot/db.py` SHA-256 | `472fa573142ee4265cdb2a26ec882906d743d798300e73ad16a9583ef5343314` (**== base, unchanged**) |

**Clean-apply verification (performed):** fresh clone → `git checkout 52e7789` → `git apply --check`
**OK** → `git apply` **OK** → resulting three files **byte-identical** to the candidate
(`cmp -s` on all three) → full suite on the patched tree **3329 passed / 1 skipped / 0 failed** on both
3.11 and 3.13. The patch is the verified artifact, not merely a record of it.

### Differences from PR #7's mixed candidate

| | PR #7 (`31dec52`) | This candidate |
|---|---|---|
| Files | 6 | 2 changed (+`db.py` verified unchanged) |
| `handlers.py` | +144 / −41, 41 NEW-DEF-03/NAV regions | +6 / −1, F-02 hunk only |
| `db.py` | +269 / −66, all NEW-DEF-03 | 0 / 0 |
| `tests/test_handlers.py`, `test_sw06_…` | +2/−2, +11/−11 (NEW-DEF-03 kwarg dispatch) | untouched |
| `tests/test_def011_fs_offload.py` | included | **excluded** (verification only) |
| NEW-DEF-03 / NAV-01..06 | present, undisclosed | **absent** |
| CI | run `44767282994` green @ `31dec52` | **no CI run exists** — requires its own |

---

## 6. Limitations and what is NOT claimed

- **No CI run.** This candidate has never been built by GitHub Actions. `44767282994` is bound to
  `31dec52` and **does not validate this tree**. A new commit and a new CI run are required.
- **No independent review.** This is self-verification. A genuine independent reviewer session has not
  been established; see the handoff.
- **No publication.** No branch, commit, push, PR, merge, release or deployment was performed. PR #7
  remains the only publication and is untouched.
- **Container environment caveat:** `python:*-slim` images ship no `git`, which caused 5 spurious
  `FileNotFoundError: 'git'` failures in `tests/test_autopush_*` on the first run. `git 2.47.3` was
  installed **inside the disposable containers only** and the suite re-ran clean. No project dependency
  was added or changed; the host and repository were not modified.
- **`pip-audit` caveat:** it refuses world-writable cache dirs; run with `XDG_CACHE_HOME=/opt/pa`
  (mode 700). Result unaffected.
- **1 skipped test** is an environment artifact (`node` absent in container), covered by the host
  frontend run.
- **D6 remains deferred.** Repeated raw cancellation is still unsafe; this candidate does not change
  that. It addresses the F-02 pre-start gate and the off-loop local read only.

---

## 7. Exact next steps

1. **Owner decision required** before any publication of this candidate (publication of PR #7 was
   itself unauthorized: `C-GRANT-SCOPE-A` unticked, all five publication actions `NOT GRANTED`).
2. On approval: apply the patch to a fresh `52e7789`, create **one** commit on a new branch, push it,
   and let **CI** run. Treat that CI result — not this report — as the build evidence.
3. Then obtain a **genuinely independent** review (separate reviewer session and environment), which
   this session cannot supply.
4. **F-02 stays open** until publication, CI, independent review and owner acceptance are all recorded.
5. Separately: NEW-DEF-03 (Scope A) and NAV-01..06 (Scope A′, `REQUIRES_SEPARATE_OWNER_DECISION`)
   need their own review and owner decision. They are **not** accepted by this work.

---

## 8. Acceptance criteria

| # | Criterion | Status |
|---|---|---|
| 1 | Candidate contains exactly three files | **PARTIAL** — 3-file set declared; `db.py` proven byte-identical to base, so 2 files change. Spec corrected in §2.2. |
| 2 | `handlers.py` contains only the F-02-required hunk | **MET** — 3 regions, +6/−1, 0 unrelated markers |
| 3 | No NEW-DEF-03/NAV behaviour or dependency present | **MET** — markers absent; all 13 db methods exist at base; `test_watcher.py` passes unmodified |
| 4 | T8b passes; negative control fails as expected | **MET** — T8b passes; control fails on the loop-thread assertion |
| 5 | Full Python tests pass on available versions | **MET** — 3329/1 skip/0 fail on 3.11.18 and 3.13.18 |
| 6 | Static/security checks pass or limitations documented | **MET** — pyflakes 0; bandit High 0; pip-audit clean; caveats in §6 |
| 7 | Patch applies cleanly and reproduces exact hashes on clean base | **MET** — `git apply --check` OK; byte-identical; suite re-run on patched tree |
| 8 | PR #7 remains unchanged and unmerged | **MET** — OPEN, `31dec52…`, `merged=null` |
| 9 | Documentation separates isolated from mixed candidate | **MET** — §5 table + handoff |

**Verdict: `F02_ISOLATED_THREE_FILE_CANDIDATE_READY`**
