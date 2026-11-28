# OHB2-AUTOMATIC-CONVERSATION-REFRESH-REMEDIATION — INDEPENDENT REVIEW

**Date:** 2026-11-28
**Reviewer:** OpenHands agent (read-only review)
**Target task:** `OHB2-AUTOMATIC-CONVERSATION-REFRESH-REMEDIATION-INDEPENDENT-REVIEW`

## 1. Verdict

**`FAIL`**

One unresolved **HIGH** finding remains: the refresh worker's ownership check and the
Telegram edit are not serialized with navigation. A refresh that starts before a
navigation can still complete its Telegram edit after the navigation has invalidated
the target and displayed another screen. This is the F1/F2 failure class the
remediation was required to close.

No publication, push, PR, merge, deployment, release, or Autopush action was
performed. The only repository change is this report.

## 2. Repository and target

| Item | Value |
|---|---|
| Repository | `TM-AEM/OpenHandBot` (`origin` = `https://github.com/TM-AEM/OpenHandBot.git`) |
| Branch | `agent/automatic-conversation-refresh` |
| HEAD / target | `71f65cc90a9bf53a0f70d3689ab9ef571187fdab` |
| Expected parent | `5e893c68eef8935c45f8510cbc65857b966edfc5` — verified |
| Target tree | `3502d001658f16e0ed75e0f9033aa9634ea275a5` |
| Commit subject | `fix: make conversation refresh target ownership explicit` |
| Working tree before review | clean; target commit present locally |
| Diff | 9 files, 1388 insertions, 131 deletions |
| `git diff --check` parent..target | exit 0 |

The target branch and commit are **not published**. Read-only GitHub API checks
returned HTTP 404 for the branch ref, HTTP 422 (`No commit found for SHA`) for the
commit, and zero workflow runs for the branch. No CI result is claimed.

The previous review report and implementation report named in the task
(`docs/reviews/...-INDEPENDENT-REVIEW-20261127.md` and
`docs/reviews/...-REMEDIATION-REPORT-20261128.md`) are absent from the target tree and
from the workspace. I therefore could not verify their exact text claim by claim. I
used the F1–F7 definitions supplied in this task and inspected the implementation and
tests directly.

## 3. Methodology and independence

I inspected the complete target diff against the verified parent, the schema and
migration, every conversation-view SQL statement, all message-edit call sites, the
refresh service/worker, handlers, sender fallback, app wiring, documentation, and the
new and existing tests. I ran the tests and static checks from the clean working tree.
I also ran isolated ad-hoc reproductions against temporary SQLite databases and fake
Telegram/OpenHands transports; those did not modify the repository.

**Independence limitation:** this review ran in the same runtime/workspace as the
implementation and is not a separate reviewer session or third-party execution. The
code/test evidence can be checked independently, but strict process independence is
**not established**. The implementation report was unavailable and was not treated as
evidence.

## 4. Findings

### R-01 — HIGH — Edit is not serialized with invalidation (F1/F2)

**Location:** `bot/refresh.py:278-284` (pre-edit `_is_current`) and
`bot/refresh.py:410-430` (`await self.bot.edit_message_text`); handler invalidation at
`bot/handlers.py:370-387`.

**Failure scenario:** the worker claims a target, fetches fresh data, passes the
pre-edit ownership check, and begins `edit_message_text`. While that Telegram call is
awaiting, a navigation handler calls `supersede_message` and edits the same Telegram
message to a menu/status/other screen. The already-started worker edit is not
cancelled or awaited by the handler and can complete afterwards.

**Reproduction evidence (isolated fake transport):** with a blocking
`edit_message_text`, `service.refresh(claimed_target)` reached the edit, then
`h.show_menu` invalidated the target and edited the menu, then the blocked worker edit
was released:

```text
handler_race: handler_edits=1 refresh_edits=[('refresh', 100)] target_superseded=True
```

The target row was correctly marked superseded, but the old refresh edit still ran.
The new remediation test only invalidates while `get_last_exchange` is awaiting
(`tests/test_automatic_conversation_refresh_remediation.py:553-573`); it does not
exercise invalidation during the edit await.

