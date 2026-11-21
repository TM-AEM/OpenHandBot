# OHB2 — Scope A — Owner Decision Record Validation

**Task:** `OHB2-SCOPE-A-OWNER-DECISION-RECORD-VALIDATION`
**Date:** 2026-11-19
**Type:** read-only authorization validation — no implementation, no publication
**Verdict:** **`BLOCKED_OWNER_AUTHORIZATION_REQUIRED`**

> The owner has **not** signed any Scope A publication decision. No branch, commit, push, PR, or CI
> action was taken. The owner's decision records were **not** edited or signed. No tests were rerun
> (existing evidence reused, candidate bytes verified unchanged).

---

## 1. Dimension summary (kept strictly separate)

| # | Dimension | Status | Evidence |
|---|---|---|---|
| 1 | **Owner authorization** | **`MISSING`** | §2 — 0 ticks, blank signature, no date |
| 2 | **Scope isolation** | **`PROVEN`** | §3 — exactly 5 files, 0 NAV / 0 DEF-011-B / 0 schema |
| 3 | **Existing local test evidence** | **`VALID, NOT RERUN`** | §4 — candidate hashes byte-identical to the 3285-run |
| 4 | **Commit status** | **`NO_COMMIT`** | HEAD still `52e7789`; no branch created |
| 5 | **Publication status** | **`NOT_PUBLISHED`** | nothing pushed, no PR |
| 6 | **CI status** | **`NOT_RUN`** | no PR ⇒ `pull_request` CI cannot trigger |
| 7 | **Independent review status** | **`NOT_ESTABLISHED`** | no separate reviewer or environment |

Local green tests are not CI. CI green would not be independent review. Candidate correctness is not
owner acceptance.

---

## 2. Phase 1/2 — Authorization inspection

### 2.1 Documents inspected (current versions)

| # | Path | Ticked boxes |
|---|---|---|
| 1 | `docs/audits/OHB2-WP07-SCOPE-A-C-GRANT-AUTHORIZATION-AND-SCOPE-REPORT.md` | **0** |
| 2 | `docs/reviews/OHB2-WP07-SCOPE-A-C-GRANT-PUBLICATION-REPORT.md` | **0** |
| 3 | `docs/audits/OHB2-WP07-BATCH04-REV2-OWNER-DECISIONS.md` | **0** (of 12 options) |

### 2.2 The `C-GRANT-SCOPE-A` decision block, as it actually stands

Location: authorization report **§6** (`docs/audits/OHB2-WP07-SCOPE-A-C-GRANT-AUTHORIZATION-AND-SCOPE-REPORT.md`).

```
- [ ] **C-GRANT-SCOPE-A** — "I authorize, and only authorize: …"
- [ ] **C-DENY-SCOPE-A** — "Do not create a branch or PR."
- [ ] **C-DEFER-SCOPE-A** — "Decide later."

Owner signature / date: ______________________
```

**All three boxes unticked. Signature blank. Date absent.** This block is a **quoted draft authored
by the agent** — it is proposed wording, not a recorded owner decision. The surrounding text says so
explicitly: *"Copy the block below into … then sign and date."*

### 2.3 Per-action grant table (§6.1) — all five rows unticked

| # | Statement | Tick |
|---|---|---|
| 1 | "I authorize creating branch `review/ohb2-wp07-scope-a-newdef03` from `52e7789`." | **`[ ]`** |
| 2 | "I authorize committing the five Scope A paths listed above to that branch." | **`[ ]`** |
| 3 | "I authorize pushing that branch to `origin`." | **`[ ]`** |
| 4 | "I authorize opening a PR to `main`." | **`[ ]`** |
| 5 | "I authorize the `pull_request` CI workflow to run on that PR." | **`[ ]`** |

### 2.4 The five required permissions — each verified independently

| # | Required permission | Granted? | Evidence |
|---|---|---|---|
| 1 | Create a dedicated Scope A branch | **NO** | §6 + §6.1 row 1 unticked |
| 2 | Commit the exact isolated Scope A candidate | **NO** | §6 + §6.1 row 2 unticked |
| 3 | Push / publish that branch | **NO** | §6 + §6.1 row 3 unticked |
| 4 | Create a pull request | **NO** | §6 + §6.1 row 4 unticked |
| 5 | Execute the existing PR-triggered CI workflow | **NO** | §6 + §6.1 row 5 unticked |

No permission was inferred from another. All five are absent, so the stop boundary is at the first
action — nothing at all was executed.

