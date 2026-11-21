# OHB2-WP07-NEW-DEF03-WATCH-UNWATCH-ATOMICITY-AND-INDEPENDENT-REVIEW

## 1) معرّف المهمة والحالة النهائية

- **Task ID:** `OHB2-WP07-NEW-DEF03-WATCH-UNWATCH-ATOMICITY-AND-INDEPENDENT-REVIEW`
- **الحالة:** **DONE** (للجزء غير المتزامن من `NEW-DEF-03` الخاص بـ watch/unwatch) —
  مع **`INDEPENDENCE_NOT_ESTABLISHED`** للمراجعة المستقلة (تفصيل في §14).
- **النطاق المُغلق:** `watch_conversation` و`unwatch_conversation` بقوا يكتبوا تغيير حالة
  المراقبة **ونتيجة** `durable_completed` في **معاملة SQLite واحدة**.
- **خارج النطاق (لم يُلمس):** تزامن `WP-07` (`OD-04`)، سياسة الإقرار، `_ACK_ELIGIBLE`،
  `list_conversations`/`_show_repos`، مسارات F-1 الستة، Mini App، ADR/المعمارية، التبعيات.

## 2) هوية المستودع وخط الأساس

| البند | القيمة |
|---|---|
| مسار الشجرة | `/workspace/project/OpenHandBot` (تحقّق بـ `git rev-parse --show-toplevel`) |
| الفرع | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (بلا تغيير) |
| upstream | **لا يوجد** (`fatal: no upstream configured`) |
| Python | `3.13.15` (`.venv/bin/python`) |
| Node | `v24.22.2` |
| Docker daemon | **غير متاح** (`/var/run/docker.sock` غير موجود) |
| `.openhands/` | موجود، **git-ignored**، لم يُلمس |

`git status --short` في بداية المهمة:

```
 M .agent/PROGRESS.md
 M bot/db.py
 M bot/handlers.py
?? docs/reviews/OHB2-REAL-EXECUTION-AND-REVIEW-BATCH-03-REPORT.md
?? docs/reviews/OHB2-WP07-F1-OPTION-C-IMPLEMENTATION-AND-INDEPENDENT-REVIEW-REPORT.md
?? tests/test_wp07_atomic_state_outcome.py
?? tests/test_wp07_f1_notification_failure.py
```

## 3) تغييرات موجودة مسبقًا مقابل تغييرات أضفتها المهمة

**موجود مسبقًا (عمل مستخدم/جلسات سابقة — محفوظ بالكامل، لم يُعَد ولا يُحذف):**
- `bot/db.py`: دوال WP-07 الذرّية من Batch 03 (`_set_awaiting_nocommit`،
  `clear_awaiting_and_record_outcome`، `set_awaiting_and_record_outcome`،
  `consume_one_shot_awaiting`) + إعادة صياغة `remove_watched` لتستخدم
  `_remove_watched_nocommit`.
- `bot/handlers.py`: تحويل 7 مسارات (`reply_prompt`، `repo_search_prompt`، `pick_repo`،
  `new_chat_no_repo`، `cancel_route`، `cancel_route_button`، فرع انتهاء المهلة في
  `handle_text`) إلى الاستدعاءات الذرّية.
- `.agent/PROGRESS.md`: مدخلان سابقان (Batch 03 + F-1 Option C).
- ملفات جديدة غير متتبَّعة: تقريران في `docs/reviews/` + `tests/test_wp07_atomic_state_outcome.py`
  + `tests/test_wp07_f1_notification_failure.py`.

**أُضيف في هذه المهمة:**

