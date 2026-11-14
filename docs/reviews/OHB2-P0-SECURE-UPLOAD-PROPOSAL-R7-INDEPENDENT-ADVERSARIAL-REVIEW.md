# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7 — INDEPENDENT ADVERSARIAL REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-INDEPENDENT-ADVERSARIAL-REVIEW`

Reviewer: fresh-context independent adversarial reviewer; **not** the author of the proposal, **not**
the author of the r7 self-review, and **not** the author of any earlier (r2–r6) review. All actions
were **read-only**: upstream public source and specs were re-fetched independently this session and
re-hashed; **no production call, no credential, no secret access, no modification** of the proposal,
the self-review, or any previous review. This review file is the **only** artifact created. No
commit/push/PR/merge/deploy, no branch change, no upstream issue/PR/maintainer contact. **P0 remains
unimplemented.**

## Verdict: **NEEDS_REVISION**

r7 is a **genuine, well-executed correction of r6**. Its two blocking claims are **verified true
against the pinned source**: (a) the materialized *workspace* copy must **not** be reclaimed by the
`expires_at` timer (the r6 lifetime hazard), and (b) an **agent-emittable** read acknowledgment is
**not** evidence, so `delivered` must require a **trusted, non-agent issuer**. All five r6 findings
(R6-1…R6-5) are addressed in the r7 text (§4), the lifecycle and trust rules were made **stricter**,
and I found **no** weakening of any threat-model row, P0 invariant, or acceptance criterion (§5).

**But r7 is not yet ready for owner approval**, because its **new lifecycle model rests on a
retention-removal path that the pinned source does not provide**, and because the new **absolute-path
contract** names a **workspace-root resolution** that the reuse target it cites cannot perform under
non-default sandbox grouping:

- **R7-1 (MEDIUM, new, source-backed) — the only "C2 is reclaimed" path ("the workspace is
  removed") is not established by the pinned source, and is contradicted for grouped sandboxes.**
  r7 makes **workspace removal** (conversation archived/deleted) the *sole* non-F7 way a
  materialized workspace copy (C2) is ever reclaimed (§5.10.1 C2 row line 1042; §5.10.1 line 1052;
  §5.10.1 "Conversation ended/deleted" lines 1085-1090; §5.10.4 lines 1134-1152; §6 T-24 line 1730;
  §8.1 I12 line 1919; §9 7b line 2060; §12 Q18 lines 2470-2475). Against the pinned source this is
  **not** what a conversation delete does: the Cloud conversation-delete finalizer **archives** the
  workspace to a bucket (`_finalize_sandbox_delete` → `archive_conversation_workspace` →
  `workspace_archive.archive_workspace`) and then tears the **sandbox** down **only when no sibling
  conversation still references it**; the agent-server delete explicitly **preserves** the workspace
  ("Safely remove only the conversation directory (workspace is preserved)"). The workspace directory
  is never *deleted* on conversation delete — it disappears, if at all, only with **sandbox/pod
  teardown** (the "runtime-api idle reap" the source names), which is exactly the path r7 does **not**
  model. Under a **grouped** sandbox (the non-default strategies in `SandboxGroupingStrategy`), a
  sibling conversation **keeps the sandbox alive**, so the shared workspace directory — including the
  deleted conversation's nested workspace — is **not** removed at all. Consequence: the retention
  limitation r7 discloses in Q18 ("C2 persists for the life of the conversation … unbounded") is
  **understated** — in the pinned model C2 can outlive the conversation indefinitely (until an
  unmodeled idle reap), and the "conversation ended ⇒ C2 goes away" claim that several sections rely
  on is **UNVERIFIED/false**.
- **R7-2 (MEDIUM, new, source-backed) — the path contract resolves the workspace root from a source
  that does not carry it.** §5.14.2 step 3 (line 1355-1358) and §5.15.5 (row "Workspace root", line
  1641) say the Cloud "re-resolves the target conversation → sandbox → workspace root **server-side**
  (reusing `_get_agent_server_context`)" and that the write happens under "`bind_local_conversation_runtime`
  `working_dir`". Those are **two different roots**: `bind_local_conversation_runtime` takes the root
  from the **agent-server's** `conversation.workspace.working_dir` — which the Cloud sets to the
  **grouped** path `{base}/{conversation_id.hex}` for every strategy other than `NO_GROUPING` — while
  the Cloud's `_get_agent_server_context` exposes only `sandbox_spec.working_dir` (the **ungrouped
  base**) and does **not** read the per-conversation pinned path (`archiveworkspacepath` tag). So the
  reuse target r7 names would compute the **wrong** root under any grouping strategy, and the op's
  `conversation_id` "must match the resolved workspace" check (§5.14.2 step 3) would compare against
  the wrong value.

