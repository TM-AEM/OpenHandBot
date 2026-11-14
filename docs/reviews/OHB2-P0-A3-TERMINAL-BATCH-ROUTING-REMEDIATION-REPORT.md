# OHB2-P0-A3-TERMINAL-BATCH-ROUTING-COMPLETE-REMEDIATION — تقرير الإصلاح

> هذا التقرير من إعداد وكيل ذكاء اصطناعي (OpenHands) نيابةً عن المالك. الحالة:
> **PARTIAL** — F2 مُصلَح ومُتحقَّق؛ F1 **مُعلَّق (BLOCKED)** بانتظار قرار مالك.
> **لا** commit / push / PR / merge / deploy / publish (حسب تعليمات المهمة).

## 1. النطاق ومعايير القبول

عيبان في بوابة توجيه النصّ لدفعات المرفقات (A3):
- **F2**: حالة دفعة مرفقات **مجهولة/غير مدعومة** (خارج `ATTACHMENT_BATCH_STATUSES` أو NULL)
  كانت تُصنَّف `NONE` ⇒ سقوط صامت لمسار البرومت/`outbox` (**fail-open**).
- **F1**: نصّ قد يخصّ دفعة **نهائية** (`delivered`/`expired`/`rejected`/`failed`) قد يسقط
  لمسار البرومت/`outbox` بلا إثبات أنه برومت جديد فعلًا.

معايير القبول (F2): الحالة المجهولة ⇒ نتيجة **fail-closed** أو استثناء سلامة **ينتشر**؛
**ممنوع** التوجيه لـ `_send_prompt`/`outbox`؛ **ممنوع** تحويل الخطأ التقني لنجاح/رفض مؤهّل.
معايير F1: **لا يمكن** تحقيقها بلا آلية هوية رسالة↔دفعة (غير موجودة) ⇒ تحتاج قرار مالك.

## 2. ما نُفِّذ

### F2 — fail-closed للحالة المجهولة (`bot/db.py`)
- `AttachmentBatchIntegrityError(RuntimeError)`: استثناء صريح للحالة المجهولة/التالفة.
- `has_unknown_attachment_batch_status(telegram_id)`: `SELECT DISTINCT status ... WHERE telegram_id=?`
  ثم مقارنة **بايثون** ضد `ATTACHMENT_BATCH_STATUSES` (مصدر واحد، بلا SQL مُركَّب، لا انحراف).
  `None not in set ⇒ True` (تغطية NULL ضمنية)؛ صفر صفوف ⇒ `False` (غياب مشروع ⇒ `NONE`).
  نطاق **المالك** إلزامي (عزل بين المستخدمين). قراءة فقط. أخطاء القراءة **تنتشر** (لا تُكتم).
- `classify_attachment_routing`: تفحص الحالة المجهولة **أولًا** (قبل `UNRESOLVED`/`LIVE`/...)
  ⇒ ترفع `AttachmentBatchIntegrityError`. للحالات **الصحيحة** الفحص no-op ⇒ لا تغيير سلوك.
- إزالة SQL ديناميكي كان يسبّب B608 (bandit Medium) ⇒ رجعنا لخط الأساس (Medium=17، High=0).

### سلوك المسار عند الحالة المجهولة (تحقّق)
- `handle_text` بينادي `_handle_accompanying_text` **بلا شرط** (قبل أي فحص route/awaiting).
- `_handle_accompanying_text` بينادي `classify_attachment_routing` **بلا شرط**.
- الاستثناء ينتشر لمعالج PTB (`handle_processing_error` → `record_update_failure`) ⇒
  `FAILED_PERMANENT` **غير مؤهّل للإقرار**، **صفر** صفوف `outbox`، **صفر** نداءات بعيدة.

### F1 — مُعلَّق (BLOCKED)
لا آلية **مُصرَّح بها** توفر هوية رسالة↔دفعة (لا `message_id`/`update_id` على الدفعات). الإصلاح
الكامل يتطلب قرار مالك (نطاق + آلية هوية). **لم** نغيّر سلوك الحالات النهائية، وأضفنا اختبارات
`xfail(strict=True)` توثّق الثابتة المطلوبة (نصّ دفعة نهائية ما يوصلش لـoutbox).

## 3. الاختبارات
- ملف جديد `tests/test_attachment_terminal_routing_remediation.py`: **24 pass / 7 xfail**
  (كان 23/6). الاختبارات على حدّ `Application.process_update` الحقيقي (SQLite حقيقي + عميل وهمي).
- إضافات بعد المراجعة العدائية: `test_f2_unknown_status_fails_closed_without_any_route`
  (يثبت F2-2: بلا route + حالة مجهولة ⇒ fail-closed)، و
  `test_f2_unknown_status_boundary_is_fail_closed_until_resolved` (يوثّق F2-1).
- تحويل كل `xfail` إلى `strict=True`، وتقوية `test_race_...` من OR ضعيف إلى تأكيدات قوية.

