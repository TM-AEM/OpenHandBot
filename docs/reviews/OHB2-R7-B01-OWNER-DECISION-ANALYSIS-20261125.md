# OHB2-R7-B01 — Owner Decision Analysis (2026-11-25)

**Task ID:** `OHB2-R7-B01-OWNER-DECISION-ANALYSIS`
**Scope:** evidence-based analysis only. No implementation.
**D-01 classification:** `OWNER_DECISION_REQUIRED`
**D-02 classification:** `OWNER_DECISION_REQUIRED`

This task did **not** modify code, schema, resolver behavior, or the existing
conversation-wide review architecture. It made no OpenHands, GitHub, provider, Telegram,
or other live/external call; did not start a worker; and did not commit, push, open a PR,
merge, deploy, or release.

The safe resolver remains unchanged. R7 live validation has not started, and R8 has not
started.

---

## 1. Executive answer

- **D-01:** No existing source is authenticated, immutable, and stable enough to be
  called authoritative for *all* OpenHands conversations. `selected_repository` is
  user-supplied/mutable OpenHands metadata; local `creation_jobs.repo` is durable but
  owner-supplied, name-only, and only exists for bot-created conversations; `watched`
  has no repository; previous review rows are historical hints, not identity.
  **D-01 remains `OWNER_DECISION_REQUIRED`.**
- **D-02:** No automatic PR-discovery source exists in the current codebase. OpenHands
  `pr_number` is documented as a field but its population semantics are unverified and
  the bot never sends it; all 20 previously observed org conversations had an empty
  list. The GitHub client can fetch a PR by number but cannot list/search PRs. No local
  table stores a conversation→PR candidate. **D-02 remains `OWNER_DECISION_REQUIRED`.**
- **Schema:** Reading either candidate needs no schema change. Durable stable repository
  identity, source/verification provenance, or persisted PR candidates would require an
  additive migration. This task made no schema change.
- **Safe canary path, not a decision:** If the owner wants a bounded canary without
  claiming automatic discovery, the least-trusting option is local `creation_jobs.repo`
  for bot-created conversations (D-01), plus an explicitly owner-supplied PR list (D-02).
  This is a recommendation for a canary only; it is **not** approval of an authoritative
  source and does not close B-01.

---

## 2. Baseline Git state

Recorded before writing this report:

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Tracked files | 569 |
| Modified tracked files | 12 |
| Untracked entries | 52 |
| Python | 3.13.15 in `.venv` |
| pytest | 9.0.3 |
| Node | 24.22.2 |

The working tree already contained the R1–R7 implementation, resolver, tests, and
historical reports before this analysis. They were preserved. No live canonical GitHub
`main` check was made; local `main` and `origin/main` both point to the baseline SHA.

### Final state for this task

- Added: `docs/reviews/OHB2-R7-B01-OWNER-DECISION-ANALYSIS-20261125.md`.
- Appended: `.agent/PROGRESS.md`.
- Final working tree: 12 modified tracked files (pre-existing; includes
  `.agent/PROGRESS.md`), 53 untracked entries (the previous 52 plus this report).
- No code, schema, resolver, test, or configuration file was changed.
- No commit/push/PR/merge/deploy/release.

---

## 3. Actual code paths inspected

The analysis was based on the current checkout, not only on previous reports.

