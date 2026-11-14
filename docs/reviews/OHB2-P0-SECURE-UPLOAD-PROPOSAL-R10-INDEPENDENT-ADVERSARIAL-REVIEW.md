# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10 — INDEPENDENT ADVERSARIAL REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-INDEPENDENT-ADVERSARIAL-REVIEW`

Reviewer: fresh-context independent adversarial reviewer; **not** the author of the proposal, **not** the
author of the r10 self-review, and **not** the author of any earlier (r2–r9) review or self-review. All
actions were **read-only**: upstream public source and the live spec were re-fetched independently this
session and re-hashed; **no production call, no credential, no secret access, no modification** of the
proposal, the self-review, `PROGRESS.md`, memory, source code, tests, or any previous review. This
review file is the **only** artifact created. No commit/push/PR/merge/deploy, no branch change, no
upstream issue/PR/maintainer contact. **P0 remains unimplemented.**

## Verdict: **PASS_WITH_NOTES**

r10 **fully remediates** the four R9 findings (R9-1 … R9-4) and I found **no** weakening of any
security requirement, threat-model row, or P0 invariant. Every source claim I re-checked independently
**matches the pinned source** (§3). The proposal hash matches the value the author reported
(`c19eb3cd…`, 3072 lines), the r10 self-review hash matches (`47e643aa…`, 169 lines), and the driving
R9 review hash matches (`62c074d4…`, 280 lines). The four residual uncertainties (U-3/issuer, U-10,
U-11, U-12-binding, C2 retention) remain honestly open.

I did **not** reach `PASS` because I found **two low-severity citation-accuracy notes** (N10-1, N10-2) of
the **same class** that R8-3 and R9-2 were raised for — a same-fact line-number inconsistency and one
file attributed to the wrong repository in the §11 source list. Neither affects any security
conclusion, and both are documentation-only. These do **not** block owner approval; they should be
folded into the next revision.

---

## 1. Baseline and file hashes

Repo `TM-AEM/OpenHandBot`; branch `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`; `HEAD`
`907b20de3fa6627795c14f29677e9f39c68e82f4`; `origin/main` `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`
(unchanged; no commit, no push, no upstream tracking). Working tree: pre-existing modifications
(`.agent/PROGRESS.md`, `bot/handlers.py`, two other `docs/proposals/*.md`) plus untracked
r-series proposal/review files — **all left exactly as found**; this review added exactly one file.

| Artifact | Lines | sha256 (independently recomputed this session) |
| --- | --- | --- |
| `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` (r10) | 3072 | `c19eb3cd801def4b089b3a7c6667e8218c3a6e1caa684e62f113259a94847222` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-SELF-REVIEW.md` | 169 | `47e643aa213ed9a5831b7dace850aa73f1eb180a08cd5549c52a157b2dbf879c` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-INDEPENDENT-ADVERSARIAL-REVIEW.md` (driving review) | 280 | `62c074d467d8665efe9841f93411abdd0cc2194cc1b0cde041565b349ac46a02` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-SELF-REVIEW.md` | 147 | `fd4640cdf66683768fe7ebc24800768bbeb23b4a37feb5ee03296aa1f354a326` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-INDEPENDENT-ADVERSARIAL-REVIEW.md` | 346 | `843bb33e8b0011acdf6c2cc83a25587ab6fae0a84f788b949b707d44f94b2ed8` |

Structural sanity: 6 triple-backtick fences (balanced); **0** real markdown table column mismatches
(checked with escaped-pipe awareness); paragraph-level parenthesis balance **0** issues.

## 2. Method

1. Read the R9 independent review (verdict `NEEDS_REVISION`, findings R9-1…R9-4) and its §9 "required
   changes" in full; read the r10 self-review in full; read the r8 review's R8-1…R8-4 for the lineage.