### 2.5 Signature and date fields — repository-wide sweep

| Check | Command | Result |
|---|---|---|
| Every `Owner signature / date:` line in `docs/` | `grep -rhoE "Owner signature / date: .*" docs/` | **6 lines, all `______________________`** |
| Any signature line carrying a real value | `grep -rhoE "Owner signature / date: [^_ ]+"` | **none** |
| Ticked boxes, all three governing docs | `grep -cE '^\s*- \[x\]'` | **0 / 0 / 0** |
| Signed grant anywhere in repo | regex sweep (`GRANTED`/`SIGNED`/`YES`, Arabic grant wording) | **none** |
| Grant markers in `.agent/PROGRESS.md` | `grep -nE "C-GRANT\|SIGNED"` | **none** |
| Owner commit since `52e7789` | `git log --oneline -3` | **none** |
| Report file mtime | `ls -l --time-style` | `23:48` = **agent write**, not an owner edit |

**A file modification timestamp is not authorization** — the only mtimes present are the agent's own
report writes.

### 2.6 Subsequent decisions — supersede or revoke check

The task requires checking for any later owner decision that supersedes or revokes the
authorization. Two candidate records were examined:

**(a) `docs/audits/OHB2-WP06-PART2-OWNER-DECISION-REGISTER-OD-WP06-PART2-02.md`** (untracked, dated
2026-11-19, "Decided by: Project owner")

- Subject: **WP-06 Part 2** — the `callback_refs` schema direction (O-5) and its deferral (O-7).
- Header states it **"Supersedes: nothing"** and authorizes **"NO Git operation"**.
- Its binding restrictions explicitly **deny** Git actions and demand separate authorization:
  - **R-7.3** — *"This decision does not authorize committing, pushing, creating PRs, merging, or
    publishing WP-07."*
  - **R-7.4** — *"Any such Git or publication operation requires separate explicit authorization."*
- **Effect on Scope A: neither grants nor revokes it.** It is a separate work package's schema
  decision and contains **no** `C-GRANT-SCOPE-A` field. It reinforces the gate rather than lifting it.

**(b) `docs/audits/OHB2-WP07-BATCH04-OWNER-AUTHORIZATION-BRIEFING.md`** — briefing only; **0 ticked
boxes**, no signature.

**No revoking or superseding Scope A decision exists.**

### 2.7 One material fact from §2.6 that must be recorded

The WP-06 register contains a **correction** relevant to how WP-07 state is described, and it is
accurate — verified directly against the baseline:

| Claim in register | Verified independently | Result |
|---|---|---|
| DEF-006 `concurrent_updates(True)` is **already in `HEAD`** | `git show origin/main:bot/app.py \| grep -c DEF-006` | **1** — ✅ true |
| DEF-013 route renewal is **already in `HEAD`** | `git show origin/main:bot/handlers.py \| grep -c DEF-013` | **1** — ✅ true |
| WP-07 is therefore **partially** committed, not "entirely uncommitted" | candidate diff vs `origin/main` | ✅ consistent |

**Implication for the exclusion list:** DEF-006 and DEF-013 are **pre-existing baseline content**,
not candidate additions. The Scope A candidate does **not** introduce or modify them — it inherits
them from `52e7789`. The "no DEF-006 / no concurrency change" exclusion therefore holds for the
**candidate's own diff**, which is the correct reading.

---

## 3. Phase 2 — Scope isolation (verified on the candidate, not the working tree)

> **Measurement note:** isolation is measured on a **reconstructed candidate**
> (`git archive origin/main` + the 12 handlers hunks + 2 watcher hunks + `bot/db.py` + the two test
> files). The working tree is the **full mixed state** (NEW-DEF-03 + NAV + DEF-011-B) and would give
> false positives — grepping it yields `NAV-0`=7, `to_thread`=2, `maybe_sweep_async`=1.

| # | Condition | Candidate result |
|---|---|---|
| 1 | Only the five approved files included | **exactly 5** files differ from `origin/main` |
| 2 | `bot/handlers.py` only the 12 NEW-DEF-03 hunks | **12 kept / 13 dropped** (of 25) |
| 3 | `bot/watcher.py` only the 2 NEW-DEF-03 hunks | **2 kept / 1 dropped** (of 3) |
| 4 | `NAV-0` = 0 | **0** |
| 5 | `to_thread` = 0 | **0** |
| 6 | `maybe_sweep_async` = 0 | **0** |
| 7 | `sweep_async` in `app.py` = 0 | **0** |
| 8 | `attachments.py` byte-identical to baseline | **YES** |
| 9 | `app.py` byte-identical to baseline | **YES** |
| 10 | Database schema changes | **0** |

