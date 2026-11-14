# PROGRESS — OHB2-PLAN-01-APPROVE-DEFERRED-P0-AND-CONTINUE-STAGES-0-5

## Goal
تنفيذ قرار المستخدم الصريح (**Option D**): تأجيل ميزة تسليم المرفقات العامة (P0) **مؤقّتًا**،
مع الحفاظ على **الرفض الآمن** للمرفقات غير المدعومة، والسماح بمتابعة **Stages 0–5** من خطة
`OHB2-PLAN-01-TELEGRAM-ACK-AND-DELIVERY-RELIABILITY`. ده **قرار منتج صريح** لتغيير **ترتيب**
التنفيذ الأصلي (P0-first) — **مش** تفويض بإضعاف أي متطلّب أمني، و**مش** ادّعاء إن P0 خلص.

## قرار المستخدم (Option D) — مُوثَّق (Phase A)
- **التاريخ:** 2026-11-11. **المرجع الأساسي الأصلي (لا يتغيّر):** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **الموافقة الصريحة:**
  1. تأجيل ميزة تسليم المرفقات العامة **مؤقّتًا**.
  2. الحفاظ على الرفض الآمن للمرفقات غير المدعومة (سلوك `handle_unsupported_attachment`).
  3. السماح بتنفيذ **Stages 0–5** بالترتيب الأصلي.
  4. الحفاظ على كل متطلبات P0 الأصلية كمتطلبات **مؤجّلة** قابلة لإعادة الفتح لاحقًا.
- **ترتيب التنفيذ الأصلي (P0 أولًا) اتغيّر استثنائيًا** بهذه الموافقة الصريحة فقط.
- **الحدود:** الموافقة دي **مش** موافقة على معمارية الإقرار (Option A)، ولا على تغييرات
  المخطط، ولا على قرارات المنتج المفتوحة في ADR §28 — دي لسه محتاجة موافقة منفصلة.

## حالة P0 (نصًّا — إلزامي)
`BLOCKED / DEFERRED BY EXPLICIT PRODUCT DECISION`
- **P0 (تنفيذ الميزة):** **مؤجّل ومحجوب** — مش DONE/PASS/IMPLEMENTED/CLOSED.
- **الرفض الآمن للمرفقات غير المدعومة:** **مُحتفَظ به** (شغّال، مش متأثّر).
- **التصريح بمتابعة Stages 0–5:** **ممنوح**.
- **متطلبات P0 الأصلية الكاملة:** محفوظة **بدون أي حذف/تضعيف/إعادة تعريف**، عبر المرجع
  غير المتغيّر `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` (§1–§26).
  تشمل: رفع آمن لنفس المحادثة الحالية، الحفاظ على ارتباط المستودع/المحادثة، منع إنشاء
  محادثة/تسليم مكرّر، تخزين معلّق دائم + نافذة 15 دقيقة، تعامل آمن مع النتائج الغامضة،
  الانتهاء/التنظيف، حماية النوع/الحجم/المسار/الملكية/حدود المحادثة، منع استخدام اعتماد
  واسع الصلاحية، منع أصل غير موثوق/SSRF، و**مفيش** worker أو قاعدة جديدة.

## شروط إعادة فتح P0 (مستقبلًا)
يتفتح P0 تاني بس لما **واحد** من دول يتحقّق (موثّق في `OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` §26.3):
1. **قرار منتج** بإلغاء التأجيل والرجوع لمتطلبات P0 الأصلية، **أو**
2. توفّر **اعتماد رفع محدود الصلاحية** (بدون قدرة تنفيذ أوامر) **و** **allowlist لأصل
   agent-server ثابت وموثوق** **و** موافقة معمارية على تكامل ثانٍ/جدول جديد.

## Acceptance criteria (المهمة دي)
1. قرار Option D مُوثَّق في المستندات المرجعية (PROGRESS + proposal P0)، وحالة P0 بالضبط
   `BLOCKED / DEFERRED BY EXPLICIT PRODUCT DECISION`، ومتطلبات P0 الأصلية محفوظة بالمرجع.
2. Stage 0: خط أساس متحقَّق منه (git + بوابة كاملة) على الشجرة الفعلية، بأوامر/أكواد خروج/
   أعداد حقيقية.
3. Stage 1: تحديث ADR الإقرار بحدّ الموثوقية وسلوك الفشل وقاعدة البادئة المؤهّلة الأطول،
   مع تمييز الإقرار عن التسليم الخارجي، وقبل Stage 2.
4. Stages 2–5: تُنفَّذ بالترتيب، أو تُسجَّل بصدق كـ **محجوبة/مؤجّلة** بسبب بوابة الموافقة
   المعمارية/المخطط/المنتج — **بدون** تنفيذ يخالف القيود.
5. مفيش كسر للسلوك الشغّال (الرفض الآمن للمرفقات + كل الاختبارات القائمة).
6. مفيش commit/push/PR/نشر/نداءات إنتاج.

---

## حالة الخطة النهائية — `COMPLETED_WITH_EXPLICIT_DEFERMENTS` (2026-11-11)
المهمة: `OHB2-PLAN01-STAGE5-FORMAL-CLOSURE-AND-PLAN-RECONCILIATION` (توثيق فقط — بلا كود/اختبارات/مخطط).
المصدر المرجعي الأصلي لنصّ خطة `OHB2-PLAN-01-TELEGRAM-ACK-AND-DELIVERY-RELIABILITY`: **مُزوَّد من
صاحب المشروع** (خارج المستودع — مفيش ملف خطة أُضيف، ولا إعادة كتابة لسجلات تاريخية).
شرط الإغلاق الأصلي (§6): «تم حسم SW-02 بدليل أو إبقاؤه صراحةً UNKNOWN مع مالك ومصدر مطلوب».

| المكوّن | الحالة | النوع |
|---|---|---|
| P0 | `BLOCKED / DEFERRED BY EXPLICIT PRODUCT DECISION` | قرار منتج صريح (Option D) — **غير منفَّذ** |
| Stage 0 | `DONE` | خط أساس متحقَّق منه (git + بوابة كاملة) |
| Stage 1 | `DONE` (ADR §30 v4) — مراجعة ذاتية | توثيقي |
| Stage 2 | `PASS_WITH_NOTES` | مُنفَّذ + مراجعة عدائية مستقلة |
| Stage 3 | `PASS_WITH_NOTES` | مُنفَّذ + تحقق احتفاظ مستقل |
| Stage 4 | `PASS` | مُنفَّذ + مراجعة عدائية مستقلة (PASS) |
| Stage 5 / SW-02 | `CLOSED_WITH_EXPLICIT_UNKNOWN — SOURCE REQUIRED` | حسم صريح UNKNOWN بقرار الخطة (§6) |

**لماذا `COMPLETED_WITH_EXPLICIT_DEFERMENTS` (وفق §6):**
- كل المراحل القابلة للتنفيذ ومعرَّفة بما يكفي (**0–4**) اكتملت (مُنفَّذة، ومُراجَعة مستقلًّا حيث ينطبق).
- **P0 مؤجّل عن قصد** بقرار منتج صريح — **مش** منفَّذ، ومتطلباته الأصلية محفوظة بالمرجع غير المتغيّر.
- **SW-02 غير معروف** — **مش** منفَّذ، ويحتاج **مصدرًا موثوقًا** قبل أي تنفيذ مستقبلي.
- الاستثناءان **مسجَّلان صراحةً** ⇒ الاستثناءات استثناءات مُعترَف بها، **مش** ادّعاء إتمام عمل مؤجّل/غير معروف.

**ممنوع:** وصف الخطة بـ «DONE» مجرّدة، أو أي ادّعاء بأن P0/SW-02 اتنفّذوا/اتصلّحوا/نجحوا.

---

## Stage 0 — خط الأساس (متحقَّق منه على الشجرة الفعلية)
- Branch `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`؛ HEAD `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` == `origin/main`؛ divergence `0 0`.
- Modified (tracked): `.agent/PROGRESS.md`، `README.md`، `bot/app.py`، `bot/handlers.py`. Untracked: ملفا `docs/proposals/*`، `tests/test_unsupported_attachment_rejection.py`.
- البوابة (على الشجرة الفعلية قبل تغييراتي الوظيفية):
  - `.venv/bin/python -m pytest -q` ⇒ **2474 passed**، 72 warnings (exit 0).
  - `node --test tests/frontend/*.test.js` ⇒ **219 pass / 0 fail**.
  - `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` ⇒ exit **0**.
  - `.venv/bin/python -m bandit -r bot/ automation/ main.py -lll -s B613` ⇒ High **0** (Medium 17، Low 5).
  - `.venv/bin/python -m pip_audit -r requirements-dev.txt` ⇒ **No known vulnerabilities found**.

## Stage 1 — ADR (مُنجَز، توثيقي)
- أُضيف **§30 (v4)** إلى `docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md`: حدّ الموثوقية،
  سلوك كل الحالات (نجاح/جزئي/استثناء/BUSY/فشل دائم/انهيار/مكرّر/صندوق/مفيش handler)، قاعدة
  «أطول بادئة مؤهّلة متّصلة»، تمييز الإقرار عن التسليم الخارجي، الفجوات المفتوحة، وبوابة Stage 2.

## Stage 2 — تنفيذ الإقرار: `DONE` (مُنفَّذ — Option A + حدّ دائم)
- **مُنفَّذ** بالقرارات المعتمدة D0–D5: `Application` بـ `updater(None)` (مفيش Updater ⇒ مفيش poller
  تاني)، وحلقة `getUpdates` مخصّصة جديدة في `bot/polling.py` (`TelegramPoller`/`run_bot`)، و`main.py`
  بينده `asyncio.run(run_bot(app))`.
- `deleteWebhook(drop_pending_updates=False)` + استئناف من `B+1` أو `None` (**حفظ المعلّق**؛ بديل صريح
  لقرار OHB2-02 القديم `drop_pending_updates=True`).
- الحكم من **نتيجة دائمة مُـcommit** (`db.update_outcome`)، والافتراضي `partial_or_unknown`
  (fail-closed)؛ `commit_batch_outcomes` بحدّ **مونوتوني** ذرّي.
- **حلّ فجوة §22.2 (Option 2):** fallback `handlers.handle_unmatched_update` (آخر group 0) بيسجّل
  `explicitly_ignored` للتحديثات غير المطابقة (مايكتبش فوق نتيجة محفوظة، ومايحوّلش استثناء لتجاهل)
  ⇒ مفيش حجب أبدي. `ALLOWED_UPDATES=("message","callback_query")`.
- **اختبارات:** `tests/test_stage2_custom_polling.py` (32، مُثبَت بالطفرة). تحديث `test_startup_policy.py`.
- **لم يُنفَّذ (خارج النطاق):** §28.4 مخطط `ack_offset_submitted/confirmed` + علم poison. مفيش ادّعاء
  exactly-once خارجي.

## Stage 3 — الاحتفاظ الآمن: `DONE` (مُنفَّذ بعد Stage 2)
- **الخطر قبل:** `prune_processed_updates` كان بيشيل أقدم الصفوف **بغض النظر عن الحدّ**. كان آمنًا
  **بس** لأن الحدّ مش مربوط بحلقة (مفيش تقدّم offset مبني عليه). بعد Stage 2 الحدّ بقى **مؤثّرًا**
  ⇒ التقليم الأعمى بقى **غير آمن** (ممكن يشيل صف لسه محتاجينه للديدَب قبل تأكيده عند تيليجرام).
- **الإصلاح (أصغر تغيير آمن):** `Database.prune_processed_updates(keep, boundary)` بقى بيشيل صفوف
  `update_id <= الحدّ` **بس** (الذيل غير المؤكَّد يفضل دايمًا)، و`keep` بيسيب أحدث `keep` صف من اللي
  `<= الحدّ` بس، ومفيش حدّ ⇒ **no-op**. النداء في `_post_init` بيقرا `get_acknowledgment_boundary()`.
- **اختبارات:** 4 في `tests/test_duplicate_update_dispatch.py` (no-op بلا حدّ / `keep=None` /
  الذيل فوق الحدّ محفوظ / نافذة `keep` تحت الحدّ) + 2 في `tests/test_app.py` (ربط الـ post_init).
  **إثبات طفرة:** شيل فلتر الحدّ ⇒ 1 يفشل؛ فرّغ فرع `keep=None` من الحدّ ⇒ 2 يفشلان.

## Stage 4 — استرجاع show_status/show_cost: `DONE` (إصلاح عيب مؤكّد)
- **العيب المؤكّد:** `show_status`/`show_cost` كانوا بيسجّلوا نتيجة **بس** على مسارات الفشل
  (`mark_display_failed`) والرفض (`mark_explicitly_ignored`)، والمسار **الناجح** كان بيرجع
  **بلا أي نتيجة** ⇒ غير مؤهّل (fail-closed) ⇒ **حجب الحدّ من غير سبب**، على عكس كل مسارات
  العرض التانية (`open_conversation`/`copy_reply`/`full_reply`).
- **الإصلاح (أصغر تغيير آمن):** `mark_explicitly_ignored(update, context)` بعد نجاح العرض في
  الاتنين (النجاح = قراءة/عرض، مفيش نية دائمة ⇒ نفس تصنيف الإخوة).
- **اختبارات:** 4 جديدة في `tests/test_manual_polling_handler_outcome_coverage.py` (نجاح
  status/cost ⇒ `explicitly_ignored` ومؤهّل؛ cost not-found ⇒ تجاهل؛ فشل عرض cost ⇒
  `failed_transient` غير مؤهّل). **إثبات طفرة:** حذف السطرين ⇒ الاختبارين الجديدين يفشلان.
- **بند يحتاج قرار (غير مُنفَّذ):** «تسليم النتيجة الفاشل غير مرئي للمستخدم» (لا يوجد زر
  تحديث مخصّص/إشعار). عرض `status` بيوفّر «تحديث» (open) كإجراء إعادة محاولة، لكن **مفيش**
  تسجيل/إشعار صريح للمستخدم بفشل التسليم. الإضافة دي **ميزة جديدة/تغيير سلوك** ⇒ **محتاج
  قرار** (لم يُنفَّذ).

## Stage 5 — SW-02: `UNKNOWN / NEEDS SOURCE`
- بحث شامل في المستودع (`grep -rn "SW-02"`) + تاريخ الـ git (`git log -S`) + كل `docs/reviews/*`:
  **مفيش أي تعريف** لـ SW-02. الموجود بس إشارتان في `.agent/PROGRESS.md` بتقولا إنه **مؤجّل (LOW)**
  وأن SW-04/SW-05 اتنفّذوا «بدون لمس SW-02».
- مقارنة: SW-01/03/04/05/06/07 **لها تعريفات** في `tests/*.py`؛ SW-02 **مالوش**.
- **النتيجة:** `SW-02 = UNKNOWN / NEEDS SOURCE` — **مفيش اختراع لمعنى**، و**مفيش إغلاق صامت**.
- **الإغلاق الرسمي (2026-11-11):** `CLOSED_WITH_EXPLICIT_UNKNOWN — SOURCE REQUIRED` — التفاصيل الكاملة
  (السبب/المالك/المصدر المطلوب/شرط إعادة الفتح/منع الاستنتاج) في «### Stage 5 / SW-02» أسفل هذا الملف.

## المراجعة والتحقق (Phase H)
- البوابة الكاملة بعد التغيير: pytest/node/pyflakes/bandit/pip-audit (النتائج في تقرير المهمة).
- **مراجعة ذاتية فقط** — **مفيش** مراجع مستقل.

## إغلاق موثَّق — Stage 2 و Stage 3 + تدقيق Stage 4 / Stage 5 (2026-11-11)
المهمة: `OHB2-STAGE2-STAGE3-CLOSURE-AND-STAGE4-STAGE5-STATUS-AUDIT` (قراءة/تدقيق فقط — بلا تعديل كود).
الأساس المرجعي غير المتغيّر: `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`؛ فرع
`openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`؛ HEAD `907b20de3fa6627795c14f29677e9f39c68e82f4` (كما هو، مفيش commit جديد).

### Stage 2 — قبول: `PASS_WITH_NOTES` (مراجعة عدائية مستقلة)
- **الاستطلاع الوحيد:** `Application` بـ `updater(None)` ⇒ مفيش Updater؛ حلقة `getUpdates` مخصّصة واحدة
  في `bot/polling.py` (`TelegramPoller`/`run_bot`)، و`main.py` بينده `asyncio.run(run_bot(app))`.
  مفيش poller/worker ثانٍ. (مفيش ادّعاء exactly-once خارجي — at-most-once + إعادة تسليم idempotent.)
- **الإقرار الدائم + الحدّ المونوتوني:** الحكم من نتيجة مُـcommit (`db.update_outcome`)، الافتراضي
  `partial_or_unknown` (fail-closed)؛ `commit_batch_outcomes` بمعاملة واحدة + حارس مونوتونية (مايتراجعش).
- **الـ fallback الآمن:** `handle_unmatched_update` بيسجّل `explicitly_ignored` للتحديثات غير المطابقة
  (مايكتبش فوق نتيجة محفوظة، ومايحوّلش استثناء لتجاهل) ⇒ مفيش حجب أبدي.
- **سياسة الاستئناف:** من `B+1` أو `None`؛ `deleteWebhook(drop_pending_updates=False)` (**حفظ المعلّق**).
- **حالة المراجعة المستقلة:** `PASS_WITH_NOTES` (مراجعة عدائية مستقلة على `907b20d`، بلا HIGH/CRITICAL
  مفتوح بعد الإصلاح). الأساس المستقل: pytest 2516، node 219، pyflakes 0، bandit High 0، pip_audit clean.
- **عيب HIGH (الإقرار):** `OHB2-STAGE2-HIGH-ACK-BLOCKING-FIX` — مسارات الرفض النهائي/فشل العرض في
  `open_conversation`/`copy_reply`/`full_reply` كانت بترجع **بلا نتيجة دائمة** ⇒ `partial_or_unknown`
  (غير مؤهّل) ⇒ الحدّ/الـ offset يتجمّد ⇒ إعادة تسليم أبدية + حجب head-of-line. **مُصلَح** (بلا commit):
  تسجيل نتيجة صريحة (`explicitly_ignored` للرفض النهائي؛ `failed_transient` لفشل العرض)، والفشل
  التشغيلي (5xx/429/بلا كود) لسه **ينتشر** (SW-07) قبل التسجيل ⇒ مستحيل يتحوّل لتجاهل كاذب.
- **التحقق المستقل للإصلاح:** مراجعة عدائية مستقلة (قراءة فقط) — قبول `PASS_WITH_NOTES`؛ الدليل:
  `tests/test_stage2_high_ack_blocking_fix.py` (25 اختبار، قاعدة حقيقية + `TelegramPoller` E2E)،
  **إثبات طفرة مُعاد إنتاجه مستقلًّا: 16/25 يفشلون بلا الإصلاح**؛ البوابة الكاملة **2541 passed**،
  node 219، pyflakes 0، bandit High 0، pip_audit clean. **الإصلاح لسه غير مُودَع (uncommitted) — مش منشور.**
- **حدّ poison الموروث (fail-closed، موثَّق):** إشعار غير قابل للتسليم دائمًا ممكن يحجب الحدّ لحد تسوية
  يدوية — سلوك مقصود (ADR §10/§18.6/§8). **§28.4 (تجاوز poison + `ack_offset_submitted/confirmed`)
  مؤجّل بقرار منفصل — غير مُنفَّذ.**

### Stage 3 — قبول: `PASS_WITH_NOTES` (تحقق احتفاظ مستقل)
- **التقليم الواعي بالإقرار:** `Database.prune_processed_updates(keep, boundary)` بيشيل صفوف
  `update_id <= الحدّ` **بس**؛ **مفيش حدّ ⇒ no-op** (مفيش تقليم بلا حدّ دائم)؛ الذيل `> الحدّ`
  (غير المؤكَّد) **يتفضل دايمًا**؛ `keep` سقف إضافي جوّه `<= الحدّ` بس.
- **حالة المراجعة المستقلة:** `PASS_WITH_NOTES` (تحقق مستقل: no-op بلا حدّ، الذيل محفوظ، نافذة `keep`،
  مونوتونية). **إثبات طفرة:** شيل فلتر الحدّ ⇒ 1 يفشل؛ فرّغ فرع `keep=None` من الحدّ ⇒ 2 يفشلان.
  **`bot/db.py` ما اتلمسش في تعديل Stage 2-HIGH (0 تغيير) ⇒ Stage 3 سليم.**

### Stage 4 — `DONE` (تدقيق مصدر + اختبار، على `907b20d`)
- `show_status`/`show_cost` بيسجّلوا `mark_explicitly_ignored` **بس بعد نجاح العرض**؛ فشل العرض ⇒
  `mark_display_failed` ⇒ `failed_transient` (غير مؤهّل، مفيش نجاح كاذب). الاستثناءات **ما بتتحوّلش**
  لنجاح (بترفع للـ error handler اللي بيسجّل `failed_permanent`). **التحقق:** 6 اختبارات في
  `tests/test_manual_polling_handler_outcome_coverage.py` (نجاح status/cost ⇒ مؤهّل؛ cost not-found
  ⇒ تجاهل؛ فشل عرض cost ⇒ `failed_transient` غير مؤهّل) — **كلها بتنجح**؛ الكود مطابق للمقبول.
- **بند مرصود (LOW، غير مُنفَّذ، سلوك قائم على `907b20d`):** عند فشل upstream تشغيلي (5xx/429) في
  `_authorized_conversation`، `show_status`/`show_cost` بيعرضوا رسالة الخطأ ويسجّلوا `explicitly_ignored`
  (مؤهّل) بدل ما يرفعوا — **عكس `open`/`copy`/`full`** اللي بيرفعوا (`OperationalApiFailure`). الأثر:
  تحديث عرض فاشل تشغيليًا يُقَرّ (at-most-once) بدل إعادة محاولة؛ **مفيش نجاح كاذب**، ومفيش أثر على
  معمارية الإقرار. **مش عيب Stage 4** (بند رفض/عرض، خارج «نجاح العرض»). إصلاحه تغيير سلوك يحتاج قرار
  ⇒ **مؤجّل، لم يُنفَّذ.**

### Stage 5 / SW-02 — `UNKNOWN / NEEDS SOURCE`
- **المصادر المفحوصة:** كل المستودع (`grep -rn "SW-02"`)، تاريخ الـ git (`git log --all -S "SW-02"`)،
  كل `docs/*` و`docs/proposals/*` و`docs/reviews/*`، وملفات الاختبارات `tests/test_sw*.py`.
- **النتيجة:** **مفيش تعريف موثوق** لـ SW-02. نصّ الخطة الأصلي `OHB2-PLAN-01-TELEGRAM-ACK-AND-DELIVERY-RELIABILITY`
  **غير موجود في المستودع** (المعرّف ظهر في نص المهمة + آرتيفاكتات سابقة فقط) ⇒ **مفيش مصدر أصلي**.
  SW-01/03/04/05/06/07 **لها تعريفات** في `tests/*.py`؛ **SW-02 مالوش**. الإشارات الوحيدة هي
  **إحالات ذاتية في هذا الملف** («مؤجّل LOW»، «SW-04/05 اتنفّذوا بدون لمس SW-02»).
- **القرار:** **`SW-02 = UNKNOWN / NEEDS SOURCE`** — **مفيش اختراع لمعنى**، و**مفيش تنفيذ**. إغلاقه
  محجوب على توفّر مصدر موثوق.

#### الإغلاق الرسمي — `OHB2-PLAN01-STAGE5-FORMAL-CLOSURE-AND-PLAN-RECONCILIATION` (2026-11-11)
- **الحالة الرسمية:** **`CLOSED_WITH_EXPLICIT_UNKNOWN — SOURCE REQUIRED`**.
- **السبب:** مفيش تعريف أصلي لـ SW-02 في أي مصدر موثوق قابل للوصول (المستودع + تاريخ git الكامل +
  سجلات GitHub: Issues/PRs/commits/comments/reviews/branches؛ **0** إشارة لـ SW-02 في كود/اختبارات/
  docs؛ الـ 23 إشارة كلها **ذاتية** في `.agent/PROGRESS.md` و`.openhands/memory/*`).
- **المالك المسؤول (دور):** **Project Owner / Original Plan Author** (دور — **مش** فرد مُختلَق).
- **المصدر المطلوب:** تعريف مهمة SW-02 الأصلي أو الـ handoff الأصلي، ويشمل: العنوان الدقيق، السلوك
  المطلوب، النطاق والاعتماديات، الاستثناءات/القيود الصريحة، معايير القبول.
- **شرط إعادة الفتح:** أن يزوّد صاحب المشروع المصدر الموثوق (أعلاه). لحد ساعتها: **مفيش تنفيذ**.
- **ممنوع صراحةً:** استنتاج SW-02 من SW-01 أو SW-03 أو §28.4 أو أي عمل غير مرتبط.
- **غير مُنفَّذ / غير مُصلَح / غير مُجتاز:** SW-02 **مش** implemented/fixed/passed — هو **مُغلَق صراحةً
  كـ UNKNOWN** فقط.
- **P0:** `BLOCKED / DEFERRED BY EXPLICIT PRODUCT DECISION` (كما هو، بلا تضعيف).
- **Stage 2/Stage 3 كود:** **0 تغيير** خلال هذه المهمة (`bot/polling.py`/`bot/db.py`/`bot/app.py` = 0).
- **§28.4:** **غير مُنفَّذ** (مفيش `poison_acknowledged`/`ack_offset_*`/`acknowledgment_overrides`).
- **Autopush:** INACTIVE (أتمتة مستقلة، غير مربوطة بـ runtime التطبيق، وغير مُنشَّطة).
- **مفيش poller/worker/DB owner موازي جديد.**
- **التغييرات غير المُودَعة = 3 بالظبط:** `.agent/PROGRESS.md`، `bot/handlers.py`،
  `tests/test_stage2_high_ack_blocking_fix.py`. HEAD `907b20d` كما هو.

---

# PROGRESS — OHB2-UNSUPPORTED-FILE-SAFE-REJECTION (رفض المرفقات غير المدعومة)

## Goal
تنفيذ الخيار المعتمد B: رفض مرفقات/وسائط تيليجرام غير المدعومة برسالة عربية واحدة واضحة،
**بدون** أي تنزيل/حفظ/رفع/طابور/برومت/إنشاء شات. **ممنوع** تنفيذ رفع ملفات (Agent Server).

## Acceptance criteria
1. كل نوع مرفق (مستند/صورة/صوت/فيديو/فويس/فيديو نوت/أنيميشن/ملصق) يترفض برد عربي واحد.
2. مفيش تنزيل (`get_file`/download)، مفيش حفظ محلي، مفيش رفع، مفيش صندوق/طلب إنشاء.
3. مفيش نداء OpenHands، مفيش شات جديد، مفيش وصول لمسار البرومت.
4. النص والأوامر زي ما هي. 5. فشل الرد = فشل مُسجّل (مش نجاح كاذب).
6. مفيش اعتماديات/جدول/worker/عميل جديد. 7. tests + pyflakes + bandit + node تعدّي.

## Plan (done)
1. `bot/handlers.py`: `UNSUPPORTED_ATTACHMENT_TEXT` + `handle_unsupported_attachment`
   (حارس تفويض ⇒ رد واحد ⇒ `mark_explicitly_ignored`؛ فشل الرد ⇒ `record_update_failure` + raise).
2. `bot/app.py`: `UNSUPPORTED_ATTACHMENT_FILTER` صريح + تسجيل `MessageHandler` بعد `handle_text`.
3. `tests/test_unsupported_attachment_rejection.py` — 17 اختبار انحدار (تطبيق حقيقي + process_update).
4. توثيق مقتصر: README + PROGRESS.

## Results (verified)
- `.venv/bin/python -m pytest tests/test_unsupported_attachment_rejection.py -q` ⇒ **17 passed**.
- `.venv/bin/python -m pytest -q` ⇒ **2472 passed**، 72 warnings (~115s) — الأساس 2455 + 17.
- `node --test tests/frontend/*.test.js` ⇒ **219 pass / 0 fail**.
- `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` ⇒ exit 0.
- `.venv/bin/python -m bandit -r bot/ automation/ main.py -lll -s B613` ⇒ exit 0 (High 0).
- إثبات الطفرة: حذف تسجيل المعالج ⇒ المرفق ما يترفضش (مفيش رد) ⇒ الاختبارات حاجز فعلي.
- الملفات المعدّلة: `bot/app.py`، `bot/handlers.py`، `README.md`، `.agent/PROGRESS.md`،
  `tests/test_unsupported_attachment_rejection.py` (جديد). **مفيش** commit/push/PR.

## Assumptions / decisions
- الفلتر **صريح** (مش `filters.ATTACHMENT`) عن قصد ⇒ ما يشملش Location/Contact/Poll/Dice/Game/
  Payment/Story (مش ملفات)، فمفيش رفض زائف لرسالة مالهاش ملف.
- `handle_unsupported_attachment` و`handle_text` في نفس المجموعة (0) ⇒ PTB ينفّذ واحد بس ⇒
  مفيش ازدواج رد ولا وقوع للمرفق في مسار البرومت.
- نجاح الرد ⇒ `explicitly_ignored` (مفيش نية دائمة)، مثل باقي مسارات القراءة/التنقّل.
- خيار C (رفع آمن) لسه **مؤجّل** — مش منفَّذ ولا معتمد هنا.

---

# PROGRESS — OHB2-PHASE1E: full product-quality + security completion + CI review (Phase 1)

## Goal
Final engineering-quality and security-completion pass over Phase 1A–1D (persistent Mini App
sessions, conversation export + full reply copy, inbox filter/archive/delete, creation-job
reconciliation). Fix real findings, extend CI to cover them, keep every finished piece working.

## Acceptance criteria
1. No known dependency vulnerabilities (`pip-audit -r requirements-dev.txt` = clean) with the
   runtime still working (full pytest + a live uvicorn smoke test pass).
2. Static analysis covers ALL first-party modules (pyflakes on bot/ automation/ tools/ main.py tests/),
   and CI enforces it; a regression test guards the CI config.
3. SAST (bandit) runs in CI at high severity; the only high finding (B613 bidi) is documented as
   intentional (Arabic comments), not silently suppressed repo-wide.
4. Docs no longer contradict the code: DELETE does real remote OpenHands deletion (MINI_APP.md,
   DEPLOY_KATABUMP.md, and stale code docstrings).
5. Full `python -m pytest -q`, `node --test tests/frontend/*.test.js`, pyflakes, pip-audit, bandit
   all pass on the pinned versions (fresh-venv verified).

## Plan (done)
- requirements.txt: starlette 0.41.3 -> 1.3.1 (clears 8 advisories; 1.3.1 is the minimal fix).
- requirements-dev.txt: pytest 8.4.2 -> 9.0.3 (PYSEC-2026-1845), pytest-asyncio 1.1.0 -> 1.3.0
  (1.1.0 pins pytest<9), add pip-audit==2.10.1 + bandit==1.9.4.