| Area | Actual paths / evidence |
|---|---|
| OpenHands conversation retrieval | `bot/openhands_client.py:79-104` (`search_conversations`, `get_conversations`), `:587-630` (`collect_conversations`) |
| OpenHands conversation creation/update | `bot/openhands_client.py:376-397` (`update_conversation_repository`, `start_conversation`) |
| OpenHands owner identity | `bot/openhands_client.py:287-290` (`get_current_user`), `bot/files.py:258-266` (`created_by_user_id` check) |
| Repository selection UI | `bot/handlers.py:3654-3720` (`search_repositories`, `pick_repo`), `bot/web/services.py:1401-1445` (`list_repositories`, `create_chat`) |
| Local creation persistence | `bot/db.py:758-771` (`CreationJob`), `:1200-1215` (`creation_jobs` schema), `:5525-5600` (`add_creation_job`), `:5813-5830` (`finish_creation_done`), `bot/outbox.py:1162-1303` |
| Watch/subscription persistence | `bot/db.py:676-694` (`Watched`), `:1155-1164` (`watched` schema), `:4074-4086` (`get_watched`) |
| Existing PR display logic | `bot/messages.py:92-101` (`pr_url`); callers at `bot/handlers.py:1886` and `bot/web/services.py:693` |
| GitHub read primitives | `bot/review/github.py:368-390` (branch list/get/verify), `:410-424` (`get_repository`, `get_pull_request`), `:427-485` (compare), `:489-580` (Actions runs/jobs) |
| Resolver | `bot/review/resolver.py:137-203` (resolve flow), `:220-263` (link/repository), `:266-367` (PR/branch/compare), `:378-445` (reservation) |
| Collector | `bot/review/collector.py:40-105` (consumes a supplied `AutoReviewMembership`; no discovery) |
| Worker | `bot/review/worker.py:122-136` (reads persisted memberships; no discovery) |
| Review schema | `bot/db.py:1398-1665` (`auto_reviews`, `auto_review_memberships`, pending memberships, evidence, reports) |
| Immutability triggers | `bot/db.py:2022-2031` (membership no-update/no-delete) |
| Reservation / conflict logic | `bot/db.py:8110-8330`; pending observation at `:8335-8375` |
| Runtime activation | `bot/app.py:105-117`, `:282-329` (starts outbox/creation/completion/watcher/notifier only; no review worker) |
| Documented OpenHands fields | `docs/API_NOTES.md:10-15`, `:38-41`, `:71-72` |
| Prior evidence | `docs/reviews/OHB2-AUTO-REVIEW-R0E-DESIGN-CORRECTION-20261124.md:79-80`, E-12/E-14; `docs/reviews/OHB2-AUTO-REVIEW-R7-READINESS-REPORT-20261125.md:104-111` |

---

## 4. D-01 — Conversation → repository identity

### 4.1 Actual candidate sources

#### A. OpenHands `selected_repository` / `selected_branch`

- Origin: owner/user selects a repository in the bot or OpenHands UI; the bot sends
  `selected_repository` on `POST /app-conversations` and `PATCH /app-conversations/{id}`
  (`bot/openhands_client.py:376-397`). The field is returned by
  `GET /app-conversations` and `/app-conversations/search`
  (`docs/API_NOTES.md:10-15`; `bot/openhands_client.py:79-104`).
- Authenticated? The OpenHands API call is authenticated; the repository value is
  user-supplied. `created_by_user_id` authenticates conversation ownership
  (`bot/files.py:258-266`) but does not authenticate the repository field.
- Immutable? No. It can be changed by `PATCH` and potentially through OpenHands UI;
  there is no local history.
- Spoofable? Yes: it is a name string; a caller can select any `owner/repo`; no numeric
  ID or signed binding.
- Restart/retry? OpenHands persists it; the bot does not persist it locally except in
  `creation_jobs.repo` for bot-created chats. A fresh `get_conversations` call re-reads
  the current value.
- Rename/transfer? No stable identity: the field is a name; rename/transfer changes or
  invalidates the name, and deletion/recreation can reuse a name.
- Same-name distinction? No numeric ID; cannot distinguish a reused name.
- Stable GitHub ID? Only after calling `GitHubClient.get_repository()`; the field itself
  has no ID.
- Migration? No schema change to read; persisting a verified ID/provenance needs new
  storage.

#### B. Local `creation_jobs.repo` + `conversation_id`

- Origin: the owner selects a repository in the bot/Mini App; `add_creation_job`
  persists `chat_id`, `repo`, and text before `POST /app-conversations`
  (`bot/db.py:5525-5600`; `bot/handlers.py:3750`; `bot/web/services.py:1433`).
  `_finish_creation` writes the resulting `conversation_id` on the same row
  (`bot/db.py:5813-5830`; `bot/outbox.py:1288-1303`).
- Authenticated? The row is owner-scoped by `chat_id`; `repo` is still a user-supplied
  name. It is not authenticated by OpenHands or GitHub.
- Immutable? `repo` is set at creation and has no update method. `conversation_id` is
  written by a CAS transition. The row is not deleted by `delete_conversation` (it is
  marked/updated), so it is durable. Direct DB/admin edits are possible.
- Spoofable/changed? The Mini App can submit any valid `owner/repo` shape; GitHub
  verification is required. OpenHands can later change `selected_repository` via PATCH;
  the local row then becomes stale unless cross-checked.
