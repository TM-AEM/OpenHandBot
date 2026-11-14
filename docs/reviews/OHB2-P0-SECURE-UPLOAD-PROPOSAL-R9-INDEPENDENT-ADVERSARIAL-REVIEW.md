# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9 — INDEPENDENT ADVERSARIAL REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-INDEPENDENT-ADVERSARIAL-REVIEW`

Reviewer: fresh-context independent adversarial reviewer; **not** the author of the proposal, **not**
the author of the r9 self-review, and **not** the author of any earlier (r2–r8) review or self-review.
All actions were **read-only**: upstream public source and specs were re-fetched independently this
session and re-hashed; **no production call, no credential, no secret access, no modification** of the
proposal, the self-review, `PROGRESS.md`, memory, source code, tests, or any previous review. This
review file is the **only** artifact created. No commit/push/PR/merge/deploy, no branch change, no
upstream issue/PR/maintainer contact. **P0 remains unimplemented.**

## Verdict: **NEEDS_REVISION**

r9 is a **genuine, well-executed correction of r8**. All four R8 findings are **substantively
addressed in the r9 text**, and **every source claim I re-checked independently matches the pinned
source** (§3). The proposal hash matches the value the author reported (`78507f5b…`, 2978 lines), the
r9 self-review hash matches (`fd4640cd…`, 147 lines), and the driving R8 review hash matches
(`843bb33e…`, 346 lines). I found **no** weakening of any threat-model row, P0 invariant, or
acceptance criterion: fail-closed rules are intact, no cleanup primitive was invented, and the four
residual uncertainties (U-3/issuer, U-10, U-11, U-12-binding, C2 retention) remain honestly open.

**But r9 is not yet ready for owner approval**, because the R8-1 remediation — which *added* the
statement that a sandbox-lifecycle timer deletes a sandbox **and its workspace** — was **not** fully
propagated to the sections that still assert, in absolute terms, that **no timer deletes the
workspace-materialized copy (C2)**. That is a **new internal contradiction introduced by r9 itself**,
in the P0 premature-deletion area:

- **R9-1 (MEDIUM, new, source-backed) — r9 now contradicts its own "no timer deletes C2" invariant.**
  r9's new §5.10.1/§5.10.4 text states that the managed-backend **sandbox lifecycle** deletes a
  sandbox **and its workspace** on an idle bound (`delete_after_seconds`), i.e. a **server-side timer
  whose firing removes the directory that holds C2**. Yet §5.10.2, §5.9, §5.10.3 and §8.4 still assert
  without qualification that there is **"no 'auto-expire timer' whose firing deletes C2"**, that
  **"C2 is never timer-deleted"**, and that **"the only clock that exists server-side is the
  operation's `expires_at`"**. Both statements cannot be true for the managed backends. The intent is
  clearly "no *operation-scoped* timer deletes C2", but the wording is an absolute claim the r9 text
  itself refutes.

Two LOW/INFO items accompany it (§5): a same-source line-number inconsistency (line 86 vs line 96 for
`RESERVED_TAG_KEYS`) and a source nuance about whether the modeled teardown actually removes the
workspace directory. These do not change the security conclusion but should be fixed in the same pass.

This is a **consistency/precision** defect in an otherwise-correct remediation, so the verdict is
`NEEDS_REVISION`, **not** `BLOCKED`. If R9-1 (and, ideally, R9-2/R9-3) are fixed, a subsequent review
should be able to move to `PASS_WITH_NOTES`.

---

## 1. Baseline and file hashes

Repo `TM-AEM/OpenHandBot`; branch `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`; `HEAD`
`907b20de3fa6627795c14f29677e9f39c68e82f4`; `origin/main` `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`
(unchanged; no commit, no push). Working tree: pre-existing modifications
(`.agent/PROGRESS.md`, `bot/handlers.py`, two other `docs/proposals/*.md`) and the untracked r-series
proposal/review files — **all left exactly as found**; this review added exactly one file.

