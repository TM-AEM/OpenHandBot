# OHB2-WP01-ATTACHMENT-LIFECYCLE-IMPLEMENTATION — تقرير التنفيذ

- **Task ID:** `OHB2-WP01-ATTACHMENT-LIFECYCLE-IMPLEMENTATION`
- **التاريخ:** 2026-11-22
- **الحالة:** `DONE_WITH_NOTES` للنطاق المصرّح به فقط. **ليس** إغلاق WP-01، و**ليس** مراجعة مستقلة.
- **التفويض:** مهمة المالك الصريحة المنشورة في `USER_CONTEXT`، مع قرارَي المالك:
  - `OD-01 = Option C`: إخلاء صريح لدفعة واحدة فقط، ولـ `expired`/`rejected` فقط.
  - `OD-03 = Option A`: `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` افتراضيًا **`0`** (opt-in صريح).
- **قيود المالك:** لا حذف ملفات غير قابل للعكس، ولا تنظيف واسع، ولا تغيير في WP-01 خارج النطاق
  المصرّح، ولا commit/push/PR/merge/deploy/Autopush.

## 1. الجرد قبل التنفيذ

تمّت قراءة/فحص ما يلي قبل التعديل:

- `AGENTS.md` وقواعد العمل، و`.agent/PROGRESS.md`.
- حالة Git والفرع و`HEAD`، والتغييرات/الملفات غير المتعقّبة الموجودة مسبقًا (تم الحفاظ عليها).
- `docs/decisions/OHB2-WP01-OD01-OD03-OWNER-DECISION-RECORD.md` وملفّات تحليل القرار السابقة.
- مخطّط `attachment_batches` / `attachment_items` / `attachment_message_identity` و`settings`،
  ودوال `AttachmentBatch` / `AttachmentItem` وrow mappers.
- مسار قبول المرفقات، `classify_attachment_routing`، `has_terminal_attachment_batch`،
  `cancel_route`، والـ reaper الحالي (`bot/attachments.py`).
- `BOT_COMMANDS` وتسجيل `CommandHandler`، و`HELP_TEXT`، واختبارات دورة حياة المرفقات،
  واختبارات `ATTACHMENT_DOCUMENT_INTAKE_ENABLED`، واختبارات التكافؤ `tests/test_doc_code_parity.py`.

## 2. قرارات التصميم المنفّذة

### OD-03 — استقبال المستندات افتراضيًا متوقف

- `Config.attachment_document_intake_enabled` أصبح `False` افتراضيًا.
- `load_config` يستخدم `_parse_bool(env, "ATTACHMENT_DOCUMENT_INTAKE_ENABLED", False)`؛
  `=1` فقط هو التفعيل الصريح، والقيم غير الصالحة تُرفض كما كان.
- عند التعطيل: `handle_attachment` يرفض **قبل** `get_file`/تنزيل/صف/ملف/نداء OpenHands/سجل outbox،
  ويُسجّل `explicitly_ignored`، ويُظهر رسالة عربية صادقة.
- تم تحديث `.env.example` و`README.md` و`docs/OPERATIONS_RUNBOOK.md` و`docs/ZERO_TOUCH_STARTUP.md`.

### OD-01 Option C — إخلاء نهائي صريح لدفعة واحدة

- أُضيف `ATTACHMENT_BATCH_CLEARABLE_STATUSES = {expired, rejected}`.
- علامة الإخلاء تُخزَّن في جدول `settings` الموجود، بمفتاح لكل دفعة:
  `attachment_terminal_clearance:<batch_id>`، والقيمة = `telegram_id` للمالك.
  لا يوجد مخطّط جديد ولا migration مدمّر، ودليل الهوية `attachment_message_identity` لا يُمسّ.
- `clear_attachment_terminal_batch`:
  - يتحقّق من الملكية (`batch_id` + `telegram_id`).
  - يقبل `expired`/`rejected` فقط.
  - يرفض `delivered`/`failed`/`pending`/`intent_recorded`/أي حالة أخرى بـ `not_eligible`.
  - يكتب العلامة والنتيجة الدائمة (`durable_completed`) في **نفس معاملة** `BEGIN IMMEDIATE`.
  - idempotent: إعادة الإخلاء ترجّع `already_cleared`.
  - `update_id` مكرّر ⇒ `duplicate` بلا تغيير.
  - أي فشل قاعدة ⇒ rollback ورفع الاستثناء؛ لا ردّ نجاح.
  - لا يحذف أي ملف أو صف أو دليل هوية.
- `classify_attachment_routing` لا يتجاهل إلا الدفعات `expired`/`rejected` التي عليها إخلاء صريح
  للمالك. `delivered`/`failed` لا تُبرَّآن أبدًا. `TERMINAL_ASSOCIATED` يظل fail-closed حتى لو
  الدفعة مُبرَّأة؛ و`TERMINAL_UNPROVEN`/`UNRESOLVED`/`MULTI_LIVE`/`EXPIRED_PENDING`/الحالات
  المجهولة تظل محجوبة/فاشلة مغلقة.
