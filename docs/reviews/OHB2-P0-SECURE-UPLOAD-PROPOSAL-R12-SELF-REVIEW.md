# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12 — HOSTILE SELF-REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12-N11-CITATION-REMEDIATION`
**Type:** Self-review (author-side). **NOT an independent review, NOT approval.**
**Scope:** the r12 revision of `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`
(sha256 `6ea52debd62918e831555a7ea4787cde75fa62c75e376ac5df93ece33e34e4dc`, 3185 lines).

This document is deliberately hostile toward my own change: it states what could still be wrong,
what I did **not** verify, and why a fresh independent adversarial review is still required.

## 1. What r12 changed

Documentation-only, in exactly **two** authorized artifacts: the proposal (in place) and this file.

| Finding (from the R11 independent review) | Correction applied | Sites touched |
| --- | --- | --- |
| **N11-1 (LOW)** — `additional_repositories.py` cited "line 89" for the `path=f'{working_dir}/{folder}'` build, but L89 is the `def conversation_repositories(` definition | State the **symbol plus verified line range**: `conversation_repositories` def at line 89; the `path=f'{working_dir}/{folder}'` expression at **line 106** | §1 (r9/R8-2 notice, L332-333), §5.15.6 (L2109-2111), §11 (L2918-2920) |
| **N11-2 (LOW)** — `archiveworkspacepath` tag read cited at "line 1185", but L1185 is a comment | Cite **line 1188** (the read); note line 1185 is the preceding comment; correct the adjacent `count_conversations_by_sandbox_id` citation to `lines 1085-1091` | §11 (L2883-2886) |
| **N11-3 (INFO)** — cron `'* * * * *'` attributed to `sweep.py`, but the declaration lives in `tasks.py` L78 | Re-attribute the declaration to **`tasks.py`** (L78, `name='sweep'` L80); keep `sweep.py` for candidate selection (`find_due_sandbox_ids`); keep `rules.py::decide` → `Action.DELETE` → `tasks.py` → `delete_sandbox` as the behavior chain | §5.10.4 (L1420-1422), §11 (L2892-2897) |

Plus: an **r12 correction notice** in the header, a **r12** lineage bullet, the header **Task ID**
and **Date**, and an **§13** revision row.

**No security requirement, threat-model mitigation, or P0 invariant was weakened; no cleanup
primitive was invented; no previously resolved finding was reopened; no unrelated section was
redesigned.**

## 2. Source re-derivation (done this session, from the pinned revisions)

- `additional_repositories.py` — `OpenHands/enterprise@3fac53df…`, sha256 `a8d0bbe3…`, 453 lines:
  `def conversation_repositories(` **L89**; `path=f'{working_dir}/{folder}' if working_dir else None,`
  **L106**. (A second `path=f'{working_dir}/{folder}'` exists at L155 in a *different* function —
  see §4.)
- `app_conversation_router.py` — same SHA `3fac53df…`, sha256 `c43ed4f7…`, 2209 lines: **L1185** is
  `# Delete the sandbox in the background if no other conversations reference it`;
  `workspace_path = app_conversation_info.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)` is **L1188**;
  `asyncio.create_task(` is **L1189**; the `count_conversations_by_sandbox_id(...) == 0` →
  `delete_sandbox(...)` block is **L1085-1091**.
- `lifecycle/tasks.py` — same SHA, sha256 `834e9452…`, 190 lines: `@lifecycle.periodic(cron='* * * * *')`
  **L78**; `name='sweep'` **L80**; `async def sweep(...)` L82.
- `lifecycle/sweep.py` — same SHA, sha256 `1d99bd1c…`, 57 lines: **no** `cron` token; holds
  `find_due_sandbox_ids` and `LAST_RAN_AT`.

## 3. Self-check performed

- Every occurrence of the three facts was grepped in the full proposal and corrected; the **only**
  remaining "line 89"/"line 1185"/"`sweep.py` cron" strings are inside the r12 correction notice,
  where the withdrawn wording is quoted to explain the fix.
- Structural counts recomputed: 6 fences (balanced); **I1-I15** = 15; **T-01…T-25** = 25 (T-19/T-24/T-25
  present); **U-1…U-12** = 12 (U-12 present); **C1-C5** = 5; **Q1…Q22** = 22; §9 criteria 1-11
  (incl. 7b/7c) intact.
- Regression axes re-grepped: N10-1 (689/690 in both places), N10-2 (`conversation_service.py` under
  the SDK bullet; enterprise bullet says the file is absent), N10-3 (`NOT INDEPENDENTLY VERIFIED` on
  the historical value), R9-1 (operation timer vs separate infrastructure timer), R9-2 (L86),
  R9-3 (container removal vs physical data deletion), R8-1…R8-4, R7-1…R7-4, R6-1…R6-5, N-1…N-5 —
  all present and unmodified in substance.
- Timer scope, Enterprise-vs-Cloud lifecycle scope, container-vs-workspace deletion, workspace-root
  provenance, polled-replica semantics, current-vs-historical OpenAPI evidence, trusted-issuer
  boundary, path containment/authorization — re-read; unchanged.

## 4. Hostile findings against my own change (what could still be wrong)

1. **H1 (self, LOW) — a second `path=f'{working_dir}/{folder}'` exists at L155.** The cited line 106
   is the expression inside `conversation_repositories` (the function the proposal names), which is
   the correct anchor for the tag→root claim. L155 belongs to a *different* function
   (the `ConversationRoot` builder). If a future reviewer reads "line 106" as the *only* such
   expression, that is slightly imprecise — but the proposal names the function and the line
   together, so the reference is unambiguous. **Not changed** (naming the function plus the line is
   the strongest form).
2. **H2 (self, INFO) — the §11 N11-2 edit also corrected `lines 1083-1091` → `lines 1085-1091`.**
   This is a *bonus* precision fix in the same sentence (L1085-1091 is the `else:` + count + delete
   block; L1083 is the end of the failure warning). It is within the N11-2 sentence and does not
   change any claim. Flagged here for transparency, in case a reviewer considers it scope creep —
   it is not a redesign and touches no other fact.
3. **H3 (self, LOW) — the r12 notice is long.** It quotes the withdrawn wording to make the fix
   auditable, consistent with the r10/r11 notices. A reviewer may judge it verbose; it introduces no
   claim.
4. **H4 (self, INFO) — I did not re-run any test or code.** Correct: the proposal is a specification;
   there is no capability to exercise. No claim in r12 rests on executed behavior.

## 5. What I did NOT verify (honest limits)

- The **r11 proposal** is no longer on disk in its pre-r12 byte form; I edited it in place, so a
  byte-diff against r11 is **not** possible from the working tree alone. The change set is enumerated
  in §1 and each edit is anchored to the exact old text.
- I did **not** run an independent adversarial review; by construction this is the author's
  self-review.
- I made **no** production call and used **no** credential.

## 6. Verdict

**Self-assessment: the three N11 findings appear resolved and no earlier finding appears weakened.**
This is a **self-review only** and is **not** independent approval. **A fresh independent adversarial
review is the required next step.** P0 remains **unimplemented and unapproved**.

*This self-review was produced by an AI agent (OpenHands) on behalf of the repository owner.*
