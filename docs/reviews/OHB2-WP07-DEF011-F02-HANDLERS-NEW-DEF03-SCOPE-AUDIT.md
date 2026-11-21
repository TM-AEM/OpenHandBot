# OHB2 — WP-07 — DEF-011 / F-02 — `bot/handlers.py` NEW-DEF-03 Scope and Disclosure Audit

**Task:** `OHB2-WP07-DEF011-F02-HANDLERS-NEW-DEF03-SCOPE-AND-DISCLOSURE-AUDIT`
**Type:** read-only scope and disclosure audit. **Not** the final independent review.
**Date:** 2026-11-18

> This document does **not** grant authorization, does **not** accept NEW-DEF-03, does **not** close
> F-02, and does **not** claim an independent review. It answers only: *what is inside the published
> `bot/handlers.py` diff, was that disclosed, and can the F-02 part be separated?*

---

## 0. Verdict

**`HANDLERS_MIXED_SCOPE_NOT_DISCLOSED`**

`bot/handlers.py` in PR #7 contains **substantial NEW-DEF-03 / NAV-01..06 implementation work that is
not required for F-02**, and **none of the three F-02 publication/review documents mentions
NEW-DEF-03 or NAV even once**. The F-02 part is a **single hunk of 6 added lines**, and it is
**provably separable**: an isolated candidate that keeps only that hunk and reverts `bot/handlers.py`
and `bot/db.py` to the published base passes the **entire** suite (**3330 passed, 0 failed**).

---

## 1. Baseline verified (read-only)

| Property | Value | Evidence |
|---|---|---|
| PR | **#7 — OPEN, unmerged** (`merged=null`) | `gh pr view 7` |
| Head commit | **`31dec52289142d0d0dc2bd16604d88644ba3baba`** | `gh pr view 7 --json headRefOid` |
| Base | `main` | `gh pr view 7 --json baseRefName` |
| Changed files | **6** | `gh pr view 7 --json changedFiles` |
| Parent | `52e7789` | local `git rev-parse`; workspace HEAD = `52e7789` = `origin/main` |
| CI run `44767282994` | **success** — jobs `Tests & lint (3.11)`, `Tests & lint (3.13)`, `Frontend tests (Node)` all success, `headSha=31dec52…` | `gh run view 44767282994 --json jobs` |
| `main` touched? | **No.** `origin/main` = `52e7789`; candidate lives only on `review/ohb2-wp07-def011-f02-six-file-ci` | `git rev-parse origin/main` |

`bot/handlers.py` diffstat: **+144 / −41** (44 change regions at `-U0`, 25 hunks at default context).

---

## 2. Phase 1 — hunk-by-hunk classification of `bot/handlers.py`

Classified by the marker comments and the API each hunk calls. "F-02" is assigned **only** to the hunk
that `test_T8b` actually requires — not because a hunk lives in `handlers.py`.