- Restart/retry? Yes: durable SQLite rows; creation recovery is idempotent and
  `client_ref` prevents duplicate jobs.
- Rename/transfer? Name only; no numeric ID. A rename makes the stored name stale;
  adding a numeric ID/verification record would be needed for stable identity.
- Same-name distinction? No current numeric ID; no.
- Stable GitHub ID? Only after GitHub lookup; no current column.
- Scope: only bot-created conversations. Conversations created outside the bot have no
  `creation_jobs` row.
- Migration? Existing `repo`/`conversation_id` support a read-only candidate. Durable
  stable ID/provenance requires an additive migration.

#### C. Explicit owner/server mapping

- Origin: owner config, admin action, or a new local table. **Not implemented.**
- Authenticated? Yes, if only the owner can write it.
- Immutable? Can be append-only/owner-controlled; not yet designed.
- Restart/retry? If persisted; no current mechanism.
- Rename/transfer? Can store numeric repository ID; yes, if designed that way.
- Same-name distinction? Yes with numeric ID.
- Stable GitHub ID? Yes, if stored and verified.
- Migration? New table/columns; additive migration required.
- Scope: can cover any conversation, including external ones; manual/owner-driven, not
  automatic discovery.

#### D. `watched.chat_id` only

- Origin: bot watch/subscription (`bot/db.py:676-694`, `:1155-1164`).
- It contains no repository. It is authorization context only. It cannot answer D-01.

#### E. Previous review cycle / previous membership

- `auto_reviews` and `auto_review_memberships` contain a repository ID/name, PR, and SHA
  after a cycle has been reserved (`bot/db.py:1426-1548`).
- This is historical evidence, not a source: it may be stale, belongs to a prior cycle,
  and cannot establish the current repository after reassignment. No code currently uses
  it as a conversation→repository resolver.

#### F. Commit trailer, prompt text, PR URL, branch-name heuristic

- No parser or convention exists in the code.
- These are not approved identity sources; a commit-trailer convention is explicitly
  out of scope and must not be introduced silently.
- Branch names are not PR or repository identity; `list_agent_branches()` only filters
  `agent/` branches (`bot/review/github.py:368-390`).

### 4.2 D-01 comparison

| Candidate | Origin / authentication | Immutable? | Restart | Rename/transfer | Same-name distinction | Stable GitHub ID | Supported now | Migration |
|---|---|---|---|---|---|---|---|---|
| A. OpenHands `selected_repository` | OpenHands API; owner/user supplied; `created_by_user_id` authenticates owner only | No; mutable via PATCH/UI | Yes in OpenHands; not local | No; name-only | No | Only after GitHub lookup | Yes, read-only | None to read; additive to persist |
| B. Local `creation_jobs.repo` + `conversation_id` | Local SQLite; owner-selected name; owner-scoped `chat_id` | `repo` fixed at creation; `conversation_id` CAS; direct DB edits possible | Yes | No; name-only | No | Only after GitHub lookup | Yes, for bot-created chats | Existing fields; additive for ID/provenance |
| C. Explicit owner/server mapping | New owner/admin record | Yes if designed append-only | Yes if persisted | Yes with numeric ID | Yes with numeric ID | Yes | No | New table/columns |
| D. `watched.chat_id` | Local authorization | N/A | Yes | N/A | N/A | N/A | Yes but no repository | None |
| E. Prior review row | Historical local DB | Snapshot immutable after reservation | Yes | Historical only | Yes historically | Yes historically | Not a resolver source | None |
| F. Trailer/prompt/URL/branch | Not implemented / untrusted | N/A | N/A | N/A | N/A | N/A | No | New convention (not approved) |

### 4.3 D-01 findings

1. **No existing source is authoritative for all conversations.** A and B are both
   name-based, user-supplied candidates. A is mutable by OpenHands; B is durable but
   only covers bot-created chats. Neither is a signed repository binding.
2. **`selected_repository` is available but not identity.** It is useful as a candidate
   only after GitHub numeric-ID verification; it cannot distinguish rename/reuse by
   itself.
3. **Local creation context is the strongest existing local record.** It is owner-scoped,
   durable, and has an exact `conversation_id`, but it still needs GitHub verification
   and a stable ID record. It cannot cover external conversations.
4. **`watched.chat_id` is authorization, not identity.** It must never be promoted to a
   repository source.