**Impact:** a user can select another screen at the same time an automatic refresh is
updating the conversation message. The repurposed message can end up containing the
old conversation view instead of the selected menu/status/files/reply screen. Because
the target is superseded, no later refresh repairs the screen. The exact final order
in a live Telegram session is network-dependent; the code provides no ordering or
serialization guarantee.

**Blocks acceptance:** **YES**.

**Required remediation:** serialize invalidation and the worker's Telegram edit per
`(chat_id, message_id)` (a per-message lock/lease owned by both the handler and
worker), and ensure a handler cannot display a replacement until any in-flight refresh
edit has been cancelled or completed and rejected. Add a regression test that blocks
inside `edit_message_text`, invalidates via a real navigation handler, releases the
blocked edit, and asserts the refresh cannot edit after invalidation. The existing
fetch-only barrier test is insufficient.

### R-02 — MEDIUM — Invalidation failure is swallowed; stale target remains usable

**Location:** `bot/refresh.py:180-194` (catch all exceptions and return 0);
`bot/handlers.py:377-387` (handler ignores the result); `bot/db.py:4550-4566`.

**Failure scenario:** the database write in `invalidate_conversation_views_for_message`
raises (for example SQLite busy beyond the timeout). `supersede_message` logs and
returns 0, but the navigation handler continues and displays the replacement screen.
The old target remains `active=1, superseded=0`, so a later worker refresh can edit the
message back to the conversation view.

**Reproduction evidence (isolated fake DB failure):**

```text
after failed invalidation: menu_edits=1 target_active=True
later refresh edits=1 row_active=True
```

**Impact:** F1's "no stale target can overwrite another screen" guarantee is
conditional on the invalidation write succeeding. This is an error-path gap rather
than the primary normal-path failure, but it is a real swallowed database error with a
user-visible consequence.

**Blocks acceptance:** **NO for the normal path**, but it is a material F1 limitation
and should be fixed with R-01. A robust design must fail closed (do not display the
replacement, or use a durable/in-memory invalidation marker) when it cannot durably
invalidate the target.

**Required remediation:** make invalidation failure explicit to the handler and
fail closed before the replacement display, or atomically combine invalidation with
the state transition. Add a DB-failure regression test.

### R-03 — MEDIUM — Unleased compatibility path bypasses generation/ownership CAS

**Location:** `bot/refresh.py:313-361` (`_current_target` / `_is_current` compatibility
path), `bot/refresh.py:378-400` (`_finish` wrapper), and
`bot/db.py:4568-4606` (unleased finish/defer/deactivate wrappers).

**Failure scenario:** `ConversationRefreshService.refresh` accepts an unleased
`ConversationView` (as returned by `get_conversation_view`, and as used by most
existing refresh tests). The unleased `_is_current` checks active/superseded/token but
not `generation`; the unleased `_finish`/`_defer` wrappers update by
`telegram_id, conversation_id` and do not CAS ownership. If `request_immediate` bumps
the generation and schedules a new check while such a refresh is fetching, the old
refresh can finish and overwrite the schedule and publish its exchange to the cache.

**Reproduction evidence (isolated blocking client):**

```text
unleased stale prompt: scheduled_next= 2026-01-01T12:00:00+00:00
unleased stale prompt: after_next= 2026-01-01T12:00:35+00:00 edits= 1
```

The prompt-success immediate schedule was overwritten by the older unleased refresh.

**Impact:** the production worker path always supplies a claimed target, so current
production scheduling is protected. The public service API and many existing tests use
the compatibility path, however, and F2's requirement says every database write that
changes refresh ownership/scheduling must be CAS-protected. This is also a test-quality
gap: the passing existing refresh tests mostly exercise the unprotected path.

**Blocks acceptance:** **NO** for the current single-worker production path, but it is
a material F2/F5 limitation and a misleading test baseline. Remove the compatibility
path from production-accessible code or make it CAS against `generation/target_token`;
make all service refresh tests use claimed targets.

### R-04 — MEDIUM — Long fallback stores the last part but the full-view fingerprint

**Location:** `bot/handlers.py:200-207` and `bot/handlers.py:214-220` (actual fallback
message is returned), `bot/refresh.py:254-303` (refresh always renders/edits the full
view), `bot/sender.py:34-45` (only the last split message is returned; a file returns
`None`).

