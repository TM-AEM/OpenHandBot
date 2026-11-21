# OHB2 — WP-07 / DEF-011 / F-03 — Independent Review Report

**Task:** `OHB2-WP07-DEF011-F03-INDEPENDENT-REVIEW-AND-CLOSURE`
**Review date:** 2026-11-21
**Subject:** `docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md` (verdict claimed: `F03_REMEDIATED`)

---

## 1. Verdict

# `INDEPENDENCE_NOT_ESTABLISHED`

**Not** `F03_REVIEW_PASS`. The task's independence requirement cannot be met in this environment, and a
same-session self-review must not be reported as an independent PASS.

This is **not** a finding against the remediation. Every technical check I could run — including
independent hash reconstruction, an isolated-container full-suite run, baseline reconstruction, and
**independent reproduction of all five mutations** — passed. The remediation appears technically sound
and the `F03_REMEDIATED` verdict is supported by evidence I regenerated myself. The verdict is
constrained solely by the independence gate, exactly as the task instructs.

---

## 2. Independence: why it could not be established

The task requires "a genuinely separate reviewer session/environment from the implementation session."

| Requirement | Finding | Result |
|---|---|---|
| Separate reviewer **session** | The agent server (`openhands-agent-server --port 60000`, PID 1/36) hosts **this** session. `/var/openhands/conversations` contains exactly **one** conversation: `6715bb35bff4420d9802ed649c3cc2ea` — the same one in which the implementation was written earlier. | **FAIL** |
| Alternative LLM profile | `~/.openhands/profiles/` contains only `.profiles.lock` (0 bytes). System prompt: "No saved LLM profiles are currently available." | **FAIL** |
| Provider connections | `~/.openhands/provider-connections/` is **empty**. | **FAIL** |
| Spawn a separate conversation | `GET :60000/api/conversations` → **401**. No delegation credentials/authorization. | **FAIL** |
| Separate **environment** | Achievable and **was** used (isolated container, frozen tarball). But the task says a separate container alone is not sufficient. | **Insufficient alone** |

**Root cause:** the implementation was performed earlier **in this same conversation**. I authored the
notices, the tests, and the implementation report. Reviewing my own work is self-review by definition.

**What I did instead of claiming independence:** performed the most rigorous *same-agent* verification
available, in a genuinely isolated environment, and labeled it honestly. Specifically:

- Frozen the tree to a tarball **outside** the repo (`/tmp/rev/snap.tar`, SHA-256
  `baf912b010df40e917824961f6b8a3c3e55979311c2edee422bf977401bd3d76`) and reviewed **that snapshot**,
  never mutating the live workspace.
- Ran in a **fresh** container (`python:3.11-slim`, name `f03-review`) that was **not** the implementation
  container (`f03-verify`, deleted at the end of the implementation session).
- Re-derived every number from the files rather than copying reported values.

A reviewer whose context contains the implementation is a **weaker** reviewer than a fresh one, even
with a clean container. That residual weakness is the reason this is not a PASS.

---

## 3. Reviewer environment / session distinction

| Aspect | Implementation session | This review session |
|---|---|---|
| Conversation | `6715bb35bff4420d9802ed649c3cc2ea` | **Same** `6715bb35bff4420d9802ed649c3cc2ea` |
| Agent/model context | authored the notices + tests + report | **Same context** (contains that work) |
| Container | `f03-verify` (deleted) | `f03-review` (fresh, deleted after use) |
| Working copy | live repo | frozen tarball copy under `/tmp/rev/work` |
| Network during tests | available | available (needed for `pip`; not for test logic) |

**Session independence: NO. Environment independence: YES.** Environment independence is real but, per
the task, not sufficient on its own.

---

## 4. Repository HEAD and Git status

| Item | Value |
|---|---|
| `HEAD` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (**in sync**) |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| Staged | **0** |
| Tracked modifications | **9** (8 pre-existing + `tests/test_doc_code_parity.py`) |
| Untracked | 91 (includes the F-03 documents; see §5) |
| Ignored | 8 |

