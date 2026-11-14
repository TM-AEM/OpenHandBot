# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9 — HOSTILE SELF-REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-R8-INDEPENDENT-FINDINGS-REMEDIATION`

**Status of this document:** the **author's own hostile consistency review** of the r9 proposal
(`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`). It is **not** an independent
review: the R8 findings were remediated by the same agent that produced r8, so this is
**self-assessment**, not independent assurance. An **independent adversarial review of r9 is still
required** (proposal §9 criterion 10). Every claim that could not be verified is marked **UNVERIFIED**
or **UNKNOWN**; no test outcome or source semantic is fabricated.

- **Repo:** `TM-AEM/OpenHandBot` · **branch** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` ·
  **HEAD** `907b20de3fa6627795c14f29677e9f39c68e82f4` · **origin/main** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **r8 proposal SHA-256 (input):** `229b5ae18e0222454f10bef4b94562736b983f711c07a452a35b5226fb240645` (2770 lines).
- **r9 proposal SHA-256 (output):** `78507f5b0f21984a335294b746704e92d9e7de7f58eddfc833240c3a5f59faee` (2978 lines).
- **Driving review:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  (sha256 `843bb33e8b0011acdf6c2cc83a25587ab6fae0a84f788b949b707d44f94b2ed8`, 346 lines), verdict
  **`NEEDS_REVISION`**, findings **R8-1** (MEDIUM) + **R8-2** (MEDIUM) + **R8-3** (LOW) + **R8-4** (INFO).
- **Scope:** documentation only. **No code, test, schema, or runtime change. P0 is NOT implemented.**
- **Method:** read the R8 review findings R8-1…R8-4 and §7 "required changes" in full; re-verified each
  cited fact against the pinned public source (re-fetched and re-hashed this session); applied the r9
  corrections; then attempted to *break* r9 on the same axes (physical-removal modeling, root
  provenance, citation accuracy, spec freshness) and on cross-section consistency.

---

## 1. Evidence re-verification (this session, read-only)

All sources fetched from the **pinned revisions** already used at r2–r8
(`OpenHands/software-agent-sdk@9f7d5cb11b1256c1878f5584a657401feca9ad16`,
`OpenHands/sandbox-server@43e91604ccd0a9960c8d5c52faadd60b30f10e63`,
`OpenHands/enterprise@3fac53df8c2efcb67ff3537d1162e8c8a108f565`), plus the **live** Cloud V1 spec.
**No production call, no credential, no secret access.**

| # | Claim (finding) | Source (pinned, sha256 prefix) | Result |
| --- | --- | --- | --- |
| 1 | A wired sandbox-lifecycle deletes a sandbox **and its workspace** after an idle period (R8-1) | `enterprise` `…/sandbox/lifecycle/settings.py` `1cdd88d5…` (`delete_after_seconds` default 10 days); `rules.py` `0f0df7a9…` (`Action.DELETE`/`Reason.INACTIVE`); `tasks.py` `834e9452…` (`sandbox_service.delete_sandbox`); `sweep.py` `1d99bd1c…` (cron `* * * * *`); `worker/app.py` `a287ec5a…` (`add_tasks_from(..., namespace='sandbox_lifecycle')`) | **MATCH** |
| 2 | Scope = managed backends (Docker/E2B/k8s); Cloud/remote delegated to runtime-api (R8-1) | `enterprise` `…/sandbox/lifecycle/__init__.py` `446effa0…`: "covers every backend that subclasses `ManagedSandboxServiceInjector`: Docker, E2B and k8s agent-sandbox … runtime-api manages the remote backend's sandboxes itself" | **MATCH** |
| 3 | The Cloud-side per-conversation root **read exists** (R8-2) | `enterprise` `…/app_conversation/app_conversation_models.py` `7a4a54c0…` (`AppConversationInfo.repositories`, `@computed_field`, reads `tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)`); `…/app_conversation/additional_repositories.py` `a8d0bbe3…` (`conversation_repositories`, `path=f'{working_dir}/{folder}'`) | **MATCH** |
| 4 | The read is **live** in Cloud V1 (R8-2) | live `openapi.json` `1.91.0` sha256 `f0f4d4e9…`: `AppConversation.repositories` → `ConversationRepository.path` = "Absolute path of the folder in the sandbox" (`GET /api/v1/app-conversations`, `/search`) | **MATCH** |
| 5 | `bb9bbe23…` is **enterprise** `sandbox/sandbox_router.py`, not sandbox-server (R8-3a) | `enterprise` `…/sandbox/sandbox_router.py` `bb9bbe23…` ("delete_sandbox … never archives"); sandbox-server equivalent `07fef71e…` | **MATCH** |
| 6 | The archive module is `workspace_archive.py` (R8-3b) | `enterprise` `…/sandbox/workspace_archive.py` `202fc8e1…` (`archive_workspace`, line 334) | **MATCH** |
| 7 | The live spec is now `1.91.0` / 244 paths (R8-4) | live `openapi.json` sha256 `f0f4d4e9…`; `multipart` = 0, `binary` = 0, no `attach`/`upload` path | **MATCH** |
| 8 | Conversation delete **archives** and **preserves** the workspace; agent-server delete preserves it (context) | `enterprise` `…/app_conversation/app_conversation_router.py` `c43ed4f7…` (`_finalize_sandbox_delete`); `…/agent_server/conversation_service.py` `9e9b3e63…` (line 1911) | **MATCH** |

**Source-revision note:** the pinned SHAs are unchanged from r2–r8. The live Cloud V1 spec advanced
`1.87.1`/242 → `1.91.0`/244 (r9); the **"no Cloud upload"** conclusion is unaffected because it rests
on the **route evidence** (`multipart` = 0, `binary` = 0, no `attach`/`upload`), not the version string.

---

## 2. Remediation mapping — all four R8 findings

| # | R8 finding | r9 location(s) | r9 action | Self-assessment |
| --- | --- | --- | --- | --- |
| **R8-1** | MEDIUM: the C2 "physical-removal path" **is modeled** in the pinned source for managed backends; r8's "unmodeled / outside the pinned repos" premise is false | §5.10.1 (C2 row + cleanup-eligibility bullet + "Conversation ended/deleted"), §5.10.0.1 (L4), §5.10.4 (rewritten), §5.9 (`expired`), §5.14.2 step 7, §5.14.4, §6 T-19/T-24, §8.1 I12, §9 7b, §12 Q18, §11 (source entry + caveat f), §13 | **Corrected** the characterization: the pinned `enterprise` **sandbox lifecycle** (`delete_after_seconds`, wired in the worker; `Action.DELETE` → `delete_sandbox`) is a **modeled** mechanism for the **managed** backends (Docker/E2B/k8s); the **Cloud/remote** backend is **delegated to runtime-api** (`lifecycle/__init__.py`) — the *only* genuinely unmodeled part. Stated the **applicability limit** (managed-only; a *sandbox-scoped idle bound*, **not** an F7 signal; does not prove a conversation's terminal state). **Re-framed Q18** around the **Cloud/runtime-api bound** + grouping interaction. Cited the lifecycle files + hashes. **Preserved** the "no conversation-scoped event reclaims C2" invariant and the C2-not-deleted-while-in-use rule; **no cleanup primitive invented.** | **RESOLVED.** Residual: the **Cloud/runtime-api** bound is still external/UNVERIFIED |
| **R8-2** | MEDIUM: the Cloud-side per-conversation workspace-root **read exists and ships live**; U-12's "NEW + UNVERIFIED" classification is wrong | §5.15.6 (rewritten classification + "existing vs new" section), §5.15 **U-12** (re-scoped), §5.14.2 step 3, §5.15.5 (2 rows), §7.0 (Q3 + net-new), §7.1, §7.4, §6 T-25, §8.1 I15, §12 Q22, §11, §13 | **Re-classified**: the **tag→root resolution is EXISTING + VERIFIED (shipped)** — `AppConversationInfo.repositories` → `conversation_repositories`, exposed live as `AppConversation.repositories.path`. Scoped the **NEW (U-12)** part to the **identity/authorization binding** of the root to `(principal, conversation_id, operation_id)` + **write-authorization**. **Kept** the **fail-closed** rule and the caveat that a *read* of a path does **not** prove it is authorized/immutable/correctly-scoped/symlink-safe. | **RESOLVED (as a contract).** Residual: the binding remains a **proposed** capability (Q22) |
| **R8-3** | LOW: source-citation inaccuracies (wrong repo for `bb9bbe23…`; wrong filenames in the r8 self-review; a garbled §2.2 sentence) | §2.2 (sentence fixed), §11 (source entry corrected), §13 | **(a)** attributed `bb9bbe23…` to **enterprise** `sandbox/sandbox_router.py` and named the sandbox-server file `07fef71e…`; **(b)** acknowledged the r8 self-review filename errors (`ws_archive.py` → `workspace_archive.py`; `sbx_router.py` → `sandbox_router.py`) — see §6 below (record kept unaltered; corrections of record are in this r9 review); **(c)** rewrote the garbled §2.2 sentence. | **RESOLVED.** |
| **R8-4** | INFO: pinned live-spec version is stale | §1, §2.1 (source table), §2.2 (×2), §11, §13 | Refreshed the live Cloud V1 identifier to `info.version = 1.91.0`, **244** paths, sha256 `f0f4d4e9…` (r8 evidence `1.87.1`/242/`0086b0b0…`), **re-confirming** the "no Cloud upload" conclusion and stating it rests on **route evidence**, not the version string. | **RESOLVED.** |

**Preservation:** no security requirement, threat-model row, or P0 invariant was **weakened**. The
corrections are **accuracy/classification** fixes: r8 was **conservative** (it over-stated the exposure
and under-credited existing capability), so correcting it neither hides a control nor relaxes a rule.
The four-gap conclusion, the rejected approaches, the §6 threat table (T-19/T-24 refined; T-25
re-classified), and §8 invariants I1–I15 remain intact; **fail-closed** rules are preserved.

---

## 3. Attempts to break r9 (hostile checks)

| # | Attack | Result |
| --- | --- | --- |
| 3.1 | "r9 now claims the workspace is removed **by a conversation-scoped** event / that C2 is reclaimed by conversation delete." | **Blocked.** §5.10.1, §5.10.4, §9 7b all keep "today **no** conversation-scoped event reclaims C2"; only a **sandbox/pod teardown** removes it. |
| 3.2 | "r9 uses the modeled lifecycle to justify **deleting C2 while the agent may still need it** (i.e. weakens the F7 rule)." | **Blocked.** §5.10.4 states the sweeper is a **sandbox-scoped idle bound, not an F7 signal**, and **must not** be treated as evidence that agent access ended; C2 is still never timer-deleted and never deleted while active use is possible. |
| 3.3 | "r9 over-claims the Cloud root read as *authorized* / *safe to write*." | **No false claim.** §5.15.6, T-25, I15 all state the read returns a **path string** and does **not** establish authorization, immutability, correct scoping, or symlink/TOCTOU safety; the write still **fails closed**. |
| 3.4 | "r9 now presents U-12 as fully existing (drops the new work)." | **No.** U-12 is re-scoped, not deleted: the **identity/authorization binding** remains **NEW** and is recorded in §12 Q22. |
| 3.5 | "The stale `1.87.1` still appears as the *current* spec." | **Blocked.** Every current-spec reference is `1.91.0`; the old value appears only labelled "r8 evidence" / in the historical r8 revision row. |
| 3.6 | "A citation is still wrong (`ws_archive.py`, `sbx_router.py`, sandbox-server `bb9bbe23…`)." | **Blocked** in the **proposal**: the only occurrences of `ws_archive.py`/`sbx_router.py` are the explicit *correction notices* (§1, §11). The r8 self-review file is retained unaltered as a record (§6). |
| 3.7 | "A security requirement or invariant was dropped." | **No weakening.** All invariants I1–I15 present; T-19/T-24/T-25 present; §6 mitigations intact. |
| 3.8 | "r9 invents a C2 cleanup primitive or closes the retention bound by assertion." | **No.** §5.10.4/Q18 keep it an **open owner decision**; no primitive is invented. |

---

## 4. State-model, lifecycle, and crash-window re-check (independent)

| Item | r9 claim | Check | Verdict |
| --- | --- | --- | --- |
| Observable states | `stored \| delivered \| rejected \| failed \| expired`; `accepted` internal-only | §5.5/§5.9 agree | **CONSISTENT** |
| Workspace-copy lifetime | never timer-deleted; only F7 (unmodeled) or **physical removal** via sandbox/pod teardown (modeled for managed backends; delegated to runtime-api for the Cloud backend); **not** conversation archive/delete | §5.10.0.1 + §5.10.1 + §5.10.4 + §5.14.2 step 7 + §5.14.4 + §6 T-19/T-24 + §8.1 I12 + §9 7b + §11 + Q18 consistent | **CONSISTENT** |
| Workspace-root provenance | tag→root **read** existing/shipped; **identity + write-authorization binding** is the new part; fail closed | §5.14.2 step 3 + §5.15.5 + §5.15.6 + U-12 + §6 T-25 + §8.1 I15 + §7.0/§7.1/§7.4 + §12 Q22 consistent | **CONSISTENT** |
| Live-spec identifier | `1.91.0`, 244 paths, sha256 `f0f4d4e9…` | §1 + §2.1 + §2.2 + §11 agree; historical `1.87.1` only as "r8 evidence" | **CONSISTENT** |
| Lifecycle scope | managed backends modeled; Cloud/remote delegated to runtime-api | §5.10.4 + §11 + §13 agree; no section claims a conversation-scoped reclaim | **CONSISTENT** |
| Threat table | T-19/T-24 refined; T-25 re-classified | §6 rows match §5.10/§5.15.6 | **CONSISTENT** |
| Crash windows (§8.3) / lifecycle races (§5.10.3) | unchanged in substance; no copy needed for reconciliation or active use is deleted | §5.10.3 case 10 unchanged (still correct); each case consistent with §5.10.1 | **CONSISTENT** |

---

## 5. What r9 does **not** claim

- It does **not** claim U-3 exists, nor that a trusted non-agent issuer exists.
- It does **not** claim the **Cloud/runtime-api** sandbox-lifecycle bound is known (it is delegated and
  external).
- It does **not** claim the modeled **managed-backend** lifecycle is an **F7 end-of-use** signal, nor
  that it proves any particular conversation reached a safe terminal state.
- It does **not** claim the Cloud root read **authorizes** or **identity-binds** the write (only the
  read is existing; the binding is **NEW/U-12**).
- It does **not** claim a **bounded** retention policy for C2 exists for the Cloud path (Q18 open).
- It does **not** claim P0 is complete; the capability still requires **upstream work + a maintainer
  decision** (§5.15, §12).

---

## 6. Corrections of record (R8-3b) and honest limitations

1. **r8 self-review citations (R8-3b).** The r8 **self-review** file
   (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-SELF-REVIEW.md`, sha256 `d026330d…`) contains two
   filename errors: `…/sandbox/ws_archive.py` (actual `workspace_archive.py`) and enterprise
   `…/sandbox/sbx_router.py` (actual `sandbox_router.py`). This r9 review **records** the correction.
   The r8 self-review file itself is **left unaltered** as a historical record; rewriting a past
   review's text would misrepresent provenance. The **proposal** (the deliverable) uses the corrected
   names (§1, §11).