2. Read the **entire** r10 proposal (3072 lines), section by section: header + r10 correction notice,
   §1–§4, §5.1–§5.16 (incl. §5.9/§5.9.1, §5.10/§5.10.0–§5.10.5, §5.14/§5.14.0–§5.14.4,
   §5.15/§5.15.1–§5.15.6), §6 (T-01…T-25), §7.0–§7.8, §8.1–§8.4, §9, §10.1–§10.2, §11, §12 (Q1…Q22),
   §13.
3. Independently re-fetched and re-hashed every source the r10 changes rest on, from the pinned
   revisions and the live spec (§3), and re-derived the specific line numbers cited.
4. Attempted to **break** r10 on the axes R9-1…R9-4 address (timer scoping, container-vs-workspace
   deletion, citation accuracy, historical-evidence labelling) **and** on cross-section consistency,
   grepping exhaustively for every surviving absolute phrasing.

## 3. Independent verification of the r10 central claims

| # | r10 claim (finding) | Independent source (pinned, sha256 prefix) | Result |
| --- | --- | --- | --- |
| 1 | The r9 "no timer deletes C2 / C2 is never timer-deleted / the only server-side clock is `expires_at`" wording is now **scoped** to the **operation-scoped** timer, and the **separate** infrastructure timer (Enterprise sandbox lifecycle) is named (R9-1) | `enterprise` `…/sandbox/lifecycle/tasks.py` `834e9452…` (cron `* * * * *` L78, `sweep`; L182 `sandbox_service.delete_sandbox`); `…/lifecycle/rules.py` `0f0df7a9…` (L107-108 `Action.DELETE`/`Reason.INACTIVE`); `…/lifecycle/settings.py` `1cdd88d5…` (L25-29 `delete_after_seconds` default 10 days); `…/lifecycle/__init__.py` `446effa0…` (scope: Docker/E2B/k8s; runtime-api manages remote) | **MATCH** — a real server-side timer removes the sandbox; scoping is required and now present |
| 2 | `RESERVED_TAG_KEYS` is at line **86**, not 96 (R9-2) | `enterprise` `…/app_conversation/app_conversation_models.py` `7a4a54c0…`: L86 `RESERVED_TAG_KEYS = frozenset(`; L96 `def _validate_caller_tags(...)` | **MATCH** — §11 now cites L86; the only surviving "line 96" mentions are the explicit correction notices |
| 3 | The verified teardown mechanism is **container removal**; physical deletion of the **underlying** workspace data is mount-dependent ⇒ **UNVERIFIED** for host-mounted layouts (R9-3) | `enterprise` `…/sandbox/docker_sandbox_service.py` `00953ee1…` (L698 `container.remove()`; L103-108 `VolumeMount{host_path,container_path,mode}`; L137/L741 `mounts: list[VolumeMount] = Field(default_factory=list)` **empty default**; L573-579 volumes built from `self.mounts`); `…/sandbox/docker_sandbox_spec_service.py` `5401c0b7…` (L92 `OH_CONVERSATIONS_PATH='/workspace/conversations'`; L98 `working_dir='/workspace/project'`) | **MATCH** — container-local vs host-bind-mount distinction is real and correctly stated |
| 4 | The r8-era spec digest `0086b0b0…ff77916` is a **reported value only — NOT INDEPENDENTLY VERIFIED** (R9-4) | r8 proposal not on disk; pinned r8 review `843bb33e…` records only "`1.87.1` / 242 paths" (no hash); r9 review line 210-216 concurs | **MATCH** — the digest is labelled in §1 (L340-341), §2.1 (L515) and §11 (L2661-2666) |
| 5 | The current live Cloud V1 spec is `1.91.0` / 244 paths / sha256 `f0f4d4e9…`, with **no** upload (context) | live `openapi.json` this session: `info.version = 1.91.0`, `paths = 244`, sha256 `f0f4d4e9…`; `multipart` = 0, `binary` = 0, no `attach`/`upload` path | **MATCH** (unchanged from r9) |
| 6 | `AppConversation.repositories.path` is live and described "Absolute path of the folder in the sandbox" (root-read context) | live `openapi.json`: `AppConversation.repositories` (array of `ConversationRepository`); `ConversationRepository.path` description = "Absolute path of the folder in the sandbox" | **MATCH** |
| 7 | `AppConversationInfo.repositories` is a `@computed_field` reading `archiveworkspacepath` via `conversation_repositories` | `enterprise` `…/app_conversation/app_conversation_models.py` `7a4a54c0…` (L65 `ARCHIVE_WORKSPACE_PATH_TAG_KEY='archiveworkspacepath'`; L250-264 `@computed_field repositories` → `conversation_repositories(..., self.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY))`); `…/additional_repositories.py` `a8d0bbe3…` (L106 `path=f'{working_dir}/{folder}'`) | **MATCH** |
| 8 | The tag is server-written at conversation start; `AgentServerContext` has no workspace-path field | `enterprise` `…/live_status_app_conversation_service.py` `9f4f1596…` (L1124 `tags[ARCHIVE_WORKSPACE_PATH_TAG_KEY] = working_dir`); `…/app_conversation_router.py` `c43ed4f7…` (L220-227 `AgentServerContext{conversation,sandbox,sandbox_spec,agent_server_url,session_api_key}`) | **MATCH** |
| 9 | Conversation delete **archives + preserves**; sandbox torn down only when unreferenced | `enterprise` `…/app_conversation_router.py` `c43ed4f7…` (L1050 `_finalize_sandbox_delete`; L1071 `archive_conversation_workspace`; L1085-1091 `count_conversations_by_sandbox_id(...) == 0` ⇒ `delete_sandbox`; L1188 `tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)`; L1189 `asyncio.create_task`); `…/sandbox/remote_sandbox_service.py` `d239ec43…` (L917-924 `delete_sandbox` docstring "Purely sandbox-scoped … Workspace capture is a separate conversation-scoped step"); `software-agent-sdk` `openhands-agent-server/…/agent_server/conversation_service.py` `9e9b3e63…` (L1911 "Safely remove only the conversation directory (workspace is preserved)") | **MATCH** |
| 10 | The Cloud `events/search` store is a **replica** fed by a poll loop only when there is no public URL, else webhooks | `enterprise` `…/sandbox/remote_sandbox_service.py` `d239ec43…` (L1256 `poll_agent_servers`; L1345 `refresh_conversation`; L1438 `event_service.save_event`; L1518-1526 `web_url is None or 'localhost' in web_url`) | **MATCH** |
| 11 | `bb9bbe23…` = **enterprise** `sandbox/sandbox_router.py`; sandbox-server = `07fef71e…` | fetched: enterprise `sandbox_router.py` = `bb9bbe23` (L302 "delete_sandbox is sandbox-scoped (stop + delete) and never archives"); sandbox-server `sandbox_router.py` = `07fef71e` | **MATCH** (R8-3 remains resolved) |
| 12 | `grouped_workspace_dir` produces `{base}/{id_hex}` for any non-`NO_GROUPING` | `enterprise` `…/settings/settings_models.py` `27bae62a…` (L753 `def grouped_workspace_dir`; L765-767 `NO_GROUPING → base`, else `f'{base}/{conversation_id_hex}'`) | **MATCH** |
| 13 | `workspace_archive.archive_workspace` at L334, `store.write` at L516 | `enterprise` `…/sandbox/workspace_archive.py` `202fc8e1…` (L334 `async def archive_workspace`; L516 `store.write, f'{base_path}.{suffix}.manifest.json', manifest`) | **MATCH** |
| 14 | `RemoteSandboxService` subclasses `SandboxService`, not `ManagedSandboxService` | `enterprise` `…/sandbox/remote_sandbox_service.py` `d239ec43…` (L115 `class RemoteSandboxService(SandboxService):`) | **MATCH** |
| 15 | The file_editor reader requires an **absolute** path; terminal `cat` failure is a non-error observation | `software-agent-sdk` `openhands-tools/…/file_editor/editor.py` `a1d735d4…` (L657 `def validate_path`; L666 `if not is_host_absolute_path(path):`); `…/terminal/terminal/terminal_session.py` `72504a4d…` (L241 `_handle_completed_command`, no `is_error`); `openhands-sdk/…/sdk/tool/schema.py` `76b4f42a…` (L417 `is_error: bool = False`); `…/tools/file_editor/utils/constants.py` `a5b3f2bf…` (L1 `MAX_RESPONSE_LEN_CHAR = 16000`); `openhands-sdk/…/sdk/tool/defaults.py` `357f005b…` (`DEFAULT_EXEC_TOOL_NAMES = ("terminal","file_editor","task_tracker")`) | **MATCH** |
| 16 | Cloud `pending-messages` is start-only, durable (SQL commit), 429 above 10 | `enterprise` `…/pending_messages/pending_message_router.py` `520c381d…` (L87-92 max 10 ⇒ 429); `…/pending_message_service.py` `5efde158…` (L64 `delete_messages_for_conversation`) | **MATCH** |
| 17 | `_delete_at_provider` removes the container; provider deletion path is real | `enterprise` `…/sandbox/docker_sandbox_service.py` `00953ee1…` (L698 `container.remove()`); `…/sandbox/managed_sandbox_service.py` `c1286e09…` (L156 `delete_sandbox`, L183 `_delete_at_provider`) | **MATCH** |
| 18 | Lifecycle wired into the worker as a blueprint | `enterprise` `…/worker/app.py` `a287ec5a…` (L6 `from …sandbox.lifecycle.tasks import lifecycle`; L33 `app.add_tasks_from(lifecycle, namespace='sandbox_lifecycle')`) | **MATCH** |