| Artifact | Lines | sha256 (independently recomputed this session) |
| --- | --- | --- |
| `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` (r9) | 2978 | `78507f5b0f21984a335294b746704e92d9e7de7f58eddfc833240c3a5f59faee` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-SELF-REVIEW.md` | 147 | `fd4640cdf66683768fe7ebc24800768bbeb23b4a37feb5ee03296aa1f354a326` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-INDEPENDENT-ADVERSARIAL-REVIEW.md` (driving review) | 346 | `843bb33e8b0011acdf6c2cc83a25587ab6fae0a84f788b949b707d44f94b2ed8` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-SELF-REVIEW.md` | 146 | `d026330d3a91bbfd52aef738d391fc317721ffdd138027bd2ff86f73bd275172` |

All four match the values the r9 self-review reports. **LIMITATION:** the **r8 proposal** is **not on
disk** (the r9 edit replaced it), so the r8 hash `229b5ae1…`/2770 lines is taken from the r8 review and
**could not be re-verified**; the r8→r9 comparison therefore relies on the r8 review's verbatim quotes
and the r9 text itself.

## 2. Method

Independent re-verification against the **pinned public revisions already used at r2–r8** — no
production call:

- `OpenHands/enterprise@3fac53df8c2efcb67ff3537d1162e8c8a108f565` (re-fetched; **equals** the live
  Cloud V1 serving repo),
- `OpenHands/software-agent-sdk@9f7d5cb11b1256c1878f5584a657401feca9ad16`,
- `OpenHands/sandbox-server@43e91604ccd0a9960c8d5c52faadd60b30f10e63`,
- the **live** Cloud V1 spec `https://app.all-hands.dev/openapi.json` (re-fetched, re-hashed).

Each file was re-fetched and re-hashed **in this session**; the live spec was re-parsed with a JSON
tool (token counts, path count, request-body content types, route inventory). I then read the r9
remediation sections (§2.1/§2.2, §5.9, §5.10.0–§5.10.4, §5.14.2, §5.14.4, §5.15/§5.15.4/§5.15.5/§5.15.6,
§6, §7.0/§7.1, §8.1/§8.3/§8.4, §9, §11, §12, §13) against the R8 findings and tried to break r9 on
the same axes plus internal consistency.

## 3. Independent verification of the r9 central claims (the strongest part of r9)

Every file hash r9 cites for its sources matches the file at the pinned SHA. Independently recomputed
`sha256` prefixes (all **MATCH** r9):