- .github/workflows/ci.yml: widen pyflakes scope; add pip-audit + bandit steps.
- AGENTS.md §1, README.md, docs/REGRESSION_GATE.md, docs/OPERATIONS_RUNBOOK.md: document new commands.
- docs/MINI_APP.md, docs/DEPLOY_KATABUMP.md, bot/web/app.py, bot/keyboards.py: fix local-only DELETE claims.
- tests/test_ci_workflow_security.py: 9 tests guarding CI triggers, least-privilege, coverage,
  no production side effects, exact runtime pins.

## Baseline vs now
- Python: 1839 passed -> 1848 passed, 0 failed.
- Frontend: 206 passed -> 206 passed.
- pyflakes bot/ main.py tests/: clean -> clean (now covers automation/ tools/ too).
- pip-audit: 14 advisories (starlette 0.41.3) -> No known vulnerabilities found.
- bandit -lll -s B613 on bot/ main.py: 0 high -> 0 high.

## Assumptions / decisions
- Bumped starlette/pytest only because the advisories are the proven cause of the audit finding,
  and the bumps were verified (1839->1848 tests, live uvicorn smoke, fresh venv) — AGENTS.md §4.
- The Katabump deploy doc still needs `starlette==1.3.1` to be uploaded (it ships requirements.txt).

# PROGRESS — OHB2 overall-audit remediation (WP1–WP6)

## Goal
Remediate the six findings from the OHB2 overall audit, on top of origin/main @ c1aef66
(tree 2a97b15f…). Do not break working behaviour; smallest safe change; verified truth.

## Acceptance criteria
1. WP1 — a Mini App prompt whose POST returns after a local delete cannot resurrect the
   deleted conversation (no tombstone clear, no outbox row, honest 409).
2. WP2 — autopush never forwards `GIT_SSL_NO_VERIFY` to child git (TLS verification kept).
3. WP3 — the rate limiter enforces each window independently (minute vs hour).
4. WP4 — tombstone filtering fails closed on a DB read error (no unfiltered list).
5. WP5 — the bot and Mini App list paths follow `next_page_id` with a bound and report
   truncation, so conversations past the first page stay reachable.
6. WP6 — docs stop claiming "no data loss if the SQLite file is deleted" and stop claiming
   the bot keeps running when the startup integrity check fails.
7. Full `python -m pytest -q` and `node --test tests/frontend/*.test.js` pass; pyflakes clean.

Out of scope: unrelated refactors, dependency/version changes, main-branch pushes.

## Plan (all done)
- WP1 `bot/db.py::add_or_group_outbox` — reject `client_ref` enqueues on a tombstoned
  conversation; Mini App `send_prompt` uses `reengage=False` and raises 409 on rejection.
- WP2 `automation/autopush/main.py` — drop `GIT_SSL_NO_VERIFY` from the allowlist and strip
  denied keys in `_child_env()`.
- WP3 `bot/web/ratelimit.py` — per-window independent counting.
- WP4 `bot/handlers.py` + `bot/web/services.py` `_without_deleted` — return `[]` on error.
- WP5 `bot/openhands_client.py::collect_conversations` + list paths — follow `next_page_id`
  (max 20 pages) and surface `truncated`.
- WP6 `docs/DEPLOY_KATABUMP.md`, `docs/OPERATIONS_RUNBOOK.md` — correct the false claims.

## Baseline vs now
- Python: 1538 passed (baseline) → 1570 passed, 0 failed.
- Frontend: 143 passed → 143 passed.
- pyflakes `bot/ main.py tests/`: clean → clean.

