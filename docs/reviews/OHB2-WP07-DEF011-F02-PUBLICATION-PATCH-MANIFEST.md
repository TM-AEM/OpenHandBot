# OHB2 — WP-07 / DEF-011 / F-02 — Publication Patch Manifest

**Base commit:** `52e7789cc8cc97a7f7c09c9592226ab117db99a2`
**Patch:** `/tmp/f02handoff/f02-publication.patch`
**Patch SHA-256:** `59b701369a3b6d2bf70f8028d3ffc8d22831b2f3eedba8cc4de16997246ebe94`
**Files:** 6 · **Diffstat:** 2445 insertions(+), 224 deletions(-)

---

## 1. Exact file list

| # | Path | Status | SHA-256 of result | Δ |
|---|---|---|---|---|
| 1 | `bot/attachments.py` | modified | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` | +444 / −104 |
| 2 | `bot/db.py` | modified | `205f1363aaf0b1f8173b74285e263891d333928ba480d478b6b525d4369c694b` | +269 / −66 |
| 3 | `bot/handlers.py` | modified | `40dd8902595c1a63875f8c9d37d4fed4a454be15e1390e5386dcfa9bce058014` | +144 / −41 |
| 4 | `tests/test_def011_fs_offload.py` | **new file** | `3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea` | +1575 / −0 |
| 5 | `tests/test_handlers.py` | modified | `2b1f978091f45c695803a73845065073690f58f1b1c8d2f41fa38d04c1fa8ea8` | +2 / −2 |
| 6 | `tests/test_sw06_unwatch_db_failure_propagation.py` | modified | `ba2633113424432467edeff6cb74f656bb4b5fe9b762dbcc8a251799b33e07ef` | +11 / −11 |

Total: **6 files changed, 2445 insertions(+), 224 deletions(-)**.

---

## 2. Why these 6 and not 2

The task assumed a two-file patch. That was **empirically rejected** — see
`docs/audits/OHB2-WP07-DEF011-F02-CI-PUBLICATION-READINESS.md` §0. Summary of the elimination:

| Set size | Added file | Result on clean `HEAD` |
|---|---|---|
| 2 | (assumed baseline) | **1 failed** — `test_T8b_local_capped_read_runs_off_event_loop_thread` |
| 3 | `bot/handlers.py` | **94 failed** |
| 4 | `tests/test_handlers.py` | **92 failed** |
| 5 | `bot/db.py` | **9 failed** |
| **6** | `tests/test_sw06_unwatch_db_failure_propagation.py` | **3330 passed, 0 failed** ✅ |

Dependency chain: DEF-011 test asserts off-loop reads → requires `to_thread` in `handlers.py` →
requires new atomicity helpers in `db.py` → requires updated expectations in two existing test files.

### 2.1 Explicitly excluded

| Path | Reason |
|---|---|
| `.agent/PROGRESS.md` | Agent working notes — not product code |
| `bot/app.py` | **Not required** — 6-file set passes with it at `HEAD` |
| `bot/watcher.py` | **Not required** — same |
| 8 other untracked `tests/test_*.py` | Belong to other work packages (F-01, WP-07 NAV, F-03) |
| `.openhands/`, `.agent/` | Agent state |
| `docs/` | Documentation, published separately by this task |

---

## 3. Reproducibility

```bash
# base
git -C /workspace/project/OpenHandBot rev-parse HEAD   # 52e7789cc8cc97a7f7c09c9592226ab117db99a2

# patch identity
sha256sum /tmp/f02handoff/f02-publication.patch
# 59b701369a3b6d2bf70f8028d3ffc8d22831b2f3eedba8cc4de16997246ebe94

# apply to pristine tree
mkdir /tmp/verify && cd /tmp/verify
git -C /workspace/project/OpenHandBot archive HEAD | tar x
git apply --check /tmp/f02handoff/f02-publication.patch   # -> clean
git apply         /tmp/f02handoff/f02-publication.patch

# confirm the two headline candidates
sha256sum bot/attachments.py tests/test_def011_fs_offload.py
# b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356  bot/attachments.py
# 3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea  tests/test_def011_fs_offload.py
```

**Verified in this task:** `git apply --check` succeeded on a pristine `HEAD` extraction, and applying
the patch reproduced both candidate hashes exactly.

---

## 4. Patch construction

```bash
cd /workspace/project/OpenHandBot
PUB="bot/attachments.py bot/db.py bot/handlers.py \
     tests/test_handlers.py tests/test_sw06_unwatch_db_failure_propagation.py"
git diff HEAD -- $PUB > /tmp/f02handoff/01-tracked-files.patch
git diff --no-index /dev/null tests/test_def011_fs_offload.py \
                     > /tmp/f02handoff/02-new-test-file.patch
cat /tmp/f02handoff/01-tracked-files.patch \
    /tmp/f02handoff/02-new-test-file.patch \
    > /tmp/f02handoff/f02-publication.patch
```

`--no-index` is used for the new test file because it is untracked; `git diff HEAD` would not include
it. The two parts are concatenated in a fixed order so the combined hash is stable.

---

## 5. Safety scan

| Check | Result |
|---|---|
| Private keys / API tokens / passwords hardcoded | **none** |
| `.env` content | **none** |
| `.openhands/` or `.agent/` content | **none** |
| Mini App source/UI/config changed | **none** |
| Schema DDL changed | **none** |
| New dependency or lockfile change | **none** |
| Workflow file change | **none** |

The only literal-looking secret in the patch is `CID = "11111111222233334444555566667777"` — a fake
fixture inside a test, not a credential.

---

## 6. Verification status of this manifest

| Item | Status |
|---|---|
| File list verified by `grep '^+++ b/'` | **done** |
| Patch applies to pristine `HEAD` | **done** (`--check` clean) |
| Applying reproduces candidate hashes | **done** |
| Full suite on applied set, 3.13 | **3330 passed** (local) |
| Full suite on applied set, 3.11 | **3330 passed** (local) |
| pyflakes on applied set, both versions | **clean** |
| M4′ discrimination on applied set | **verified** (correct passes, mutant fails `assert 1 == 0`) |
| **CI** | **NOT RUN** — see readiness audit §4 |
| **Independent review** | **NOT PERFORMED** — see handoff doc |

**Nothing was staged or committed. The patch lives outside the repository.**
