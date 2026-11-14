# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8 — INDEPENDENT ADVERSARIAL REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-INDEPENDENT-ADVERSARIAL-REVIEW`

Reviewer: fresh-context independent adversarial reviewer; **not** the author of the proposal, **not**
the author of the r8 self-review, and **not** the author of any earlier (r2–r7) review or self-review.
All actions were **read-only**: upstream public source and specs were re-fetched independently this
session and re-hashed; **no production call, no credential, no secret access, no modification** of the
proposal, the self-review, `PROGRESS.md`, memory, source code, tests, or any previous review. This
review file is the **only** artifact created. No commit/push/PR/merge/deploy, no branch change, no
upstream issue/PR/maintainer contact. **P0 remains unimplemented.**

## Verdict: **NEEDS_REVISION**

r8 is a **genuine, well-executed correction of r7**. Its four remediations (R7-1…R7-4) are
**substantively present in the r8 text** and **three of the four rest on facts I independently
re-verified against the pinned source** (§3). The proposal hash matches the value the author reported
(`229b5ae1…`, 2770 lines), the r8 self-review hash matches (`d026330d…`, 146 lines), and the driving
R7 review hash matches (`1b276ac6…`, 423 lines). Every file hash r8 cites for its sources matches the
file at the pinned SHA (§1). I found **no** weakening of any threat-model row, P0 invariant, or
acceptance criterion.

**But r8 is not yet ready for owner approval**, because its two MEDIUM remediations each rest on a
**source-grounding claim that the pinned source contradicts or over-generalizes**, and one of them
mis-classifies **shipped, live** capability as **new**:

- **R8-1 (MEDIUM, new, source-backed) — the C2 "physical-removal path" is modeled *in the pinned
  source*, not "unmodeled / outside the pinned repos".** r8 makes the "runtime-api idle reap" the sole
  physical-removal path for the workspace-materialized copy (C2) and asserts it is **"not modeled by
  any primitive in the pinned source"** and **"outside the pinned repos"** (§5.10.1 C2 row; §5.10.4;
  §5.10.3 case 10; §6 T-24; §11; §12 Q18). The pinned `OpenHands/enterprise@3fac53df…` contains a
  **complete, wired sandbox lifecycle** — `openhands/app_server/sandbox/lifecycle/{__init__,settings,sweep,rules,tasks}.py`
  — whose `delete_after_seconds` (default 10 days) is documented **"Delete a sandbox, and its
  workspace, once it has not run for this long"** and whose DELETE action calls
  `sandbox_service.delete_sandbox(...)`. So the retention mechanism **is** a primitive in the pinned
  source (for every managed backend), and the "unbounded with no modeled mechanism" framing is
  inaccurate. (For the Cloud's remote/runtime-api backend the reaper is indeed external — r8's
  statement is true *only* for that one path, not universally.)
- **R8-2 (MEDIUM, new, source-backed) — the Cloud-side per-conversation workspace-root read
  *exists and ships live*; classifying it as "NEW + UNVERIFIED" (U-12) is wrong.** r8's U-12 / §5.15.6
  state that "**no** single Cloud-side read of the per-conversation root" is established and classify
  the whole root-provenance read as **NEW upstream capability (U-12), UNVERIFIED**. The pinned
  `AppConversationInfo.repositories` (`app_conversation_models.py:250-265`) is a computed property
  that reads the pinned, server-managed `archiveworkspacepath` tag via `conversation_repositories(...)`
  and builds `path = {working_dir}/{folder}` — a Cloud-side resolution of the per-conversation root —
  and it is exposed in the **live** Cloud V1 API (live OpenAPI `1.91.0`: `AppConversation.repositories`
  → `ConversationRepository.path` = *"Absolute path of the folder in the sandbox"*, returned by
  `GET /api/v1/app-conversations` and `/search`). Only the **identity binding** of that root to
  `(principal, conversation_id, operation_id)` is genuinely new.

**All required fixes are documentation/contract-level.** No new upstream *machinery* beyond what r8
already lists is required; no security control needs to be weakened. The corrections are to *state the
source accurately*: name the modeled lifecycle (and its applicability), and re-classify the shipped
root read.

---

## 1. Baseline and file hashes

