# OHB2 — WP-07 / DEF-011 / F-01 — Review Package (read-only handoff)

**Package:** `OHB2-WP07-BATCH04-DEF011-F01-20261119`
**Created:** 2026-11-19
**Purpose:** hand a reproducible, integrity-verified snapshot to a **genuinely
separate** reviewer. This package is **not** evidence that any review happened.

> ⚠️ **No independent review has been performed.** The producing session cannot
> establish reviewer independence (same host, same user, same session). Do not
> treat this package, or a review run on the same host/session, as independent.

---

## 1. What is in the package

```
snapshot/bot/attachments.py                              # post-fix implementation
snapshot/tests/test_f01_reaper_fs_offload.py             # 13 new F-01 regression tests
snapshot/tests/test_def011_fs_offload.py                 # existing DEF-011 tests (signature-compat edit)
snapshot/docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md
snapshot/docs/reviews/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-REPORT.md   # prior handoff (context)
snapshot/docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md                 # baseline reference
snapshot/docs/audits/OHB2-WP07-DEF011-REMEDIATION-AUDIT.md                  # DEF-011 audit
snapshot/docs/audits/OHB2-WP07-DEF011-IMPLEMENTATION-PLAN.md                # DEF-011 plan (T-1..T-14)
MANIFEST.sha256                                          # 8 entries, SHA-256
```

Batch-03 findings that motivated this fix: **F-01** (fixed here), **F-02**
(still open), **F-03** (still open), **PACK-01/PACK-02** (manifest/`__pycache__`
hygiene in the *previous* package — see that package's report).

---

## 2. Integrity verification

From the package root:

```sh
sha256sum -c MANIFEST.sha256
```

Expected: **8 lines, all `OK`, 0 failures.**

Individual checksums are listed in `MANIFEST.sha256`. Reference values for the
two most important artifacts:

| File | SHA-256 |
|---|---|
| `snapshot/bot/attachments.py` | `d27fb79870d900f584aebfea861619f6e4000ba1b9cb026d359189ae1e914ed5` |
| `snapshot/tests/test_f01_reaper_fs_offload.py` | `0caa88c6e8c3cae176d90464d2f46e1495e6512fa282c33bdc795daf01fdae2e` |

The **pre-fix** baseline for the same file (from the Batch-03 snapshot) is
`e72745eb9d628c20daec3caddd4c6e95fd3365ece6655ec2adb2d03138b99d2e` — a reviewer
can diff against it to see exactly the F-01 delta (+162 / −65 lines).

---

## 3. How to reproduce the verification

Copy the package to an isolated location, then:

```sh
# 1. Verify integrity
sha256sum -c MANIFEST.sha256

# 2. Reconstruct a working tree from the real repository at HEAD 52e7789,
#    then overwrite the two snapshot files:
#      bot/attachments.py
#      tests/test_f01_reaper_fs_offload.py
#      tests/test_def011_fs_offload.py

# 3. Run the gates
python -m pytest -q tests/test_f01_reaper_fs_offload.py          # expect 13 passed
python -m pytest -q tests/test_def011_fs_offload.py              # expect 21 passed
python -m pytest -q                                              # expect 3419 passed, 0 failed
python -m pyflakes bot/ automation/ tools/ main.py tests/         # expect exit 0
python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613  # expect High: 0
node --test tests/frontend/*.test.js                              # expect 280 pass / 0 fail
python -m pytest -q tests/test_doc_code_parity.py                 # expect 6 passed
```

### 3.1 The decisive independent check (recommended)

Do **not** trust the report's numbers. Re-derive the defect independently:

1. Instrument `_remove_file` to record `threading.get_ident()`.
2. Run `sweep_async` over a batch with ≥100 staged files.
3. Assert **every** recorded ident differs from the event-loop thread ident.
4. Then restore the pre-fix `attachments.py` (hash above) and confirm the same
   assertion **fails** — that reproduces F-01 and proves the test discriminates.

Mutation check already performed by the producer (for reference, must be
re-derived independently): the 13 F-01 tests give **8 failed / 5 passed**
against the pre-fix file, and **13 passed** against the fixed file.

---

## 4. What a reviewer should try to falsify

| Claim to attack | Where |
|---|---|
| No filesystem call on the loop thread during `sweep_async` | `_apply_cleanups` / `_sweep_fs_tail` |
| DB decision (`reaped` CAS) strictly precedes deletion | `_plan_batch` / `_plan_orphan_items` vs `_apply_cleanups` |
| No SQLite call from a worker thread | `_sweep_fs_tail` must not touch `self._db` |
| Missing-file / FS-error / DB-error semantics unchanged | `_finish_batch`, `_finalize` |
| Sync `sweep()` still blocks its caller (documented, not silent) | `sweep()` docstring |
| Startup + watcher both use the async path | `bot/app.py:241`, `bot/watcher.py:183` |

---

## 5. Explicitly out of scope / still open

- **F-02** — `_accept_lock` released while worker still writing on cancellation. **OPEN.**
- **DEF-011 A** — quota/reservation ledger. **NOT IMPLEMENTED** (D-12 / OD-04).
- **DEF-011 C** — attachment UX copy. **NOT IMPLEMENTED** (WP-01).
- **F-03** — stale acceptance doc. **OPEN.**
- **WP-09 Python 3.11 matrix** — **UNVERIFIED** (no 3.11 interpreter, no CI).

---

## 6. Package checksum

The archive's own SHA-256 is **not** stored inside the archive (a self-referential
hash cannot be valid). It is published outside, in the repository copy of
`docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` §10.

Verify the archive, then the contents:

```sh
sha256sum OHB2-WP07-BATCH04-DEF011-F01-20261119.tar.gz   # compare with report §10
tar xzf OHB2-WP07-BATCH04-DEF011-F01-20261119.tar.gz
cd OHB2-WP07-BATCH04-DEF011-F01-20261119
sha256sum -c MANIFEST.sha256                            # expect 8/8 OK
```