5. **A new explicit owner mapping is the only existing design that can cover all
   conversations with an owner-controlled numeric ID.** It is not implemented and needs
   a schema/config decision.

### 4.4 D-01 recommendation and classification

**Recommendation:** retain **`D-01 = OWNER_DECISION_REQUIRED`** as the authoritative
decision. Do not approve A or B as authority based on current evidence.

If the owner wants a bounded canary before choosing a durable authority, the least-risk
candidate is **B (local `creation_jobs.repo` + `conversation_id`)** for bot-created
conversations, with all of the following:

- require `status='done'`, matching `conversation_id`, and owner-scoped `chat_id`;
- verify the repository through `GitHubClient.get_repository()` and use its numeric ID;
- cross-check the current OpenHands `selected_repository` when present; reject mismatch;
- reject missing/empty/name-only ambiguity and do not fall back to `selected_repository`
  alone;
- do not claim this covers externally created conversations;
- record this as a canary, not as closure of D-01.

The owner must still decide whether to authorize B for canary, A as candidate only, or
C as the authoritative mapping.

---

## 5. D-02 — PR candidate discovery

### 5.1 Actual candidate sources

#### A. OpenHands `pr_number` metadata

- Origin: OpenHands `AppConversation` field; documented as an array-shaped field
  (`docs/API_NOTES.md:71-72`; R0E E-12). `bot/messages.py:92-101` treats it as a scalar
  or list for a display link only.
- Is it implemented for review? No. `OpenHandsClient.start_conversation()` sends only
  `selected_repository`/`selected_branch`; it does not send `pr_number`
  (`bot/openhands_client.py:386-397`).
- Population evidence: all 20 org conversations observed in R0E had `pr_number=[]`;
  no resolver-created conversation with non-empty metadata was observed
  (`OHB2-AUTO-REVIEW-R0E-DESIGN-CORRECTION-20261124.md:79-80`, E-10).
- Authoritative? No. The field's population semantics are unverified. Sending it
  ourselves would make it user-supplied, not proof.
- Multiple PRs? The documented shape can be an array; current display code selects the
  first element (`bot/messages.py:95-99`). No normalizer rejects multiple/empty/malformed
  values for review.
- Closed/merged/fork/cross-repo? A number alone says nothing; GitHub `get_pull_request`
  can check state, base/head repo, and fork. The resolver rejects closed/merged and forks.
- Bound to repository ID? No; it must be paired with the verified repository.
- Exact head SHA? No; GitHub PR lookup is required.
- Branch movement? No; resolver/collector branch checks are required.
- Pagination/incomplete? Conversation search is paginated with a `truncated` flag
  (`bot/openhands_client.py:587-630`); the per-conversation array has no completeness
  guarantee. There is no review consumer.
- Restart? OpenHands persists the field; the bot does not persist it locally.
- Supported now? Display only; not a review source.

#### B. Explicit owner/server PR list

- Origin: owner/harness supplies PR numbers to `ConversationMembershipResolver.resolve()`
  (`bot/review/resolver.py:152-203`). The resolver validates positive integers, rejects
  duplicates, and fetches each PR through GitHub.
- Authoritative? Explicit owner input; not automatic discovery.
- Multiple PRs? Yes; resolver accepts a tuple/list and returns sorted memberships.
- Closed/merged/fork/cross-repo? Rejected by `_validate_pull_request`
  (`bot/review/resolver.py:282-310`).
- Bound to repository ID? Yes, after `get_repository`/`get_pull_request`.
- Exact SHA? Yes, from the PR and compare checks.
- Branch movement? Verified before/after; PR re-read (`resolver.py:312-367`).
- Pagination/incomplete? Not applicable to an explicit list; the caller must supply a
  complete list or accept a partial scope.
- Restart? Only if the owner/harness persists the list; no current persistence.
- Supported now? Resolver API only; no source adapter, no persistence, no automatic
  discovery.

#### C. GitHub read-only PR discovery

- Current client has `get_pull_request(repository, number)` only
  (`bot/review/github.py:417-424`). It has branch list/get/verify and Actions runs/jobs,
  but no `GET /repos/{repo}/pulls` list/search and no commit→PR lookup.
- `list_agent_branches()` only lists branches whose names start with `agent/`
  (`github.py:368-390`); a branch is not a PR.
