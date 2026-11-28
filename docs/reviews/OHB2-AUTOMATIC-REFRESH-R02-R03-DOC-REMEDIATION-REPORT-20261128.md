# OHB2-AUTOMATIC-REFRESH-R02-R03-DOC-REMEDIATION-REPORT-20261128

## 1. الحالة والهدف

- **Task ID:** `OHB2-AUTOMATIC-REFRESH-R02-R03-DOC-REMEDIATION`
- **الحالة النهائية:** **DONE — READY FOR INDEPENDENT REVIEW**
- تمت معالجة findings المراجعة السابقة:
  - `REV-R03-01` — lease cleanup عند الإلغاء/الخطأ المبكر.
  - `REV-R02-01` — تصنيف استنفاد BUSY/LOCKED كـ transient.
  - `REV-DOC-01` — توثيق migration `conversation_views` بدقة.
- لم يتم push/PR/merge/deploy/release، ولم يتم staging أو commit per تعليمات المهمة.

## 2. Baseline وidentifiers

- Repository: `/workspace/project/OpenHandBot`
- Branch: `agent/automatic-conversation-refresh`
- **Baseline HEAD:** `a123a01f33091ce069c6916242a27df98cb0e147`
- **Baseline tree:** `f0f0e5ddacc6e10642876eb99fd3bc3959869c15`
- **Baseline parent:** `71f65cc90a9bf53a0f70d3689ab9ef571187fdab`
- Baseline target commit مؤكد محليًا، وكان HEAD عند بدء العمل.
- **Final commit:** **NONE** — لا يوجد commit جديد لأن المهمة تمنع الـ commit.
- **Final tree:** لا يوجد final commit/tree identifier؛ HEAD/tree ما زالا baseline. تغييرات implementation موجودة كـ working-tree modifications/untracked files.
- Final changed-file blob hashes:
  - `bot/refresh.py`: `483deb435ef55a87548526b3c695f4eb4ff4717b`
  - `bot/handlers.py`: `205c0783671a82caa5e555a9c68517f7544154fb`
  - `docs/OPERATIONS_RUNBOOK.md`: `62b843a6a134f8aac07b2360b785fccb76ec2c9a`
  - `tests/test_automatic_refresh_r02_r03_doc_remediation.py`: `295550f451d50d378dbfc6dfac1d60ce87846ed0`
- Baseline working tree قبل التغييرات كان فيه ملفان untracked فقط:
  - `docs/reviews/OHB2-AUTOMATIC-CONVERSATION-REFRESH-REMEDIATION-INDEPENDENT-REVIEW-20261128.md`
  - `docs/reviews/OHB2-AUTOMATIC-REFRESH-R01-R04-INDEPENDENT-REVIEW-20261128.md`
  لم يتم تعديلهما أو حذفهما.

## 3. REV-R03-01 — Lease cleanup

### التغيير

- `bot/refresh.py::refresh` أصبح ownership boundary واضحة:
  - يحصل على lease مرة واحدة عبر `_ensure_lease`.
  - يستدعي `_refresh_leased` داخل `try`.
  - في `finally` يستدعي `_release(leased_target)` دائمًا.
- `_refresh_leased` يحتفظ بمنطق refresh الأصلي: `_current_target`, API fetch, edit lock, Telegram edit, `_finish`/`_defer`/`_deactivate`.
- `_release` أصبح يرجع bool ويطبع:
  - `WARNING` عند فشل DB cleanup مع نص صريح أن الحجز **لم يُؤكَّد تحريره**.
  - `DEBUG` فقط عند no-op متوقع (lease انتهى أو استُبدل).
- `release_conversation_view_lease` نفسه يطابق `view_id + lease_token` فقط، ولا يغيّر `active`, `superseded`, `next_check_at`, `target_token`, أو `generation`.

### السلوك بعد التغيير

- Cancellation أثناء `authorize_conversation_detailed` أو `get_last_exchange` أو `_edit` أو انتظار edit lock:
  - `CancelledError` يُعاد رفعه (لا swallowing).
  - `finally` يحرر الـ lease المملوك قبل خروج `refresh`.
- خطأ DB بعد claim:
  - `finally` يحرر الـ lease ثم يعيد رفع الخطأ (أو يعود بعد `_defer` حيث ينطبق).
- Early return بسبب `_current_target is None`:
  - `finally` يحرر الـ lease.
- Lease استُبدل بـ token أحدث:
  - `release` CAS لا يمس الـ token الجديد.
- Target اتعمل له supersede أو delete:
  - `release` لا يعيده active ولا ينشئه من جديد.
- فشل cleanup:
  - لا يُقدَّم كنجاح؛ warning + False؛ lease القديم يبقى حتى انتهاء صلاحيته بدلًا من ادعاء تحرير كاذب.

### Regression tests (`tests/test_automatic_refresh_r02_r03_doc_remediation.py`)