**All eighteen central claims I re-checked independently match the pinned source.** No fabricated
hash, line, symbol, or semantic was found.

## 4. Remediation mapping — all four R9 findings independently re-verified

| # | R9 finding | Required change (R9 §9) | r10 location(s) I verified | Verdict |
| --- | --- | --- | --- | --- |
| **R9-1** | MEDIUM, blocking: narrow the absolute "no timer deletes C2 / C2 is never timer-deleted / the only server-side clock is `expires_at`" wording in §5.9, §5.10.2, §5.10.3 (invariant + case 4), §8.4, §12 Q18 to "no **operation-scoped** (`expires_at`) timer" | §5.9 (L1076-1080 "never reclaimed by the **operation's** timer … a **separate** infrastructure timer … may still remove the sandbox **and its workspace**"); §5.10.1 C2 row (L1229 "**NEVER at `expires_at`** … the infrastructure lifecycle timer above is a **separate** clock"); §5.10.2 (L1308-1315 "no **operation-scoped** timer … not a claim that **no** server-side timer can ever remove C2"); §5.10.3 invariant (L1346-1353 "**no operation-scoped (`expires_at`) timer ever deletes C2** … binds the **application** … **cannot** prevent that external infrastructure deletion") + case 4 (L1337 "cannot be invalidated by the **operation's** timer"); §8.4 (L2456-2463 "never reclaimed by the **operation's** timer"); §12 Q18 (L3008-3012 "not deleted by the **operation's** timer"); §6 T-24 (L2131); §11(f) (L2883-2885); §14→§13 r10 row (L3071) | **RESOLVED.** Every absolute statement is now scoped; the two timer kinds are explicitly named and distinguished, and the invariant now binds the **application** without over-claiming the ability to stop external deletion |
| **R9-2** | LOW: fix `RESERVED_TAG_KEYS` line in §11 (86, not 96) | §11 (L2802 "line **86** — corrected r10/R9-2; the former 'line 96' was wrong: line 96 is `def _validate_caller_tags(...)`"); §5.15.6 (L2020) already cited 86 | **RESOLVED.** Independently confirmed L86 = constant, L96 = validator |
| **R9-3** | LOW, optional: add the container-local/mount caveat to §5.10.4's teardown sentence | §5.10.4 (L1380-1398) — explicit four-way separation: (i) container removal (verified), (ii) mounted data (layout-dependent), (iii) physical deletion of underlying files (**UNVERIFIED / SOURCE REQUIRED** for host-mounted layouts), (iv) external storage lifecycle; plus §5.10.1 C2 row (L1229), §5.14.2 step 7 (L1746-1750), §11(f) (L2884-2885) | **RESOLVED.** The mount-dependence is real (empty `mounts` default; in-container paths) and correctly stated |
| **R9-4** | INFO, optional: mark or drop the unverifiable r8-spec hash in §2.1/§2.2/§11 | §1 (L340-341), §2.1 (L515), §11 (L2661-2666) label the digest `0086b0b0…ff77916` as "**reported value only — NOT INDEPENDENTLY VERIFIED**" | **RESOLVED** (with a minor residual — see N10-3) |

