# OHB2 — WP-07 / DEF-011 / F-03 — Genuinely Independent Review Report

**Task:** `OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-AND-CLOSURE`
**Review date:** 2026-11-21
**Subject:** `docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md` (verdict claimed: `F03_REMEDIATED`)
**Supersedes (as the independent verdict):** `docs/reviews/OHB2-WP07-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md`
(which returned `INDEPENDENCE_NOT_ESTABLISHED` for a genuine reason: it ran in the implementation conversation).

---

## 1. Verdict

# `F03_REVIEW_PASS`

The reviewer independence gate **is met** this time (see §2), and every technical claim in the
implementation report was **independently reproduced from the live repository**, not copied from the
report. The remediation is insertion-only, the historical bytes are exactly recoverable, `§2.2`/`§7`
are byte-identical to their originals, the factual status (B implemented; A/C not; no ledger; DEF-011
open) is accurate against the source, the full suite moved **+7**, and all five documented mutations
are detected.

**This closes the F-03 documentation defect only.** `DEF-011` as a whole remains **open**
(`DEF-011-A`, `DEF-011-C` unimplemented; `D6` deferred). One separate, out-of-scope stale document is
recorded as a follow-up in §9.

---

## 2. Phase 1 — Reviewer independence (established)

The task requires a *separate conversation/session identity* **and** *independently obtained repository
access*, and explicitly rejects "a different container" as sufficient on its own. Both requirements
are satisfied, with evidence:

| Requirement | Evidence in this session | Result |
|---|---|---|
| Separate **conversation identity** | `meta.json`: `conversation_id = de819568-6590-47d2-906a-e4b94a4ddc7c`, `parent_conversation_id = null` (a root conversation, not a child of the implementation conversation). | **PASS** |
| Not the implementation conversation | The implementation/review conversation was `6715bb35bff4420d9802ed649c3cc2ea` (recorded in the previous review). It is **not hosted here**: `OH_CONVERSATIONS_PATH=/var/openhands/conversations` contains exactly **one** directory — `de819568659047d2906ae4b94a4ddc7c` (this session, created 2026-11-21 09:59). The old id appears in this environment only inside the text of the prior report I read. | **PASS** |
| Fresh model context | This conversation begins with the review prompt; there is **no** prior turn containing the implementation. The project memory file (`.openhands/memory/MEMORY.md`) contains **no** mention of the DEF-011 F-03 documentation remediation (`grep -niE "DEF-011-F03|CONDITIONAL-OWNER|FINAL-STABILIZATION-BATCH|LATER CORRECTION|supersession"` → none). The only `F-03` in memory is a *different* label (`DEF-009` / WP-06). | **PASS** |
| Independently obtained repository snapshot | `git reflog`: `HEAD@{1}: clone: from https://github.com/TM-AEM/OpenHandBot.git`, then `HEAD@{0}: checkout: moving from main to openhands-workspace-11yyMvqKPjTrIZt1RRpWq9`. HEAD = `origin/main` = `30dfa0d`. The implementation session worked in branch `openhands-workspace-40xxn2SbOi0tRICb3y8TE` at HEAD `52e7789` with untracked docs — a **different** workspace. | **PASS** |
| Separate environment | Fresh container, different branch, fresh clone. (Used as corroboration only, not as the sole basis.) | **PASS** |

**Conclusion:** the reviewer is a genuinely separate session that obtained the code by cloning the
published repository, not by continuing the implementation agent's conversation or workspace.
`INDEPENDENCE_NOT_ESTABLISHED` does **not** apply here.

Honest note: the implementation was authored in `6715bb35…`; this review runs in `de819568…`. The two
are distinct conversations with distinct event logs. No implementation turn is present in this context.

---

## 3. Repository state at review time

| Item | Value |
|---|---|
| `HEAD` | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` |
| `origin/main` | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` (**in sync**) |
| Branch | `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` |
| Working tree | **clean** (`git status --porcelain` empty) |
| Staged | **0** |
| Clone origin | `https://github.com/TM-AEM/OpenHandBot.git` |

