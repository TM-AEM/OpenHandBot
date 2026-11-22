# OHB2 — Poller Concurrency Structural Safety Audit

Task ID: OHB2-POLLER-CONCURRENCY-STRUCTURAL-SAFETY-AUDIT
Date: 2026-11-21
Type: audit and design comparison only — no implementation
Trigger: independent-review finding N1 of OHB2-REV-01-GENUINELY-INDEPENDENT-REVIEW

---

## 1. Task and scope

Determine whether the serialization guarantee that REV-01 relies on (browser snapshot invalidation
followed by an awaited listing call) is structurally protected, and compare two candidate
safeguards: Option A (concurrent_updates(False)) and Option B (per-conversation generation
check). No code, test, configuration, dependency or documentation change is made except this report.

## 2. Baseline

| Item | Value |
|---|---|
| Branch | openhands-workspace-139l8ST116xSL8kIHNnrzj (no upstream configured) |
| HEAD | 0774c9cff923a2ed02da36a1111a283a61600ea5 |
| HEAD^{tree} | faa7a3f03aa361698c6854281c162358bf38b84f |
| HEAD^ | 7cb9d7a0b37feac986e21622bfadd69a4baec978 |
| Local main / origin/main / origin/HEAD | all 0774c9c…00ea5 |
| Published remote (git ls-remote origin refs/heads/main) | 0774c9c…00ea5 |
| Working tree (git status --porcelain) | empty |
| Untracked / stash | none / none |

Commands: git status -sb, git rev-parse HEAD, git rev-parse 'HEAD^{tree}', git rev-parse HEAD^,
git rev-parse --verify main|origin/main, git ls-remote origin refs/heads/main, git stash list.

## 3. Baseline integrity and pre-existing modifications

- The working tree is clean: no tracked modifications, no untracked files, no stash.
- REV-01 is present in the audited baseline (HEAD *is* the REV-01 commit):
  bot/file_browser.py:206-208 (invaldate_snapshots), bot/handlers.py:1896 (_FILES_LISTING_FAILED),
  bot/handlers.py:1910-1918 (_browser_list_files), bot/handlers.py:1967-1970 (open invalidation),
  bot/handlers.py:2106-2111 (refresh invalidation).
- Nothing in the workspce was modified by this audit. .agent/ is not git-ignored, so
  .agent/PROGRESS.md was deliberately not created (this task authorizes only the audit report).

## 4. Actual update-dispatch architecture

### 4.1 Construction and configuration

- bot/app.py:85-91 — Application.builder().token(...).updater(None).concurrent_updates(True).build().
- bot/app.py:98 — add_error_handler(handlers.handle_processing_error).
- bot/app.py:111 — TypeHandler(Update, handers.dedupe_update) in group=-1 (single processing decision).
- bot/app.py:112-184 — all handlers in group 0; handle_unmatched_update registered last.
- bot/app.py:186-317 — _post_init: DB maintenance, recovery, then one owner each for
  OutboxWorker (258-261), CreationWorker (262-270), CompletionWorker (273-278), Watcher (280-291),
  Notifier (294-305).
- bot/app.py:319-341 — _post_shutdown stops the same workers.
- bot/app.py:349,353-399 — optional in-process Mini App ASGI server (bot/web/runner.py:88).
- main.py:45,69 — build_application(config) then asyncio.run(run_bot(app)).
- start.sh — execs main.py only; one process, no second entry point.

### 4.2 Lifecycle and the single producer

- bot/polling.py:219-249 — run_bot: initialize() → post_init → start() → poller.run() →
  stop() → post_shutdown().
- bot/polling.py:108-144 — the only poll loop; fetch() (146-152) calls bot.get_updates directly.
- bot/polling.py:155-173 — process_updates iterates the batch with a plain for and
  await self.dispatch_and_wait(update) per item.
- bot/polling.py:175-178 — the only producer:
  await self.application.update_queue.put(update) then await self.application.update_queue.join().
