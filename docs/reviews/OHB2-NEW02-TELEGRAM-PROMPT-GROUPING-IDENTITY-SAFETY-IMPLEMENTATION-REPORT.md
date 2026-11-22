# OHB2-NEW02 — Telegram Prompt Grouping Identity Safety

**التاريخ:** 2026-11-22  
**الفرع:** `agent/ohb2-new01-cancel-race`  
**الحالة:** `IMPLEMENTED / VERIFIED` — commit محلي على الفرع؛ **لا push/PR/نشر**.  
**النوع:** إصلاح سلامة ملكية رسائل Telegram (DEF-011 لا علاقة له؛ لم يُلمس).

---

## 1. المشكلة

كان `Database.add_or_group_outbox` يدمج أي رسالتين لنفس `(conversation_id, chat_id)` إذا
وصلتا خلال `GROUP_WINDOW = 1.5s`. هذا يعني أن رسالتين مستقلتين من المستخدم قد:

- تُرسلان كبرومت واحد؛
- تُحذفان معًا بعد اكتمال الدفعة؛
- تفقدان ملكية كل رسالة على حدة عند التنظيف.

## 2. الإصلاح

الدمج الآن يحتاج **دليل Telegram صريح** فقط:

- `bot/handlers.py` يمرّر `update.message.reply_to_message.message_id` إلى
  `add_or_group_outbox`.
- `bot/db.py::add_or_group_outbox` يدمج فقط إذا كان `reply_to_message_id` موجودًا فعليًا
  في `telegram_message_ids` لسجل `pending` (يبحث في كل السجلات المعلّقة، وليس الأحدث فقط).
- بدون ردّ صريح: سجل `pending` مستقل، حتى لو وصلت الرسالتان في نفس اللحظة.
- `GROUP_WINDOW` بقي **تأخير نضج الحجز** فقط، وليس معيار تجميع. التعليقات حُدِّثت لتطابق
  السلوك.

## 3. ما تم الحفاظ عليه

- تنظيف الدفعات ما زال لكل سجل `outbox` على حدة: `telegram_message_ids` +
  `ack_message_ids` + رسالة التأكيد فقط.
- NEW-01 (`/cancel` أثناء قبول البرومت) ما زال شغّالًا: guard موجود، و53 اختبارًا مرتبطًا
  يعدّي.
- ترتيب الإرسال، retry/backoff، at-most-once، وإعادة التشغيل دون تغيير.
- لا تغيير في DEF-011-A، DEF-011-C، D6، أو أي معمارية أخرى.

## 4. الاختبارات

### ملف جديد
`tests/test_new02_prompt_grouping_identity.py` — 13 اختبارًا:

1. R1: رسالتان مستقلتان بنفس الوقت ⇒ سجلان، IDs/ACKs منفصلة.
2. R2: cleanup سجل لا يمس سجلًا مستقلًا.
3. R3: ردّ صريح ⇒ دفعة واحدة، النص بالترتيب، cleanup يحذف IDs الدفعة فقط.
4. R4: دفعتان متداخلتان + cleanup معزول.
5. R4b: ردّ على دفعة أقدم لا يندمج مع الدفعة الأحدث.
6. R5: تكرار نفس `update` لا يكرّر membership.
7. R6: فشل حذف جزئي يُسجَّل، ولا يحذف التأكيد/الدفعة الأخرى.
8. R7: إعادة التشغيل تحافظ على membership كل دفعة.
9. R8: 4 رسائل متزامنة ⇒ 4 سجلات مستقلة.
10. R9: تسليم worker لكل سجل مستقل.
11. R9b: فشل إرسال أول برومت لا يفسد حالة الثاني.
12. R10: توقيت cleanup (5s ثم 10s) لكل دفعة.
13. R11: لا حذف لمعرّف غير معروف/غير صالح.

### تحديثات اختبارات قائمة
- `tests/test_grouping.py`: استبدال افتراض «الوقت يجمع» بعزل مستقل + تجميع بالردّ.
- `tests/test_prompt_cleanup.py` و`test_telegram_prompt_cleanup_durable.py`: بناء الدفعات
  بعلاقة ردّ صريحة.
- `tests/test_miniapp_operations.py`: التوقع الجديد: لا دمج بلا مرجع.
- `tests/test_persistent_ready_sticky_routing.py`، `test_4b.py`،
  `test_existing_conversation_repository_context.py`: توقع سجلات مستقلة للرسائل المتزامنة/
  المتتالية، مع الحفاظ على الوجهة الصحيحة.

## 5. التحقق الفعلي

| الفحص | الأمر | النتيجة |
|---|---|---|
| Python suite | `/tmp/ohb2-chat-venv/bin/python -m pytest -q` | **3738 passed**, 0 failed (كان 3723) |
| NEW-02 focus | `pytest -q tests/test_new02_prompt_grouping_identity.py tests/test_grouping.py` | **38 passed** |
| NEW-01/duplicate | `pytest -q tests/test_new01_cancel_prompt_atomicity.py tests/test_def011_review_remediation.py tests/test_duplicate_update_dispatch.py` | **53 passed** |
| Frontend | `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** |
| Pyflakes | `python -m pyflakes bot automation tools main.py tests/` | exit **0** |
| Bandit | `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High **0** |
| Dependency SCA | `python -m pip_audit -r requirements-dev.txt` | No known vulnerabilities |
| Compile | `python -m compileall -q ...` | exit **0** |
| Whitespace | `git diff --check` | exit **0** |

## 6. القيود والملاحظات

- **لا يوجد مراجع مستقل** لهذا التغيير؛ هذا تقرير تنفيذ وتحقق ذاتي، وليس مراجعة مستقلة.
- أُنشئ **commit محلي** فقط على `agent/ohb2-new01-cancel-race`؛ لم يُنفَّذ push/PR/merge/deploy، ولم تُفعَّل Autopush.
- NEW-01 وNEW-02 في نفس الـ commit المحلي لأن `bot/db.py` يحتوي التغييرين معًا.
- تقسيم رسالة Telegram الطويلة إلى أجزاء مستقلة قد ينتج برومتات منفصلة إذا لم يحتوِ الجزء
  الثاني على `reply_to_message`؛ هذا آمن (رفض الدمج بالوقت)، ويحتاج قرار UX منفصلًا إذا
  أردنا تجميعًا تلقائيًا.

## 7. الملفات المتغيرة

- `bot/db.py`
- `bot/handlers.py`
- `bot/outbox.py` (تعليقات/توثيق فقط)
- `tests/test_new02_prompt_grouping_identity.py` (جديد)
- الاختبارات السبعة المذكورة في §4.
- `.agent/PROGRESS.md`