- **Repo:** `TM-AEM/OpenHandBot` · **branch** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` ·
  **HEAD** `907b20de3fa6627795c14f29677e9f39c68e82f4` · **origin/main** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **Under review:** `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` —
  sha256 `229b5ae18e0222454f10bef4b94562736b983f711c07a452a35b5226fb240645`, **2770 lines**. **MATCHES**
  the value reported in the task and in the r8 self-review.
- **r8 self-review:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-SELF-REVIEW.md` — sha256
  `d026330d3a91bbfd52aef738d391fc317721ffdd138027bd2ff86f73bd275172`, 146 lines. **MATCHES.**
- **Driving review:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  — sha256 `1b276ac684ee9ce3f1a72b460cff2fe667ea33ea5ff2662bc7c0e6b5ae5bd2ed`, 423 lines. **MATCHES.**
- **Working tree:** pre-existing modified files (`.agent/PROGRESS.md`, `bot/handlers.py`, two
  proposals) and many untracked review files were **left untouched**. This review file is the only
  artifact added.

**Source revisions (re-fetched and re-hashed this session, read-only).** The pinned SHAs are unchanged
from r2–r7; I confirmed each is still fetchable and re-hashed every file r8 cites:

| Repo | Pinned commit |
| --- | --- |
| `OpenHands/software-agent-sdk` | `9f7d5cb11b1256c1878f5584a657401feca9ad16` |
| `OpenHands/sandbox-server` | `43e91604ccd0a9960c8d5c52faadd60b30f10e63` |
| `OpenHands/enterprise` | `3fac53df8c2efcb67ff3537d1162e8c8a108f565` |

**Enterprise files (sha256 prefix) — all MATCH r8's citations:** `app_conversation/app_conversation_router.py`
`c43ed4f7`; `app_conversation/app_conversation_models.py` `7a4a54c0`; `app_conversation/live_status_app_conversation_service.py`
`9f4f1596`; `sandbox/remote_sandbox_service.py` `d239ec43`; `sandbox/workspace_archive.py` `202fc8e1`;
`settings/settings_models.py` `27bae62a`; `app_conversation/additional_repositories.py` `a8d0bbe3`.
**SDK files — all MATCH:** `agent_server/runtime_router.py` `5bea70f0`; `agent_server/file_router.py`
`13f0cae7`; `agent_server/conversation_service.py` `9e9b3e63`; `agent_server/models.py` `57b3680c`;
`openhands-tools/…/file_editor/editor.py` `a1d735d4`.

**Live Cloud V1 spec (re-fetched this session):** `https://app.all-hands.dev/openapi.json` —
`info.version = **1.91.0**`, **244** paths, sha256 `f0f4d4e9…`. (r8 pins `1.87.1`, 242 paths; see §5
R8-4.) `multipart` = 0, `format: binary` = 0, no `attach`/`upload` path ⇒ **the "no Cloud upload"
conclusion still holds.**

**New evidence files re-fetched this session (enterprise @ `3fac53df…`), not cited by r8:**

| File | sha256 prefix | What it establishes |
| --- | --- | --- |
| `sandbox/lifecycle/__init__.py` | `446effa0` | lifecycle worker; managed backends = Docker/E2B/k8s; runtime-api manages the remote backend itself |
| `sandbox/lifecycle/settings.py` | `1cdd88d5` | `idle_seconds` / `max_session_seconds` / **`delete_after_seconds`** ("Delete a sandbox, **and its workspace**") |
| `sandbox/lifecycle/sweep.py` | `1d99bd1c` | periodic sweep finds due sandboxes from the sandbox table alone |
| `sandbox/lifecycle/rules.py` | `0f0df7a9` | `decide()` → `Action.DELETE` on `delete_after_seconds` |
| `sandbox/lifecycle/tasks.py` | `834e9452` | DELETE → `await sandbox_service.delete_sandbox(sandbox_id)` |
| `sandbox/managed_sandbox_service.py` | `c1286e09` | `delete_sandbox` → `_delete_at_provider` (removes the container/pod) |
| `sandbox/docker_sandbox_service.py` | `00953ee1` | `class DockerSandboxService(ManagedSandboxService)` |
| `worker/app.py` | `a287ec5a` | `app.add_tasks_from(lifecycle, namespace='sandbox_lifecycle')` |
| `sandbox/sandbox_router.py` | `bb9bbe23` | the "never archives" comment r8 attributes to *sandbox-server* (see §5 R8-3a) |
| `event_callback/webhook_router.py` | `ca457ed1` | `POST /events/{conversation_id}` → `event_service.save_event(...)` (webhook population path) |