**Preservation check.** All P0 invariants I1–I15 present (15 rows); threat rows T-01…T-25 present (25
rows); requirements U-1…U-12 present (12 rows); per-copy lifecycle C1–C5 present (5 rows); §9
acceptance criteria 1–11 (incl. 7b/7c) unchanged in substance; §12 Q1…Q22 present. **No security
requirement, threat-model mitigation, or P0 invariant was weakened, removed, or relaxed** by r10.

## 5. Adversarial findings (new)

### N10-1 (LOW) — same fact cited at two different line numbers (`editor.py` missing-path rejection)

The proposal cites the file_editor `validate_path` missing-path rejection for non-`create` commands at
**two different lines** for the **same** fact:

- §5.15.5 (L1969): "*a missing path is also rejected for non-`create` commands (**line 691**)*".
- §11 (L2725): "*rejects a missing path for non-`create` commands (**line 693**)*".

Ground truth (independently fetched, `openhands-tools/…/tools/file_editor/editor.py` `a1d735d4…`): the
guard is `if command != "create" and not path.exists():` at **line 689**, with its
`raise EditorToolParameterInvalidError(` at **line 690**; line 691 is the `"path",` argument and line
693 is the message string. So both cited numbers fall *inside* the same raise block (690-694) and are
each defensible, but they **disagree with each other** for the same fact — exactly the class of defect
R8-3/R9-2 were raised for. (The `validate_path` definition at L657 and the absolute-path check at L666
are both correct.)