| r9 claim (finding) | Independent result |
| --- | --- |
| Sandbox-lifecycle subsystem exists and is wired (R8-1) | `sandbox/lifecycle/{__init__,settings,sweep,rules,tasks}.py` = `446effa0`/`1cdd88d5`/`1d99bd1c`/`0f0df7a9`/`834e9452`; `worker/app.py` = `a287ec5a`, line 33 `app.add_tasks_from(lifecycle, namespace='sandbox_lifecycle')`. **MATCH** |
| `delete_after_seconds` default 10 days, "Delete a sandbox, **and its workspace**, once it has not run for this long" | `lifecycle/settings.py` line 25 `default=10*24*60*60`, description verbatim. **MATCH** |
| Periodic sweep (cron `* * * * *`); `decide()` → `Action.DELETE`/`Reason.INACTIVE`; `delete_sandbox` | `lifecycle/tasks.py` line 78 `@lifecycle.periodic(cron='* * * * *')`, line 182 `sandbox_service.delete_sandbox(sandbox_id)`; `lifecycle/rules.py` line 106 `last_ran_at = max(state_changed_at, last_active_at)`, line 108 `Decision(Action.DELETE, Reason.INACTIVE)`; `lifecycle/__init__.py` line 9 "runs every minute". **MATCH** |
| Scope = managed backends (Docker/E2B/k8s); Cloud/remote delegated to runtime-api | `lifecycle/__init__.py` lines 3-4: "covers every backend that subclasses `ManagedSandboxServiceInjector`: Docker, E2B and k8s agent-sandbox. runtime-api manages the remote backend's sandboxes itself." **MATCH** |
| `_delete_at_provider` removes the container/pod | `managed_sandbox_service.py` (`c1286e09`) line 156 `delete_sandbox` → line 183 `_delete_at_provider`; `docker_sandbox_service.py` line 686 `_delete_at_provider` → `container.stop(...)` / `container.remove()`. **MATCH** |
| Cloud-side per-conversation root **read exists/ships** (R8-2) | `app_conversation_models.py` (`7a4a54c0`) line 252 `def repositories(...)` `@computed_field` reading `self.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)` (line 263) → `conversation_repositories(...)` (`additional_repositories.py`, `a8d0bbe3`, line 89) which builds `path = f'{working_dir}/{folder}'` (line 106). **MATCH** |
| The read is **live** in Cloud V1 | live `openapi.json` sha256 `f0f4d4e9…`, `info.version = 1.91.0`, **244** paths; `AppConversation.repositories` → `ConversationRepository.path` = "Absolute path of the folder in the sandbox", on `GET /api/v1/app-conversations` and `/search`. **MATCH** |
| Tag is server-written; reserved key | `live_status_app_conversation_service.py` (`9f4f1596`) line 1124 `tags[ARCHIVE_WORKSPACE_PATH_TAG_KEY] = working_dir`; `RESERVED_TAG_KEYS` present in `app_conversation_models.py`. **MATCH** |
| Grouped root `{base}/{conversation_id.hex}` for non-`NO_GROUPING` | `settings_models.py` (`27bae62a`) `SandboxGroupingStrategy` (739-750), `grouped_workspace_dir` (753-767) returns `f'{base}/{conversation_id_hex}'`. **MATCH** |
| `_get_agent_server_context`/`AgentServerContext` carry **no** workspace-path field | `app_conversation_router.py` (`c43ed4f7`) `AgentServerContext` dataclass fields = conversation/sandbox/sandbox_spec/agent_server_url/session_api_key; context built with `sandbox_spec` only. **MATCH** |
| Conversation delete **archives + preserves**; agent-server delete preserves | `_finalize_sandbox_delete` → `archive_conversation_workspace`; `count_conversations_by_sandbox_id(...) == 0` before `delete_sandbox`; `conversation_service.py` (`9e9b3e63`) line 1911 "workspace is preserved". **MATCH** |
| `bb9bbe23…` is **enterprise** `sandbox/sandbox_router.py`; sandbox-server is `07fef71e…` (R8-3) | enterprise `sandbox/sandbox_router.py` = `bb9bbe23` ("delete_sandbox … never archives", line 302); sandbox-server `sandbox/sandbox_router.py` = `07fef71e`. **MATCH** |
| Archive module is `workspace_archive.py` (R8-3) | `sandbox/workspace_archive.py` = `202fc8e1` (`archive_workspace`). **MATCH** |
| Live spec "no upload" (R8-4) | live spec: `multipart` = 0, `"binary"` = 0, no `upload` path, `attach` only in unrelated descriptions; request-body content types = `application/json` + `application/x-www-form-urlencoded` (the latter **only** on `/oauth/*`); `send-message` body = `anyOf[TextContent, ImageContent]`; `/file`,`/files`,`/download`,`git/changes`,`git/diff` all present and **read-only**. **MATCH** |

**Conclusion of §3:** r9's factual corrections are accurate and source-grounded. The R8-1 and R8-2
"premise" corrections are **correct** — the pinned source *does* model the managed-backend teardown,
and the Cloud-side root read *does* ship.

## 4. Remediation mapping — all four R8 findings independently re-verified

| # | R8 finding | r9 action (verified in text) | Independent verdict |
| --- | --- | --- | --- |
| **R8-1** | MEDIUM: the C2 "physical-removal path" **is modeled**; r8's "unmodeled" premise false | §5.10.1 (C2 row + cleanup bullet + "Conversation ended/deleted"), §5.10.0.1 (L4), §5.10.4 (rewritten), §5.9 (`expired`), §5.14.2 step 7, §5.14.4, §6 T-19/T-24, §8.1 I12, §9 7b, §12 Q18, §11, §13. Names the lifecycle files/hashes; states the **applicability limit** (managed-only; sandbox-scoped idle bound, **not** an F7 signal; does not prove a terminal state); keeps "no conversation-scoped event reclaims C2". | **ADDRESSED, but see R9-1** — the correction is accurate, yet the *absolute* "no timer deletes C2" wording elsewhere was not reconciled with it. |
| **R8-2** | MEDIUM: the Cloud-side root **read exists and ships**; U-12's "NEW + UNVERIFIED" classification wrong | §5.15.6 (rewritten: "existing vs new"), U-12 re-scoped to the **identity/authorization binding**, §5.14.2 step 3, §5.15.5 (2 rows), §7.0 (Q3 + net-new), §7.1, §7.4, §6 T-25, §8.1 I15, §12 Q22, §11, §13. Keeps fail-closed and the "a read ≠ authorized/immutable/safe" caveat. | **PASS.** Classification corrected; the binding remains NEW (Q22); no capability over-claimed. |
| **R8-3** | LOW: citation defects (`bb9bbe23…` repo; `ws_archive.py`/`sbx_router.py`; garbled §2.2) | §2.2 sentence fixed; §11 attributes `bb9bbe23…` to enterprise `sandbox/sandbox_router.py` and names sandbox-server `07fef71e…`; §13 records the corrections; the r8 self-review is retained unaltered as a record. | **PASS** (with a residual same-source line-number slip → R9-2). |
| **R8-4** | INFO: pinned live-spec version stale | §1/§2.1/§2.2/§11/§13 refreshed to `1.91.0`, 244 paths, sha256 `f0f4d4e9…`; historical `1.87.1`/242 retained only as labelled "r8 evidence"; states the conclusion rests on **route evidence**, not the version string. | **PASS** (with an unverifiable r8-hash lineage → R9-4). |