## 2. Method

1. Read the r8 header notice, §1, §2, §5 (all sub-sections incl. §5.9, §5.10.0/§5.10.0.1/§5.10.1–§5.10.5,
   §5.14.0–§5.14.4, §5.15/§5.15.1–§5.15.6, §5.16), §6, §7, §8, §9, §10, §11, §12, §13 of the proposal
   in full, and the r8 self-review in full.
2. Re-fetched and re-hashed **every** source r8 cites, **independently** (not from any cached copy of a
   prior reviewer), and confirmed each cited line/behavior.
3. For each r8 remediation and each central claim, attempted to **falsify** it: read the code path the
   claim depends on, looked for a counterexample, and searched the pinned repos for a primitive the
   claim says does not exist (the lifecycle module and the tag-reading property were found this way).
4. Cross-checked the live Cloud V1 OpenAPI for the API surfaces the proposal reasons about.

## 3. The r8 central claims and remediations — independent re-verification

The strongest part of r8 is that its facts are real. I confirm:

| # | r8 claim (remediation) | Pinned source (verified this session) | Result |
| --- | --- | --- | --- |
| 1 | R7-1: conversation delete **archives** the workspace (`_finalize_sandbox_delete` → `archive_conversation_workspace` → `archive_workspace`); sandbox torn down only when `count_conversations_by_sandbox_id == 0` | `app_conversation_router.py` `c43ed4f7`: `_finalize_sandbox_delete` (1050), `archive_conversation_workspace(...)` (1071), `count_conversations_by_sandbox_id(...)` (1086), `delete_sandbox` (1091), `asyncio.create_task` (1189), tag read (1188); `workspace_archive.py` `202fc8e1` `archive_workspace` (334), `store.write` (516) | **MATCH** |
| 2 | R7-1: the agent-server delete **preserves** the workspace | SDK `conversation_service.py` `9e9b3e63` (1911): "Safely remove only the conversation directory (**workspace is preserved**)" | **MATCH** |
| 3 | R7-1: sandbox-scoped delete **never archives** | enterprise `sandbox/sandbox_router.py` `bb9bbe23` (302-304) — *not* sandbox-server (see §5 R8-3a) | **MATCH (claim); attribution off** |
| 4 | R7-2: `_get_agent_server_context` / `AgentServerContext` carries **no** per-conversation root | `app_conversation_router.py` `c43ed4f7`: `AgentServerContext` (220-228) has no workspace-path field; `sandbox_spec.working_dir` used (334, 1364) | **MATCH** |
| 5 | R7-2: grouped root `{base}/{conversation_id.hex}` exists; pinned in the reserved `archiveworkspacepath` tag, server-written | `settings_models.py` `27bae62a` `grouped_workspace_dir` (753); `SandboxGroupingStrategy` (739-748); `app_conversation_models.py` `7a4a54c0` `ARCHIVE_WORKSPACE_PATH_TAG_KEY` (65), `RESERVED_TAG_KEYS` (86); `live_status_app_conversation_service.py` `9f4f1596` (1124) `tags[...] = working_dir` | **MATCH** |
| 6 | R7-2: the agent-server derives the root from its **own** conversation | SDK `runtime_router.py` `5bea70f0` (41-43): `workspace_root = Path(event_service.get_conversation().workspace.working_dir).resolve()` | **MATCH** |
| 7 | R7-3: the poller runs **only when there is no public URL**; otherwise **webhooks** | `remote_sandbox_service.py` `d239ec43` (1519): `if web_url is None or 'localhost' in web_url:` → `poll_agent_servers` (1523); `poll_agent_servers` (1256) → `refresh_conversation` (1345) → `save_event` (1438); webhook path `event_callback/webhook_router.py` (557 → 573 `save_event`) | **MATCH** |
| 8 | R7-4: the L1–L8 ↔ F1–F7/F6a/F6b cross-map | proposal §5.10.0.1 (1086) present, complete for L1–L8 and F1–F5/F6a | **MATCH** |