*Suggested fix:* cite the guard line **689** (or "689-694") in **both** places. Cosmetic; no security
impact.

### N10-2 (LOW) — `conversation_service.py` attributed to the wrong repository in §11

In the §11 source list, the "agent-server delete **preserves** the workspace" citation appears under
the **`OpenHands/enterprise`** bullet (which begins at L2739):

> "*The **agent-server** delete **preserves** the workspace: `conversation_service.py` (sha256
> `9e9b3e63…`, line 1911) — 'Safely remove only the conversation directory (**workspace is
> preserved**)'*" (L2783-2784).

The file with sha256 `9e9b3e63` is the **software-agent-sdk** agent-server file
`openhands-agent-server/openhands/agent_server/conversation_service.py` (verified: L1911 matches), **not**
an enterprise file — `OpenHands/enterprise` has no `conversation_service.py` (all candidate paths 404)
and no `agent_server` package under `openhands/`. So the citation is **correct in content but misplaced
in repository attribution** in the §11 list.

*Suggested fix:* move (or annotate) the `conversation_service.py` `9e9b3e63…` citation into the
`OpenHands/software-agent-sdk` bullet. Documentation-only; no security impact.

### N10-3 (INFO) — the historical r8 version string is still called "r8 evidence" in §2.2

R9-4 asked to mark or drop the unverifiable r8 digest in §2.1/§2.2/§11. The digest (`0086b0b0…`) is now
labelled in §1, §2.1 and §11 — but §2.2 (L533, L538, L605) still writes "*r8 evidence `1.87.1`*" without
the "NOT INDEPENDENTLY VERIFIED" qualifier. This is **less severe** than the hash case because §2.2
cites only the version string `1.87.1` (which the pinned r8 review *does* record, at lines 91/263) and
never repeats the unverifiable hash. It is a residual labelling inconsistency, not an evidence defect.

