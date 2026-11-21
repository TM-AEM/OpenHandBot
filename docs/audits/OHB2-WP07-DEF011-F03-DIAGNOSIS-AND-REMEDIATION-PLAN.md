# OHB2 — WP-07 / DEF-011 / F-03 — Diagnosis and Remediation Plan

**Task:** `OHB2-WP07-DEF011-F03-DIAGNOSIS-AND-REMEDIATION-PLAN`
**Date:** 2026-11-21
**Type:** diagnosis + planning only. **No source or test file was changed.**

---

## Verdict

# `F03_CONFIRMED_REMEDIATION_READY`

F-03 is real, currently present in the working tree, and reproducible by a one-line count. It is a
**documentation-drift defect**, not a code defect. The remediation is small, has no code risk, and can
be batched into a single follow-up implementation task.

---

## 0. Identifier disambiguation (read first)

Three **different** findings in this repository carry the label `F-03`. Using the wrong one would
produce a nonsense plan, so the distinction is stated explicitly.

| Context | `F-03` means | Where defined | Status |
|---|---|---|---|
| **DEF-011 / WP-07 (this task)** | **Stale acceptance-proposal text** — the proposal still asserts DEF-011 is entirely unimplemented | `OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-REPORT.md` §1.4 (**D-1** / **D-2**); checklist item **SD-5**; called `F-03` in `OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md:300` | **OPEN — this document** |
| WP-05 / `DEF-009` | Missing end-to-end test pinning the Arabic status label | `OHB2-POST-REMEDIATION-CUMULATIVE-INDEPENDENT-REVIEW.md:156` | Closed by `tests/test_f03_status_label_end_to_end.py` |
| P0 decisions register | Incomplete explanation of the U-5/U-6 fold in §4 | `OHB2-P0-OWNER-DECISIONS-REGISTER-INDEPENDENT-ADVERSARIAL-REVIEW.md:476` | Closed in that review |

Only the **first** row is in scope. The other two are mentioned solely to prevent confusion and are
not to be touched.

---

## 1. The original F-03 finding

### 1.1 Wording and severity

The finding was **not** registered in the authoritative remediation baseline. It originated as a
**reviewer-facing discrepancy** in the Batch-03 external-review handoff:

> **Discrepancy D-1:** `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` states
> "`DEF-011` is entirely unimplemented" and lists it under "Explicit non-authorizations" (§7 "No
> DEF-011 implementation"). That document predates the DEF-011 work and is **now stale**. It is
> packaged **as-is** (it is the authoritative record of what was proposed at that time) and flagged
> here rather than edited, per the read-only constraint.
>
> **Discrepancy D-2:** the same proposal's reservation **R9** ("DEF-011 entirely unimplemented") is
> superseded by the current tree. Reviewer must re-verify rather than trust R9.
>
> — `docs/reviews/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-REPORT.md:88-96`

It was later folded into the `F-0x` scheme as:

> `**F-03** (stale acceptance doc claiming "0 to_thread")` — **OPEN / NOT FIXED** — Batch-03 DOC-01
> — `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md:300`

and named as `F-03 (stale acceptance doc)` in
`docs/audits/OHB2-WP07-BATCH04-REV2-OWNER-DECISIONS.md:219` and
`docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-REVIEW-PACKAGE.md:116`.

**Severity:** never assigned a formal severity in the baseline. By effect it is **LOW** —
documentation drift with no runtime impact, but it can mislead an owner or reviewer who reads the
proposal as current fact. I am recording `LOW` as an inference from effect, not as an inherited label.

**Note on the `F-03` mapping.** The F-01 report attributes F-03 to "Batch-03 DOC-01". That pointer is
**imprecise**: `DOC-01` in this repository is a *different* identifier (Mini App session persistence,
`OHB2-PLAN16-DOCUMENTATION-CONSISTENCY-REPORT.md`). The real origin is the Batch-03 handoff
discrepancies **D-1/D-2** and checklist item **SD-5**. This is a citation defect in the F-01 report,
not a second finding; the remediation does not need to chase `DOC-01`.

### 1.2 Exact location and affected "execution path"

There is **no execution path** — this is not a runtime defect. The affected artifact is a document,
and the affected *reader* path is: owner/reviewer opens the proposal → reads §1 bullet 3, §5 R9 → acts
on a false statement.

| Location | Text | Nature |
|---|---|---|
| `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md:26` | `- an entirely **unimplemented** finding (DEF-011).` | **factual claim — STALE** |
| `…:159` | `\| **R9** \| **DEF-011 is entirely unimplemented** … \| 0 \`to_thread\` in \`attachments.py\`; 0 quota ledger \|` | **factual claim — PARTLY STALE** |
| `…:189` | `- **No DEF-011 implementation.**` | **normative non-authorization — still valid, DO NOT CHANGE** |
| `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md:216` | `\| 1 \| **DEF-011 is entirely unimplemented** (no \`asyncio.to_thread\` in \`attachments.py\`, no quota ledger) …` | **second propagating copy — STALE** |

**Critical distinction.** Line 189 sits under "§7 Explicit non-authorizations" and is a *rule about
what the owner was authorizing at that time*, not an assertion about code. It must be **preserved**.
Lines 26/159 are *assertions of fact about the tree* and are the actual defect.

The second copy at `OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md:216` was **not** previously recorded
under F-03. I found it while tracing citations. It repeats the identical false claim, so fixing only
the proposal would leave the drift alive.

### 1.3 Original evidence

The Batch-03 handoff produced the evidence by direct source inspection, not by running code:

```
bot/attachments.py:909   await to_thread.run_sync(   # store write
bot/attachments.py:1199  await to_thread.run_sync(   # sweep fs tail
bot/handlers.py:2086     await to_thread.run_sync(   # _read_local_capped
```
— `OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-REPORT.md:75-85`

### 1.4 Why it was classified as a separate finding

It was separated from F-01 (reaper `_remove_file` on the loop thread) and F-02 (`_accept_lock`
released while the worker writes) because it is **categorically different**: F-01/F-02 are code
defects requiring code fixes and regression tests; F-03 is a **documentation-accuracy** defect
requiring a text correction. It has no shared state, no test surface, and cannot be mutation-tested.

### 1.5 Prior partial work

**None.** No document was corrected, and no test covers it. The Batch-03 handoff explicitly declined
to repair it ("No repair was attempted. Both are documented, not fixed."), and the Batch-04 F-01 task
declared it out of scope. The checklist's own instruction was:

> **Confirm** this is documentation drift, not a code defect, and that it must not be edited
> retroactively. — `OHB2-WP07-BATCH03-EXTERNAL-REVIEW-FINDINGS-TEMPLATE.md:86-88`

### 1.6 Current status

**OPEN and fully reproducible.** See §3.

---

## 2. Current baseline

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| `HEAD` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (identical — no drift) |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| Staged / modified / untracked / ignored | `0` / `8` / `89` / `8` |
| `.openhands/`, `.agent/` | present, untouched |

### Hashes of F-03-relevant files

| Path | SHA-256 | Tracked? |
|---|---|---|
| `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` | `82fbf9869e9393b5f3c7d756aea82991ffff97a77124a8dfbb9f82d2681c2b7c` | **untracked** |
| `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md` | `2cce88dd4290a285dc383b9c4ada43a9fe9ce36b3141a0369a7065f7a171512c` | **untracked** |
| `bot/attachments.py` (reference only, not to change) | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` | untracked (pre-existing work) |

Both defective documents are **untracked**. That matters for the remediation: nothing in Git history
has to be rewritten, and no `git revert`/rewrite is involved.

---

## 3. Root-cause analysis and reproduction

### 3.1 Reproduction (deterministic, read-only)

```bash
cd /workspace/project/OpenHandBot

# Claim in the doc: "0 to_thread in attachments.py"
grep -c "to_thread" bot/attachments.py        # → 5

# Claim in the doc: "0 quota ledger"
grep -cE "reserv|in_flight|_ledger" bot/attachments.py   # → 0
```

Observed:

| Doc claim | Measured | Verdict |
|---|---|---|
| `0 to_thread` in `attachments.py` | **5** | **FALSE — stale** |
| `0 quota ledger` | **0** | **TRUE — still correct** |
| "DEF-011 is entirely unimplemented" | sub-defect **B is implemented**, **A is not**, **C is WP-01** | **FALSE — stale** |

Exact occurrences of `to_thread` in `bot/attachments.py`:

```
88:   from anyio import to_thread
900:  (docstring reference)
953:  await to_thread.run_sync(_worker)
968:  await to_thread.run_sync(_done.wait)
1295: await to_thread.run_sync(  (sweep fs tail)
```

### 3.2 Root cause

**Mechanism: temporal coupling without supersession markers.**

The proposal was written on **2026-11-19** to describe the tree as it existed then. DEF-011-B was
implemented *afterwards*. The document was deliberately **not** edited — correctly, because it is a
historical record of what was proposed. But it was also never given a **supersession notice**, so its
present-tense factual statements ("Verification against the current tree", §2.2; reservation R9, §5)
continued to read as current truth.

This is **not**:
- a cancellation or concurrency defect (F-02),
- a filesystem/offload defect (DEF-011-B, F-01),
- a SQLite-ownership defect (DEF-011-A, NEW-DEF-03),
- a repeated-cancellation defect (**D6**, deferred),
- an exception-handling defect.

It is **documentation lifecycle**: an immutable historical record lacking a "this is now out of date"
banner, whose stale statements are quoted elsewhere as if authoritative.

**Why it matters in practice:** the proposal is cited as authority by at least four other records
(`O7-READINESS-ASSESSMENT.md:29`, `NEW-DEF03-S3-…RECONCILIATION.md:33`,
`BATCH04-REV2-S3-EXECUTION-REPORT.md:28`, `GIT-STABILIZATION-PLAN.md:203`). A reader following those
citations lands on "DEF-011 is entirely unimplemented" and may wrongly conclude WP-07 has no
implementation at all — which is the opposite of the truth for sub-defect B.

### 3.3 The tension that shapes the fix

Two repo rules collide:

1. **Do not rewrite history** — the Batch-03 checklist says the proposal "must not be edited
   retroactively", and it is the authoritative record of what was proposed on 2026-11-19.
2. **Do not leave misleading current-tense claims** — the document asserts facts about "the current
   tree" that are now false.

The standard resolution, and the one this plan adopts, is **append-only correction**: keep every
original sentence byte-identical, and add an explicit dated correction notice that states which claims
are superseded and what is true now. This satisfies both rules. It also matches the repository's own
precedent — `docs/OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md:47` uses `~~old~~ **SUPERSEDED by …**`
inline, and `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md:140` uses
`**⚠ SUPERSEDED by r6**`.

### 3.4 Relation to F-02, D6, DEF-011-A/C, NEW-DEF-03, NAV-01..06

| Item | Relation to F-03 |
|---|---|
| **F-02** (lock released while worker writes) | **None.** Different finding, different category (code vs doc). F-03 does not touch `_accept_lock` or `store_async`. |
| **D6** (repeated raw cancellation during drain) | **None.** Deferred and out of scope; F-03 does not implement it. |
| **DEF-011-A** (quota reservation ledger) | **Documentation only.** A remains unimplemented; the correction must *say so truthfully* rather than fix it. |
| **DEF-011-C** (attachment UX copy) | **None.** Owned by WP-01; not mentioned in the correction beyond noting it stays open. |
| **NEW-DEF-03 / NAV-01..06** | **None.** A-1..A-5 and NAV claims in the proposal are **still accurate** (verified in §4.2) and must not be touched. |

---

## 4. Proposed remediation (one consolidated change)

### 4.1 Design decision

**Append-only correction. Do not rewrite the historical sentences. Do not delete anything.**

Rationale: the proposal is a dated snapshot and its value depends on remaining unaltered. Rewriting
`R9` in place would destroy the record of what the owner was actually asked to decide on 2026-11-19
and would silently falsify an audit trail. An appended notice achieves accuracy without falsification.

### 4.2 Verified facts the correction must state

| Sub-defect | Status **now** | Evidence |
|---|---|---|
| **DEF-011-B** (filesystem offload) | **IMPLEMENTED** | `to_thread` ×5 in `bot/attachments.py` (lines 88, 953, 968, 1295 + docstring 900); `bot/handlers.py:2087` `functools.partial(_read_local_capped, …)` inside `to_thread.run_sync` |
| **DEF-011-A** (quota reservation ledger) | **NOT IMPLEMENTED** — remains open | `grep -cE "reserv|in_flight|_ledger" bot/attachments.py` → `0`; blocked by D-12 / OD-04 |
| **DEF-011-C** (attachment UX copy) | **NOT IMPLEMENTED** — owned by WP-01 | Blocked on OD-01/OD-03 |
| **A-1 … A-5** (Scope A) | **still present** — proposal §2.2 remains accurate | 4 db helpers present (`add_watched_and_record_outcome`, `remove_watched_completing`, `clear_awaiting_and_record_outcome`, `set_awaiting_and_record_outcome`); 6 NAV handlers present |
| **DEF-011 overall** | **NOT closed** | B implemented; A and C open |

So the correction is **narrower than "DEF-011 is implemented"**: only B is. Stating "DEF-011 is now
implemented" would be a *new* falsehood. This is the single biggest risk in the remediation and the
plan guards it explicitly (§4.5, test T-3).

### 4.3 Exact file and line scope

**File 1 — `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md`**

- **Insert** a correction block immediately after the existing ⚠ blockquote (after line 13), before
  `## 1. Why the scope must be split`.
- **Do not modify** lines 26, 159, or 189. Instead, the inserted block names them by line/section and
  marks them superseded.
- **Do not** alter the title, Task ID, date, status header, or any other section.

Proposed block (wording may be tightened at implementation; content must not change):

```markdown
> ## ⚠ LATER CORRECTION — 2026-11-21 (append-only; original text above is unchanged)
>
> This proposal was written on 2026-11-19 and is preserved **as-is** as the authoritative record of
> what was proposed then. Three of its statements about DEF-011 are **superseded** and must not be
> read as current:
>
> | Original statement | Location | Superseded by |
> |---|---|---|
> | "an entirely **unimplemented** finding (DEF-011)" | §1, bullet 3 (L26) | DEF-011-B is now implemented |
> | Reservation **R9** "DEF-011 is entirely unimplemented … 0 `to_thread` in `attachments.py`" | §5 (L159) | `bot/attachments.py` now has 5 `to_thread` uses |
>
> **What is true as of 2026-11-21:**
>
> - **DEF-011-B** (filesystem offload) — **IMPLEMENTED.** `bot/attachments.py` offloads the store write
>   and the sweep filesystem tail via `anyio.to_thread.run_sync`; `bot/handlers.py` offloads
>   `_read_local_capped`.
> - **DEF-011-A** (quota reservation ledger) — **NOT IMPLEMENTED.** Still blocked by `D-12` / `OD-04`.
>   The "0 quota ledger" half of R9 remains correct.
> - **DEF-011-C** (attachment acceptance UX copy) — **NOT IMPLEMENTED.** Owned by `WP-01`, blocked on
>   `OD-01` / `OD-03`.
> - **DEF-011 is therefore NOT closed.** Only sub-defect B landed.
>
> §2.2 ("Verification against the current tree") and §7 ("No DEF-011 implementation") are **not**
> affected by this correction: §2.2 remains accurate for A-1…A-5, and §7 is a normative
> non-authorization, not a claim about code.
```

**File 2 — `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md`**

- **Insert** an equivalent, shorter correction note directly under the `## 11. Findings that materially
  changed the picture` heading, before the table.
- **Do not modify** row 1 of that table (line 216).

```markdown
> **⚠ LATER CORRECTION — 2026-11-21.** Row 1 below ("DEF-011 is entirely unimplemented") was accurate
> on 2026-11-19 and is now **superseded for sub-defect B only**: `bot/attachments.py` now offloads
> filesystem I/O via `anyio.to_thread.run_sync`. **DEF-011-A** (quota ledger) is still **not
> implemented**, and **DEF-011 is still not closed**. Row 1 is preserved unchanged as a historical
> record.
```

### 4.4 Explicitly out of scope

- `bot/attachments.py`, `bot/handlers.py`, `bot/db.py`, `bot/watcher.py`, `bot/app.py` — **no code change.**
- Any test file — **no test change.** This defect has no test surface.
- **D6** — not implemented.
- **DEF-011-A** — not implemented; only described accurately.
- **DEF-011-C** — not touched (WP-01).
- **NEW-DEF-03 / NAV-01..06** — not touched.
- Git: no commit, push, branch, or PR (unless the owner separately authorizes publication).
- Repository settings, secrets, visibility, workflows — untouched.

### 4.5 Regression tests and negative controls

A documentation fix cannot be unit-tested in the usual sense, and inventing a mock test for prose
would be fake work. The honest, meaningful checks are **content assertions** that fail if the drift
returns. If the project has a docs-parity test surface (`tests/test_doc_code_parity.py` exists — see
`NEW-DEF-08`), the cheapest robust option is a small addition there. Two viable scopes:

**Option 1 — no test (minimum).** Rely on the §5 verification commands. Acceptable because the change
is prose-only and CI cannot regress prose.

**Option 2 — one parity assertion (recommended).** Add a single test to the existing docs-parity
module asserting that any document which mentions `DEF-011` *and* `to_thread` in the same stale claim
either carries a `LATER CORRECTION` marker or is listed as historical. Concretely, the minimal robust
form:

| Test | Asserts | Fails when |
|---|---|---|
| **T-1** | `OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` contains `LATER CORRECTION` and the string `DEF-011-A` | the correction block is removed |
| **T-2** | The same file still contains the original `R9` line **verbatim** | someone rewrites history instead of appending |
| **T-3** | The correction does **not** claim DEF-011 is fully implemented — i.e. it contains `NOT closed` and `DEF-011-A` + `NOT IMPLEMENTED` | someone "fixes" the drift by overclaiming |
| **T-4** | `OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md` contains `LATER CORRECTION` | the second copy is missed |

**T-2 and T-3 are the important ones.** T-2 is the negative control against *over-correction*
(destroying the audit trail); T-3 is the negative control against *false correction* (claiming A and C
landed). Both are mutation-checkable by hand: delete the marker or flip "NOT closed" to "closed" and
the test must go red.

If the repo prefers zero test-surface growth for prose, **Option 1 is acceptable** and must be stated
as such in the implementation report rather than silently skipped.

### 4.6 Verification commands

```bash
cd /workspace/project/OpenHandBot

# 1. F-03 gone: both docs carry the correction marker
grep -c "LATER CORRECTION" docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md   # ≥1
grep -c "LATER CORRECTION" docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md        # ≥1

# 2. History preserved: original R9 line still present verbatim
grep -c "0 \`to_thread\` in \`attachments.py\`; 0 quota ledger" \
  docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md                             # 1

# 3. No overclaim: correction names A and C as open
grep -c "DEF-011-A" docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md           # ≥1
grep -c "NOT closed" docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md          # ≥1

# 4. No code or test touched
git status --porcelain bot/ tests/                                                            # empty (beyond pre-existing)

# 5. Full gates (unchanged expectations — nothing functional changed)
python -m pytest -q
node --test tests/frontend/*.test.js
python -m pyflakes bot/ automation/ tools/ main.py tests/
python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
```

### 4.7 Expected evidence

| Check | Expected |
|---|---|
| Correction marker in both docs | present |
| Original R9 text intact | unchanged, byte-identical |
| `DEF-011-A` / `NOT closed` stated | present |
| `bot/`, `tests/` diffs | **none** |
| `python -m pytest -q` | same pass count as the current baseline, **0 new failures** |
| pyflakes | 0 |
| bandit severity High | 0 |
| Node frontend tests | same as baseline |

Because the change is prose-only, **the suite result must be identical to the pre-change baseline**.
Any movement means something else was touched and the step must be reverted.

---

## 5. Acceptance criteria

| # | Criterion | How verified |
|---|---|---|
| **AC-1** | Both stale documents carry a dated `LATER CORRECTION` notice naming the superseded statements | `grep -c "LATER CORRECTION"` ≥1 in each |
| **AC-2** | Original sentences are **unchanged** — no retro-edit, no deletion | `grep` finds the original `R9` line verbatim; `git diff` shows insertions only |
| **AC-3** | Correction states DEF-011-B implemented, **A and C not implemented**, and **DEF-011 not closed** | `grep` for `DEF-011-A`, `NOT closed` |
| **AC-4** | No source, test, workflow, or schema file changed | `git status --porcelain bot/ tests/ .github/` shows nothing new |
| **AC-5** | Full Python suite and Node tests match the pre-change baseline exactly | run both, compare counts |
| **AC-6** | pyflakes 0, bandit severity High 0 | run both |
| **AC-7** | D6 remains unimplemented; DEF-011-A/C remain unimplemented | `grep` for D6 markers unchanged; no ledger code added |

---

## 6. Dependencies and unresolved decisions

| # | Item | Impact on F-03 |
|---|---|---|
| 1 | **The append-only approach itself** | Chosen here as the conservative reading of "must not be edited retroactively". If the owner prefers in-place correction, AC-2 changes — **but that would alter an audit record and needs explicit owner approval.** |
| 2 | **Whether to add a docs-parity test** (Option 1 vs 2) | Affects AC-5/AC-6 scope only. Option 1 is acceptable. |
| 3 | **Publication** | Both files are **untracked**. Committing them is a Git action not authorized by this task and not required to close F-03. |
| 4 | **DEF-011-A / OD-04 / D-12** | Not a blocker. The correction simply states A remains open. **No architectural decision is required or changed.** |
| 5 | **DEF-011-C / WP-01 / OD-01 / OD-03** | Not a blocker; stated as open. |
| 6 | **No new architectural decision is needed.** | F-03 requires no change to the one-bot/ASGI process, the single SQLite owner, outbox/workers, or schema. |

---

## 7. Confirmation of read-only conduct

- **No production source file was modified.** `bot/attachments.py` hash unchanged
  (`b98d561f…`) — pre-existing untracked work, preserved.
- **No test file was modified.**
- **No schema, dependency, workflow, or repository setting was changed.**
- **No commit, push, branch, or PR was created.**
- **No `git reset`, `git clean`, `stash`, or destructive operation was run.**
- Pre-existing state preserved: `HEAD 52e7789`, `0` staged, `8` modified, `89` untracked, `8` ignored,
  `.openhands/` and `.agent/` intact.
- The only file written by this task is this report.

---

## 8. What the next (second) task must do

One consolidated implementation task, no sub-prompts:

1. Insert the two correction blocks exactly as scoped in §4.3 — **append-only**, touching nothing else.
2. Optionally add tests **T-1…T-4** to the existing docs-parity module (§4.5, Option 2 recommended).
3. Run the §4.6 verification commands and record real output.
4. Run the full gates and confirm the suite count is **identical** to the pre-change baseline.
5. Report with `AC-1…AC-7` each marked met/not met with evidence.
6. **Do not** implement D6, DEF-011-A, or DEF-011-C. **Do not** claim DEF-011 is closed.
7. **Do not** commit or push unless the owner separately authorizes it.

**No further diagnosis prompt is needed.** The root cause is established, the defect is reproduced,
and the fix is fully specified.