**Conclusion of §3:** the R7-1…R7-4 remediations are real, not cosmetic. r8 did not weaken any control.

## 4. Adversarial findings (new)

### R8-1 (MEDIUM, new, source-backed) — the C2 physical-removal path **is modeled in the pinned source**; r8's "unmodeled / outside the pinned repos" premise is false

**What r8 claims.** r8 makes the workspace directory's physical removal the *only* non-F7 path by which
C2 (the workspace-materialized copy) is ever reclaimed, and asserts that path is **not modeled by any
primitive in the pinned source**:

- §5.10.1 C2 row (line 1119): C2 is removed "**only** … the workspace directory is physically removed —
  which the pinned source shows happens **only on sandbox/pod teardown** ('runtime-api idle reap',
  **unmodeled**; **indefinitely delayed under sandbox grouping**)";
- §5.10.4 (1227-1252): "the directory is physically removed **only on sandbox/pod teardown**
  ('runtime-api idle reap'), which is **not modeled**";
- §11 (2526-2531): "The only named physical-removal backstop is the '**runtime-api idle reap**' … —
  **outside** the pinned repos";
- §5.10.3 case 10 (1176-1182): "the 'runtime-api idle reap' — which is **not modeled** by any primitive
  in the pinned source";
- §12 Q18 (2723-2729) and §6 T-24 (1909) carry the same premise.

**What the pinned source actually contains.** The pinned `OpenHands/enterprise@3fac53df…` has a full,
wired sandbox-lifecycle subsystem — a **primitive in the pinned source** — that deletes the sandbox
**and its workspace** after an idle period:

- `sandbox/lifecycle/settings.py` `1cdd88d5` (25-31): `delete_after_seconds: int = Field(default=10 * 24 * 60 * 60, …)`
  with the description **"Delete a sandbox, and its workspace, once it has not run for this long."**
- `sandbox/lifecycle/rules.py` `0f0df7a9` (107-108): `if _elapsed(settings.delete_after_seconds, last_ran_at, now): return Decision(Action.DELETE, Reason.INACTIVE)`.
- `sandbox/lifecycle/tasks.py` `834e9452` (181-182): `elif decision.action == Action.DELETE: await sandbox_service.delete_sandbox(sandbox_id)`.
- `sandbox/lifecycle/sweep.py` `1d99bd1c`: periodic sweep (`* * * * *`) selecting due sandboxes from the sandbox table.
- `worker/app.py` `a287ec5a` (6, 33): `from …sandbox.lifecycle.tasks import lifecycle` … `app.add_tasks_from(lifecycle, namespace='sandbox_lifecycle')` — **the job is wired into the running worker**.
- `sandbox/managed_sandbox_service.py` `c1286e09` (156-167): `delete_sandbox` → `_delete_at_provider(...)` (removes the container/pod, and with it the workspace).
- Scope (`sandbox/lifecycle/__init__.py` `446effa0`, lines 3-4): "This covers every backend that subclasses `ManagedSandboxServiceInjector`: **Docker, E2B and k8s agent-sandbox**. **runtime-api manages the remote backend's sandboxes itself.**" — confirmed by `class DockerSandboxService(ManagedSandboxService)` (docker `00953ee1` line 124), `E2BSandboxService(ManagedSandboxService)`, `K8sAgentSandboxService(ManagedSandboxService)`.

**Why this is a defect.**

1. The literal claim "**not modeled by any primitive in the pinned source**" (§5.10.3 case 10; §5.10.4)
   is **false**: the lifecycle module *is* a primitive in the pinned source and *is* wired.
2. The claim "**outside** the pinned repos" (§11) is true **only** for the Cloud production path
   (RemoteSandboxService → runtime-api, whose lifecycle the enterprise source explicitly delegates to
   runtime-api). It is **false** as a universal statement: for the managed backends the same pinned
   repo models the removal, with a **configurable** bound (default 10 days idle).
3. "**indefinitely delayed under sandbox grouping**" (§5.10.1, §5.10.4) is **overstated**: the
   lifecycle's `delete_after_seconds` uses `LAST_RAN_AT = greatest(state_changed_at, last_active_at)`
   (sweep.py), so once **all** conversations in a grouped sandbox are idle, the sandbox — and the
   shared workspace, including the deleted conversation's nested directory — **is** deleted on the
   bound. Grouping delays, it does not make it unbounded.
