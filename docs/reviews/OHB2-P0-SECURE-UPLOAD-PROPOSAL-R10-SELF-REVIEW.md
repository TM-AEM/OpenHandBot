# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10 — HOSTILE SELF-REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-R9-INDEPENDENT-FINDINGS-REMEDIATION`

**Status of this document:** the **author's own hostile consistency review** of the r10 proposal
(`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`). It is **not** an independent
review: the R9 findings were remediated by the same agent that produced r9, so this is
**self-assessment**, not independent assurance. An **independent adversarial review of r10 is still
required**. Every claim that could not be verified is marked **UNVERIFIED** or **SOURCE REQUIRED**; no
test outcome or source semantic is fabricated.

- **Repo:** `TM-AEM/OpenHandBot` · **branch** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` ·
  **HEAD** `907b20de3fa6627795c14f29677e9f39c68e82f4` · **origin/main** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **r9 proposal SHA-256 (input):** `78507f5b0f21984a335294b746704e92d9e7de7f58eddfc833240c3a5f59faee` (2978 lines).
- **r10 proposal SHA-256 (output):** `c19eb3cd801def4b089b3a7c6667e8218c3a6e1caa684e62f113259a94847222` (3072 lines).
- **Driving review:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  (sha256 `62c074d467d8665efe9841f93411abdd0cc2194cc1b0cde041565b349ac46a02`, 280 lines), verdict
  **`NEEDS_REVISION`**, findings **R9-1** (MEDIUM) + **R9-2** (LOW) + **R9-3** (LOW) + **R9-4** (INFO).
- **Scope:** documentation only. **No code, test, schema, or runtime change. P0 is NOT implemented.**
- **Method:** read the R9 review findings R9-1…R9-4 and §9 "required changes" in full; re-verified the
  cited facts against the pinned public source (re-fetched and re-hashed this session); applied the r10
  corrections; then attempted to *break* r10 on the same axes (timer scoping, container-vs-workspace
  deletion, citation accuracy, historical-evidence labelling) and on cross-section consistency.

---

## 1. Evidence re-verification (this session, read-only)

Sources fetched from the **pinned revisions** already used at r2–r9
(`OpenHands/enterprise@3fac53df8c2efcb67ff3537d1162e8c8a108f565`,
`OpenHands/software-agent-sdk@9f7d5cb11b1256c1878f5584a657401feca9ad16`,
`OpenHands/sandbox-server@43e91604ccd0a9960c8d5c52faadd60b30f10e63`), plus the **live** Cloud V1 spec.
**No production call, no credential, no secret access.**

| # | Claim (finding) | Source (pinned, sha256 prefix) | Result |
| --- | --- | --- | --- |
| 1 | The R8-1 "no timer deletes C2" wording contradicts the modeled lifecycle (R9-1) | `enterprise` `…/sandbox/lifecycle/tasks.py` `834e9452…` (cron `* * * * *`, `sandbox_service.delete_sandbox`); `…/lifecycle/rules.py` `0f0df7a9…` (`Action.DELETE`/`Reason.INACTIVE`); `…/lifecycle/settings.py` `1cdd88d5…` (`delete_after_seconds` default 10 days) | **MATCH** — a real server-side timer removes the sandbox; the absolute wording had to be scoped |
| 2 | `RESERVED_TAG_KEYS` is at line **86**, not 96 (R9-2) | `enterprise` `…/app_conversation/app_conversation_models.py` `7a4a54c0…`: `RESERVED_TAG_KEYS = frozenset(` at **L86**; `def _validate_caller_tags(...)` at **L96** | **MATCH** — §11 corrected to L86 |
| 3 | The verified teardown mechanism is **container removal**; the workspace layout is mount-dependent (R9-3) | `enterprise` `…/sandbox/docker_sandbox_service.py` `_delete_at_provider` → `container.remove()`; `DockerSandboxServiceInjector.mounts: list[VolumeMount] = Field(default_factory=list)` (**empty default**); `…/sandbox/docker_sandbox_spec_service.py` `working_dir='/workspace/project'`, `OH_CONVERSATIONS_PATH='/workspace/conversations'` (in-container) | **MATCH** — physical deletion of the **underlying** workspace data is layout-dependent ⇒ **UNVERIFIED / SOURCE REQUIRED** for host-mounted layouts |
| 4 | The r8-era spec digest `0086b0b0…ff77916` cannot be independently confirmed (R9-4) | r8 proposal **not on disk**; the pinned r8 **review** (`843bb33e…`) records only "`1.87.1` / 242 paths" (no hash); r7 review says it "relied on the proposal's `1.87.1`" | **MATCH** — retained only as a **reported, NOT INDEPENDENTLY VERIFIED** historical value |
| 5 | The current Cloud V1 spec is `1.91.0` / 244 paths (context) | live `openapi.json` sha256 `f0f4d4e9…`; `multipart` = 0, `binary` = 0, no `attach`/`upload` path | **MATCH** (unchanged from r9) |

**Source-revision note:** the pinned SHAs are unchanged from r2–r9. This task **changed no source
attribution of a pinned revision**; the only source-fact corrections are (a) the `RESERVED_TAG_KEYS`
line (86 not 96), and (b) the newly-explicit statement that the modeled teardown removes the
**container** and that physical deletion of the **underlying** workspace data is **not** established for
all mount layouts.

---

## 2. Remediation mapping — all four R9 findings

| # | R9 finding | r10 location(s) | r10 action | Self-assessment |
| --- | --- | --- | --- | --- |
| **R9-1** | MEDIUM: r9 documented the Enterprise sandbox-lifecycle timer but left **absolute** statements ("no timer deletes C2", "C2 is never timer-deleted", "the only server-side clock is `expires_at`") that contradict it | §5.9 (`expired`), §5.10.1 (C2 row), §5.10.2 (stored-timer rule), §5.10.3 (case 4 + invariant), §5.10.4 (storage-growth bullet), §5.14.2 step 7, §6 T-24, §8.4, §12 Q18, §11(f), §13 | Replaced **every** absolute statement with **scoped** wording: the **operation's `expires_at`** reclaims **C1/C3 only** and **never** deletes **C2**; a **separate** infrastructure timer (the Enterprise sandbox lifecycle, `delete_after_seconds`) **may** remove the sandbox **and its workspace** in governed environments; the two clocks are **distinct and must not be conflated**; applicability to the **Cloud/runtime-api** backend is **delegated** and **not assumed**; the existence of any infrastructure lifecycle timer **does not prove** a conversation reached a safe terminal-use state. The **C2-must-not-be-deleted-while-in-use invariant is preserved** and now explicitly binds the **application** (it does **not** claim the application can prevent external infrastructure deletion). **No cleanup primitive invented; no policy change.** | **RESOLVED.** Residual: the **Cloud/runtime-api** bound remains external/UNVERIFIED (as at r9) |
| **R9-2** | LOW: §11 cited `RESERVED_TAG_KEYS` at "line 96"; the correct line is 86 | §11 (source entry) | Corrected §11 to **line 86**, noting line 96 is `def _validate_caller_tags(...)` (the validator that **uses** the constant). §5.15.6 already cited line 86. **No validation behavior or security contract changes.** | **RESOLVED.** |
| **R9-3** | LOW: the modeled teardown is **container removal**; whether the **underlying workspace data** is deleted depends on mount behavior | §5.10.1 (C2 row), §5.10.4 (new r10/R9-3 paragraph), §5.14.2 step 7, §11(f) | Added an explicit qualification separating (i) **container removal** (verified), (ii) **mounted workspace data** (layout-dependent; **not** deleted by container removal if bind-mounted), (iii) **physical deletion of underlying workspace files** (**UNVERIFIED / SOURCE REQUIRED** for host-mounted layouts), (iv) **any external storage lifecycle** (deployment/runtime-api owned). The **R8-1 correction stands** (the removal path **is** modeled, contra r8); no mount-cleanup guarantee is invented; no C2 cleanup policy changed. | **RESOLVED** (as a factual qualification) |
| **R9-4** | INFO: the r8-era spec digest `0086b0b0…ff77916` could not be independently confirmed | §1 (R8-4 note), §2.1 (source table), §2.2, §11 | Labelled the digest a **historical reported value — NOT INDEPENDENTLY VERIFIED** (retained for audit history; the r8 proposal is not on disk and no artifact establishes the digest; the r8 review records only "`1.87.1` / 242 paths"). It is **not** used as evidence for current route behavior; the **current** evidence is the re-verified `1.91.0` / 244 paths / `f0f4d4e9…`. Historical context kept, not removed. | **RESOLVED.** |

**Preservation:** no security requirement, threat-model row, or P0 invariant was **weakened**. The r10
changes are **precision/consistency** fixes: r9 was **substantively correct** but left an over-broad
denial in four places; r10 narrows the denial to the **operation-scoped** timer while **keeping** the
C2-safety invariant and all fail-closed rules. The four-gap conclusion, the rejected approaches, the §6
threat table (T-19/T-24 refined; T-25 unchanged), and §8 invariants I1–I15 remain intact.

---

## 3. Attempts to break r10 (hostile checks)

| # | Attack | Result |
| --- | --- | --- |
| 3.1 | "r10 weakened the C2-safety invariant by admitting a lifecycle timer can remove the workspace." | **Blocked.** §5.10.3 invariant still forbids the **application** deleting any copy needed for reconciliation or active use; §5.10.4 keeps the sweeper a **sandbox-scoped idle bound, not an F7 signal**; C2 is still **never** deleted at `expires_at` and **never** on conversation archive/delete. The invariant now binds the **application** and does not over-claim ability to stop external deletion. |
| 3.2 | "r10 now claims the application **can prevent** external infrastructure deletion." | **No.** §5.10.3 states explicitly the application **cannot** prevent that external deletion; the lifecycle timer is infrastructure-owned. |
| 3.3 | "r10 conflates the operation `expires_at` with the infrastructure lifecycle timer." | **Blocked.** Every touched section now states they are **distinct** clocks and **must not be conflated**; T-24 adds the conflation itself as the failure mode. |
| 3.4 | "r10 claims the Enterprise lifecycle governs the **Cloud/runtime-api** backend." | **No.** §5.10.4/§12 Q18 keep the Cloud/runtime-api lifecycle **delegated to runtime-api** and **not assumed**; the applicability limit is retained. |
| 3.5 | "r10 treats `container.remove()` as proof of **universal** physical workspace deletion." | **No.** §5.10.4 separates container removal from physical file deletion and labels the latter **UNVERIFIED / SOURCE REQUIRED** for host-mounted layouts. |
| 3.6 | "r10 re-introduced a wrong citation (`RESERVED_TAG_KEYS` line 96)." | **Blocked.** §11 now cites line **86**; the only occurrence of "line 96" is the explicit correction notice (§1, §11). |
| 3.7 | "r10 presents the r8 digest `0086b0b0…` as verified." | **No.** §1/§2.1/§2.2/§11 label it **NOT INDEPENDENTLY VERIFIED** and forbid its use as current route evidence. |
| 3.8 | "A security requirement or invariant was dropped." | **No weakening.** All invariants I1–I15 present; T-19/T-24/T-25 present; §6 mitigations intact; P0 requirements (§9) unchanged. |
| 3.9 | "r10 invents a C2 cleanup primitive or closes the retention bound by assertion." | **No.** §5.10.4/Q18 keep it an **open owner decision**; no primitive is invented. |

---

## 4. State-model, lifecycle, and crash-window re-check (independent)

| Item | r10 claim | Check | Verdict |
| --- | --- | --- | --- |
| Observable states | `stored \| delivered \| rejected \| failed \| expired`; `accepted` internal-only | §5.5/§5.9 agree | **CONSISTENT** |
| Operation timer | `expires_at` reclaims **C1/C3 only**; **never** C2 | §5.9 + §5.10.1 + §5.10.2 + §5.10.3 + §5.14.2 step 7 + §8.4 + §6 T-19/T-24 + §8.1 I12 + §12 Q18 agree | **CONSISTENT** |
| Infrastructure timer | Enterprise sandbox lifecycle (`delete_after_seconds`) **may** remove the sandbox **and its workspace** (managed backends); **delegated** for Cloud/runtime-api; **not** an F7 signal | §5.10.1 + §5.10.4 + §5.14.2 step 7 + §6 T-24 + §11(f) + §13 agree; explicitly **distinct** from `expires_at` | **CONSISTENT** |
| C2 lifetime | never reclaimed by `expires_at` or conversation archive/delete; only F7 (unmodeled) or **physical removal** (teardown) | §5.10.0.1 + §5.10.1 + §5.10.4 + §5.14.2 step 7 + §5.14.4 + §6 T-19/T-24 + §8.1 I12 + §9 7b + §11 + Q18 consistent | **CONSISTENT** |
| Teardown mechanism | verified = **container removal**; underlying workspace deletion **UNVERIFIED** for host-mounted layouts | §5.10.1 + §5.10.4 + §5.14.2 step 7 + §11(f) agree | **CONSISTENT** |
| Workspace-root provenance | tag→root **read** existing/shipped; **identity + write-authorization binding** is the new part; fail closed | §5.14.2 step 3 + §5.15.5 + §5.15.6 + U-12 + §6 T-25 + §8.1 I15 + §7.0/§7.1/§7.4 + §12 Q22 consistent | **CONSISTENT** |
| Live-spec identifier | `1.91.0`, 244 paths, sha256 `f0f4d4e9…` | §1 + §2.1 + §2.2 + §11 agree; historical `1.87.1` only as **reported, NOT INDEPENDENTLY VERIFIED** | **CONSISTENT** |
| Threat table | T-19 unchanged in substance; T-24 scoped (two-timer distinction); T-25 unchanged | §6 rows match §5.10/§5.15.6 | **CONSISTENT** |
| Crash windows (§8.3) / lifecycle races (§5.10.3) | unchanged in substance; no copy needed for reconciliation or active use is deleted | §5.10.3 cases 1–11 consistent with §5.10.1 | **CONSISTENT** |

---

## 5. What r10 does **not** claim

- It does **not** claim U-3 exists, nor that a trusted non-agent issuer exists.
- It does **not** claim the **Cloud/runtime-api** sandbox-lifecycle bound is known (delegated/external).
- It does **not** claim the modeled **managed-backend** lifecycle is an **F7 end-of-use** signal, nor
  that it proves any particular conversation reached a safe terminal state.
- It does **not** claim the application can **prevent** external infrastructure deletion.
- It does **not** claim `container.remove()` establishes **universal** physical deletion of the
  underlying workspace data.
- It does **not** claim the Cloud root read **authorizes** or **identity-binds** the write.
- It does **not** claim a **bounded** retention policy for C2 exists for the Cloud path (Q18 open).
- It does **not** claim the historical r8 digest `0086b0b0…` is verified.
- It does **not** claim P0 is complete; the capability still requires **upstream work + a maintainer
  decision**.

---

## 6. Regression check — prior findings remain closed

| Prior finding | Status at r10 | Evidence |
| --- | --- | --- |
| **R8-1** (physical-removal path is modeled) | **Still resolved** | §5.10.4 retains the modeled lifecycle; r10 only **qualifies** it (container vs workspace) — the correction stands |
| **R8-2** (Cloud root read exists/ships; U-12 re-scoped) | **Still resolved** | §5.15.6/U-12/T-25/I15/Q22 unchanged |
| **R8-3** (citation defects) | **Still resolved** | `bb9bbe23…` = enterprise `sandbox_router.py`; `workspace_archive.py`; §2.2 fixed |
| **R8-4** (live-spec refreshed) | **Still resolved** | `1.91.0`/244/`f0f4d4e9…` throughout; digest now also labelled unverified (R9-4) |
| **R7-1** (no conversation-scoped reclaim of C2) | **Preserved** | "today no conversation-scoped event reclaims C2" retained in §5.10.1/§5.10.4/§9 7b |
| **R7-2** (authoritative root + provenance/binding) | **Preserved** | §5.15.6/U-12/I15/T-25 intact |
| **R7-3** (authoritative vs replicated state) | **Preserved** | §5.15.4/U-10 intact |
| **R7-4** (L↔F cross-map) | **Preserved** | §5.10.0.1 intact |
| **R6-1** (`expires_at` never reclaims C2) | **Preserved (strengthened)** | Now scoped to the **operation** timer, with the separate infrastructure timer named |
| **R6-2** (U-3 trust boundary) | **Preserved** | §5.15.1–§5.15.3 intact |
| **R6-3** (quiesced source / U-10) | **Preserved** | §5.15.4 intact |
| **R6-4** (absolute agent path / U-11) | **Preserved** | §5.15.5 intact |
| **R6-5** (stale "seven facts" wording) | **Preserved** | eight-fact model unchanged |
| **N-1…N-5** (read-evidence + primitive corrections) | **Not reintroduced** | §5.14.0/§5.15 U-3, §5.5 state example, §5.9.1 `pending-messages`, §5.14.2 step 5 all unchanged in substance |

---

## 7. Corrections of record and honest limitations

1. **R9-1 scope correction.** The r9 text was **substantively correct**; r10 removes the **over-broad
   denial** it left behind. This is a **consistency** fix, not a change of the security posture.
2. **R9-3 is a factual qualification, not a policy change.** No C2 cleanup policy was altered; the
   teardown is now described as **container removal**, with physical workspace deletion **UNVERIFIED /
   SOURCE REQUIRED** for host-mounted layouts.
3. **R9-4 is a labelling fix.** The r8 digest `0086b0b0…ff77916` remains **unverified**; it is retained
   only for audit history and is not used as current route evidence.
4. **U-3 / U-10 / U-11 / U-12** remain **NEW upstream work** unless the implementation provides them.
5. **C2 retention (Q18)** remains an **open owner decision**; the **Cloud/runtime-api** teardown bound
   is **external/UNVERIFIED**.
6. **No test was executed** for the upstream capability (it does not exist); OpenHandBot attachment
   behavior is unchanged by this documentation-only task.
7. **Independence:** this is a **self-review**; an **independent adversarial review of r10 is still
   required** before r10 is treated as accepted.

---

## 8. Verdict of this self-review

**The four R9 findings (R9-1…R9-4) are addressed in the r10 text**, with the C2 timer claims scoped
consistently across the proposal, the `RESERVED_TAG_KEYS` citation corrected to line 86, the modeled
teardown qualified as **container removal** (physical workspace deletion **UNVERIFIED** for host-mounted
layouts), and the historical r8 spec digest labelled **NOT INDEPENDENTLY VERIFIED** — **without
weakening any security requirement, threat-model mitigation, or P0 invariant** (fail-closed rules
preserved; no cleanup primitive invented; prior findings R6-1…R6-5, N-1…N-5, R7-1…R7-4, R8-1…R8-4 remain
closed). Residual uncertainties remain disclosed: U-3 and its trusted issuer are **proposed/unverified**,
and the **Cloud/runtime-api** teardown bound is external/unverified, so the workspace-copy retention
bound remains an **open owner decision**. Because the R9 remediation was authored by the same agent that
produced r9, this document is **self-assessment only**; **an independent adversarial review of r10 is
required** before r10 is treated as accepted.