- `/cancel` **لم يتغيّر**: لا يمسح الحجب النهائي، ولا يحذف ملفات/صفوف. إلغاء الدفعة النشطة
  يبقى **BLOCKED** لأن تحويلها إلى حالة نهائية سيسمح للـ reaper الحالي بحذف البايتات، ولا يوجد
  تصريح لحذف غير قابل للعكس.

### الأوامر والرسائل

- أُضيف `/attachments` لعرض بيانات وصفية مقيّدة بالمالك فقط (المعرّف/الحالة/المحادثة، بلا نص أو مسار ملف).
- أُضيف `/attachments_clear <batch_id> confirm`؛ يتطلّب معرّفًا صريحًا وكلمة `confirm`.
- أُضيفت الأوامر إلى `BOT_COMMANDS` وتسجيل `CommandHandler` و`HELP_TEXT`، ووثّقها
  `docs/OPERATIONS_RUNBOOK.md`.
- الرسائل صارت صادقة:
  - القبول لا يقول «تم الحفظ محليًا» إلا بعد `AcceptOutcome.STORED`.
  - التكرار له نص منفصل: «كان متسجل قبل كده؛ مفيش نسخة جديدة».
  - رسالة التعطيل تقول صراحةً إنه لا يتم حفظ أو إرسال أي ملف.
  - رفض الوسائط غير المدعومة لا يعرض خيار «مستند» إلا إذا كان الاستقبال مفعّلًا صراحةً.

## 3. الملفات المتغيرة

### كود التطبيق

- `bot/config.py` — افتراضي OD-03 `False` في `Config` و`load_config`.
- `bot/db.py` — ثوابت الإخلاء، استعلامات مقيّدة بالمالك، `clear_attachment_terminal_batch`،
  `is_attachment_terminal_cleared`، واستثناء الإخلاء في `classify_attachment_routing`.
- `bot/handlers.py` — `/attachments`، `/attachments_clear`، رسائل مرفقات صادقة وسياسة-aware،
  وتحديث `HELP_TEXT`.
- `bot/app.py` — إضافة الأمرين إلى `BOT_COMMANDS` وتسجيلهما فقط. (يوجد في نفس الملف تغيير
  `concurrent_updates` سابق غير تابع لهذه المهمة؛ تم الحفاظ عليه كما هو.)

### إعدادات/توثيق

- `.env.example` — `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0`.
- `README.md` — توضيح الافتراضي المعطّل والتفعيل الصريح.
- `docs/OPERATIONS_RUNBOOK.md` — الافتراضي + أوامر المرفقات وسلوك الإخلاء.
- `docs/ZERO_TOUCH_STARTUP.md` — توضيح الافتراضي `0`.
- `.agent/PROGRESS.md` — سجل التنفيذ والإكمال.

### الاختبارات

- `tests/test_wp01_attachment_lifecycle.py` — **جديد**، 25 دالة اختبار / 28 حالة بعد
  الـ parametrization: الإخلاء، الرفض، الملكية، idempotency، التكرار، rollback، بقاء
  `TERMINAL_ASSOCIATED`، الحالات المجهولة، عدم حذف الملفات/الصفوف، `/cancel`، الأوامر،
  والرسائل.
- `tests/test_attachment_batch_lifecycle_a2.py` — opt-in صريح في harness دورة الحياة،
  وتوقّع نص التكرار/الرفض الجديد.
- `tests/test_repair_plan_02_life03_intake_kill_switch.py` — الافتراضي أصبح معطّلًا،
  والتفعيل الصريح مُختبَر، و`.env.example` يوثّق `=0`.

## 4. معايير القبول

| المعيار | النتيجة | الدليل |
| --- | --- | --- |
| التثبيتات الجديدة: استقبال المستندات معطّل افتراضيًا، والتفعيل `=1` صريح | **متحقّق** | `Config`/`load_config` + `.env.example=0` + اختبارات intake |
| الإخلاء صريح، لدفعة واحدة، دائم، idempotent، ومقصور على `expired`/`rejected` | **متحقّق** | `clear_attachment_terminal_batch` + 28 حالة اختبار |
| `delivered`/`failed`/`TERMINAL_ASSOCIATED`/`TERMINAL_UNPROVEN`/unknown/unresolved/live/expired-pending تظل fail-closed | **متحقّق** | اختبارات الحالات + classification |
| `/cancel` لا يمسح الحجب النهائي، ولا يحذف ملفات/صفوف | **متحقّق** | اختبارا `/cancel`؛ الكود لم يتغيّر |
| رسائل المرفقات صادقة وpolicy-aware | **متحقّق** | اختبارات الرسائل + تحديث النصوص |
| لا تغيير في Mini App/dependencies/CI/concurrency أو WP-01 خارج النطاق | **متحقّق** | لا تعديلات في `bot/web/*` أو dependency/CI؛ تغيير `bot/app.py` السابق محفوظ |