**Failure scenario:** the initial display is split into several Telegram messages and
the target correctly points at the last message. `record_view` still fingerprints the
**full** text, while the last Telegram message contains only the last part. When the
exchange changes, `refresh` renders the full text and sends it to the last part. If the
full text exceeds the Telegram edit limit, the edit returns `BadRequest("Message is too
long")`, which `_edit` treats as transient; the target backs off and the displayed part
never updates. The file/report fallback (`send_long` returns `None`) correctly records
no target, but no test covers the complete fallback + refresh path.

**Reproduction evidence (isolated service path):** recording a 5000-character view on
message 777 and making the edit return `Message is too long` produced:

```text
long fallback: active=True failures=1 edits=0
```

**Impact:** the F6 requirement "long fallback tracks the actual message" is satisfied
for identity, but not for subsequent refresh behavior. Normal `format_conversation_view`
output is bounded, so the production conversation-view fallback is expected to be rare;
the code still has no safe recovery if it occurs.

**Blocks acceptance:** **NO** if bounded normal views are accepted as the only real
path, but it is a material F6 fallback gap. Persist the part/index/actual last text or
add a refresh-time "too long" re-send path; test the real `open_conversation` fallback
registration and a subsequent refresh.

### R-05 — LOW — `REFRESH_MAX_CONCURRENT=1` is declared, not enforced

**Location:** `bot/refresh.py:46-50` and `bot/refresh.py:532`; the actual worker loop is
`bot/outbox.py:1160-1171`.

The constant is assigned to `worker.max_concurrent`, but no code reads that attribute
to limit claims or processing. The current app creates exactly one
`ConversationRefreshWorker` (`bot/app.py:316-319`), and `_BaseWorker._tick` awaits one
`_process`, so the observed production path is sequential. The remediation test
`test_worker_claims_one_due_view_at_a_time_and_uses_fair_order` actually leases **two**
different rows before processing the first; a second worker or a second process would
therefore be able to process different targets concurrently. This is an architectural
assumption, not a proven global limit.

No provider rate limits are claimed. Startup/backlog behavior is sequential, but
three upstream calls per view and two event searches in `get_last_exchange` remain an
operational load risk.

**Blocks acceptance:** **NO** for the current one-process architecture; document the
single-worker assumption and add a two-worker guard if multi-process deployment is
allowed.

### R-06 — LOW — Migration is not crash-atomic and conflict winner is not timestamp-based

**Location:** `bot/db.py:1797-1830`; schema creation at `bot/db.py:1251-1789`.

The old table is renamed, a new table is created through `executescript`, rows are
copied, conflicts are resolved by keeping `MAX(view_id)`, and the legacy table is
dropped. The migration is not wrapped in an explicit transaction. A process failure
between the rename/insert/drop steps can leave a legacy table and a partially
populated new table without recovery code. `MAX(view_id)` is insertion order, not
necessarily the row with the newest `updated_at`; conflicting legacy targets are kept
deterministically but not semantically newest. The test covers a successful migration
with two conflicting active rows, not interruption/rollback.

**Blocks acceptance:** **NO** for a normal clean startup; the migration must be made
transactional/recoverable before deployment to an existing production database.

### R-07 — LOW — Inactive retention only runs at startup

**Location:** `bot/app.py:281-292`; `bot/db.py:4651-4657`.

Inactive/superseded rows older than 30 days are pruned in `_post_init`. A long-running
process that never restarts can retain inactive rows indefinitely. Active rows are
correctly excluded from pruning. This is a bounded-growth gap, not a correctness or
security finding.

## 5. F1–F7 status matrix