**Important structural change since the previous review.** In the previous review the two corrected
documents were **untracked** and the test file was a working-tree modification at `52e7789`. They are
now **committed** in `30dfa0d` ("feat: sync complete OHB2 WP-05/WP-06/WP-07 remediation work to main").
That sync commit contains `92 A / 9 M / 0 D`; the **9 modified** files are exactly the **8 pre-existing
modified files + `tests/test_doc_code_parity.py`** that the previous review already catalogued. The
two F-03 documents are among the 92 **added** files. There are **no deletions**.

So the F-03 change set is still exactly the intended three files; the rest of the sync commit is the
publication of pre-existing, already-reviewed work (see §8).

---

## 4. Phase 2 — Exact remediation verification

### 4.1 Change set is limited to the intended files

| Check | Evidence | Result |
|---|---|---|
| Supersession notices exist only in the two intended docs | `grep -rl "LATER CORRECTION — 2026-11-21"` → the two corrected docs **plus** the F-03 diagnosis and implementation reports (audit artifacts that *describe* the remediation, not remediation edits). No other document carries the notice. | **CONFIRMED** |
| The 7 new tests exist only in `tests/test_doc_code_parity.py` | `grep -rl "_HISTORICAL_STALE_LINES"` → only the test file (+ the two F-03 reports that quote it). | **CONFIRMED** |
| Test diff is insertion-only | `git diff 52e7789 30dfa0d -- tests/test_doc_code_parity.py`: **+206 additions, 0 deletions**; exactly **7** `+def test_` lines. | **CONFIRMED** |
| No source file changed by F-03 | `bot/attachments.py` = `b98d561f…4d818356`, identical to the diagnosis-recorded reference hash (§4.4). | **CONFIRMED** |

### 4.2 Notices are additive; the historical text remains intact

- Proposal notice: blockquote at lines **18–53**; the pure insertion is lines **18–56** (**39** lines,
  incl. its trailing blank + `---` + blank). 239 − 39 = **200** original lines.
- Batch-report notice: blockquote at lines **214–220**; pure insertion is lines **214–221** (**8**
  lines). 277 − 8 = **269** original lines.
- The three historical stale statements are still present **verbatim**:
  - `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md:65` → `- an entirely **unimplemented** finding (DEF-011).`
  - Proposal §5 **R9** → `| **R9** | **DEF-011 is entirely unimplemented** while inside WP-07's authoritative scope. | 0 `to_thread` in `attachments.py`; 0 quota ledger |`
  - `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md:224` → `| 1 | **DEF-011 is entirely unimplemented** (no `asyncio.to_thread` in `attachments.py`, no quota ledger) though inside WP-07's authoritative scope | WP-07 is **not** implementation-complete |`

### 4.3 Original content is exactly recoverable (pure insertion proof)

Removing **only** the inserted notice and re-hashing reproduces the **exact** original SHA-256:

| File | Current SHA-256 | Reconstructed (notice removed) | Diagnosis-recorded original | Match |
|---|---|---|---|---|
| Proposal | `8fe7d96d450f5ffc61539813990b168899b81aab81c53fae36e52df007b1533f` | `82fbf9869e9393b5f3c7d756aea82991ffff97a77124a8dfbb9f82d2681c2b7c` | `82fbf986…c2b7c` (diagnosis line 141) | **EXACT** |
| Batch report | `217374d2f26c3a26e6ec6d4c25c7c25ba908a00756cfa0feb8c81211c9f2fa5e` | `2cce88dd4290a285dc383b9c4ada43a9fe9ce36b3141a0369a7065f7a171512c` | `2cce88dd…512c` (diagnosis line 142) | **EXACT** |

The "original" values were recorded in the **pre-implementation** diagnosis report, so this is not
circular: a pre-change record and my post-change reconstruction agree byte-for-byte. The edits are
**pure insertions** — no historical byte was altered, moved, or deleted.

### 4.4 `§2.2` and `§7` are byte-for-byte unchanged

I compared the current file against the reconstructed original using the **same** slicing on both
sides, under **both** boundary conventions:

| Section | Exclusive-boundary current == original | Inclusive-boundary current == original | Inclusive SHA-256 | Report value | Match |
|---|---|---|---|---|---|
| §2.2 | **True** | **True** | `b10cdb6dca9017e195b911d98bd603b3f243056dc2146468b2d65888d067a98d` | `b10cdb6d…a98d` | **EXACT** |
| §7 | **True** | **True** | `ba02416da1b943bffb10cd99338a8c406d428fae18b660378f5d92b4ad5f8374` | `ba02416d…8374` | **EXACT** |

The `sed -n '/start/,/end/p'` (inclusive) convention reproduces the report's values exactly, which
confirms the previous review's "apparent mismatch" was only a boundary convention, not content drift.
The historical line `- **No DEF-011 implementation.**` inside §7 is preserved and was **not** converted
into a present-day claim.

### 4.5 `bot/attachments.py` was not modified by F-03

`sha256sum bot/attachments.py` = `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356`,
**identical** to the diagnosis-recorded reference (`…DIAGNOSIS-AND-REMEDIATION-PLAN.md:143`) and to the
previous review's pre-F-03 value. **CONFIRMED unchanged.**

### 4.6 Factual distinction is accurate against the source

| Claim | Independent measurement | Accurate? |
|---|---|---|
| **`DEF-011-B` implemented** | `grep -c to_thread bot/attachments.py` → **5**: line 88 (`from anyio import to_thread`), line 900 (docstring), lines 953, 968, 1295 (three `await to_thread.run_sync(...)` call sites). `bot/handlers.py:2086-2087` → `await to_thread.run_sync(functools.partial(_read_local_capped, …))`. The notice's wording ("five occurrences: module import, one docstring reference, and three `anyio.to_thread.run_sync` call sites") is exactly correct. | **YES** |
| **`DEF-011-A` not implemented** | `grep -cE "reserv|in_flight|_ledger" bot/attachments.py` → **0**; repo-wide `grep -rniE "reservation|quota ledger|_ledger|reserved_bytes" bot/ automation/ tools/` → **no matches**. | **YES** |
| **No reservation ledger implemented** | Same repo-wide grep → none. | **YES** |
| **`DEF-011-C` not implemented** | F-03 touched no source file; both notices mark C `NOT IMPLEMENTED` (blocked on OD-01/OD-03). No acceptance-UX-copy change exists as part of this work. | **YES** |
| **`DEF-011` as a whole remains open** | Proposal notice: "**DEF-011 is NOT fully implemented and NOT closed.**" and "`DEF-011` **remains open**." Batch notice: "**`DEF-011` remains open** — it is **not** fully implemented and **not** closed." | **YES** |

**The key overclaim risk is handled correctly:** the historical R9 had two halves. The "0 `to_thread`"
half is now false and is marked **SUPERSEDED**; the "0 quota ledger" half is **still true** and is
explicitly reaffirmed as accurate. The notices do not claim A, B and C are all implemented.

---

## 5. Phase 3 — Independent reproduction of verification

All commands were run by me in this session; results are actual output, not copied.