| الملف | السبب |
|---|---|
| `bot/db.py` | `_add_watched_nocommit` (استخراج جسم `add_watched`)؛ `_set_last_state_nocommit`؛ `add_watched_and_record_outcome`؛ `_remove_watched_nocommit`؛ توسيع `remove_watched` و`remove_watched_completing` بوسائط نتيجة اختيارية؛ `_remove_watched_completing_nocommit` |
| `bot/handlers.py` | `watch_conversation`/`unwatch_conversation` بقوا يمرّروا `update_id`/`now`/`outcome` للكتابة الذرّية؛ `_remove_watched_with_retry` بيقبل الوسائط الاختيارية |
| `bot/watcher.py` | `Watcher.unwatch` بيقبل `update_id`/`now`/`outcome` ويوصّلهم لمساري `remove_watched`/`remove_watched_completing` |
| `tests/test_wp07_watch_unwatch_atomicity.py` | **جديد** — 24 اختبار انحدار (مصفوفة §11) |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | **تكييف ميكانيكي فقط**: تواقيع الـ fakes `(cid, **_kw)` — **لا تغيير في أي تأكيد** |
| `tests/test_handlers.py` | **تكييف ميكانيكي فقط**: `_RemoveFailsDb.remove_watched`/`_RemoveFailsWatcher.unwatch` تقبل `**_kw` — **لا تغيير في أي تأكيد** |

## 4) سلوك معاملة `watch_conversation` الفعلي