## Assumptions / decisions
- Working on branch `agent/ohb2-audit-remediation` (AGENTS.md §6: push only agent/*).
- Mini App prompt path is treated as NOT an explicit re-engagement (re-watch goes through
  `watch`), so any prompt for a tombstoned conversation is refused.
- Bounded pagination cap = 20 pages (no unbounded loop if the server repeats `next_page_id`).

## Known issues
- None open. WP6 RUNBOOK §4 manual copy/restore text is accurate and left as-is.

## Branch and commits
- Branch: `agent/ohb2-audit-remediation`
- Commit: `b1dd979` — fix: remediate OHB2 audit findings (WP1-WP6)
- Pushed to origin; CI runs only on push/PR to main, so CI was verified locally with the
  exact workflow commands (pytest, node --test, pyflakes) — all green.

## Working commands
- Install: `pip install -r requirements-dev.txt`
- Test: `python -m pytest -q` ; `node --test tests/frontend/*.test.js`
- Lint: `python -m pyflakes bot/ main.py tests/`

## Phase 5 — Operational readiness audit (OHB2-PHASE5-OPERATIONAL-READINESS-AUDIT-AND-VERIFICATION)

Acceptance criteria: audit operational readiness (config, persistence, runtime, security,
hosting compatibility); resolve the open Phase-4 review notes; keep the full suite green;
make the smallest safe change only.

### Resolved from Phase 4 review
- P2-01 + P3-01: `bot/openhands_client.py::collect_conversations` now sorts merged pages by
  `updated_at` (desc) and de-duplicates by conversation id; fixed the misleading handler
  comment; added tests (unsorted pages + duplicate ids).
- P2-02: corrected the re-engagement description in `docs/MINI_APP.md`.
- P3-02: added fail-closed **then recovery** tests for both the bot list
  (`tests/test_handlers.py`) and the Mini App list (`tests/test_conversation_deletion.py`).

### Audit findings (Phase 2)
- P3-03: `MINI_APP_TRUSTED_PROXIES` was validated by `bot/config.py` and honoured by
  `bot/web/clientip.py` but was **missing** from `.env.example` and the `docs/MINI_APP.md`
  env block. Documented in both (behaviour unchanged; default stays fail-closed).

### Readiness notes
- Persistence: single SQLite file at `DB_PATH` with WAL + `busy_timeout=5000`; integrity is
  checked before polling (`Database.run_startup_maintenance`). No durable volume is documented
  for the free tier ⇒ **data-loss risk (H1 UNVERIFIED)** — see `docs/ZERO_TOUCH_STARTUP.md` §5b.
- Runtime: one process (bot polling + optional in-process Mini App ASGI); no `exec`, no second
  worker, no backup/SFTP/paramiko in runtime.
- Security: server-side initData verification, opaque in-memory sessions, Origin checks,
  body-size caps, per-IP/per-session rate limits, durable delete tombstone.
- CI: workflow `CI` runs `pyflakes` + `pytest` (3.11 & 3.13) and Node frontend tests; it runs
  only on push/PR to `main`, so on this branch it is verified locally with the exact commands.

### Phase 5 verification
- `python -m pyflakes bot/ main.py tests/` → clean (exit 0).
- `python -m pytest -q` → 1576 passed (in a venv; see note below).
- `node --test tests/frontend/*.test.js` → 143 passed.
- Focused: 431 passed (client, handlers, deletion, resurrection, config, bootstrap, ratelimit, authz, db).
- Note: `tests/test_deploy_manifest.py::test_documented_manifest_is_import_sufficient` fails
  when run against the sandbox's user-site packages (the subprocess is given a synthetic `HOME`
  and `PATH=/usr/bin:/bin`, so user-site deps are invisible). Proven environmental, not a code
  defect: with the same deps visible on the child's `PYTHONPATH`, `import main` returns 0, and
  the whole suite is green inside `.venv` (as CI installs into a normal site-packages).

### Branch and commits
- Branch: `agent/ohb2-audit-remediation` (push only agent/* per AGENTS.md §6).

## Phase 6 — Hosting compatibility & deployment plan (OHB2-PHASE6-HOSTING-COMPATIBILITY-AND-DEPLOYMENT-PLAN)

Acceptance criteria (testable):
1. Actual repo state established (branch/HEAD/clean tree/refs/merge-base) without fetch/switch.
2. Phase-5 follow-up commit `c41a57c` reviewed (ordering, dedup, cursor/truncation, tombstone
   filtering, recovery tests, trusted-proxies docs) — with a verdict.
3. Hosting requirements derived from real code (cited files/symbols), no invented config.
4. Provider comparison grounded in current official docs; unknowns labelled.
5. ≥1 technically suitable hosting recommendation justified, or its absence explained.
6. Explicit SQLite persistence contract (path, WAL, owner, restart/redeploy, lost state).
7. H1 stays UNVERIFIED unless real hosting evidence proves it.
8. Documentation-only deployment runbook (no execution).
9. Precise H1 evidence checklist.
10. All local verification reported honestly; independent-review status disclosed.
Out of scope: any code/config change, deployment, Git write, production access.

Plan (steps): (1) state+refs, (2) review c41a57c + focused/full tests, (3) requirements extraction,
(4) official provider research, (5) persistence contract, (6) write `docs/OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md`,
(7) report.

Result: DONE (code-level review + documentation). H1 remains UNVERIFIED (no hosting evidence).
Independent review: BLOCKED (no local reviewer session; contacting production is forbidden).
Artifact: `docs/OHB2_PHASE6_HOSTING_AND_DEPLOYMENT_PLAN.md` (documentation only, uncommitted).

## Phase 6b — Katabump preflight & H1 validation (OHB2-KATABUMP-PREFLIGHT-AND-H1-VALIDATION)

Acceptance criteria (testable):
1. Current Katabump official docs reviewed (docs.katabump.com + katabump.com/terms), each claim
   cited with URL + date + confidence.
2. Katabump compatibility assessed against real OpenHandBot requirements (PASS/CONDITIONAL/FAIL/UNKNOWN).
3. Renewal + permanent-deletion risk assessed explicitly; no Backup/snapshot workaround proposed.
4. A safe, isolated SQLite canary procedure documented (no OpenHandBot config/services).
5. No deployment, no production polling, no provider infra created, no secrets.
6. H1 remains UNVERIFIED (docs are not proof of mounted-volume persistence).
7. Only `docs/OHB2_KATABUMP_H1_VALIDATION.md` created; no code/config/script edits.
Out of scope: running the canary, creating a Katabump account/server, any Git write.

Result: DONE (documentation only). H1 = UNVERIFIED. Katabump = provisional candidate.

## Phase 6c — Katabump isolated SQLite canary package (OHB2-KATABUMP-ISOLATED-SQLITE-CANARY-PACKAGE)

Acceptance criteria (testable):
1. Package independent of OpenHandBot runtime (stdlib only; no app imports/env/.env).
2. No application code or configuration changed.
3. No production service accessed; no network in the canary.
4. Local canary checks pass (write/read/inspect + guardrails).
5. Instructions distinguish process restart vs server restart vs redeployment.
6. No automatic deletion or overwrite of existing data.
7. No provider account/server created by this task.
8. H1 remains UNVERIFIED until actual provider tests pass.

Result: DONE (package + docs only). Created `tools/katabump-sqlite-canary/{canary.py,README.md,requirements.txt}`.
Local tests: write/read/inspect OK (WAL confirmed, markers persist, 2nd process reads); guardrails OK
(relative path, repo-local path, bot_state.sqlite3, missing parent, existing DB w/o --confirm-overwrite,
missing DB ⇒ non-zero; no --db ⇒ exit 2); socket-blocked write/read ⇒ no network.
H1 = UNVERIFIED. Autopush INACTIVE. No Git write.

## Phase 7 — Final release gate (OHB2-PHASE7-FINAL-RELEASE-GATE)

Acceptance criteria (testable):
1. Repo identity/branch/HEAD/upstream/tree recorded; baseline vs origin/main established read-only.
2. Full release-readiness audit of the app (architecture, handlers, Mini App, OpenHands client, DB,
   workers, deletion lifecycle, security, RTL/a11y, deps, docs, tests) with severities.
3. All documented checks run; exact commands + exit codes + counts recorded; blockers classified.
4. Only clear in-scope defects fixed, each with a regression test; full suite re-run.
5. Independent-review package prepared (baseline/candidate hashes, diff, evidence, risks).
6. Final decision (PASS/PASS_WITH_NOTES/BLOCKED/FAIL) + Phase 8 recommendation.
Out of scope: deploy, publish, merge, push, PR, Telegram/OpenHands production calls, autopush,
Backup, architecture change, Enzonic Backups/Reinstall/Delete/Egg-switch.
Constraints: Enzonic canary = SKIPPED/UNVERIFIED (persistent SQLite across container recreation
unverified); autopush DISABLED/INACTIVE; preserve unrelated changes/protected paths.

Result: PASS_WITH_NOTES. Baseline = origin/main c1aef66 (tree == ac35877, the branch merged by PR #4);
candidate = HEAD c41a57c (3 commits ahead, linear). Audited: lifecycle (main.py/bootstrap/app/web),
handlers, Mini App auth/ownership/CSRF/CORS, OpenHands client, DB schema/WAL/tombstones/deletion,
workers/recovery, security invariants, RTL/a11y, deps, docs. No Backup in operational code.
Verification (local, .venv py3.13): pyflakes exit 0; pytest 1576 passed / 0 skipped; node 143 pass;
high-risk subset 335 passed; compileall OK; no TODO/bare-except/hardcoded-secret. No code fixed
(no P0/P1 found). No Git write; tree unchanged except this file. Enzonic canary = SKIPPED/UNVERIFIED.
Phase 8: NOT_ELIGIBLE until H1 (SQLite persistence across container recreation) is verified.

## Phase 8 — Enzonic controlled-deployment PREFLIGHT (OHB2-PHASE8-ENZONIC-CONTROLLED-DEPLOYMENT-PREFLIGHT)

Acceptance criteria (testable):
1. Baseline re-verified (repo/branch/HEAD/upstream/tree) without fetch or branch change.
2. Enzonic compatibility assessed (esp. Python 3.14) with real evidence, not provider claims.
3. Exact deployment config documented (env names only, files, startup cmd, DB path, WAL, single-instance).
4. Personal single-user risk assessment incl. what SQLite holds and what is lost if it disappears.
5. Local checks run (py + frontend + static + compile + manifest/config + py3.14) with real output.
6. Autopush DISABLED/INACTIVE and no Backup subsystem; H1 recorded SKIPPED/UNVERIFIED.
7. Final preflight report + ordered manual procedure + recommendation; NO deployment performed.

Result: DONE (preflight only, docs only). Python 3.14.9 installed locally via uv and verified:
pytest 1576 passed / 0 skipped, pyflakes 0, compileall 0 (also green on repo venv 3.13); node 143 pass;
deploy-manifest/config/bootstrap/zero-touch/security subset 86 passed. Peak import RSS ~57 MiB,
site-packages ~47 MB. WAL+busy_timeout OK on nested abs path; parent dir auto-created (bootstrap READY).
Key blocker found: Enzonic default `python3 app.py` fails (no root app.py) ⇒ set `sh start.sh`/`python3 main.py`.
H1 = SKIPPED/UNVERIFIED. Autopush INACTIVE. No Backup. No Git write; no upload/deploy. Doc:
`docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md`. Recommendation: PREFLIGHT_READY_WITH_RISKS.

## Phase 8 — Enzonic PRODUCTION deployment (OHB2-PHASE8-ENZONIC-PRODUCTION-DEPLOYMENT)

Result: BLOCKED at the server-side step (environment lacks Enzonic panel/SFTP credentials and the
app secrets TELEGRAM_BOT_TOKEN / ALLOWED_TELEGRAM_ID). Per policy: did not guess, did not request
secrets in chat, did not perform account recovery. No file uploaded, no server configured, no
process started, no Telegram/OpenHands production call.
Pre-deployment work DONE and verified:
- HEAD == candidate c41a57ca30558289918cb6883a2872d0826fbfee; runtime files identical to that commit.
- Local: pyflakes 0; pytest 1576 passed/0 skipped; node 143 pass; compileall 0.
- Verified exact runtime bundle built from tracked tree at HEAD (36 entries, zero forbidden files):
  main.py, start.sh, requirements.txt, README.md, full bot/ incl. bot/web/static/.
- Bundle self-sufficient: extracted ZIP, repo off sys.path → import main OK, bootstrap READY,
  DB healthy, journal_mode=wal, busy_timeout=5000, parent dir auto-created; single-instance proven.
- Bundle artifacts (outside repo): /workspace/ohb2-phase8-enzonic-deployment/
  ohb2-runtime-c41a57ca3055.zip (sha256 d85ae1840fb9e05995d8dd2625ccfd2e318261d7f1bc9c67652689fb056cc676),
  CHECKSUMS.sha256, DEPLOYMENT-RUNBOOK.md.
H1 = SKIPPED/UNVERIFIED. Autopush INACTIVE. No Backup. No Git write.

## Publish approved candidate to origin/main (OHB2-PUBLISH-APPROVED-CANDIDATE-TO-GITHUB-MAIN)

Result: STOPPED — not published. Gate failure: candidate is NOT a fast-forward of origin/main.
Evidence (read-only, after `git fetch --prune origin`):
- origin/main = c1aef66c5838f2216fef9ba4c096a73dbfaea374 (unchanged from historical value).
- candidate HEAD = c41a57ca30558289918cb6883a2872d0826fbfee (branch agent/ohb2-audit-remediation).
- merge-base(HEAD, origin/main) = ac358775edc23bdc38e428430776eaccba8b92eb.
- `git merge-base --is-ancestor origin/main HEAD` -> NO  ⇒ not a fast-forward.
- origin/main has 1 commit the candidate lacks: c1aef66 (merge of PR #4 from openhands-workspace-...).
- candidate has 3 commits origin/main lacks: b1dd979, 0e2ab56, c41a57c.
- tree(c1aef66) == tree(ac35877)  ⇒ divergence is TOPOLOGY ONLY (no content conflict expected).
- `git push --dry-run origin HEAD:main` would be rejected (non-fast-forward); also hit a password
  prompt (interactive credential path), so it was not used.
Per the task STOP condition: did NOT rebase/reset/merge/overwrite; did NOT push. No PR, no deploy.
Verification still run (read-only): pyflakes 0; compileall 0; pytest 1576 passed; node 143 pass.
Gates: no .env / no *.sqlite3 tracked; no operational Backup; autopush INACTIVE; user work preserved
(.agent/PROGRESS.md, docs/* untracked, tools/, .openhands/) — nothing staged or committed.
Safest next step (needs explicit user approval): rebase the 3 candidate commits onto origin/main
(`git rebase origin/main`) then push FF-only; expected clean because the trees are identical.

## Rebase and publish to origin/main (OHB2-REBASE-AND-PUBLISH-TO-GITHUB-MAIN)

Result: COMPLETE — published and independently verified.
- Original candidate HEAD: c41a57ca30558289918cb6883a2872d0826fbfee.
- Rebased HEAD: 4468eab833c510a34be6833d8399f290f395e6f8 (branch agent/ohb2-audit-remediation).
- origin/main: c1aef66c5838f2216fef9ba4c096a73dbfaea374 -> 4468eab833c510a34be6833d8399f290f395e6f8 (fast-forward).
- Rebased commits: b1dd979->b372c12, 0e2ab56->705464f, c41a57c->4468eab (order preserved, no conflicts).
- tree(rebased HEAD) == tree(old candidate c41a57c) => content fully preserved; only topology changed.
- Rebase used --autostash so my uncommitted .agent/PROGRESS.md notes were reapplied uncommitted (NOT published).
- Verification on rebased tree: pyflakes 0; compileall 0; pytest 1576 passed; node 143 pass.
- Gates: no .env/sqlite/wal/shm/pyc/venv/credentials in published tree (155 files); no operational Backup;
  autopush INACTIVE; untracked docs/* and tools/ NOT published.
- Independent check via GitHub API: remote main commit 4468eab, tree f0bf1617... == local HEAD tree.
- Auth: non-interactive GitHub HTTPS with ephemeral credential helper from GITHUB_TOKEN (no persistence).

## TASK: OHB2-TELEGRAM-MINI-APP-ACTIVATION-AND-REMOTE-OPENHANDS-DELETION
Branch: agent/ohb2-miniapp-remote-delete (from 4468eab = origin/main).

### Acceptance criteria (testable)
A1. index.html loads the official Telegram WebApp SDK so `Telegram.WebApp` exists inside the Mini App (current: SDK missing ⇒ initData empty ⇒ "افتح من جوه تيليجرام").
A2. /app + menu show a real `web_app` button when config valid; when invalid, ordinary commands keep working and a non-secret diagnostic explains why (ConfigError message via bootstrap/health), not a silent generic "unavailable".
A3. MINI_APP_URL rejects credentials, fragments, query, and non-https; ASGI routes reachable (already mounted); static assets load.
A4. initData validated server-side (already correct); ownership/ALLOWED_TELEGRAM_ID enforced.
B1. Delete removes the conversation from OpenHands via the verified endpoint `DELETE /api/v1/app-conversations/{conversation_id}` (Bearer), then finalizes local deletion. Confirmed remote success required before reporting success.
B2. Confirmation text explains remote deletion; Cancel changes nothing.
B3. Ownership enforced server-side; other users cannot delete.
B4. Durable deletion-in-progress marker; idempotent across retries/duplicate callbacks/restarts/timeouts.
B5. Timeout/lost response ⇒ uncertain outcome, NOT success; reconcile (verify absence) before deciding.
B6. Explicit handling of 401/403/404/429/5xx/malformed; no silent local-only fallback; no false success.
B7. No resurrection after success (tombstone already blocks).
Out of scope: Enzonic deployment, GitHub push/PR, production calls, Autopush, Backup.

### Phase 1 root causes (evidence)
- /app unavailable: handlers.app_command returns MINI_APP_UNAVAILABLE when `config.mini_app_url` is empty; MINI_APP_ENABLED defaults 0 ⇒ feature off by default. Not a bug in the handler; it is an activation/config gap.
- REAL frontend bug: bot/web/static/index.html never loads https://telegram.org/js/telegram-web-app.js, so window.Telegram.WebApp is undefined in real Telegram; app.js `tg` is null ⇒ initData "" ⇒ 401 "افتح من جوه تيليجرام". The whole flow cannot work.
- Deletion: bot/handlers.py delete_conversation_confirm + bot/web/services.py delete_conversation call db.delete_conversation (local only). openhands_client has NO delete method. Local-only by design.
- Tombstone + is_deleted guards block resurrection (kept).
- Verified API (Phase 3 gate PASS): live OpenAPI v1.79.0 has DELETE /api/v1/app-conversations/{conversation_id}; auth X-Access-Token (Bearer works; app uses Authorization: Bearer); 200 {"success":true}; 404 not found; 422 validation. Confirmed implemented in OpenHands source (deleteCloudConversation + official test conversation-delete.test.ts).

### Plan
1. index.html: add Telegram WebApp SDK script (before app.js, no defer issues).
2. Bootstrap diagnostics: surface Mini App config state (enabled/configured) without secrets.
3. Client: add delete_conversation(conversation_id) + get_conversation_status.
4. db: add deletion state machine (deleting/uncertain) columns + tombstone on delete start.
5. Mini App service + route: remote-first deletion with confirmations.
6. Bot handler: remote-first deletion.
7. Frontend: update delete UX + messages.
8. Tests: mini app + remote deletion; update existing local-only tests.
9. Full verification + docs.

### Phase 4 implementation — DONE (branch agent/ohb2-miniapp-remote-delete)
- A1: index.html loads telegram-web-app.js before /mini/app.js; CSP already allows telegram.org.
- A2: /app + menu button gated by MINI_APP_ENABLED AND valid MINI_APP_URL; non-secret diagnostic
  (_mini_app_diagnostic) when unavailable; ordinary commands unaffected.
- A3: MINI_APP_URL now rejects userinfo/fragment/query (config.py), https-only + public host.
- B1-B7: bot/deletion.py = single shared orchestration (bot + Mini App).
  - client.delete_conversation → DELETE /app-conversations/{id}, success only on {"success": true}.
  - client.conversation_exists → GET ?ids= for reconciliation.
  - db: deleted_conversations.remote_state/remote_updated_at (+migration), states
    deleting/uncertain/confirmed, begin_remote_deletion (durable pre-call marker),
    list_pending_remote_deletions, clear_remote_deletion; delete_conversation(remote_confirmed=).
  - Outcomes: 200/404 ⇒ confirmed+local delete; 401/403/422 ⇒ definite failure (no local delete);
    429/5xx/timeout/malformed ⇒ verify existence (absent⇒success, present⇒failure, unknown⇒pending 503).
  - Startup reconcile (bot/app.py _post_init) finalizes/undoes pending deletions; survives restart.
  - No resurrection (tombstone written before remote call); idempotent repeated delete.
- Frontend: delete confirm/success text says "from OpenHands"; retryable on failure.
- Docs: README, docs/MINI_APP.md, docs/API_NOTES.md updated.
- Tests added: tests/test_remote_deletion.py (17), client delete tests (5),
  miniapp activation tests (4), frontend remote-delete UX (2); existing local-only tests updated.
- VERIFIED: pytest 1602 passed; node --test 145 pass/0 fail; pyflakes 0; compileall 0.

## OHB2-REMOTE-DELETE-404-SEMANTICS — DONE (branch agent/ohb2-miniapp-remote-delete)

Goal: 404 من `DELETE /app-conversations/{id}` **مبهم** (غياب أو فشل خدمة داخلي) ⇒ ممنوع
اعتباره حذفًا مؤكّدًا. لازم يمرّ بتسوية التحقق من الوجود.

Acceptance criteria (كلها متحققة):
1. 404 مش نجاح تلقائي. 2. مدعوم بسلوك upstream موثّق. 3. المبهم يفضل pending/uncertain.
4. الوجود المؤكّد مايؤدّيش لحذف محلي. 5. المعمارية/الضمانات سليمة. 6. كل الاختبارات/الفحوص تمر.
7. المراجعة المستقلة معلّقة (مفيش backend reviewer) + handoff جاهز. 8. مفيش نشر/حذف حقيقي.

Evidence (upstream, OpenHands/enterprise@main):
- `app_conversation_router.py` DELETE: 404 في حالتين — `'Conversation not found'` (مش موجود)
  و`'Failed to delete conversation'` (فشل داخلي). ⇒ 404 مش دليل حذف.
- `GET /app-conversations?ids=`: نفس جلسة الكتابة (مفيش replica)، soft-delete بيتفلتر
  (`deleted_at IS NULL`)، الكتابة commit قبل الرد ⇒ قراءة قوية.

Changes:
- bot/deletion.py: 404 اتشال من auto-success و`_is_definite_failure` استثناه؛ أضفنا
  `_establish_absence` (قراءتين متتاليتين، bounded) و`_reconcile` المشترك؛ التسوية استخدمت
  `_establish_absence`. الحالات: غايب⇒confirmed+حذف محلي، موجود⇒failed+رجوع، تعذّر⇒uncertain.
- bot/openhands_client.py, bot/web/services.py: توثيق 404 المبهم.
- tests: test_remote_deletion.py (+6 حالات 404/reconcile)، test_conversation_deletion.py
  (+4 عبر المسار الحقيقي)، test_batch_c_integration.py (تحضير حذف محلي مباشرة)،
  tests/frontend/delete.test.js (local_only→remote_deleted).
- docs: README, docs/API_NOTES.md, docs/MINI_APP.md.

VERIFIED: pytest 1612 passed; node 145/145; pyflakes 0; compileall 0; focused deletion 252 passed.
NOT VERIFIED: live behavior against real OpenHands (no real API calls). Independent review pending.
No commit/push/PR/deploy/real deletion.

## OHB2-PHASE1A-PERSISTENT-MINIAPP-SESSIONS — IN PROGRESS (branch agent/ohb2-phase1a-persistent-sessions)

Goal: جلسات Telegram Mini App **دائمة** تنجو من إعادة تشغيل العملية/الخدمة، **بدون** إضعاف
أي ضمان مصادقة/تفويض/جلسة، وبدون كسر المعمارية (نفس مالك العملية/اتصال SQLite الواحد).

Acceptance criteria:
1. جلسة صالحة تفضل تصادق بعد إعادة بناء الخدمة/القاعدة (مثبت باختبار).
2. الانتهاء (TTL) والإلغاء (logout/رفض مستخدم) يفضلوا فعّالين بعد إعادة التشغيل.
3. الأمان ما اتضعّفش: توكن عشوائي opaque؛ القاعدة تخزّن **هاش SHA-256** بس (مفيش توكن خام)؛
   كوكي HttpOnly/Secure/SameSite=Strict؛ ملكية المستخدم مفروضة؛ فشل مغلق عند أي خطأ؛ مفيش تسجيل أسرار.
4. المعمارية محفوظة: نفس كائن Database/الاتصال الواحد؛ مفيش worker أو مخزن خارجي أو اتصال جديد.
5. الترحيل إضافي وغير مدمّر (CREATE TABLE IF NOT EXISTS) للقواعد القديمة.
6. كل الفحوص تمر: pytest كامل، pyflakes، node (بدون انخفاض عن baseline 1692).
7. مراجعة مستقلة معلّقة (مفيش backend reviewer متاح) + handoff جاهز.
8. مفيش نشر/دمج/force-push.

Out of scope: تغيير TTL الافتراضي أو خصائص الكوكي، إضافة تبعيات، تغيير بروتوكول initData،
تغيير تصميم التفويض، أي نشر/دمج.

Plan: (1) عمود/جدول web_sessions + دوال DB. (2) SessionStore دائم (هاش + fail closed).
(3) ربط app.py + FakeDb. (4) اختبارات. (5) توثيق MINI_APP.md. (6) تحقق كامل + مراجعة.

Baseline (before): pytest 1692 passed / pyflakes 0 / node 145 pass 0 fail.
After: pytest 1721 passed / pyflakes 0 / node 145 pass 0 fail.

Done: كل الكود والاختبارات والتوثيق (اختبارات الجلسات الجديدة 29).
Next: مراجعة مستقلة على SHA محدّد، ثم تقرير.

### Independent review (2026-11-06)
Reviewer conversation `90ff1c53-...` (delegated, separate context) reviewed exact commit
`3b75954` in an isolated worktree: **VERDICT: PASS-WITH-NOTES** (no blocker/major).
Verified by the reviewer with real output: pytest 1721 passed, pyflakes 0, session suite 29 passed,
raw token absent from DB file, auth survives reconstruct, expired rejected, revoked durable, db error -> fail closed.
Findings addressed in `ad6dd84`: revoke DB failure now logged (not silent) + stale docstring fixed + test.
Nit left as-is (documented): `reset()` uses `prune_web_sessions(inf)`; no production callers.

## OHB2-PHASE1B-MINIAPP-CONVERSATION-EXPORT-AND-FULL-REPLY-COPY — IN PROGRESS

Branch: `agent/ohb2-phase1b-export-and-copy-reply` (from verified Phase 1A `8a86e25`).

Goal: إضافة قدرتين ناقصتين في الـ Mini App: (1) تصدير الشات، (2) نسخ الرد الكامل للـ assistant.

Acceptance criteria:
1. تصدير الشات يشتغل للمستخدم المصرّح له (endpoint مصادَق).
2. منع تصدير شات مستخدم تاني server-side (مفيش ثقة في هوية من العميل).
3. حجم/ذاكرة التصدير محدودة (نفس `MAX_EXPORT_BYTES`/`_read_capped`).
4. حمايات الحذف/الشواهد كما هي: مفيش تصدير/إحياء لشات محذوف محليًا.
5. نسخ الرد الكامل بلا قصّ بصري (مصدره الرد الكامل مش المعاينة).
6. فشل/رفض الحافظة يُبلّغ بصدق (مفيش نجاح كاذب) + fallback آمن.
7. العربي/RTL وWebView الموبايل مغطّيين باختبارات.
8. الاختبارات والفحوص الثابتة تمر (بلا انخفاض عن baseline: pytest 1722 / node 145 / pyflakes 0).
9. مراجعة مستقلة PASS أو PASS-WITH-NOTES بدون Critical/High.
10. الـ diff النهائي فيه تغييرات المهمة بس.

Out of scope: Inbox archive/delete/filter، creation-job reconciliation UI، تغيير دلالات الحذف البعيد،
أي Backup، Autopush، نشر/دمج.

Baseline (before): pytest 1722 passed / pyflakes 0 / compileall 0 / node 145 pass 0 fail.

Plan:
1. Backend: `MiniAppService.export_conversation` (تفويض ملكية ⇒ قراءة محدودة ⇒ حدود حجم ⇒ اسم ملف آمن).
2. Backend: `MiniAppService.get_full_reply` (الرد الكامل + علامة القصّ).
3. Routes: `GET .../conversations/{id}/export` (مصادَق، غير مُغيّر للحالة) + `GET .../conversations/{id}/reply`.
4. Frontend: وحدة `export.js` مشتركة (اسم ملف آمن + منطق النسخ + رسائل) تُختبر في Node.
5. Frontend: `app.js` — زر تصدير + زر «نسخ الرد الكامل» مع Clipboard API + fallback + feedback صادق.
6. Tests: backend export/reply + frontend copy/export.
7. Docs: `docs/MINI_APP.md` (تصدير + نسخ كامل).

### Phase 1B — تم (مبدئيًا)
- Backend: `MiniAppService.export_conversation` (تفويض ⇒ شاهد حذف ⇒ تنزيل محدود) و`get_full_reply`.
- Routes: `GET /api/v1/conversations/{id}/export` و`/reply` (مصادَقة، read-only).
- Frontend: `copy.js` + `export.js` (وحدات مشتركة)، أزرار «نسخ الرد الكامل» و«تصدير الشات» في `app.js`.
- Tests: `tests/test_miniapp_export_reply.py` (23)، `tests/frontend/copy.test.js` (8)،
  `tests/frontend/export.test.js` (6)، `tests/frontend/export_copy_ui.test.js` (7).
- Docs: `docs/MINI_APP.md` (§4 routes، §12 tests، §13ج جديد، §14 محدّث).
- Results: pytest 1745 passed (baseline 1722) / node 166 pass 0 fail (baseline 145) / pyflakes 0 / compileall 0.

---

# OHB2-PHASE1C-MINIAPP-INBOX-FILTER-ARCHIVE-AND-SAFE-DELETE

## Goal
Complete the Mini App Inbox: all/unread-only filter, reversible archive, and a
restricted server-enforced permanent delete — without losing operational events,
hiding unresolved failures, or weakening delivery/reconciliation guarantees.

## Verified baseline (Phase 0)
- Repo `TM-AEM/OpenHandBot`; branch `agent/ohb2-phase1c-inbox-filter-archive-delete`
  from `30987867555386204fda587462fd72c488158689` (Phase 1B tip, descendant of Phase 1A
  `8a86e25e8cc6fe29191b08c4dca6aae90dd0d8e6`). Both are ancestors of HEAD (verified).
- Baseline green: pytest 1745 passed; node 166 pass/0 fail; pyflakes 0; compileall 0.
- Inbox data model: `notification_inbox` rows with `read_at` (read axis) and
  `delivery_status` ∈ {pending, delivered, failed} (delivery axis). Kinds: terminal,
  timeout, missing, stale_report, proactive. Retention (`_prune_inbox`) deletes only
  read, non-pending rows at soft caps. `notifier_pending.event_id` links a durable
  pending-delivery marker to an inbox row (reconciliation evidence).
- API already supports `GET /notifications?unread=1` (reuse it; do not duplicate).
- Single-owner Mini App: `_guarded` enforces an allowed Telegram session; non-owners
  cannot authenticate. No second DB/worker/scheduler.

## Acceptance criteria (testable)
1. The Mini App exposes an all / unread-only filter that changes the rendered data via
   the existing `unread=1` API, and preserves read-state, pagination and ordering.
2. Authorized users can archive and unarchive eligible notifications reversibly;
   archiving changes only visibility, never delivery/operation/read state, and is
   idempotent; archived items are excluded from the active inbox and reachable via an
   archived view.
3. Permanent deletion is server-enforced to the safe subset only (delivered + read +
   not referenced by `notifier_pending`); pending/failed/unread evidence is protected.
4. Failed DB operations never produce false success; cross-user access/mutation is
   rejected; underlying operation/outbox/delivery/reconciliation rows are untouched.
5. Full pytest + node suites, pyflakes and compileall pass (>= baseline); docs updated.
6. Independent review of the exact final SHA returns PASS or PASS-WITH-NOTES with no
   unresolved Critical/High findings.

## Plan (steps)
1. DB: additive `archived_at` column + migration; `list_inbox`/`count_inbox` archived
   param; `archive_inbox_item`/`unarchive_inbox_item`/`delete_inbox_item` (transactional,
   eligibility-checked) + DB tests.
2. Service: `list_notifications(archived=)`, `archive_notification`,
   `unarchive_notification`, `delete_notification` + API tests.
3. App routes: `POST /notifications/{id}/archive|unarchive`, `DELETE /notifications/{id}`,
   list `archived=1` param.
4. Frontend: `inbox.js` helpers (filter query, canDelete, archived), `app.js` filter +
   row actions with confirmation, `index.html` controls, `dom_stub` updates, node tests.
5. Docs (`docs/MINI_APP.md` §13b, `docs/NOTIFICATIONS.md` §9) + this file.
6. Verification: focused + full suites, pyflakes, compileall, diff self-review.
7. Independent review (separate agent-server session) of the exact final SHA.

## Assumptions / decisions
- Archive is a third axis (`archived_at`), separate from read and delivery state; it is
  reversible and never mutates delivery/operation state.
- Unread badge counts **active** (non-archived) unread items; `read_at` semantics unchanged.
- Permanent delete eligible subset = `delivery_status='delivered' AND read_at IS NOT NULL`
  AND not referenced by `notifier_pending` — i.e. no more than what retention already
  prunes, and never pending/failed/unread evidence.
- Protected from permanent delete: `pending`, `failed`, unread, and `notifier_pending`-
  referenced rows. Deletion touches only `notification_inbox`.
- Deletion requires an explicit two-step confirmation in the UI; the server re-checks.

## Out of scope
Creation-job reconciliation UI; remote conversation deletion semantics; Backup; Autopush
(remains DISABLED/INACTIVE); any second DB/worker/scheduler/external service.

## Status: DONE (implementation + local verification)

- Step 1 (DB): `archived_at` column + migration; `archived` on `InboxItem`;
  `list_inbox`/`count_inbox(archived=)`; `archive_inbox_item`/`unarchive_inbox_item`/
  `inbox_item_delete_eligibility`/`delete_inbox_item`. DONE.
- Step 2 (service): `list_notifications(archived=)`, `archive_notification`,
  `unarchive_notification`, `delete_notification` (404/409 mapping, no false success). DONE.
- Step 3 (routes): `POST /notifications/{id}/archive|unarchive`, `DELETE /notifications/{id}`,
  `GET /notifications?archived=1`. DONE.
- Step 4 (frontend): `inbox.js` (`isArchived`/`canDelete`/`filterQuery`/`emptyText`),
  `app.js` filter bar + `renderInboxRow` + two-step delete confirm, `index.html` chips,
  `styles.css`, `dom_stub.js`. DONE.
- Step 5 (docs): `docs/NOTIFICATIONS.md` (§2.7/§3/§5/§9/§11/§12) + `docs/MINI_APP.md`
  (§13b/§14). DONE.
- Step 6 (verification): pytest **1775 passed**, node **184 pass / 0 fail**, pyflakes **0**,
  compileall **0**, `git diff --check` clean. DONE.
- Step 7 (independent review of the exact final SHA): PENDING — see "Suggested next step".

## Hardening pass (spec re-audit, OHB2-PHASE1C)
Re-read the full task spec against the implementation; found and closed these gaps:
- **G1 (delete safety)**: eligibility was not kind-aware. Added `INBOX_DELETABLE_KINDS`
  allowlist `{terminal,timeout,missing,stale_report}` — unknown kinds and `proactive`
  are now protected (fail-closed). New `has_open_outbox`/`has_notifier_pending` guards
  protect a row whose conversation has an open outbox prompt or a durable
  `notifier_pending` marker. `delete_inbox_item` already re-checks inside
  `BEGIN IMMEDIATE`.
- **G2 (archive durability)**: `_prune_inbox` now exempts `archived_at IS NOT NULL`
  rows, so a deliberate archive is not silently pruned by retention.
- **G3 (frontend race)**: `loadInbox` now captures the request filter and discards a
  stale response (reloads for the current filter) — proven by a `/tmp` mutation.
- **G4 (frontend fallback)**: `canDelete` fallback is now fail-closed for unknown kinds
  (mirrors the server allowlist).
- **G5 (tests)**: added unknown/`proactive` kind, open-outbox (same/closed conv),
  `notifier_pending` (event ref + conversation), archived-prune survival,
  unarchive-prunable-again, invalid/expired session, rate-limit, cross-origin, repeat
  archive/delete, TOCTOU, migration (`archived_at`), and frontend filter-race tests.
- **Verification**: pytest **1791 passed** (+16), node **187 pass / 0 fail** (+3),
  pyflakes **0**, compileall **0**, `git diff --check` clean.
- **Gap (accepted)**: the spec's "authentication/security incident notifications" and
  "running/incomplete creation jobs" categories have no dedicated kind/table link in
  this codebase; they are covered by the fail-closed default (unknown kind ⇒ protected)
  and by the open-outbox guard. Documented as an explicit limitation, not a code gap.

### Independent review (adversarial, separate agent-server session)
- Reviewer read the real code (db/services/app/inbox + watcher/notifier/outbox) at the
  working-tree revision, ran the suites, and mutation-tested every guard.
- Verdict: **PASS-WITH-NOTES** — no Critical/High/Medium. All required guarantees
  (delivery evidence, unresolved-failure visibility, no loss of operation/reconciliation
  rows, reversible archive, two-step delete, non-destructive migration) held.
- Notes found and fixed:
  1. Filter-race guard existed only in the `.then` path; added the same guard to the
     `.catch` (network failure) path + test `F10` (mutation-verified).
  2. `canDelete` fallback read inherited prototype keys (`constructor`/`__proto__` →
     true, fail-open in the UI hint). Switched to `hasOwnProperty` + `typeof string` +
     widened `D8` (mutation-verified).
  3. `A1`/`D4` "reload" assertions were vacuous (`!== null`); now count `/notifications?`
     calls before/after (mutation-verified).
- Verification after fixes: pytest **1791 passed**, node **188 pass / 0 fail**, pyflakes
  **0**, compileall **0**, `git diff --check` clean.

### Working commands
```
.venv/bin/python -m pytest -q
node --test tests/frontend/*.test.js
.venv/bin/python -m pyflakes bot/ main.py tests/
.venv/bin/python -m compileall -q bot/ main.py
git diff --check
```

### Branch / commits
- Branch: `agent/ohb2-phase1c-inbox-filter-archive-delete` (pushed to origin).
- Commit: see `git log -1` on that branch (message `feat: Mini App inbox unread filter,
  reversible archive, and safe eligible delete`).

### Next
- Independent review (separate agent-server session) of the exact final SHA: request
  PASS / PASS-WITH-NOTES with no unresolved Critical/High findings before opening a PR.

# OHB2-PHASE1D-MINIAPP-CREATION-JOB-RECONCILIATION

## Goal
رؤية آمنة (owner-scoped) لطلبات إنشاء الشات في الـ Mini App + إجراءات تسوية يدوية
(إلغاء قبل الإرسال / تأكيد البدء للغامض) بنفس دلالات البوت، مع الحفاظ الكامل على
حدّ at-most-once ومنع أي إنشاء شات مكرّر.

## Verified baseline
- Branch `agent/ohb2-phase1c-inbox-filter-archive-delete`, HEAD `48fa7f85583b69dbb6e4b187c90c7116e45fa9eb`.
- Phase 1A `8a86e25e8cc6fe29191b08c4dca6aae90dd0d8e6` و1B `30987867555386204fda587462fd72c488158689`
  و1C موجودين في الأسلاف الفعلية (تم التحقق من ancestry الملفات والحالة).

## State machine (من `bot/db.py`)
pending/claimed (POST مابدأش، آمن للإلغاء) · starting (POST ممكن بدأ) · done (اتأكد) ·
unknown (غامض) · failed (فشل مؤكد) · discarded (اتلغى قبل الإرسال).
التحويلات: pending→claimed→starting→done/failed/unknown · pending/claimed→discarded (CAS).

## Implemented
- `bot/db.py`: `get_outbox(id, chat_id=None)` و`get_creation_job(id, chat_id=None)` مقيّدين بالمالك.
- `bot/web/services.py`: `creation_operation_list`، `reconcile_creation` (cancel/mark_sent)،
  تفريغ `_creation_dto` بحقول آمنة (`post_state`/`cancellable`/`resolvable`/`terminal`)،
  وتطبيق نطاق المالك على مسارات الـ outbox كمان.
- `bot/web/app.py`: راوتس/هاندلرز `/operations/creation/list` و`/operations/creation/reconcile`.
- الواجهة: تاب «طلبات البدء» + `bot/web/static/jobs.js` + `app.js` (عرض + تأكيد خطوتين).

## Safety guarantees
- الإلغاء **بس** pending/claimed (CAS `discard_creation_job`)؛ starting/unknown ⇒ not_confirmed
  بلا تغيير؛ نهائي ⇒ 409.
- mark_sent **بس** من unknown (CAS `set_creation_status_if_in`) ⇒ done؛ idempotent.
- التسوية مابتعملش أي شبكة ⇒ مستحيل إنشاء مكرّر؛ الغموض مايتحوّلش لحالة قابلة لإعادة POST.
- **دفاع في العمق (بعد مراجعة مستقلة)**: نطاق المالك اتضاف كمان على مستوى `bot/db.py`
  في `discard_creation_job(chat_id=...)` و`set_creation_status_if_in(chat_id=...)`
  (شرط `AND chat_id=?` جوّه الـ UPDATE والقراءة اللاحقة)؛ المسارات الداخلية من غير نطاق
  لسه شغّالة زي ما هي. mutation-tested: شيل الشرط بيفشّل اختبارات `test_db_*_owner_scoped_*`.

## Tests
- `.venv/bin/python -m pytest -q` ⇒ **1824 passed** (كان 1791).
- `node --test tests/frontend/*.test.js` ⇒ **203 pass / 0 fail** (كان 188).
- pyflakes **0**, compileall **0**, `git diff --check` clean.
- Mutation testing (M1–M6) أثبت إن اختبارات الحمايات غير تافهة (تفشل عند كسر الحرس).

## Independent review (adversarial, different model: NVIDIA Nemotron Ultra 550B)
- مراجعة مستقلة على الكود **الكامل** (مش مقتطع) — النتيجة: **NONE** (مفيش CRITICAL/HIGH/MEDIUM).
- المراجعة الأولى كانت على حزمة مقتطعة فطلّعت نتائج كاذبة؛ اتصلّحت بإعادة المراجعة على الكود الكامل.
- الثغرة الحقيقية الوحيدة اللي ظهرت (دفاع في العمق): دوال الكتابة في `db.py` كانت بمفتاح
  `job_id` بس. اتضاف نطاق المالك (`chat_id`) + اختبارات + mutation-testing.

## Branch / commits
- Branch: `agent/ohb2-phase1c-inbox-filter-archive-delete` (متدفوع لـ origin).
- Commit: `75e5b40af98d3146de7ee9725f12fc9b116435a9`
  (`feat: Mini App creation-job visibility and safe manual reconciliation (OHB2-PHASE1D)`).
- CI: workflow `CI` بيشتغل على push لـ main أو PR لـ main بس — فدفع الفرع مايشغّلش CI (متوقّع).

## Next
- فتح PR (لما المستخدم يطلب) ⇒ CI هيشتغل ويأكّد على GitHub Actions.

---

## OHB2-PHASE1D-FIX — independent-review findings (branch agent/ohb2-phase1c-inbox-filter-archive-delete)

مراجعة مستقلة (نموذج مختلف: deepseek-v4.1-flash عبر agent-server محلي) على الـ commit
`75e5b40` طلّعت HIGH واحد + MEDIUM. اتأكدت كلها تجريبيًا واتصلّحت:

- **F1 (HIGH) — إلغاء كاذب لطلب الـ POST بتاعه رجع فعلاً.** `_creation_dto` كان بيصنّف
  `pending`/`claimed` كـ `not_started`/`cancellable` **حتى لو فيه `task_id`** (دليل قاطع
  إن `start_conversation` رجع). الإلغاء كان بيحوّل شات بعيد حقيقي لـ `discarded` من غير
  تسجيل `conversation_id` ⇒ شات يتيم. الإصلاح: `_creation_post_started(job)` (task_id أو
  حالة غير قابلة للشطب) بيمنع `not_started`/`cancellable`، + حرس دفاع في العمق في
  `discard_creation_job` (`AND task_id IS NULL` + قراءة `task_id` ⇒ `not_confirmed`).
- **F2 (MEDIUM) — ادّعاء "بدأ فعلاً واتأكد" لطلب `done` من `mark_sent`** (بدون معرّف
  محادثة). jobs.js بقى يعرض رسالة أضعف ("المالك أكّد إنه بدأ") لما مفيش `conversation_id`.
- **F3 (MEDIUM) — `action` غير نصي ⇒ 500.** `(body.get("action") or "").strip()` كان
  بيرمي `AttributeError` لقيمة رقم/مصفوفة/كائن. دلوقتي `isinstance(..., str)` ⇒ 400.
- **F4 (MEDIUM) — طلب ملغي بيسدّ نفس (مستودع+نص) للأبد.** `TERMINAL` في ops.js كان ناقص
  `discarded`؛ + `add_creation_job` بقى يعمل صف جديد لو الصف الموجود `failed`/`discarded`
  (مفيش شات بعيد). **`done` مش استثناء** — نفس المعرّف ⇒ نفس الصف (at-most-once).
- **F5 (LOW) — أرقام ضخمة ⇒ 500** (`OverflowError` من SQLite). حدّ `MAX_SQLITE_INT`
  في `page`/`id` ⇒ 400.
- **F6 (LOW) — توثيق حجم الصفحة** 20 ⇒ 10 (الصحيح).

### Tests (بعد الإصلاح)
- `.venv/bin/python -m pytest -q` ⇒ **1839 passed** (كان 1830؛ +9 اختبارات انحدار F1–F5).
- `node --test tests/frontend/*.test.js` ⇒ **206 pass / 0 fail** (كان 203؛ +3).
- pyflakes **0**, compileall **0**, `git diff --check` clean.
- **Mutation testing**: كل إصلاح اتأكّد إنه غير تافه (شيل الحرس ⇒ اختبار واحد على الأقل
  بيفشل): M9/M10 (F1، طبقتين)، F3، F5، F4-backend، F2-frontend، F4-frontend.

### Safety (لسه محفوظ)
- at-most-once: مفيش أي مسار بيحوّل غموض ⇒ إعادة POST؛ الإلغاء لسه CAS على الحالة + task_id.
- الـ F4-backend بيتصرّف بس على `failed`/`discarded` (مفيش شات بعيد) — `done` بيتعامل
  idempotent زي الأول.

---

## OHB2-PHASE2A-FREE-HOSTING-QUALIFICATION — 2026-11-08 (research + docs only)

**Status:** PARTIAL/BLOCKED by Phase 1 (review=HIGH). Final classification: `NO_QUALIFIED_FREE_NO_CARD_HOST`.
- Phase 1 gate: HEAD `5b10850`; independent review `b4588fc1…` VERDICT **HIGH** (delete→500 `_wake`,
  OverflowError/AttributeError→500, LOW doc nits). Phase 1 not closed ⇒ hosting selection stopped per task §2.
- Baseline at start: working tree had pre-existing uncommitted fixes+tests (NOT mine, left untouched).
- Verified: pytest 1856 passed, pyflakes 0, frontend 206 pass/0 fail, autopush NOT running, Backup out of scope.
- Provider research dated 2026-11-08 (official pages): Katabump (free, no card, **4-day renewal→delete**, no
  inbound port) = REJECTED; Enzonic (free = **hibernating game tier**, R2-archived ⇒ ephemeral) = REJECTED;
  Northflank Sandbox Free (free, **no card**, always-on, single-instance volumes, generated HTTPS+LE TLS) =
  STRONGEST but **free-tier volume entitlement UNVERIFIED**; Render (ephemeral FS, disks paid) / Railway
  (trial→$1) / Fly (trial) / Koyeb (no free tier) / Oracle (card required) = REJECTED.
- Deliverable: `docs/OHB2_PHASE2A_FREE_HOSTING_QUALIFICATION.md`.
- No account/resource/deploy/DNS/Telegram/credential/production op performed. No commit/push.
- Next: fix review findings #1–#3 + regression tests, re-run independent review, then (if owner approves)
  an authorized Northflank canary to prove volume durability (tests T1–T8 in the doc).

---

## OHB2-PHASE2B-AUTHORIZED-HOSTING-DEPLOYMENT — 2026-11-08 (preparation only)

**Status:** `BLOCKED_PENDING_EXPLICIT_AUTHORIZATION` (+ BLOCKED_PENDING_REQUIRED_EVIDENCE). **No deployment action taken.**
- No explicit deployment authorization in the current task context (task text says a template/prior
  attempts/provider access are NOT authorization). ⇒ task's own rule: prepare only, do not deploy.
- Prerequisite gate FAILS: (2) Phase 1 not approved — review VERDICT HIGH; (3) 1×HIGH + 2×MEDIUM
  unresolved; (6) 0 CI runs for revision `5b10850` (CI only triggers on `main`); (7) working tree has
  7 modified + 4 untracked paths ⇒ not a reviewed deployable revision; (9) Phase 2A qualified **no**
  host (`NO_QUALIFIED_FREE_NO_CARD_HOST`).
- Non-destructive prep done: deployment guardrails, storage/SQLite rules, full env-var inventory
  (names only) from `bot/config.py` + autopush, secrets handling rules, safety gates, persistence
  test plan (T1–T8), rollback plan, handoff checklist.
- Deliverable: `docs/OHB2_PHASE2B_DEPLOYMENT_PREPARATION_AND_BLOCKERS.md`.
- Verified: pytest 1856 passed, pyflakes 0, frontend 206/0. No code changed by this task; no commit/push.
- Unblocks: fix review findings → clean re-review → authorize exact revision (+CI) → authorize a
  Northflank canary to prove free-tier volume durability → explicit deployment authorization.

---

## OHB2-AUD-01-08-REMEDIATION-AFTER-682DF5C-AND-INDEPENDENT-REVIEW — 2026-11-06

**Status:** DONE (AUD-01..05,07,08 code+docs remediated, reviewed, committed, pushed). AUD-06 = owner decision (outside branch scope).
- Commits: `b170bef` (fix(audit): AUD-01..08 remediation, 15 files) + `601b57b` (fix(review): README SAST scope + dead-branch test, 3 files). Pushed to `origin/agent/ohb2-phase1c-inbox-filter-archive-delete` (601b57b == remote).
- Independent review (agent-server deepseek-v4.1-flash, detached worktree at the exact SHA): first pass PASS-WITH-NOTES on `b170bef` (HIGH: AUD-06 not addressed; MEDIUM: README bandit scope stale; LOW: `_page_offset` overflow branch untested). After fixes, re-review **PASS** on `601b57b`.
- AUD-01: `_wake` tolerates missing/raising `wake` (services.py); a successful remote delete never 500s on a secondary wake. Mutation-proven.
- AUD-02/03: oversized/negative ints and non-string JSON ⇒ 400 (not 500). Mutation-proven.
- AUD-04: reject `page` outside `[0, MAX_PAGE]` at API + service (no silent clamp); db validates limit/offset/page_size before SQLite binding; `page=2**62` was reproduced as `OverflowError ⇒ 500`, now 400. 5 mutations proven + `_page_offset` overflow branch now covered.
- AUD-05: rate-limit key = SHA-256(session token), never raw. Mutation-proven.
- AUD-07: bandit scope `bot/ automation/ main.py` in ci.yml; proved a high finding (B602) in `automation/` makes bandit exit 1.
- AUD-08: README.md, docs/MINI_APP.md, docs/NOTIFICATIONS.md, OPERATIONS_RUNBOOK.md, REGRESSION_GATE.md all consistent; docs-consistency test added.
- Verification: pytest **1900 passed**; pyflakes clean; bandit exit 0 (High 0); node **206/0**; pip-audit "No known vulnerabilities found".
- AUD-06 (UNRESOLVED by design): `ci.yml` triggers only on push/PR to `main`; 0 check-runs for b170bef/601b57b. AGENTS.md §6 forbids opening a PR without explicit user request. Repo is PUBLIC + unlimited free CI + precedent shows a `pull_request` from an `agent/*` branch runs CI. Options for the owner: (a) open a PR to `main` (runs CI), or (b) add the branch pattern to ci.yml triggers. Both need explicit approval; proposed, not executed.

## OHB2-OUTBOX-TOMBSTONE-TOCTOU-RACE-AUDIT-AND-REMEDIATION — 2026-11-06

**الهدف:** إغلاق ملاحظة LOW في `bot/outbox.py::_post_claimed` — هل ممكن يتبعت محتوى شات
بعد ما ياخد شاهد حذف فعّال؟

**معايير القبول (acceptance criteria):**
1. تحليل السباقات السبعة المطلوبة (tombstone قبل الحجز/بعد الحجز/أثناء الفحص/بعد الفحص
   قبل الإرسال/أثناء الإرسال/نتيجة غامضة/تعافي أو worker تاني) بالدليل من الكود.
2. لو فيه سباق إفصاح حقيقي ⇒ أصغر تصحيح آمن: فرض الشاهد عند أقوى حد قبل الإرسال الحامل
   للمحتوى، مع حماية المطالبات القديمة/المسترجَعة، وبقاء CAS/at-most-once كما هي.
3. اختبارات حتمية: (أ) شاهد قبل الحجز، (ب) شاهد بعد الحجز وقبل الإرسال، (ج) شاهد عند حد
   الفحص النهائي، (د) شاهد بعد بدء الإرسال (يُوثَّق القيد)، (هـ) مطالبة قديمة/مسترجَعة،
   (و) شات سليم لسه بيتبعت، (ز) شات تاني غير متأثّر، (ح) الملكية/التفويض كما هي، (ط) مفيش
   إعادة إرسال بعد نتيجة غامضة.
4. الاختبارات تثبت **منع النداء البعيد** و**غياب الإفصاح** (مش الحالة النهائية بس).
5. البوابات كاملة: pytest, node, pyflakes, bandit, pip-audit — كلها أخضر.
6. مراجعة مستقلة على الـ diff غير المُودَع + معالجة أي HIGH/MEDIUM، وتوثيق LOW.
7. عدم لمس الأربعة ملفات F-1 غير المُودَعة، وعدم أي كتابة git، وعدم أي نداء إنتاجي.

**حالة:** IN PROGRESS.

**النتيجة النهائية (OHB2-OUTBOX-TOMBSTONE-TOCTOU): DONE / PASS.**
- سباق حقيقي مؤكَّد (نافذة `deleting/uncertain` تسيب السجل مؤهّلًا؛ الـ CAS لوحده ماكانش كافي).
- الإصلاح: حرس شاهد (fail-closed) مرتين في `_post_claimed` — عند المدخل وفورًا قبل CAS الإرسال
  (بلا `await` بينهما) ⇒ `discarded`. الحدّ الوحيد المتبقّي: شاهد يُكتب **بعد** بدء الـ POST (خارجي، موثَّق).
- اختبارات: `tests/test_outbox_tombstone_toctou.py` (15 اختبار). إثبات الطفرة: 9 تفشل بلا الحرسين،
  و2 (الحالة 3) تفشل بحرس المدخل وحده.
- البوابات: pytest 2021 passed؛ node 206/0؛ pyflakes 0؛ bandit High 0؛ pip-audit نظيف.
- مراجعتان مستقلّتان: الأولى PASS-WITH-NOTES + HIGH (الحالة 3) أُصلح؛ الثانية PASS (تصميم/منطق)،
  بلا HIGH/MEDIUM جديدة، والحدّ in-flight موثَّق بصدق.
- لا كتابة git، لا نداءات إنتاج، Autopush غير مُفعَّل، ملفات F-1 الأربعة دون تغيير.

## OHB2-COMPLETE-REMAINING-DEFECTS-AND-INCOMPLETE-FEATURES-REMEDIATION — 2026-11-06

**الهدف:** جولة تدقيق متبقية شاملة + إصلاح كل عيب مؤكَّد داخل النطاق.

**معايير القبول:**
1. تدقيق كامل للسطح (بوت/ويب/قاعدة/أمان/واجهة/CI/مستندات) بأدلّة.
2. إغلاق/تصنيف النتائج المذكورة: outbox (sent بعد الإرسال، إشعار sandbox)، كشف الميتاداتا
   المحلية، SameSite/WebView، `_API_CSP`، متجهات التوكن في الاختبارات، مستندات قديمة/مضلّلة.
3. أصغر إصلاح صحيح لكل عيب مؤكَّد + اختبار انحدار يفشل قبل الإصلاح.
4. بوابات كاملة خضراء (pytest/node/pyflakes/bandit/pip-audit) + مصفوفة ميزات متبقية.
5. مراجعة مستقلة على الـ diff غير المُودَع + معالجة HIGH/MEDIUM.
6. عدم لمس ملفات F-1/outbox السابقة، لا كتابة git، لا نداءات إنتاج، Autopush معطّل.

**النتائج الأولية (Phase A):**
- `_API_CSP` كود ميت (معرّف، غير مستخدم) + تعليق فوقه بيوصف `_STATIC_CSP` خطأً ⇒ LOW (توضيح/إزالة).
- كشف ميتاداتا الصندوق: صف `notification_inbox` لشات محذوف بيفضل بعنوانه/نصه وبيظهر في
  `list_inbox`/`count_inbox` (واجهة إشعارات الـ Mini App) ⇒ **MEDIUM (إفصاح محتوى)**.
- المتابعات (`watched`) بتتشال على الحذف المؤكّد ⇒ مفيش كشف (بس بتفضل خلال نافذة deleting/uncertain).
- SameSite=Strict: same-origin، متّسق مع قرار الاستضافة (Option A) ⇒ لا تغيير (الأدلّة تحت).

**حالة:** IN PROGRESS.


**النتائج الكاملة + الإصلاحات (Phase B/C):**
1. **كشف ميتاداتا شات محذوف (MEDIUM → مُصلَح):** `delete_conversation` بتسيّب صفوف
   `notification_inbox` أثر تدقيق (بعنوان + نص)، وقبل الإصلاح `list_inbox`/`count_inbox`
   كانوا بيعرضوها في واجهة إشعارات الـ Mini App، و`list_watched` كان بيعرض عنوان شات
   خلال نافذة deleting/uncertain. الإصلاح: `_inbox_visibility_clause` (بقت `self` مش
   `@staticmethod`) بتضيف `NOT EXISTS (... deleted_conversations)` على النشط والأرشيف معًا،
   و`list_watched` بنفس الاستبعاد. الصفوف نفسها ما بتتحذفش (أثر تدقيق/استرجاع محفوظ).
   اختبارات: `tests/test_deleted_conversation_metadata_exposure.py` (9 اختبارات)؛ إثبات طفرة:
   4+2 تفشل بلا الإصلاح، والضوابط تعدّي.
2. **إشعارات outbox لشات محذوف (LOW → مُصلَح):** الإشعاران `_SANDBOX_NOT_READY_NOTICE`
   و`_OUTBOX_EXHAUSTED_NOTICE` (خاليان من المحتوى) كانا ممكن يتبعتوا لو الشات أخد شاهد حذف
   أثناء التحضير (بعد حرس المدخل). الإصلاح: `_tombstoned()` (fail-closed) قبل كل إرسال إشعار.
   اختبارات: `tests/test_outbox_notice_tombstone.py` (3)؛ إثبات طفرة: 2 تفشل بلا الحرس.
3. **`_API_CSP` كود ميت (LOW → مُصلَح):** كان معرّفًا وغير مستخدم (ضابط CSP ناقص لردود
   الـ API)، والتعليق فوقه كان بيوصف `_STATIC_CSP` خطأً. الإصلاح: ربطه بـ `_SECURITY_HEADERS`
   ⇒ كل ردود `_json`/`_attachment` بتاخد `default-src 'none'`، وتصحيح التعليق.
   اختبار: `test_api_responses_carry_restrictive_csp` في `tests/test_miniapp_api.py`.
4. **متجه توكن في الاختبارات (LOW → موثَّق):** `tests/test_miniapp_initdata.py` فيه توكن
   تيليجرام يشبه الحقيقي؛ لكنه **فيكتور توثيقي عام** من core.telegram.org (مش سر إنتاج).
   أُضيف تعليق صريح يوضّح ذلك (لا تغيير في القيمة لأن الفيكتور لازم يطابق التوثيق حرفيًا).
5. **SameSite/WebView (لا عيب):** `SameSite=Strict` متّسق مع same-origin (الواجهة والـ API
   على نفس الأصل)؛ الكوكي بيتولّد من داخل الصفحة المضمّنة ⇒ same-site. الوضع مقصود أمنيًا
   وما اتغيّرش. أُضيف قسم «نطاق دعم العميل» في MINI_APP.md يوضّح أن الفتح في متصفّح عادي
   خارج تيليجرام غير مدعوم عن قصد (مفيش initData).
6. **مستندات:** README (قسم الأمان: لا أسرار إنتاج + استبعاد الشات المتشاهد)، MINI_APP.md
   (كشف الشاتات المحذوفة + CSP ردود الـ API + نطاق العميل)، NOTIFICATIONS.md (§3.8) — كلها
   مطابقة للكود بلا مبالغة.

**البوابات (Phase C):** pytest **2034 passed** (exit 0؛ +13 اختبار جديد)؛ node **206/0**؛
pyflakes **exit 0** على bot/ automation/ main.py tests/؛ bandit **High=0** (5 Low/17 Medium
موثّقة)؛ pip-audit **No known vulnerabilities found**. ملفات F-1 الأربعة بايت-متطابقة (hash).

**حالة:** البوابات خضراء؛ في انتظار المراجعة المستقلة على الـ diff غير المُودَع.

## OHB2-TELEGRAM-EXISTING-CONVERSATION-REPOSITORY-CONTEXT-FIX — 2026-11-06

**الهدف:** التحقق من/إصلاح بلاغ: إرسال برومت جوه شات تيليجرام موجود (مربوط بمستودع) كان
بيعمل شات OpenHands جديد من غير مستودع بدل ما يبعت للشات الموجود.

**معايير القبول (12 بند في المهمة):** إعادة استخدام الشات الموجود، حفظ المستودع/الـ sandbox،
ممنوع الاستبدال الصامت بشات جديد، خطأ صريح لو التعيين مش قابل للحسم، استمرار الشاتات
المستقلة (إنشاء/موجود)، دعم ربط المستودع لاحقًا، حفظ التفويض/الملكية، منع التكرار عبر
إعادة المحاولة/التعافي، عدم إدخال مالك قاعدة/worker/معمارية بديلة.

**Phase 1 — تشخيص (قراءة فقط، بأدلّة):**
- تتبّع المسار كامل: `handle_text` → `take_awaiting` (kind=route/reply) → `_send_prompt` →
  `db.add_or_group_outbox` → `OutboxWorker` → `outbox._post_claimed` →
  `get_conversation(conversation_id)` ثم `client.send_message(conversation_id, text)`
  (POST `/app-conversations/{id}/send-message`). الإنشاء مسار منفصل تمامًا
  (`_start_new_chat`/`_create_chat` → `creation_jobs` → `client.start_conversation`
  = POST `/app-conversations`).
- **النتيجة: البلاغ غير قابل للتكرار على الكود الحالي.** مفيش أي fallback صامت بيعمل شات
  جديد لو الشات مش موجود: `get_conversation` بترجّع `{}` **من غير استثناء** (لما الـ API
  يرجّع 200 + قائمة فاضية) ⇒ المسار بيدخل فرع «sandbox غير جاهز» (`bump_outbox_attempt`)
  ويفضل `pending` (إعادة محاولة) بلا أي POST إرسال أو إنشاء. (تصحيح دقة من المراجعة المستقلة:
  المانع هو فرع sandbox، مش استثناء ApiError؛ النتيجة النهائية — مفيش إنشاء — صحيحة.)
- مفيش فقدان لمعرّف الشات: التوجيه (`awaiting_conversation_id`) هو المعرّف المستخدَم حرفيًا
  في `send_message`. المستودع بيتقرا من نفس الشات بعيدًا (`selected_repository`) ولا يحتاج
  تحميلًا محليًا ولا بيتغيّر أثناء الإرسال. الـ `sandbox_id` بيتاخد من نفس الشات.
- فحص كل الفروع (`origin/main`, `release/*`, `feature/*`, `agent/*`) ⇒ نفس المسار الصح.
- دليل تجريبي (عميل OpenHands حقيقي + `httpx.MockTransport` + SQLite معزولة): فتح شات مربوط
  بمستودع ثم إرسال برومتين ⇒ **صفر** نداء `POST /app-conversations`، ونداء واحد بالظبط
  `POST /app-conversations/{existing}/send-message`، والمستودع/الـ sandbox كما هما.

**Phase 2 — الإصلاح:** لا يوجد — لا عيب مؤكَّد في المسار الحالي ⇒ لا تغيير كود (AGENTS.md §6:
ممنوع تغييرات غير مطلوبة؛ §7: ممنوع ادّعاء إصلاح بلا دليل). لم تُلمس أي ملفات إنتاج.

**Phase 3 — اختبارات الانحدار:** أُضيف `tests/test_existing_conversation_repository_context.py`
(13 اختبارًا) يثبّت كل السيناريوهات الاثني عشر المطلوبة. إثبات الطفرة: بحقن fallback إنشاء
صامت مؤقتًا في `_post_claimed` يفشل الاختبار `test_missing_conversation_mapping_fails_safely_without_creation`
(ثم أُعيد `bot/outbox.py` بايت-متطابقًا: sha256 9b203e54…1024b).

**Phase 4 — البوابات:** pytest **2052 passed** (2039 أساس + 13)؛ node **206/0**؛ pyflakes
**exit 0**؛ bandit **High=0** (5 Low/17 Medium موثّقة)؛ pip-audit **No known vulnerabilities found**.

**الحالة:** DONE (لا عيب مؤكَّد؛ اختبارات انحدار مثبِّتة؛ كل البوابات خضراء). لا كتابة git،
لا نداءات إنتاج، Autopush غير مُفعَّل، ملفات F-1 غير المُودَعة لم تُلمس.

**المراجعة المستقلة (عدائية، Cloud API، محادثة `fbe4c0746a8449ce89be10367e2052cc`):**
- الحكم: **PASS-WITH-NOTES**. أكّدت: (أ) استنتاج Phase 1 صحيح (مفيش مسار إنشاء صامت عند
  إرسال برومت لشات موجود)؛ (ب) الاختبارات الـ13 سليمة وغير وهمية — أُعيد تشغيلها وأثبتت
  الطفرات: الباگ المُبلَّغ عنه حرفيًا (توجيه route/reply لـ `_start_new_chat(None, text)`)
  بيكسّر **9 اختبارات**؛ (ج) إضافة الاختبارات لوحدها بلا خطر HIGH/MEDIUM.
- ملاحظتان «HIGH» عند المراجع = **أثر استنساخ معروف**: المراجع بيشوف الـ commits المدفوعة بس،
  فحرّاس F-1 غير المُودَعة وملف الاختبار الجديد مش موجودين عنده (نفس ما هو موثَّق في ذاكرة
  المشروع عن المراجعات السحابية). لا يمثّلان عيبًا في تسليم المهمة.
- ملاحظة MEDIUM (دقة تقرير): اتصلّحت — المانع عند غياب الشات هو فرع «sandbox غير جاهز»، مش
  استثناء ApiError. النتيجة النهائية (مفيش إنشاء) صحيحة.
- ملاحظة خارج النطاق: المراجع رصد أن ثغرة outbox tombstone TOCTOU لسه **غير مطبَّقة في الشجرة
  المدفوعة** — لكنها **مطبَّقة محليًا** في `bot/outbox.py` غير المُودَع (69 سطرًا)؛ ده نطاق
  مهمة سابقة (OHB2-OUTBOX-TOMBSTONE-TOCTOU) ومسجَّل مغلقًا في الذاكرة، ومش نطاق مهمتنا دي.

**الحالة النهائية:** DONE.

---

# PROGRESS — OHB2-DUPLICATE-TELEGRAM-PROMPT-DISPATCH-ROOT-CAUSE-AND-FIX

## Goal
رسالة تيليجرام واحدة من المستخدم لازم تعمل **قرار معالجة واحد** بس: إرسال واحد لشات موجود،
أو إنشاء شات واحد — مش الاتنين. العَرَض المُبلَّغ عنه: برومت لشات موجود A (مربوط بمستودع S)
بيوصل لـ A **وكمان** بيعمل شات جديد B (بدون مستودع) ونفس البرومت بيتبعت له.

## Acceptance criteria
1. تحديث واحد ما يعملش إرسال لشات موجود **و** إنشاء شات جديد في نفس الوقت.
2. إعادة تسليم نفس التحديث (شبكة/إعادة تشغيل/تزامن) ما تعملش عملية OpenHands تانية.
3. المعالجة المتزامنة لنفس التحديث ⇒ قرار معالجة واحد بس.
4. توجيه الشات الموجود + سياق المستودع/الـ sandbox محفوظين.
5. أوامر «شات جديد» الصريحة + الشاتات المستقلة لسه شغالة.
6. رسائل متتالية شرعية (تحديثات مختلفة) ما تتشالْش غلط.
7. استرجاع الصندوق ما يعملش إنشاء شات مكرّر؛ النتائج الغامضة ما تعملش إنشاء بديل.
8. تفويض المستخدم/ملكية الشات لسه مفروضين.

## Root cause (confirmed)
- `Application.builder().concurrent_updates(True)`؛ وكل الـ handlers في مجموعة واحدة (0)،
  وPTB بينفّذ **handler واحد بس لكل مجموعة** (سليم). بس **مفيش ديدَب على مستوى التحديث**:
  `telegram.ext._updater` بيسجّل `_last_update_id` **بعد** ما يحط التحديث في الطابور
  (مش بعد تنفيذه)، ومفيش أي تتبّع لـ `update_id` في الكود.
- النتيجة: أي إعادة تسليم لنفس التحديث (انقطاع قبل تأكيد الـ offset ⇒ إعادة جلب بعد restart؛
  أو التحديث في الطابور مرتين) بتوصل لـ `handle_text` تاني. ولأن `take_awaiting` بتستهلك
  الحالة في المرة الأولى، فالمرة التانية بتشوف حالة مختلفة (مثلاً `newchat` بدل `route`)
  ⇒ **قرار معالجة تاني** مستقل (إرسال A + إنشاء B). ده يفسّر العَرَض حرفيًا.
- المساران نفسهما سليمان (مفيش fallback صامت)؛ المشكلة كانت في **غياب حاجز على مستوى
  التحديث**، مش في مسار الإرسال أو الإنشاء.

## Fix (smallest architecture-compatible)
- جدول **دائم** `processed_updates(update_id INTEGER PRIMARY KEY, processed_at TEXT)`
  (إضافي، `CREATE TABLE IF NOT EXISTS` ⇒ غير مدمّر للقواعد القديمة).
- `Database.mark_update_processed(update_id, now) -> bool` بـ `INSERT OR IGNORE` ذرّي
  (أول نداء يفوز؛ التزامن يعطي True واحد بس). + `prune_processed_updates(keep)` (تقليم
  عند الإقلاع، نافذة 50k) + `count_processed_updates()`.
- `handlers.dedupe_update` مسجّل في **group=-1** عبر `TypeHandler(Update, ...)` (أعلى
  أولوية، أول حاجة تتشغّل). أول مرة ⇒ نكمّل؛ مكرّر ⇒ `raise ApplicationHandlerStop`
  (يوقف كل المجموعات) **قبل أي عملية خارجية**.
- لا worker جديد، ولا مالك قاعدة تاني، ولا ادّعاء exactly-once خارجي (كشف تكرار فقط).

## Tests / mutation evidence
- جديد: `tests/test_duplicate_update_dispatch.py` — **18 اختبار** على **`Application.process_update`**
  (المدخل الكامل)، بقاعدة معزولة وعميل OpenHands وهمي (مفيش شبكة). يغطّي الـ12 سيناريو.
- اختبار العَرَض الحرفي `test_exact_reported_symptom_one_update_cannot_send_and_create`:
  تحديث واحد مرتين (route ثم newchat) ⇒ **إرسال واحد لـ A، صفر إنشاء**.
- **إثبات الطفرة**: حذف تسجيل الحاجز (`group=-1`) ⇒ 4 اختبارات تفشل، منها اختبار العَرَض
  الحرفي اللي بيرجّع `creates == [('برومت', None)]` (شات B بدون مستودع) + إرسال مكرّر
  لـ A — **نفس العَرَض المُبلَّغ عنه**. ثم أُعيد `bot/app.py` بايت-متطابق (sha256 063a85a4…).

## Verification (actual)
- `python -m pytest -q` ⇒ **2070 passed** (2052 أساس + 18)، 72 تحذير، ~79s.
- `node --test tests/frontend/*.test.js` ⇒ **206 pass / 0 fail**.
- `python -m pyflakes bot/ automation/ main.py tests/` ⇒ **exit 0**.
- `python -m bandit -r bot/ automation/ main.py -lll -s B613` ⇒ **High 0** (Low 5، Medium 17).
- `python -m pip_audit -r requirements-dev.txt` ⇒ **No known vulnerabilities found**.
- مجموعات مركّزة (handlers/app/outbox/grouping/u04/f02-f06/batch3r×2/batch-c/existing-context/
  miniapp_operations/resurrection/outbox_commands/db) ⇒ **399 passed**.

## Constraints honored
- لا commit/push/PR/merge/rebase/reset/clean/تبديل فرع. لا staging واسع. لا تعديل Mini App.
  Autopush غير مُفعَّل. لا نداءات إنتاج.
- ملفات F-1 (`bot/outbox.py`, `tests/test_outbox_tombstone_toctou.py`,
  `tests/test_existing_conversation_repository_context.py`, ومحتوى `.agent/PROGRESS.md`
  السابق) لم تُلمس (mtime قديم). التعديلات: `bot/app.py`, `bot/db.py`, `bot/handlers.py`,
  + ملف الاختبار الجديد + هذا القسم.

## Remaining risks / limitations
- الحاجز يمنع **إعادة تسليم نفس `update_id`**. لو تيليجرام (نظريًا) سلّم نفس الرسالة المنطقية
  بمعرّف تحديث **مختلف**، الحاجز مايمنعهاش (لكن إعادة التسليم الفعلية بتعيد نفس `update_id`).
- عقد at-most-once الخارجي زي ما هو: الـ CAS/`unknown` موجودين مسبقًا؛ الحاجز ما بيدّعيش
  exactly-once عبر APIs خارجية.
- سجل `processed_updates` بيكبر ببطء (تقليم 50k عند الإقلاع) — مقبول.

---

# PROGRESS — OHB2-DUPLICATE-DISPATCH-CRASH-CONSISTENCY-AND-FAILURE-REMEDIATION

## Goal
إغلاق مخاطر **فقد بيانات** و**معالجة مزدوجة** اتكشفت في تنفيذ حاجز منع تكرار التحديثات
اللي اتعمل قبل كده (OHB2-DUPLICATE-TELEGRAM-PROMPT-DISPATCH)، مع إصلاح سلوك الفشل.

## الخللان المؤكّدان في التصميم السابق (تسجيل عند الحاجز)
1. **نافذة فقد دائم (data loss):** الحاجز (`group=-1`) كان بيسجّل `update_id` «معالَج»
   **قبل** كتابة سجل العمل الدائم (outbox/creation). لو العملية ماتت/انقطعت في النافذة
   بين الحاجز والكتابة، إعادة تسليم نفس التحديث كانت **بتتخطّى** ⇒ البرومت يضيع للأبد
   (لا سجل، ولا إعادة محاولة).
2. **فشل مقفول ناقص:** لو فحص/تسجيل الحاجز رمى (قاعدة مقفولة)، PTB كان **بيكمّل** للمجموعة
   الجاية (اتأكّد تجريبيًا: PTB بيكمّل عند الاستثناء العادي، وبيبتلع `ApplicationHandlerStop`
   من غير ما يسجّله) ⇒ احتمال معالجة مزدوجة + ادّعاء صامت.

## الإصلاح (أصغر تغيير آمن)
- **الحاجز بقى فحص قراءة فقط** (`Database.update_is_processed`) — **ما بيكتبش** أي حاجة.
- **التسجيل «معالَج» بقى ذرّيًا مع كتابة السجل الدائم**: `_mark_processed_nocommit(update_id, now)`
  بيتنادى **جوه نفس معاملة** `add_or_group_outbox` / `add_creation_job` (INSERT OR IGNORE
  على مفتاح أساسي). النتيجة: إما الاتنين يتكتبوا معًا، أو ولا واحد ⇒ لا نافذة فقد، ولا ازدواج.
- **إغلاق سباق التزامن:** بما إن الحاجز قراءة، نداءين متزامنين لنفس `update_id` ممكن يوصلوا
  للكتابة. الفحص جوه `BEGIN IMMEDIATE` (قفل كتابة قبل القراءة) بيخلّي التاني يشوف «معالَج»
  ويرجع `0`. (`add_or_group_outbox` و `add_creation_job` الاتنين.)
- **عقد القيمة 0:** `_send_prompt`/`_start_new_chat` بيتعاملوا مع `0` (خسارة السباق) بـ
  `return` مبكر ⇒ **مفيش تأكيد كاذب** ولا عملية مكرّرة. مسارات Mini App بتستدعي بنفس العقد
  أصلًا (`if not outbox_id`).
- **فشل مقفول صريح:** `dedupe_update` عند فشل الفحص: `log.exception` (تتبّع كامل — لأن PTB
  بيبتلع الـ stop) + `raise ApplicationHandlerStop` ⇒ المجموعة 0 مابتشتغلش (مفيش تنفيذ مزدوج)،
  والخطأ بيتسجّل (مفيش توه صامت).

## النطاق والمقايضة (مقصودة، موثّقة في docstring)
- العمليات اللي **مابتعملش** سجل دائم (رد/توجيه/أوامر/أزرار) مش مسجّلة «معالَج» ⇒ إعادة
  تسليمها بتعيد الرد. أغلبها قراءة/idempotent، وقليل بيغيّر حالة صغيرة (مثل `notif:toggle`).
- **المقايضة مقصودة:** إغلاق نافذة **فقد البرومت** (الأثر الأعلى) اتقدّم على منع تكرار تبديل
  الإشعارات (إعادة تسليم كولباك نادرة + أثر بسيط قابل للرجوع). **الالتزام القائم** «تحديث
  واحد ⇒ قرار إرسال/إنشاء واحد» محفوظ بالكامل (وهو موضوع التقرير الأصلي).
- السبب: البديل (تسجيل عند الحاجز + تعافي عند الإقلاع) بيحوّل المقايضة من «فقد البرومت»
  لـ «منع تنفيذ تاني لتحديث لسه ما اتنفّذش» — نفس عدم الحتمية، مش حلها. الفحص-القراءة
  يحسم الحالة الصحيحة بلا تخمين.

## الاختبارات (جديد: 5 اختبارات في `tests/test_duplicate_update_dispatch.py` ⇒ الإجمالي 23)
1. `test_guard_is_read_only_marker_written_with_durable_record` — الحاجز مش بيسجّل؛ الكتابة
   الدائمة هي اللي بتسجّل.
2. `test_guard_db_error_fails_closed_stops_handlers_and_logs` — فشل القاعدة ⇒ مفيش صندوق،
   مفيش إرسال، وخطأ مسجّل (caplog).
3. `test_same_update_second_write_in_transaction_rejected` — كتابة تانية بنفس `update_id`
   ⇒ `0` (سجل واحد بس).
4. `test_two_distinct_updates_both_written` — تحديثين مختلفين ⇒ سجلين (مفيش رفض كاذب).
5. `test_crash_between_guard_and_durable_write_does_not_lose_prompt` — عطل بعد الحاجز وقبل
   الكتابة ⇒ إعادة التسليم **تنفّذ** (مفيش فقد).

## إثبات الطفرة (mutation)
- حذف الفحص الذرّي جوه المعاملة (الموضعين) ⇒ `test_same_update_second_write_in_transaction_rejected`
  يفشل (`assert 1 == 0`). ثم أُعيد `bot/db.py` بايت-متطابق.
- إرجاع الحاجز للتصميم القديم (`mark_update_processed` عند الحاجز) ⇒
  `test_crash_between_guard_and_durable_write_does_not_lose_prompt` يفشل (البرومت بيضيع).
  ثم أُعيد `bot/handlers.py` بايت-متطابق.
- تحقّق تجريبي مباشر لـ PTB 22.8: استثناء عادي في handler ⇒ بيتسجّل (بيكمّل للمجموعة الجاية)؛
  `ApplicationHandlerStop` ⇒ بيتلغطّى وبيمنع المجموعة الجاية، **بدون** أي لوج ⇒ لذا بنسجّل بنفسنا.

## Verification (actual)
- `python -m pytest -q` ⇒ **2075 passed** (2070 أساس + 5)، 72 تحذير، ~78s.
- `python -m pyflakes bot/ tests/` ⇒ **exit 0**.
- الملفات المعدّلة: `bot/db.py`, `bot/handlers.py`, `bot/app.py`, `README.md`,
  `tests/test_duplicate_update_dispatch.py`, وهذا القسم. مسارات F-1 لم تُلمس.

## Remaining risks / limitations
- إعادة تسليم **كولباك يغيّر حالة صغيرة** (مثل تبديل الإشعارات) ممكن تتكرّر (موثّق أعلاه).
- الحاجز يمنع إعادة تسليم **نفس `update_id`**؛ معرّف تحديث مختلف لنفس الرسالة المنطقية لا
  يُمنع (نفس القيد السابق).
- عقد at-most-once الخارجي زي ما هو (CAS/`unknown` مسبقًا) — الحاجز ما بيدّعيش exactly-once.

---

# PROGRESS — OHB2-ONE-SHOT-ROUTING-CRASH-CONSISTENCY

## Goal
إغلاق نافذة الفقد المؤكّدة للحالات لمرة واحدة (reply/newchat/reposearch) + معالجة
P2 (فشل القاعدة) و P3 (تبديل الإشعارات المكرّر) — بدون أي مخزن/worker جديد.

## Acceptance criteria
1. استهلاك الحالة لمرة واحدة + كتابة العمل الدائم = معاملة SQLite واحدة (أو تعافٍ مكافئ).
2. اختبار انحدار بيفشل لو فصلنا الاستهلاك عن الكتابة (mutation-verified).
3. حمايات منع التكرار الحالية سليمة. 4. لا ارتداد F-1/تفويض. 5. pytest + pyflakes يعدّوا.
6. الـ diff بيحفظ شغل المستخدم. 7. مفيش نشر/commit/push.

## Root cause (مؤكّد مستقلًا)
`handle_text` كان بينادي `take_awaiting` اللي **بيـcommit استهلاك** الحالة لمرة واحدة،
وبعدين معاملة **تانية** بتكتب السجل الدائم. عطل بينهم = فقد دائم (الحالة اتمسحت، مفيش سجل،
وإعادة التسليم بتلاقي مفيش حالة).

## الإصلاح (أصغر تغيير آمن، بدون تغيير المعمارية)
- `handle_text` بقى **يقرأ بدون استهلاك** (`Database.awaiting_state`)، و`route` بيتجدّد
  (`renew_awaiting`)، والحالة المنتهية بتتمسح وتتبلّغ (زي الأصل).
- `add_or_group_outbox`/`add_creation_job` بياخدوا `consume_awaiting=(telegram_id, kind)`:
  الفحص + مسح الحالة + كتابة السجل الدائم + علامة «معالَج» **جوه نفس `BEGIN IMMEDIATE`**.
  حالة متغيّرة/منتهية ⇒ رجوع 0 بدون كتابة. استثناء ⇒ rollback للكل.
- `consume_one_shot_awaiting` لبحث المستودعات (مساره مافيهوش سجل دائم): بيعمل الحالة +
  علامة «معالَج» ذرّيًا **بعد** إرسال القايمة (عطل قبل كده ⇒ إعادة تنفيذ، قايمة مكرّرة غير ضارة).
- P3: `Database.toggle_notifications_once(update_id, now)` — التبديل + العلامة في معاملة
  واحدة؛ نفس `update_id` ⇒ مفيش تبديل تاني؛ `update_id` مختلف ⇒ تبديل عادي.
- P2 (موثّق غير مُصلَح): fail-closed زي ما هو + توضيح الحدود في docstring `dedupe_update`
  (مفيش requeue؛ `drop_pending_updates=True` ⇒ إسقاط نادر محتمل وقت عطل قاعدة عابر).

## Verification (actual)
- `python -m pytest -q` ⇒ **2094 passed** (2075 + 19 جديد)، 72 تحذير.
- `python -m pyflakes bot/ tests/` ⇒ **exit 0**. `bandit -lll -s B613` ⇒ **exit 0**.
- mutation 1 (فصل الاستهلاك في handlers) ⇒ 7 اختبارات تفشل. mutation 2 (شيل حاجز P3) ⇒ 1 يفشل.
- ملفات المهمة: `bot/db.py`, `bot/handlers.py`, `README.md`, `tests/test_one_shot_awaiting_atomicity.py`, هذا القسم.

---

# PROGRESS — OHB2-SW04 + OHB2-SW05 (تفويض upstream + فشل التسليم)

## Goal
إصلاحان ضيّقان: (SW-04) الحفاظ على تمييز `UPSTREAM_ERROR` من `_authorized_conversation`،
و(SW-05) إيقاف تجاهل فشل `_edit_or_send()` الصامت. بدون لمس SW-02، ولا F-1، ولا الاستطلاع/
الإقرار/إدارة offset، وبدون أي مكوّن معماري جديد.

## Acceptance criteria
1. فشل `/users/me` (upstream) يفضل `UPSTREAM_ERROR` (502) ولا يتحوّل لـ `UNAUTHORIZED` (403).
2. غياب الهوية (`{}`/بلا id) لسه `UNAUTHORIZED` (فشل مغلق محفوظ). 3. كل مستدعي التفويض
   مايحوّلش عطل الخدمة لرفض تفويض، وماينفّذش عملية من غير تفويض مؤكّد. 4. كل مستدعي
   `_edit_or_send` المتأثّر يتعامل مع `False`؛ مفيش نجاح كاذب؛ مفيش استثناء بيطلع من فرع فشل.
5. pytest + pyflakes + bandit يعدّوا. 6. مفيش commit/push/نشر. 7. شغل المستخدم محفوظ.

## Root causes (مؤكّدة تجريبيًا)
- SW-04: `IdentityCache.owner_id()` كان بيحوّل أي `ApiError` من `/users/me` لـ None، فـ
  `authorize_conversation_detailed` بتحوّله `UNAUTHORIZED` ⇒ عطل 429/503/مهلة يبان رفض
  تفويض عادي (403) بدل upstream (502) — على البوت والـ Mini App.
- SW-05: `show_status`/`show_cost` كانوا بيتجاهلوا القيمة الراجعة؛ وفرع «too long» في
  `_edit_or_send` كان بيرمي استثناء الإرسال البديل للخارج بدل ما يرجّع False.

## الإصلاح (أصغر تغيير آمن)
- `bot/files.py`: `IdentityCache.owner_id_detailed()` جديدة تفرّق (`UPSTREAM_ERROR` مقابل
  `UNAUTHORIZED`)؛ `owner_id()` بقت غلاف متوافق يرجّع الهوية فقط (بلا تغيير سلوك).
  `authorize_conversation_detailed` بتستخدم التفصيل. الاتنين لسه رفض مغلق (مفيش نجاح).
- `bot/handlers.py`: `_edit_or_send` بترجّع False عند فشل الإرسال البديل (بلا استثناء)؛
  `show_status`/`show_cost`/`open_conversation` (فرعا الرفض وخطأ التبادل) بيفحصوا النتيجة
  ويسجّلوا تحذير صريح. توثيق docstring محدّث.
- تحديث اختبارين قديمين كانوا بيثبّتوا التلبيس القديم (`test_a2_owner_cache.py`,
  `test_files_service.py`) + ملف انحدار جديد `tests/test_sw04_sw05_authz_upstream_and_delivery.py`.

## Verification (actual)
- `python -m pytest -q` ⇒ **2231 passed** (الأساس 2183 + 48 صافي جديد)، 72 تحذير.
- `python -m pyflakes bot/ automation/ main.py tests/` ⇒ **exit 0**.
- `bandit -r bot/ automation/ main.py -lll -s B613` ⇒ High: 0. `node --test tests/frontend/*.test.js` ⇒ 206 pass.
- `pip-audit -r requirements-dev.txt` ⇒ No known vulnerabilities found.
- mutation: إرجاع تلبيس SW-04 ⇒ 3 اختبارات تفشل؛ إرجاع رمي SW-05 ⇒ 1 يفشل؛ تجاهل النتيجة ⇒
  1 يفشل؛ تجاهل فرعي open ⇒ 2 يفشلون. كل الملفات أُعيدت بايت-متطابق بعد كل طفرة.

## Remaining risks / limitations
- `show_status`/`show_cost` ما زالا بيسجّلوا فشل التسليم بدل ما يعيدوا المحاولة (مفيش retry
  أعمى — ممنوع منعًا لتكرار الرسايل). المستخدم ممكن ما يشوفش الرد، لكن مفيش ادعاء نجاح كاذب.
- SW-02 (لَوْ LOW): مؤجّل — ما اتلمسش.

## Assumptions / decisions
- التمييز SW-04: «فشل upstream في `/users/me`» ⇒ `UPSTREAM_ERROR`؛ «الهوية غائبة/ناقصة» ⇒
  `UNAUTHORIZED`. الاتنين رفض مغلق، فالقرار الأمني (ممنوع) ما اتغيّرش.
- اخترت تحديث اختبارين قديمين بدل تركهما يفشلان (تثبيت السلوك القديم الخاطئ كان هيكسر البوابة).

---

# PROGRESS — OHB2-MANUAL-POLLING-OUTCOME-AND-ACK-BOUNDARY-CORRECTION

## Goal
إغلاق المشاكل الخمس غير المحلولة في تصميم الـ Manual Polling (من مراجعة التصميم السابقة):
(1) نتيجة معالجة **دائمة** تُكتب ذرّيًا مع عملية القاعدة اللي بتنفّذ نية التحديث،
(2) فشل الـ handlers المُبتلَع ما يتحوّلش لنجاح، (3) حدّ الإقرار = أطول بادئة مؤهّلة
بترتيب الاستقبال (مش max+1)، (4) معاملة ذرّية للنتائج + حدّ الإقرار (restart-safe)،
(5) تحليل آثار جانبية خارجية قبل الـ commit. **بدون** تنفيذ ترحيل الـ Manual Polling.

## Acceptance criteria
1. النجاح الدائم مُثبَت من معاملة قاعدة مُـcommitted (عمود outcome) — مش من رجوع الـ handler.
2. الاستثناءات المُبتلَعة/النتائج الغامضة ما تتقبلش كنجاح (fail-closed: مفيش سجل مؤهّل ⇒ غير مؤهّل).
3. حدّ الإقرار = أطول بادئة مؤهّلة بترتيب الاستقبال، وبيتعامل مع فجوات المعرّفات.
4. كتابة النتائج + الحدّ المحلي ذرّية (معاملة واحدة) وrestart-safe.
5. سلوك crash/retry للآثار الجانبية الخارجية محلَّل ومغطّى باختبارات أو معلَّم UNRESOLVED.

## Plan
1. `bot/update_outcomes.py`: ثوابت النتائج + تصنيف الفشل + `acknowledgment_boundary()` (نقي).
2. `bot/db.py`: عمود `outcome` + جدول `update_failures` + APIs + `commit_batch_outcomes` + حدّ الإقرار.
3. `bot/handlers.py`: error handler + تسجيل الفشل في مسارات الابتلاع.
4. `bot/app.py`: تسجيل error handler.
5. `tests/test_manual_polling_outcome_and_ack.py`: اختبارات مركّزة.
6. التحقق الكامل: pytest + pyflakes.

## Assumptions / decisions
- **بدون** تبديل فرع (المهمة منعت `switch branches` صراحةً) ⇒ العمل على `main` بدون commit/push.
- **بدون** ربط بحلقة الاستطلاع الحيّة (تغيير دلالات الإقرار/الـ offset = ممنوع) ⇒ المكوّنات مكتبة + اختبارات.
- `update_is_processed` (ديدَب) ما اتغيّرش؛ الأهلية للإقرار بقت على `outcome` (fail-closed).
- `update_failures` جدول منفصل ⇒ ما يلمسش دلالات الديدَب.

## Results (verified)
- `pyflakes bot/ automation/ tools/ main.py tests/` ⇒ exit 0.
- `python -m pytest -q` ⇒ **2348 passed** (baseline 2315 + 33 جديد)، 72 warnings.
- الجديد: `tests/test_manual_polling_outcome_and_ack.py` (33 اختبار) — كلها بتنجح.
- ملفات معدّلة في المهمة دي: `bot/update_outcomes.py` (جديد), `bot/db.py`,
  `bot/handlers.py`, `bot/app.py`, `tests/test_manual_polling_outcome_and_ack.py` (جديد),
  `.agent/PROGRESS.md`.
- محفوظات محميّة (لم تُلمس): `bot_state.sqlite3` sha256 = 72453e96…09463318،
  `AGENTS.md` sha256 = d6ceda4e…f6565bc4، WAL فاضي، SHM زي ما هو.
- Branch `main`، HEAD `1b201ba0…` — **مفيش** commit/push/PR.

## الحدود المعمارية اللي **ما اتعبرتش** (تحتاج موافقة منفصلة)
- الحدّ المحلي (`commit_batch_outcomes`/`get_acknowledgment_boundary`) **مش** موصول
  بحلقة استطلاع حيّة، ولا اتغيّر `getUpdates`/offset/`drop_pending_updates`/دلالات الإقرار.
  ربط الحدّ بـ `getUpdates(offset=boundary+1)` = **تغيير معماري** ممنوع في المهمة دي.
- `delete_conversation_confirm`: حذف الشات البعيد **مش** idempotent بالكامل (الـ CAS
  بيمنع الطمس، بس إعادة المحاولة ممكن تعمل DELETE تاني ⇒ 404 مبهم ⇒ تسوية تحقق).
  المسار ده لسه زي ما هو (مفيش تغيير دلالات) ومعلَّم UNRESOLVED.

---

# PROGRESS — OHB2-MANUAL-POLLING-HANDLER-OUTCOME-COVERAGE

## Goal
إغلاق فجوات تسجيل نتائج المعالجات اللي حدّدها OHB2-MANUAL-POLLING-ACK-INTEGRATION-DESIGN:
كل تنفيذ ذي صلة لأي معالج تيليجرام لازم يسجّل **نتيجة صريحة مصنّفة صح** قبل ما يرجع،
والفشل الغامض/غير المحسوم يفضل **غير مؤهّل** (fail-closed).

## Acceptance criteria
1. كل مسار رجوع ذي صلة في المعالجات المسجّلة (26) عنده نتيجة مصنّفة (durable/ignored/
   ambiguous/transient/permanent) — مش رجوع بلا نتيجة.
2. `durable_completed` بس عند عملية قاعدة **مُـcommitted** فعلًا (مفيش نجاح كاذب).
3. النتائج الغامضة/الفشل المُبتلَع ⇒ `partial_or_unknown`/`failed_*` (غير مؤهّل).
4. مسار الديدَب الفاشل ما يتحوّلش لتجاهل/نجاح صامت.
5. pytest + pyflakes + bandit يعدّوا. 6. مفيش commit/push. 7. شغل المستخدم محفوظ.

## Plan (done)
1. helpers جديدة في `bot/handlers.py`: `mark_ambiguous_external`, `mark_display_failed`,
   `mark_failed_permanent` + إعادة استخدام الموجودة.
2. ربط العلامات بكل نقاط رجوع المعالجات المسجّلة (تفويض/قراءة/عمليات دائمة/فشل عرض).
3. إصلاح أخطاء الإدراج (indent)، وإزالة علامات غير قابلة للوصول/خاطئة.
4. `tests/test_manual_polling_handler_outcome_coverage.py` — اختبارات انحدار مركّزة.
5. تعديلات دقّة: مسار الرفض 4xx في `list_conversations` بقى `explicitly_ignored`
   (المسار التشغيلي اترفع فوقه)؛ حالة الانتظار **المنتهية** في `handle_text` بقت
   `explicitly_ignored` (البرومت ما اتنفّذش عمدًا) بدل `durable_completed`؛ `_send_prompt`
   للنص الفاضي بقى `explicitly_ignored`.

## Results (verified)
- `python -m pytest -q` ⇒ **2375 passed**، 72 warnings، ~97s (baseline الجلسة 2348 + 27 جديد).
- `python -m pyflakes bot/ automation/ tools/ main.py tests/` ⇒ exit 0.
- `python -m bandit -r bot/ automation/ main.py -lll -s B613` ⇒ exit 0 (High 0).
- `node --test tests/frontend/*.test.js` ⇒ 219 pass / 0 fail.
- `python -m pip_audit -r requirements-dev.txt` ⇒ No known vulnerabilities found.
- إثبات الطفرة: حذف تسجيل فشل الديدَب ⇒ `test_dedupe_db_failure_records_failure_and_stops` يفشل.
- الملفات المعدّلة في المهمة: `bot/handlers.py`،
  `tests/test_manual_polling_handler_outcome_coverage.py` (جديد)، `.agent/PROGRESS.md`.
- Branch `main`، HEAD `1b201ba0…` — **مفيش** commit/push/PR.

## Assumptions / decisions
- «حالة انتظار منتهية» = تجاهل صريح (مفيش نية دائمة معلّقة)، مش إتمام دائم.
- مسار `_show_repos` بلا `update` ⇒ ما بيتسجّلش جواه (المستدعي بيسجّل) — مقصود.

---

## OHB2-STAGE2-CUSTOM-POLLING-DURABLE-ACK-IMPLEMENTATION (منفّذ)

### Goal
تنفيذ Stage 2 (القرارات المعتمدة D0–D5): حلقة استطلاع مخصّصة (Option A: `updater(None)` +
`getUpdates` مخصّص) + حدّ إقرار دائم، مع حلّ فجوة ADR §22.2 (Option 2: تسجيل «مفيش handler»).

### Acceptance criteria (مُتحقّقة)
1. التطبيق مبني بـ `updater(None)` ⇒ مفيش Updater/`run_polling` ⇒ **مفيش poller تاني**.
2. الإقلاع: `deleteWebhook(drop_pending_updates=False)` ثم `offset = B+1` أو `None` (**حفظ المعلّق**).
3. `allowed_updates=["message","callback_query"]` + fallback `handle_unmatched_update` يسجّل
   `explicitly_ignored` (بدون كتابة فوق نتيجة محفوظة، بدون تحويل استثناء لتجاهل).
4. الحكم من **نتيجة دائمة** (`db.update_outcome`)، الافتراضي `partial_or_unknown` (fail-closed).
5. `commit_batch_outcomes`: نتائج + حدّ **ذرّية** + **مونوتونية** (مايتراجعش).
6. الرفض الآمن للمرفقات سليم؛ حالة P0 لسه `BLOCKED / DEFERRED BY EXPLICIT PRODUCT DECISION`.

### Changes
- `bot/polling.py` (**جديد**): `TelegramPoller` (bootstrap/fetch/dispatch_and_wait/collect_outcomes/
  commit/advance_offset/backoff/stop) + `run_bot` (تنظيم دورة الحياة).
- `bot/app.py`: `.updater(None)` + تسجيل `handle_unmatched_update` كآخر handler في group 0.
- `bot/handlers.py`: `handle_unmatched_update` (fallback آمن).
- `bot/db.py`: حارس مونوتونية الحدّ جوه `commit_batch_outcomes`.
- `main.py`: `asyncio.run(run_bot(app))` بدل `run_polling(drop_pending_updates=True)`.
- `tests/test_startup_policy.py`: تحديث العقد (مفيش `run_polling`).
- `tests/test_stage2_custom_polling.py` (**جديد**): 32 اختبار انحدار.

### Results (verified)
- `python -m pytest -q` ⇒ **2507 passed**، 72 warnings (baseline 2478 + 29 صافي جديد).
- `python -m pyflakes bot/ automation/ tools/ main.py tests/` ⇒ exit 0.
- `node --test tests/frontend/*.test.js` ⇒ 219 pass / 0 fail.

### Known limits / NOT implemented
- §28.4 (مخطط `ack_offset_submitted/confirmed` + علم poison) ⇒ **لم يُنفَّذ** (خارج النطاق).
- **مفيش ادّعاء exactly-once خارجي** (at-most-once + إعادة تسليم idempotent).
- فجوة §18.2 (تأكيد نداء `getUpdates` بعد انهيار) غير قابلة للتجنّب — محفوظة.
- الحجب head-of-line لتحديث فاشل مقصود (fail-closed) ويُعاد تسليمه لاحقًا.

### Assumptions / decisions
- الـ fallback بيكتب النتيجة بنفسه (مصدر حقيقة واحد) بدل تتبّع «لمسه handler».
- «مفيش handler» ⇒ `explicitly_ignored` (مؤهّل)؛ «handler لكن مفيش نتيجة» ⇒ `partial_or_unknown`.

---

## OHB2-PLAN-01-STAGE3-SAFE-RETENTION (منفّذ)

### Goal
تقليم آمن لسجل `processed_updates` بعد ما الحدّ الدائم (Stage 2) بقى مؤثّرًا.

### Acceptance criteria (مُتحقّقة)
1. التقليم يشيل بس الصفوف `update_id <= الحدّ` (الذيل غير المؤكَّد يفضل دايمًا).
2. مفيش حدّ ⇒ **no-op** (مفيش تقليم بلا watermark).
3. `keep` بيسيب أحدث `keep` صف من اللي `<= الحدّ` بس.
4. النداء في `_post_init` بيقرا `get_acknowledgment_boundary()` ويمرّره.

### Changes
- `bot/db.py`: `prune_processed_updates(keep=None, boundary=None)` واعيًا بالحدّ.
- `bot/app.py`: الـ `_post_init` بيمرّر الحدّ الدائم للتقليم.
- `tests/test_duplicate_update_dispatch.py`: 4 اختبارات (no-op / `keep=None` / الذيل محفوظ / نافذة keep).
- `tests/test_app.py`: 2 اختبارات (ربط الـ post_init بالحدّ + no-op بلا حدّ).

### Results (verified)
- `python -m pytest -q` ⇒ **2516 passed**، 72 warnings.
- `python -m pyflakes bot/ automation/ tools/ main.py tests/` ⇒ exit 0.
- `python -m bandit -r bot/ automation/ main.py -lll -s B613` ⇒ exit 0.
- **إثبات طفرة:** شيل فلتر الحدّ ⇒ اختبار يفشل؛ فرّغ فرع `keep=None` من الحدّ ⇒ اختباران يفشلان.

### Known limits
- التقليم لسه **عند الإقلاع بس** (زي قبل) — مقصود (أصغر تغيير). لو الحدّ مونوتوني دايمًا فالتقليم
  المتكرّر أثناء التشغيل ممكن مستقبلًا، لكنه خارج نطاق Stage 3.

---

## OHB2-STAGE2-HIGH-ACK-BLOCKING-FIX (منفّذ — بلا commit بعد)

### Goal
إصلاح عيب حجب الإقرار (HIGH) اللي أثبتته المراجعة العدائية المستقلة على `907b20d`:
`open_conversation`/`copy_reply`/`full_reply` يرجعوا على مسارات الرفض النهائي/فشل العرض
بلا **نتيجة دائمة** ⇒ `partial_or_unknown` (غير مؤهّل) ⇒ الحدّ/الـ offset يفضلوا ثابتين ⇒
إعادة تسليم لا نهائية تحجب كل التحديثات اللي بعدها.

### Acceptance criteria (مُتحقّقة)
1. كل مسار رفض نهائي مؤكّد يسجّل نتيجة دائمة مؤهّلة (`explicitly_ignored`).
2. فشل عرض تيليجرام **مايتحوّلش** لنجاح/تجاهل (`failed_transient`، غير مؤهّل).
3. الفشل التشغيلي upstream (5xx/429/بلا كود) لسه **ينتشر** (SW-07) — مايتحوّلش لتجاهل.
4. الحدّ والـ offset يتقدّموا بعد التحديث الحاجب، والتحديث اللي بعده يتعالج.
5. تحديث غير مؤهّل سابق لسه يحجز الحدّ (مفيش تجاوز).

### Changes
- `bot/handlers.py`: `mark_explicitly_ignored` بره شرط `UPSTREAM_ERROR` في فرعي
  `_conv is None` لـ `copy_reply`/`full_reply` + فرع `conv is None` لـ `open_conversation`؛
  و`mark_display_failed` لفرع فشل عرض فتح الشات.
- `tests/test_stage2_high_ack_blocking_fix.py`: 25 اختبار انحدار (نتيجة/أهلية فعلية +
  end-to-end عبر `TelegramPoller`).

### Results (verified)
- `python -m pytest -q` ⇒ **2541 passed** (2516 + 25 جديد)، 72 warnings.
- `node --test tests/frontend/*.test.js` ⇒ **219 pass / 0 fail**.
- `python -m pyflakes bot/ automation/ tools/ main.py tests/` ⇒ exit 0.
- `python -m bandit -r bot/ automation/ main.py -lll -s B613` ⇒ High **0**.
- `python -m pip_audit -r requirements-dev.txt` ⇒ **No known vulnerabilities found**.
- **إثبات طفرة:** إرجاع `bot/handlers.py` لأصل `907b20d` ⇒ **16 اختبار يفشل**؛ الإصلاح ⇒ 25 pass.

### Known limits / decisions
- سياسة فشل العرض: **عابر** (`failed_transient`) — نفس سياسة `show_status/show_cost`؛
  مفيش `mark_permanent` لأن العبور التالي بيحاول تاني (سلوك مقصود).
- Stage 3 لم يُلمس. P0 لسه مؤجّل. Stage 5/SW-02 لم يُلمس. مفيش commit/push/PR/نشر.

---

# PROGRESS — OHB2-STAGE4-F1-FAIL-CLOSED-OPERATIONAL-ACK-FIX (منفّذ)

## Task ID
`OHB2-STAGE4-F1-FAIL-CLOSED-OPERATIONAL-ACK-FIX`

## الحالة
`DONE` — إصلاح F1 مطبَّق ومُتحقَّق منه (بلا commit/push/PR/نشر).

## Goal
حلّ عيب Stage 4 F1 المؤكَّد: `show_status`/`show_cost` كانوا بيسجّلوا `explicitly_ignored`
(نتيجة **مؤهّلة** للإقرار) لأي `conv is None`، بما فيه **الفشل التشغيلي** upstream
(5xx/429/مهلة/انقطاع) ⇒ تحديث عرض فاشل تشغيليًّا كان بيتقبل كأنه اتعالج (الحدّ/الـ offset
يتقدّموا فوقه، ومفيش إعادة محاولة بعد التعافي). مطلوب: الفشل التشغيلي ⇒ `failed_transient`
(غير مؤهّل، fail-closed)، مع الحفاظ على الرفض النهائي المؤكّد `explicitly_ignored`.

## Baseline (مُتحقَّق منه قبل التغيير)
- Branch: `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`؛ HEAD: `907b20d`؛ parent/origin-main: `a29164f`.
- `git status --short`: ` M .agent/PROGRESS.md`، ` M bot/handlers.py`، `?? tests/test_stage2_high_ack_blocking_fix.py`.
- إصلاح Stage 2 HIGH لسه **غير مُودَع** (محفوظ كما هو). عيب F1 **اتأكّد** على الشجرة الحالية (500/429 ⇒
  `explicitly_ignored`, eligible=True) قبل التعديل.

## Root cause
`show_status`/`show_cost` كانوا بيستخدموا الغلاف `_authorized_conversation` اللي **بيسقّط**
`status`/`exc`، فمسار `conv is None` ماكانش بيفرّق بين فشل تشغيلي (5xx/429/بلا كود) ورفض
نهائي مؤكّد (404/403/NOT_FOUND/DELETED/UNAUTHORIZED) ⇒ الاتنين `mark_explicitly_ignored`.

## Changes (ملفات + سبب)
- `bot/handlers.py`:
  - دالة جديدة `mark_operational_failure(update, context, reason)` — تسجيل **صارم** `FAILED_TRANSIENT`
    (لو تعذّر التسجيل ⇒ **يرفع**، ممنوع نجاح صامت).
  - `show_status`/`show_cost`: استخدام المسار المفصّل `_authorized_conversation_status`؛ عند `conv is None`:
    فشل تشغيلي (`UPSTREAM_ERROR` وبلا رفض متوقّع) ⇒ `mark_operational_failure` (غير مؤهّل)؛ غير كده
    (رفض نهائي مؤكّد) ⇒ `mark_explicitly_ignored` (مؤهّل). نجاح العرض/فشل التسليم زي ما كانوا.
- `tests/test_stage4_f1_status_cost_operational_ack.py` (**جديد**): 28 اختبار (status/cost ×
  500/502/503/429/مهلة/انقطاع/404/403/NOT_FOUND/نجاح/فشل تسليم/فشل تسجيل + E2E عبر `TelegramPoller`
  للحدّ والـ offset + التعافي بإعادة التسليم).
- `docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md`: صف في §30.2 + قسم **§37** (سياسة F1 الكاملة).
- `.agent/PROGRESS.md`: القسم ده.

**لم يُلمس:** `bot/db.py`، `bot/polling.py`، `bot/update_outcomes.py`، `bot/app.py` (البنية fail-closed
القائمة أُعيد استخدامها كما هي). إصلاح Stage 2 HIGH محفوظ بايت-متطابق. Stage 3 سليم.

## Tests / Results (فعلية)
- `tests/test_stage4_f1_status_cost_operational_ack.py` ⇒ **28 passed**.
- **إثبات طفرة (F1):** إرجاع فرعي F1 لأصل السلوك القديم ⇒ **17 failed / 11 passed** (الاختبارات بتكشف
  العيب)؛ بعد الاسترجاع ⇒ 28 pass. الملف اتأكّد بايت-متطابق (sha256 `da589518…b748`).
- الحزم المركّزة (sw07/sw04-sw05/manual-polling-outcome/stage2-high/b06/stage2-custom/dup-dispatch) ⇒ **230 passed**.
- Full suite: **2569 passed** (2541 + 28 F1)؛ node **219 pass**؛ pyflakes exit 0؛ bandit High 0؛ pip_audit clean.

## Acknowledgement boundary / offset
- E2E: فشل تشغيلي ⇒ `failed_transient` مُثبَّت ⇒ الحدّ `None` والـ `_next_offset` `None` (مااتقدّمش)؛
  التحديث اللي بعده **مؤهّل** بس الحدّ واقف عند الأول (مفيش تجاوز). الرفض النهائي (404) ⇒ الحدّ يتقدّم.
- التعافي: تحديث الفشل **مايسجّلش** «معالَج» ⇒ إعادة التسليم تنفّذ تاني ⇒ لو نجح ⇒ `explicitly_ignored` ⇒ الحدّ يتقدّم.

## Remaining limitations
- لو فشل OpenHands التشغيلي **دائم**، الحدّ/الـ offset يتوقّفوا عند أول تحديث عالق (حجب head-of-line)
  لحد التعافي. سلوك fail-closed **مقصود**. **مفيش** مسار تجاوز تلقائي ولا آلية poison bypass.
  التعافي: إعادة تسليم ناجحة بعد زوال الفشل، أو قرار منفصل لتجاوز poison (§28.4، مؤجّل).
- المسارات التانية (`open`/`copy`/`full`) بتستخدم **الانتشار** (raise) للفشل التشغيلي (سلوك قائم، مش
  جزء من F1). توحيد الأسلوبين قرار منفصل — **لم يُنفَّذ**.

## Current Stage 4 status
`DONE` — F1 مُصلَح ومُتحقَّق منه. Stage 4 اكتمل (كان موقوفًا على قرار F1).

## Safety
مفيش commit/push/PR/merge/deploy/نداء إنتاجي/وصول أسرار. Stage 2 HIGH محفوظ. Stage 3 سليم.
§28.4 وStage 5/SW-02 لم يُلمسا. P0 لسه مؤجّل بقرار منتج.

## إغلاق تغطية LOW — OHB2-STAGE4-F1-LOW-COVERAGE-CLOSURE (2026-11-11)
المهمة: إغلاق ملاحظتي LOW من المراجعة العدائية المستقلة (`OHB2-STAGE4-F1-INDEPENDENT-ADVERSARIAL-REVIEW`).
**اختبارات فقط** — مفيش تعديل تنفيذ. النطاق: ملف Stage 4 F1 + هذا السجل.

- **Test A — فشل تسليم رسالة الخطأ:** فشل OpenHands تشغيلي + فشل تسليم رسالة الخطأ (`BadRequest`).
  `_safe_edit` بيعيد رفع الاستثناء (مش "not modified") ⇒ التنفيذ يتوقف **قبل** أي تسجيل.
  الثابت: التحديث **مستحيل يبقى مؤهّل** ومفيش `explicitly_ignored`. ملاحظة دقيقة: في نداء الـ handler
  مباشرة النتيجة `None`؛ عبر حلقة الاستطلاع الحقيقية معالج الأخطاء بيسجّل `failed_permanent` —
  الاتنين **غير مؤهّلين**، فالاختبار بيؤكّد على عدم الأهلية (مش على قيمة النتيجة).
  E2E: الحدّ `None` و`_next_offset` `None` و`update_is_processed` False.
- **Test B — فشل `/users/me`:** جلب الشات بينجح لكن `/users/me` يفشل (5xx/429/مهلة/انقطاع) ⇒
  `authorize_conversation_detailed` بتحفظ الاستثناء ⇒ `failed_transient` (مش `explicitly_ignored`)،
  غير مؤهّل. E2E: الحدّ و`_next_offset` مايتقدّموش.
- **الاختبارات الجديدة:** 17 (28 ⇒ **45** في ملف F1).
- **إثبات طفرة (نسخة مؤقتة خارج المستودع):** (A) شيل تصنيف الفشل التشغيلي ⇒ **30 فشل**؛
  (B) إرجاع `_safe_edit` ليبلع الخطأ ⇒ **2 فشل**؛ (C) تسجيل `explicitly_ignored` **قبل** عرض
  رسالة الخطأ ⇒ **17 فشل** (منها اختبارات Test A الجديدة) — إثبات إن المسار الكاذب مكشوف.
- **البوابة:** pytest **2586 passed**؛ node **219 pass**؛ pyflakes exit 0؛ bandit High 0؛ pip_audit clean.
- **مفيش** تغيير في `bot/handlers.py` (sha256 `da589518…b748` كما هو) ولا ADR ولا Stage 2/3. مفيش commit/push.

---

# PROGRESS — OHB2-PLAN01-STAGE5-FORMAL-CLOSURE-AND-PLAN-RECONCILIATION (2026-11-11)

## Goal
إغلاق Stage 5 رسميًّا عبر **مسار UNKNOWN الصريح** في الخطة الأصلية، ومصالحة حالة الخطة الكاملة —
**توثيق فقط**، بلا اختراع لمعنى SW-02.

## Source
نصّ خطة `OHB2-PLAN-01-TELEGRAM-ACK-AND-DELIVERY-RELIABILITY` **مُزوَّد من صاحب المشروع** (خارج المستودع).
شرط الإغلاق (§6): «تم حسم SW-02 بدليل أو إبقاؤه صراحةً UNKNOWN مع مالك ومصدر مطلوب».

## Result
- **Stage 5:** `CLOSED_WITH_EXPLICIT_UNKNOWN — SOURCE REQUIRED` (تفاصيله في «### Stage 5 / SW-02» أعلى الملف).
- **حالة الخطة الكلية:** `COMPLETED_WITH_EXPLICIT_DEFERMENTS` (الجدول في «## حالة الخطة النهائية» أعلى الملف).
- **P0:** `BLOCKED / DEFERRED BY EXPLICIT PRODUCT DECISION` (بلا تغيير، غير منفَّذ).
- **SW-02:** غير منفَّذ/غير مُصلَح/غير مُجتاز — مُغلَق صراحةً كـ UNKNOWN؛ يحتاج مصدرًا موثوقًا.

## Files changed (documentation only)
- `.agent/PROGRESS.md` فقط (هذا القسم + قسم «حالة الخطة النهائية» + تفاصيل الإغلاق في قسم Stage 5).

## Verification
- SW-02: **0** إشارة في كود/اختبارات/docs (فقط في هذا الملف). مفيش ملف اختبار `test_sw02*`.
- ADR: مفيش قسم حالة خطة مناسب ⇒ **لم يُعدَّل** (مفيش تكرار/تضارب).
- مفيش ادّعاء تنفيذ لـ P0/SW-02. Stages 2/3/4 بلا تخفيض. مفيش تعديل كود/اختبارات/مخطط.

## Safety
مفيش commit/push/PR/merge/نشر/نداءات إنتاج/وصول أسرار. الشجرة محفوظة كما هي + تعديل توثيقي واحد.

---

# PROGRESS — OHB2-P0-ATTACHMENT-WORKFLOW-REOPEN-AND-SECURE-COMPLETION (2026-11-12)

## Goal
إعادة فتح P0 (سير عمل المرفقات) والتحقّق من إمكانية تنفيذه **بأمان** قبل أي كود. P0 هو النطاق
الوحيد المصرَّح به في هذه المهمة.

## Baseline (متحقَّق منه)
- الفرع `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`؛ HEAD `907b20de3fa6627795c14f29677e9f39c68e82f4`؛
  `origin/main` = `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- بوابة الأساس (قبل أي تعديل): pytest **2586 passed** (72 warnings)؛ pyflakes **exit 0**؛ bandit **High 0**.

## Feasibility gate — أعيد تشغيله مقابل الواجهة الحالية (مصادر عامة فقط، مفيش اعتماد/نداء إنتاج)
- **Cloud V1** (`app.all-hands.dev/openapi.json` **1.87.1**، 242 مسارًا): **مفيش رفع** (`upload`=0،
  `multipart`=0، `format:binary`=0)؛ مسارات الملفات **قراءة فقط**؛ `send-message` بيحمل
  `TextContent|ImageContent` بس (مفيش نوع ملف عام).
- **Agent Server** (`docs.openhands.dev/openapi/agent-sdk.json` **0.1.0**، 40 مسارًا): الرفع الوحيد
  `POST /api/file/upload/{path}` (multipart) — **مفتاح `X-Session-API-Key` واحد شامل** (نفس المفتاح
  يوصل `POST /api/bash/execute_bash_command`)، **مفيش عزل مسار** (بس `is_absolute()`)، **مفيش سقف حجم**،
  و**مفيش مصدر موثوق** لـ `conversation_url`.

## Verdict
**`BLOCKED — SECURE OPENHANDS UPLOAD CAPABILITY NOT ESTABLISHED`.** الحاجزان B1 (مفيش اعتماد محدود
الصلاحية) وB2 (مفيش أصل موثوق) **مُعاد التحقق منهما** ⇒ **مفيش تنفيذ**. الحالة `fail-closed` قائمة
(الرفض الآمن للمرفقات زي ما هو). P0 **مش DONE/PASS/IMPLEMENTED/CLOSED**.

## Files changed (documentation only — مفيش كود/اختبارات/مخطط)
- `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md`: تحديث رأس الحالة إلى r5 + قسم §27
  (إعادة التحقق + القرار + الأدلة المطلوبة لفتح الحاجز). §1–§26 محفوظة.
- `.agent/PROGRESS.md`: هذا القسم.

## Safety
مفيش commit/push/PR/merge/نشر/نداءات إنتاج/وصول أسرار/تغيير مخطط. الملفات الموجودة مسبقًا محفوظة.

---

# PROGRESS — OHB2-P0-OPENHANDS-SECURE-UPLOAD-CAPABILITY-INVESTIGATION-AND-UPSTREAM-SPEC (2026-11-12)

## Goal
تحقيق + مواصفة لقدرة OpenHands المطلوبة لفكّ حجب P0 (رفع ملف إلى شات موجود بأمان، بلا منح البوت
صلاحيات Agent Server غير المقيّدة). **تحقيق ومواصفة فقط — مفيش تنفيذ** (upstream أو OpenHandBot).

## Baseline (متحقَّق منه)
- الفرع `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`؛ HEAD `907b20de3fa6627795c14f29677e9f39c68e82f4`؛
  `origin/main` = `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.

## إعادة تحقق المصادر الحالية (public فقط، مفيش اعتماد/نداء إنتاج)
- **Cloud V1** `openapi.json` v**1.87.1** (242 مسارًا): مفيش رفع (`multipart`=0، `binary`=0)؛
  مسارات الملفات قراءة فقط؛ `send-message` = `anyOf[TextContent, ImageContent]`.
- **Agent Server** `agent-sdk.json` v**0.1.0** (40 مسارًا): الرفع الوحيد `POST /api/file/upload`
  (multipart `file`، query `path`) — مفتاح `X-Session-API-Key` **واحد على مستوى الخادم** (نفس المفتاح
  يوصل `POST /api/bash/execute_bash_command`)، **مفيش عزل مسار** (بس `is_absolute()`)، **مفيش سقف حجم**.
- **`conversation_url`**: مبني من `runtime['url']` عبر `exposed_urls` (path-mode/subdomain-mode) ⇒ أصل
  غير مستقر/غير موثّق ⇒ **مفيش allowlist موثوق**.
- **جديد (هذه المهمة):** واجهة OpenHands الرسمية (GUI) بتعمل رفع مرفقات فعلاً عبر **نفس** نقطة
  Agent Server و**نفس** `session_api_key` (وسم prompt بمسار النص + صور base64). يعني القدرة موجودة
  على مستوى المنتج لكن **الاعتماد غير مقيّد** ⇒ الفجوة upstream في التفويض/المعمارية مش في غياب endpoint.

## Verdict
**`PARTIALLY COMPLETE — UPSTREAM CAPABILITY OR MAINTAINER DECISION REQUIRED`.** صُمِّمت قدرة آمنة
(§5 في المستند) لكنها **غير موجودة اليوم** وتحتاج تغيير upstream + قرار maintainer. **P0 مش مكتمل.**

## Deliverable
- `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` (جديد): ملخص تنفيذي، تدقيق القدرة
  الحالية + المصادر، حدود الـ API، مقارنة 5 بدائل، عقد الـ API الموصى به (Cloud-hosted scoped upload op
  + status endpoint)، threat model، خطة upstream، عقد تكامل OpenHandBot، معايير القبول، أسئلة مفتوحة، مراجع.

## Files changed (documentation only — مفيش كود/اختبارات/مخطط/سلوك)
- `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` (جديد).
- `.agent/PROGRESS.md` (هذا القسم).

## Safety
مفيش commit/push/PR/merge/نشر/نداءات إنتاج/وصول أسرار/تغيير سلوك الرفض. الملفات الموجودة مسبقًا محفوظة.

---

# PROGRESS — OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW (2026-11-11)

## Goal
مراجعة عدائية مستقلة (read-only) للمقترح `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`:
هل تصميمه/أدلته/ادعاءاته الأمنية/صحة المواصفة upstream صحيحة؟

## Verdict
**PASS_WITH_MAJOR_FINDINGS — REVISION REQUIRED.** الإطار (المشكلة/الحاجة لتفويض مقيّد + حلّ وجهة على
الخادم + حدود حجم/نوع + مصالحة) **سليم**، لكن **تدقيق القدرة ناقص ماديًّا**.

## Findings (مختصر)
- **F1 (MAJOR):** المقترح بيقول «مفيش عزل مساحة عمل» — **غير صحيح**: عند SHA المثبَّت فيه مسار **مربوط
  بالشات ومحصورة في مساحة العمل**: `POST /api/conversations/{runtime_conversation_id}/file/upload`
  (من `runtime_router.py::create_runtime_router` + `bind_local_conversation_runtime`، بيتفرض
  `resolve().is_relative_to(workspace_root)` وإلا **422**). المسار القديم `/api/file/upload` فعلًا غير
  محصور. ⇒ §3 (B/C) مُبالغ فيهما و§7.1/§7.4 بيطلبوا بناء موجود أصلًا.
- **F2 (MAJOR):** مواصفة الـ docs export قديمة ومتناقضة: `agent-sdk.json` بيعرض
  `POST /api/file/upload/{path}` (path param) بينما المصدر عند الـ SHA المثبَّت `@file_router.post("/upload")`
  (query param) — وكمان عند الوسوم `v1.58.1`/`v1.62.0`. الشكل `/{path:path}` موجود عند `v1.10.0` فقط.
  الـ export كمان **ناقص** `capabilities` ومسارات runtime-scoped و`/api/auth/workspace-session` و`/hooks`.
- **F3 (MODERATE):** جدول الفجوات §3 بيبالغ: B/C = PARTIAL مش NO (الحصر موجود على المسار المقيّد).
- **F4 (MODERATE):** §2.2 «بس نداءي runtime» غلط — فيه كمان `GET …/file`, `/files`, `/download`.
- **F5/F6/F7 (LOW/INFO):** الـ SHAs المثبَّتة == main الحالي (متحقَّق)؛ ادعاءات securitySchemes صحيحة؛
  §6/§8 قويّان ويجب الحفاظ عليهما.

## Files changed (documentation only — مفيش كود/اختبارات/سلوك)
- `docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md` (جديد).
- `.agent/PROGRESS.md` (هذا القسم).

## Safety
مفيش commit/push/PR/merge/نشر/نداء إنتاج/وصول أسرار/تعديل على المقترح نفسه. كل الأدلة من مصادر عامة
وإعادة استنتاج مستقلة. الملفات الموجودة مسبقًا محفوظة.

---

# PROGRESS — OHB2-P0-SECURE-UPLOAD-PROPOSAL-EVIDENCE-CORRECTION-AND-REVISION (2026-11-11)

## Goal
تصحيح أدلّة المقترح `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` ومراجعته
(إصدار **r2**) اعتمادًا على نتائج المراجعة العدائية المستقلة (`PASS_WITH_MAJOR_FINDINGS — REVISION
REQUIRED`، findings **F1–F4**). التمييز الدقيق بين **ما هو موجود فعلًا** و**ما هو مقترح**.
**توثيق فقط — مفيش كود/اختبارات/مخطط/سلوك.**

## Baseline (متحقَّق منه)
- الفرع `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`؛ HEAD `907b20de3fa6627795c14f29677e9f39c68e82f4`؛
  `origin/main` = `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- الشجرة الأساسية (لازم تُحفظ): modified `.agent/PROGRESS.md`, `bot/handlers.py`,
  `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md`,
  `docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md`؛ untracked المقترح + المراجعة + ملفَّي اختبار.

## إعادة التحقق من الأدلة (public فقط، مفيش اعتماد/نداء إنتاج)
- الـ SHAs المثبَّتة **== main الحالي**: SDK `9f7d5cb1…`، sandbox-server `43e91604…`، OpenHands `a8aaf681…`.
- `runtime_router.py::create_runtime_router` ⇒ prefix `/conversations/{runtime_conversation_id}` +
  `Depends(bind_local_conversation_runtime)` (يفرض `resolve().is_relative_to(workspace_root)` وإلا **422**).
- `conversation_registry.py::add_execution_routes` ⇒ `include_router(create_runtime_router())`؛ `api.py`
  بيركّب `file_router` (قديم، host-level) + `add_execution_routes` (مقيّد) تحت **نفس** `check_session_api_key`.
- `file_router.py` ⇒ `@file_router.post("/upload")` بـ **query** `path`؛ `_upload_file` بيفرض `is_absolute()` بس.
- `tests/agent_server/test_runtime_router.py` ⇒ دليل تنفيذي (422/401/400 + `conversation_runtime_routes_v1`).
- Cloud live `openapi.json` **1.87.1** (242 مسارًا): `/file`, `/files`, `/download`, `/git/changes`,
  `/git/diff` **قراءة/تنزيل فقط** — مفيش رفع. `_get_agent_server_context` + `_proxy_git_runtime_call`
  = قفزة runtime من جهة الخادم (مفتاح الرمل مش بيتسرّب للمتصل).
- docs export `agent-sdk.json` **0.1.0** (40 مسارًا): شكل قديم `POST /api/file/upload/{path}` **يناقض**
  المصدر؛ **ناقص** مسارات runtime-scoped و`/api/auth/workspace-session` و`/hooks` و`capabilities`.

## ما اتصحّح في المقترح (r2) — خرائط F1–F4
- **F1:** التمييز بين **قديم غير محصور** `POST /api/file/upload` و**مربوط-بالشات ومحصور**
  `POST /api/conversations/{runtime_conversation_id}/file/upload`؛ الفجوة أعيدت صياغتها كـ
  *تفويض مقيّد + حلّ وجهة على الخادم + حدود + مصالحة*، مش «غياب حصر». (§1/§2.3/§3/§4/§5.1/§7/§7.7)
- **F2:** تنزيل docs export من «مرجع موثوق» لـ «لقطة محتملة القدوم»، والاعتماد على **المصدر** عند الـ SHA.
- **F3:** إعادة كتابة جدول فجوات §3 ليفصل **موجود** (حصر مساحة العمل/ربط الشات) عن **مفقود** (A/B/C/D/E).
- **F4:** تصحيح «بس نداءي runtime» ⇒ `/file`, `/files`, `/download`, `/git/changes`, `/git/diff`.
- **إضافات:** §7.0 (أدنى تغييرات upstream + خريطة إعادة استخدام، بإجابة 7 أسئلة إعادة التقييم)؛
  تعليم حدود §5.7 كـ **مبدئية + غير متّسقة داخليًا**؛ ملاحظة «لازم تفضل خضراء» في §10.1؛
  hashes + caveats في §11؛ قسم **§13 r2** في سجل المراجعات. **التصميم والمتطلبات الأمنية (§5/§6/§8/§9) محفوظة.**

## Files changed (documentation only)
- `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` (تحرير في المكان — r2؛ الملف لسه untracked).
- `.agent/PROGRESS.md` (هذا القسم).

## Verification
- المقترح: 872 سطرًا؛ 13 قسمًا سليمة؛ مفيش بقايا ادعاءات r1 («no confinement»، «only two runtime calls»).
- مقارنة مراجعة↔مقترح: كل بنود §5 «Required revisions» الخمسة مُعالَجة.
- البوابة **لم تُعَد** لأن التغيير **توثيقي فقط** (لا كود/اختبار) — البوابة الحالية **2586 passed**،
  pyflakes exit 0، bandit High 0 (كما في قسم F1-LOW-COVERAGE-CLOSURE أعلاه).

## Safety
مفيش commit/push/PR/merge/نشر/نداء إنتاج/وصول أسرار/تعديل كود/تغيير سلوك. الشجرة الأساسية محفوظة.


---

# PROGRESS — OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-ADVERSARIAL-REVIEW (2026-11-11)

## Goal
مراجعة عدائية مستقلة (**read-only**) لإصدار **r2** من المقترح
`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`: هل هو دقيق تقنيًّا، متّسق
داخليًّا، آمن، وجاهز لموافقة المالك النهائية؟ **مفيش تنفيذ، مفيش تعديل للمقترح، مفيش مراجعة r1 مُعدّلة.**

## Verdict
**`PASS_WITH_NOTES`** — r2 جاهز لموافقة المالك كطلب upstream. **PASS هنا = جاهزية للموافقة فقط،
مش** يعني إن P0 اتنفّذ (P0 لسه غير منفّذ).

## Baseline (متحقَّق منه)
- الفرع `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`؛ HEAD `907b20de3fa6627795c14f29677e9f39c68e82f4`؛
  `origin/main` = `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- الـ SHAs المثبَّتة **== main الحالي** (SDK `9f7d5cb1…`، sandbox-server `43e91604…`، OpenHands `a8aaf681…`).
- كل الـ hashes في §11 من المقترح أُعيد اشتقاقها و**طابقت** (agent-server، sandbox-server، GUI، SDK، TS، Cloud، docs export).

## F1–F4 (إعادة تحقق مستقلة)
- **F1 ✅ مُصحّح:** المسار المقيّد `POST /api/conversations/{runtime_conversation_id}/file/upload`
  مسجَّل عبر `create_runtime_router` + `bind_local_conversation_runtime` (422 لو خارج
  `workspace_root`). **دقّة مهمة:** الحصر يُطبَّق على **بارامتر الطلب** `path` بالحل (`resolve()`)،
  **مش** حارس بعد الحل على الكتابة — `_upload_file` بيعمل `open(...,"wb")` بلا `O_NOFOLLOW`/`O_EXCL`
  ⇒ symlink/TOCTOU قائم. المقترح **ما يساويش** الحصر بأمان كامل. الـ GUI بيستخدم المسار المقيّد فعلًا.
- **F2 ✅ مُصحّح:** docs export `agent-sdk.json` (0.1.0، 40 مسارًا) قديم: شكل `/{path}`، `securitySchemes=None`،
  ناقص `capabilities`/`workspace-session`/المسارات المقيّدة. المصدر عند الـ SHA يحكم. SHAs دقيقة.
- **F3 ✅ مُصحّح:** A=NO، B=PARTIAL، C=PARTIAL، D=NO، E=PARTIAL — أُعيد اشتقاقها من المصدر (مفيش
  middleware/سقف حجم؛ مفيش نوع/عدّ؛ مفيش op id/status).
- **F4 ✅ مُصحّح:** Cloud 1.87.1 = `GET …/file`, `/files`, `/download`, `/git/changes`, `/git/diff`
  (**قراءة فقط**)؛ `multipart`=0، `binary`=0؛ `form-urlencoded` = 5 مسارات `/oauth/*` بالظبط.

## تحقيق ImageContent (إضافي)
- `ImageContent = {type:"image", image_urls: list[str], cache_prompt}` (SDK `message.py`).
- **صور فقط** عبر **data URLs** (base64)، مفيش رفع ملف ثنائي عام؛ الملفات غير الصورية تُرفع للمساحة منفصلة.
- حدود **من جهة العميل** بس (3MB/ملف + 3MB إجمالي)؛ مفيش سقف عند الخادم. مربوط بنفس الشات (send-message).
- **مفيش** op id/reconciliation، ومش مؤكَّد إنه يترسّخ كمرفق. ⇒ **مش بديل لـ P0** (ملفات متعدّدة + دفعة 15 دقيقة).

## تحقيق عدم تطابق live Cloud مع المصدر (إضافي)
- **R2-1 (MEDIUM):** مسار `GET …/{id}/files` موجود في **`OpenHands/enterprise`**
  (`app_conversation_router.py`، `list_conversation_files`، sha256 `c43ed4f7…`) — superset من
  `sandbox-server` المثبَّت (`864bff55…`). يعني Cloud V1 بيتقدّم من **مستودع مختلف (أحدث)**، مش
  «build أحدث لنفس المستودع». **تأثيره: صفر** على الاستنتاج (enterprise مفيش فيه رفع؛ `/files` قراءة فقط).

## Design/security + P0 compatibility
- التصميم **سليم وقريب من الحدّ الأدنى**: بيستخدم الحصر/الربط الموجودين، وبيضيف 4 قطع ناقصة فقط.
- تحديات: confused-deputy/كشف اعتماد = محلول؛ TOCTOU/symlink = مطلوب `O_NOFOLLOW`+`O_EXCL`؛ cross-user/conv = مذكور؛ replay = `Idempotency-Key`.
- **R2-6 (MEDIUM):** انتقال «consumed» غير قابل للملاحظة كما هو موصوف (§5.9/§5.10) — لازم تعريف إشارة الاستهلاك.
- **R2-8/R2-9 (LOW):** `expires_at` ناقص من سكيما الحالة؛ `uploading` يمكن يكون غير قابل للوصول.
- **R2-4 (LOW):** واجهة `enterprise/frontend` القديمة لسه بترفع على `/api/file/upload?path=…` (سلوك قديم، يعزّز الحاجة للنطاق).
- **مصفوفة توافق P0:** كل المتطلبات مدعومة بالعقد المقترح؛ الفجوات تفاصيل مواصفة (مش عيوب تصميم).

## Deliverable
- `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-REVIEW.md` (جديد).

## Safety
مفيش commit/push/PR/merge/نشر/نداء إنتاج/وصول أسرار/تعديل كود/تعديل المقترح أو مراجعة r1. الشجرة محفوظة.

---

# PROGRESS — OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-FINDINGS-REMEDIATION (2026-11-11)

## Goal
ترقية المقترح `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` من **r2** إلى
**r3** بمعالجة نتائج المراجعة المستقلة r2 (R2-1…R2-9) + مراجعة ذاتية عدائية. **توثيق فقط — مفيش تنفيذ
P0، مفيش تغيير سلوك، مفيش كود/اختبارات/مخطط.**

## Baseline
- الفرع `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`؛ HEAD `907b20de3fa6627795c14f29677e9f39c68e82f4`؛
  `origin/main` `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`. المقترح r2 sha256 `f7aaefe8…9023b2`.
- أعيد التحقق من المصادر المثبَّتة: enterprise `3fac53df…` (router sha256 `c43ed4f7…`)،
  sandbox-server `43e91604…` (`864bff55…`)، SDK `9f7d5cb1…` (`file_router 13f0cae7…`)،
  Cloud 1.87.1 (`0086b0b0…`, multipart=0)، enterprise frontend `0a0b80c6…`.

## Remediation (Phase 2)
- **R2-1 (MEDIUM):** §2.1/§2.2/§11 — المصدر الحقيقي لـ Cloud V1 هو **`OpenHands/enterprise`** (superset
  من sandbox-server، **مستودع مختلف أحدث**، مش build أحدث لنفس المستودع)؛ الاستنتاج «مفيش رفع» سليم.
- **R2-6 (MEDIUM):** §5.9.1 جديد — تعريف **`consumed_at`** كـ marker دائم مملوك للـ Cloud attachment
  service، يُضبط لما مسار `send-message` عند Cloud **يقبل الرسالة بشكل دائم**؛ يوضّح المعنى (≠ نجاح
  الرفع ≠ التسليم)، الدوام، قاعدة الكراش (unconfirmed ⇒ not consumed ⇒ مفيش حذف مبكر)، والتفاعل مع
  المهلة/النص المتأخر/النتائج الغامضة/تليجرام.
- **R2-8 (LOW):** §5.9 — إضافة **`expires_at`** لسكيما الحالة (UTC ISO-8601، ثابت عند القبول، لا يُمَدّ،
  وقاعدة terminal بعد الانتهاء + derivation-on-read).
- **R2-9 (LOW):** **إزالة `uploading`** من نموذج الحالات (`accepted|stored|rejected|failed|expired`)؛
  التبرير + شرط إعادة الإدخال (Q13).
- **R2-4 (LOW):** §5.13 جديد — ملاحظة توافق الـ enterprise/frontend القديم (`/api/file/upload?path=…`):
  coexist، خارج النطاق، غير مكافئ للعملية الآمنة.
- **R2-2 (MEDIUM):** §2.2/§4 — `send-message` عند Cloud بيعمل الـ hop server-side فعلًا.
- **R2-7 (LOW):** §5.7 — ملاحظة رؤية الملفات المؤقتة.
- تحديثات متسقة: §5.5، §5.10، §7.5، §8.1 (I12/S7)، §9 (معيار 7b)، §10.1 (اختبارات الحالة/الاستهلاك)،
  §11، §12 (Q5/Q6 + Q12/Q13)، §13.

## Self-review (Phase 4)
`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md` — مراجعة ذاتية عدائية على 8 محاور
(فقد دفعة، consumed كاذب، سباق الانتهاء، إعادة محاولة مكررة، حالة غير قابلة للملاحظة، حذف مبكر،
متطلب أمني غير محدَّد، ادّعاء قدرة غير مدعوم). كل المحاور أُغلقت على مستوى العقد، والمخاطر المتبقية
(A–H) موثَّقة كقرارات مالك (Q3/Q5/Q7/Q10/Q11/Q12/Q13) — مفيش افتراض صامت.

## Deliverables
- `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` (r3، في المكان).
- `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md` (جديد).

## Verdict
**READY_WITH_EXPLICIT_OPEN_QUESTIONS** (المقترح جاهز لموافقة المالك مع قرارات مفتوحة موثَّقة).
**P0 غير منفّذ.**

## Safety
مفيش كود/اختبارات/مخطط/تغيير سلوك؛ مفيش نداء إنتاج/أسرار؛ مفيش commit/push/PR/merge/نشر؛ الشجرة محفوظة.

---

# PROGRESS — OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-CRITICAL-GAP-REMEDIATION

## Goal
مراجعة المقترح r3 → r4 ومعالجة **كل** نتائج المراجعة العدائية المستقلة
(`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW.md`، الحكم
`NEEDS_REVISION`). إنشاء وثيقة r4 جديدة (بدون مسّ هوية r3). **بدون تنفيذ P0.**

## Acceptance criteria
1. كل نتيجة (H-1، M-1…M-5، L-1…L-4، I-1) مُعالَجة وموثّقة في المقترح.
2. H-1: عقد كامل يوضّح كيف يصبح المحتوى **قابلًا للقراءة من الوكيل** (resolve → materialize → مسار
   مقروء → دليل قراءة/استيعاب).
3. لا يُضعَّف أي متطلّب أمني/صف في نموذج التهديد/أي ثابت P0 (I1–I13)؛ إضافة I14.
4. المقترح متّسق داخليًا (جداول/أسوار) و§13 يحمل صف r4.
5. مراجعة ذاتية عدائية لـ r4 (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-SELF-REVIEW.md`).
6. قراءة-فقط على مستوى الإنتاج: فقط المقترح (r3→r4) + وثيقة المراجعة الذاتية أُنشئت/عُدّلت.

## Done
- **H-1 (HIGH):** §5.14 جديد (فحص آليات موجودة = لا شيء يكفي؛ تصميم A = materialization داخل
  الـ workspace بمسار `delivered_path` مُولَّد من الخادم؛ مقارنة A/B/C/D؛ جدول إجابات H-1 الإلزامي).
  حالة terminal جديدة **`delivered`** (§5.9) بدليل قراءة/استيعاب من سجل أحداث agent-server.
  عقد التسليم = **قدرة upstream جديدة** (قرار مالك Q14).
- **M-1:** §8.3 جديد (ترتيب الدوام + 7 نوافذ كراش) + §8.1 I13 + §8.2 S3/S10.
- **M-2:** تصحيح §2.2/§5.9.1 — `send-message` = proxy رفيع بلا كتابة سحابية دائمة؛ §5.15 U-2.
- **M-3:** §5.10 حذف مبني على الدليل (`delivered`/`expires_at`) لا `consumed_at`؛ I12؛ T-19.
- **M-4:** §5.16 جديد (client_operation_id + صف عملية قبل staging)؛ §5.4/§5.5/§5.6/§5.8.
- **M-5:** §8.4 جديد (مهلة الدفعة client-side؛ لا مفهوم دفعة على الخادم)؛ §5.9؛ §5.15 U-5.
- **L-1…L-4، I-1:** §5.9/§5.9.1/§5.10/§5.13/§8.4/§5.15 U-6.
- نموذج التهديد: صفوف **T-16…T-20**. المعايير: **7b (مصحّح)/7c/11**. الأسئلة: **Q5 مُوسَّع، Q11/Q12/Q13
  محدَّثة، Q14–Q17 جديدة**. §11 (حالات/تحفظات d–g) + §13 (صف r4).

## Verification
- فحص البنية: `lines=1509 | fences even: True | tables=20 | inconsistent: 0` (المقترح)؛
  `lines=114 | fences even: True | tables=2 | inconsistent=0` (المراجعة الذاتية).
- إعادة تحقق الأدلة: `send-message` proxy رفيع؛ `Message.content: Sequence[TextContent|ImageContent]`؛
  `ImageContent.image_urls`؛ إلحاق الحدث في `event_service.send_message` (خطوة دائمة على agent-server).

## Not implemented / out of scope
- **P0 غير منفّذ.** لا كود/مخطط/سلوك. عقد التسليم (§5.14) **قدرة upstream جديدة مقترحة**، ليست موجودة.

## Assumptions / decisions
- عقد التسليم = تصميم A (materialization) **موصى به** لكنه **قرار مالك** (Q14).
- fallback آمن لو تعذّر دليل القراءة: الاستبقاء حتى `expires_at` (Q16).
- r4 = مراجعة على نفس ملف المقترح (r3→r4) كما يطلبه المهمة؛ هوية r3 محفوظة في §13 + إشعار r4.

## Verdict
**READY_WITH_EXPLICIT_OPEN_QUESTIONS** — كل نتائج r3 مُعالَجة كعقود موثّقة؛ مراجعة عدائية مستقلة
لـ r4 **مطلوبة** قبل الاعتماد. **P0 غير منفّذ.**

## Safety
لا commit/push/PR/merge/نشر؛ لا نداء إنتاج/أسرار؛ الشجرة غير المتعلقة محفوظة كما هي.

---

# PROGRESS — OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-REVIEW-FINDINGS-REMEDIATION

## Goal
ترقية المقترح r4 → r5 بتطبيق **كل** التصحيحات المطلوبة من المراجعة العدائية المستقلة لـ r4
(`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW.md`، الحكم
`NEEDS_REVISION`، §12). **توثيق فقط — بدون تنفيذ P0، بدون كود/مخطط/سلوك.**

## Acceptance criteria
1. كل التصحيحات الثمانية في §12 من مراجعة r4 مُطبَّقة على المقترح.
2. H-1a: دليل `delivered` = قراءة **ناجحة** (F6) وليس محاولة (F4).
3. H-1c: إعادة تأطير "قدرة جديدة" إلى "جزئيًا composable، جزئيًا جديدة" مع ذكر البدائل الدائمة الموجودة.
4. M-2-res: تعريف واحد متّسق لـ `consumed_at` (§5.9.1 = §7.5).
5. S-1: لا تناقض §5.5/§5.9 (`accepted` داخلي فقط، لا يُرجَع أبدًا).
6. M-3b: قاعدة استرجاع واحدة لكل أثر (§5.10 = §5.9).
7. M-4b: `client_operation_id` **إلزامي** + نطاق فرادة + سياسة تكرار الحمولة.
8. H-1b/S-2/S-3: ربط `delivered_path` بجذر الـ workspace المقيّد؛ حد التكامل (outbox نصّي فقط)؛
   ضمانات الملفات (نشر ذرّي، صلاحية قراءة، تنظيف الكتابة الجزئية).
9. لا يُضعَّف أي متطلّب أمني/صف تخفيف/أي ثابت P0؛ §13 يحمل صف r5؛ المقترح متّسق (جداول/أسوار).
10. قراءة-فقط إنتاجيًا: تعديل المقترح فقط + PROGRESS/الذاكرة.

## Done
- **H-1a (MEDIUM):** §5.14.0 جديد (سبع حقائق دورة حياة F1–F7، لا تُخلَط) + إعادة كتابة §5.14.2 خطوة 6
  (`delivered` ⇔ F2/F3 + **F6**: `ObservationEvent` مترابطة بـ `action_id`/`tool_call_id` مع
  `ActionEvent` يسمّي `delivered_path` ونتيجة **غير خطأ**؛ `AgentErrorEvent` ⇒ ليس delivered؛ F7 غير
  مُنمذَج). حُدِّثت §5.9/§7.5/§10.1/§10.2/§8.1 (I12/I14)/§9 (7c)/§6 (T-18/T-19).
- **H-1c (LOW):** §5.14/§5.14.1/§5.15/§11(e) أُعيد تأطيرها: المكوّنات الموجودة الدائمة
  (`pending-messages`، `events/search`، قفزة runtime، الكتابة المقيّدة) مقابل المكوّنات الجديدة
  (عملية المرفق، materialization، تفويض التسليم، قاعدة القراءة الناجحة). صف "Status" في §5.15 (U-1…U-9).
- **M-2-res (MEDIUM):** §5.9.1 أُعيد كتابته بتعريف **واحد** لـ `consumed_at` (علامة استلام رسالة،
  تُضبط فقط على استلام **دائم**؛ لا يضبطها `send-message` الرفيع)؛ أُزيل تناقض §7.5.
- **S-1 (MEDIUM):** §5.5/§5.9: staging متزامن داخل طلب الإنشاء؛ الإنشاء الناجح يُرجع **`stored`**؛
  `accepted` داخلي ولا يُرجَع.
- **M-3b (LOW):** §5.10 أُعيد كتابته كقاعدة لكل أثر (على `delivered` يُسترجع **staging** فقط؛ النسخة
  المُسلَّمة تبقى)؛ سُحِب نص r4.
- **M-4b (LOW):** `client_operation_id` **إلزامي** (UUID)، فرادة `(principal, conversation_id)`،
  نفس المفتاح+نفس الحمولة ⇒ نفس العملية، مختلف ⇒ **409 `client_operation_id_conflict`** (§5.4/§5.8/§5.16؛
  صف T-21 جديد).
- **H-1b/S-2/S-3 (LOW/INFO):** §5.14.2 خطوة 5 (مسار نسبي للجذر المقيّد)؛ §8.3 (حد التكامل: outbox نصّي
  فقط؛ U-9 جديد)؛ §7.4 (نشر ذرّي `os.replace`، صلاحية mode/owner، تنظيف جزئي، عزل عبر المحادثات).
- إضافي: §5.11 (`attachment.row_created` + `attachment.read_confirmed`)؛ §9 (7b/7c)؛ §10.1/§10.2؛ §11
  (مصادر r5 + تحفظات d/e/f/h)؛ §12 (Q5/5c/Q11–Q17)؛ §13 (صف r5).

## Verification
- بنية المقترح: `lines=1840 | fences=6 (متساوٍ) | tables=23 | inconsistent=0` (مع احتساب الأنابيب المُهرَّبة).
- `sha256` للمقترح r5: `6008c3ab44149b4a4cd9988fb9760752a92b9c38caf86672557f133341227085`.
- تغطية تصحيحات §12: 1→H-1a، 2→M-2-res، 3→S-1، 4→M-3b، 5→M-4b، 6→H-1b، 7→H-1c، 8→S-2/S-3. ✅
- إعادة تحقق الأدلة (r5، read-only في `/tmp/r4review`): `pending_message_router.py` +
  `pending_message_service.py` (StoredPendingMessage + `db_session.commit()`)؛ `event_router.py` +
  `event_service_base.py` + `filesystem_event_service.py` (`/conversation/{id}/events/search`).

## Not implemented / out of scope
- **P0 غير منفّذ.** لا كود/مخطط/اختبار/سلوك. لا test suite (مهمة توثيقية).
- بقايا المراجعة غير القابلة للحل: فرق r3→r4 بايتي غير قابل للتحقق؛ commit `enterprise` المنشور غير
  قابل للتحقق؛ صلاحية قراءة الملف المُسلَّم (mode/owner) غير مثبتة (موثّقة كـ UNVERIFIED).

## Assumptions / decisions
- تصميم التسليم A موصى به لكن قرار مالك (Q14). `delivered` يحتاج قراءة ناجحة؛ fallback الاستبقاء حتى
  `expires_at` لو تعذّر الدليل (Q16).
- `consumed_at` يُضبط عبر المسار الدائم `pending-messages` اليوم (composable) أو خطوة دائمة على
  `send-message` (عمل جديد) — قرار مالك (Q15).

## Verdict
**READY_WITH_EXPLICIT_OPEN_QUESTIONS** — كل تصحيحات §12 الثمانية مُطبَّقة كعقود متّسقة؛ مراجعة عدائية
مستقلة لـ r5 **مطلوبة** قبل الاعتماد. **P0 غير منفّذ.**

## Safety
لا commit/push/PR/merge/نشر؛ لا نداء إنتاج/أسرار؛ الشجرة غير المتعلقة (بما فيها `bot/handlers.py`
ووثائق أخرى) محفوظة كما هي؛ لم يُعدَّل سوى ملف المقترح + PROGRESS/الذاكرة.

---

# PROGRESS — OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW

## Goal
مراجعة عدائية مستقلة **بسياق جديد** للمقترح r5 (`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`، sha256
`6008c3ab44149b4a4cd9988fb9760752a92b9c38caf86672557f133341227085`) + إعادة جلب/إعادة تجزئة المصادر العامة
بشكل مستقل. **قراءة-فقط بالكامل** — بلا نداءات إنتاج/أسرار/اعتمادات، وبلا أي تعديل على المقترح أو المراجعات السابقة.

## Acceptance criteria
1. إعادة جلب المصادر المثبّتة (SDK SHA `9f7d5cb1…`, enterprise SHA `3fac53df…`) وإعادة تجزئتها.
2. التحقق من تصحيحات §12 الثمانية في مراجعة r4 مقابل نص r5.
3. تحديد أي مشكلات جديدة/متبقية مانعة (خصوصًا قاعدة دليل `delivered` F6).
4. إصدار حكم نهائي + كتابة ملف المراجعة + تحديث PROGRESS/الذاكرة.
5. حفظ كامل لحالة الشجرة (لا reset/clean/checkout/force/delete)؛ لا commit/push/PR/merge/نشر.

## Done
- قُرئ المقترح r5 كاملًا (1840 سطرًا) + مراجعة r4 المستقلة (§12) + مراجعتا r4/r5 الذاتيتان.
- أُعيد جلب وتجزئة كل ملفات المصدر الحاملة للحِمل (SDK + tools + enterprise + OpenAPI الحي 1.87.1).
- فُحصت التصحيحات الثمانية: **5 PASS كامل، 2 PARTIAL (#1→N-1، #3→N-2)، و#7 PASS مع تحفّظ (N-3)**.
- **N-1 (MEDIUM، جديد، مسنود بالمصدر):** قاعدة F6 «observation غير خطأ» **غير كافية** — أداة الطرفية
  تُرجع `TerminalObservation` **غير خطأ** لخروج غير صفري (`is_error` لا يُضبط إلا لحالات تفاعل/أوامر
  متعددة/طرفية مغلقة)، فالقراءة الفاشلة (`cat` لملف غير موجود) قد تُضبط `delivered` ⇒ استرجاع مبكر
  لنسخة staging (نفس صنف T-18/T-19). ملف المراجعة §N-1.
- **N-2 (LOW):** مثال §5.5 لا يزال يطبع `"state": "accepted"` رغم أن نصّ نفس القسم يقول إنه لا يُرجَع أبدًا.
- **N-3 (LOW):** مسار `pending-messages` يُفرَّغ **فقط عند بدء المحادثة** (`_process_pending_messages`
  في `live_status_app_conversation_service.py`، نداء وحيد بعد READY) — **ليس** بدائية استلام دائم لمحادثة
  جارية؛ المقترح يقدّمه كـ«التركيب الموصى به» دون ذكر هذا القيد.
- **N-4 (INFO):** §5.14.2 خطوة 5 تتيح `cat` كقارئ دون إشارة نجاح محددة (نفس جذر N-1).
- **N-5 (INFO):** ترويسة المقترح لا تزال تعرّف نفسها كـ r4 وتفتقد معرّف مهمة r5.
- أُنتج ملف المراجعة `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW.md`.

## Verification
- `sha256` (هذه الجلسة): المقترح r5 `6008c3ab…`؛ r5 self-review `67a7d1a5…`؛ r4 review `ce13bc94…`؛
  r4 self-review `0afa0a2c…`؛ r3 review `150ca104…`. كل تجزئات SDK/enterprise القابلة للتحقق تطابق §11.
- OpenAPI الحي: 242 مسارًا؛ `multipart`=0، `format binary`=0؛ `events/search` و`pending-messages` موجودان.
- `terminal_session.py`: `is_error=True` فقط عند 6 مواضع (تفاعل/فراغ/أوامر متعددة/مغلقة)؛ مسار
  `_handle_completed_command` يُرجع `exit_code` بلا `is_error`. `Observation.is_error` افتراضه `False`.

## Not implemented / out of scope
- **P0 غير منفّذ.** لا كود/مخطط/اختبار/سلوك. لم تُشغَّل اختبارات (مهمة توثيقية).
- غير قابل للتحقق: فرق r4→r5 بايتي (الملف غير متعقَّب، لا نسخة r4 على القرص/في Git) — استُبدل تحقّق دلالي.

## Assumptions / decisions
- اعتُمد تعريف «مانع» كما في المهام السابقة: أي شيء يمنع موافقة المالك أو يمنح `delivered` بلا دليل كافٍ.
- الحكم `NEEDS_REVISION` (لا `PASS_WITH_NOTES`): ملاحظة N-1 **مانعة** لأنها تمسّ قاعدة أمنية حاملة للحِمل.

## Verdict
**NEEDS_REVISION** — كل تصحيحات §12 الثمانية مُعالَجة، لكن قاعدة دليل `delivered` (F6) **غير كافية**
مسنودًا بالمصدر (N-1)، مع تبقيات N-2/N-3/N-4/N-5. **P0 غير منفّذ**، والملاحظات لا تخوّل تنفيذًا/نشرًا.

## Safety
قراءة-فقط: لم يُنشأ سوى ملف المراجعة؛ المقترح والمراجعات السابقة لم تُعدَّل (التجزئات ثابتة)؛ الشجرة
غير المتعلقة محفوظة؛ لا commit/push/PR/merge/نشر/تغيير فرع؛ لا نداءات إنتاج/أسرار/اعتمادات.

# PROGRESS — OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-READ-EVIDENCE-AND-PRIMITIVE-CORRECTIONS (2026-11-11)

## Goal
دفع مقترح رفع المرفقات الآمن (P0) من **r5 → r6** عبر معالجة **توثيقية فقط** لملاحظات المراجعة
المستقلة r5 (الحكم `NEEDS_REVISION`؛ الملاحظات **N-1** (MEDIUM، مانعة) + **N-2/N-3** + **N-4/N-5**).

## Acceptance criteria
1. تصحيح قاعدة دليل القراءة بحيث **لا** يكفي `ObservationEvent` غير خطأ لضبط `delivered` (N-1).
2. إصلاح مثال §5.5 إلى `"state": "stored"` (N-2).
3. تصحيح ادّعاء «`pending-messages` بدائية استلام دائم» إلى **start-only** (N-3).
4. تسمية القارئ وإشارة نجاحه ورفض `cat` الطرفي (N-4).
5. تحديث ترويسة المستند إلى r6 وإضافة معرّفات المهام (N-5).
6. **لا إضعاف** لأي متطلّب أمني أو صف في نموذج التهديد أو ثابت P0؛ توثيق فقط.

## Done
- **N-1:** سُحبت قاعدة r5 («مراقبة غير خطأ مترابطة ⇒ نجاح»)؛ أُضيف **§5.14.0** بنموذج **ثماني الحقائق**
  (F1–F5، **F6a** مراقبة غير خطأ، **F6b** قراءة محتوى ناجحة، F7)، ونُصّ على أن **لا بدائية حالية تُثبت F6b**،
  وطُلب **إشارة قراءة مُهيكلة جديدة (U-3)** مع **عقد حقول** في §5.15؛ `delivered` **غير قابل للوصول** بدون U-3،
  والبديل الآمن هو الاحتفاظ حتى `expires_at` (**بدون** استرداد مبكر). حُدّثت §5.9/§7.5/§6/§8.1/§9/§10.1/§10.2/§5.10/§5.11/§4/§5.14.2/§5.14.4.
- **N-2:** مثال §5.5 أصبح `"state": "stored"` + ملاحظة صريحة؛ فُحصت كل الأمثلة.
- **N-3:** §5.9.1/§5.14.1/§5.15 U-2/§8.2 S7/§8.3/§2.2/§11/§12 Q12/Q15 تُصرّح بأن الطابور **يُفرَّغ عند البدء فقط**،
  وأن الاستلام الدائم لمحادثة **جارية** عمل **جديد** (U-2).
- **N-4:** §5.14.2 خطوة 5 تسمّي القارئ المُهيكل وإشارة U-3، وترفض `cat` الطرفي (رمز خروج غير صفري = قراءة فاشلة
  حتى لو `is_error == false`)، وتذكر أن `read_file` المُهيكل **ليس** أداة افتراضية.
- **N-5:** الترويسة تعرّف نفسها **r6** وتُدرج معرّفات r5/r6 والمراجعتين.
- أُنتج **مراجعة ذاتية** جديدة: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-SELF-REVIEW.md`.

## Verification
- `sha256` (هذه الجلسة): المقترح **r5** `6008c3ab…` (مدخل) → **r6** `a02b9747…` (مخرج)؛ مراجعة r5 `4d5d7088…`.
- إعادة تحقق المصادر المثبّتة: `terminal_session.py` `72504a4d…` (`is_error=True` عند 6 مواضع فقط؛ مسار
  `_handle_completed_command` يُرجع `exit_code` بلا `is_error`)؛ `tool/schema.py` `76b4f42a…` (`is_error=False` افتراضًا)؛
  `file_editor/editor.py` `a1d735d4…` + `utils/constants.py` `a5b3f2bf…` (قصّ 16000)؛ `gemini/read_file/*` `893fd5d5…`/`2d5f81f2…`؛
  `sdk/tool/defaults.py` `357f005b…` (`("terminal","file_editor","task_tracker")`) + `tests/cross/test_default_tool_names.py` `3b406311…`؛
  `live_status_app_conversation_service.py` `9f4f1596…` (نداء وحيد لـ `_process_pending_messages`).
- لا اختبارات (مهمة توثيقية)؛ لا كود/مخطط/سلوك تغيّر.

## Not implemented / out of scope
- **P0 غير منفّذ** — لا كود/مخطط/اختبار/سلوك. U-3 وU-2 (الاستلام الدائم) متطلّبات **مقترحة** غير منفّذة upstream.
- غير قابل للتحقق: فرق r5→r6 بايتي (الملف غير متعقَّب، لا نسخة r5 محفوظة) — استُبدل تحقّق دلالي.
- بعض بارامترات النشر (صلاحية/ملكية الملف، توفّر `read_file` المُهيكل) تبقى **UNVERIFIED**.

## Assumptions / decisions
- عُرّف «مانع» كما في المهام السابقة: ما يمنح `delivered` بلا دليل كافٍ أو يمنع موافقة المالك.
- `delivered` **غير قابل للوصول** اليوم (لا U-3) — هذا **تقوية** لا إضعاف؛ البديل الآمن (احتفاظ حتى `expires_at`) لا يصرّح بأي قراءة ناجحة.

## Verdict
**DONE (توثيقيًا)** — كل ملاحظات r5 (N-1…N-5) مُعالَجة؛ قواعد دليل القراءة والاحتفاظ **أصبحت أشدّ**؛ **لا** إضعاف لأي متطلّب أمني/تهديد/ثابت P0. مراجعة مستقلة لـ r6 **مطلوبة** (ذاتية هنا).

## Safety
توثيق فقط: عُدّل المقترح + PROGRESS وأُضيف ملف مراجعة ذاتية؛ الشجرة غير المتعلقة محفوظة؛ لا commit/push/PR/merge/نشر/تغيير فرع؛
لا نداءات إنتاج/أسرار/اعتمادات.

---

# PROGRESS — OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-INDEPENDENT-ADVERSARIAL-REVIEW

## Goal
مراجعة **مستقلة عدائية** (مصدرية) لمقترح رفع المرفقات الآمن **r6** (`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`)،
وفق `AGENTS.md`، **قراءة فقط** (لا تنفيذ، لا نداءات إنتاج، لا أسرار، لا commit/push/PR/merge/نشر/تغيير فرع).

## Acceptance criteria
1. إعادة جلب/تجزئة كل مصدر مثبّت يعتمد عليه r6 بشكل مستقل (لا نقل من المقترح).
2. التحقق من ادّعاء r6 المركزي (N-1: مراقبة غير خطأ ≠ قراءة ناجحة؛ لا بدائية تُثبت F6b).
3. تقييم كل ملاحظات r5 (N-1…N-5) وحالة/احتفاظ/ثوابت r6.
4. إيجاد ملاحظات جديدة (إن وُجدت) مع دليل مصدري + حكم.
5. كتابة ملف المراجعة تحت `docs/reviews/` + تحديث PROGRESS/الذاكرة + تقرير عربي.

## Done
- قُرئ `AGENTS.md` (165 سطرًا) والمقترح كاملًا (2098 سطرًا) والمراجعة الذاتية r6 (121 سطرًا) ومراجعة r5 (440 سطرًا).
- أُعيد جلب/تجزئة المصادر المثبّتة (SDK `9f7d5cb1…`، sandbox-server `43e91604…`، enterprise `3fac53df…`، OpenHands `a8aaf681…`) في `/tmp/r6rev`.
- تحقّق مصدري كامل لادّعاء N-1: `terminal_session.py` (`72504a4d…`) يُرجع `TerminalObservation` بـ `exit_code` **بلا** `is_error`
  على مسار الأمر المكتمل (أسطر 282-287)؛ `is_error=True` فقط في 506/520/526/542/608/670؛ `Observation.is_error=False` افتراضًا
  (`schema.py` `76b4f42a…`, سطر 417). كذلك `file_editor` (`view` يتطلّب مسارًا **مطلقًا**، سطر 666؛ ملف مفقود ⇒ `ToolError`؛ قصّ 16000)
  و`read_file` المُهيكل (gemini preset، ليس افتراضيًا) — كلها **تطابق** نص r6.
- **R6-1 (MEDIUM، جديد، مصدري — مسبّب الحكم):** نسخة **الملف المُجسّد** (delivered copy) تُحذف عند `expires_at` حين لا تصل العملية إلى
  `delivered` (§5.10 سطر 948؛ §5.9 سطر 845). وبما أن r6 يجعل `delivered` **غير قابل للوصول** اليوم (لا U-3)، فكل ملف يُجسّد
  فعليًا **يُحذف ≤ 15 دقيقة** — وهو صنف الحذف المبكر T-18/T-19 الذي يقول المستند إنه أغلقه. يتناقض مع §5.14.2 خطوة 7 («يبقى ملف الوكيل
  لمدى المحادثة»).
- **R6-2 (MEDIUM، جديد):** نموذج ثقة U-3 غير محدَّد — يُسمح بأن يُصدِره «القارئ»؛ لم يُنصّ على أن المُصدِر **موثوق وغير تابع للوكيل**،
  ولا كيفية مصادقته ⇒ احتمال إعادة فتح ثغرة F6a بمستوى أعلى (تأكيد قراءة كاذب).
- **R6-3 (LOW، جديد، مصدري):** «سجل الأحداث القابل للوصول من السحابة» هو **نسخة مُستنسخة بالاستطلاع** (`remote_sandbox_service.py`
  `d239ec43…`: `poll_agent_servers`→`refresh_conversation`→`save_event`، أسطر 1256/1345/1438) وقراءتها **غير ذرّية** ⇒ قراءة ممزّقة محتملة؛
  شرط «لا حدث خطأ لاحق» يحتاج مصدرًا **هادئًا**/إعادة تحقّق من agent-server.
- **R6-4 (LOW، جديد):** القارئ المسمّى (`file_editor view`) يتطلّب مسارًا **مطلقًا**، لكن `delivered_path` **نسبي** ⇒ «مسار قابل للقراءة» غير مُثبت من طرف إلى طرف.
- **R6-5 (INFO، جديد):** نص «seven lifecycle facts» قديم باقٍ في §1 (سطر 106) وفي صف r5 بـ §13 ⇒ تناقض مع نموذج «ثماني الحقائق».
- **الحكم:** `NEEDS_REVISION` (لا `BLOCKED`). الملاحظات كلها **توثيقية/عقدية**؛ لا آلة upstream جديدة مطلوبة.

## Verification
- `sha256` (هذه الجلسة): المقترح r6 `a02b9747…` (2098 سطرًا)؛ المراجعة الذاتية r6 `908caa60…`؛ مراجعة r5 `4d5d7088…`.
- ملف المراجعة الجديد: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- لا اختبارات (مراجعة فقط)؛ لا كود/مخطط/سلوك تغيّر.

## Not implemented / out of scope
- **P0 غير منفّذ.** U-3/U-2 مقترحات غير منفّذة upstream. لم يُشغَّل أي اختبار للميزة (غير موجودة).
- **UNVERIFIED:** مواصفة Cloud V1 الحيّة لم تُعد جلبها (الاعتماد على 1.87.1 المنصوص + راوتر `enterprise` المثبّت)؛ قيمة `sleep_interval` لـ `poll_agent_servers` لم تُقرأ (وجود مسار الاستطلاع تحقّق مصدريًا، القيمة لا).

## Assumptions / decisions
- عُرّف «مانع» كالسابق: ما يمنح `delivered` بلا دليل كافٍ، أو يُهلك محتوى يحتاجه الوكيل، أو يمنع موافقة المالك.
- المراجعة مستقلة (سياق جديد، مؤلف مختلف عن المقترح/المراجعات الذاتية/مراجعات r2–r5).

## Verdict
**DONE (مراجعة مستقلة)** — الحكم `NEEDS_REVISION`؛ الادّعاء المركزي لـ r6 (N-1) **تحقّق صحيح**، وكل ملاحظات r5 مُعالَجة،
لكن ظهرت ملاحظتان مانعتان (R6-1/R6-2) + ثلاث ملاحظات أقل (R6-3/R6-4/R6-5).

## Safety
قراءة فقط: لم يُعدّل المقترح ولا أي ملف متعقّب آخر؛ أُضيف ملف مراجعة واحد + تحديث PROGRESS/الذاكرة؛ الشجرة غير المتعلقة محفوظة؛
لا commit/push/PR/merge/نشر/تغيير فرع؛ لا نداءات إنتاج/أسرار/اعتمادات.

---

# PROGRESS — OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-INDEPENDENT-ADVERSARIAL-REVIEW (2026-11-11)

## Goal
مراجعة عدائية **مستقلة** (سياق جديد) لمقترح r7 الحالي لميزة رفع/تسليم المرفقات الآمنة، مدعومة بالمصادر
المثبّتة. **قراءة فقط**: بلا نداءات إنتاج/أسرار/كتابة على المقترح، وبلا commit/push/PR/merge/نشر.

## Acceptance criteria
1. مراجعة r7 بمصادر مثبّتة (إعادة جلب/تجزئة مستقلة) — لا اعتماد على نسخ سابقة.
2. التحقق/الدحض لكل من R6-1…R6-5.
3. فحص الاتساق الداخلي (لا تعارض مع §5.10؛ لا نص «seven lifecycle facts» حيّ).
4. مراجعة عدائية فعّالة: محاولة إسقاط r7 وإيجاد ملاحظات جديدة (source-grounded).
5. ملف مراجعة واحد فقط هو الأثر المُنشأ.

## Done
- قُرئ المقترح r7 (2504 سطرًا، `d4e4fdc8…`) والمراجعة الذاتية r7 ومراجعة r6 كاملة.
- أُعيد جلب/تجزئة المصادر المثبّتة (SDK `9f7d5cb1…`، sandbox-server `43e91604…`، enterprise `3fac53df…`) في `/tmp/r7ir`.
- **تحقّق صحيح** لأربعة ادّعاءات مركزية في r7: (R6-1) نسخة C2 لا تُستردّ عند `expires_at`؛ (R6-2) U-3 يحتاج
  مُصدِرًا موثوقًا غير تابع للوكيل؛ (R6-3) مخزن أحداث Cloud نسخة مستطلعة (`poll_agent_servers` سطر 1256→
  `refresh_conversation` 1345→`save_event` 1438، `d239ec43…`)؛ (R6-4) قارئ file_editor يتطلّب مسارًا **مطلقًا**
  (`validate_path` سطر 666، `a1d735d4…`). لا إضعاف لأي صف تهديد/ثابت P0/معيار قبول (T-18/T-19/I10/I12/I13/I14/7b/7c مُقوّاة).
- **R7-1 (MEDIUM، جديد، مصدري):** مسار استرداد C2 الوحيد غير-F7 («إزالة مساحة العمل») **غير مُثبَت** بالكود المثبّت:
  حذف المحادثة في Cloud **يؤرشف** مساحة العمل (`_finalize_sandbox_delete` سطر 1050 → `archive_conversation_workspace`
  → `workspace_archive.archive_workspace` سطر 334) ثم يحذف **الـ sandbox فقط** إن لم يبقَ محادثة مرجعية (سطر ~1090)؛
  وagent-server يحذف دليل المحادثة **مع الإبقاء على مساحة العمل** (`conversation_service.py` سطر 1911، `9e9b3e63…`).
  وبالتجميع (`SandboxGroupingStrategy` غير `NO_GROUPING`، `settings_models.py` سطر 767) يُبقي شقيق المحادثة الـ sandbox
  حيًّا ⇒ لا تُزال مساحة العمل. المسار الحقيقي الوحيد = «idle reap» لـ sandbox (غير مُنمذَج في r7، وغير محدود زمنيًا).
  ⇒ ادّعاء «المحادثة المنتهية ⇒ C2 يزول» **غير صحيح**، وحدّ Q18 مُقلَّل.
- **R7-2 (MEDIUM، جديد، مصدري):** عقد المسار يحلّ جذر مساحة العمل من مصدر **لا يحمله**: `_get_agent_server_context`
  يعرض `sandbox_spec.working_dir` (القاعدة غير المُجمَّعة) فقط (`app_conversation_router.py` سطر 278)، بينما
  `bind_local_conversation_runtime` يأخذ الجذر من agent-server (`runtime_router.py` سطر 41) = المسار **المُجمَّع**
  `{base}/{conversation_id.hex}`. المسار المثبَّت موجود فقط في وسم `archiveworkspacepath` (سطر 65) الذي لا يقرأه الـ helper.
- **R7-3 (LOW، جديد):** وصف «poll loop» ليس شاملًا: الاستطلاع **مشروط** بعدم وجود URL عام (`remote_sandbox_service.py`
  سطر 1518-1526)؛ وإلا فالـ webhook هو المُغذّي. **R7-4 (INFO):** تصنيفان «ثمانيّان» متوازيان (L1–L8 وF1–F7/F6a/F6b) بلا خريطة تقاطع.
- **الحكم:** `NEEDS_REVISION` (لا `BLOCKED`).

## Verification
- `sha256` (هذه الجلسة): المقترح r7 `d4e4fdc8…` (2504 سطرًا)؛ المراجعة الذاتية r7 `a72f12a0…`؛ مراجعة r6 `e264ebdf…`.
- ملف المراجعة المُنشأ: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- `git status`: لم يُعدَّل أي ملف متعقّب بواسطتي؛ الشجرة غير المتعلقة محفوظة. لا اختبارات (مراجعة فقط).

## Not implemented / out of scope
- **P0 غير منفّذ.** U-3/U-10/U-11 مقترحات غير منفّذة upstream. لم يُشغَّل أي اختبار للميزة (غير موجودة).
- **UNVERIFIED:** مواصفة Cloud V1 الحيّة لم تُعد جلبها؛ قيمة `sleep_interval` ومسار الـ webhook لم تُقرأ؛ **توقيت**
  الـ idle reap خارج المستودعات الثلاثة المثبّتة.

## Assumptions / decisions
- «مانع» = ما يُدخل اعتمادًا غير مُثبَت في عقد الأمن، أو يمنع موافقة المالك. عُرّف R7-1/R7-2 كمانعين لأنهما يُبطلان
  ادّعاءات عقدية جديدة يعتمد عليها المقترح.
- المراجعة مستقلة: مؤلف مختلف عن المقترح/المراجعة الذاتية/مراجعات r2–r6.

## Verdict
**DONE (مراجعة مستقلة)** — `NEEDS_REVISION`؛ إصلاحات r6 الخمسة **مُتحقَّقة**، لكن ظهرت ملاحظتان مانعتان جديدتان
(R7-1/R7-2) + ملاحظتان أقل (R7-3/R7-4).

## Safety
قراءة فقط: لم يُعدَّل المقترح ولا أي ملف متعقّب آخر؛ أُضيف ملف مراجعة واحد + تحديث PROGRESS/الذاكرة؛
لا commit/push/PR/merge/نشر/تغيير فرع؛ لا نداءات إنتاج/أسرار/اعتمادات.

---

# PROGRESS — OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-R7-INDEPENDENT-FINDINGS-REMEDIATION (2026-11-11)

## Goal
معالجة ملاحظات المراجعة العدائية **المستقلة** لـ r7 وإنتاج **المقترح r8**. توثيق فقط.

## Acceptance criteria
1. معالجة R7-1…R7-4 داخل المقترح r8، دون إضعاف أي متطلّب أمني/صف تهديد/ثابت P0.
2. إسناد كل ادّعاء جديد إلى المصادر المثبّتة (إعادة جلب/تجزئة هذه الجلسة).
3. اتساق داخلي كامل (لا بقايا لنصّ «إزالة مساحة العمل» أو لادّعاء جذر مساحة العمل من الـ helper).
4. أثر واحد جديد: مراجعة ذاتية r8. لا commit/push/PR/merge/نشر.

## Done
- قُرئت مراجعة r7 المستقلة (423 سطرًا، `1b276ac6…`) كاملة، وأقسام r7 المستهدفة (§5.9، §5.10.0–§5.10.5، §5.14.0/§5.14.2/§5.14.4، §5.15.4/§5.15.5، §6، §8.1، §9، §10.1، §11، §12، §13).
- أُعيد جلب/تجزئة المصادر المثبّتة في `/tmp/r8ir` وتطابقت البصمات مع مراجعة r7.
- **R7-1:** أُلغي افتراض «حذف المحادثة يزيل مساحة العمل»؛ صار r8 يصرّح أن حذف/أرشفة المحادثة **يؤرشف ويُبقي** مساحة العمل
  (`_finalize_sandbox_delete` 1050 → `archive_conversation_workspace` 1071 → `archive_workspace` 334)، وأن الـ sandbox
  يُهدم فقط عند عدم وجود محادثة شقيقة (1083-1091)، وأن حذف agent-server **يُبقي** مساحة العمل (`conversation_service.py` 1911).
  المسار الوحيد المرئي للإزالة الفيزيائية = «runtime-api idle reap» (غير مُنمذَج، مؤجّل بلا حدّ عند التجميع). **اليوم لا يوجد
  حدث محادثة واحد يستردّ C2.** قُوّي حدّ Q18 ولم يُخترع أي بدائي تنظيف. (§5.10.1، §5.10.3، §5.10.4، §5.9، §5.14.2 step 7،
  §5.14.4، T-19/T-24، I12، §9 7b، §10.1، Q18، §11، §13.)
- **R7-2:** ثُبِّت المصدر المرجعي لجذر مساحة العمل (وسم `archiveworkspacepath` أو استعلام agent-server لـ `workspace.working_dir`)،
  وبيّن r8 أن `_get_agent_server_context` يحمل القاعدة غير المُجمَّعة فقط، وأُضيف عقد **provenance/binding** (ربط بـ
  `(principal, conversation_id, operation_id)`)، وصُنِّف **U-12 جديد + UNVERIFIED** مع **fail-closed**.
  (new §5.15.6، §5.14.2 step 3، §5.15.5، §5.15 U-12، §7.0، §7.1، §7.4، T-25، I15، Q22.)
- **R7-3:** فُصلت الحالة **المرجعية** (سجل agent-server) عن **النسخة** (مخزن Cloud)، وذُكر المسارَان (استطلاع **فقط** عند غياب URL عام، وإلا webhook)، وبقي شرط quiescence على المسارَين. (§5.15.4، U-10، §11، Q20، §10.1.)
- **R7-4:** أُضيفت خريطة تقاطع كاملة **L1–L8 ↔ F1–F7/F6a/F6b** (new §5.10.0.1) + إحالة من §5.14.0.
- كُتبت المراجعة الذاتية: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-SELF-REVIEW.md`.

## Verification
- `sha256` r8 (هذه الجلسة): `229b5ae18e0222454f10bef4b94562736b983f711c07a452a35b5226fb240645` (2770 سطرًا، من 2504 في r7).
- `sha256` مدخلات: المقترح r7 `d4e4fdc8…`، مراجعة r7 المستقلة `1b276ac6…` (423 سطرًا).
- `grep`: لا بقايا لـ «workspace is removed/removal» كمسار استرداد C2؛ ولا ادّعاء أن الـ helper يحلّ الجذر لكل محادثة.
- `git status`: لم يُعدَّل أي ملف متعقّد بواسطتي؛ الشجرة غير المتعلقة محفوظة. لا اختبارات (توثيق فقط).

## Not implemented / out of scope
- **P0 غير منفّذ.** U-3/U-10/U-11/U-12 مقترحات غير منفّذة upstream. لا اختبار للميزة (غير موجودة).
- **UNVERIFIED:** التوقيت/التأخير الدقيق لـ idle reap (خارج المستودعات المثبّتة)؛ قيمة `sleep_interval`؛ تأخّر مسار webhook؛ مواصفة Cloud V1 الحيّة.

## Assumptions / decisions
- «مانع» = ادّعاء عقدي جديد غير مُسند بالمصدر. عُولج R7-1/R7-2 كمانعَين. لم يُخفَّف أي متطلّب أمني.
- لم يُخترع أي بدائي تنظيف لـ C2؛ بقي الحدّ غير المحدود مُعلَنًا ومُقوّى.

## Verdict
**DONE (توثيق)** — r8 يعالج R7-1…R7-4، والمراجعة الذاتية r8 مكتوبة. مطلوب مراجعة عدائية **مستقلة** لـ r8 قبل الاعتماد.

## Safety
توثيق فقط: عُدّل المقترح (ملف غير متعقّب) وأُضيف ملف مراجعة ذاتية + تحديث PROGRESS/الذاكرة؛ لا commit/push/PR/merge/نشر؛
لا نداءات إنتاج/أسرار/اعتمادات.

---

# OHB2-P0-A2 — دورة حياة دفعة المرفقات المحلية + التفويض

## الهدف
تنفيذ **P0 Stage A2 فقط** حسب `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` (R4)
و`docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md`: ربط كل ملف مدعوم بـ (مستخدم + محادثة + دفعة)،
تثبيت `T0` عند أول ملف، مهلة 15 دقيقة **بلا تمديد**، ورفض المحادثة المشاهدة (tombstone) — كل ذلك **محليًا**
بلا أي إرسال بعيد. خارج النطاق: A3 (نص مصاحب/نية إرسال)، A4 (تنظيف/كنس)، B (تسليم بعيد).

## معايير القبول
1. مرفق مدعوم (`Document`) ⇒ قبول آمن + صف عنصر `pending` **قبل** أي بايت (row-first) ⇒ `stored` بعد تحقّق.
2. `T0` يُثبَّت مرة واحدة عند أول ملف ولا يُمدَّد أبدًا (لا UPDATE يلمس `t0`).
3. دفعة `pending` منتهية (T0+15د) ⇒ **ترفض** الملف الجديد و**تبدأ دفعة جديدة** (R4-literal).
4. محادثة مشهدة (deleted) ⇒ رفض (fail closed) **بلا** أي نداء `get_conversations` بعيد.
5. عزل بين المستخدمين: معرّف الدفعة وحده ليس تفويضًا.
6. `Document` ⇒ `handle_attachment`، باقي الوسائط ⇒ مسار الرفض القديم، والفلتران **متمايزان تمامًا**.
7. مفيش A2 scope creep: لا outbox/إنشاء شات/تسليم بعيد/كنس.

## الملفات
- `bot/attachments.py` (جديد/موسّع): قسم A2 — `classify_incoming_file`، `BatchDecision`، `BatchAcceptance`،
  `batch_deadline`/`batch_is_expired`، `normalize_declared_size`، `precheck_rejection`، `AcceptOutcome`،
  `AttachmentService.accept`. أُعيد استخدام `StagingStore` (A1) و`bot.files` (`authorize_conversation_detailed`).
- `bot/db.py`: دورة حياة الدفعة — `latest_pending_attachment_batch`، `mark_attachment_batch_status`،
  `accept_attachment_item[_into_new_batch]` (كتابة ذرّية للصف + نتيجة التحديث)، وتوسيع `set_attachment_item_status`
  بحقل `staging_token` (استعلامات ثابتة).
- `bot/handlers.py`: `handle_attachment` + نصوص الرسائل.
- `bot/app.py`: فصل فلتر المرفقات (`SUPPORTED_ATTACHMENT_FILTER` = Document؛ `UNSUPPORTED_ATTACHMENT_FILTER` = الباقي `& ~Document`).
- `tests/test_attachment_batch_lifecycle_a2.py` (جديد)، `tests/test_unsupported_attachment_rejection.py` (تحديث).

## Done
- المرحلة A2 كاملة + تصحيح عيبين متوسطين من المراجعة المستقلة:
  - **F-1:** الصف الدائم **ما كانش** بيسجّل `staging_token` ⇒ الملف المؤقّت ما ينفعش يتكنس في A4. أُصلح: التوكن
    يُولَّد قبل الصف الدائم ويُخزَّن في الصف (المسارَين + `set_attachment_item_status`)، و`store(staging_token=...)` يعيد استخدامه.
  - **F-2:** `display_name` كان بيتخزّن **خامًا**. أُصلح: يُخزَّن `sanitize_display_name(display_name)` (بيانات وصفية فقط).
  - **F-8:** الفلتران كانا **متداخلين** لرسالة تحمل مستندًا + أنيميشن/فيديو/صوت/صورة. أُصلح بجعل غير المدعوم `& ~Document`
    (كان السلوك صحيحًا فعليًا بسبب تفرد PTB لكل مجموعة، لكن الادّعاء/الاختبار كانا غير دقيقين).
- المراجعة العدائية المستقلة (جلسة Cloud منفصلة): **PASS_WITH_NOTES**؛ كل ضمانات A2 صمدت و5/5 طفرات مرصودة.
  الأثر: `docs/reviews/OHB2-P0-A2-INDEPENDENT-ADVERSARIAL-REVIEW.md`.

## Verification
- `pytest -q` (كامل): كل الاختبارات تمرّ، `EXIT=0` (لا فشل).
- `node --test tests/frontend/*.test.js`: 219 pass / 0 fail.
- `pyflakes bot/ automation/ tools/ main.py tests/`: نظيف.
- `bandit -lll -s B613` على الملفات المتغيرة: High=0، Medium عاد إلى الأساس (14) بعد إعادة صياغة الاستعلام.
- اختبارات الطفرات: تعطيل حفظ التوكن ⇒ فشل اختبارَي F-1؛ عدم تعقيم الاسم ⇒ فشل اختبار F-2.
- بصمات الملفات المحمية لم تتغيّر: REGISTER `846a9b23…`، PLAN `06be7ea8…` (والـ PROPOSAL/SECURE-API كذلك).

## Not implemented / out of scope
- A4 (كنس العناصر المعلّقة/المنتهية) — لاحقًا. C1/C2/C3 — مسجّلة في الـ register.
- F-3/F-4/F-5/F-6/F-7 (LOW/INFO من المراجعة): مقبولة/مؤجّلة (موثّقة في أثر المراجعة).

## Assumptions / decisions
- **R4-literal:** الدفعة المنتهية ترفض الملف **وتبدأ دفعة جديدة** (القديمة تُوسَم `expired`، `t0` بلا لمس).
- التفويض عبر `authorize_conversation_detailed` وحده (fail closed)، والتفويض **قبل** أي كتابة دائمة/تنزيل.
- لا commit/push/PR/merge/نشر (بانتظار إذن المالك).

## Branch / commits
- الفرع الحالي (workspace) — لا commit ولا push حتى الآن.

## Suggested next step
اعتماد A2 (أو طلب تعديلات)، ثم بدء A3 (النص المصاحب/نية الإرسال) في خطوة منفصلة.

---

## OHB2-P0-A2-F4-DUPLICATE-RESULT-REMEDIATION-AND-F5-OWNER-DECISION-BRIEF (2026-11-11)

### Goal / acceptance criteria
- **Task A (F-4):** مسار التكرار **ما يرجّعش** معرّف عنصر مُفبرَك؛ تمييز دقيق بين (جديد حقيقي/تكرار
  بمعرّف حقيقي/تكرار بلا معرّف/مرفوض/فاشل). حفظ دلالات الديدَب/الإقرار، بلا نظام ديدَب ثانٍ.
- **Task B (F-5/F-6):** تحليل الفرق 10/15 دقيقة + موجز قرار مالك. **بلا تغيير سلوك** إلا لو قرار مالك
  صريح + متطلّب R4 يُصرّحان بذلك (لا يوجد ⇒ لا تغيير).
- **خارج النطاق:** A3/A4/Group B/Group C/إصدار/قبول/نشر.

### Done
- **F-4 (DONE):** `accept_attachment_item` + `accept_attachment_item_into_new_batch` ترجّع `None` عند
  التكرار (مع تسجيل `duplicate_completed` ذرّيًّا)؛ `AcceptOutcome.DUPLICATE` جديد؛ `accept()` ترجّعه
  **قبل** أي تنزيل/تخزين؛ الـ handler يردّ نص القبول نفسه بلا لمس النتيجة الدائمة.
- **Task B (DONE):** موجز قرار: `docs/decisions/OHB2-P0-F5-F6-ROUTE-ATTACHMENT-WINDOW-OWNER-DECISION-BRIEF.md`
  (موصى به: حسم F-5/F-6 في A3؛ بلا تغيير الآن).

### Verification
- `pytest -q tests/test_attachment_batch_lifecycle_a2.py`: **48 passed** (كان 44).
- الحزم المتعلّقة (A2+A1+schema+rejection): **116 passed**.
- `pytest -q` (كامل): **2692 passed** (كان 2688)، `EXIT=0`.
- `node --test tests/frontend/*.test.js`: 219 pass / 0 fail.
- `pyflakes bot/ automation/ tools/ main.py tests/`: نظيف (exit 0).
- `bandit -r bot/ automation/ main.py -lll -s B613`: **High=0**.
- طفرات F-4 (نسخة معزولة): إرجاع `batch_id` (APPEND) / `batch_id` (NEW) / إزالة حارس الخدمة /
  إزالة فرع الـ handler ⇒ **كلها مرصودة**.
- بصمات الملفات المحمية لم تتغيّر: REGISTER `846a9b23…`، PLAN `06be7ea8…`، PROPOSAL `6ea52deb…`.

### Assumptions / decisions
- `DUPLICATE` **ليس** في مجموعة `mark_explicitly_ignored` ⇒ لا يُكتب فوق `duplicate_completed`.
- ردّ التكرار = نص القبول (idempotent، صادق) — مفيش ادّعاء عنصر جديد.
- **لا** تغيير لنافذة route (F-5) ولا للنافذتين (F-6) — بانتظار قرار المالك.

### Not implemented / out of scope
- F-5/F-6 سلوكيًّا (قرار مالك مطلوب). A3/A4/B/C. لا commit/push/PR/merge/نشر.

### Branch / commits
- الفرع الحالي (workspace) — لا commit ولا push.

### Suggested next step
قرار المالك على سؤال F-5/F-6 (§8 في الموجز)، ثم بدء A3.

---

## OHB2-P0-A2-FAIL-CLOSED-WRITER-REGRESSION-TESTS (2026-11-11)

### Goal / acceptance criteria
- إغلاق فائدتَي التغطية LOW-1/LOW-2 من مراجعة F-4: طفرة M6 (ابتلاع استثناء الكاتب ⇒ None)
  وطفرة M9 (إزالة rollback) لازم يكشفهما اختبار انحدار.
- **اختبارات فقط**؛ صفر تغيير في سلوك الإنتاج. بلا commit/push/PR/merge/نشر. A3/A4 غير مُصرَّح بهما.

### Done
- اختباران جديدان في `tests/test_attachment_batch_lifecycle_a2.py`:
  - `test_writer_exception_inside_transaction_is_not_a_duplicate` (M6).
  - `test_writer_rollback_leaves_no_partial_state_on_append` (M9).
- الحقن **داخل معاملة الكاتب الحقيقية** عبر `_mark_processed_nocommit` (يُنادى بعد إدراج صف
  العنصر وقبل `commit`) ⇒ مسار حقيقي، مش غلاف مزيّف. يغطّي: انتشار الاستثناء الأصلي، لا تحويل
  إلى None/DUPLICATE/ACCEPTED، لا علامة `duplicate_completed`، لا صفوف جزئية، وإعادة محاولة صحيحة.

### Verification
- اختبارا الانحدار: **2 passed** على الشجرة السليمة.
- A2 كامل: **50 passed** (كان 48). A2+A1+schema+rejection: **118 passed**.
- الكامل: **2694 passed** (كان 2692)، `EXIT=0`.
- `pyflakes`: نظيف. `bandit -lll`: High=0. `node --test`: 219 pass.
- الطفرات (نسخة معزولة `/tmp/rev5`، الشجرة الحقيقية لم تُمَس):
  - **M6** (ابتلاع ⇒ None، في الكاتبَين): الاختباران **فشلا** (DID NOT RAISE).
  - **M9** (إزالة rollback، في كاتبي A2 فقط): الاختباران **فشلا** (صفوف جزئية + DID NOT RAISE).
- الملف الوحيد المتغيّر: `tests/test_attachment_batch_lifecycle_a2.py`. مجموعة ملفات
  `git status` مطابقة تمامًا لخط الأساس (`0b31e66f…`)؛ diffstat الإنتاجي مطابق (app 29/db 418/handlers 256).
- بصمات الملفات المحمية لم تتغيّر: REGISTER `846a9b23…`، R4 `06be7ea8…`، P0 `6ea52deb…`.

### Assumptions / decisions
- اختيار `_mark_processed_nocommit` كنقطة حقن لأنها **آخر خطوة قبل `commit`** بعد إدراج العنصر ⇒
  تحدث بعد تعديل دلالي حقيقي (يفيد M9) وفي نفس المعاملة (يفيد M6).
- بلا تعديل سلوك/`db.py`/`handlers.py`/`attachments.py`.

### Not implemented / out of scope
- A3/A4/B/C. لا commit/push/PR/merge/نشر.

### Suggested next step
قرار المالك على F-5/F-6، ثم A3.

---

## OHB2-P0-A3-LOCAL-ACCOMPANYING-TEXT-INTENT (2026-11-13)

### Goal / acceptance criteria (من رسالة المهمة)
- تنفيذ A3: ربط نصّ مصاحب مؤهّل بدفعة واحدة بالضبط + نيّة محلية متينة (لا إرسال بعيد).
- AC: (1) مخطّط/حالة معتمدة؛ (2) ذرّية النيّة+النتيجة؛ (3) دفعة واحدة فريدة؛ (4) فشل مغلق عند
  الغموض عبر المحادثات/الدفعات؛ (5) الدفعة المنتهية لا تُحيا/لا تتحوّل لبرومت؛ (6) فصل 10/15؛
  (7) D-28 حرفيًّا؛ (8) `rejected_ineligible` مع حدّ الإقرار؛ (9) الفشل التقني fail-closed؛
  (10) ردّ الرفض أفضل-جهد بلا exactly-once؛ (11) لا outbox/إرسال بعيد؛ (12) لا دعم captions/مجموعات؛
  (13) A0/A1/A2 سليمة؛ (14) نتائج فعلية للاختبارات/الفحوص؛ (15) لا تغييرات غير مصرّح بها.

### Implementation map (Phase 1)
- ملفات: `bot/db.py` (عمود/حالة/طرق ذرّية)، `bot/attachment_text.py` (D-28، وحدة نقيّة جديدة)،
  `bot/handlers.py` (فرع A3 قبل البرومت العادي)، `bot/update_outcomes.py` (`rejected_ineligible`)،
  اختبارات جديدة + تحديث تعدادات الحالة.
- التصميم الذرّي: `BEGIN IMMEDIATE` + `UPDATE ... WHERE batch_id=? AND status='pending'` (CAS) +
  `_mark_processed_nocommit(...)` في نفس المعاملة ⇒ نصّ+حالة+نتيجة إما معًا أو لا.
- أسبقية المعالج: فرع A3 **قبل** فحص انتهاء route وقبل أي `_send_prompt`.
- استعلام عبر المحادثات: `list_live_pending_attachment_batches(telegram_id)`.
- تكامل الإقرار: `rejected_ineligible` مضاف إلى `_ACK_ELIGIBLE` (مصدر واحد).
- ملاحظة نطاق: A3 **محلي فقط** — تحقّق محلي (route/ملكية تيليجرام/ربط المحادثة/الحالة/المهلة/شاهد
  الحذف). **بلا** نداء بعيد (D-26 يعرّف الملكية كملكية مستخدم تيليجرام محليًّا).
- اختبارات: `tests/test_attachment_text_a3.py` (تحقّق D-28)، `tests/test_attachment_intent_a3.py`
  (ذرّية/توجيه/إقرار)، وتحديث `tests/test_attachment_batch_schema.py`.

### Done (A3 — محلي فقط)
- `bot/update_outcomes.py`: نتيجة جديدة `REJECTED_INELIGIBLE` + إضافتها لـ `_ACK_ELIGIBLE` (مصدر
  الإقرار الواحد) ⇒ مؤهّلة للإقرار؛ `failed_*`/`partial_or_unknown` تبقى غير مؤهّلة.
- `bot/db.py`:
  - حالة دفعة جديدة `intent_recorded` (بين `pending` و`dispatching`) + تحديث التعداد/التعليق.
  - عمود `intent_text` في `attachment_batches` (مخطّط جديد + ترحيل إضافي غير مدمّر لقواعد ما قبل A3).
  - `AttachmentBatch.intent_text` + تحديث `_row_to_attachment_batch`.
  - `list_live_pending_attachment_batches(telegram_id, now_iso)` (عبر المحادثات، حيّة فقط).
  - `has_expired_pending_attachment_batch(telegram_id, now_iso)`.
  - `record_attachment_intent(...)`: `BEGIN IMMEDIATE` + CAS (`status=pending`) + إعادة تحقّق
    ملكية/محادثة/مهلة **داخل المعاملة** + كتابة النتيجة ذرّيًّا (`durable_intent_recorded`؛
    `duplicate_completed` للتحديث المكرّر).
  - `record_rejected_ineligible(...)`: نتيجة نهائية متينة في معاملة واحدة (بلا `update_id` ⇒ False).
  - `_attachment_batch_deadline` مساعد محلي (تفادي دورية الاستيراد مع `attachments`).
- `bot/attachment_text.py` (جديد، نقيّ): تنفيذ **D-28** حرفيًّا (توحيد CRLF/CR⇒LF، رفض NUL/C0/C1
  عدا TAB/LF، ≥1 غير مسافة، حدّ 4096 code point بعد التوحيد، بلا قصّ/بلا NFC/بلا حذف صامت).
- `bot/handlers.py`: فرع A3 `_handle_accompanying_text` في `handle_text` **قبل** أي مسار برومت
  (وقبل فحص انتهاء route)؛ `_reject_accompanying_text` (نتيجة نهائية commit ثم ردّ أفضل-جهد).
  أسبقية fail-closed: multi-batch / route mismatch / no route / deleted / expired ⇒ رفض نهائي.
  لا `outbox` ولا نداء بعيد في مسار A3.

### Verification (A3)
- `tests/test_attachment_text_a3.py` (18) + `tests/test_attachment_intent_a3.py` (26) + تحديث
  `tests/test_attachment_batch_schema.py` (17، منها ترحيل ما قبل A3).
- الكامل: **2739 passed** (خط الأساس 2694)، `EXIT=0`.
- `pyflakes` نظيف؛ `bandit -lll` High=0؛ `node --test` 219 pass / 0 fail.
- طفرات في نسخة معزولة (الشجرة الحقيقية لم تُمَس، وتمّت الاستعادة والتحقّق):
  - M1 حاجز الغموض (`len(live)>1`) ⇒ فشل اختبا الغموض. M2 مهلة `record_attachment_intent` ⇒
    فشل اختبار الانتهاء. M3 حذف كتابة النتيجة الذرّية ⇒ فشل اختبار الذرّية.
  - M4 إزالة `rejected_ineligible` من `_ACK_ELIGIBLE` ⇒ 5 إخفاقات. M5 إبطال فحص محارف التحكّم ⇒
    5 إخفاقات. M6 ربط route ⇒ فشل اختبارَي «محادثة أخرى/بلا route».

### Assumptions / decisions
- **A3 محلي فقط** (D-09-R2): التحقّق محلي (ملكية تيليجرام = المالك نفسه + route + ربط + مهلة +
  شاهد حذف). **بلا** نداء ملكية بعيد — مطابق D-26 (الملكية = ملكية المستخدم/الحالة/الدفعة محليًّا).
- نصّ مرفوض **نهائيًّا** فقط ⇒ `rejected_ineligible`؛ أي عطل تقني/سباق غير مفسَّر ⇒ `record_update_failure`
  (غير مؤهّل) — التزام D-30/D-09-R2 fail-closed.
- المهلة تُقيَّم **مرة واحدة ذرّيًّا** داخل معاملة النيّة (D-25 بند 3): حيّ = `now < T0+15د`
  (مطابق `batch_is_expired`)، والمساواة = منتهٍ (fail-closed). الدفعة المنتهية تُرفض بلا وسم (الوسم A4).
- ردّ الرفض **أفضل-جهد بعد الالتزام** (بلا exactly-once، بلا تحويل الرفض النهائي لفشل قابل للإعادة).
- لا دعم captions/مجموعات (D-31): `handle_text` بيفحص `message.text`؛ التعليقات خارج النطاق.

### Not implemented / out of scope
- الإرسال البعيد/التسليم/outbox (B1–B3)، التنظيف/الوسم التلقائي (A4)، الإصدار/القبول (D-19).
- لا commit/push/PR/merge/نشر.

### Independent adversarial review (D-19) — ROUND 1 (Cloud API, 2026-11-11)
- مراجعة عدائية مستقلة عبر Cloud API (المحادثة `dd43624e59624165b87964ca90746a5a`)؛ أعادت بناء
  الأكواد في نسخة منفصلة وشغّلت اختباراتها. الحكم الأول: **NEEDS_REVISION**.
- **F-1 (MEDIUM، حاجب) — مُثبَت ومُصلَح:** دفعة `pending` بـ`t0` غير صالح كانت **لا حيّة ولا منتهية**
  ⇒ النصّ **يسقط لمسار البرومت العادي** (`outbox`/إرسال بعيد) — خرق صريح لـ D-29 بنود 4/5/7.
  الإصلاح: `has_expired_pending_attachment_batch` صارت **fail-closed** (`t0`/`now` غير صالح ⇒ «مش حيّة»)،
  مع حاجز «مفيش صفوف ⇒ False» كي لا يُرفض مستخدم بلا دفعة. اختبار انحدار جديد.
- **F-3 (MEDIUM) — مُصلَح:** الذرّية/الـCAS لم تكن مقفولة باختبار. اختبار حقن عطل جديد
  (`test_intent_write_is_atomic_on_failure`) يثبت التراجع الكامل.
- **F-2/F-4/F-7/F-8 (LOW/خارج النطاق):** F-2 (تغيّرات ack لمسارات العرض) من عمل سابق/خارج A3؛ F-4
  (`attachments.py` غائب عن الـdiff) قيد بيئة المراجعة (الملف موجود فعليًّا ومسجَّل في `app.py`).
  لم تُعدّل (خارج نطاق A3؛ لا كسر لعمل قائم).
- التحقّق: **2741 passed**؛ الاختبارات الجديدة تُسقط طفراتها (F-1 وF-3 مُثبَتان بالطفرة).
- إعادة مراجعة مستقلة (جولة 2، المحادثة `b2cfeacc644e49cba532410e2f1ca7c9`): الحكم **NEEDS_REVISION**.
  - **F1-2 (LOW) — مُصلَح:** `has_expired_pending_attachment_batch` كانت ترجّع `True` عند `now` غير صالح
    حتى بلا أي صفوف ⇒ رفض خاطئ لمستخدم بلا دفعة. أُضيف حاجز `if not rows: return False`.
  - **F1-1a/F1-1b (MEDIUM، سؤال سياسة) — لم يُعدَّل (STOP + توثيق):** دفعة بحالة **غير `pending`**
    (`intent_recorded`/`dispatching`/`uncertain`/`delivered`/`expired`/`rejected`/`failed`) ⇒ النصّ **يسقط
    لمسار البرومت العادي** (لأن `list_live_...`/`has_expired_...` مقيّدتان بـ`status=pending`).
    - هذا **ليس خطأً صريحًا مقابل قرار مالك**: D-29 يحكم «دفعة معلّقة **حيّة**» (= `pending` داخل المهلة)
      و«دفعة **منتهية**»؛ أما الحالات الأخرى فتنتمي لحدّ **A3↔B** (`dispatching`/`uncertain`/`delivered`
      حالات مرحلة B **غير مُصرَّح بها**)، و**A4** (الوسم `expired`).
    - **لماذا لم أُعدّل:** (أ) حجب **كل** الحالات غير `pending` خطأ (الحالات النهائية `delivered`/`expired`/
      `rejected`/`failed` لا غموض فيها، وحجبها **يُعلّق المستخدم دائمًا** ما دامت B غير منفَّذة)؛ (ب) تحديد
      «الحالات النشطة غير المُرسَلة» يتطلّب سياسة مرحلة B (D-10/D-11 غير مُصرَّح بهما) ⇒ **اختراع سياسة**.
      (ج) السلوك الحالي (نصّ بعد تسجيل النيّة = برومت عادي) متّسق مع خطة المراحل («A3 يوجّه النصّ عند وجود
      دفعة **حيّة**»، والحيّ = `pending`)، ويمنع تعليق المستخدم.
    - **المطلوب:** قرار مالك يحدّد أيّ الحالات غير `pending` تحجب البرومت العادي (واقتراح المراجع: حجب
      `intent_recorded`/`dispatching`/`uncertain`/`delivered`). التفاصيل في التقرير النهائي.
- التحقّق بعد الإصلاحات: **2741 passed**؛ `pyflakes=0`؛ `bandit -lll`=0؛ `node --test` 219/0.

### Open policy question (A3↔B boundary) — يتطلّب قرار مالك
أيّ حالات `attachment_batches` غير `pending` يجب أن **تحجب** البرومت العادي (fail-closed) بدل السقوط لمساره؟
الخيارات: (A) الحالي — لا حجب (النصّ برومت عادي)؛ (B) حجب الحالات «النشطة غير المُرسَلة» فقط
(`intent_recorded`، ولاحقًا `dispatching`/`uncertain`) مع ترك النهائية (`delivered`/`expired`/`rejected`/
`failed`) لا تحجب. **لا يُنفَّذ أيّ تغيير بلا قرار مالك** (تجنّب اختراع سياسة).

### Suggested next step
قرار مالك على السؤال أعلاه (F1-1a)، ثم إعادة مراجعة عدائية نظيفة قبل أي إرسال بعيد (B1–B3).

---

## OHB2-P0-A3-TERMINAL-BATCH-ROUTING-COMPLETE-REMEDIATION (2026-11-11)
- **الهدف:** إصلاح F2 (حالة دفعة مجهولة ⇒ fail-open) + F1 (نصّ دفعة نهائية يسقط للبرومت).
- **F2 — DONE (مُصلَح ومُتحقَّق):** في `bot/db.py`: `AttachmentBatchIntegrityError` +
  `has_unknown_attachment_batch_status` (SELECT DISTINCT status بالمِلك، مقارنة بايثون ضد
  `ATTACHMENT_BATCH_STATUSES`)؛ `classify_attachment_routing` تفحص المجهول/NULL **أولًا** وترفع.
  ينتشر لمعالج PTB ⇒ `FAILED_PERMANENT` غير مؤهّل، صفر outbox، صفر نداء بعيد. بلا تغيير SQL schema.
- **F1 — BLOCKED:** لا آلية هوية رسالة↔دفعة مُصرَّح بها ⇒ يحتاج قرار مالك. 7 اختبارات `xfail(strict=True)`.
- **الاختبارات:** `tests/test_attachment_terminal_routing_remediation.py` = 24 pass / 7 xfail.
- **التحقّق:** full suite **2798 passed / 7 xfailed** (خط الأساس 2774)؛ pyflakes=0؛ bandit High=0/Med=17؛
  frontend 219.
- **مراجعة عدائية مستقلة (جلستان):**
  - R1 `fb72c9ca…`: NEEDS_REVISION (F2-1/F2-2/F1-1/F1-2).
  - R2 `bd0e15dc…`: NEEDS_REVISION لكنه **أكّد**: F2-2 مُدحَض، F2-1 متأصّل ومقبول (ليس عيب الإصلاح)،
    لا انحدار A0/A1/A2/A3. المتبقّي BLOCKING-1 (القطعة غير مُلتزَمة — تعارض تعليمة «NO commit») و
    BLOCKING-2 (F1 غير متنازَل عنه). ملاحظتان: البوابة نصّية فقط؛ «الحجب ينفكّ بعد الإصلاح» مُتحقَّق.
- **قرارات (بلا سؤال):** الحالة المجهولة ⇒ استثناء منتشر (كما تنصّ المهمة)؛ F2-1 حجب متأصّل مقبول؛
  البوابة نصّية؛ `xfail(strict=True)` عمدًا؛ لا commit (تعليمة صريحة).
- **الحالة:** PARTIAL. **لا** commit/push/PR. تقرير: `docs/reviews/OHB2-P0-A3-TERMINAL-BATCH-ROUTING-REMEDIATION-REPORT.md`.
- **الخطوة التالية:** قرار مالك على F1 (آلية هوية أو تنازل صريح)، ثم (بإذن) دفع `agent/*` ليتحقّق CI.


---

## OHB2-P0-A0-A1-R4-REVIEW-AND-FINAL-CLOSURE (2026-11-11)
- **الهدف:** إغلاق متطلّبات الأدلّة/المراجعة المتبقّية للـ P0: مراجعة عدائية مستقلة لخطة R4 (§11)،
  إنتاج+مراجعة أدلّة A0 و A1، ثم حسم الإغلاق النهائي.
- **Phase One — مراجعة خطة R4:** **`R4_REVIEW_PASS_WITH_NOTES`**. الحقيقة التاريخية: شرط §11
  (مراجعة مستقلة للخطة **قبل** A0) **لم يتحقّق** قبل A0 (لا ملف مراجعة للخطة موجود — تحقّق شامل)،
  وهذا التقرير مراجعة **بأثر رجعي** تُغلق متطلّب التوثيق ولا تعيد كتابة التاريخ. التقرير:
  `docs/reviews/OHB2-P0-R4-PLAN-INDEPENDENT-REVIEW.md` (`d4a94246…`).
- **Phase Two/Three — A0:** أدلّة `A0_EVIDENCE_SUFFICIENT` + مراجعة `A0_REVIEW_PASS`؛ 3 طفرات
  مُلتقَطة. التقارير: `OHB2-P0-A0-IMPLEMENTATION-EVIDENCE-REPORT.md` (`23979931…`)،
  `OHB2-P0-A0-INDEPENDENT-ADVERSARIAL-REVIEW.md` (`8cfbffa6…`). ملاحظات INFO فقط.
- **Phase Four/Five — A1:** أدلّة `A1_EVIDENCE_SUFFICIENT` + مراجعة `A1_REVIEW_PASS_WITH_NOTES`؛
  5 طفرات مُلتقَطة. انحراف LOW: علَم rollback (F7) غير مُنفَّذ. التقارير:
  `OHB2-P0-A1-IMPLEMENTATION-EVIDENCE-REPORT.md` (`bd026325…`)،
  `OHB2-P0-A1-INDEPENDENT-ADVERSARIAL-REVIEW.md` (`a12faf6f…`).
- **Phase Six — الإغلاق النهائي:** **`P0_CLOSED_WITH_NOTES`**. كل المتطلّبات مستوفاة؛ A2–A4 سارية
  (تجزئات المراجعات مطابقة)؛ A4 remediation PASS؛ لا BLOCKER/HIGH/MEDIUM؛ لا انتهاك قرارات المالك.
  التقرير النهائي: `docs/reviews/OHB2-P0-FINAL-CLOSURE-AUDIT-REPORT.md` (`ff66e535…`).
- **التحقّق:** full suite **2884 passed**؛ A0=17، A1=34، A2=50، A4=44، A0–A4=308، A3/F1=65؛
  frontend 219؛ pyflakes=0؛ bandit High=0/Med=17؛ pip_audit نظيف.
- **الحالة:** DONE (إغلاق موثَّق). لا commit/push/PR؛ لا تفعيل Autopush. لا تعديل كود/اختبار.
- **الخطوة التالية:** لا شيء مطلوب للإغلاق؛ (اختياري، بموافقة مالك منفصلة) مواءمة F-5 `>=` مع A2 `>`،
  أو إضافة علَم F7.