`git diff --name-only` (all 9):

```
.agent/PROGRESS.md          <- pre-existing
bot/app.py                  <- pre-existing
bot/attachments.py          <- pre-existing
bot/db.py                   <- pre-existing
bot/handlers.py             <- pre-existing
bot/watcher.py              <- pre-existing
tests/test_doc_code_parity.py   <- F-03 change (authorized)
tests/test_handlers.py      <- pre-existing
tests/test_sw06_unwatch_db_failure_propagation.py  <- pre-existing
```

The eight pre-existing files all carry mtimes of **2026-11-19 / 2026-11-20**, predating this work
(2026-11-21) — independently confirming they were not touched.

**No staging, commit, push, PR, merge, deploy, or Autopush action was performed.**

---

## 5. Files reviewed and their tracked/untracked status

| File | Status | Note |
|---|---|---|
| `AGENTS.md` | **tracked** | governance |
| `docs/audits/OHB2-WP07-DEF011-F03-DIAGNOSIS-AND-REMEDIATION-PLAN.md` | **untracked** | Prompt-1 output |
| `docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md` | **untracked** | subject of review |
| `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` | **untracked** | corrected doc #1 |
| `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md` | **untracked** | corrected doc #2 |
| `tests/test_doc_code_parity.py` | **tracked, modified** | +7 tests |
| `bot/attachments.py` | **tracked, pre-existing modification** | reviewed for status claims |
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | **untracked** | found to contain a residual stale claim (§14.2) |

**Explicitly confirmed:** the two corrected documents are **untracked**. They exist only in the working
tree and are **not published**. Nothing in this review treats them as committed content. `git ls-files
--error-unmatch` returns "UNTRACKED" for both.

---

## 6. Scope verification

| Check | Result |
|---|---|
| Implementation limited to 2 docs + `tests/test_doc_code_parity.py` | **CONFIRMED** — 1 tracked modification, 2 doc edits; the reports are separate artifacts |
| Implementation report at stated path | **CONFIRMED** |
| Untracked files identified | **CONFIRMED** (§5) |
| 8 pre-existing modified files intact | **CONFIRMED** (mtimes 11-19/11-20; hashes match pre-session record) |
| `bot/attachments.py` unchanged | **CONFIRMED** — `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` |
| Unrelated runtime/source unchanged | **CONFIRMED** — `app.py fb3d5038…`, `db.py 205f1363…`, `watcher.py 06f3dd4c…`, `handlers.py 40dd8902…` all at pre-session values |
| No unrelated modifications | **CONFIRMED** |

---

## 7. Independent SHA-256 results

Recomputed from the frozen snapshot with my own script — **not copied** from the reports.

| File | Current SHA-256 | Stripped SHA-256 (notice removed) | Diagnosis-recorded original | Match |
|---|---|---|---|---|
| Proposal | `8fe7d96d450f5ffc61539813990b168899b81aab81c53fae36e52df007b1533f` | `82fbf9869e9393b5f3c7d756aea82991ffff97a77124a8dfbb9f82d2681c2b7c` | `82fbf986…c2b7c` | **EXACT** |
| Batch report | `217374d2f26c3a26e6ec6d4c25c7c25ba908a00756cfa0feb8c81211c9f2fa5e` | `2cce88dd4290a285dc383b9c4ada43a9fe9ce36b3141a0369a7065f7a171512c` | `2cce88dd…512c` | **EXACT** |

**Corroboration strength.** The "original" values were independently recorded in the **diagnosis report**
(`…DIAGNOSIS-AND-REMEDIATION-PLAN.md` lines 141–142), which was written **before** implementation. So the
comparison is not circular within the implementation session: the pre-implementation record and my
post-implementation reconstruction agree exactly.