4. Consequently, §12 **Q18** asks the owner to define a bounded retention policy "for C2" as if none
   existed, when a bounded, configurable mechanism exists in the pinned source for the managed
   backends. The owner question is mis-framed (the real open question is the *Cloud/runtime-api* path's
   bound and the *interaction with grouping*, not a from-scratch policy).

**Direction and severity.** The direction is **conservative** (r8 over-states the exposure; it does not
hide a control or weaken one), which is why this is **MEDIUM**, not HIGH. But it is a **false
source-grounding claim on the central R7-1 remediation** — exactly the class the R7 review made
blocking — and §11's own method rule is "source wins". The r8 self-review row 9 also asserts "the
sandbox-scoped delete **never archives**" as the *only* context, omitting the modeled delete.

**Required fix (documentation only).** State the removal path accurately: (a) the pinned enterprise
source **models** an idle/`delete_after_seconds` sandbox-and-workspace delete for **managed** backends
(Docker/E2B/k8s), wired in the worker; (b) for the **Cloud/runtime-api** backend the lifecycle is
**delegated to runtime-api** (external, unmodeled by these repos) — that is the *only* "unmodeled"
part; (c) re-frame Q18 around the Cloud/runtime-api bound and grouping interaction, and cite the
lifecycle files + hashes. No control changes.

### R8-2 (MEDIUM, new, source-backed) — the Cloud-side per-conversation workspace-root read **exists and ships live**; U-12's "NEW + UNVERIFIED" classification is wrong

**What r8 claims.** §5.15.6 and U-12 (line 1631) state: the pinned source "does **not** establish a
**single Cloud-side read** of the per-conversation root, nor a Cloud-side verification of the binding",
and classify the Cloud-side **root-provenance binding** as **NEW upstream capability (U-12)** with its
availability **UNVERIFIED** (also §5.14.2 step 3, §5.15.5 rows at 1784-1785, §12 Q22).

**What the pinned source and the live API actually show.** The pinned `enterprise@3fac53df…` **does**
read the per-conversation root Cloud-side, and that read **ships in the live Cloud V1 API**:

- `app_conversation/app_conversation_models.py` `7a4a54c0` (250-265): `AppConversationInfo.repositories`
  is a `@computed_field` property that calls
  `conversation_repositories(self.selected_repository, self.selected_branch, self.git_provider, self.additional_repositories, self.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY))`
  — i.e. it reads the pinned, server-managed **`archiveworkspacepath`** tag (the per-conversation root).
- `app_conversation/additional_repositories.py` `a8d0bbe3` (89-106): `conversation_repositories(...)`
  builds `path=f'{working_dir}/{folder}'` from that `working_dir` (the tag value) — a Cloud-side
  resolution of the per-conversation root subtree.
- **Live proof:** the live OpenAPI (`1.91.0`, `f0f4d4e9…`) exposes
  `AppConversation.repositories` (array of `ConversationRepository`) with
  `ConversationRepository.path` = **"Absolute path of the folder in the sandbox"**, returned by
  `GET /api/v1/app-conversations` and `GET /api/v1/app-conversations/search`. This is a **shipped**
  Cloud-side read of the tag-derived root.

**Why this is a defect.** The pinned source **does** establish a Cloud-side read of the
per-conversation root, and it is **live** — directly contradicting "UNVERIFIED that a Cloud-side read
of the per-conversation root exists today" and the "NEW upstream capability" classification of the
*read*. What is genuinely new is narrower: the **identity binding** of the resolved root to
`(principal, conversation_id, operation_id)` and the **write-authorization** of the delivery. r8
bundles a **shipped read** into a **NEW** capability, which inflates the upstream-work estimate for the
R7-2 remediation (the very artifact the R7 review asked for).

**Direction and severity.** Conservative (r8 demands more than exists), hence **MEDIUM**: it is an
inaccurate classification on the central R7-2 remediation, and it under-credits existing, auditable
capability. It does **not** create an unsafe design.