**Preservation check (independent):** §6 rows T-19/T-24/T-25 present and consistent with §5.10/§5.15.6;
§8.1 invariants I1–I15 all present; §9 acceptance criteria intact; fail-closed rules preserved; **no**
cleanup primitive invented; the four residual uncertainties remain open. **No security requirement or
P0 invariant was weakened by r9.**

## 5. Adversarial findings (new)

### R9-1 (MEDIUM, new, source-backed) — r9 contradicts its own "no timer deletes C2" invariant

**What r9 newly asserts (the R8-1 fix):** the pinned Enterprise **sandbox lifecycle** deletes a sandbox
**and its workspace** on an idle bound, and this **is** a modeled mechanism for the managed backends:

- §5.10.1 C2 row (line 1187): "*the **workspace directory is physically removed** on **sandbox/pod
  teardown**. Teardown **is modeled for the *managed* backends** (Docker/E2B/k8s) by the Enterprise
  **sandbox lifecycle** (`delete_after_seconds`, a *configurable* idle bound …)*".
- §5.10.4 (lines 1313-1320): "*`delete_after_seconds` (default 10 days) with the description "Delete a
  sandbox, **and its workspace**, once it has not run for this long"; a periodic `sweep` (cron
  `* * * * *`) … `rules.decide()` returns `Action.DELETE` … and the `check` job calls
  `sandbox_service.delete_sandbox(sandbox_id)`*".
- §11 (lines 2736-2740) and §6 T-24 repeat it.

**What r9 still asserts elsewhere, in absolute terms (unchanged r6/r7 text):**

- §5.10.2 (lines 1266-1268): "*A successful `stored` transition MUST NOT arm any timer that deletes the
  workspace copy. There is **no** "auto-expire timer" whose firing deletes **C2**. The only clock that
  exists server-side is the operation's `expires_at`, and it reclaims **C1/C3 only**.*"
- §5.10.3 (line 1301): "*`expires_at` is a **staging-only** bound; **C2 is never timer-deleted**.*"
- §5.10.3 case 4 (line 1290): "*an in-progress read cannot be invalidated by the timer*".
- §5.9 (line 1038): "*the **workspace-materialized copy is never timer-reclaimed***".
- §8.4 (line 2382): "*the **workspace-materialized copy (C2) is never timer-reclaimed***".
- §12 Q18 (lines 2919-2920): "*the workspace copy … is **not** timer-deleted (§5.10.1)*".

**The contradiction.** For the **managed** backends the r9 text now names, there **is** a server-side
timer whose firing removes the directory that holds C2 — the lifecycle sweep that runs
`delete_sandbox` after `delete_after_seconds` of inactivity (`lifecycle/tasks.py` line 78 cron, line 182
`delete_sandbox`; `lifecycle/rules.py` line 108 `Action.DELETE`). So the absolute statements "no timer
whose firing deletes C2", "C2 is never timer-deleted", and "the only clock that exists server-side is
`expires_at`" are **false as written** for exactly the backends r9 just added. The *intended* claim is
narrower and correct — "no **operation-scoped** timer deletes C2; `expires_at` is staging-only" — but
the text does not say that, and a reader/implementer could conclude that **no** timer can ever remove
C2, which r9's own §5.10.1/§5.10.4 refute.