*Suggested fix (optional):* in §2.2 use "*r8-reported `1.87.1` (not independently verified; see §11)*".

## 6. State-model, lifecycle, and crash-window re-check (independent)

| Item | r10 claim | Independent check | Verdict |
| --- | --- | --- | --- |
| Observable states | `stored \| delivered \| rejected \| failed \| expired`; `accepted` internal-only; no `uploading` | §5.5 (L913-921) and §5.9 (L1056-1074) agree; no JSON example returns `accepted`/`uploading` | **CONSISTENT** |
| Operation timer | `expires_at` reclaims **C1/C3 only**; **never** C2 | §5.9 + §5.10.1 + §5.10.2 + §5.10.3 + §5.14.2 step 7 + §8.4 + §6 T-19/T-24 + §8.1 I12 + §12 Q18 agree | **CONSISTENT** |
| Infrastructure timer | Enterprise sandbox lifecycle (`delete_after_seconds`) **may** remove sandbox **and its workspace** (managed backends); **delegated** for Cloud/runtime-api; **not** an F7 signal | §5.10.1 + §5.10.4 + §5.14.2 step 7 + §6 T-24 + §11(f) + §13 agree; explicitly **distinct** from `expires_at` | **CONSISTENT** |
| C2 lifetime | never reclaimed by `expires_at` or conversation archive/delete; only F7 (unmodeled) or **physical removal** (teardown) | §5.10.0.1 + §5.10.1 + §5.10.4 + §5.14.2 step 7 + §5.14.4 + §6 T-19/T-24 + §8.1 I12 + §9 7b + §11 + Q18 consistent | **CONSISTENT** |
| Teardown mechanism | verified = **container removal**; underlying workspace deletion **UNVERIFIED** for host-mounted layouts | §5.10.1 + §5.10.4 + §5.14.2 step 7 + §11(f) agree | **CONSISTENT** |
| Root provenance | tag→root **read** existing/shipped; **identity + write-authorization binding** new; fail closed | §5.14.2 step 3 + §5.15.5 + §5.15.6 + U-12 + §6 T-25 + §8.1 I15 + §7.0/§7.1/§7.4 + §12 Q22 consistent | **CONSISTENT** |
| Live-spec identifier | `1.91.0`, 244, `f0f4d4e9…` | §1 + §2.1 + §11 agree; re-verified live this session; historical `1.87.1` only as reported (N10-3) | **CONSISTENT** |
| Threat table | T-19 unchanged in substance; T-24 scoped (two-timer distinction); T-25 unchanged | §6 rows match §5.10/§5.15.6 | **CONSISTENT** |
| Crash windows (§8.3) / races (§5.10.3) | no copy needed for reconciliation or active use is deleted | §5.10.3 cases 1–11 internally consistent; §8.3 windows 1–7 unchanged in substance | **CONSISTENT** |
| L↔F cross-map (§5.10.0.1) | L6↔F6b, L7↔F7 only; others "none" | table matches §5.10.0/§5.14.0 | **CONSISTENT** |

**Exhaustive absolute-phrasing scan.** I grepped the full text for `no timer deletes C2`, `C2 is never
timer`, `only server-side clock`, `only clock that exists server-side`, `timer-deleted`,
`timer-reclaimed`, `never timer-deleted`, and every `timer` occurrence. The **only** surviving absolute
phrasings are inside the two **explicit correction notices** (L356, L3071) that *quote* the withdrawn
wording to explain the fix. No unscoped absolute claim remains in the normative text.

## 7. What r10 does **not** claim (fairness note)