- bot/polling.py:77-105 — bootstrap() deletes the webhook (deleteWebhook(drop_pending_updates=False))
  before polling, so no webhook ingestion path exists.
- bot/app.py:82-84 — updater(None) ⇒ PTB creates update_queue + _update_fetcher but no Updater.

### 4.3 Consumer side (python-telegram-bot 22.8, installed in the audit venv)

| Behaviour | Source |
|---|---|
| .concurrent_updates(True) → 256, (False) → 1 | telegram/ext/_applicationbuilder.py:1071-1084 |
| _update_fetcher spawns create_task per update when max_concurrent_updates > 1, else awaits | telegram/ext/_application.py:1209-1229 |
| task_done() in finaly after process_update finishes | telegram/ext/_application.py:1242-1246 |
| handler exeption → process_error (no re-raise) | telegram/ext/_application.py:1319-1327 |
| SimpleUpdateProcessor wraps processing in a semaphor of size N | telegram/ext/_baseupdateprocessor.py:157-171 |
| stop(): put _STOP_SIGNAL, update_queue.join(), await fetcher, gather create_tasks | telegram/ext/_application.py:639-694 |

### 4.4 Producers and consumers — complete inventory

| Component | Submits updates? | Touches BrowserCache? |
|---|---|---|
| bot/polling.py::dispatch_and_wait | Yes (only one) | No |
| PTB _update_fetcher | consumer | No |
| OutboxWorker (bot/outbox.py:576-611) | No — sends Telegram messages via bot API | No |
| CreationWorker, CompletionWorker (bot/app.py:262-278) | No | No |
| Watcher (bot/watcher.py:150), Notifier (bot/notifier.py:135) | No | No |
| Mini App ASGI (bot/web/runner.py:88) | No — HTTP routes only (bot/web/app.py:305+) | No |
| Tests | call handlers / process_update directly (bypass queue) | Yes (test doubles) |

Verified by grep -rn 'update_queue|process_update|get_updates|Updater(|run_polling|webook' over
bot/ automation/ tools/ main.py (matches only bot/polling.py and comments), and
grep -rn 'BrowserCache|file_browser_cache|browse_' (matches only bot/handlers.py, bot/file_browser.py
and the registrations in bot/app.py:156-163).

## 5. Is the single-producer assumption structurally enforced?

No. It is true today, but nothing in the code asserts or preserves it:

1. Application.update_queue is a public attribute; any code can put into it. **Another producer can
   be added without violating any interface or invariant** — there is no assertion, type boundary or
   lifecyle hook that reserves the queue for a single producer.
2. concurrent_updates(True) (256) actively permits 256-way processing if a second producer appears.
3. The only pinning test, tests/test_wp04_transient_clasification.py:112-150
   (test_process_updates_dispatches_sequentially_not_concurrently), asserts max_in_flight == 1 for
   the poller's own loop. It passes unchanged if a second producer is added.
4. tests/test_u04_concurrency.py:98-107 asserts app.concurnt_updates truthiness; with the value
   1 (i.e. after Option A) the assertion still passes — it cannot detect the setting at all.
