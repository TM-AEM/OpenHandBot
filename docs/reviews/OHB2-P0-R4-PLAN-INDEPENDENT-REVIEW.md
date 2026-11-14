# OHB2-P0-STAGED-IMPLEMENTATION-PLAN (R4) — Independent Adversarial Review (read-only)

> Prepared by an AI agent (OpenHands) on behalf of the owner. **Read-only review**: the reviewer did
> not author the plan, did not author any prior remediation of it, and treats every claim in the plan
> as a claim to verify, not as evidence. The only repository write is this report at `docs/reviews/`.
> No implementation, test, schema, config, register, plan, `AGENTS.md`, `.agent/PROGRESS.md`, or
> `.openhands/memory/*` change. No commit, push, PR, merge, deployment, release, publication,
> production call, or Autopush activation.

- **Task ID:** OHB2-P0-EXECUTE-MISSING-A0-A1-R4-EVIDENCE (Phase One; originally authored under OHB2-P0-A0-A1-R4-REVIEW-AND-FINAL-CLOSURE).
- **Date (UTC):** 2026-11-11.
- **Verdict:** **`R4_REVIEW_PASS_WITH_NOTES`**.

---

## 1. Artifact identified

| Item | Value |
|---|---|
| Authoritative staged plan | `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` |
| Revision | **R4** (the plan's own header: "Current revision: R4") |
| Task ID in plan | `OHB2-P0-STAGED-IMPLEMENTATION-PLAN-R1` (document lineage; revision R4) |
| **SHA-256 (whole file, computed this session)** | `06be7ea850c0f605ab6c23a161b19da0733143adaba852ddae6650f0836de868` |
| Lines / bytes | 950 lines / 65,143 bytes |
| Historical R3 hash (recorded in plan) | `70858fd7b8563e690e1ee3d01e3d43a4ad71ec0c6d30fcfc334c8e293d5b0997` (historical, not recomputable) |
| Register that authorizes it | `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md`, SHA-256 `1eca72c1c3a6e9962719b59d7ba0d7eff02d5b76e6464f7d052d0d9ea967471c` |

**Evidence class:** the plan is a **tracked/untracked planning artifact** present on disk; its hash was
computed directly in this session. Its self-declared R3 predecessor hash is **historical** (the R3 bytes
are not on disk and are not asserted as re-verifiable here).

---

## 2. Intended scope and sequencing

Traced from the plan (not inferred from later execution):

1. **Groups:** (A) local-only **A0–A4**; (B) transport **B1–B3**; (C) delivery/evidence **C1, C2, D0**
   (plan §1, §6, §9).
2. **Authorization:** only **A0–A4** are `AUTHORIZED TO START — LOCAL-ONLY D-09-R2 EXCEPTION`; B1–B3 and
   Group C are `NOT AUTHORIZED TO START`; release/acceptance `NOT GRANTED` (plan §3.8, §9).
3. **Sequencing:** stages are **dependency-ordered** (§6); A0 is the foundation, then A1, A2, A3, A4;
   each stage is subject to its own dependencies and acceptance criteria (§3.8 "per-stage caveat").
4. **Scope of this review:** the whole plan, with emphasis on §11 and the A0–A4 portion that was
   historically executed.

---

## 3. Acceptance criteria (per the plan)

The plan defines acceptance criteria per stage in §6 (and cross-cutting requirements in §5, §7, §8):

- **A0:** `python -m pytest -q` green; new tables present after init **and after re-init**; evidence =
  test names + `PRAGMA table_info`.
- **A1:** adversarial validation tests pass; **no file created on rejection**; **every incomplete item
  is reachable by the sweep**; evidence = test names + staging-dir listing.
- **A2:** deadline tests pass; isolation tests pass; accept writes a **durable intent outcome** with
  the exact ack-outcome mapping (§6 A2 "Acknowledgement outcome").
- **A3:** atomicity tests (`BEGIN IMMEDIATE`) pass; ack-eligibility correct.
- **A4:** retention/cleanup tests pass; log scan clean; **no new worker/scheduler** introduced.
- **Cross-cutting:** §5 non-negotiable P0 requirements 1–12; §7 ACK-safety prohibitions; §8
  independent-review requirement before P0 completion.

---

## 4. Prerequisites and dependencies

- **§3.3 technical details** that the implementation agent may determine without owner approval
  (staging location, opaque ids, `ATTACHMENT_BATCH_TTL`, ack copy, provisional size/type policy, audit
  events, **and the F7 feature-flag question**).
- **§3.4 blocking owner decisions** D-10…D-24 (these block **B/C**, not A0–A4).
- **§9** per-stage additional blockers: A0 none; A1 **D-12 (PROVISIONAL, not blocking)**; A2 none;
  A3 local-intent-only; A4 local-sweep-only.
- **§11 single recommended next step:** **"Independent adversarial review of this R4 plan before
  starting A0."**

---

## 5. Assessment of §11 (the review requirement) — the decisive question

**§11 states (verbatim):** *"**Independent adversarial review of this R4 plan before starting A0.**
After that review, the locally authorized A0–A4 subset may begin under D-09-R2 …"*

**Findings:**

1. **The plan's own header discloses the gap:** "…**the plan itself has NOT undergone independent
   review.** (Supersedes the R3 note.)"
2. **No R4 plan-review artifact exists.** Exhaustive verification in this session:
   - `docs/reviews/` contains **44 files**; **none** is a review of the staged plan (no
     `*STAGED*`, `*PLAN*R4*`, or `STAGED-PLAN-CODE-EVIDENCE*` artifact).
   - `grep` for `STAGED-IMPLEMENTATION-PLAN` / `STAGED-PLAN` across `docs/` and `.agent/` finds only:
     the plan itself; the previous final-closure report; and incidental references inside A3/A4 reports
     (which cite the plan as a scope reference, not as a reviewed artifact).
   - `git log --all --name-only` shows **no** plan-review file ever committed.
   - The conversation/editor artifacts on disk contain **no** plan-review report.
3. **A prior, different review exists but is not this review.** `OHB2-P0-STAGED-PLAN-CODE-EVIDENCE-AND-WORKTREE-VERIFICATION`
   (verdict `NEEDS_REVISION`) is cited in the plan's R2 revision note as the review that R2 remediated.
   That is an **R2-era** review of an **earlier revision**, and **no durable file** for it exists on
   disk. It is **not** the §11 "review of this R4 plan before starting A0", and it does **not** satisfy
   §11 for R4.
4. **A0 began without the §11 review.** A0's code (`bot/db.py` `OHB2-P0-A0` anchors) and tests
   (`tests/test_attachment_batch_schema.py`) are present, and A1–A4 followed. There is **no evidence**
   that an independent review of R4 was performed and durably recorded **before** A0 started.

**Accurate statement of the historical fact (no rewriting of history):** the §11 prerequisite was
**not fulfilled at the time A0 began**. Implementation of the locally authorized A0–A4 subset
proceeded **without** a durable independent review of the R4 plan. This review cannot and does not
retroactively assert that the prerequisite was satisfied before A0; it records the opposite.

**Does a retrospective review now satisfy the remaining requirement?** The plan's §11 phrasing is a
**prerequisite to *starting* A0** ("before starting A0"), not merely a documentation deliverable. A
retrospective review is therefore **remedial, not conforming**: it verifies the plan's *quality* after
the fact and can close the **documentation/closure** gap, but it **cannot** convert a historically
missed precondition into one that was met. The plan does **not** prescribe a specific owner action to
"validate" a late review, and no retroactive authorization may be invented. Accordingly: the
**closure-documentation requirement is now addressed** by this report, while the **historical §11
precondition remains recorded as unmet-before-A0**.

---

## 6. Were the plan's requirements superseded, amended, or still binding?

| Plan element | Status (verified) |
|---|---|
| §3.8 D-09-R2 local-only A0–A4 exception | **Binding**; matches register §5 → D-09/I exactly (A0–A4 local-only; B/C not authorized; D-19 mandatory for release). |
| §5 non-negotiable P0 requirements 1–12 | **Binding.** |
| §6 per-stage acceptance criteria | **Binding** (each stage "subject to its own documented dependencies and acceptance criteria"). |
| §7 ACK-safety prohibitions | **Binding.** |
| §8 independent-review requirement before P0 completion | **Binding.** |
| §9 authorization matrix | **Binding**; A0–A4 authorized, B1–B3/C1/C2/D0 not. |
| §11 R4-plan review before A0 | **Binding as written; historically unmet before A0.** |
| §12 former owner question | **RESOLVED** (recorded as D-09-R2); retained as resolved history. |
| A1 rollback-by-flag (F7, §3.3/§6 A1) | The plan says a rollback flag "**must be added**"; **no such flag exists** (see §8 below). |

**Amendments/supersessions by later owner decisions:** the plan predates and is complemented by the A3
owner decisions **D-25…D-35** (route validity at the A3 boundary, durable local intent, eligibility,
routing precedence, rejection/ack, message-type scope, non-`pending` blocking, message↔batch identity,
`TERMINAL_UNPROVEN`, identity retention). These **do not conflict** with the plan; they refine the A3
portion the plan left open. The plan's A3 text ("durable dispatch intent", "atomic with outcome")
remains consistent with D-27/D-33/D-34/D-35.

---

## 7. Did the historical A0–A4 execution comply with the plan?

Assessment based on the plan text and the on-disk A0–A4 evidence (the stage-level detail is established
in the companion A0/A1/A2/A3/A4 reviews):

- **Scope compliance:** A0–A4 were implemented as **local-only** stages; no B1–B3, Group C, remote
  transport, delivery, deployment, or release work is present in the reviewed code paths. ✅
- **Architecture compliance:** one SQLite owner/connection, no new worker/scheduler/process (verified
  in the A4 review and re-verified here for A0/A1). ✅
- **Acceptance-criteria compliance:** A0/A2/A3/A4 acceptance criteria are met; A1 meets its criteria
  **except** the §3.3/§6 "rollback-by-flag (F7)" item, which was **not** implemented (no attachment
  feature flag exists). ⚠️ (LOW; see §8).
- **Sequencing:** stages executed in dependency order (A0 → A1 → A2 → A3 → A4). ✅
- **§11:** **not complied with before A0** (see §5). ❌ (documentation/process).

---

## 8. Plan requirement vs. owner-decision register / later decisions — conflicts

- **No material conflict** was found between the plan and the register or the later D-25…D-35 decisions.
- **One plan item is unmet in implementation:** the A1 **F7 rollback flag**. The plan itself flagged
  this as a "design/implementation detail requiring verification at implementation time (and is **not**
  implemented by this document)". Verification in this session: `bot/features.py` exposes only
  `{files, export, cost, followups}`; there is **no** attachment/upload flag in `features.py`,
  `config.py`, `.env.example`, or `bot/app.py`. So A1's rollback is achievable only by
  disabling the handler registration / removing the staging dir — not by a dedicated flag. This is a
  **LOW** deviation from the plan's stated rollback mechanism, **not** a correctness or safety defect
  (see the A1 review for severity rationale).