| Finding | Status | Evidence / reason |
|---|---|---|
| **F1** — Telegram target lifecycle | **PARTIALLY RESOLVED** | Per-message primary key, unique active-message index, navigation invalidation and actual fallback message identity are implemented and tested. R-01 (edit not serialized) and R-02 (invalidation failure swallowed) remain. R-04 also limits fallback refresh. |
| **F2** — Lease ownership and CAS | **PARTIALLY RESOLVED** | Claimed worker path uses unique lease token + target token + generation; finish/defer/deactivate CAS predicates are correct; stale DB writes and prompt reactivation are rejected. R-01 (TOCTOU with edit) and R-03 (unleased compatibility path) remain. |
| **F3** — Ambiguous metadata | **RESOLVED** | `authorize_conversation_detailed(..., empty_is_ambiguous=True)` maps empty metadata to retryable `AMBIGUOUS`; 404/tombstone/unauthorized deactivate; 5xx/429 retry with bounded backoff; malformed identifier stops. The opt-in leaves ordinary file-browser behavior at `NOT_FOUND`. |
| **F4** — API load/concurrency | **RESOLVED** (with R-05 LOW note) | Production has one refresh worker and `_BaseWorker` processes one item at a time; backlog is sequential and leases prevent re-claim. The named constant is not an enforcement mechanism; no global multi-process limit or provider rate limit is claimed. |
| **F5** — Exchange cache consistency | **PARTIALLY RESOLVED** | Claimed successful refresh updates the cache only after successful `_finish`; stale/superseded/error paths do not publish; cache is shared with copy/full and bounded to 20 entries. R-03 shows the unleased compatibility path can publish/overwrite after a newer immediate schedule. Eviction is insertion-order, not true LRU (INFO). |
| **F6** — Identity/fallback/cleanup | **PARTIALLY RESOLVED** | Unique active target per message, independent targets per message, deletion cleanup in the delete transaction, inactive-only retention, and legacy migration are implemented/tested. R-04 leaves long-split refresh behavior incomplete; R-06 leaves migration crash/winner caveats; file fallback correctly creates no target. |
| **F7** — idle / paused semantics | **RESOLVED** | `bot/messages.py:64-66` keeps `idle`/`paused` non-terminal; the existing approved policy table says `running, idle, paused → RUNNING → continue polling`; `docs/OPERATIONS_RUNBOOK.md:116-119` states the same and explicitly says no new provider semantics were invented. The test only asserts `is_terminal` values, which is the same production predicate. Residual uncertainty is documented, not guessed. |

## 6. Test and check evidence

All commands were run from the clean target working tree with
`.venv/bin/python` (Python **3.13.15**). Exact results:

| Check | Command | Result |
|---|---|---|
| Targeted refresh/db/handlers/outbox/sender/files/messages/doc tests | `.venv/bin/python -m pytest -q tests/test_automatic_conversation_refresh.py tests/test_automatic_conversation_refresh_remediation.py tests/test_db.py tests/test_handlers.py tests/test_outbox.py tests/test_sender.py tests/test_conversation_deletion.py tests/test_files_service.py tests/test_messages.py tests/test_doc_code_parity.py` | **404 passed, 5 warnings, 29.91s**, exit 0 |
| Full Python suite | `.venv/bin/python -m pytest -q` | **4385 passed, 77 warnings, 342.83s**, exit 0 |
| Frontend | `node --test tests/frontend/*.test.js` | **272 pass, 0 fail**, 965.508ms, exit 0 |
| Typecheck | `npm run lint` | exit 0 |
| Build | `npm run build` | exit 0; Vite `configLoader: native` warning only |
| Lint | `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit 0 |
| SAST | `.venv/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | exit 0; High **0**, Medium 27, Low 7 |
| Dependency audit | `.venv/bin/python -m pip_audit -r requirements-dev.txt` | no known vulnerabilities, exit 0 |
| Whitespace/diff | `git diff --check <parent> <target>` | exit 0 |
| Schema smoke | isolated `PRAGMA integrity_check`; duplicate active insert | `ok`; duplicate rejected by unique index |

**Python 3.11:** not available (`python3.11` absent); not run. **GitHub Actions:** no CI
run exists for the unpublished branch/commit. **Live Telegram/OpenHands:** not called;
no production credentials used.

## 7. Critical race-scenario coverage