**All required fixes are documentation/contract-level.** No new upstream *machinery* beyond what r7
already lists (U-1…U-11) is needed; both findings are about **precision and source-grounding** of the
new lifecycle/path contracts. Hence the verdict is `NEEDS_REVISION`, **not**
`BLOCKED_BY_MISSING_UPSTREAM_EVIDENCE`.

---

## 1. Baseline and file hashes

| Item | Value |
| --- | --- |
| Repository | `TM-AEM/OpenHandBot` |
| Branch | `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` |
| HEAD | `907b20de3fa6627795c14f29677e9f39c68e82f4` |
| origin/main | `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` |
| Review date | Wed Nov 11 2026 |
| r7 proposal | `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` — sha256 `d4e4fdc84b7a474e1ff166026dec187db65702ae238316466972d27a36342ba1` (2504 lines) |
| r7 self-review | `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-SELF-REVIEW.md` — sha256 `a72f12a0e56696a8b511a5c553511a520382418d458124732b737abea014cd5a` (133 lines) |
| r6 review (driver) | `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-INDEPENDENT-ADVERSARIAL-REVIEW.md` — sha256 `e264ebdf8c4d3c17566c99ea396c7fa106293486786ce3cdbac7c04a2049564e` (430 lines) |

**Working-tree status before review** (read only; nothing reset/cleaned/deleted/checked out):

```
 M .agent/PROGRESS.md
 M bot/handlers.py
 M docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md
 M docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md
?? docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? tests/test_stage2_high_ack_blocking_fix.py
?? tests/test_stage4_f1_status_cost_operational_ack.py
```