---

## 9. Findings

| ID | Severity | Finding | Evidence | Blocking? |
|---|---|---|---|---|
| **R4-1** | **Process/documentation (non-code)** | The §11 prerequisite — independent review of the R4 plan **before A0** — was **not** performed/recorded before A0 began. | Plan §11; plan header "has NOT undergone independent review"; exhaustive search found no plan-review artifact. | **Yes, for the closure-documentation requirement** — now **addressed** by this report; **historically unmet** (recorded, not rewritten). |
| **R4-2** | LOW | The A1 rollback-by-flag (F7) was not implemented; no attachment feature flag exists. | `bot/features.py`, `config.py`, `.env.example`, `bot/app.py` (no attachment flag). | No (rollback still possible via handler/dir; not a safety defect). |
| **R4-3** | INFO | The R3 hash in the plan is historical and not re-verifiable (R3 bytes absent). | Plan header; no R3 file on disk. | No. |
| **R4-4** | INFO | The R2-era review `OHB2-P0-STAGED-PLAN-CODE-EVIDENCE-AND-WORKTREE-VERIFICATION` is cited but has no durable file. | Plan R2 note; no file found. | No. |

No BLOCKER/HIGH/MEDIUM **code or safety** finding was found in the plan itself. The only blocking
item is **process/documentation** (R4-1), which this report now documents.