- Adding discovery would be new code and a new policy: list open/closed/all PRs, filter
  by head/base repository, handle pagination/truncation, and define what to do with
  multiple PRs. Branch names are untrusted and cannot be used as the sole correlation.
- No live GitHub call was made, so no API behavior is claimed.

#### D. Existing local persistence

- `creation_jobs` stores `repo` and `conversation_id` but no PR number
  (`bot/db.py:1200-1215`, `:758-771`).
- `watched` stores conversation/title/state/chat, no PR.
- `outbox` stores prompts/messages, no PR.
- `auto_reviews` has PR fields only after a caller supplies memberships
  (`bot/db.py:1426-1548`, `:8110-8330`).
- `auto_review_pending_memberships` can store observed PRs, but there is no producer
  that discovers them (`bot/db.py:1533-1548`; no consumer in `bot/review` except the
  next reservation).
- No table stores a conversation→PR candidate.

#### E. Branch-name heuristic

- `list_agent_branches()` filters `agent/` but does not map a branch to a PR.
- Branch names are mutable and not unique to a PR; this is not safe without an approved
  naming/correlation rule.

#### F. Commit trailer / free-form text / PR URL

- Not implemented. A trailer would be a new identity convention and is explicitly
  outside this task. Free-form text/URLs are user-controlled and cannot be authoritative.

#### G. OpenHands resolver

- Documentation mentions a resolver workflow, but this repository has no implementation
  or live evidence. R0E B-01 remains `UNVERIFIED`: no real conversation with non-empty
  `pr_number` and matching PR/SHA/CI. A documented resolver trigger does not prove
  `pr_number` population.

### 5.2 D-02 comparison

| Candidate | Implemented? | Authoritative? | Multiple PRs | Closed/merged/fork detection | Bound to repo ID | Exact head SHA | Branch movement | Pagination/incomplete | Restart |
|---|---|---|---|---|---|---|---|---|---|
| A. OpenHands `pr_number` | Display only | No; population unverified | Array-shaped, unnormalized | Only after GitHub lookup | No; needs verified repo | No; GitHub lookup | No; resolver checks | No review consumer | OpenHands only; not local |
| B. Explicit owner list | Resolver API | Explicit owner input; not discovery | Yes | Yes via resolver | Yes | Yes | Yes | Caller must supply complete list | Only if caller persists |
| C. GitHub discovery | No | Could be made safe only with a new approved rule | Yes, if designed | Yes via GitHub | Yes after repo resolution | Yes via PR | Yes via resolver | Must be designed | Not applicable |
| D. Local persistence | No PR source | No | N/A | N/A | N/A | N/A | N/A | N/A | Durable rows exist but no PR |
| E. Branch heuristic | Branch list only | No | N/A | N/A | N/A | No | No | Branch pagination only | N/A |
| F. Trailer/text/URL | No | No | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

### 5.3 D-02 findings

1. **No automatic PR-discovery source is implemented.** The resolver requires an
   explicit PR list; the collector/worker consume a pre-existing membership.
2. **OpenHands `pr_number` is not proven.** It is a documented field shape, but the bot
   never sends it, all observed conversations had an empty list, and no real resolver
   population evidence exists.
3. **The current display helper is not a source.** `pr_url()` reads a field and picks
   the first value for a link; it does not normalize, verify, or persist a candidate.
4. **GitHub discovery is absent.** Adding it would require a new API method, pagination/
   truncation handling, multiple-PR policy, and an approved correlation rule.
5. **Explicit owner input is the only safe canary input.** It is not automatic
   discovery and does not close D-02.

### 5.4 D-02 recommendation and classification

**Recommendation:** retain **`D-02 = OWNER_DECISION_REQUIRED`** for automatic discovery.

For a controlled canary, the only safe input is an **explicit owner-supplied PR list**
passed to the existing resolver. That is not a discovery mechanism and must be labelled
as such. Do not use OpenHands `pr_number` or branch names automatically without an
owner-approved trust rule and tests.

---

## 6. Provenance and database implications

### 6.1 Current schema facts

- `auto_reviews` stores `conversation_id`, `repository_id`, `repository_full_name`,
  `pr_number`, `branch`, `base_sha`, `head_sha`, `scope`, `scope_policy`, provider
  snapshot, lifecycle, and delivery fields (`bot/db.py:1426-1508`).
