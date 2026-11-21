# DEF-011-A Option B — External Reviewer Instructions

**Audience:** an external reviewer running in a genuinely separate session and working environment.
**Purpose:** reconstruct the exact candidate and perform the independent technical review.

> This package does **not** establish reviewer independence. Independence must come from your own separate
> session/environment. Do not review from the implementation session or the implementation workspace.

## 0. Preconditions

- A **genuinely separate** reviewer conversation/session (not the implementation session).
- A fresh working environment with its own checkout.
- Python 3.11+ and the repository's dev dependencies (`pip install -r requirements-dev.txt`).
- Network access to `https://github.com/TM-AEM/OpenHandBot.git` (or a local mirror of the same commit).

## 1. Clone and check out the exact base

```bash
git clone https://github.com/TM-AEM/OpenHandBot.git OpenHandBot-review
cd OpenHandBot-review
git checkout 30dfa0d6432cdb8f7787edde38f48fb482b6ced6
git rev-parse HEAD
# MUST print: 30dfa0d6432cdb8f7787edde38f48fb482b6ced6
```

## 2. Verify the package checksums (before applying anything)

From the package directory (where `SHA256SUMS` lives):

```bash
sha256sum -c SHA256SUMS
# Every packaged file must print "OK".
```

`SHA256SUMS` covers `README.md`, `candidate.patch`, `CANDIDATE-MANIFEST.md`, `REVIEW-INSTRUCTIONS.md`, and
all four files under `supporting/`. It cannot include itself.

## 3. Apply the candidate patch (isolated clone only)

```bash
# from the clone root
git apply --check /path/to/DEF011-A-OPTION-B/candidate.patch
git apply /path/to/DEF011-A-OPTION-B/candidate.patch
```

The patch contains **only** the four candidate files. It must not touch any other file.

## 4. Verify the reconstructed candidate

```bash
# from the clone root, after applying the patch
sha256sum -c /path/to/DEF011-A-OPTION-B/CANDIDATE-SHA256SUMS
# All four must print "OK":
#   bot/handlers.py
#   bot/attachments.py
#   tests/test_def011_a_option_b_limits.py
#   docs/audits/OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md

git status --porcelain
# MUST list exactly these four files and nothing else.
```

If any hash or the file list differs, **stop** and report the discrepancy; do not review an approximate
candidate.

## 5. Read the required context

Read, in this order:

1. `AGENTS.md` (repository instructions).
2. `docs/audits/OHB2-WP07-DEF011-A-DIAGNOSIS-AND-DECISION-BRIEF.md` (diagnosis / decision brief).
3. `docs/audits/OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md` (implementation report).
4. The previous review reports:
   - `docs/reviews/OHB2-WP07-DEF011-A-INDEPENDENT-REVIEW-REPORT.md`
   - `docs/reviews/OHB2-WP07-DEF011-A-INDEPENDENT-REVIEW-RETRY-REPORT.md`

The previous reviews are **historical context only**: their independence was not established, and the
implementation report's test results are **historical implementation evidence**, not independent
verification.

## 6. Perform the independent review

Use the existing independent-review prompt/task specification. At minimum verify:

- **Production wiring:** `bot/handlers.py::_attachment_service` builds the production `StagingStore` with
  `max_items_per_batch=10` and `max_total_bytes=64*1024*1024`; other callers keep `None` defaults.
- **Enforcement:** 3 MiB per-file cap, 10 files per batch, 64 MiB global staged bytes, exact-boundary
  behavior, cross-batch sharing.
- **Concurrency and failures:** `_accept_lock`, `_write_to_path`, `try_mark_attachment_item_stored`,
  failed/interrupted writes, idempotent release, expiry/restart accounting.
- **Orphan files:** preserved orphan files count toward `staging_total_bytes` and are never deleted or
  silently excluded.
- **Architecture:** no reservation ledger, no schema migration/version change, no new worker/queue/process/
  SQLite owner, no new env/config surface, no D-15/C2 or Telegram-delivery change, no F-02/D6 change.

Do **not** rely on the implementation report as a substitute for source inspection. Read the actual source
and tests.

## 7. Run the required checks independently

```bash
python -m pytest tests/test_def011_a_option_b_limits.py -v
python -m pytest -q
python -m pyflakes bot/ automation/ tools/ main.py tests/
python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
node --test tests/frontend/*.test.js
```

Also run the attachment/staging subset and the schema/ledger/default checks described in the review prompt.
Record exact commands, runtime/Python versions, exit codes, and pass/fail/skip counts. Compare against the
historical baseline **3451** and candidate **3467**; explain any discrepancy (the candidate-only count on a
clean base is 3466 because the pre-existing T-5 test is not part of this candidate).

Where practical, repeat the mutation checks (wiring removed; item cap `None`; total cap `None`; 10→11;
64 MiB→128 MiB; orphans excluded; release broken) in a **disposable copy**. Do not modify the candidate.

## 8. Write the independent review report

Create a new review report (do not overwrite the previous ones). Record:

- Reviewer session identity and independence evidence.
- Base and candidate revisions.
- Package hashes and reconstruction result.
- Production wiring, accounting, concurrency, orphan, and architecture findings.
- Independent test results and mutation results.
- Findings by severity and the final verdict.

## 9. Safety rules

- **Never modify the candidate.** Review only.
- Do not fix or improve the candidate during review.
- Do not overwrite existing audit/review reports.
- Do not change owner decisions.
- Do not commit, push, open/update a PR, merge, deploy, or activate Autopush.
- Do not use destructive Git operations (`reset`, `clean`, force, broad deletion).

## 10. Definition of a valid independent review

A valid `A_REVIEW_PASS` / `A_REVIEW_PASS_WITH_NOTES` requires:

- Genuine reviewer session independence (documented).
- Exact candidate provenance (hashes + patch reconstruction verified).
- Correct production wiring and enforcement of both approved limits.
- No critical/high regression.
- Successful independent execution of the relevant test suite.