**Why this matters (severity).** This is the P0 premature-deletion area (T-24/I12): the whole point of
the r6→r7→r8 chain was to be precise about *which* mechanisms can reclaim C2. r9 fixed the *mechanism*
description in one place and left an absolute *denial* of it in four others — an internal inconsistency
in a security invariant. It does **not** create an exploitable path (the design still never deletes C2
on `expires_at`; the lifecycle deletion is a deployment mechanism r9 now acknowledges), which is why
this is MEDIUM and not HIGH/BLOCKING.

**Required change (minimal, documentation-only).** Qualify the absolute wording to "no **operation-scoped
/ `expires_at`** timer deletes C2" (or "C2 is never deleted by the **operation's** timer") in §5.9,
§5.10.2, §5.10.3 (invariant + case 4), §8.4, and §12 Q18, so they agree with §5.10.1/§5.10.4/§6 T-24.
The invariant itself ("the system never deletes a copy needed for reconciliation or active use") is
unchanged; only the over-broad "no timer" phrasing must be narrowed. **No new primitive, no policy
change.**

### R9-2 (LOW, new) — same source cited at two different line numbers (`RESERVED_TAG_KEYS`)

r9 cites the **same** symbol, in the **same** file, at **two different lines**:

- §5.15.6 (line 1944): "*`RESERVED_TAG_KEYS`, `app_conversation_models.py` **line 86***".
- §11 (line 2717): "*`RESERVED_TAG_KEYS` **line 96***".

Ground truth (independently fetched, `app_conversation_models.py` `7a4a54c0`): `RESERVED_TAG_KEYS =
frozenset(...)` is at **line 86**; **line 96** is `def _validate_caller_tags(...)`. The r8 *review*
correctly recorded `RESERVED_TAG_KEYS (86)`; the r8 *self-review* recorded "(line 96)" — and r9's §11
appears to have carried forward the **self-review's** wrong value while §5.15.6 used the **review's**
right value. Cosmetic, but it is the same class of citation defect R8-3 was raised for; fix §11 to
line 86.

### R9-3 (LOW, new, source-backed) — the modeled teardown removes the **container**; its effect on the workspace directory depends on mounts

r9's R8-1 fix rests on the phrase "Delete a sandbox, **and its workspace**". The *description* says so,
and the *intent* is clear; but the **mechanism** I could verify is `container.remove()`
(`docker_sandbox_service.py` line 698). Whether that removes the **workspace directory** depends on
where the workspace lives: the pinned Docker spec sets `working_dir='/workspace/project'` and the
conversations path to `/workspace/conversations` **inside** the container (`docker_sandbox_spec_service.py`
lines 92-98), while the mount layout is **deployment-configurable** (`DockerSandboxServiceInjector.mounts:
list[VolumeMount] = Field(default_factory=list)`, i.e. **empty by default**). If an operator bind-mounts
the workspace to the host, `container.remove()` would **not** delete C2. So "teardown removes C2" is
**not universally established** by the pinned source; it holds for the container-local layout and is
**unverified** for a host-mounted layout. This does **not** negate R8-1 (the removal path **is**
modeled, contra r8) — it only means the r9 wording "*sandbox-and-workspace teardown is a modeled
mechanism*" should carry the same kind of applicability caveat r9 already gives for the Cloud backend.
Suggested one-line hedge in §5.10.4: "for the container-local layout; a host-mounted workspace is
governed by the mount policy." (Optional; the item is informational.)

### R9-4 (INFO, new) — the r8-spec hash lineage cannot be independently confirmed

r9 states the r8 evidence as "`1.87.1`, 242 paths, sha256 `0086b0b0…ff77916`" (§2.1, §2.2 ×2, §11).
The **r8 proposal is not on disk**, and the pinned **r8 review** records only "`1.87.1` / 242 paths"
(lines 91, 263) — **not** the hash `0086b0b0…ff77916`; the r7 review (line 378) says it "relied on the
proposal's `1.87.1`" without re-fetching. So this specific hash is **asserted, not independently
verifiable** from the available artifacts. It is harmless to the conclusion (which rests on the
**re-verified** current spec `f0f4d4e9…` and the route evidence), but r9 should either mark it
"as reported in the r8 proposal (not independently re-checkable)" or drop the exact hash.

## 6. State-model, lifecycle, and crash-window re-check (independent)