- `auto_review_memberships` stores the immutable PR snapshot
  (`repository_id`, `repository_full_name`, `pr_number`, `branch`, `base_sha`,
  `head_sha`, `created_at`) and has no-update/no-delete triggers
  (`bot/db.py:1510-1527`, `:2022-2031`).
- `auto_review_pending_memberships` stores observed PRs with `observed_at`, but has no
  source/verification fields and no current producer (`bot/db.py:1533-1548`).
- `creation_jobs` stores `repo` and `conversation_id`, but no repository ID, source,
  or verification timestamp (`bot/db.py:1200-1215`).
- `watched` stores no repository (`bot/db.py:1155-1164`).
- No table currently stores a conversation→repository binding or a conversation→PR
  candidate before a review reservation.
- The resolver's `MembershipProvenance` is in-memory only; `reserve_conversation_review`
  does not accept/persist source or `verified_at` (`bot/review/resolver.py:108-120`,
  `:378-445`; `bot/db.py:8110-8330`).

### 6.2 Fields needed if provenance is persisted

| Field | Purpose | Immutable? |
|---|---|---|
| `conversation_id` | Stable local/OpenHands conversation key | Binding key |
| `chat_id` | Owner authorization context; not repository identity | Snapshot |
| `repository_id` | Immutable GitHub identity | Yes |
| `repository_full_name` | Display snapshot at verification time | Yes per observation |
| `source` | `local_creation_job` / `openhands_selected_repository` / `owner_mapping` / `explicit_owner_list` | Yes |
| `source_version` | Adapter/rule version if applicable | Yes |
| `observed_at` | When the candidate was read | Yes |
| `verified_at` | When GitHub verification completed | Yes |
| `pr_number` | PR candidate/membership | Yes per snapshot |
| `head_ref` | PR head branch | Yes per snapshot |
| `base_sha` / `head_sha` | Exact reviewed commits | Yes per snapshot |
| `verification_result` | Accepted/rejected reason code | Yes |
| `review_id` / membership link | Binding to the cycle | Yes |

Do not store API tokens, raw provider responses, or free-form conversation text.

### 6.3 Stale/conflicting provenance rules

- **Repository ID mismatch** → reject; never treat a same-name repository as the same
  identity.
- **Same ID, different name** → current resolver rejects as
  `repository_rename_ambiguous`; owner decision D-05 is still open. If later approved,
  retain the old full name as a snapshot and record the new name separately.
- **OpenHands `selected_repository` differs from local creation context** → reject; do
  not silently choose one.
- **PR head SHA changed** → reject/conflict; start a new cycle; never mutate the active
  membership.
- **PR closed/merged/fork/cross-repo** → reject.
- **Duplicate `(repository_id, pr_number)`** → reject.
- **Stale pending observation** → do not merge into an active cycle; keep it pending or
  reject on conflict.
- **Partial/incomplete API response** → fail closed; no empty success.
- **Restart/retry** → re-read the source and re-verify GitHub; a durable provenance row
  is evidence of a past observation, not a license to skip current verification.

### 6.4 Migration implications by option

| Option | Schema change needed now? | Additive migration if durable provenance/ID is required |
|---|---|---|
| D-01 A (`selected_repository`) | No to read; no local persistence | Yes for stable ID/source/verified_at |
| D-01 B (`creation_jobs.repo`) | No to read existing rows | Yes for `repository_id` and verification metadata, or a new binding table |
| D-01 C (owner mapping) | Yes | New table/columns |
| D-02 A (`pr_number`) | No to read; no persistence | Yes for candidate/provenance persistence |
| D-02 B (explicit list) | No if ephemeral | Yes if owner list/provenance must survive restart |
| D-02 C (GitHub discovery) | No to add a read method | Yes if candidates are persisted |

### 6.5 Conversation-wide scope and immutability

No option changes the approved conversation-wide scope:

- `scope='conversation'` and `scope_policy='conversation-wide'` remain the only review
  cycle policy (`bot/db.py:1426-1508`).
- One active cycle per conversation is enforced by
  `ux_auto_reviews_active_conversation` (`bot/db.py:1498-1506`).
- Memberships are immutable after insertion; new PRs go to
  `auto_review_pending_memberships` and are consumed only by a later reservation
  (`bot/db.py:1510-1548`, `:2022-2031`, `:8110-8330`).