**Required fix (documentation only).** Re-classify U-12: state that the **tag→root resolution is
shipped** (`AppConversationInfo.repositories` + `conversation_repositories`, exposed live via
`AppConversation.repositories.path`), cite `additional_repositories.py` `a8d0bbe3` and the live
schema, and scope the **NEW** part to the **identity binding + write-authorization**. Keep the
fail-closed rule (§5.15.6) — it remains correct and desirable.

## 5. Additional defects (lower severity)

### R8-3 (LOW, new) — source-citation inaccuracies

- **(a) Wrong repo for `sandbox_router.py` `bb9bbe23…`.** §11 (2527) writes "sandbox-server
  `sandbox_router.py` (sha256 `bb9bbe23…`)". `bb9bbe23…` is the **enterprise**
  `openhands/app_server/sandbox/sandbox_router.py`; the **sandbox-server** file is `07fef71e…`. Both
  contain the "never archives" comment, so the *claim* is true — but the *attribution* is wrong.
- **(b) Wrong filename in the r8 self-review.** Self-review row 2 cites `…/sandbox/ws_archive.py`
  `202fc8e1…`; the file is `…/sandbox/workspace_archive.py` (there is no `ws_archive.py`). Self-review
  row 9 cites enterprise `…/sandbox/sbx_router.py` `bb9bbe23…`; enterprise has no `sbx_router.py` (that
  name exists only in sandbox-server). These are in the self-review, not the proposal, but they are
  source-citation errors.
- **(c) Garbled sentence in §2.2.** Line 477 reads "… else **webhooks** feed the store copies events
  **one at a time** on a `sleep_interval` …" — a merge artifact; the intended meaning (webhooks feed
  the store when a public URL exists; the *poll loop* copies one at a time) is stated correctly
  elsewhere (§5.15.4). Fix the sentence.

### R8-4 (INFO, new) — pinned live-spec version is stale

r8 pins the live Cloud V1 spec at `1.87.1` / 242 paths. The live spec this session is **`1.91.0` / 244
paths** (sha256 `f0f4d4e9…`). The **"no Cloud upload"** conclusion is unaffected (`multipart` = 0,
`binary` = 0, no `attach`/`upload` path). Not a defect — the proposal labels it "as of r2 time" — but
the number no longer equals the live value, and §11's method treats these as current identifiers.

## 6. State model, lifecycle, and crash windows (independent re-check)

| Item | r8 claim | Check | Verdict |
| --- | --- | --- | --- |
| Observable states | `stored \| delivered \| rejected \| failed \| expired`; `accepted` internal-only | §5.5 (789-810) / §5.9 agree | **CONSISTENT** |
| `delivered` reachability | only via U-3 (F6b) from a trusted, non-agent issuer, from a quiesced source | §5.9/§5.10/§5.14.2/§5.15.1–§5.15.4/§6/§8.1/§9/§10 agree | **CONSISTENT** |
| Staging reclaim authority | `delivered` (U-3) or `expires_at`; never `consumed_at` alone | §5.10.1 C1 + §8.3 + §12 Q12 agree | **CONSISTENT** |
| Workspace-copy lifetime | never timer-deleted; only F7 (unmodeled) or physical removal; not conversation archive/delete | consistent internally — **but the "physical removal" characterization is R8-1** | **CONSISTENT (internal); source claim wrong** |
| Workspace-root provenance | authoritative source pinned; bound to `(principal, conversation_id, operation_id)`; fail closed | consistent internally — **but the "read is NEW/UNVERIFIED" part is R8-2** | **CONSISTENT (internal); classification wrong** |
| Agent-facing path form | absolute | §5.14.2 step 5 + §5.15.5 agree (reader `a1d735d4` verified) | **CONSISTENT** |
| Event-evidence source | quiesced/finalized, on either population path | §5.15.4 + §11 + §2.2 agree (both paths verified) | **CONSISTENT** |
| L/F taxonomy | two vocabularies, explicitly cross-mapped | §5.10.0.1 + §5.14.0 agree | **CONSISTENT** |
| Crash windows (§8.3) / lifecycle races (§5.10.3) | unchanged in substance | §5.10.3 case 10 updated; no case deletes a copy needed for reconciliation/active use | **CONSISTENT** |

## 7. What r8 does **not** claim (fairness note)