---

## 10. Sequencing / authorization implications

- The **plan content is sound and remains binding**: A0–A4 local-only, B/C not authorized,
  release/acceptance not granted, D-19 mandatory for release.
- The **§11 precondition was historically missed**. Because §11 is a *pre-start* gate, the correct
  characterization is: *A0–A4 started without it; this report is a retrospective review that closes the
  documentation gap but does not retroactively satisfy the gate.* No retroactive authorization is
  invented or implied.
- **No new authorization is created by this review.** It does not authorize B1–B3, Group C, release,
  acceptance, deployment, or any work beyond the existing D-09-R2 A0–A4 exception.

---

## 11. Verdict

**`R4_REVIEW_PASS_WITH_NOTES`.**

The R4 plan is **complete, internally consistent, grounded in the actual repository, and compliant
with the owner-decision register**; its A0–A4 scope, acceptance criteria, sequencing, and authorization
boundary are correct and remain binding, and no material conflict with D-25…D-35 exists. The plan is
**adversarially sound** for the locally authorized A0–A4 work.

The **only** blocking item is the **process/documentation gap R4-1**: the §11 independent review was
**not** performed before A0, and this retrospective review cannot make it so. This report **addresses
the remaining closure-documentation requirement**; the historical fact is recorded, not rewritten. The
single LOW code-side note (R4-2, F7 flag) does not block closure.

Therefore the verdict is **PASS_WITH_NOTES**, not a clean PASS, because a required pre-start review was
historically missed.

---

## 12. Report integrity

- Durable path: `docs/reviews/OHB2-P0-R4-PLAN-INDEPENDENT-REVIEW.md`.
- `/tmp` path: `/tmp/OHB2-P0-R4-PLAN-INDEPENDENT-REVIEW.md`.
- Both copies are byte-identical (`cmp` verified); the shared full-file SHA-256 is recorded in the
  final consolidated report.