- It does **not** claim U-3 exists, nor that a trusted non-agent issuer exists.
- It does **not** claim the **Cloud/runtime-api** sandbox-lifecycle bound is known (delegated/external).
- It does **not** claim the managed-backend lifecycle is an **F7 end-of-use** signal, nor that it proves
  any particular conversation reached a safe terminal state.
- It does **not** claim the application can **prevent** external infrastructure deletion.
- It does **not** claim `container.remove()` establishes **universal** physical deletion of the
  underlying workspace data.
- It does **not** claim the Cloud root read **authorizes** or **identity-binds** the write.
- It does **not** claim a **bounded** retention policy for C2 exists for the Cloud path (Q18 open).
- It does **not** claim the historical r8 digest `0086b0b0…` is verified.
- It does **not** claim P0 is complete; the capability still requires **upstream work + a maintainer
  decision**.

## 8. Unverified / limitations of this review (honest list)

1. The **r8 proposal** is not on disk; the r8→r10 lineage was assessed from the r8/r9 reviews' verbatim
   quotes and the r10 text, not from the r8 file itself.
2. The **r8-spec hash** `0086b0b0…ff77916` could not be independently confirmed (it is now correctly
   labelled unverified in the proposal; → N10-3 concerns only the §2.2 version-string label).
3. I did **not** run any code or test (P0 is a proposal; no capability exists). No claim here rests on
   an executed test.
4. Whether the modeled teardown removes the **workspace directory** (vs only the container) remains
   **unverified** for host-mounted layouts — the proposal now states this correctly (R9-3).
5. I did not contact any maintainer and made no production call. The live spec was fetched read-only.
6. This review covers **r10 only**; it does not re-adjudicate the closed r6/r7 findings except where
   r10 touches them.
7. The pinned `enterprise`/`software-agent-sdk`/`sandbox-server` SHAs are **not** the current `main`
   heads (they moved since: SDK `main` = `10be259c…`, enterprise `main` = `7c1e5537…` at review time).
   This is **expected** — the proposal deliberately pins revisions; I re-verified the claims at the
   **pinned** revisions, which is the correct basis.

## 9. Verdict and required changes

**Verdict: `PASS_WITH_NOTES`.**

The four R9 findings are **independently confirmed resolved** in the r10 text, with the C2 timer claims
scoped consistently across every normative section, the `RESERVED_TAG_KEYS` citation corrected to line
86, the modeled teardown qualified as container removal (physical workspace deletion **UNVERIFIED** for
host-mounted layouts), and the historical r8 spec digest labelled **NOT INDEPENDENTLY VERIFIED** —
**without weakening any security requirement, threat-model mitigation, or P0 invariant** (fail-closed
rules preserved; no cleanup primitive invented; prior findings R6-1…R6-5, N-1…N-5, R7-1…R7-4,
R8-1…R8-4 remain closed).

Recommended (documentation-only, **non-blocking**, for the next revision):

1. **N10-1 (LOW):** make the `editor.py` missing-path citation consistent — cite line **689** (or
   "689-694") in both §5.15.5 and §11.
2. **N10-2 (LOW):** move/annotate the `conversation_service.py` `9e9b3e63…` citation into the
   `OpenHands/software-agent-sdk` bullet in §11.
3. **N10-3 (INFO, optional):** in §2.2, qualify the "*r8 evidence `1.87.1`*" mentions as reported-only.

If items 1–2 are folded in, the document is ready to move to `PASS` for the citation axis; the residual
**substantive** uncertainties (U-3/issuer, U-10, U-11, U-12-binding, C2 retention bound, Cloud/runtime-api
teardown) remain honestly open and are **owner decisions**, not review defects.

---

**Independence statement.** This review was authored by a fresh-context reviewer that is not the author
of the proposal, the r10 self-review, or any earlier review/self-review in this series. All artifacts
were read-only; the only file created is this one. No secrets, credentials, or production calls were
used.