| Item | r9 claim | Independent check | Verdict |
| --- | --- | --- | --- |
| Observable states | `stored \| delivered \| rejected \| failed \| expired`; `accepted` internal-only | §5.5 and §5.9 agree; no example returns `accepted`/`uploading` | **CONSISTENT** |
| `expires_at` semantics | staging-only bound; never extends; derives `expired` | §5.9 prose matches; `delivered` gated on U-3 | **CONSISTENT** |
| C2 lifetime | never reclaimed by **`expires_at`** or conversation archive/delete; only F7 (unmodeled) or physical teardown | §5.10.1/§5.10.4/§6 T-24 agree **with each other**, but conflict with the absolute "no timer" wording in §5.9/§5.10.2/§5.10.3/§8.4/§12 | **INCONSISTENT → R9-1** |
| Root provenance | tag→root read **existing**; identity/authorization binding **NEW**; fail closed | §5.14.2 step 3 + §5.15.5 + §5.15.6 + U-12 + T-25 + I15 + Q22 agree | **CONSISTENT** |
| Live-spec identifier | `1.91.0`, 244, `f0f4d4e9…` | §1/§2.1/§2.2/§11 agree; re-verified live this session | **CONSISTENT** |
| Crash windows (§8.3) / races (§5.10.3) | no copy needed for reconciliation or active use is deleted | cases 1-11 internally consistent; case 10 updated for R8-1 | **CONSISTENT** |

## 7. What r9 does **not** claim (fairness note)

- It does **not** claim U-3 or a trusted issuer exists.
- It does **not** claim the **Cloud/runtime-api** lifecycle bound is known (delegated/external).
- It does **not** claim the modeled managed-backend lifecycle is an **F7** signal or proves a
  conversation's terminal state.
- It does **not** claim the Cloud root read **authorizes**/identity-binds the write (only the read is
  existing; the binding is NEW/U-12).
- It does **not** claim a bounded C2 retention policy exists (Q18 open) and invents **no** cleanup
  primitive.
- It does **not** claim P0 is complete.

This candour is why the verdict is `NEEDS_REVISION` and **not** `BLOCKED`.

## 8. Unverified / limitations of this review (honest list)

1. The **r8 proposal** is not on disk; the r8→r9 diff was assessed from the r8 review's verbatim
   quotes and the r9 text, not from both files side by side.
2. The **r8-spec hash** `0086b0b0…ff77916` could not be independently confirmed (→ R9-4).
3. I did **not** run any code or test (P0 is a proposal; no capability exists). No claim here rests on
   an executed test.
4. Whether the modeled teardown removes the **workspace directory** (vs only the container) is
   **unverified** for host-mounted layouts (→ R9-3).
5. I did not contact any maintainer and made no production call.
6. This review covers r9 only; it does not re-adjudicate the closed r6/r7 findings except where r9
   touches them.

## 9. Verdict and required changes

**Verdict: `NEEDS_REVISION`.**

Required (documentation-only, no security/policy change):

1. **R9-1 (MEDIUM, blocking):** narrow the absolute "no timer deletes C2 / C2 is never timer-deleted /
   the only server-side clock is `expires_at`" wording in §5.9, §5.10.2, §5.10.3 (invariant + case 4),
   §8.4, and §12 Q18 to **"no operation-scoped (`expires_at`) timer"**, so it agrees with the r9
   §5.10.1/§5.10.4/§6 T-24 statement that the managed-backend lifecycle teardown removes the workspace.
   Keep the invariant and the fail-closed rules unchanged.
2. **R9-2 (LOW):** fix the `RESERVED_TAG_KEYS` line number in §11 (line 86, not 96).
3. **R9-3 (LOW, optional):** add the container-local/mount caveat to §5.10.4's teardown sentence.
4. **R9-4 (INFO, optional):** mark or drop the unverifiable r8-spec hash in §2.1/§2.2/§11.

If items 1-2 are fixed (3-4 recommended), the two MEDIUM R8 findings are **resolved** and the r9
remediation is otherwise **source-accurate and faithful**; a subsequent independent review should be
able to move to `PASS_WITH_NOTES`.

---

**Independence statement.** This review was authored by a fresh-context reviewer that is not the author
of the proposal, the r9 self-review, or any earlier review/self-review in this series. All artifacts
were read-only; the only file created is this one. No secrets, credentials, or production calls were
used.