- Any provenance table must be append-only or bound to an immutable membership; it must
  not provide an update path into an active snapshot.

---

## 7. Security threat analysis

| Risk | Required fail-closed behavior | Existing control / gap |
|---|---|---|
| Spoofed conversation metadata | Treat `selected_repository`/`pr_number` as candidates only; verify GitHub; reject missing/mismatch | Resolver verifies repository/PR; no automatic source exists |
| User-controlled repository reference | Allowlist + numeric repository ID; reject same-name ambiguity; no name-only trust | `GitHubClient.get_repository`/resolver; creation job name is unverified |
| Forged PR reference | Fetch PR by number; require base/head repo IDs equal verified repo; reject cross-repo/fork | Resolver `_validate_pull_request` |
| Fork/cross-repository confusion | Require head repo ID/name == base repo ID/name == verified repo; no fork support | Resolver `PR_FORK_AMBIGUOUS`/`PR_REPOSITORY_MISMATCH` |
| Repository rename/transfer | Numeric ID is identity; current policy rejects name mismatch as ambiguous | Resolver `REPOSITORY_RENAME_AMBIGUOUS`; D-05 open |
| Branch movement | Verify branch tip before and after all reads; reject moved/missing/blocked | Resolver `_verify_branch`; collector rechecks |
| PR head changes | Re-read PR after reads; reject head SHA/ref change | Resolver `_reverify_pull_request` |
| Stale provenance | Re-verify on every use; `verified_at` is evidence, not trust | Resolver re-reads; no persistence currently |
| Duplicate/conflicting candidates | Reject duplicate `(repo_id, pr)`; DB conflict; pending, not mutation | Resolver `_validate_request`; DB reservation |
| Partial GitHub API responses | Strict parsers; pagination error/truncation; no empty success | `GitHubClient` parsers/pagination; no PR discovery method |
| Authorization vs identity confusion | `watched.chat_id`/owner check is authorization only; repository identity requires GitHub ID | Resolver `_authorize`; no OpenHands owner check in resolver |
| OpenHands metadata mutation after creation | Compare current OpenHands repository to local creation context; reject mismatch | Not implemented; must be part of any B source |
| `pr_number` array/scalar shape | Normalize exactly one positive integer or reject; never select first | Display code selects first; no review normalizer |
| API token overreach | GitHub allowlist; read-only methods; no token in URL/logs | Existing GitHub client |
| Partial/empty PR list | Reject empty/malformed; require explicit complete list | Resolver rejects empty/duplicate/invalid |

---

## 8. Required implementation sequence after owner approval

No step below was executed.

1. **Record the owner decision** for D-01 and D-02 in an additive decision record; do not
   treat this analysis as approval.
2. **D-01 adapter**: implement only the approved candidate source behind
   `ConversationRepositoryLinkSource`; no worker wiring. For B, read
   `creation_jobs.repo`/`conversation_id` and verify GitHub; for C, add the owner mapping.
3. **D-02 adapter**: implement only the approved PR candidate source; normalize
   scalar/one-item list only if approved; reject multiple/empty/malformed; no first-PR
   selection.
4. **Provenance**: if required, add an additive migration/table; keep active memberships
   immutable and pending PRs separate.
5. **Tests**: add the regression tests listed below; run focused and full local suites.
6. **Independent review**: request a reviewer separate from the author.
7. **B02**: only after separate approval, wire a disabled-by-default worker/startup
   path with lease/shutdown/recovery tests.
8. **B03**: only after explicit live authorization, run a disposable-repository canary;
   do not claim live success before evidence.

---

## 9. Required regression tests after approval

### D-01

- missing/empty `creation_jobs.repo`; no creation job for an external conversation;
- `chat_id` mismatch/unauthorized conversation; deleted conversation;
- GitHub repository ID mismatch; same-name different-ID; rename/transfer ambiguity;
- local repo vs OpenHands `selected_repository` mismatch;
- no numeric ID vs verified numeric ID;
- restart/idempotency; duplicate creation job; direct-DB mutation rejected by
  verification;
- allowlist rejection; API timeout/partial response.

### D-02

- missing/empty PR metadata; scalar; one-item list; multiple-item list;
- zero/negative/bool/string/non-integer values;
- duplicate PR numbers; cross-repository PR; fork PR; closed/merged PR;
- branch movement before/after; PR head change; PR not found;
- partial/truncated GitHub response; pagination overflow;
- restart/idempotency; explicit owner list completeness;
- no first-PR selection; no branch-name inference; no free-form text inference.

