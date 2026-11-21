# OHB2 — WP-07 — DEF-011 / F-02 — Isolated Candidate Manifest

**Base commit:** `52e7789cc8cc97a7f7c09c9592226ab117db99a2`
**Patch:** `docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE.patch`
**Patch SHA-256:** `75f74a3661a070ba4034d8a125d45d31710d3e911805c7ae374e8e7541c5ae26`
**Verdict:** `F02_ISOLATED_THREE_FILE_CANDIDATE_READY` (see `docs/audits/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE-REPORT.md`)

---

## 1. Declared three-file set

| # | Path | Candidate SHA-256 | Base SHA-256 | Δ | Changed? |
|---|---|---|---|---|---|
| 1 | `bot/attachments.py` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` | `7e448b52ac3b5f470cb23e5de073161539e61b47a7c89c8fe5c4e65ec0c2276c` | +444 / −104 | **yes** |
| 2 | `bot/handlers.py` | `82d9c4b8e0fa0e005f2a7c9494a57903a94e7f79eb45d08babe5ebd9dbd57525` | `96325cf2d8f24d291f0bf2f664188678ff03e6f27e914410803f4216affb4f6a` | +6 / −1 | **yes** |
| 3 | `bot/db.py` | `472fa573142ee4265cdb2a26ec882906d743d798300e73ad16a9583ef5343314` | `472fa573142e…` | 0 / 0 | **NO — byte-identical to base** |

> **`bot/db.py` is unchanged.** It belongs to the declared three-file set and was exhaustively
> investigated, but it carries **no** F-02 change. All 269 added lines in the published `db.py` are
> NEW-DEF-03 / WP-07 watch–unwatch–awaiting work. The patch therefore contains **2** file diffs.
> See report §2.2 for the three independent proofs.

Total: **+450 / −105** across 2 changed files.

---

## 2. `bot/handlers.py` — the complete diff

Three regions, `+6 / −1`, zero NEW-DEF-03 / NAV / WP markers.

```
@@ -3,6 +3,7 @@ from __future__ import annotations
 import asyncio
 import errno
+import functools
 import io

@@ -13,6 +14,7 @@ from datetime import datetime, timezone
 import httpx
+from anyio import to_thread
 from telegram import InputFile, Update

@@ -2009,7 +2011,10 @@ async def _download_attachment_chunks(context, file_id: str, max_bytes: int):
             if os.path.isfile(file_path):
                 try:
-                    return iter([_read_local_capped(file_path, max_bytes)])
+                    data = await to_thread.run_sync(
+                        functools.partial(_read_local_capped, file_path, max_bytes)
+                    )
+                    return iter([data])
                 except AttachmentTooLargeError:
                     raise
```

Purpose: the capped local read of a local-Bot-API file must not block the event loop. Asserted by
`test_T8b_local_capped_read_runs_off_event_loop_thread`.

---

## 3. Excluded paths — confirmed absent from the patch

| Path | Why excluded | Present in patch? |
|---|---|---|
| `tests/test_def011_fs_offload.py` | excluded by task; absent at base | **no** (used only to execute T8b) |
| `tests/test_handlers.py` | NEW-DEF-03 kwarg dispatch only | **no** |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | NEW-DEF-03 kwarg dispatch only | **no** |
| `bot/app.py` | NEW-DEF-03 | **no** |
| `bot/watcher.py` | NEW-DEF-03 (`unwatch(update_id=…)`) | **no** |
| NAV-01..06 implementation | out of scope, unaccepted | **no** |
| Mini App (source/UI/assets/config/tests/docs) | forbidden | **no** |

---

## 4. Reproducible apply and verification

```bash
# 1. fresh base
git clone https://github.com/TM-AEM/OpenHandBot.git /tmp/f02
cd /tmp/f02
git checkout 52e7789cc8cc97a7f7c09c9592226ab117db99a2

# 2. apply (deterministic; verified `git apply --check` OK)
git apply --check /path/to/docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE.patch
git apply         /path/to/docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE.patch

# 3. hashes must equal §1 exactly
sha256sum bot/attachments.py bot/handlers.py bot/db.py

# 4. verify T8b (the test file is NOT part of the patch — copy it in for verification only)
cp /path/to/tests/test_def011_fs_offload.py tests/
python -m pytest tests/test_def011_fs_offload.py -q -k T8b      # expect 1 passed
python -m pytest tests/test_def011_fs_offload.py -q             # expect 45 passed
python -m pytest -q                                             # expect 3329 passed, 1 skipped
python -m pyflakes bot/ automation/ tools/ main.py tests/       # expect 0 issues
python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613  # expect High severity 0
python -m pip_audit -r requirements-dev.txt                     # expect no known vulnerabilities
node --test tests/frontend/*.test.js                            # expect 280 pass, 0 fail
```

Note: `tests/test_def011_fs_offload.py` is copied in **only** to execute T8b. It is not part of the
candidate; a publication commit must decide separately whether the test ships.

---

## 5. Verification evidence

| Check | Python 3.11.18 | Python 3.13.18 |
|---|---|---|
| T8b | **1 passed** | **1 passed** |
| DEF-011 file (45) | **45 passed** | **45 passed** |
| Full suite | **3329 passed, 1 skipped, 0 failed** (exit 0) | **3329 passed, 1 skipped, 0 failed** (exit 0) |
| pyflakes | **0 issues** | — |
| bandit (`-lll`) | **High severity 0** (Medium 19, Low 5 — pre-existing) | — |
| pip-audit | **No known vulnerabilities** | — |
| frontend | **280 pass / 0 fail** (host, node 22) | — |
| Negative control (no F-02 hunk) | **T8b FAILED** — loop-thread assertion; 44 others passed | — |

The 1 skip is `tests/test_frontend_ops.py:21` ("Node.js غير متاح") — `node` is absent inside the
container; the frontend suite was run on the host instead.

---

## 6. Count reconciliation — three distinct numbers

| Figure | What it measures | Valid for this candidate? |
|---|---|---|
| **3330** | published six-file candidate (PR #7 @ `31dec52`) | no |
| **3329 + 1 skipped** | **this candidate** (same collection; 1 env skip) | **yes** |
| **3443** | wider working tree: + 8 untracked NEW-DEF-03 test files + uncommitted `watcher.py`/`app.py` | no |

---

## 7. Differences from PR #7's mixed candidate

| | PR #7 (`31dec52`) | This candidate |
|---|---|---|
| Changed files | 6 | 2 (+`db.py` verified unchanged) |
| `handlers.py` | +144 / −41, 41 NEW-DEF-03/NAV regions | +6 / −1, F-02 hunk only |
| `db.py` | +269 / −66, all NEW-DEF-03 | 0 / 0 |
| `test_handlers.py` / `test_sw06_…` | modified for NEW-DEF-03 kwargs | untouched |
| NEW-DEF-03 / NAV-01..06 | present, undisclosed | **absent** |
| CI evidence | run `44767282994` green @ `31dec52` | **none** — needs its own commit and CI run |

---

## 8. State guarantees

- PR #7: **OPEN, unmerged**, head `31dec52289142d0d0dc2bd16604d88644ba3baba` — unchanged by this work.
- Local repo: HEAD `52e7789` = `origin/main`; 8 modified / 73 untracked before and after; **0 staged**.
- No branch, commit, push, PR, merge, deployment or workflow change was made.
- `.openhands/` and `.agent/` untouched. D6 unchanged (repeated raw cancellation remains unsafe).
- F-02 is **not** closed; NEW-DEF-03 and NAV-01..06 are **not** accepted.