| Check | Command | Result | Exit |
|---|---|---|---|
| Focused parity tests | `python3 -m pytest tests/test_doc_code_parity.py -v` | **13 passed** (6 pre-existing + 7 new) | 0 |
| Full Python suite (final) | `python3 -m pytest -q` | **3450 passed, 0 failed**, 74 warnings | 0 |
| Full Python suite (baseline: F-03 block removed in a scratch copy) | `python3 -m pytest -q` in `/tmp/f03rev/base` (file 297 → 91 lines) | **3443 passed, 0 failed**, 74 warnings | 0 |
| **Seven-test delta** | 3450 − 3443 | **+7 exactly** (2×T-1, 2×T-2, 2×T-3, 1×T-4) | — |
| pyflakes | `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | **no output** | 0 |
| bandit (high only) | `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | "No issues identified"; severity **High: 0** (Low 5, Medium 19); exit 0 | 0 |
| Frontend Node | `node --test tests/frontend/*.test.js` | **pass 280, fail 0** | 0 |
| pip-audit (SCA) | `python3 -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities found** | 0 |

### 5.1 Environment disclosure (honest, not concealed)

- First full-suite run gave **3449 passed, 1 failed** — `tests/test_deploy_manifest.py::test_documented_manifest_is_import_sufficient`.
  Root cause: I had installed deps with `pip --user` (into `/home/openhands/.local/…`), and that test
  launches `python -c "import main"` in a subprocess with `HOME=<tmp>`, which disables the user site,
  so `telegram` was not importable. This is an **environment** artifact (a `--user` install), not a
  code or F-03 defect.
- I re-installed the same pinned deps system-wide (`sudo python3 -m pip install -r requirements-dev.txt`),
  after which `tests/test_deploy_manifest.py` → **6 passed**, and the full suite → **3450 passed, 0 failed**.
  The repo itself was not modified by this; `git status` stayed clean.
- Python here is **3.13.15** (the implementation report used **3.11**). On 3.11 the report recorded
  `3449 passed, 1 skipped` (total 3450); on 3.13 the same total is `3450 passed, 0 skipped`. The
  **+7 delta holds identically** on both interpreters (3443 → 3450 here; 3442 → 3449 there).

### 5.2 Mutation checks — independently reproduced

I applied each mutation to a **fresh scratch copy** (never the live repo), ran the focused tests, and
restored. My harness applied the change and asserted the target text existed before editing.

| # | Mutation | Tests that failed (my run) | Summary |
|---|---|---|---|
| **M1** | Rewrite the historical "0 `to_thread`" claim in place | `test_t2_historical_stale_claims_are_preserved_verbatim` | 1 failed, 12 passed |
| **M2** | Delete the entire proposal correction notice | `test_t1_correction_notice_matches_actual_implementation_state`, `test_t3_both_documents_state_def011_remains_open`, `test_t3_no_claim_that_all_sub_defects_are_implemented`, `test_t4_both_notices_share_date_status_and_scope_language` | 4 failed, 9 passed |
| **M3** | Flip `DEF-011-A` to **IMPLEMENTED** in the notice | `test_t1_correction_notice_matches_actual_implementation_state` | 1 failed, 12 passed |
| **M4** | Tamper §2.2 by one token (`(edited)` appended) | `test_t2_protected_sections_are_byte_for_byte_unchanged` | 1 failed, 12 passed |
| **M5** | Diverge the batch-report notice date (2026-11-20) | `test_t4_both_notices_share_date_status_and_scope_language` | 1 failed, 12 passed |
| **Control** | Unmodified snapshot | none | 13 passed, 0 failed |

Every mutation was caught by the **intended** test, and the control run is green — the tests are
**non-vacuous**.

---

## 6. Test-quality assessment (read independently)

The 7 new tests parse **document sections** by textual boundaries (not line numbers) and compare
against **golden literals embedded in the test file**, while the subject is read from disk. This is the
correct direction of dependency: a document-only edit fails the test; the test cannot silently follow
the document.

Carried-forward, non-blocking observation (same as the previous review, not repaired here):
`test_t3_no_claim_that_all_sub_defects_are_implemented` scans the text before each "fully implemented"
for the word "not", so a contrived sentence like *"DEF-011-A is not implemented, but DEF-011 is fully
implemented"* could slip past **that specific assertion**. In practice the sibling assertions
("not implemented" present) and T-1/M3 still catch the realistic overclaim, and M2/M3 demonstrate real
detection. Recorded as an observation, not a defect.

---

## 7. Phase 4 — Scope and safety audit

| Requirement | Evidence | Result |
|---|---|---|
| No unrelated implementation/architecture changes introduced by F-03 | F-03 change set = 2 docs (notices) + `tests/test_doc_code_parity.py` (+206, 0 deletions). No source file differs from its pre-F-03 hash. | **CONFIRMED** |
| No change to `DEF-011-A` | 0 ledger tokens in `attachments.py`; repo-wide none. | **CONFIRMED** |
| No change to `DEF-011-C` | No acceptance-UX-copy change; notices keep C `NOT IMPLEMENTED`. | **CONFIRMED** |
| No change to `D6` | D6 still documented as deferred at `bot/attachments.py` (~line 916 and ~966). | **CONFIRMED** |
| No unrelated pre-existing work removed/overwritten | Sync commit has **0 deletions**; the 9 modified files are the 8 pre-existing + the F-03 test file. Pre-existing hashes match: `app.py fb3d5038…`, `db.py 205f1363…`, `watcher.py 06f3dd4c…`, `handlers.py 40dd8902…`, `attachments.py b98d561f…`. | **CONFIRMED** |
| No destructive Git operations | `git reflog` shows only `clone` + `checkout`. No reset/clean/stash/force/rebase. | **CONFIRMED** |
| No commit/push/PR/merge/deploy/Autopush by this review | `git status` clean, `git diff --cached` empty, HEAD == origin/main unchanged; no network Git writes performed. | **CONFIRMED** |
| Review is read-only except the mandated report | This report is the only file this review creates; all mutations ran in `/tmp/f03rev/*`; live-tree hashes unchanged after review. | **CONFIRMED** |

**Note on commit `30dfa0d`:** it pre-existed this review (it is `origin/main` as cloned). It is the
publication of pre-existing, already-reviewed work plus the F-03 docs/tests. This review performed **no**
Git write; it only read the published commit.

---

## 8. Findings and limitations

1. **NON-BLOCKING — third document still asserts F-03 is unfixed.** See §9. Out of scope; recorded as
   a follow-up, not modified.
2. **NON-BLOCKING — T-3 negation soft spot.** See §6. Unchanged; not repaired (review is read-only).
3. **NON-BLOCKING — interpreter matrix.** I verified on Python **3.13.15** only. The report's numbers
   were on **3.11**. The +7 delta is identical on both, but I did not run the full suite on 3.11 here
   (no 3.11 interpreter installed). This is a reproducibility scope note, not a failure.
4. **Environment precondition.** A clean full-suite run requires the pinned deps importable **without**
   `HOME` (i.e., system/site installs, not `--user`) and `git` on `PATH` (autopush tests shell out to
   `git`). Both are environment preconditions, not code issues.

---

## 9. Phase 2b — Separate follow-up: stale `BATCH04-F01` reference

`docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md:300` still reads:

```
| **F-03** (stale acceptance doc claiming "0 `to_thread`") | **OPEN / NOT FIXED** | Batch-03 DOC-01; not part of this task. |
```

**Confirmed still stale** (the two documents it refers to are now corrected). This is the **same class**
of defect F-03 addresses, in a **third** document. It was deliberately excluded from the remediation
scope by the diagnosis (recorded as a separate historical-attribution issue) and the implementation
report lists it under "Remaining limitations."

**Not modified by this review** (scope: record only). It does not contradict the two corrected
documents, but anyone reading that file alone would still believe F-03 is open. **Recommendation:** the
owner decide whether to append a similar dated notice there — as its own task, not this one.

---

## 10. Explicit confirmation: this review was read-only

- No source, test, or historical document was modified. All mutation experiments ran on scratch copies
  under `/tmp/f03rev/` (never the live repo).
- Live-workspace hashes after review equal those before review: proposal `8fe7d96d…b1533f`,
  batch report `217374d2…f2fa5e`, `bot/attachments.py` `b98d561f…4d818356`,
  `tests/test_doc_code_parity.py` `00db35e7…f87fb7`.
- `git status`: clean; **staged 0**; HEAD == `origin/main` == `30dfa0d`.
- **No commit, push, PR, merge, deploy, or Autopush activation.** No `git add`, reset, clean, stash, or
  force operation.
- The only repository write is this report file (explicitly requested by the task).

---

## 11. What the owner can rely on

Independently verified facts (this session, live repo, actual output):

1. The remediation is **insertion-only**; the original bytes are exactly recoverable (SHA-256 match to
   the pre-implementation diagnosis record).
2. `§2.2` and `§7` are byte-identical to their originals under any consistent slicing.
3. `DEF-011-B` is implemented (5 `to_thread`, 3 real call sites, plus the handlers offload);
   `DEF-011-A` and `DEF-011-C` are **not**; **no** reservation ledger exists; `DEF-011` remains **open**,
   stated in both documents.
4. Full suite: **3443 → 3450** (+7), reproduced by physically removing the F-03 test block in a scratch
   copy.
5. pyflakes 0; bandit High 0; node 280/0; pip-audit clean.
6. All five documented mutations are detected — reproduced with my own harness and a green control.
7. Scope is exact: 2 documents + 1 test file; the 8 pre-existing files are hash-identical to their
   pre-F-03 values; no deletions anywhere in the sync commit.

**`DEF-011` is NOT closed.** `DEF-011-A` and `DEF-011-C` remain unresolved and `D6` remains deferred.
This review closes **F-03 documentation remediation** only.

---

## 12. Final report (AGENTS.md format)

- **Status:** **DONE** — `F03_REVIEW_PASS`, independence established.
- **Acceptance criteria:**
  - Independent reviewer session — **MET** (separate conversation `de819568…`, parent null; §2).
  - Independent repo access — **MET** (fresh clone from origin, HEAD `30dfa0d`; §2, §3).
  - Remediation limited to 2 docs + test file — **MET** (§4.1).
  - Notices additive; historical text intact — **MET** (§4.2).
  - §2.2 / §7 byte-for-byte unchanged — **MET** (§4.4).
  - Original recoverable; hashes match diagnosis — **MET** (§4.3).
  - `attachments.py` unchanged — **MET** (§4.5).
  - B implemented / A, C open / no ledger / DEF-011 open — **MET** (§4.6).
  - Full suite, +7 delta, 5 mutations, pyflakes, bandit, node reproduced — **MET** (§5).
  - Stale BATCH04-F01 recorded as follow-up, not modified — **MET** (§9).
- **Changes:** added `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` (this
  report). No other repository change.
- **Verification:** focused 13 passed; full 3450 passed / 0 failed; baseline 3443 → +7; 5/5 mutations
  caught + green control; pyflakes exit 0; bandit High 0 exit 0; node 280/0; pip-audit clean.
- **Not verified / not implemented:**
  - Full suite not run on Python 3.11 in this session (3.13 only). +7 delta reproduced on 3.13.
  - `DEF-011-A`, `DEF-011-C`, `D6` remain unimplemented (by design; out of F-03 scope).
  - The stale third document (§9) is intentionally left unchanged.
- **Assumptions and decisions:**
  - Interpreted "the current diff" as the **F-03 change set** (2 docs + test), not the whole
    pre-existing sync commit; documented in §3/§7.
  - Installed the pinned dev deps system-wide to make the isolated-import test runnable; this changes
    only the container environment, not the repo.
  - Did **not** update `.agent/PROGRESS.md`, to honour the task's "preserve all pre-existing workspace
    state" and the read-only nature of the review.
- **Branch and commits:** `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` at `30dfa0d` (unchanged). No
  commit/push performed by this review.
- **Suggested next step:** open a separate, scoped task to append a dated supersession notice to
  `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md:300` (the last known stale
  F-03-class reference), or explicitly accept it as historical.

---

## 12. CURRENT TASK UPDATE — 2026-11-22 (remediation session; NOT an independent review)

### 12.1 Phase 1 — independence verdict for the current tree

**`INDEPENDENCE_NOT_ESTABLISHED` for the current working tree.**

- The prior review in §2 ran in conversation `de819568-6590-47d2-906a-e4b94a4ddc7c`, which is distinct
  from the implementation conversation `6715bb35bff4420d9802ed649c3cc2ea`. That evidence remains valid
  **only for the snapshot it reviewed** (`HEAD 30dfa0d`).
- This current remediation task was executed in the same live session that edited the F-03 notices and
  implemented F-01..F-12. A reviewer cannot independently certify code/docs it authored in the same
  conversation. No separate reviewer conversation, independently obtained clone, or second agent
  identity is available in this environment.
- Consequently the top `F03_REVIEW_PASS` verdict **must not** be read as a pass for the current working
  tree. It is a historical verdict on `30dfa0d`, not on the current delta.

No evidence was manufactured. The technical checks below are reported as **non-independent
implementation verification**, not as an independent review.

### 12.2 Current state and F-03 verification (non-independent)

- Current `HEAD`: `9d1e13d72ed7dca8ffd2c6eebff1c6a36400ab17`; `main == origin/main`.
- F-03 notices now mark `DEF-011-B` **IMPLEMENTED**, `DEF-011-A` **NOT IMPLEMENTED**, and
  `DEF-011-C` **IMPLEMENTED (2026-11-22)** after the explicit local-only acceptance copy was added.
  `DEF-011` as a whole remains **OPEN**; no reservation ledger exists; `D6` is untouched.
- `bot/attachments.py` is **not modified in the current working tree** (`git status` clean for it).
  Its current hash is `0c52d04bfc7a461a0d8ca0a92476faa91a00ef9ebe7becb1e00fb12a76126d9b`; it differs
  from the diagnosis hash `b98d561f…` because of later non-F-03 `to_thread` work, not because F-03
  changed it.
- Removing the F-03 notice from the batch report reproduces the diagnosis original exactly:
  `2cce88dd4290a285dc383b9c4ada43a9fe9ce36b3141a0369a7065f7a171512c`.
- Removing the F-03 notice from the proposal reproduces `b636a7a8…`, the **immediate pre-notice
  parent**, not the diagnosis hash `82fbf986…`. The difference is the pre-existing
  `Post-decision update — 2026-11-22` block, which F-03 did not add. This is recorded as a separate
  documentation-drift follow-up, not claimed as an F-03 hash match.
- The F-03 parity guard passes **15/15** (`tests/test_doc_code_parity.py`), including the new
  implementation-report correction test.
- Five documented mutation checks were reproduced on a scratch copy of the tree:
  control 15 passed; M1 (rewrite historical `0 to_thread`) 1 failed; M2 (delete proposal notice)
  4 failed; M3 (flip `DEF-011-A` to IMPLEMENTED) 2 failed; M4 (tamper §2.2) 1 failed; M5 (diverge
  notice date) 1 failed. Every mutation was caught by the intended parity guard.

### 12.3 Broader remediation verification (non-independent)

The task also required F-01..F-12 remediation. The implementation changed routing/outbox/cleanup code
and tests; it is **not** an F-03-only diff. Actual results from this session:

| Check | Result |
|---|---|
| `python -m pytest -q` | **3714 passed**, 0 failed, 74 warnings |
| `node --test tests/frontend/*.test.js` | **280 passed**, 0 failed |
| `python -m pyflakes bot automation tools main.py tests/` | exit 0, no findings |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | exit 0; **High: 0** |
| `python -m pip_audit -r requirements-dev.txt` | exit 0, no known vulnerabilities |

### 12.4 Follow-up issues (not modified in this task)

1. `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` is **still stale**: its
   correction notice (lines ~298, ~312-314) says `DEF-011-C` remains `NOT IMPLEMENTED`, while the
   current code and F-03 notices mark C implemented. It was intentionally left untouched to keep
   this task's scope bounded.
2. The proposal's diagnosis hash `82fbf986…` is not reproducible from current `HEAD` because of the
   pre-existing post-decision update described in §12.2. A future documentation-only task should
   either re-record the intended baseline or add an explicit correction notice.

### 12.5 Scope and safety

- No commit, push, PR, merge, deployment, release, or Autopush activation occurred.
- No destructive Git operation was used. Pre-existing uncommitted `bot/db.py` work and the untracked
  prior review report were preserved.
- No changes were made to `DEF-011-A`, `DEF-011-C` semantics beyond the explicit local-only copy, or
  `D6`; no reservation ledger was implemented.

### 12.6 Final verdict

**`INDEPENDENCE_NOT_ESTABLISHED`** for the current working tree. The implementation checks are green,
but a genuinely separate reviewer session was not available in this environment, so this report does
**not** issue a current passing verdict and does not close `DEF-011` or the F-03 review.