The pre-existing untracked/modified files were **left untouched**. The r7 review file this task
creates (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-INDEPENDENT-ADVERSARIAL-REVIEW.md`) is
intentionally **not** shown above.

**Source revisions used (re-fetched and re-hashed this session, read-only).** The pinned SHAs are
unchanged from r2–r6:

| Repo | Pinned commit |
| --- | --- |
| `OpenHands/software-agent-sdk` | `9f7d5cb11b1256c1878f5584a657401feca9ad16` |
| `OpenHands/sandbox-server` | `43e91604ccd0a9960c8d5c52faadd60b30f10e63` |
| `OpenHands/enterprise` | `3fac53df8c2efcb67ff3537d1162e8c8a108f565` |

**Additional files re-fetched this session** (sha256 prefix, enterprise unless noted): `workspace_archive.py`
`202fc8e1`; `settings/settings_models.py` `27bae62a`; `app_conversation/app_conversation_models.py`
`7a4a54c0`; `app_conversation/additional_repositories.py` `a8d0bbe3`; sandbox-server
`remote_sandbox_service.py` `c523a807`; sandbox-server `sandbox_router.py` (conversation-delete
ownership comment); SDK `openhands-agent-server/…/runtime_router.py` `5bea70f0`; SDK
`openhands-agent-server/…/file_router.py` `13f0cae7`; SDK
`openhands-agent-server/…/conversation_service.py` `9e9b3e63`; SDK
`openhands-tools/…/file_editor/definition.py` `da48687f`; SDK
`openhands-tools/…/file_editor/exceptions.py` `ca35cad9`.

---

## 2. Method

1. Read the r6 review findings R6-1…R6-5 and the r7 header notice, §1, §2, §5 (all sub-sections), §6,
   §7, §8, §9, §10, §11, §12, §13 of the proposal in full.
2. Re-fetched and re-hashed every source the r7 text cites, **independently** (not from any cached
   copy of a prior reviewer), and confirmed each cited line/behavior.
3. For each r7 claim, attempted to **falsify** it: read the code path the claim depends on and looked
   for a counterexample. The two MEDIUM findings below are counterexamples found this way.
4. Re-checked **preservation** (no threat row, invariant, or acceptance criterion weakened vs r6) and
   **internal consistency** of the re-derived lifecycle, trust, consistency, and path contracts.
5. Cross-checked the r7 self-review's claims against the same source (the self-review's evidence
   table re-verified, with two additions it does not make — R7-1 and R7-2).

---

## 3. The r7 central claims are verified (the strongest part of r7)

**Claim (r6-1 fix).** The workspace-materialized copy (C2) must **never** be reclaimed at
`expires_at`; only the staging/recovery copy (C1/C3) is timer-reclaimed.

**Independent verification — TRUE (as a contract).** The r7 §5.10.1 per-copy table (C1 staging /
C2 workspace / C3 recovery / C4 op rows / C5 local rows) is internally consistent, and the
`expires_at`-reclaims-C1-only rule is repeated consistently across §5.9, §5.10.2–§5.10.5, §5.14.2
step 7, §5.14.4, §5.11, §6 (T-19/T-24), §8.1 (I10/I12), §8.3, §9 7b/7c, §10, §12 (Q6/Q16/Q18). I
found **no surviving text** that lets `expires_at` reclaim C2. The r6 §5.10 line-948 wording is
withdrawn. This is a real, correct fix.

**Claim (r6-2 fix).** U-3 must be issued by a **trusted, non-agent** component; an agent/tool-emitted
acknowledgment is never evidence.

**Independent verification — TRUE (as a contract).** §5.15.1 (trust boundary), §5.15.2 (authenticated
provenance / integrity / replay protection / authorization scope), §5.15.3 (fields + 8 invariants +
the F-fact mapping) are coherent and strictly stronger than r6. §5.11 forbids `attachment.read_confirmed`
for a non-trusted issuer; §6 T-22 records the spoofing threat; §12 Q16/Q19 record it as an owner
decision. The self-review's source check ("no read-acknowledgment primitive in the pinned SDK") is
reproduced: code search over the pinned SDK for `read_complete` / `read_receipt` / `bytes_read`
returns **0** results, so the "U-3 is NEW / issuer UNVERIFIED" classification is accurate.

**Claim (r6-3 fix).** The Cloud `events/search` store is a **polled replica**, so event-based evidence
must come from a **quiesced** source (U-10).

**Independent verification — TRUE.** `remote_sandbox_service.py::poll_agent_servers` (`d239ec43…`,
line 1256) is `while True: … await asyncio.sleep(sleep_interval)` → `refresh_conversation` (line
1345) → `event_service.save_event` (line 1438); `event_service_base.save_event` writes one event
file and invalidates the index; `search_events` reads an index snapshot page-by-page. It is a
**replica**, not an atomic view. The requirement is correct. (One completeness gap: the poll loop is
**conditional** — see R7-3.)

**Claim (r6-4 fix).** file_editor `view` requires an **absolute** path; the agent-facing path must be
absolute.

**Independent verification — TRUE.** `file_editor/editor.py` (`a1d735d4…`) `validate_path` line 666:
`if not is_host_absolute_path(path): raise EditorToolParameterInvalidError("path", …)`; line 690:
`if command != "create" and not path.exists(): raise …`. A missing path is rejected; `impl.py`
(`35353ad3…`) maps a `ToolError` to `is_error=True` (lines 68-70); a successful `view` is truncated at
`MAX_RESPONSE_LEN_CHAR = 16000` (`utils/constants.py` `a5b3f2bf…`, applied in `_make_output`).
The absolute-path requirement is accurate.

**Conclusion:** r7's four central corrections are sound and verifiable. The findings below are about
what r7's **new lifecycle and path text still assumes**, not about the corrections themselves.

---

## 4. Remediation mapping — all five r6 findings (independent re-verification)

| # | r6 finding | r7 location(s) | Independent verdict |
| --- | --- | --- | --- |
| **R6-1** | MEDIUM (blocking): the materialized copy is deleted at `expires_at`; §5.10 vs §5.14.2 step 7 contradiction | §5.10 (re-derived: §5.10.0 concepts, §5.10.1 per-copy table, §5.10.2 post-text lifecycle, §5.10.3 crash/race, §5.10.4 retention bound, §5.10.5 deadline); §5.9 rows; §5.14.2 step 7; §5.14.4; §5.11; §6 T-19/T-24; §8.1 I10/I12; §8.3; §9 7b/7c; §10; §12 Q6/Q16/Q18; §13 | **RESOLVED as a contract.** `expires_at` reclaims C1/C3 only; C2 is never timer-deleted. *Residual:* the **only** non-F7 C2-reclaim path ("workspace removal") is not source-grounded (**R7-1**). |
| **R6-2** | MEDIUM (blocking): the U-3 trust model is unspecified | §5.15.1/§5.15.2/§5.15.3; §5.14.0 F6b; §5.14.2 step 6; §5.15 U-3 row; §5.11; §6 T-18/T-22; §8.1 I14; §9 7c; §10.1; §12 Q16/Q19; §13 | **RESOLVED as a contract.** Trust boundary pinned; agent-emitted never evidence; issuer **NEW/UNVERIFIED** (disclosed). *Residual:* none material. |
| **R6-3** | LOW: the "event log" is a polled replica; the read is not atomic | §5.15.4 + U-10; §5.14.1; §5.14.2 step 6; §2.2; §7.5; §6 T-23; §9 7c; §10.1; §11; §12 Q20; §13 | **RESOLVED as a contract.** Quiesced-source requirement stated and source-verified. *Residual:* the poll loop is **conditional** (**R7-3**). |
| **R6-4** | LOW: the reader needs an absolute path but `delivered_path` was relative | §5.15.5 + U-11; §5.14.2 step 5; §5.14.4; §5.7; §5.9; §5.15 U-1; §6 T-22; §9 7c; §10.2; §11; §12 Q21; §13 | **RESOLVED as a contract** for the absolute-path requirement. *Residual:* the **root** the absolute path is built from is mis-specified (**R7-2**). |
| **R6-5** | INFO: stale "seven lifecycle facts" text survives | header r5 notice; §13 r5 row; §5.14.0 (eight) | **RESOLVED.** The only surviving "seven" strings are (a) the header line explicitly marking r5's seven **superseded** (line 112), (b) §13's r5 row marked **superseded**, and (c) unrelated text ("seven crash boundaries", "seven reassessment questions"). No live text claims seven facts. |

**Preservation check (no weakening).** Compared r7 against r6 across the threat model (§6), the P0
invariants (§8.1 I1–I14), and the acceptance criteria (§9). T-18/T-19 are **strengthened**; T-22/T-23/T-24
are **added**; I10/I12/I13/I14 are **strengthened**; criteria 7b/7c are **strengthened**. No row,
invariant, or criterion was weakened. **Confirmed.**

---

## 5. Adversarial findings (new)

### R7-1 (MEDIUM, new, source-backed) — the "workspace removal" C2-reclaim path is not established by the pinned source

**Claim in r7.** The materialized workspace copy (C2) is reclaimed **only** (a) on a trustworthy F7
end-of-use (unmodeled today) **or** (b) when the **workspace is removed** — "the workspace (and
therefore C2) is removed with it" on conversation archive/delete (§5.10.1 C2 row line 1042; §5.10.1
line 1052; §5.10.1 "Conversation ended/deleted" lines 1085-1090; §5.10.4 line 1143; §6 T-24 line 1730;
§8.1 I12 line 1919; §9 7b line 2060; §12 Q18 lines 2470-2475).

**The hazard / gap.** Because F7 is unmodeled, **workspace removal is the sole mechanism by which C2
is ever reclaimed**. r7 presents it as an established lifecycle fact. Against the pinned source it is
**not** what a conversation delete does, and for grouped sandboxes it does **not** happen at all:

- The Cloud conversation-delete route calls `delete_app_conversation(...)`, commits, then schedules a
  **detached** `_finalize_sandbox_delete(...)` (enterprise `app_conversation_router.py` `c43ed4f7…`,
  lines 1111-1198; `asyncio.create_task` at line 1189). That finalizer **archives** the workspace
  (`sandbox_service.archive_conversation_workspace(...)` → `workspace_archive.archive_workspace`,
  enterprise `workspace_archive.py` `202fc8e1…`, line 334; the capture uploads to a bucket via
  `store.write`, line 516) and then deletes the **sandbox** **only if no other conversation still
  references it** (`count_conversations_by_sandbox_id(...) == 0`, lines 1083-1091). **No local
  workspace deletion occurs.**
- `RemoteSandboxService.delete_sandbox` is documented as "**Purely sandbox-scoped**: stop the runtime
  and delete the record. Workspace capture is a separate conversation-scoped step" (enterprise
  `remote_sandbox_service.py` `d239ec43…`, lines 917-925). The sandbox DELETE route repeats this:
  "delete_sandbox is sandbox-scoped (stop + delete) and **never archives** … Workspace capture is
  owned by the conversation-delete finalizer and the runtime-api idle reaper" (sandbox-server
  `sandbox_router.py`).
- The **agent-server** conversation delete explicitly **preserves** the workspace: "Safely remove only
  the conversation directory (**workspace is preserved**)" (SDK `conversation_service.py` `9e9b3e63…`,
  lines 1911-1914; it `safe_rmtree`s only `event_service.conversation_dir` and, for a shared worktree,
  the worktree — not the workspace directory).
- Under a **grouped** sandbox (`SandboxGroupingStrategy` = `GROUP_BY_NEWEST` / `LEAST_RECENTLY_USED` /
  `FEWEST_CONVERSATIONS` / `ADD_TO_ANY`, enterprise `settings/settings_models.py` `27bae62a…`, lines
  739-748), the workspace is nested `{base}/{conversation_id.hex}` (line 767) and a **sibling
  conversation keeps the sandbox** — so neither the shared base directory nor the deleted
  conversation's nested directory is removed by the delete flow.

The only source-visible path by which the workspace directory actually disappears is **sandbox/pod
teardown** — the "runtime-api idle reap" the source repeatedly names as the durability backstop
(enterprise `app_conversation_router.py` lines 1067/1078; `remote_sandbox_service.py` lines 1088/1125)
— which r7 **does not model** as a lifecycle event.

**Why it matters.** r7's retention story is: "C2 persists for the life of the conversation; a bounded
policy is an owner decision (Q18)." But the pinned model shows C2 can persist **past** the conversation
— indefinitely, until an unmodeled sandbox reap — and for grouped sandboxes the "conversation ended ⇒
C2 goes away" statement is simply **false**. So (i) the "workspace removal" reclaim path that §5.10.1,
T-24, I12, §9 7b and Q18 all lean on is **UNVERIFIED/false**, and (ii) the disclosed unbounded-storage
limitation (Q18) is **worse** than stated: there is today **no** conversation-scoped event that
reclaims C2.

**Required fix (contract).** Either (a) state that the "workspace removal" path is the **sandbox/pod
teardown (idle reap)**, not conversation delete — and that under grouping it may be **indefinitely
delayed** while a sibling keeps the sandbox alive — or (b) drop the "workspace removal" reclaim claim
and state plainly that **today no conversation-scoped event reclaims C2** (making Q18's bound
strictly necessary). In both cases, correct §5.10.1's "the workspace (and therefore C2) is removed
with it", T-24, I12, §9 7b, and Q18 to match the source, and add a grouping caveat.

### R7-2 (MEDIUM, new, source-backed) — the path contract's workspace-root resolution uses a source that does not carry the root

**Claim in r7.** §5.14.2 step 3: "The Cloud re-resolves the target conversation → sandbox → workspace
root **server-side** (reusing `_get_agent_server_context`, §7.0) and verifies the operation's
`conversation_id` matches the resolved workspace before any write." §5.15.5 row "Workspace root": "the
write happens under the **resolved** conversation workspace root (`bind_local_conversation_runtime`
`working_dir`); the op's `conversation_id` must match the resolved workspace." §7.0 reuse-map: reuse
`app_conversation_router.py::_get_agent_server_context`.

**The gap.** Those two named sources expose **different** roots, and the one r7 designates for the
Cloud side does not carry the per-conversation workspace path:

- `bind_local_conversation_runtime` derives the root from the **agent-server's** own conversation:
  `workspace_root = Path(event_service.get_conversation().workspace.working_dir).resolve()` (SDK
  `runtime_router.py` `5bea70f0…`, lines 41-43). The agent-server's `working_dir` is the **grouped**
  path — the Cloud sets it to `grouped_workspace_dir(sandbox_spec.working_dir, strategy,
  conversation_id.hex)` at start (enterprise `live_status_app_conversation_service.py` `9f4f1596…`,
  lines 972-976; `settings_models.py` line 767).
- The Cloud's `_get_agent_server_context` exposes only `sandbox_spec.working_dir` (enterprise
  `app_conversation_router.py` lines 230-306; spec fetched at line 278, context built at 300-306) —
  the **ungrouped base** — and its `AgentServerContext` dataclass (lines 220-228) has **no** field for
  the pinned per-conversation path. The pinned path lives in the conversation **tag**
  `archiveworkspacepath` (enterprise `app_conversation_models.py` `7a4a54c0…`, line 65;
  `live_status…` line 1124 writes it), which `_get_agent_server_context` does **not** read.

Note the asymmetry with §7.0: there, Q3 correctly says `_get_agent_server_context` resolves
"conversation → sandbox → `AGENT_SERVER` exposed URL → `session_api_key`" — i.e. the **runtime
endpoint and key**, not the workspace root. §5.14.2 step 3 and §5.15.5 then **overstate** it as also
resolving the "**workspace root**". The helper does not do that.

So for every grouping strategy other than `NO_GROUPING`, a Cloud re-resolution built on
`_get_agent_server_context` would compute the **wrong** workspace root (the shared base rather than the
conversation's nested dir), and the op's `conversation_id`-matches-workspace check would compare
against the wrong value — either writing outside the intended conversation subtree or producing a
false rejection. r7 never mentions sandbox grouping.

**Why it matters.** This is the load-bearing "how is the workspace root resolved" step of the very
path contract r7 was written to pin (§5.15.5). Getting the root from the wrong source undermines the
"server-side resolution" and "conversation identity verification" claims (§5.14.2 steps 3–4) and the
`O_NOFOLLOW`/containment guarantees that are asserted relative to that root.

**Required fix (contract).** Specify the **authoritative** source of the conversation's workspace root
for the Cloud side — the pinned `archiveworkspacepath` tag, or a query to the agent-server that
returns its actual `workspace.working_dir` — and state the **grouping** behavior explicitly (the root
is the per-conversation nested dir under any non-`NO_GROUPING` strategy). Note that the
`bind_local_conversation_runtime` containment applies **on the agent-server**, where the correct root
is already available, and is therefore a defense-in-depth check, not the Cloud's resolution source.

### R7-3 (LOW, new, source-backed) — the polled-replica description is not universal

**Claim in r7.** §5.15.4: "The Cloud `GET …/events/search` store is populated by a **best-effort poll
loop** — `remote_sandbox_service.py::poll_agent_servers` … It is a **replica** of the agent-server
event log."

**Gap.** That poller is **conditional**: it is started only when the app server has **no public URL**
(`web_url is None or 'localhost' in web_url`) (enterprise `remote_sandbox_service.py` `d239ec43…`,
lines 1518-1526: "When the app server does not have a public facing url, we poll the agent servers").
In a deployment with a public URL, the Cloud event store is fed by a **different** path (webhook
callbacks — the module's own docstring names "webhook callbacks cannot be invoked" as the reason for
polling), whose freshness/lag characteristics differ. So "populated by a best-effort poll loop" is
**deployment-dependent**, not universal.

**Why it matters.** The *requirement* r7 states (evidence must come from a quiesced source) is
correct and should stand; but the *mechanism* description is incomplete, and a reader could wrongly
assume the quiescence argument is scoped to the poll interval in every deployment.

**Required fix.** Qualify §5.15.4: the replica may be fed by the poll loop **or** by webhooks,
depending on deployment; the quiescence requirement applies regardless of which path populates the
store.

### R7-4 (INFO, new) — two parallel "eight"-item taxonomies without a cross-map

r7 introduces **two** distinct eight-item vocabularies, both asserted "never conflated":
`§5.10.0` concepts **L1–L8** (deadlines/lifetimes/evidences) and `§5.14.0` facts **F1–F5, F6a/F6b, F7**
(milestones). They overlap in meaning (L6 "read evidence (F6b)" vs F6b; L7 "end-of-use (F7)" vs F7)
but only partly cross-reference, and §5.15.3's fact table maps only the F-* side. In a document whose
thesis is "no two may be equated", two near-homonymous eight-item taxonomies are a clarity risk.

**Suggested fix (optional).** Add a one-line cross-map (L1→F-none, L6→F6b, L7→F7, …) so the two
vocabularies cannot drift.

---

## 6. State model, lifecycle, and crash windows (independent re-check)

| Item | r7 claim | Check | Verdict |
| --- | --- | --- | --- |
| Observable states | `stored \| delivered \| rejected \| failed \| expired`; `accepted` internal-only | §5.5 example (line 743) and §5.9 example (line 867) both `"state": "stored"`; §5.5/§5.9 prose agree | **CONSISTENT** |
| `delivered` reachability | only via **U-3** (F6b) from a trusted, non-agent issuer, quiesced source | §5.9/§5.10/§5.14.2/§5.15.1–§5.15.4/§6/§8.1/§9/§10 all consistent | **CONSISTENT** |
| Staging (C1) reclaim | `delivered`+terminal, or `expires_at`; never `consumed_at` alone | §5.10.1 C1 row (line 1041) + §8.3 + §12 Q12 consistent | **CONSISTENT** |
| Workspace-copy (C2) lifetime | never timer-deleted; only F7 (unmodeled) or workspace removal | §5.10.0–§5.10.4 + §5.14.2 step 7 + §6 T-19/T-24 + §8.1 I10/I12 internally consistent — **but the "workspace removal" premise is not source-grounded** | **INCONSISTENT WITH SOURCE — R7-1** |
| Agent-facing path form | **absolute** | §5.14.2 step 5 + §5.15.5 + §5.14.4 + §5.7 + §5.9 consistent; no surviving "relative to the agent" claim | **CONSISTENT** (root source: **R7-2**) |
| Event-evidence source | quiesced/finalized (not the replica) | §5.15.4 + §5.14.1 + §5.14.2 step 6 + §6 T-23 consistent; mechanism description incomplete | **CONSISTENT** (R7-3) |
| Crash windows (§8.3) | 7 boundaries; no exactly-once claim | unchanged in substance; reclamation decoupled from the Telegram ack | **CONSISTENT** |
| Lifecycle crash/race (§5.10.3) | 11 cases; no copy needed for reconciliation or active use is deleted | each case consistent with §5.10.1 | **CONSISTENT** |
| r6-5 stale wording | no live "seven facts" text | only superseded/unrelated occurrences remain | **CONSISTENT** |

---

## 7. What r7 does **not** claim (fairness note)

r7 is honest about its limits: it does **not** claim U-3 exists, nor that a trusted non-agent issuer
exists, nor that a quiesced evidence source (U-10) or the absolute-path producer (U-11) exists, nor
that a bounded C2 retention policy exists (Q18). It marks each as NEW/UNVERIFIED and records the owner
decisions. This candour is why the verdict is `NEEDS_REVISION` and not `BLOCKED`.

---

## 8. Unverified / limitations of this review (honest list)

1. **No test was executed** for the upstream capability (it does not exist). This is a review-only
   task; I did not run the OpenHandBot test suite (no code changed).
2. **The live Cloud V1 spec** was not re-fetched this session; I rely on the proposal's `1.87.1`
   observation and on the pinned `enterprise` router. **UNVERIFIED** that the live spec is unchanged.
3. **The exact `sleep_interval`** of `poll_agent_servers` and the **webhook** population path's lag are
   deployment values I did not read; the **existence** of the poll/replica path is source-verified
   (R6-3/R7-3).
4. **The runtime-api idle reap** (the sandbox teardown that would finally remove a workspace) is
   **outside** the three pinned repos; I can only observe that the pinned code **names** it as the
   durability backstop and that **no** pinned code path deletes the workspace directory. So R7-1's
   positive claim ("conversation delete does not remove the workspace") is source-verified; the
   **timing** of the eventual reap is **UNVERIFIED**.
5. This is a **single** independent review; it does not replace the upstream security review required
   by §7.8 / §9 criterion 10.

---

## 9. Verdict and required changes

**Verdict: `NEEDS_REVISION`.**

r7 correctly and verifiably fixes all five r6 findings and weakens nothing. But its **new lifecycle
model** rests on a retention-removal path the pinned source does not provide, and its **new
absolute-path contract** resolves the workspace root from a source that does not carry it.

**Required before owner approval (all documentation/contract-level):**

1. **R7-1 (MEDIUM).** Correct the "workspace is removed on conversation archive/delete" premise in
   §5.10.1, §5.10.4, T-24, I12, §9 7b, and Q18 to match the pinned source (conversation delete
   **archives** the workspace; the directory is removed only with sandbox/pod teardown — the idle
   reap — which is **not** modeled and is **indefinitely delayed** under sandbox grouping). State
   plainly that today **no conversation-scoped event reclaims C2**.
2. **R7-2 (MEDIUM).** Pin the **authoritative** source of the conversation's workspace root for the
   Cloud side (the `archiveworkspacepath` tag, or an agent-server query for its actual
   `workspace.working_dir`), and state the **grouping** behavior; do not present
   `_get_agent_server_context`/`sandbox_spec.working_dir` as the resolved per-conversation root.
3. **R7-3 (LOW).** Qualify §5.15.4: the Cloud event store may be fed by the poll loop **or** by
   webhooks (deployment-dependent); the quiescence requirement stands either way.
4. **R7-4 (INFO).** Optionally add a cross-map between the L1–L8 and F1–F7/F6a/F6b vocabularies.

**No new upstream machinery beyond U-1…U-11 is required.** After items 1–2 (and preferably 3–4), an r8
review should be able to move to `PASS_WITH_NOTES` or `PASS`.

---

*This review was produced by an independent adversarial reviewer agent (OpenHands) on behalf of the
repository owner. Read-only: no production call, no credential, no modification of the proposal or any
other tracked file. This file is the only artifact created.*