## 5. التحقّق المنفَّذ

تم إنشاء بيئة مؤقتة خارج الريبو:
`/tmp/ohb2-venv`، وتثبيت `requirements-dev.txt` بنجاح، ثم:

```text
python -m pytest -q
3545 passed, 74 warnings in 185.09s
```

```text
python -m pytest -q tests/test_wp01_attachment_lifecycle.py \
  tests/test_repair_plan_02_life03_intake_kill_switch.py \
  tests/test_attachment_batch_lifecycle_a2.py
101 passed in 5.14s
```

```text
python -m pytest -q tests/test_wp01_attachment_lifecycle.py
28 passed in 1.91s
```

```text
python -m pyflakes bot/ automation/ tools/ main.py tests/
exit 0 — no output
```

```text
python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
No issues identified.
High: 0 | Medium: 19 | Low: 5 | exit 0
```

```text
python -m pip_audit -r requirements-dev.txt
No known vulnerabilities found
exit 0
```

```text
node --test tests/frontend/*.test.js
tests 280 | pass 280 | fail 0 | exit 0
```

```text
git diff --check
exit 0

python -m compileall -q bot tests
exit 0
```

كما نجح smoke مستقل لقاعدة البيانات (`DB_CLEARANCE_SMOKE_OK`) في:
الإخلاء، الرفض، الملكية، idempotency، forged clearance، بقاء identity، والحالة المجهولة.
ونجح smoke لافتراضي الإعداد (`CONFIG_DEFAULT_SMOKE_OK`) مع stubs للتبعيات الاختيارية غير المثبّتة
في بيئة التحقق المؤقتة.

> **ملاحظة صدق:** التشغيل الكامل الأول كشف توقّعًا قديمًا واحدًا في harness مُفعّل صراحةً
> (نص رفض الصور كان يتوقّع النسخة المحايدة بدل نسخة «المستند المفعّل»). تم تحديث التوقّع،
> ثم نجح التشغيل الكامل أعلاه. لا توجد فشولات متبقّية.

## 6. ما لم يُنفَّذ / محجوب

- **إلغاء الدفعة النشطة عبر `/cancel`: BLOCKED / لم يُغيَّر.** السبب: تحويلها إلى حالة نهائية
  سيسمح للـ reaper الحالي بحذف البايتات؛ المالك منع الحذف غير القابل للعكس. `/cancel` الحالي
  يمسح التوجيه فقط ولا يحذف شيئًا.
- **لا حذف تلقائي جديد للـ expired/rejected.** لم يُضَف أي حذف. الـ reaper القائم (A4) لم يُعدَّل،
  ومسار الإخلاء الجديد لا يستدعيه ولا يحذف ملفات.
- **Mini App / رفع بعيد / P0:** خارج النطاق ولم يُلمس.
- **مراجعة مستقلة:** لم تُطلب ولم تُدّعى.
- **إغلاق WP-01:** لم يحدث؛ هذا تنفيذ للنطاق المصرّح فقط.

## 7. السلامة والحفاظ على الحالة

- لا commit، لا stage، لا push، لا PR، لا merge، لا deployment، لا Autopush.
- لا `git reset`/`restore`/`clean`/`force-push`، ولا حذف ملفات أو قواعد بيانات.
- كل التغييرات/الملفات غير المتعقّبة السابقة محفوظة؛ لم يُعَد كتابة أي منها.
- لا اتصالات Telegram أو OpenHands إنتاجية.
- لا أسرار أو tokens في التقرير أو الاختبارات.

## 8. الافتراضات والقرارات

- اعتُبر `settings` الجدول المناسب لعلامة الإخلاء الدائمة، لأنه موجود أصلًا ويحفظ دليل الهوية
  منفصلًا (`attachment_message_identity`).
- اعتُبر `expired`/`rejected` هما الحالتان الوحيدتان القابلتان للإخلاء، تطبيقًا حرفيًا لـ OD-01 Option C.
- اعتُبر أن `TERMINAL_ASSOCIATED` يجب أن يظل محجوبًا حتى بعد إخلاء الدفعة، لأن دليل الهوية نفسه
  يمنع السقوط لمسار البرومت.
- لم يُضَف status جديد للدفعات (مثل `cancelled`) لأن ذلك يوسّع المخطّط/الـ reaper ويحتاج قرارًا
  معماريًا مستقلًا.

## 9. الخطوة التالية المقترحة

قرار مالك مستقل لتصميم إلغاء دفعة نشطة **بلا حذف غير قابل للعكس** (حالة `cancelled` صريحة +
تعليم الـ reaper بتجاهلها)، أو تأكيد أن `/cancel` الحالي يكفي. هذا خارج نطاق هذه المهمة.
