# OHB2 — WP-07 — DEF-011 / F-02 — Isolated Candidate: Independent Review Handoff

**For:** an **independent** reviewer (separate session, separate environment)
**Candidate:** isolated F-02, base `52e7789cc8cc97a7f7c09c9592226ab117db99a2`
**Patch SHA-256:** `75f74a3661a070ba4034d8a125d45d31710d3e911805c7ae374e8e7541c5ae26`
**Prepared:** 2026-11-18

---

## 1. Read this first — five facts that must not be blurred

1. **PR #7 contains mixed scope.** Its `bot/handlers.py` carries **41 change regions** of
   NEW-DEF-03 / NAV-01..06 work beside **one** 6-line F-02 hunk, and its `bot/db.py` carries
   **269 lines that are entirely NEW-DEF-03**. That was **not disclosed** in the publication report,
   the earlier handoff, or the closure report — which in fact asserts "no unrelated change".
2. **This candidate excludes NEW-DEF-03 and NAV-01..06 entirely.** No NAV-01..06 implementation, no
   NEW-DEF-03 helper, no `watcher.py`/`app.py`, no NEW-DEF-03 test edits. The only markers in the diff
   are `DEF-011` and `F-02`.
3. **PR #7's CI result does not validate this candidate.** Run `44767282994` is bound to commit
   `31dec52`. This candidate is a **different tree**. Its green result is evidence about `31dec52`
   only.
4. **This candidate requires its own publication commit and its own CI run.** Until then it has
   **no** CI evidence — only the local evidence in §4.
5. **D6 remains deferred. Repeated raw cancellation is still unsafe.** This candidate addresses the
   F-02 pre-start gate and the off-loop local read. It does not fix, and does not claim to fix, D6.

---

## 2. What you are reviewing

A two-file change against `52e7789` (declared as a three-file set; `bot/db.py` is proven unchanged):