### Provenance/immutability

- source/verified_at persisted once and not silently overwritten;
- active membership cannot be updated/deleted;
- new PR stays pending, not merged into the active cycle;
- conflicting provenance rejected; stale provenance re-verified;
- additive migration preserves existing rows and conversation-wide scope;
- no secrets in provenance/logs/reports.

---

## 10. Exact unresolved owner decisions

### D-01

Choose one:

```text
D-01: A | B | C | reject-for-now
```

- **A** — approve OpenHands `selected_repository` as a candidate only (never as proof);
  verify GitHub numeric ID; reject missing/mismatch; no stable-ID claim without storage.
- **B** — approve local `creation_jobs.repo` + `conversation_id` for bot-created
  conversations; verify GitHub; external conversations need C or remain unsupported.
- **C** — approve an explicit owner/server mapping with numeric repository ID; add
  storage and verification; strongest but manual.
- **reject-for-now** — keep explicit membership/canary only; no automatic D-01.

**Analysis recommendation:** keep D-01 `OWNER_DECISION_REQUIRED`; if a canary is
authorized, choose B only for bot-created conversations, with GitHub verification and
no authority claim. C is the only candidate that can cover all conversations with an
owner-controlled numeric ID, but it is not implemented.

### D-02

Choose one:

```text
D-02: A | B | C | reject-for-now
```

- **A** — approve OpenHands `pr_number` as a candidate; normalize/reject ambiguous
  shapes; verify every PR through GitHub. Evidence of population is missing.
- **B** — approve an explicit owner-supplied PR list for canary; not automatic
  discovery.
- **C** — approve new GitHub read-only discovery with an explicit multiple-PR and
  pagination/truncation policy; not implemented.
- **reject-for-now** — no automatic PR discovery; keep explicit list/canary only.

**Analysis recommendation:** keep D-02 `OWNER_DECISION_REQUIRED`. Use B only for a
controlled canary; do not treat it as discovery. A is unverified; C is new code and a
new policy.

---

## 11. Classification summary

| Decision / component | Classification |
|---|---|
| D-01 authoritative conversation→repository source | `OWNER_DECISION_REQUIRED` |
| D-01 OpenHands `selected_repository` | Candidate only; not authoritative |
| D-01 local `creation_jobs.repo` | Preferred canary candidate; not authoritative; bot-created only |
| D-01 explicit owner mapping | Not implemented; possible authoritative option |
| D-01 `watched.chat_id` | Not a repository source; authorization only |
| D-02 automatic PR discovery | `OWNER_DECISION_REQUIRED` |
| D-02 OpenHands `pr_number` | Unverified candidate; not implemented for review |
| D-02 explicit owner list | Safe canary input; not discovery |
| D-02 GitHub read-only discovery | Not implemented |
| Durable provenance | Not implemented; additive migration required |
| Resolver behavior | Unchanged |
| Worker activation | Deferred |
| Live validation | Not started |
| R8 | Not started |

---

## 12. Scope and verification statement

- **No code changes:** `bot/review/resolver.py`, `bot/review/github.py`,
  `bot/review/collector.py`, `bot/review/worker.py`, `bot/db.py`, `bot/app.py`, and all
  other source files are unchanged by this task.
- **No schema changes:** no table, column, index, trigger, or migration was added.
- **No resolver behavior changes:** the safe resolver still requires an injected
  repository-link source and explicit PR numbers.
- **No tests run:** this was analysis-only; no behavior changed, so no test run was
  required. No test was modified or disabled.
- **No live operations:** no OpenHands API, GitHub API, provider, Telegram, workflow
  dispatch, or external data transmission.
- **No worker activation:** no `ReviewWorker`/`ReviewRunner` startup wiring.
- **No publication:** no commit, push, PR, merge, deployment, or release.
- **No independent review:** this is an author decision analysis, not an independent
  review.
- **No live validation:** R7 live validation has not started.
- **R8:** not started.
- **Conversation-wide scope:** unchanged; one active cycle per conversation, immutable
  membership, new PRs pending.

Final classification: **D-01 = `OWNER_DECISION_REQUIRED`; D-02 =
`OWNER_DECISION_REQUIRED`.**