2. **U-3 is a proposal** and its issuer is **UNVERIFIED** to exist.
3. **U-10** (quiesced source), **U-11** (absolute-path producer/content identity), and **U-12** (the
   **identity/authorization binding** — narrower than at r8) are **NEW upstream work** unless the
   implementation provides them.
4. **C2 retention (Q18)** remains an **open owner decision**; for the **Cloud/runtime-api** backend the
   teardown bound is **external/UNVERIFIED**.
5. **Live Cloud V1** is `1.91.0` (244 paths) with **no** upload operation; the "no Cloud upload"
   conclusion is unchanged.
6. **No test was executed** for the upstream capability (it does not exist); existing OpenHandBot
   attachment-rejection tests are unchanged by this task.
7. **Independence:** this is a **self-review**; an independent adversarial review of r9 is still
   required (§9 criterion 10).

---

## 7. Verdict of this self-review

**The four R8 findings (R8-1…R8-4) are addressed in the r9 text**, with the physical-removal
characterization and the root-provenance classification corrected to match the pinned source, the
citations fixed, and the live-spec identifier refreshed — **without weakening any security requirement,
threat-model mitigation, or P0 invariant** (fail-closed rules preserved; no cleanup primitive
invented). Two residual uncertainties are inherent and disclosed: (a) U-3 and its trusted issuer are
**proposed/unverified**, and (b) the **Cloud/runtime-api** teardown bound is external/unverified, so
the workspace-copy retention bound remains an **open owner decision**. Because the R8 remediation was
authored by the same agent that produced r8, this document is **self-assessment only**; **an
independent adversarial review of r9 is required** before r9 is treated as accepted.