قبل: `add_watched()` (commit #1) → `set_last_state()` (commit #2) →
`mark_durable_completed()` (commit #3) → تعديل تيليجرام.

بعد (سطر `bot/handlers.py:1392`):

```python
db.add_watched_and_record_outcome(
    conversation_id, conv.get("title", ""), q.message.chat_id,
    get_status(conv), _update_id(update), outbox.now_iso(),
    update_outcomes.DURABLE_COMPLETED,
    new_lifecycle=False, reengage=True,
)
```

`bot/db.py::add_watched_and_record_outcome` — `BEGIN IMMEDIATE` واحد يحتوي:
1. `_add_watched_nocommit(...)` — نفس جسم `add_watched` بالحرف (فحص شاهد الحذف
   `is_deleted`/`reengage`، تسوية `pending_delivery_state` عبر `_mark_pending_delivered`،
   و`INSERT ... ON CONFLICT` مع `watch_seq`).
2. `_set_last_state_nocommit(...)` — `UPDATE watched SET last_state=?`.
3. `mark_update_outcome(..., commit=False)` — نتيجة `durable_completed` (أو صف
   `update_failures` لو النتيجة غير مؤهّلة).

ثم `conn.commit()` واحد. تعديل تيليجرام (`_safe_edit`) **بعد** الـ commit، **برّه** المعاملة.

`add_watched` نفسها بقيت غلافًا رفيعًا فوق `_add_watched_nocommit` — سلوكها لم يتغيّر.

## 5) سلوك معاملة `unwatch_conversation` الفعلي

قبل: `watcher.unwatch()`/`db.remove_watched()` (commit #1) →
`mark_durable_completed()` (commit #2) → تعديل تيليجرام.

بعد (سطر `bot/handlers.py:1416-1423`): نفس سطح الاستبدال (`remover`) يُستدعى عبر
`_remove_watched_with_retry(remover, conversation_id, update_id, now, outcome)`، فيمرّر
`update_id`/`now`/`outcome` **كوسائط مفتاحية**.

- `db.remove_watched(..., update_id=, now=, outcome=)` — `BEGIN IMMEDIATE` واحد:
  `_remove_watched_nocommit` (تسجيل `pending_delivery_state` عبر
  `record_notification_sent(..., _commit=False)` ثم `DELETE FROM watched`) **+**
  `mark_update_outcome(..., commit=False)` → `conn.commit()`.
- `Watcher.unwatch(...)` — يوصّل نفس الوسائط للفرعين:
  - فرع التلميح المطابق (`remove_watched_completing`): نتيجة + تسجيل + حذف في معاملة واحدة.
  - الفرع العادي (`remove_watched`): نفس الذرّية.
  - `_marker_pending` بيتشال **بعد** نجاح الكتابة فقط (فشل ⇒ التلميح يفضل ⇒ retry آمن).

القيم الافتراضية `outcome=None` تحفظ السلوك القديم حرفيًا (إزالة بلا كتابة نتيجة) —
لذلك `bot/web/services.py` و`tests/test_watcher.py` ما اتغيّروش.

## 6) دليل المعاملة والتراجع

`tests/test_wp07_watch_unwatch_atomicity.py`:

| الاختبار | يثبت |
|---|---|
| `test_watch_commit_failure_leaves_neither_state_nor_outcome` | فشل `commit` ⇒ لا صف `watched` ولا صف `processed_updates` |
| `test_unwatch_commit_failure_leaves_state_and_outcome_untouched` | فشل `commit` ⇒ الصف باقٍ، ولا نتيجة |
| `test_watch_outcome_write_failure_rolls_back_state` | فشل كتابة النتيجة ⇒ الإضافة متراجعة |
| `test_unwatch_outcome_write_failure_rolls_back_removal` | فشل كتابة النتيجة ⇒ الإزالة متراجعة (الصف يفضل) |
| `test_watch_watcher_persistence_failure_never_records_outcome` | فشل كتابة صف المتابعة ⇒ لا نتيجة، وغير مؤهّل |
| `test_watch_pending_delivery_reconciled_in_same_transaction` | تسوية التسليم المعلّق + النتيجة في نفس المعاملة |
| `test_unwatch_completes_pending_delivery_in_same_transaction` | دليل التسليم محفوظ + النتيجة معًا |
| `test_watcher_unwatch_failure_keeps_state_and_hint` | فشل مسار التلميح ⇒ الصف والتلميح باقيان، لا نتيجة |

`test_committed_state_and_outcome_survive_reopen` يثبت الثبات بعد `close()` وإعادة فتح اتصال جديد.

## 7) التكرار وإعادة التسليم

- `test_duplicate_watch_update_no_duplicate_state`: نفس `update_id` مرتين مع
  `new_lifecycle=False` ⇒ صف واحد، **نفس** `watch_seq`، نتيجة واحدة.
- `test_duplicate_unwatch_update_consistent`: إزالة مكرّرة no-op، النتيجة ثابتة.
- `test_processed_updates_remains_authoritative_for_ack`: كتابة `FAILED_TRANSIENT` بعد
  `durable_completed` **لا** تجعل التحديث غير مؤهّل ولا تُعيده قابلًا لإعادة التنفيذ
  (`update_is_processed` يفضل True، `is_update_acknowledgment_eligible` يفضل True).

**حدّ موثّق (غير مُصلَح، خارج النطاق):** مساري `watch:`/`unwatch:` **لا** يسجّلان
«معالَج» في `processed_updates` قبل التنفيذ (لا سجل عمل دائم) — تعليق `dedupe_update`
القائم يوثّق هذا كقرار مقصود لأن الأثر upsert/حذف **idempotent**. التزام «تحديث واحد ⇒
قرار إرسال/إنشاء واحد» محفوظ؛ ما أُضيف هنا هو أن **النتيجة** تُكتب ذرّيًا مع الأثر.

## 8) سلوك فشل إشعار تيليجرام وحدّ الإقرار (F-1 Option C)

`_assert_f1_preserved` يتحقّق بعد فشل التعديل:
`update_outcome == durable_completed`، `is_update_acknowledgment_eligible is True`،
`update_is_processed is True`، و`update_failure == FAILED_TRANSIENT|FAILED_PERMANENT`.

- `test_watch_telegram_timeout_preserves_commit` / `test_unwatch_telegram_timeout_preserves_commit`:
  `TimedOut` ⇒ الالتزام المحلي والنتيجة **ثابتان**، دليل الفشل في `update_failures` فقط.
- `test_watch_telegram_bad_request_no_rollback_no_replay` /
  `test_unwatch_telegram_bad_request_no_rollback_no_replay`: `BadRequest` ⇒ لا تراجع،
  ولا إعادة تنفيذ (الديدَب مصدر الحقيقة)، دليل `FAILED_PERMANENT`.
- `test_failure_recording_failure_does_not_downgrade_committed_outcome`: تعذّر تسجيل دليل
  الفشل نفسه ⇒ النتيجة المؤهّلة **لا تتخفّض** ولا تتلوّث.

لا إعادة محاولة إشعار تلقائية، ولا استخدام لصندوق الصادر/العمال، ولا ادّعاء exactly-once
ولا ذرّية SQLite↔تيليجرام (قيود F-1 كما هي).

## 9) تأكيد سلامة F-1

- `tests/test_wp07_f1_notification_failure.py` **لم يُعدَّل** (0 تغييرات) و**14/14 ناجح**.
- المسارات الستة في `bot/handlers.py` لم تُلمس في هذه المهمة.
- `_ACK_ELIGIBLE`/`_INELIGIBLE` في `bot/update_outcomes.py` لم تُلمس.

## 10) مصفوفة اختبارات الانحدار والنتائج

`tests/test_wp07_watch_unwatch_atomicity.py` — **24 ناجح / 0 فاشل**:

| السيناريو المطلوب | الاختبار |
|---|---|
| نجاح watch (حالة+نتيجة معًا) | `test_watch_success_commits_state_and_outcome_together` |
| نجاح unwatch (إزالة+نتيجة معًا) | `test_unwatch_success_commits_state_and_outcome_together` |
| فشل معاملة watch | `test_watch_commit_failure_leaves_neither_state_nor_outcome` |
| فشل معاملة unwatch | `test_unwatch_commit_failure_leaves_state_and_outcome_untouched` |
| فشل تسجيل النتيجة ⇒ تراجع الحالة | `test_watch_outcome_write_failure_rolls_back_state`, `test_unwatch_outcome_write_failure_rolls_back_removal` |
| فشل كتابة المراقبة ⇒ لا نتيجة | `test_watch_watcher_persistence_failure_never_records_outcome` |
| تكرار watch | `test_duplicate_watch_update_no_duplicate_state` |
| تكرار unwatch | `test_duplicate_unwatch_update_consistent` |
| مهلة تعديل تيليجرام (watch/unwatch) | `test_watch_telegram_timeout_preserves_commit`, `test_unwatch_telegram_timeout_preserves_commit` |
| فشل API تيليجرام بلا إعادة تنفيذ/تراجع | `test_watch_telegram_bad_request_no_rollback_no_replay`, `test_unwatch_telegram_bad_request_no_rollback_no_replay` |
| إغلاق/إعادة فتح القاعدة | `test_committed_state_and_outcome_survive_reopen` |
| فشل تسجيل الفشل | `test_failure_recording_failure_does_not_downgrade_committed_outcome` |
| الإلغاء | `test_watch_cancellation_propagates_without_commit`, `test_unwatch_cancellation_propagates_without_commit` |
| ثوابت الاتساق | `test_no_outcome_without_watcher_row_after_failure`, `test_watch_pending_delivery_reconciled_in_same_transaction`, `test_unwatch_completes_pending_delivery_in_same_transaction` |
| المراقب (فرعا التلميح) | `test_watcher_unwatch_with_matching_hint_is_atomic`, `test_watcher_unwatch_without_hint_is_atomic`, `test_watcher_unwatch_failure_keeps_state_and_hint` |
| `processed_updates` مصدر الحقيقة | `test_processed_updates_remains_authoritative_for_ack` |

المساران مُختبَران **كلٌّ على حدة** (وليس عبر مساعد مشترك فقط)، وبعض الاختبارات تقود
`Application.process_update` الحقيقي (dedupe + handler + معالج الأخطاء) والبعض ينادي
الطبقة الذرّية مباشرةً للسيناريوهات الدقيقة.

## 11) أوامر التحقّق والنتائج

| # | الأمر | النتيجة |
|---|---|---|
| 1 | `.venv/bin/python -m pytest -q tests/test_wp07_watch_unwatch_atomicity.py` | **24 passed** |
| 2 | `.venv/bin/python -m pytest -q tests/test_wp07_atomic_state_outcome.py` | **9 passed** |
| 3 | `.venv/bin/python -m pytest -q tests/test_wp07_f1_notification_failure.py` | **14 passed** |
| 4 | `.venv/bin/python -m pytest -q` | **3332 passed, 0 failed** (خط الأساس 3308 ⇒ +24) |
| 5 | `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit **0** |
| 6 | `.venv/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High 0**، `No issues identified` |
| 7 | `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** (لم أعدّل أي ملف frontend) |
| 8 | `.venv/bin/python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities found** |
| 9 | تحقّق معزول: نسخة طازجة من `git ls-files` + الملفات المعدّلة في `/tmp/review-snapshot`، نفس الـ venv | **3332 passed, 0 failed** |

**فحوص لم تُشغَّل:** لا شيء مستثنى من بوابات المشروع القياسية. لم أُثبّت أي حزمة ولم
أُعدّل أي بيان تبعيات (`requirements*.txt` بلا تغيير).

**إصلاح انحدار أثناء العمل (موثّق بصدق):** أول تشغيل كامل أعطى
`1 failed / 3328 passed` — `test_d1_extended_transient_codes.py::test_handler_remove_watched_wrapper_retries_extended_busy`
لأن `_remove_watched_with_retry` بقى يمرّر وسائط مفتاحية لمُزيل بمعامل واحد. الإصلاح:
الرجوع للاستدعاء بمعامل واحد لما `outcome is None` (توافق خلفي)، فالعيب زال دون تعديل
أي اختبار قائم.

## 12) أدلة قتل الطفرات (mutation checks)

أُجريت يدويًا (لا أداة طفرات جديدة، لا تثبيت). كل طفرة أُعيدت للأصل وتحقّق التطابق
بالبصمة (`diff -q` = IDENTICAL):

| # | الطفرة | النتيجة |
|---|---|---|
| M1 | فصل معاملة watch: `commit` قبل كتابة النتيجة | `test_watch_outcome_write_failure_rolls_back_state` **FAILED** |
| M2 | فصل معاملة unwatch: `commit` قبل كتابة النتيجة | `test_unwatch_outcome_write_failure_rolls_back_removal` **FAILED** |
| M3 | `watch_conversation` يمرّر `update_id=None` (لا نتيجة ذرّية) | 4 اختبارات **FAILED** |
| M4 | `unwatch_conversation` يمرّر `update_id=None` | 3 اختبارات **FAILED** |
| M5 | فرع تلميح `Watcher.unwatch` يُسقط `outcome` | `test_watcher_unwatch_with_matching_hint_is_atomic` **FAILED** |

⇒ الاختبارات **غير خاوية** ومميِّزة.

## 13) المراجعة المستقلة

**الحكم: `INDEPENDENCE_NOT_ESTABLISHED`.**

لم تُستوفَ شروط الاستقلال الحقيقية في هذه البيئة:
- لا Docker daemon (`/var/run/docker.sock` غير موجود) ⇒ لا حاوية مراجع منفصلة.
- خادم الوكيل الوحيد المتاح (`localhost:60000`) يستضيف **هذه الجلسة نفسها**.
- لا ملفات تعريف LLM بديلة ولا `switch_llm` ولا اتصالات مزوّد مُهيّأة.
- أدوات الجلسات الفرعية/oracle تُنشأ **من هذه الجلسة** (ليست مُهيّأة بشكل منفصل).
- التفويض إلى السحابة = تكلفة/اعتمادات غير مُصرَّح بها لهذه المهمة.

**بديل تكميلي (ليس مراجعة مستقلة، ولا يُقدَّم كأنه كذلك):**
مراجعة ذاتية صارمة في **نسخة معزولة** (`/tmp/review-snapshot`) مع بيان بصمات:

```
205f1363aaf0b1f8173b74285e263891d333928ba480d478b6b525d4369c694b  bot/db.py
2f16182da749c1906818ed9aaf31d7de3320e45cf55b2619728dab51ea602653  bot/handlers.py
e7dbce406374de4ba053901f4ca4e6f4202444493f1edcc53e448bf6a6c52cb7  bot/watcher.py
4b03f73b0a675ef2df7b4358b7b25ade8878219f9f830a8fc442f7316c6a9476  tests/test_wp07_watch_unwatch_atomicity.py
ba2633113424432467edeff6cb74f656bb4b5fe9b762dbcc8a251799b33e07ef  tests/test_sw06_unwatch_db_failure_propagation.py
2b1f978091f45c695803a73845065073690f58f1b1c8d2f41fa38d04c1fa8ea8  tests/test_handlers.py
```

النسخة المعزولة أعادت إنتاج **3332/0**. هذه **ليست** مراجعة مستقلة.

## 14) عيوب/معايير محجوبة/حدود متبقية

1. **`INDEPENDENCE_NOT_ESTABLISHED`** — لا مراجعة مستقلة (أعلاه).
2. **تزامن `WP-07`** يظل **محجوبًا بـ `OD-04`** ولم يُلمس (لا `concurrent_updates`، لا
   تغيير في الإرسال/الاستطلاع/سياسة الإقرار العامة).
3. **حدود F-1 القائمة** تظل قائمة: عطل قبل الإرسال، وتسليم غامض. لم أُضِف أي بنية تحتية
   لحلّها، ولا أدّعي exactly-once ولا ذرّية SQLite↔تيليجرام.
4. **دليل فشل الإشعار** يُسجَّل في `update_failures`؛ مسار الفحص المدعوم هو
   `Database.update_failure(update_id)` / `update_outcome(update_id)`. **لا** أدّعي وجود
   واجهة تشغيلية/لوحة جاهزة لعرضه.
5. **بقية مواقع `NEW-DEF-03`** (مسح التنقّل، مسارات النية الدائمة، `callback_refs`)
   خارج نطاق هذه المهمة كما حُدِّد.

## 15) حالة Git النهائية

```
 M .agent/PROGRESS.md
 M bot/db.py
 M bot/handlers.py
 M bot/watcher.py
 M tests/test_handlers.py
 M tests/test_sw06_unwatch_db_failure_propagation.py
?? docs/reviews/OHB2-REAL-EXECUTION-AND-REVIEW-BATCH-03-REPORT.md
?? docs/reviews/OHB2-WP07-F1-OPTION-C-IMPLEMENTATION-AND-INDEPENDENT-REVIEW-REPORT.md
?? docs/reviews/OHB2-WP07-NEW-DEF03-WATCH-UNWATCH-ATOMICITY-AND-INDEPENDENT-REVIEW-REPORT.md
?? tests/test_wp07_atomic_state_outcome.py
?? tests/test_wp07_f1_notification_failure.py
?? tests/test_wp07_watch_unwatch_atomicity.py
```

`.openhands/` لم يُلمس (git-ignored). لم يُستخدم `git add .`/`git add -A`، ولا `reset`،
ولا `clean`، ولا أي عملية قسرية أو حذف واسع.

## 16) تأكيد عدم وجود عمليات إصدار

**لا commit، لا stage، لا push، لا PR، لا merge، لا نشر، لا إصدار، ولا تفعيل Autopush.**
لم تُجرَ أي عملية تيليجرام/OpenHands حقيقية ولم تُستخدم أي اعتمادات إنتاج. HEAD ما زال
`52e7789cc8cc97a7f7c09c9592226ab117db99a2`.