**Excluded and confirmed absent:** NAV-01..06 · DEF-011-B · F-01 · DEF-006/concurrency additions ·
Mini App (untouched) · schema changes · unrelated working-tree changes.

**Scope isolation: PROVEN. No `BLOCKED_SCOPE_ISOLATION`.**

---

## 4. Existing local test evidence — reused, not rerun

The task forbids repeating completed tests. The candidate bytes were verified unchanged instead:

| File | SHA-256 (first 12) | vs the run that produced 3285 |
|---|---|---|
| `bot/db.py` | `205f1363aaf0` | identical |
| `bot/handlers.py` | `40dd8902595c` | identical |
| `bot/watcher.py` | `06f3dd4c23e3` | identical |
| `tests/test_handlers.py` | `2b1f978091f4` | identical |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | `ba2633113424` | identical |

Because the bytes are unchanged, the previously recorded results **remain valid for this exact
candidate**:

| Check | Recorded result |
|---|---|
| Full Python suite | **3285 passed** |
| NEW-DEF-03 focused | **47 passed** |
| Full suite + 4 WP-07 regression files | **3334 passed** |
| Frontend | **280 passed** |
| pyflakes | **clean** |
| Bandit severity High | **0** |
| pip-audit | **no known vulnerabilities** |

**Python-version coverage:** those results are **Python 3.13.15 only**. `python3.11` is **not
installed** on this host, so **Python 3.11 compatibility is NOT established** and is not claimed.
CI's matrix is `["3.11", "3.13"]`; only a real PR run could prove the 3.11 leg.

---

## 5. Phase 3 — Stop condition applied

Because the decision is **unsigned and missing all five permissions**, the mandatory stop condition
was applied in full:

| Prohibition | Applied |
|---|---|
| Did not edit the owner's decision | ✅ |
| Did not create or modify any branch | ✅ (2 branches, unchanged) |
| Did not stage or commit | ✅ (staged = 0) |
| Did not push | ✅ |
| Did not create a PR | ✅ |
| Did not trigger CI | ✅ |
| Did not repeat completed tests | ✅ (hash check instead) |
| Did not ask another agent to sign or approve | ✅ |

**Working tree preserved:** HEAD `52e7789`, staged **0**, modified **8**, untracked **54**,
ignored **8**, 2 local branches (`main` + workspace), `.openhands/` and `.agent/` intact,
`ci.yml` unchanged, both archives intact. No `git reset`, `clean`, force push, broad deletion,
`git add .`, or `git add -A`.

---

## 6. Exact missing fields — owner action required

To move from `BLOCKED_OWNER_AUTHORIZATION_REQUIRED` to
`SCOPE_A_AUTHORIZATION_VERIFIED_READY_FOR_PUBLICATION`, the owner must, in an authoritative record:

| # | Missing item | Where |
|---|---|---|
| 1 | Tick **`C-GRANT-SCOPE-A`** (and leave `C-DENY`/`C-DEFER` unticked) | auth report §6, or `OHB2-WP07-BATCH04-REV2-OWNER-DECISIONS.md` |
| 2 | Write the **owner signature** | the `Owner signature / date:` line |
| 3 | Write a **valid date** | same line |
| 4 | Grant all five permissions (via the §6 single grant, or the §6.1 rows individually) | §6 / §6.1 |

The authorization report §6 block is already written and needs only a tick, signature, and date.
**No engineering work remains.**

---

## 7. Explicit non-claims

- **The owner has not authorized publication.** No permission of the five exists.
- **No CI ran.** `ci.yml` triggers on `push[main]` and `pull_request[main]` only; there is **no
  `workflow_dispatch`**, so CI cannot run without a PR — and adding one is forbidden.
- **Python 3.11 is unverified.**
- **No independent technical review** — `INDEPENDENCE_NOT_ESTABLISHED`.
- **WP-07 is NOT complete. DEF-011 is NOT complete.** The remediation program is not complete.
- **DEF-011-B / F-01 are NOT authorized** and were not published.
- DEF-011-A, DEF-011-C, F-02, F-03, WP-09 (Python 3.11), NAV-01..06 acceptance, and DEF-006/OD-04
  remain **open**.