r8 is honest about its limits and I verified these are not over-claims: it does **not** claim U-3
exists or that any existing primitive proves a successful content read; it does **not** claim a
quiesced evidence source (U-10), the absolute-path producer (U-11), or a durable
active-conversation accept exists; it does **not** claim a bounded retention policy exists; and it
does **not** claim P0 is complete. The r8 self-review explicitly labels itself **self-assessment** and
requests an independent review (§9 criterion 10) — this document is that review.

## 8. Unverified / limitations of this review (honest list)

1. **The Cloud production sandbox backend's lifecycle is external.** I verified the enterprise source
   *delegates* the remote backend's lifecycle to runtime-api (`lifecycle/__init__.py` line 4); I could
   **not** read runtime-api's source (not in the pinned repos), so I cannot state its exact
   `delete_after_seconds` equivalent. r8's "unmodeled" is true for *this* path; my R8-1 is scoped to
   the *managed* backends, where the pinned source **does** model it.
2. **The live Cloud spec is a moving target.** I verified `1.91.0`/244 paths and the
   `AppConversation.repositories` field *this session*; the field's presence in the live API is strong
   evidence the tag→root read ships, but I did not exercise the endpoint (no credential, no production
   call).
3. **`AppConversationInfo` is not itself a response schema** in the live spec (`AppConversation` is);
   `AppConversation` inherits `repositories`, which is why the field appears in the live schema. I
   verified inheritance in source (`class AppConversation(AppConversationInfo)`).
4. **No test was executed** for any upstream capability (none exists); this task is documentation-only
   and read-only.
5. **Independence:** I am not the author of the proposal or of any r2–r7 review/self-review. This is a
   fresh-context adversarial review.

## 9. Verdict and required changes

**Verdict: `NEEDS_REVISION`.**

The four R7-1…R7-4 remediations are real and three rest on independently re-verified facts; no security
control was weakened. However, two MEDIUM source-grounding defects sit on the two **blocking**
remediations, so r8 is not ready for owner approval until they are corrected. All fixes are
documentation/contract-level; **no control may be weakened and no machinery needs to be invented.**

**Required changes (in priority order):**

1. **(R8-1) Correct the C2 physical-removal account.** In §5.10.1 (C2 row), §5.10.3 case 10, §5.10.4,
   §6 T-24, §8.1 I12, §9 7b, §11, and §12 Q18: (a) state that the pinned **enterprise** source
   **models** an idle / `delete_after_seconds` sandbox-and-workspace delete for **managed** backends
   (Docker/E2B/k8s), wired in the worker, and cite
   `sandbox/lifecycle/{settings,rules,tasks,sweep}.py` + `worker/app.py` with hashes; (b) scope the
   "unmodeled / external" statement to the **Cloud/runtime-api** backend only; (c) re-frame Q18 around
   the Cloud/runtime-api bound and the grouping interaction rather than "no mechanism exists".
2. **(R8-2) Re-classify U-12 / §5.15.6.** State that the **tag→root resolution is shipped**
   (`AppConversationInfo.repositories` + `conversation_repositories`; live via
   `AppConversation.repositories.path`), cite `additional_repositories.py` `a8d0bbe3` and the live
   schema, and scope the **NEW** part to the **identity binding + write-authorization**. Keep the
   fail-closed rule.
3. **(R8-3) Fix the citations:** attribute `bb9bbe23…` to **enterprise** `sandbox/sandbox_router.py`
   (sandbox-server is `07fef71e…`); fix the self-review's `ws_archive.py` → `workspace_archive.py` and
   drop the nonexistent enterprise `sbx_router.py`; repair the garbled §2.2 sentence (line 477).
4. **(R8-4) Refresh the live-spec identifier** (or label it explicitly as of-r2-time), noting
   `1.91.0`/244 paths today; confirm the "no upload" conclusion is unchanged.

**Not required (do not change):** the state model, the U-3 trust boundary (§5.15.1–§5.15.3), the
quiescence requirement (§5.15.4), the absolute-path contract (§5.15.5), the L/F cross-map (§5.10.0.1),
the threat table, or any invariant — all re-verified as internally consistent and source-grounded.

---

*This review was produced by an AI agent (OpenHands) on behalf of the repository owner. It is
read-only and created exactly one artifact; no other file was modified.*