| # | Scenario | Existing coverage | Assessment |
|---|---|---|---|
| 1 | Open A, navigate same message, trigger old refresh | `test_navigation_supersedes_claimed_target_delete_and_menu`; R-01 ad hoc | Handler path covered for fetch-complete invalidation; **edit-time race not covered**. |
| 2 | Two conversations successively on same message | `test_same_message_has_only_one_active_target` | Real service + claimed target; good. |
| 3 | Same conversation on two messages | `test_same_conversation_on_two_messages_has_two_independent_targets` | Real service + claimed targets; good. |
| 4 | Invalidate during refresh | `test_invalidation_while_refresh_is_fetching_prevents_edit` | Fetch only; **edit stage uncovered (R-01)**. |
| 5 | Claim, immediate request, stale finish | `test_immediate_refresh_survives_older_worker_finish` | DB-level CAS verified; service-level claimed flow not directly tested. |
| 6 | Claim, deactivate/supersede, stale finish/defer | `test_superseded_target_rejects_stale_finish_defer_and_edit` | Good DB + service edit check. |
| 7 | Expire/replace lease while old worker runs | `test_expired_lease_can_be_replaced_and_old_owner_rejected` | DB-level only; no concurrent old service task. |
| 8 | Terminal completion vs prompt success | `test_terminal_completion_cannot_reactivate_after_prompt_immediate` | DB-level; production CAS predicate verified in SQL. |
| 9 | Empty, 429, 5xx, 404, auth failure | `test_empty_metadata_is_ambiguous_and_retried`; parametrized outcome test | Classification covered; many calls use unleased service path (R-03). |
| 10 | Refresh then copy/full | `test_successful_refresh_updates_exchange_cache_and_copy_reads_it` | Cache + `_get_exchange`; actual `copy_reply` handler not invoked. |
| 11 | Delete conversation during refresh | None | Ad hoc verified 0 edits/0 rows; no repository test. |
| 12 | Restart with pending/expired lease | `test_active_schedule_survives_a_new_service_instance`; ad hoc pending/expired | Pending lease restart not in repository tests. |
| 13 | Legacy conflicting active targets | `test_old_conversation_view_schema_is_migrated` | Successful migration only; no crash/rollback test. |
| 14 | Long conversation fallback | `test_long_message_fallback_records_actual_replacement_message` | Helper-level identity only; no registration + subsequent refresh + file fallback test. |

## 8. Architecture and regression assessment

- One bot/ASGI process and one SQLite owner are preserved; no new worker or source of
  truth was introduced.
- Background refresh only reads authorization/metadata/exchange and edits Telegram. It
  does not send prompts, resume/stop/create/delete conversations, or alter
  `last_accessed_conversation_id`; grep of `bot/refresh.py` confirms no such writes.
- Existing outbox/worker lifecycle is reused; refresh has its own existing worker and
  35-second interval. Immediate scheduling on confirmed prompt success remains wired
  through `on_sent`.
- The schema remains scheduling/presentation state, not conversation ownership.
- No exactly-once claim is made; the leased/CAS model is at-most-one-owner with
  retries.
- Full Python/frontend suites and static checks are green; no unrelated frontend
  regression observed.
- The `REFRESH_MAX_CONCURRENT` constant is not a real guard (R-05); the actual
  single-worker assumption must be documented/defended before multi-process operation.

## 9. Limitations and non-claims

- Previous review and implementation report files are absent; exact historical claim
  matching is `UNVERIFIED`.
- Independence is `NOT ESTABLISHED` in the strict process sense: same runtime/agent,
  not a separate reviewer.
- Python 3.11, CI, live Telegram, and live OpenHands were not executed.
- No production credentials or external mutation calls were used.
- The only created file is this report. No implementation/test/config change, no
  branch switch, no fetch/pull, no reset/clean/stash/rebase/amend/cherry-pick, no commit,
  no push/PR/merge/deploy/Autopush.
- Working tree after review contains only this report and remains otherwise clean.

## 10. Release-readiness conclusion

The remediation substantially improves the normal per-message lifecycle, owner CAS,
ambiguous-metadata handling, deletion cleanup, exchange-cache ordering, and fallback
message identity. It is **not ready to proceed as a clean release-readiness candidate**
because R-01 remains a HIGH F1/F2 correctness gap and R-02 is a material F1 error-path
gap. The next task should implement and independently review the serialization/fail-
closed remediation; it should not be treated as a PASS based only on the existing
fetch-stage test or the green suite.