| Path | SHA-256 | Δ |
|---|---|---|
| `bot/attachments.py` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` | +444 / −104 |
| `bot/handlers.py` | `82d9c4b8e0fa0e005f2a7c9494a57903a94e7f79eb45d08babe5ebd9dbd57525` | +6 / −1 |
| `bot/db.py` | `472fa573142ee4265cdb2a26ec882906d743d798300e73ad16a9583ef5343314` | 0 / 0 — **== base** |

The `handlers.py` diff is exactly three regions: `import functools`, `from anyio import to_thread`,
and the `_download_attachment_chunks` local-read offload. Nothing else.

Full reconstruction steps, per-file hashes, apply commands and evidence:
`docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE-MANIFEST.md`.
Analysis and verdict rationale: `docs/audits/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE-REPORT.md`.

---

## 3. Why `bot/db.py` is in the set but unchanged

The task specified three files including `bot/db.py`. Investigation shows `db.py` needs **no** F-02
change, and including the published `db.py` would import 269 lines of NEW-DEF-03. Three independent
proofs:

- **Markers:** every added `db.py` line carries `NEW-DEF-03`/`OHB2-WP-07`; **zero** carry
  `DEF-011`/`F-02`, and **zero** mention attachment/batch/TTL/reap/sweep.
- **Call sites:** the F-02 fix in `attachments.py` makes **zero** db calls in its added lines; the file's
  13 db methods all exist at base.
- **Empirical:** with `db.py` at base, T8b passes, all 45 DEF-011 tests pass, and the full suite passes
  **3329/0** on 3.11 and 3.13.

**Please challenge this specifically.** If you find any F-02-relevant `db.py` hunk, the candidate's
scope is wrong and the verdict should fall to `F02_ISOLATION_NOT_PROVEN`.

---

## 4. Local evidence (self-verified — not CI, not independent)

| Check | 3.11.18 | 3.13.18 |
|---|---|---|
| T8b | 1 passed | 1 passed |
| DEF-011 file (45) | 45 passed | 45 passed |
| Full suite | **3329 passed, 1 skipped, 0 failed** (exit 0) | **3329 passed, 1 skipped, 0 failed** (exit 0) |
| pyflakes | 0 issues | — |
| bandit `-lll` | High severity **0** (Medium 19, Low 5 pre-existing) | — |
| pip-audit | no known vulnerabilities | — |
| frontend `node --test` | 280 pass / 0 fail | — |
| Negative control (no F-02 hunk) | **T8b FAILED** on the loop-thread assertion | — |

The single skip is `tests/test_frontend_ops.py:21` ("Node.js غير متاح"): `node` is absent in the
container, so the frontend suite was run on the host.

**This is self-verification by the same agent that built the candidate. It is not independent
evidence.** Reproduce it yourself.

---

## 5. Suggested review focus

1. **Is the F-02 hunk correct and complete?** `_read_local_capped` moved into `to_thread.run_sync` via
   `functools.partial`; the cap and fail-closed behaviour preserved; `AttachmentTooLargeError` still
   propagates unchanged.
2. **Is anything missing that F-02 needs?** The strongest attack: find a required F-02 change that is
   absent. Note that `tests/test_def011_fs_offload.py` is **not** in the patch.
3. **Is anything extra present?** Confirm the `handlers.py` diff has exactly 3 regions and no
   NEW-DEF-03/NAV behaviour.
4. **`attachments.py`'s 444 added lines** are the DEF-011/F-02 storage rework (`store_async` worker
   offload, F-02 atomic start gate, sweep split into `_sweep_db_phase` / `_sweep_fs_tail`). They carry
   only `DEF-011`/`F-02` markers — but they are the bulk of the change and deserve the closest read.
5. **Concurrency/atomicity claims.** No exactly-once Telegram delivery and no SQLite-Telegram atomicity
   may be claimed. Verify none is.
6. **Architecture.** One bot + ASGI process, one authoritative SQLite owner, existing outbox/workers
   only. No new worker system, no parallel polling, no new queue, no schema change, no new dependency,
   no Mini App change.

---

## 6. Reproduce

```bash
git clone https://github.com/TM-AEM/OpenHandBot.git /tmp/f02-review
cd /tmp/f02-review && git checkout 52e7789cc8cc97a7f7c09c9592226ab117db99a2
git apply --check docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE.patch   # from the repo
git apply         docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE.patch
sha256sum bot/attachments.py bot/handlers.py bot/db.py     # must match §2
cp tests/test_def011_fs_offload.py /tmp/ 2>/dev/null       # not in the patch; copy from the working tree
python -m pytest -q                                        # expect 3329 passed, 1 skipped
```

Negative control: revert `bot/handlers.py` to `52e7789` and re-run
`pytest tests/test_def011_fs_offload.py -k T8b` — T8b must **fail**.

---

## 7. What you must not accept on my word

- That this candidate is correct because the local suite is green.
- That this candidate is build-verified. **It is not: it has no CI run.**
- That F-02 is closed. **It is not.**
- That NEW-DEF-03 or NAV-01..06 is accepted. **Neither is.**
- That PR #7 is ready to merge. It bundles unaccepted scope and was published without a signed grant
  (`C-GRANT-SCOPE-A` unticked; all five publication actions `NOT GRANTED`).

---

## 8. State at handoff

- PR #7: **OPEN, unmerged**, head `31dec52289142d0d0dc2bd16604d88644ba3baba` — untouched.
- Local repo: HEAD `52e7789` = `origin/main`; 0 staged; no branch or commit created by this task.
- `.openhands/` and `.agent/` untouched.
- D6: unchanged and still deferred.
- F-02: **open**. NEW-DEF-03 (Scope A) and NAV-01..06 (Scope A′, `REQUIRES_SEPARATE_OWNER_DECISION`):
  **not accepted**.

---

## 9. Requested outcome

State explicitly, for the **isolated** candidate:

1. Whether the F-02 isolation holds (especially the `db.py` finding in §3).
2. Whether T8b is genuinely required and genuinely passes, with the negative control failing.
3. Whether any NEW-DEF-03/NAV behaviour or dependency is present.
4. Whether the architecture and safety constraints in §5.5–5.6 are respected.
5. Any blocking defect.

And, separately, state whether **publication** of this candidate is appropriate given that the earlier
publication of PR #7 had no signed grant.