## 4. التحقّق (النتائج الفعلية)
| الأمر | قبل | بعد |
|---|---|---|
| `python -m pytest -q` | 2774 passed | **2798 passed, 7 xfailed** |
| `pytest tests/test_attachment_terminal_routing_remediation.py -q` | — | 24 passed, 7 xfailed |
| `python -m pyflakes bot/ automation/ main.py tests/` | 0 | **0** |
| `python -m bandit -r bot/ automation/ main.py -lll -s B613` | High=0/Med=17 | **High=0 / Medium=17** |
| `node --test tests/frontend/*.test.js` | 219 | **219** |

## 5. المراجعة العدائية المستقلة (جلستان، Cloud API)
- **الجولة 1** (conv `fb72c9ca…`): `NEEDS_REVISION` — F2-1 (حجب head-of-line)، F2-2 (فعّالية
  الفحص غير مُثبَتة)، F1-1 (F1 مفتوح، تأكيد صادق)، F1-2 (ملاحظات اختبار).
- **الجولة 2** (conv `bd0e15dc…`): `NEEDS_REVISION` — لكن **أكّد موقفنا التقني**:
  - F2-2 **مُدحَض** (الفحص بلا شرط؛ متوافق مع wiring الموجود).
  - F2-1 **متأصّل** في قاعدة fail-closed المطلوبة، مطابق لأي فشل دائم ⇒ **ليس عيبًا في الإصلاح**.
  - لا انحدار A0/A1/A2/A3 للحالات الصحيحة. الاختبارات على الحدّ الحقيقي، `xfail(strict=True)`.
  - **BLOCKING-1**: القطعة غير مُلتزَمة (لا يستطيع التحقق) — يتعارض مع تعليمة «NO commit».
  - **BLOCKING-2**: F1 ما زال مفتوحًا بلا تنازل مالك صريح.
  - ملاحظتان non-blocking: (5) البوابة على مسار النصّ فقط؛ (6) «الحجب ينفكّ بعد الإصلاح» — تحقّقنا
    منه: `advance_offset` بيتقدّم **بس** مع الحدّ المؤهّل ⇒ التحديث الفاشل يُعاد تسليمه ويُعالج،
    وبعد إصلاح البيانات ينجح والحدّ يتقدّم.

## 6. قرارات وافتراضات (بلا سؤال)
1. الحالة المجهولة ⇒ استثناء منتشر (fail-closed) كما تنصّ المهمة؛ لم نُحوّله لنجاح/رفض مؤهّل.
2. F2-1 (حجب الحدّ) **مقبول متأصّل**: إصلاحه يتطلب (أ) نتيجة مؤهّلة لتلف بيانات (ممنوع صراحةً)
   أو (ب) تغيير حدّ D-30 (تغيير واسع غير مُصرَّح). لم نفعل أيهما.
3. البوابة **نصّية فقط** (نفس نطاق A3 الحالي)؛ مسارات غير النصّ/الـ callbacks خارج نطاق F2.
4. `xfail(strict=True)` عمدًا: أي `xpass` مستقبلي يفشل الـ suite (فضح صريح بدل تمرير صامت).
5. **لم** نُلتزم/نَدفع أي شيء (تعليمة صريحة) ⇒ BLOCKING-1 (عدم قابلية التحقق) متأصّل في تعليمة
   المهمة، وليس عيبًا تقنيًا.

## 7. غير مُتحقَّق / غير مُنفَّذ / ما زال مكسورًا
- **F1**: مفتوح (BLOCKED) — لا إصلاح، بلا قرار مالك. موثّق بـ 7 اختبارات `xfail(strict=True)`.
- **F2-1**: حجب head-of-line عند فشل دائم (سلوك fail-closed متأصّل ومقبول، موثّق).
- القطعة **غير مُلتزَمة** (تعليمة المهمة) ⇒ لا يمكن للمراجع التحقق تنفيذيًّا.
- فشل أساسي **سابق وغير مرتبط**: `tests/test_deploy_manifest.py` (لا علاقة بـ A3؛ غير موجود في
  خط الأساس لدينا الذي مرّ بالكامل: 2798 passed).

## 8. الفرع والالتزامات
- الفرع: `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`؛ HEAD `907b20de…`؛ origin `a29164ff…`.
- **لا** commits جديدة (حسب التعليمة). الملفات المتغيّرة (لنا): `bot/db.py` + ملف الاختبار الجديد.

## 9. الخطوة التالية المقترحة (واحدة)
قرار مالك صريح بشأن F1: إمّا (أ) تحديد آلية هوية رسالة↔دفعة لإصلاحه، أو (ب) تنازل صريح عن
F1 مع نطاق موثّق؛ ثم (عند الإذن بالالتزام) دفع فرع `agent/*` ليصبح الأثر قابلًا للتحقق في CI.