- `test_cancellation_immediately_after_claim_releases_lease`
- `test_cancellation_during_metadata_releases_lease_and_allows_next_claim`
- `test_db_error_immediately_after_claim_releases_lease`
- `test_db_error_during_early_validation_releases_lease`
- `test_db_error_during_post_fetch_validation_cleans_lease`
- `test_normal_unexpected_exception_cleans_lease_after_defer`
- `test_cleanup_does_not_release_a_newer_lease`
- `test_cleanup_after_supersede_preserves_superseded_state`
- `test_cleanup_after_delete_does_not_recreate_target`
- `test_cleanup_failure_is_observable_and_does_not_corrupt_newer_lease`

كل الاختبارات تستخدم `Database` على ملف SQLite مؤقت وتتحقق من الصف المحفوظ (`lease_token`, `lease_until`, `active`, `superseded`, وجود/غياب الصف)، وليس return values فقط. اختبارات cancellation/DB-error تؤكد أن `_claim` التالي ينجح بدون انتظار timeout الـ lease.

## 4. REV-R02-01 — تصنيف BUSY/LOCKED

### التغيير

- `RefreshInvalidationError` أصبح يحمل `transient: bool` (default `False`).
- `supersede_message_with_retry`:
  - خطأ غير SQLite-transient ⇒ `transient=False` فورًا (permanent/unexpected).
  - BUSY/LOCKED قبل نهاية الميزانية ⇒ retry كما هو.
  - BUSY/LOCKED بعد استنفاد `DEDUPE_RETRY_DELAYS` ⇒ `RefreshInvalidationError(..., transient=True)`.
- عدد المحاولات لم يتغير: محاولة أولى + 3 إعادة = **4 محاولات** كحد أقصى.
- `_classify_failure` في `bot/handlers.py` يقرأ `transient=True` من exception ويُرجع `FAILED_TRANSIENT`؛ غير ذلك يظل permanent.
- لا يتم استبدال الشاشة عند فشل الإلغاء؛ الـ handler يظل fail-closed.

### Regression tests

- `test_transient_invalidation_succeeds_within_budget` — BUSY وLOCKED، نجاح بعد محاولتين فاشلتين، ثم `changed == 1`.
- `test_transient_invalidation_exhaustion_is_transient_and_blocks_screen` — BUSY/LOCKED، 4 محاولات، `transient is True`, `_classify_failure == FAILED_TRANSIENT`, `q.edits == []`, target ما زال active/non-superseded.
- `test_permanent_invalidation_failure_is_not_transient` — `disk I/O error`، محاولة واحدة، `transient is False`, `FAILED_PERMANENT`, no screen.
- `test_unexpected_database_error_is_not_silently_successful` — `DatabaseError` غير عابر ⇒ exception، no screen، permanent.
- **تأكيد عدم الـ tight loop:** الاختبارات تتحقق من `calls == 4` بعد استنفاد الميزانية.

## 5. REV-DOC-01 — Migration documentation

تم تعديل `docs/OPERATIONS_RUNBOOK.md` ليفرّق بين:

- **ترحيلات إضافية:** `ALTER TABLE … ADD COLUMN` و`CREATE TABLE IF NOT EXISTS`.
- **Rebuild لجدول `conversation_views` القديم:**
  - condition: عدم وجود `view_id`.
  - `BEGIN IMMEDIATE`.
  - drop الفهارس، rename إلى `conversation_views_legacy`، create الجدول الجديد، copy كل الصفوف مع `view_id`/`target_token` جديدين، `lease_token=NULL`، copy `lease_until` لو موجود.
  - dedupe لنفس `(chat_id, message_id)`: الأحدث بـ `updated_at` ثم `view_id` يظل active؛ الأقدم يصبح `active=0, superseded=1, next_check_at=NULL` ولا يُحذف في خطوة النسخ.
  - `DROP TABLE conversation_views_legacy` بعد نجاح النسخ.
  - rollback عند exception؛ commit بعد نجاح كل الخطوات؛ لا ادعاء بحفظ الجدول القديم بعد commit.
  - retention inactive الأقدم من 30 يومًا ليست جزءًا من migration.
  - verification tests المذكورة، وفحص `PRAGMA table_info(conversation_views)`.

أضفت كذلك test `test_legacy_conversation_view_migration_rolls_back_on_failure`:
- ينشئ old schema فعلية.
- يجبر فشل SQL داخل `_migrate`.
- يفتح الملف بعد الفشل ويتحقق من بقاء old columns والصف، وعدم بقاء `conversation_views_legacy`.

لم يتم تغيير migration behavior؛ التعديل توثيقي فقط.

## 6. الملفات المتغيرة/المضافة

| الملف | الحالة | السبب |
|---|---|---|
| `bot/refresh.py` | modified | lease finalization + transient classification metadata |
| `bot/handlers.py` | modified | احترام `RefreshInvalidationError.transient` في classifier |
| `docs/OPERATIONS_RUNBOOK.md` | modified | تصحيح وصف migration والـ rebuild |
| `tests/test_automatic_refresh_r02_r03_doc_remediation.py` | new | 17 regression tests for R-02/R-03/DOC |
| `docs/reviews/OHB2-AUTOMATIC-REFRESH-R02-R03-DOC-REMEDIATION-REPORT-20261128.md` | new | هذا التقرير |

لا تعديل على أي feature أو architecture غير مرتبطة.