**Conclusion:** both edits are **pure insertions**. Removing the inserted notice restores the exact
original bytes — not one byte of historical content was altered, reordered, or deleted.

---

## 8. §2.2 and §7 byte-for-byte verification

| Section | Current SHA-256 | Report's pre-change SHA-256 | Match |
|---|---|---|---|
| §2.2 | `74cfb2fea89a346c9ff0ce861e4129c29428259b1fa91cb7a41ce0705d4cc9b2` | `b10cdb6dca9017e195b911d98bd603b3f243056dc2146468b2d65888d067a98d` | *apparent mismatch* |
| §7 | `3547522d8e62cc08468c5672c507d2aeae4ba7f35e0f26ae7ce755b2fd0ce63e` | `ba02416da1b943bffb10cd99338a8c406d428fae18b660378f5d92b4ad5f8374` | *apparent mismatch* |

### 8.1 Resolution of the apparent mismatch — NOT a defect

The discrepancy is a **boundary convention**, not content drift. The implementation hashed with
`sed -n '/start/,/end/p'`, which **includes the terminating heading line**. I first sliced
**exclusively** (ending before the next heading). Recomputing with the inclusive convention reproduces
the reported values **exactly**:

| Section | Inclusive-boundary SHA-256 (sed semantics) | Report value | Match |
|---|---|---|---|
| §2.2 | `b10cdb6dca9017e195b911d98bd603b3f243056dc2146468b2d65888d067a98d` | same | **EXACT** |
| §7 | `ba02416da1b943bffb10cd99338a8c406d428fae18b660378f5d92b4ad5f8374` | same | **EXACT** |

Independently, and more importantly, I compared the sections in the **current** file against the
**reconstructed original** (notice removed) using the *same* slicing on both sides:

```
2.2 identical to pre-edit original: True
7   identical to pre-edit original: True
```

**Verdict on §8: PASS.** Both sections are unchanged under any consistent slicing. The historical
non-authorization line `- **No DEF-011 implementation.**` remains present in §7 as historical/normative
context and was **not** converted into a current implementation claim.

**Minor note for future reports:** quoting section hashes without stating the boundary convention makes
them non-reproducible at first glance. Recommend stating "inclusive of terminating heading" next time.
This is non-blocking and affects no content.

---

## 9. Independent verification of B / A / C and open status

### 9.1 `DEF-011-B` — IMPLEMENTED (verified by context, not just count)

`bot/attachments.py` contains exactly **5** `to_thread` occurrences. I inspected each in context:

| Line | Context | Nature |
|---|---|---|
| 88 | `from anyio import to_thread` | import |
| 900 | docstring: "`to_thread.run_sync` بيغطّي نطاقات إلغاء anyio بس…" | documentation of F-02 |
| 953 | `await to_thread.run_sync(_worker)` | **real offload** (store write) |
| 968 | `await to_thread.run_sync(_done.wait)` inside `CancelScope(shield=True)` | **real offload** |
| 1295 | `await to_thread.run_sync(functools.partial(self._sweep_fs_tail, …))` | **real offload** (sweep FS tail) |

Also `bot/handlers.py:17` imports `to_thread` and `:2086` calls `await to_thread.run_sync(` for
`_read_local_capped`. **The notice's description — "five occurrences (module import, one docstring
reference, and three `anyio.to_thread.run_sync` call sites)" — is exactly accurate.**

### 9.2 `DEF-011-A` — NOT IMPLEMENTED (verified against a possible false negative)

`grep -cE "reserv|in_flight|_ledger" bot/attachments.py` → **0**.

I did **not** accept the repo-wide count at face value, because a whole-tree grep does return hits:
`bot/notifier.py:323 in_flight = self._db.list_notifier_pending()` and `ip.is_reserved` in the IP
helper. Inspecting them shows:

- `notifier.py`'s `in_flight` is **notifier inbox deduplication** (`list_notifier_pending`), unrelated to
  attachment byte accounting.
- `is_reserved` is Python's `ipaddress` API.