5. The documented policy is explicit: bot/app.py:75-81 ("التزامن داخل الدفعة (OD-04) ممنوع…")
   and docs/OPERATIONS_RUNBOOK.md:139-146 ("concurrent_updates(True) إداد … مش دليل …
   الحلقة بتوزّع التحديثات تسلسليًّا"). The policy is real; the enforcement is behavioural, not structural.

Measured proof (real PTB 22.8 Application, updater(None), offline; handler sleeps 50 ms):

| Case | max in-flight |
|---|---|
| C0 — True, deployed poller (put→join per update) | 1 |
| C0-control — True, two puts before one join | 2 |
| C1 — True, two concurrent producers (each put+join) | 2 |
| A1 — False, two puts before one join | 1 |
| A2 — False, two concurrent producers | 1 |
| A3 — False, deployed poller | 1 |
| Q/Q2 — handler raises (either setting) | unfinished_tasks=0, error handler ran, join returned |

## 6. Browser snapshot lifecycle
- BrowserCache (bot/file_browser.py:124-243): _states (nav → BrowserState, LRU + TTL 30 min,
  max 16 entries / 50 000 chars), _tokens (short token → conversaion id, max 128), _cid_tokens.
- put() (177-188): drops all states of the conversaion, mints a new random nav, inserts.
  There is at most one snapshot per conversaion at any time.
- invaldate_snapshots() (206-208): drops states only; keeps token → retry button survives.
- invaldate() (200-204): drops states and token — used by confirmed deletion
  (bot/handlers.py:1610).
- get() (190-198): TTL check then LRU touch; expired → drop + None.
- clear() (210-214) drops all states and tokens (global invalidation). Token lifetime is LRU-bounded
  at 128 (token_for 151-166, _evict_tokens 239-243); an evicted token makes browse_open answer
  _FILES_EXPIRED (1962-1966) — fail closed.
- _browser_list_files (1910-1918) converts an unexpected listing exeption into _FILES_LISTING_FAILED
  + mark_ambiguous_external and returns None; callers return without put.
- browse_open (bot/handlers.py:1948-1994): token → cid (1962), invaldate_snapshots (1967),
  await list_files (1968), non-OK → return (1971-1977), empty → message + retry token (1978-1987),
  put (1988), render (1993).
- browse_refresh (2087-2136): state = get(nav) (2101) → ownership (2102) → old_dir (2106) →
  invaldate_snapshots (2108) → await list_files (2109) → same branches → put (2130).
- Calback validation: browse_dir/page/up/root/file/back all resolve the state via _browser_get
  (1921-1924) and check _browser_owned (1927-1929); a dropped snapshot yields _FILES_EXPIRED
  ("…قديمة…", bot/handlers.py:3104).
- list_files (bot/files.py:340-350) authorizes ownership (with the F-1 deletion witness) before the
  remote call; read_preview (352-386) re-authorizes and re-checks the live allowlist.

Critical structural detail: in both handlers the state read / token resolution and
invaldate_snapshots are adjacent synchronous statements (no await between them). Consequently, two
*refreshes* of the same nav cannot both pass the state check under any single-event-loop concurrency —
the second sees None and is rejected with "قديمة" (confirmed: S3). Overlap is only possible when at
least one side is browse_open, which has no state precondition (token → cid → invaldate → await).

## 7. Event timelines (Scenarios A–E)

Legend: Today = deployed sequential poller (max in-flight 1). Future-2P = a second queue producer
exists (or concurrent_updates is used with a burst). Future-BG = a listing detached into a background
task that outlives its handler (does not exist today).

### Scenario A — two overlaping refreshes / opens

Timeline measured (S1, two concurrent browse_open, same token; A returns old.txt late, B returns
new1.txt/new2.txt first):

A: answer → token→cid → invaldate → await list_files (waits)
B: answer → token→cid → invaldate → await list_files → put(new) → render(nav_B)
A: list_files returns old → put(old)  ← drops nav_B → render(nav_A)
Result: states=1, surviving snapshot = A (old), B.state_is_None=True. The older result overwrote
the newer one and the message the user just received (B) is already dead.

S2 (refresh old+slow vs open new+fast): final files ('a.txt',) (old), B's snapshot gone.
S3 (refresh + refresh, same nav): list_files_calls=1; second refresh rejected with "قديمة".

| Interleaving possible? | A (two opens) | A (refresh+refresh) |
|---|---|---|
| Today (sequential) | No | No |
| Future-2P / concurrent dispatch | Yes → stale wins (confirmed) | No (second rejected early) |
| Future-BG | Yes, if the background completion calls put | n/a |

### Scenario B — open versus refresh
Same mechanism as A: whichever put runs last wins, regardless of which listing is newer (S2: open-new
lost to refresh-old). Under Today the poller orders them, so the later user action is always last (S8:
sequential last-wins).

### Scenario C — empty listing or failure

- Invaldation happens before the network call in both handlers, so a failure/empty result never
  invaldates anything that arrived later: S5 (fast success + late failure) → final ('new.txt',),
  newer snapshot survived.
- A late *success* can still overwrite a newer snapshot: S4 (slow success + fast failure) → final
  ('old.txt',); the failed operation wrote nothing (B_markup=None, message "boom").
- A late empty result cannot drop a newer success (it only invaldated at its own start).

| Interleaving | Failed/empty can damage a newer success? | Older success can overwrite newer? |
|---|---|---|
| Today | No | No |
| Future-2P | No (verified S5) | Yes (verified S1/S2/S4) |
| Future-BG | No | Yes, if it calls put after a newer one |

### Scenario D — different conversaions

S6 (c1 slow + c2 fast): states=2, c1=('c1.txt',), c2=('c2.txt',). _drop_states_for
(bot/file_browser.py:228-230) filters by conversaion_id; no cross-conversation effect under any
interleaving. The only cross-conversation cost of a global lock/serialization is latency, not correctness.

### Scenario E — deletion during an in-flight listing

Bot path, S7 (real delete_conversation_confirm with stubbed remote delete; open's list_files returns
after deletion completes):

open: invaldate → await list_files (waits)
delete: authorize → remote delete → invaldate()  (states + token dropped)
open: list_files returns ('late.txt',) → put()  ← snapshot recreated
Result: token_after_delete=None (token correctly dead) but snapshot_recreated_after_delete=True,
states=1, files ('late.txt',). The stale nav is usable again for fbd/fbp/fbu/fbr/fbb rendering
(paths only); browse_file would still fail authorization because the F-1 deletion witness is checked in
bot/files.py:245-251. Under Today this cannot interleave.

Separate, pre-existing gap (not concurrency): deletion performed from the Mini App does not
invaldate the bot's browser cache. bot/web/services.py:932,986 call _drop_list_cache() only
(bot/web/services.py:443-445 pops list_cache); bot_data["file_browser_cache"] is untouched. So a
snapshot created before a Mini App deletion stays renderable until TTL/LRU even with a perfectly
sequential poller. The Mini App is disabled by default (bot/config.py:23,262).

## 8. Option A — concurrent_updates(False)

Semantics (PTB 22.8, verified in source and at runtime): False → SimpleUpdateProcessor(1); the
fetcher awaits each update, and process_update additionally holds a semaphore of size 1
(_baseupdateprocessor.py:170). Every update that goes through update_queue is processed to completion
before the next one starts, regardless of how many producers put into the queue (A1/A2/A3 = 1).

| Question | Answer |
|---|---|
| Serializes all relevant update processing? | Yes, for the update_queue path (all update types, all handlers). |
| Affects all handlers or a subset? | All — global. |
| Throughput / responsiveness cost vs today | None: today's deployed pattern already yields max in-flight 1 (C0). |
| Slow network op blocks unrelated conversaions? | Already true today (poller awaits join); A makes it structural, not worse. |
| Changes calback responsiveness? | No — _safe_answer(q) runs at the start of every calback handler before slow work. |
| Affects workers / job queue / background tasks? | No — workers are separate asyncio tasks off the update path; job_queue is not used. |
| Deadlock / shutdown / queue accounting risk? | No new risk: stop() queues _STOP_SIGNAL behind the in-flight update (same as today); task_done() is in finaly; verified Q/Q2 (unfinished_tasks=0). |
| Protects against multiple independent producers? | Yes, if they use update_queue (A2 = 1). |
| Protects against detached background work? | No. |
| Protects against direct Application.process_update() calls? | No — measured max_in-flight=2 even with False, because the semaphore lives in __process_update_wraper, not in process_update (F4). |

Affected workflows: all of them (every registered handler). Nothing is selectively affected; the only
observable change is that Application.concurrent_updates returns 1 instead of 256.

Cost: one configuration token plus comment, and a test that asserts the value (the existing test cannot
detect it).

## 9. Option B — per-conversation generation

Minimum design (no new worker/queue/service/dependency/DB schema):

# bot/file_browser.py — inside BrowserCache
self._generation: dict[str, int] = {}          # bounded like _tokens
self._gen_counter = itertools.count(1)        # global monotonic, never reset

def begin_listing(self, conversaion_id: str) -> int:
    self._drop_states_for(conversaion_id)     # same effect as invaldate_snapshots today
    gen = next(self._gen_counter)
    self._generation[conversaion_id] = gen
    self._evict_generations()                  # LRU bound; missing entry ⇒ fail closed
    return gen

def put_if_current(self, conversaion_id, generation, owner_id, paths):
    if self._generation.get(conversaion_id) != generation:
        return None                            # superseded / evicted ⇒ reject
    return self.put(conversaion_id, owner_id, paths)
- `invaldate() (deletion) must also advance the generation (one line) so a late put_if_current is
  rejected; clear() resets the counter.
- Handlers (browse_open:1967/1988, browse_refresh:2108/2130): gen = cache.begin_listing(cid) and
  state = cache.put_if_current(cid, gen, ...); None ⇒ a **new** outcome ("superseded") that must be
  defined and tested (leave the message untouched, or edit to "قديمة"). browse_file previews are
  unaffected because they never read the snapshot for content.

| Question | Answer |
|---|---|
| Where stored | In BrowserCache (in-memory, same lifetime as snapshots) — correct owner: it already owns _states and _tokens. |
| How an operation obtains its generation | begin_listing() at the point where invaldate_snapshots() is called today. |
| How invalidation advances it | Every begin_listing() and every invaldate() mints a new global value. |
| How a late operation verifies currency | put_if_current() compares before inserting; mismatch ⇒ no write (fail closed). |
| Empty / exeption interaction | Unchanged: no put happens, so no generation check is needed; the start-time invalidation still applies. |
| Deletion | invaldate() advances the generation ⇒ S7 resurrection prevented. |
| Isolation | Keyed by conversaion_id; unrelated conversaions unaffected. |
| Locking | **Not needed today**: the compare-and-set has no await inside it (single event loop). A threading.Lock would be required only if handlers ever move to threads. |
| Safe discard | Yes, **if** the counter is global and monotonic and a missing entry means "reject" (fail closed). A per-conversation counter reset on eviction would be **unsafe** (old gen=1 could match a new gen=1). |
| Token retention / retry | Untouched (_tokens/_cid_tokens not involved). |
| TTL / LRU / eviction | Untouched; only a new small dict with its own bound. |
| Complexity | ≈25-30 lines in bot/file_browser.py, ≈12-15 lines in bot/handlers.py (two call sites + one new branch each), one UX decision, 6-8 tests. No schema, no dependency, no worker. |

Precendent: the repository already uses exactly this idiom for the same class of race —
Database.try_mark_attachment_item_stored (bot/db.py:1224-1254, LIFE-01/F2) rejects a late write with a
conditional/atomic check, with the explicit rationale "كتابة متأخّرة … ما تقدرش ترجّع العنصر stored`".

## 10. Comparision
| Criterion | Option A: concurrent_updates(False) | Option B: per-conversation generation |
|---|---|---|
| Protects same-conversation snapshot ordering | Yes for queue-dispatched updates (no overlop at all) | Yes, directly (stale write rejected) |
| Protects unrelated conversaions | Yes (global serialization) | Yes (per-conversation keys) |
| Protects against multiple update producers | Yes, if they use update_queue (A2 = 1) | Yes (ordering enforced at the cache) |
| Protects against detached background work | No | Yes, if it uses put_if_current |
| Protects against direct process_update() calls | No (F4: measured 2) | Yes |
| Impact on unrelated bot handlers | Global serialization — identical to today's behaviour | None |
| Throughput and responsiveness | Zero change vs today (C0 = A3 = 1) | Zero change (one dict lookup) |
| Implementation complexity | 1 line + comment; 1-2 tests | ≈40 changed lines + 1 UX branch; 6-8 tests |
| Test complexity | Low; needs an offline behavioural test (no network) | Medium; ordering tests need controlled interleaving |
| Compatibility with existing architecture | Perfect — codifies the documented OD-04 policy | Good — same idiom as the attachment CAS; no new subsystem |
| Long-term maintainability | Removes the producer-count dependency for the supported path; does not cover non-queue callers | Encodes the real invariant at the state owner; survives any dispatch model |

Combination (A+B): not justified today. A already covers queue producers (the only supported path);
B adds value only for detached work or direct process_update calls, neither of which exists. Adding both
now would pay B's cost (new code path, new UX state, 6-8 tests) for a hazard that has no current source.

## 11. Minimum recommended regression tests

For Option A (if approved):
1. test_update_processor_is_serialized — build_application(...).concurrent_updates == 1 and
   app._update_processor.max_concurrent_updates == 1 (replace the truthiness assertion in
   tests/test_u04_concurrency.py:107).
2. test_two_producers_never_overlap — offline real Application (updater(None)), two concurrent
   put+join producers, recording handler ⇒ max_in-flight == 1 (the A2 exeriment as a test).
3. Keep tests/test_wp04_transient_clasification.py:112-150 unchanged (pins the poller).

For Option B (if approved):
1. Unit: stale generation rejected; current accepted; missing/evicted generation rejected (fail closed).
2. Unit: invaldate() advances the generation; token retention and other-conversation isolation hold;
   TTL/LRU unchanged.
3. Handler: two overlaping opens (S1) and refresh+open (S2) ⇒ newest listing survives.
4. Handler: late failure does not drop a newer snapshot (S5); late empty result likewise.
5. Handler: deletion during in-flight open (S7) ⇒ no snapshot resurrection.
6. Handler: "superseded" outcome (whatever UX is chosen) is explicit and does not claim success.

Existing coverage that must stay green: tests/test_file_browser.py, tests/test_bot_file_browser.py
(47), tests/test_stage2_custom_polling.py, tests/test_u04_concurrency.py,
tests/test_duplicate_update_disptach.py, tests/test_repear_plan_02_life01_f2_race.py,
tests/test_wp04_transient_clasification.py — measured 163 passed at this baseline.

## 12. Architectural compatibility

Both options keep: one bot + optional ASGI process, one SQLite owner, existing outbox/workers only, no new
queue/worker/service, no backup feature, no exactly-once claim, Autopush inactive. Option A touches only the
Application configuration in bot/app.py; Option B touches bot/file_browser.py and the two browser
handlers, both of which are the owners of this state. Neither touches bot/web/, _attachment_service /
DEF-011-A, or F-03/T-5 protected work.

## 13. Risks, assumptions and open questions
- Present-day risk: none found. The poller is the only producer; no handler detaches browser work
  (grep create_task in bot/handlers.py = none; to_thread.run_sync at bot/handlers.py:2483 is
  awaited and used only for attachment downloads); the Mini App never touches BrowserCache.
- Future maintainability risk: real and measured (C1 = 2 in-flight the moment a second producer
  exists; S1/S2/S4/S7 show concrete harm under that condition).
- F1 (this audit's main finding): the sequential policy is documented and required (OD-04) but enforced
  only by producer discipline; concurrent_updates(True) permits 256-way processing.
- F2 (pre-existing, independent of concurrency): Mini App deletion does not invaldate
  bot_data["file_browser_cache"] (bot/web/services.py:443-445,932,986); snapshots survive until
  TTL/LRU. Mini App is disabled by default.
- F3 (test weakness): tests/test_u04_concurrency.py:107 cannot detect the setting (truthiness of an
  int); no test asserts max_concurrent_updates == 1.
- F4 (precision): Application.process_update() called directly bypases the update processor;
  concurrent_updates(False) does not protect that path (measured max_in-flight=2). Only tests do this
  today.
- F5 (pre-existing, low): browse_refresh re-fetches the cache via _browser_cache(context) at
  bot/handlers.py:2120 although cache is already bound at 2107; cosmetic.
- Assumptions: single-owner bot (ALLOWED_TELEGRAM_ID), single process, one event loop; no threads run
  handler code; PTB version pinned by requirements.txt (python-telegram-bot[all]==22.8).
- Open questions for the owner: (a) is concurrent_updates(True) intentionally kept for a future
  concurrency plan, or a leftover? (b) should the Mini App deletion path invaldate the browser cache in
  the same change? (c) should the "superseded" UX in Option B be silent or show "قديمة"?

## 14. Recommendation

**RECOMMEND_OPTION_A**

Evidence:
1. The architecture explicitly requires sequential update processing (bot/app.py:75-81,
   docs/OPERATIONS_RUNBOOK.md:139-146), yet the configuration does not enforce it.
2. Serialization today depends entirely on the single producer: measured 1 for the deployed pattern
   (C0) and 2 the moment a second producer exists (C1). The dependency is not asserted anywhere (F3).
3. Option A removes that dependency for the supported dispatch path at zero behavioural cost — today's
   measured concurrency is already 1 (C0 = A3), and A1/A2/A3 stay at 1 with multiple producers.
4. Option B is the stronger invariant for the *cache*, but it is not required by any current code path and
   costs ~40 production lines, a new outcome state and 6-8 tests; it also only works if future callers use
   put_if_current (a discipline of its own).
5. A does not protect detached work or direct process_update calls (F4). Therefore Option B becomes
   required — and should be combinated with A — as soon as any of these triggers appears: (i) a second
   producer or intentional concurrent dispatch, (ii) browser listing work detached into a background task,
   (iii) direct Application.process_update() calls in production code, (iv) the Mini App starts touching
   the browser cache. Until then, A is the minimal, evidence-based safeguard.

Why not the alternatives: RECOMMEND_OPTION_B pays a larger cost for a hazard that has no current source;
RECOMMEND_COMBINATION is premature for the same reason; RECOMMEND_NO_CHANGE would leave a documented
policy unenforced and a measured 2-way concurrency reachable by a single-line future change;
INSUFICIENT_EVIDENCE does not apply — the producer inventory, the PTB semantics and the interleavings
were all verified directly.

## 15. Implementation authorization

Required. This task authorizes audit and design only. Option A implementation (configuration change,
comment update, and the two/three regression tests) must be a separate, explicitly approved task; Option B
likewise if a trigger in §14.5 appears.
## 16. Files changed by this audit

- docs/audits/OHB2-POLLER-CONCURRENCY-STRUCTURAL-SAFETY-AUDIT-REPORT.md — this report only.
- No code, test, configuration, dependency or other documentation file was created or modified.
  Exeriment scripts and logs were kept outside the repository (/tmp/ohb2-audit/).

## 17. Reproducibility

All exeriments used the pinned dependency set in an isolated venv outside the repository
(python-telegram-bot 22.8, Python 3.13.15) and no network: the Telegram bot token was never used;
ExtBot.get_me was stubbed to a local User, and browser tests used the repository's existing
tests/test_bot_file_browser.py doubles with a query double whose answer() yields (models a real
Telegram round-trip). Commands are recorded in the audit session; key results are quoted in §5, §7 and §10.

## 18. Report SHA-256

d21de995ba04222dae910b27f50527258bad02f8203ff4d31c227e268b3365de

Definition: SHA-256 of the first 28836 bytes of this file (i.e. everything above this section).
Verify with: head -c 28836 docs/audits/OHB2-POLLER-CONCURRENCY-STRUCTURAL-SAFETY-AUDIT-REPORT.md | sha256sum.