## 7. Verification — exact results

كل الأوامر من `/workspace/project/OpenHandBot` باستخدام `.venv/bin/python` (Python 3.13.15) وNode 24.22.2.

| # | الأمر | النتيجة |
|---|---|---|
| 1 | `.venv/bin/python -m pytest -q tests/test_automatic_refresh_r02_r03_doc_remediation.py` | **17 passed**, 1.89s |
| 2 | `.venv/bin/python -m pytest -q tests/test_automatic_conversation_refresh.py tests/test_automatic_conversation_refresh_remediation.py tests/test_automatic_refresh_r01_r04_remediation.py tests/test_automatic_refresh_r02_r03_doc_remediation.py` | **81 passed**, 3 warnings, 8.30s |
| 3 | `.venv/bin/python -m pytest -q tests/test_doc_code_parity.py tests/test_handlers.py tests/test_db.py tests/test_db_maintenance.py tests/test_sender.py tests/test_outbox.py tests/test_files_service.py tests/test_wp05_worker_correctness.py tests/test_manual_polling_outcome_and_ack.py tests/test_wp04_transient_classification.py` | **361 passed**, 2 warnings, 24.33s |
| 4 | `.venv/bin/python -m pytest -q` | **4424 passed**, 0 failed, 77 warnings, 348.44s |
| 5 | `node --test tests/frontend/*.test.js` | **272 passed**, 0 failed, 819ms |
| 6 | `npm run lint` | exit 0 (`tsc --noEmit`) |
| 7 | `npm run build` | exit 0؛ Vite warning غير حاصر |
| 8 | `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit 0، **0 findings** |
| 9 | `.venv/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | exit 0؛ **High 0**, Low 7, Medium 28 |
| 10 | `.venv/bin/python -m pip_audit -r requirements-dev.txt` | exit 0؛ **No known vulnerabilities found** |
| 11 | migration + parity smoke: `.venv/bin/python -m pytest -q tests/test_doc_code_parity.py tests/test_automatic_conversation_refresh_remediation.py::test_old_conversation_view_schema_is_migrated tests/test_automatic_refresh_r01_r04_remediation.py::test_migration_keeps_newest_updated_at_not_insertion_order tests/test_automatic_conversation_refresh_remediation.py::test_deletion_removes_view_rows_and_retention_prunes_only_inactive` | **19 passed**, 0.61s |
| 12 | `git --no-pager diff --check` | exit 0, clean |

- **Skipped/failed:** لم تظهر tests failed أو skipped في full suite/frontend runs المذكورة.
- **Warnings:** 77 warnings في full suite (pre-existing deprecations)، و3 warnings في focused refresh.
- **Migration rollback test** نجح داخل new test file.

## 8. Python 3.11 وCI وlive

- **Python 3.11:** **NOT RUN** — `python3.11` غير موجود في البيئة (`NOT_FOUND`)، ولم يتم تثبيت packages أو تغيير environment.
- **CI:** **NOT RUN / no target CI evidence** — لا يوجد تشغيل CI لهذا working tree/commit. لم يتم push؛ لذلك لا يصح claim CI pass. baseline CI runs على `main` لا تخص هذا الـ working tree.
- **Live Telegram/OpenHands:** **NOT RUN** — لا مكالمات API حقيقية أو secrets.
- **Third-party independence:** NOT ESTABLISHED — هذه implementation session ليست مراجعة مستقلة. المراجعة المستقلة يجب أن تجري لاحقًا في clone/runtime/session منفصل.

## 9. Remaining risks / follow-up

- لا يوجد blocker معروف لتحقيق R-03 cleanup أو R-02 classification في الاختبارات المحلية.
- **Limitations:**
  - Python 3.11 غير متاح محليًا.
  - CI لم يُشغّل هذا التغيير.
  - Cleanup failure بعد DB locked/disk error يظل محتملًا؛ هو مسجّل وobservable، والـ lease القديم ينتظر timeout بدلًا من ادعاء تحرير كاذب. لا retry cleanup غير محدود.
  - Migration rollback test يفترض SQLite transactional DDL كما في البيئة الحالية؛ راجعه في Python 3.11/CI عند أول تشغيل.
  - لا live integration.
- **Follow-up:** independent clone/runtime review على working-tree snapshot أو commit لاحق بعد push/commit المصرح به من المالك. لا يتم push أو CI trigger في هذه المهمة.

## 10. Git/publication status

- **لا stage، لا commit، لا push، لا PR، لا merge، لا deploy، لا release، لا Autopush.**
- لا fetch/pull/switch/reset/clean/stash.
- الملفات الحالية في working tree:
  - modified: `bot/handlers.py`, `bot/refresh.py`, `docs/OPERATIONS_RUNBOOK.md`
  - new untracked: `tests/test_automatic_refresh_r02_r03_doc_remediation.py`, هذا التقرير.
  - pre-existing untracked محفوظة: ملفا المراجعة السابقان.
- لا تغييرات staged.
- Baseline commit/tree ما زالا `a123a01...` / `f0f0e5d...`؛ لا final commit/tree لأن الـ commit ممنوع.