**Neither is a quota reservation ledger.** `DEF-011-A` is genuinely absent. **CONFIRMED NOT IMPLEMENTED.**

### 9.3 `DEF-011-C` — NOT IMPLEMENTED

Owned by `WP-01`, gated on `OD-01`/`OD-03`. The only `OD-03` reference in the runbook is a config-flag
note (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED`), not UX copy work. No UX copy change exists in the tree.
**CONFIRMED NOT IMPLEMENTED.**

### 9.4 `DEF-011` open status and cross-document agreement

| Document | Statement |
|---|---|
| Proposal (line 29) | "**DEF-011 is NOT fully implemented and NOT closed.**" |
| Proposal (line 43) | "Because `DEF-011-A` and `DEF-011-C` remain unimplemented, `DEF-011` **remains open**." |
| Batch report (line 219) | "**`DEF-011` remains open** — it is **not** fully implemented and **not** closed." |

Both notices state all three sub-defects with **identical status classification** (B implemented,
A/C not) and the **same date** (2026-11-21) and the **same count** ("five"). Neither implies DEF-011 is
implemented or closed. **CONFIRMED — notices agree on all facts.**

---

## 10. T-1 … T-4 quality assessment and execution

### 10.1 Code quality (read independently)

| Test | Assessed as | Notes |
|---|---|---|
| T-1 | Genuine parity test | Parses the notice's status rows via `_sub_defect_status` (real table-row parsing, with `NOT IMPLEMENTED` checked before `IMPLEMENTED` to avoid substring shadowing) **and** cross-checks `ATTACHMENTS_SRC` for `from anyio import to_thread`, `to_thread.run_sync`, and `count == 5`. Ties document claim to source. |
| T-1b | Genuine | Asserts the reservation tokens are absent from `bot/attachments.py`, so if A ever lands the test fails and forces a notice update. |
| T-2 | Genuine, strongest test | Compares §2.2 and §7 to **golden literals embedded in the test file**, so a document-only edit fails. Plus verbatim preservation of the three historical stale statements. |
| T-3 | Genuine but has a minor soft spot | Asserts "remains open"/"not closed" in both notices, and that any "fully implemented" mention is negated. See §14.1 for the soft spot. |
| T-4 | Genuine | Cross-document: same date, same three sub-defect IDs, same "five" count, NOT-implemented present in the report notice. |

**Not vacuous.** The golden literals are hardcoded **in the test** while the subject is **read from
disk**, so the tests fail on document drift. This is the correct direction of dependency — a test that
read its expectations from the document would be vacuous, and these do not.

### 10.2 Execution (my run, isolated container)

```
python -m pytest tests/test_doc_code_parity.py -q   ->  13 passed in 0.03s
```

6 pre-existing + 7 new = 13. All T-1…T-4 pass. **Independently reproduced.**

---

## 11. Baseline vs final full suite (independently reproduced)

| Run | My result | Claimed | Match |
|---|---|---|---|
| **Final** (current tree) | **3449 passed, 1 skipped, 74 warnings** | 3449 / 1 / 0 | **YES** |
| **Baseline** (my reconstruction: removed the 7 appended tests from the test file) | **3442 passed, 1 skipped, 74 warnings** | 3442 / 1 / 0 | **YES** |

**Arithmetic proven, not assumed:** I physically removed the F-03 test block (file went 297 → 91 lines),
re-ran the full suite, got **3442**, then restored the file byte-identically (`restored identical: True`).

```
3442 + 7 = 3449   ✅
```

The 7-test delta corresponds exactly to the 7 added test functions (2×T-1, 2×T-2, 2×T-3, 1×T-4).

### 11.1 The Git-binary reproducibility caveat (verified, and it is real)

The implementation report discloses that a slim image without `git` produced
`5 failed, 3437 passed` in `tests/test_autopush_automation.py`. **I reproduced this class of issue
myself**: my first `apt-get install git` in the reviewer container silently failed (no `apt-get update`),
and `git --version` returned `git: not found`. After `apt-get update && apt-get install -y git`, git
2.47.3 was present and the suite was clean.

**Conclusion:** the 5 failures are a **missing-binary environment artifact**, not a code or F-03 defect.
The autopush tests shell out to `git`. Any environment claiming a clean 3442/3449 baseline **must** have
`git` on `PATH`; this should be stated as a precondition. No test was excluded or skipped to obtain the
result.

---

## 12. Lint, static analysis, security, and Node

All run independently in the reviewer container:

| Gate | Command | Result |
|---|---|---|
| pyflakes | `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **exit 0**, no output |
| Bandit | `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **exit 0**, `Severity: High` count = **0** |
| Node frontend | `node --test tests/frontend/*.test.js` | **pass 280, fail 0** |

Identical to the implementation session's results and to the pre-change baseline (node 280/0).

---

## 13. Mutation evidence — REPRODUCED independently

This is the section where a real review differs from re-reading a report. I **did not** inherit these
results; I re-applied all five mutations to the frozen snapshot with my own script and re-ran the tests.

| # | Mutation | Tests failed (my reproduction) | Matches claimed? |
|---|---|---|---|
| **M1** | Rewrite historical "0 `to_thread`" claim | `test_t2_historical_stale_claims_are_preserved_verbatim` (1) | **YES** |
| **M2** | Delete the entire correction notice | `t1_correction_notice…`, `t3_both_documents…`, `t3_no_claim…`, `t4_both_notices…` (4) | **YES** |
| **M3** | Mark `DEF-011-A` IMPLEMENTED | `test_t1_correction_notice_matches_actual_implementation_state` (1) | **YES** |
| **M4** | Tamper §2.2 by one character | `test_t2_protected_sections_are_byte_for_byte_unchanged` (1) | **YES** |
| **M5** | Diverge correction dates | `test_t4_both_notices_share_date_status_and_scope_language` (1) | **YES** |

Every mutation was confirmed to have actually been applied (`applied=True`), and after restoration the
suite returned to **0 failures**. So the tests genuinely detect each regression they claim to prevent —
they are **not** vacuous.

**Distinction requested by the task:** the implementation session's mutation evidence is *inherited
testimony*. The table above is **independently reproduced review evidence** — same mutations, my own
harness, my own container, my own run.

---

## 14. Findings, limitations, and residual risks

### 14.1 NON-BLOCKING — T-3's negation check is weaker than its name suggests

`test_t3_no_claim_that_all_sub_defects_are_implemented` scans text before each "fully implemented" for
the word "not". It would accept a sentence like *"DEF-011-A is not implemented, but DEF-011 is fully
implemented"* as long as "not" appears before the period. In practice T-1 and T-3's sibling assertion
("not implemented" present) still catch the realistic overclaim — and M2/M3 demonstrate real detection —
so this does not undermine the remediation. **Recorded as an observation, not repaired** (review is
read-only, and the task forbids fixing findings).

### 14.2 NON-BLOCKING — a third document still asserts F-03 is unfixed

`docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md:300` (**untracked**, mtime
2026-11-19) still reads:

```
| **F-03** (stale acceptance doc claiming "0 `to_thread`") | **OPEN / NOT FIXED** | Batch-03 DOC-01; not part of this task. |
```

This is **the same class of defect F-03 is about** — a stale present-tense status claim — in a third
document. It was **deliberately excluded** from the remediation scope by the diagnosis (which recorded
it as a separate historical-attribution issue and instructed leaving it alone), and the implementation
report lists it under "Remaining limitations." I verified it is untouched and I am **not** repairing it.

**Impact assessment:** it is an untracked, task-scoped historical report whose own text says "not part
of this task"; it does not contradict the two corrected documents. So it does not invalidate the
correction. But it **does** mean F-03-class drift is not fully eliminated repo-wide. Anyone reading that
file alone would still believe F-03 is open. Recommend the owner decide whether to append a similar
dated notice there; **not created in this review**.

### 14.3 NON-BLOCKING — publication status

Both corrected documents and both F-03 reports remain **untracked**. The remediation exists only in the
working tree. Nothing is committed or published. That is consistent with the task's no-publish rule, but
it means the correction is **not durable** against workspace loss.

### 14.4 NON-BLOCKING — section-hash boundary convention

See §8.1. Future reports should state the slicing convention so hashes reproduce at first attempt.

### 14.5 Confirmed NOT done (scope boundaries honored)

| Boundary | Verified |
|---|---|
| No source/runtime behavior change | **CONFIRMED** — source hashes unchanged |
| Did not implement `DEF-011-A` | **CONFIRMED** — 0 ledger tokens in `attachments.py` |
| Did not implement `DEF-011-C` | **CONFIRMED** |
| Did not attempt `D6` | **CONFIRMED** — D6 still documented as deferred at `attachments.py:916,966` |
| Did not change approved architecture | **CONFIRMED** — no architecture file touched |
| Did not change §2.2 / §7 | **CONFIRMED** (§8) |
| Did not modify the F-01 attribution issue | **CONFIRMED** — line 300 unchanged, still says "OPEN / NOT FIXED" |
| No exactly-once delivery claim | **CONFIRMED** — no such wording in either notice |
| No broader DEF-011 closure claim | **CONFIRMED** — both say "remains open" |

---

## 15. Explicit confirmation: review was read-only

- **No source, test, or historical document was modified** by this review. All mutation experiments ran
  on a **frozen tarball copy** under `/tmp/rev/work`, never the live repo.
- Live-workspace hashes after review are **identical** to before review:
  - proposal `8fe7d96d…b1533f`, report `217374d2…f2fa5e`, `bot/attachments.py` `b98d561f…4d818356`,
    `tests/test_doc_code_parity.py` `00db35e7…f87fb7`.
- `git status`: `HEAD=52e7789`, **staged 0**, modified 9 — unchanged from the start of the review.
- **No commit, push, PR, merge, deploy, or Autopush activation.** No `git add`, no `git add .`, no
  `git add -A`, no reset/clean/stash/force.
- The temporary reviewer container (`f03-review`) and `/tmp/rev` scratch data were removed; running
  containers = **0**.
- No file was repaired, including the findings in §14.1 and §14.2.

---

## 16. What the owner can rely on

Even without an independent PASS, the following are **independently verified** facts:

1. The remediation is **insertion-only**; original bytes are exactly recoverable (SHA-256 match against
   the pre-implementation diagnosis record).
2. §2.2 and §7 are byte-identical to their originals under any consistent slicing.
3. `DEF-011-B` is implemented (5 `to_thread`, 3 real call sites, contexts inspected);
   `DEF-011-A` and `DEF-011-C` are **not**; `DEF-011` remains **open**, stated in both documents.
4. Full suite: **3442 → 3449** (+7), reproduced by reconstructing the baseline myself.
5. pyflakes 0, Bandit High 0, node 280/0.
6. All 5 mutations are detected — reproduced with my own harness.
7. Scope is exact: 2 documents + 1 test file; all 8 pre-existing files and all source untouched.

**`DEF-011` is NOT closed.** `DEF-011-A` and `DEF-011-C` remain unresolved and `D6` remains deferred.
This review closes **F-03 documentation remediation** only, and even that only as
"technically verified but not independently reviewed."

---

## 17. Recommended next step

To obtain a genuine `F03_REVIEW_PASS`, re-run this review in a **fresh conversation** (new session, no
prior context) against the same branch. Everything needed is already reproducible:
`python -m pytest -q` → 3449, the reconstruction scripts in this report's §7/§11, and the five mutations
in §13. A fresh reviewer should additionally decide whether to append a dated notice to
`…BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` (§14.2).