| # | Function | ≈line | Behaviour changed | Marker / ID | Required by F-02? | Removable? |
|---|---|---|---|---|---|---|
| 1 | module imports | 6 | `import functools` | — (F-02 support) | **yes** (used by #30) | no |
| 2 | module imports | 17 | `from anyio import to_thread` | — (F-02 support) | **yes** (used by #30) | no |
| 3 | `_is_deleted_with_retry` | 391 | passes outcome kwargs to remover | NEW-DEF-03 / WP-07 | **no** | yes |
| 4 | `_remove_watched_with_retry` | 397 | new `update_id`/`now`/`outcome` params | NEW-DEF-03 / WP-07 | **no** | yes |
| 5 | `_remove_watched_with_retry` | 413 | keyword-arg dispatch to remover | NEW-DEF-03 / WP-07 | **no** | yes |
| 6,8,10,12,18,23,24,27,29,32,34,36,37,40,42,44 | various | — | pure deletions of the old single-arg call lines | NEW-DEF-03 | **no** | yes |
| 7 | `start` | 900 | `clear_awaiting_and_record_outcome` | NEW-DEF-03 / **NAV-01** | **no** | yes |
| 9 | `show_menu` | 961 | `clear_awaiting_and_record_outcome` | NEW-DEF-03 / **NAV-02** | **no** | yes |
| 11,13,14,15 | `list_conversations` | 1078–1139 | atomic clear + outcome, incl. failure path | NEW-DEF-03 / **NAV-03** | **no** | yes |
| 16,17 | `open_conversation` | 1201–1205 | `set_awaiting_and_record_outcome` | NEW-DEF-03 / **NAV-06** | **no** | yes |
| 19,20 | `list_watches` | 1389–1409 | atomic clear + outcome | NEW-DEF-03 / **NAV-04** | **no** | yes |
| 21–24 | `watch_conversation` | 1443–1453 | `add_watched_and_record_outcome` | NEW-DEF-03 (A-1) | **no** | yes |
| 25–27 | `unwatch_conversation` | 1466–1494 | atomic remove + outcome | NEW-DEF-03 (A-2) | **no** | yes |
| 28,29 | `reply_prompt` | 1859–1867 | `set_awaiting_and_record_outcome` | NEW-DEF-03 (A-3) | **no** | yes |
| **30** | **`_download_attachment_chunks`** | **2084** | **`_read_local_capped` moved to `to_thread.run_sync`** | **`DEF-011`** | **YES — required by `test_T8b`** | **no** |
| 31,32 | `handle_text` | 2528–2539 | atomic clear + outcome | WP-07 / NEW-DEF-03 | **no** | yes |
| 33–36 | `cancel_route`, `cancel_route_button` | 2589–2610 | atomic clear + outcome | NEW-DEF-03 | **no** | yes |
| 38 | `start_new_chat` | 2694 | atomic clear + outcome | NEW-DEF-03 / **NAV-05** | **no** | yes |
| 39–44 | `repo_search_prompt`, `pick_repo`, `new_chat_no_repo` | 2745–2840 | `set_awaiting_and_record_outcome` | NEW-DEF-03 (A-3) | **no** | yes |

**Tally:** exactly **one** functional F-02 hunk (#30, 6 added lines) plus its **two** import lines.
The remaining **41 of 44** change regions are NEW-DEF-03 / NAV-01..06 work.

Grep of the published diff: **12 added lines** carry `NEW-DEF-03` / `NAV-0` markers; **0** added lines
carry any other work-package marker except `DEF-011` on #30.

---

## 3. Phase 2 — disclosure audit

Searched all six named documents. All six are **present** (none `DOCUMENTATION_UNAVAILABLE`).

| Question | Document / location | What it actually says | Verdict |
|---|---|---|---|
| Is NEW-DEF-03 named in the F-02 publication set? | `docs/reviews/OHB2-WP07-DEF011-F02-SIX-FILE-PUBLICATION-CI-REPORT.md` — whole file | `grep -c NEW-DEF-03` = **0**; `grep -c NAV-` = **0** | **NOT disclosed** |
| Is it named in the reviewer handoff? | `docs/reviews/OHB2-WP07-DEF011-F02-INDEPENDENT-REVIEW-HANDOFF.md` — whole file | `grep -c NEW-DEF-03` = **0**; `NAV-` = **0** | **NOT disclosed** |
| Is it named in the closure report? | `docs/reviews/OHB2-WP07-DEF011-F02-FINAL-CI-INDEPENDENT-REVIEW-AND-CLOSURE-REPORT.md` — whole file | `grep -c NEW-DEF-03` = **0**; `NAV-` = **0** | **NOT disclosed** |
| Why is `handlers.py` in the set? | Handoff **L141** | "Off-loop `to_thread` local read (asserted by T-8b)" | Describes **only** the F-02 hunk — implies the file diff is entirely that |
| Same claim, PR body | PR #7 body, "What changed" table | "`bot/handlers.py` — Off-loop `to_thread.run_sync` local read — asserted by `test_T8b`" | **Incomplete** — omits 41 other change regions |
| Is `db.py` justified as F-02? | Handoff **L142** | "Atomic watch/unwatch helpers **used by handlers**" | Circular: they are used only by the NEW-DEF-03 handlers, not by F-02 |
| Does any doc say the **whole** file diff is required? | PR #7 body, "Why all six files are required" | "…that is implemented by the `anyio.to_thread` change in `bot/handlers.py` → **which needs the new atomic helpers in `bot/db.py`**" | **Yes — and it is factually wrong** (§4) |
| Is the reviewer told of mixed scope? | Handoff §2 "Note for the reviewer" | Only discusses the 2-file vs 6-file premise; no mention of unrelated hunks | **NOT disclosed** |
| Is "no unrelated change" asserted? | Closure report **L256** ("No unrelated changes or regressions → verified"), **L344** ("no unrelated change") | Asserted | **Contradicted by this audit** |

### Classification

**`NOT_DISCLOSED`**

No document distinguishes F-02 from NEW-DEF-03 inside `handlers.py`. The only statements made about
that file describe it as *exclusively* the T8b offload. The handoff/PR dependency claim
("handlers needs db, db needs the test updates") is presented as a technical necessity and is the
opposite of what the tests show.

> A statement that the PR contains six files is **not** disclosure of mixed-purpose hunks.

---

## 4. Phase 3 — variant test matrix

All runs: isolated container `f02review` (Python **3.13.18**, pytest 9.0.3), fresh `git clone` of
`31dec52`, each variant a separate copy under `/work/variants/`. Original repo and PR untouched.

| Variant | `bot/attachments.py` | `bot/handlers.py` | `bot/db.py` | `tests/test_def011_fs_offload.py` | `tests/test_handlers.py`, `test_sw06_…` |
|---|---|---|---|---|---|
| **A** — published 6-file candidate | candidate | candidate (all 44 regions) | candidate | candidate | candidate |
| **B** — candidate minus NEW-DEF-03 in handlers | candidate | **base + F-02 hunk only** | candidate | candidate | candidate |
| **C** — candidate minus NEW-DEF-03 in handlers **and** db | candidate | **base + F-02 hunk only** | **base** | candidate | candidate |
| **D** — as C, both test files also reverted | candidate | **base + F-02 hunk only** | **base** | candidate | **base** |
| **F** — minimal 3-file: candidate `attachments` + F-02 hunk + `test_def011`, everything else base | candidate | **base + F-02 hunk only** | **base** | candidate | **base** |
| **E** — as C but F-02 hunk removed | candidate | **base (no hunk)** | base | candidate | candidate |
| **G** — candidate handlers + base db (PR's "3-file" step) | candidate | candidate | **base** | candidate | candidate |

Hashes (sha256, first 12): `attachments b98d561f0ba0`, candidate `handlers 40dd8902595c`,
isolated `handlers 82d9c4b8e0fa`, candidate `db 205f1363aaf0`, base `db 472fa573142e`.

### Results

| Variant | T8b | DEF-011 file (45) | NEW-DEF-03/outcome tests (120) | **Full suite** |
|---|---|---|---|---|
| **A** | 1 passed | 45 passed | — | **3330 passed, 0 failed** |
| **B** | 1 passed | 45 passed | — | **3330 passed, 0 failed** |
| **C** | 1 passed | 45 passed | **120 passed** | **3330 passed, 0 failed** |
| **D** | 1 passed | 45 passed | — | **3330 passed, 0 failed** |
| **F** | 1 passed | 45 passed | — | **3330 passed, 0 failed** |
| **E** | **1 FAILED** | — | — | — |
| **G** | — | — | — | **83 failed, 3247 passed** |

`test_T8b_local_capped_read_runs_off_event_loop_thread`:
- **fails** when hunk #30 is absent (variant E) → the hunk is genuinely **required by F-02**;
- **passes** whenever hunk #30 is present, regardless of whether `db.py` or the other `handlers.py`
  hunks are present → nothing else in `handlers.py` is required.

**Variant G reproduces the PR body's failure chain exactly**, and proves its cause:

```
E  AttributeError: 'Database' object has no attribute 'clear_awaiting_and_record_outcome'
   bot/handlers.py:964
E  AttributeError: 'Database' object has no attribute 'set_awaiting_and_record_outcome'
```

The PR's "3 files → 94 failed, 5 files → 9 failed" cascade is **not** an F-02 dependency. It exists
only because the published `handlers.py` calls NEW-DEF-03 `db.py` methods. Add the NEW-DEF-03
`db.py` and the two test files and the errors vanish — but so do they if you simply **remove the
NEW-DEF-03 handlers code**, which is variant C/D: **3330 passed**.

### Technical dependency conclusion

> `bot/handlers.py`'s F-02 requirement is **one hunk of 6 lines** (plus `import functools` and
> `from anyio import to_thread`). `bot/db.py`'s NEW-DEF-03 work is **not** required by F-02 at all.
> `tests/test_handlers.py` and `tests/test_sw06_unwatch_db_failure_propagation.py` are required
> **only** to keep the NEW-DEF-03 keyword-argument dispatch working — variant F reverts both and still
> passes 3330.

**F-02 is separable. The six-file set is not the minimum self-consistent unit; a 3-file set is**
(`bot/attachments.py` + minimal `bot/handlers.py` hunk + `tests/test_def011_fs_offload.py`), and it is
green.

### Side finding — the closure report's "3443" figure is not the candidate

The closure report records **3443 passed** on both interpreters (§2.3, §3.1, L25, L340). The published
candidate collects **3330**. Reproduced the discrepancy exactly:

| Tree | Collected |
|---|---|
| Published 6-file candidate | **3330** |
| + the 8 **untracked** `tests/test_wp07_*` / `test_f0*` files (not in PR #7) | **3443** |
| 3443 tree, without uncommitted `bot/watcher.py` + `bot/app.py` | 3 failed / 3440 passed (`TypeError: Watcher.unwatch() got an unexpected keyword argument 'update_id'`) |
| 3443 tree, **with** uncommitted `bot/watcher.py` + `bot/app.py` | **3443 passed, 0 failed** |

So the closure report's headline number was measured on a **working tree containing NEW-DEF-03 files
that PR #7 does not contain**. It is not evidence about the published candidate. (It is also further
evidence that NEW-DEF-03 is a separate, larger body of work spanning `bot/watcher.py` and `bot/app.py`.)

---

## 5. Phase 4 — scope and governance assessment

Dimensions kept separate: **technical correctness ≠ scope authorization ≠ disclosure ≠ independent
review ≠ owner acceptance.**

**1. Was NEW-DEF-03 work included in PR #7?**
**Yes.** 41 of 44 change regions in `bot/handlers.py`, 12 lines explicitly marked `NEW-DEF-03` /
`NAV-0x`, plus `bot/db.py` (+269/−66) whose new methods exist only to serve them.

**2. Was it required for F-02 correctness, or merely co-located?**
**Merely co-located.** Variant C/D: with `handlers.py` reverted to base plus the single F-02 hunk and
`db.py` reverted to base, the **full suite passes 3330/0**. The PR's dependency claim is refuted.

**3. Was its inclusion accurately disclosed before publication?**
**No.** `NOT_DISCLOSED`. Zero occurrences of `NEW-DEF-03` or `NAV-` in the publication report, the
reviewer handoff, or the closure report. The handoff and PR body describe `handlers.py` as *only* the
T8b offload. The closure report asserts "no unrelated change" (L256, L344).

**4. Does the successful CI run validate the mixed six-file candidate technically?**
**Yes, but only that.** Run `44767282994` at `31dec52` passed on 3.11, 3.13 and frontend. That
establishes the mixed tree is green and self-consistent. Nothing more.

**5. Does CI success establish that NEW-DEF-03 was authorized, independently reviewed, or
owner-accepted?**
**No.** CI answers "does it build and pass" only.
- **Authorization:** `docs/audits/OHB2-WP07-SCOPE-A-C-GRANT-AUTHORIZATION-AND-SCOPE-REPORT.md` records
  `C-GRANT-SCOPE-A` **unticked**, signature blank, and all five publication actions
  ("create branch / commit / push / create PR / allow CI") as **NOT GRANTED**. The publication of PR #7
  itself is therefore unauthorized — independent of what the diff contains.
- **Owner acceptance:** the reconciliation doc
  (`docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md` L32) records Scope A
  (NEW-DEF-03 non-concurrency, A-1..A-5) as `NEW-DEF-03_NON_CONCURRENCY_OWNER_ACCEPTED`, but
  **Scope A′ — NAV-01..06 as `REQUIRES_SEPARATE_OWNER_DECISION` — NOT accepted** (L33). PR #7 ships
  **both** scopes.
- **Independent review:** the closure report itself states `NOT ESTABLISHED` (§5, §7).

**6. Would removing the unrelated hunks change the published commit and invalidate the existing CI
evidence for the modified candidate?**
**Yes.** Any change to `bot/handlers.py` or `bot/db.py` produces a new commit and a new tree hash.
Run `44767282994` is bound to `31dec52`; it would no longer describe the modified candidate, which
would need its own CI run. Variants C/D are green **locally** in an isolated container — that is not
CI evidence.

**7. Is a separate NEW-DEF-03 review or owner acceptance still required?**
**Yes.**
- **NEW-DEF-03 Scope A:** owner-accepted per the reconciliation record, but its code is **uncommitted**
  and is being published only as a side-effect of an F-02 PR — no review of it as a unit has occurred.
- **NAV-01..06 (Scope A′):** explicitly `NOT accepted`; needs an owner decision. PR #7 ships it.
- **`bot/watcher.py` + `bot/app.py`:** carry NEW-DEF-03 changes, are **not** in PR #7, and are required
  by the untracked NEW-DEF-03 tests. The delivered set is therefore internally inconsistent with its
  own test suite.

---

## 6. Impact on the existing CI evidence

| Claim | Status after this audit |
|---|---|
| "CI run `44767282994` passed at `31dec52`" | **TRUE** — verified via `gh run view` |
| "The six-file set is the minimum self-consistent unit" | **FALSE** — 3 files suffice (variant F) |
| "`handlers.py` changes are required for F-02 / T8b" | **PARTLY TRUE** — only hunk #30 (6 lines) is required |
| "`db.py` atomic helpers are used by the handlers (F-02)" | **FALSE as stated** — used only by NEW-DEF-03 handlers |
| "Full suite 3443 passed on the candidate" | **FALSE** — candidate is 3330; 3443 included files not in PR #7 |
| "No unrelated change" (closure L256, L344) | **FALSE** — 41 of 44 `handlers.py` regions are unrelated to F-02 |

CI evidence for `31dec52` **remains valid as evidence about `31dec52`**. It does **not** transfer to a
corrected candidate, and it never spoke to scope, authorization, review or acceptance.

---

## 7. Phase 5 — minimum safe next action

Evidence-driven ranking. **No remedy chosen here is executed by this audit.**

1. **Immediate (documentation only, no code change): disclose the mixed scope to the reviewer.**
   Required regardless of which remedy follows. Add to the handoff: *"`bot/handlers.py` also contains
   41 NEW-DEF-03 / NAV-01..06 change regions unrelated to F-02; only the
   `_download_attachment_chunks` hunk is F-02. `bot/db.py`'s new methods serve those, not F-02."*
   This is safe, reversible, and does not disturb CI evidence for `31dec52`.

2. **Recommended: prepare a separate isolated F-02 candidate (3 files).**
   Proven safe by variant F (**3330 passed / 0 failed** in isolation): `bot/attachments.py` +
   `bot/handlers.py` limited to hunk #30 + `import functools` + `from anyio import to_thread` +
   `tests/test_def011_fs_offload.py`. This removes NEW-DEF-03 from F-02 entirely and makes the
   publication match its stated scope. It requires a **new commit and a new CI run**, and it does not
   by itself satisfy the authorization/acceptance gaps.

3. **Do not** close F-02 on the basis of PR #7. NEW-DEF-03 (Scope A′ NAV-01..06 especially) is
   unaccepted, unreviewed as a unit, and its `watcher.py`/`app.py` parts are not even in the PR.

**Not recommended:** merging or closing on the current six-file set. It bundles unaccepted scope
behind an F-02 label.

---

## 8. Explicit unresolved questions

1. **Who authorized publishing PR #7?** `C-GRANT-SCOPE-A` is unticked and all five publication actions
   read `NOT GRANTED`. The publication appears unauthorized; no document records a grant.
2. **Was the NEW-DEF-03 bundling intentional or accidental?** No document says. The working tree
   carries NEW-DEF-03 across `attachments.py`, `db.py`, `handlers.py`, `watcher.py`, `app.py` and 8
   untracked test files; the six-file set is a subset that happened to be green together.
3. **Where is the owner decision on NAV-01..06 (Scope A′)?** The reconciliation doc says
   `REQUIRES_SEPARATE_OWNER_DECISION`; no decision is on record, yet PR #7 ships that scope.
4. **Does the closure report's "3443 passed" invalidate its closure reasoning?** The count describes a
   tree that includes uncommitted `watcher.py`/`app.py` and 8 untracked test files. Its conclusions
   about the *candidate* should be re-derived from a 3330-test run.
5. **Is `bot/watcher.py` NEW-DEF-03 work owner-accepted?** The reconciliation doc lists
   `watcher.unwatch` under A-2 as accepted-but-uncommitted; it is absent from PR #7 and from the
   published CI evidence.

---

## 9. Verification performed

| Check | Result |
|---|---|
| PR #7 state / head / file count | OPEN, `31dec52…`, 6 files — `gh pr view 7` |
| CI run `44767282994` | success, 3 jobs, `headSha=31dec52…` — `gh run view` |
| Published diff hunk inventory | 44 regions (`-U0`) / 25 hunks — `git diff` |
| Marker tally in published diff | 12 lines `NEW-DEF-03`/`NAV-0`; 1 region `DEF-011` |
| Disclosure grep (3 F-02 docs) | `NEW-DEF-03` = 0, `NAV-` = 0 in **all three** |
| Variant A full suite | **3330 passed, 0 failed** |
| Variant B full suite | **3330 passed, 0 failed** |
| Variant C full suite | **3330 passed, 0 failed** |
| Variant D full suite | **3330 passed, 0 failed** |
| Variant F full suite (true 3-file minimum) | **3330 passed, 0 failed** (re-run twice) |
| Variant E (F-02 hunk removed) | T8b **FAILED** — hunk is required |
| Variant G (candidate handlers + base db) | **83 failed / 3247 passed**, `AttributeError` on NEW-DEF-03 methods |
| Variant C NEW-DEF-03/outcome tests | **120 passed** without NEW-DEF-03 code |
| 3443 reproduction | 3330 + 8 untracked test files = **3443 collected**; passes only with uncommitted `watcher.py`+`app.py` |
| Original repo / PR / branch | **unmodified** — HEAD `52e7789`, staged 0, `main` untouched |

**Not verified:** Python 3.11 for the new variants (only 3.13.18 was available in this container run);
no CI run exists for variants B/C/D; frontend suite not re-run for the variants.

---

## 10. Final verdict

**`HANDLERS_MIXED_SCOPE_NOT_DISCLOSED`**

`bot/handlers.py` in PR #7 carries 41 unrelated NEW-DEF-03 / NAV-01..06 change regions beside a single
6-line F-02 hunk. None of the three F-02 documents names that scope, and two of them assert its
absence. The mixed scope is **technically harmless** (CI green) but **not required** (a 3-file
isolated set passes 3330/0) and **not authorized** (`C-GRANT-SCOPE-A` unsigned, NAV-01..06 not
accepted).

**Exact next action:** disclose the mixed scope in
`docs/reviews/OHB2-WP07-DEF011-F02-INDEPENDENT-REVIEW-HANDOFF.md` (documentation only), then obtain an
owner decision on whether F-02 is republished as the isolated 3-file candidate (variant F, proven
green) or PR #7 is retained with its scope explicitly disclosed. **F-02 remains open** until its
independent-review and closure requirements are satisfied.
