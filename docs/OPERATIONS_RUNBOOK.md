# دليل تشغيل OpenHandBot (Operations Runbook)

مرجع تشغيلي للمالك/المشغّل: إزاي تثبّت البوت وتشغّله، تفهم قاعدة البيانات وصندوق
الصادر، تتعافى من الأعطال، وتتحقق من الصحة. كل أمر ومتغيّر هنا مستخرَج من المستودع
نفسه (`bot/config.py`، `.env.example`، `bot/db.py`، `bot/app.py`، `bot/outbox.py`،
`bot/watcher.py`، `docs/REGRESSION_GATE.md`، `.github/workflows/ci.yml`).

> نطاق الدليل: التشغيل والصيانة والاسترجاع فقط. تفاصيل الـ API في `docs/API_NOTES.md`،
> والخطة الأصلية في `docs/PLAN.md`، والنشر على استضافة مجانية في `docs/DEPLOY_KATABUMP.md`.

---

## 1) المتطلبات

- **بايثون:** النسخ المدعومة والمختبَرة هي **3.11** و**3.13** (مصفوفة CI في
  `.github/workflows/ci.yml`). التشغيل الحالي على 3.13.
- **الاعتماديات:** كلها في `requirements.txt` (وقت التشغيل) و`requirements-dev.txt`
  (تطوير/اختبار). مفيش خدمات خارجية مطلوبة للاختبارات (بتشتغل على SQLite مؤقت/ذاكرة).
- **وصول الشبكة:** البوت بيعمل long polling على تيليجرام وطلبات HTTPS لـ OpenHands.
  مفيش منفذ وارد مطلوب.
- **بيانات الاعتماد:** توكن بوت تيليجرام + مفتاح OpenHands + معرّفك الرقمي (مستخدم
  واحد بس). كلها متغيّرات بيئة، ممنوع تتحط في الكود أو المستودع.

## 2) التثبيت

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # (أو requirements.txt للتشغيل فقط)
cp .env.example .env                  # واملأ القيم
```

قبل أي تشغيل حقيقي، شغّل بوابة الانحدار مرة عشان تتأكد إن البيئة سليمة:

```bash
python -m pyflakes bot/ automation/ main.py tests/
python -m pytest -q
```

## 3) متغيّرات البيئة

المصدر: `bot/config.py::load_config` و`.env.example`. البوت بيقرأ `.env` عبر
`python-dotenv` (لو الملف موجود)، وأي متغيّر موجود في البيئة بيفضل.

| المتغيّر | مطلوب؟ | الافتراضي | التحقّق |
| --- | --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | نعم | — | لازم يطابق `^\d{3,}:[A-Za-z0-9_-]{8,}$` (زي `123456:ABC…`) |
| `OPENHANDS_API_KEY` | نعم | — | طوله ≥ 8، ومفيش مسافات/محارف تحكّم |
| `ALLOWED_TELEGRAM_ID` | نعم | — | رقم صحيح موجب **واحد بس** (أكتر من ID مختلف ⇒ رفض) |
| `OPENHANDS_BASE_URL` | لا | `https://app.all-hands.dev` | لازم يبدأ بـ `http://` أو `https://` |
| `LOG_LEVEL` | لا | `INFO` | واحد من `DEBUG, INFO, WARNING, ERROR, CRITICAL` |
| `WATCHER_INTERVAL` | لا | `25` | رقم صحيح بين **5** و**3600** ثانية |
| `DB_PATH` | لا | `bot_state.sqlite3` | مسار ملف SQLite (انظر §4) |

ملاحظات:

- القيم بتتظبّط تلقائيًا: المسافات وعلامات التنصيص المحيطة بتتشال (`_clean`).
- رسائل أخطاء الإعداد بتذكر **اسم** المتغيّر بس، مش قيمته (احتمال يكون سر).
- `Config` عنده `__repr__` آمن: حتى لو اتسجّل بالغلط، ما بيطبعش التوكن/المفتاح.
- `WATCHER_INTERVAL` يقل عن 5 أو يزيد عن 3600 ⇒ `ConfigError` والبوت ما يبدأش.

## 4) قاعدة البيانات

- **النوع:** ملف SQLite واحد. **الافتراضي** `bot_state.sqlite3` في مجلد العمل الحالي
  (`bot/config.py`: `db_path`). المسار النسبي بيتفسّر بالنسبة لمجلد التشغيل الحالي —
  لو شغّلت من مكان مختلف، الملف هيتعمل هناك. استخدم مسارًا مطلقًا لو محتاج موقع ثابت.
- **مستثنى من Git:** `.gitignore` فيه `*.sqlite3`، فالملف عمره ما يتدفع للمستودع.
- **الإعداد وقت الإنشاء (`bot/db.py::Database.__init__`):**
  - `PRAGMA journal_mode=WAL` — يسمح بالقراءة أثناء الكتابة (الـ handlers والمراقب
    بيكتبوا في وقت واحد).
  - `PRAGMA busy_timeout=5000` — بدل ما يرمي `database is locked`، بيستنى لحد 5 ثواني.
  - `CREATE TABLE IF NOT EXISTS` للجداول: `watched`, `user_state`, `outbox`,
    `creation_jobs` (+ فهارس `idx_outbox_status`, `idx_creation_jobs_status`).
- **الترحيلات (`_migrate`):** إضافية وغير مدمّرة فقط (`ALTER TABLE … ADD COLUMN`) —
  بتضيف أعمدة جديدة للقواعد القديمة من غير فقد بيانات. الأعمدة المُدارة:
  `watched.chat_id`, `user_state.awaiting_at`, `user_state.awaiting_title`,
  `watched.submitted_at`, `watched.added_at`, `watched.retry_count`, `outbox.attempts`.
  الجداول الجديدة بتتعمل بـ `IF NOT EXISTS`. **مفيش حذف ولا إعادة كتابة للبيانات.**
- **الصيانة عند بدء التشغيل (`run_startup_maintenance`):** فحص سريع (`PRAGMA
  quick_check`) ثم `PRAGMA optimize` + `incremental_vacuum` (لو متاح) + `wal_checkpoint(TRUNCATE)`.
  - لو القاعدة سليمة: البوت يكمل.
  - لو الفحص فشل: **البوت مابيبدأش** — `main.py` يخرج بكود غير صفري (1) قبل أي polling، ومفيش
    workers ولا ادّعاء جاهزية. **مفيش إصلاح/حذف تلقائي** — راجع القاعدة يدويًا. (لو الفشل حصل
    جوه `_post_init` بعد الإقلاع، بيتسجّل `startup_failed` وبيتمنع التشغيل برضه.)
  - لو الصيانة نفسها فشلت (مش حرجة): بيسجّل `WARNING` ويكمل.
- **الإغلاق النظيف (`app._post_shutdown`):** يوقف الـ workers/المراقب، يقفل عميل httpx،
  يعمل `wal_checkpoint(TRUNCATE)` تاني، وبعدين `db.close()`. لو الـ checkpoint فشل،
  بيسجّل `WARNING` ويكمل الإغلاق.
- **نسخ/استرجاع (مهم):** لأن WAL مفعّل، وقت التشغيل في ملفات `-wal` و`-shm` جنب الملف
  الرئيسي. انسخ **التلاتة مع بعض** وقت توقف البوت (أو بعد checkpoint) عشان تاخد نسخة
  متّسقة. ما تنسخش الملف الرئيسي لوحده وقت التشغيل — ممكن تاخد نسخة ناقصة.

### أوامر فحص يدوية (قراءة فقط، آمنة)

```bash
sqlite3 bot_state.sqlite3 "PRAGMA quick_check;"            # سليم لو رجّع ok
sqlite3 bot_state.sqlite3 "PRAGMA integrity_check;"        # فحص كامل
sqlite3 bot_state.sqlite3 "PRAGMA wal_checkpoint(TRUNCATE);"  # أرجّع الـ WAL للقاعدة
sqlite3 bot_state.sqlite3 "SELECT status, COUNT(*) FROM outbox GROUP BY status;"
sqlite3 bot_state.sqlite3 "SELECT id, status, attempts, updated_at FROM outbox WHERE status IN ('pending','claimed','sending');"
sqlite3 bot_state.sqlite3 "SELECT conversation_id, retry_count FROM watched;"
```

> `sqlite3` أداة سطر أوامر منفصلة (مش جزء من بايثون). لو مش مثبّتة عندك، تقدر تعمل نفس
> الفحوص من غيرها عبر `/outbox` داخل تيليجرام (انظر §8) — ما تفتحش الملف ببايثون بأداة
> مكتوبة بسرعة على قاعدة شغّالة.

## 5) دورة حياة التشغيل

```bash
python main.py
```

- **البدء (`app.post_init`):** 1) صيانة القاعدة (§4) → 2) **تعافي الصندوق**
  (`outbox_recover`, `creation_recover`) قبل أي معالجة → 2.1) **تعافي/تسوية الإكمال
  المحلي** (`completion_recover`: صفوف `sent`/`done` قديمة من غير intent تُرجَع للتكامل
  المحلي بتحفّظ، بدون أي POST خارجي) → 3) بدء **worker واحد مالك** لصندوق البرومتات،
  و**worker واحد مالك** لطلبات الشات الجديد، و**worker واحد مالك** للإكمال المحلي،
  و**المراقب**، و**المُبلّغ**. فيه حرس يمنع إنشاء worker مكرّر لو `post_init` اتنادت تاني.
- **الاستقبال:** long polling على تيليجرام (`app.run_polling(drop_pending_updates=True)`)
  مع `concurrent_updates(True)` عشان تأكيد «وصل ✅» مايتأخّرش بسبب أمر بطيء.
- **الحالة المستقرة:** الـ workers بيعالجوا من الطوابير؛ المراقب بيسأل كل
  `WATCHER_INTERVAL` ثانية في طلب واحد لكل الشاتات المتابَعة.
- **الإغلاق:** `Ctrl+C` (SIGINT) أو SIGTERM ⇒ `post_shutdown` بيوقف كل حاجة بأمان
  (أي إرسال كان شغّال بيتعلّم حالة آمنة — انظر §7).
- **إعادة التشغيل:** آمنة. التعافي في `post_init` بيحوّل الحالات المتروكة لقيم آمنة
  قبل ما أي worker يشتغل، فمفيش ازدواج إرسال ولا إنشاء مكرّر.
- **liveness vs readiness:** `/health` = العملية عايشة (200 ثابت، مفيش فحص قاعدة).
  `/ready` = جاهز فعلاً (200) أو لأ (503): بيتحقق من تكامل القاعدة + بدء الـ workers.
  `/status` = liveness + readiness + ملخّص الإكمال (عدّادات بس). التفاصيل في §8.

## 6) بوابة الانحدار والتحقّق

المصدر: `docs/REGRESSION_GATE.md` و`.github/workflows/ci.yml`.

```bash
pip install -r requirements-dev.txt
python -m pyflakes bot/ automation/ main.py tests/  # لازم يخرج من غير أي تحذير
python -m pip_audit -r requirements-dev.txt                # SCA: لازم «No known vulnerabilities found»
python -m bandit -r bot/ automation/ main.py -lll -s B613  # SAST: مفيش نتائج عالية الخطورة
python -m pytest -q                                        # كل الاختبارات لازم تعدّي
```

- نفس الخطوات بتشتغل تلقائيًا في CI على `push`/`pull_request` لـ `main`، على
  **Python 3.11 و3.13** (وظيفتان: «Tests & lint» للـ Python + «Frontend tests (Node)»).
- `pyflakes` بقى يغطّي `automation/` كمان (فحص ثابت AST، مش استيراد/تنفيذ ⇒ مفيش تشغيل
  لأتمتة/autopush). `pip-audit` و`bandit` اتضافوا في OHB2-PHASE1E، و`bandit` كمان بقى
  يغطّي `automation/` (AUD-07) — نفس سياسة الفشل عند أي نتيجة عالية الخطورة.
- استثناء `B613` في bandit **مقصود**: علامات bidi (RTL) في التعليقات العربية، مش trojan-source.
- تشغيلات سريعة مركّزة (اختيارية):

```bash
python -m pytest -q tests/test_outbox.py tests/test_grouping.py   # الصندوق والتجميع
python -m pytest -q tests/test_config.py                          # الإعدادات
python -m pytest -q tests/test_db_maintenance.py                  # تكامل/صيانة القاعدة
python -m pytest -q tests/test_watcher.py tests/test_u01_watcher.py
```

- معايير القبول: فحص ثابت نضيف + كل الاختبارات خضراء + مفيش أسرار في الكود + أي تحديث
  لحقل واحد بيستخدم `UPDATE … WHERE id=:id` ضيّق (مش استبدال صف كامل).

## 7) نموذج الأمان: at-most-once

البوت مصمّم عشان **ما يبعتش نفس البرومت مرتين** (at-most-once)، على حساب إنه ممكن
**ما يبعتش** في حالات نادرة (يفضّل عدم الإرسال عن الإرسال المزدوج).

### حالات صندوق البرومتات (`outbox`)

| الحالة | المعنى | بعد إعادة التشغيل |
| --- | --- | --- |
| `pending` | اتسجّل بثبات، والإرسال لسه مابدأش | آمن ⇒ يتعاود |
| `claimed` | worker خده ذرّيًا، والـ POST لسه مابدأش | آمن ⇒ يرجع `pending` |
| `sending` | بدأ الـ POST والنتيجة مش محسومة | **`unknown`** (ما يتعاودش تلقائيًا) |
| `sent` | نجاح مؤكّد | نهائي |
| `unknown` | نتيجة غامضة (timeout/انقطاع/إلغاء) | نهائي (ما يتعاودش) |
| `failed` | رفض نهائي مؤكّد (4xx **باستثناء 429**) | نهائي |
| `discarded` | شال المالك السجل يدويًا | نهائي |

- حد إعادة المحاولة الآمنة: **`MAX_OUTBOX_ATTEMPTS = 5`** (`bot/outbox.py`). كل فشل
  **قبل** بدء الـ POST (sandbox مش جاهز / فشل قراءة الشات) بيزوّد `attempts` ذرّيًا.
  أول محاولة ⇒ إشعار مؤقّت؛ عند الحد ⇒ الحالة `failed` + إشعار واحد نهائي.
- حد الغموض: `sending` بيتسجّل **بثبات قبل الـ POST بالظبط**. أي انقطاع بعده ⇒ `unknown`
  (ما يتعاودش أبدًا تلقائيًا).

### حالات طلب الشات الجديد (`creation_jobs`)

| الحالة | المعنى | بعد إعادة التشغيل |
| --- | --- | --- |
| `pending` | مسجَّل، وPOST البدء لسه مابدأش | آمن ⇒ يتعاود |
| `claimed` | worker خده، والـ POST لسه مابدأش | آمن ⇒ يرجع `pending` |
| `starting` | بدأ POST البدء (أو استطلاع مهمة معروفة) | بـ `task_id` ⇒ استطلاع GET آمن؛ من غيره ⇒ `unknown` |
| `done` | اتأكد البدء واتعرف `conversation_id` | نهائي |
| `unknown` | نتيجة غامضة | نهائي |
| `failed` | رفض نهائي (4xx **باستثناء 429**) أو فشل مهمة | نهائي |
| `discarded` | شال المالك السجل يدويًا | نهائي |

### المراقب (`watcher`) وإشعارات الانتهاء

- `MAX_WATCH_NOTIFY_RETRIES = 5` (`bot/watcher.py`): أقصى عدد محاولات فاشلة متتالية
  لإشعار انتهاء **واحد**. العدّاد متخزّن في `watched.retry_count` (SQLite) فما يتصفّرش
  بإعادة التشغيل، وبيرجع 0 لما تبدأ دورة إشعار جديدة (حالة غير منتهية جديدة / إضافة
  متابعة). عند بلوغ الحد: البوت يستسلم ويشيل المتابعة (ما يحاولش كل دورة).
- **مش exactly-once:** لو العملية اتقطعت بين ما تيليجرام يقبل الرسالة وما نسجّل النجاح
  (شيل المتابعة)، ممكن الإشعار يتبعت تاني بعد إعادة التشغيل — مفيش آلية idempotency
  مثبّتة بين تيليجرام والقاعدة. ده قيد معروف ومقصود، مش عطل.

### حدود الاحتفاظ بحاجز تكرار التحديثات (`processed_updates`)

حاجز الإدخال (`bot/handlers.py::dedupe_update`، مجموعة `-1`) بيمنع معالجة نفس `update_id`
مرتين **طول ما سجله لسه موجود**. السجل نفسه (`processed_updates`) **محدود الحجم**، فالحماية
**مش دائمة**. التفاصيل:

**سياسة الاحتفاظ (retention):**
- الثابت `PROCESSED_UPDATES_KEEP = 50_000` (`bot/handlers.py`). القيمة دي **عدد صفوف
  محتفظ بيها (retention count)** — مش مدة زمنية، ومش حجم دفعة حذف.
- التقليم بيحصل **مرة واحدة عند الإقلاع** (`bot/app.py::_post_init`، البند 1.1b) عبر
  `Database.prune_processed_updates(keep)` (`bot/db.py`).
- الترتيب المستخدم: **`ORDER BY processed_at DESC, update_id DESC`** ⇒ بيُحتفظ بأحدث
  `keep` صف، والأقدم بيتحذف.
- لو التقليم فشل، بيتسجّل `WARNING` و**مايمنعش الإقلاع** (مقصود: التقليم غير حرج).
- **مهم:** الـ 50,000 **مش** «نافذة آمنة لإعادة التسليم». هو مجرد حدّ لحجم السجل؛ أي
  `update_id` أقدم من آخر 50,000 سجل «معالَج» **مش محميّ** من إعادة التنفيذ.

**طبيعة الضمان:**
- `processed_updates` بيوفّر **كشف تكرار دائم للسجلات اللي لسه متخزّنة** (مفتاح أساسي
  `update_id`، إدراج `INSERT OR IGNORE`).
- التسجيل الدائم **بيحصل ذرّيًا مع كتابة العملية** في نفس معاملة SQLite (المسارات:
  `add_or_group_outbox`، `add_creation_job`، `consume_one_shot_awaiting`،
  `toggle_notifications_once`) ⇒ إما الاتنين يتكتبوا أو ولا واحد.
- **بعد ما السجل يتقلّم، الحاجز مابيعرفش الـ `update_id` ده تاني.** لو نفس التحديث اتسلّم
  تاني بعد كده، **ممكن يعدّي الحاجز وينفّذ عمليته تاني**.
- يعني الميكانيزم **كشف تكرار محدود (bounded)**، **مش ضمان exactly-once**.
- **استثناء مقصود:** عمليات مابتكتبش سجل تكرار دائم (أوامر، تنقّل، أزرار قراءة،
  `watch:`/`unwatch:`) ⇒ إعادة تسليمها بتعيد التنفيذ عادي (أغلبها idempotent/قابلة
  للتكرار عمدًا). ده **مختلف** عن مسار الحماية العادي اللي بيسجّل `update_id`.

**دلالات polling في تيليجرام وPTB (مُتحقَّق منها في PTB v22.8):**
- PTB بيقدّم `_last_update_id` **بعد** ما يحط التحديثات المجلوبة في طابور التحديثات،
  **وقبل** ما الـ handler يخلّص (`.venv/.../telegram/ext/_updater.py`: `update_queue.put`
  ثم `_last_update_id = updates[-1].update_id + 1`).
- تيليجرام بيعدّ التحديث **مؤكَّدًا (confirmed)** لما نداء `getUpdates` لاحق يستخدم
  `offset` أكبر من `update_id` بتاعه (توثيق Bot API الرسمي).
- البوت بيشتغل بـ `run_polling(drop_pending_updates=True)` (`main.py`) ⇒ عند كل إقلاع
  التحديثات المعلّقة على خادم تيليجرام **بتترمى**.
- السلوكيات دي **بتقلّل** أو **بتلغي عمدًا** بعض فرص إعادة التسليم، لكنها **ماتحوّلش**
  آلية الاحتفاظ في القاعدة لضمان exactly-once.

**تمييز لازم (4 طبقات منفصلة):**
1. تأكيد تيليجرام من جهة الخادم (عند `offset` أعلى).
2. تقدّم `offset` في PTB (عند وضع التحديثات في الطابور).
3. الكشف الدائم في التطبيق (`processed_updates`).
4. اكتمال معاملة العملية (`commit`).
مفيش طبقة فيهم بتوفّر ضمان «مرة واحدة بالظبط» بشكل مستقل.

**المخاطر والحدود** (بحسب أدلة تحقيق `OHB2-PROCESSED-UPDATES-PRUNING-INVESTIGATION`):
- تجربة **معزولة داخل الذاكرة** أثبتت إن تقليم سجل بيسمح لنفس `update_id` إنه يعدّي
  الحاجز الحالي وينفّذ عملية دائمة تاني. التجربة بتثبت **الميكانيزم على مستوى التطبيق**،
  **مش** إعادة تسليم فعلية من تيليجرام.
- **إعادة التسليم الفعلية في الإنتاج لسه غير مُثبَتة**، والاحتمالية العملية **منخفضة جدًا**
  في الإعداد الحالي (التقليم عند الإقلاع فقط + `drop_pending_updates=True`).
- ده **قيد احتفاظ محدود (bounded-retention limitation)**، **مش** دليل على فساد بيانات
  حالي ولا حادثة إنتاج مؤكّدة.

**اعتبار مستقبلي (غير مُعتمد — للمراجعة فقط):** مراجعة تصميم مستقبلية ممكن تدرس سياسة
احتفاظ بنافذة زمنية متوافقة مع مدة احتفاظ تيليجرام الموثّقة، أو سياسة هجينة (حد أدنى
بالعدد + نافذة زمنية)، مع موازنة نمو التخزين والعبء التشغيلي. **مفيش سياسة جديدة
مختارة أو مُنفَّذة هنا، ومفيش سياسة 24 ساعة معتمدة.**

**مراجع المصدر:** `bot/handlers.py` (`PROCESSED_UPDATES_KEEP`، `dedupe_update`)،
`bot/db.py` (`processed_updates`، `update_is_processed`، `_mark_processed_nocommit`،
`prune_processed_updates`، دوال الكتابة الذرّية)، `bot/app.py` (استدعاء التقليم في
`_post_init`)، `main.py` (`run_polling(drop_pending_updates=True)`)،
`.venv/.../telegram/ext/_updater.py` (تقدّم `offset`).

## 8) الفحص والتسوية اليدوية

### أوامر البوت (للمالك فقط، أي مستخدم تاني بيتجاهل بصمت)

| الأمر | الاستخدام |
| --- | --- |
| `/outbox` | عرض محدود للسجلات **غير المنتهية** (prompt/creation): المعرّف، الحالة، المحاولات، آخر تحديث — **بدون نص البرومت** |
| `/outbox_status <prompt:id \| creation:id>` | تفاصيل سجل واحد (الحالة، المحاولة، آخر خطأ، الطوابع الزمنية) |
| `/outbox_discard <prompt:id \| creation:id> confirm` | تعليم سجل **غير نهائي** كـ `discarded` (نهائي). idempotent |
| `/outbox_mark_sent <prompt:id \| creation:id> confirm` | تعليم سجل `unknown` كـ `sent`/`done` — **تأكيد منك** إن العملية نجحت (مش إثبات من OpenHands). ما بيعيدش إرسال |

قواعد مهمة:

- المرجع لازم يكون **`prompt:<id>` أو `creation:<id>`** بالظبط (النوع إلزامي — رقم
  مجرّد مرفوض عشان ما يختارش جدول بالغلط).
- `/outbox_discard` و`/outbox_mark_sent` بيسيبوا **الحالات النهائية زي ما هي** (مفيش تغيير).
- **ممنوع** أي إعادة إرسال تلقائية لسجل `unknown`. القرار الوحيد المتاح: تتأكد بنفسك من
  الموقع، وبعدين إما `mark_sent` (لو وصل فعلًا) أو `discard` (لو مش عايزه). الحالتان
  نهائيتان، فالسجل عمره ما يرجع `pending`.

### إجراء آمن لمعالجة سجل `unknown` أو `failed`

1. `/outbox` ⇒ خد معرّف السجل الغامض.
2. `/outbox_status prompt:<id>` ⇒ شوف آخر خطأ ووقت آخر تحديث.
3. افتح الشات على OpenHands وتأكد بنفسك: هل البرومت وصل/اتنفّذ؟
4. لو **وصل**: `/outbox_mark_sent prompt:<id> confirm`.
   لو **مش عايزه**: `/outbox_discard prompt:<id> confirm`.
5. لو محتاج تبعت من جديد: افتح الشات من الموقع وابعت البرومت من هناك (مش من البوت).

### رصد وحل أعمال الإكمال المحلي (F02 STABILIZATION)

بعد ما العملية الخارجية تنجح، البوت بيسجّل **intent إكمال محلي** (إشعار المستخدم + تسجيل
المتابعة) في **نفس معاملة** الانتقال `sent`/`done` — فمستحيل يبقى فيه نجاح خارجي من غير
إكمال محلي قابل للتعافي. الإكمال المحلي **ما بيعملش أي POST خارجي** أبدًا.

- **مصادر الرصد:** `/status` (عام، عدّادات بس) و`CompletionWorker.health()`
  (`pending` / `eligible` / `deferred` / `exhausted` / `oldest_pending_at` / آخر نجاح/فشل).
- **الاستنفاد (`exhausted`):** لو إشعار تيليجرام فشل `COMPLETION_MAX_ATTEMPTS=5` مرة
  (بـ backoff أسّي محدود: 5، 10، 20، 40 ثانية)، الصف يتعلّم `exhausted=1` و**يتسيب ظاهر**
  (مايتشالش)، ويُستبعد من المؤهّل ⇒ مايعطّلش باقي الأعمال (fairness). يظهر في `/status`
  كـ `completion.exhausted` و`checks.completion == "action_required"`.
- **الحل الآمن (بدون إعادة أي عملية خارجية):** بعد ما تتأكد إن سبب الفشل اتحلّ (مثلًا
  الشات اتفتح تاني)، أعد تأهيل الصف بـ `Database.rearm_completion_pending(kind, ref_id, now)`
  — بيصفّر `exhausted`/`next_attempt_at`/`attempts` من غير أي POST. الـ worker هيحاول تاني.
- **الصفوف القديمة (`sent`/`done` من غير intent):** **ما تتسوّاش تلقائيًا** — مستحيل
  نفرّق بأمان بين صف اكتمل فعلًا (الإكمال اتشال بعد النجاح) وصف وقع في نافذة الـ crash
  القديمة، فالتسوية التلقائية كانت هتبعت إشعارات مكرّرة. بدل كده تفضل **ظاهرة للمشغّل**
  كـ `completion.legacy_unresolved` في `/status`، وللمشغّل تسوية **يدوية صريحة** لكل مرجع
  بـ `Database.reconcile_legacy_completion(kind, ref_id, now)` — بينشئ intent من الحقول
  الموجودة فعلًا بس، **بدون أي POST خارجي ولا اختلاق نجاح**.
- **ملاحظة:** عناصر `deferred` (مجدولة) وعناصر `exhausted` **لا** تمنع الجاهزية
  (`/ready` يفضل 200)، لكنها ظاهرة في `/status` للتدخّل.

## 9) استكشاف الأعطال

| العرض | السبب المحتمل | الإجراء |
| --- | --- | --- |
| `ConfigError: متغيرات بيئة ناقصة: …` | متغيّر مطلوب مش متظبّط | ظبّط `TELEGRAM_BOT_TOKEN` / `OPENHANDS_API_KEY` / `ALLOWED_TELEGRAM_ID` |
| `TELEGRAM_BOT_TOKEN شكله غلط` | التوكن مش بصيغة `\d+:[A-Za-z0-9_-]+` | انسخه تاني من @BotFather |
| `WATCHER_INTERVAL لازم يكون بين 5 و3600` | قيمة برّا المدى | عدّلها لقيمة صحيحة |
| البوت مش بيرد على حد | `ALLOWED_TELEGRAM_ID` غلط | اتأكد إنه معرّفك الرقمي الصح |
| «الـ sandbox مش قادر يشتغل» | sandbox الشات مش `RUNNING` | البوت بيحاول يوقّظه؛ لو فشل، افتح الشات من الموقع |
| «تعذّر إرسال البرومت بعد عدة محاولات» | استُنفد `MAX_OUTBOX_ATTEMPTS=5` | راجع `/outbox`؛ ابعت من الموقع |
| «مش قادرين نتأكد إن البرومت وصل» (`unknown`) | انقطاع/مهلة أثناء الإرسال | §8: تأكّد من الموقع ثم `mark_sent`/`discard` |
| «مفتاح OpenHands غير صحيح أو منتهي» (401) | مفتاح غلط/منتهي | جدّد `OPENHANDS_API_KEY` |
| «طلبات كتير على OpenHands» (429) | rate limit (فشل عابر) | قبل بدء الـ POST: السجل يفضل `pending` ويتعاود تلقائيًا بحد `MAX_OUTBOX_ATTEMPTS=5`؛ بعد بدء الـ POST: غامض ⇒ `unknown` ⇒ §8 |
| «خطأ داخلي في OpenHands» (500) | عطل مؤقّت عند OpenHands | يتعاود في دورة لاحقة؛ السجل غامض ⇒ §8 |
| «فيه برومت ممكن يكون اتبعت قبل إعادة التشغيل» | تعافي `sending` ⇒ `unknown` | §8: تأكّد من الموقع قبل أي إعادة إرسال |
| رسالة إشعار ما وصلتش للشات | فشل تيليجرام متكرّر | البوت يعيد المحاولة حتى `MAX_WATCH_NOTIFY_RETRIES=5` ثم يوقف المتابعة |
| الشات «لم يعد موجوداً» | اتمسح من OpenHands | المراقب بيلاحظ غيابه `MISSING_LIMIT=3` دورات ثم يبلّغ ويوقف المتابعة |
| `database is locked` | كتابة متزامنة | WAL + `busy_timeout=5000` بيتعاملوا معاه؛ لو استمر راجع مساحة القرص/الصلاحيات |
| «إكمال محلي مستنفد» (`/status` ⇒ `completion.exhausted > 0`) | فشل إشعار تيليجرام متكرّر | راجع الشات، وبعد حل السبب `rearm_completion_pending` (§8) — بدون إعادة أي POST |
| `/ready` بيرجّع 503 | القاعدة مش متحقّقة أو فشل إقلاع أو worker مش شغّال | شوف `/status` ⇒ `readiness.checks`: `database`/`startup`/`*_worker`. القاعدة التالفة: أوقف البوت وخد نسخة (§4) — **مفيش إصلاح تلقائي** |
| القاعدة «فحصها فشل» في اللوج | تلف ملف SQLite | أوقف البوت، خد نسخة من الملفات التلاتة (§4)، وافحص بـ `integrity_check` |

ملاحظات تشخيص عامة:

- البوت **مابيسجّلش** نص البرومتات كامل، ولا التوكن/المفتاح (فلتر `RedactingFilter`
  بيخفي أي سر مسجَّل من الرسالة والمعاملات والـ traceback).
- الأخطاء غير المتوقعة في شات واحد **معزولة**: ما توقفش باقي دورة المراقب.
- أي `500`/`429` عابر من OpenHands وارد؛ السجلات بتفضل متّسقة والـ worker بيتعافى
  في الدورة الجاية. **ملاحظة (OHB2-N10-05):** `429` تصنيفه فشل **عابر** مش دائم — قبل
  بدء الـ POST بيتعاود تلقائيًا، وبعد بدء الـ POST يبقى `unknown` (غامض، مايتعادش
  تلقائيًا) لحماية at-most-once. أي `4xx` تاني (مثل `422`) رفض دائم ⇒ `failed`.

## 10) مرجع سريع

- الإعداد: `bot/config.py` · البيئة: `.env.example`
- القاعدة والترحيلات/الصيانة: `bot/db.py`
- تجميع التطبيق ودورة الحياة: `bot/app.py` · التشغيل: `main.py`
- الصندوق وحدود المحاولات: `bot/outbox.py`
- المراقب وإشعارات الانتهاء: `bot/watcher.py`
- أوامر التشغيل: `bot/handlers.py` (`/outbox*`)
- بوابة الانحدار: `docs/REGRESSION_GATE.md` · CI: `.github/workflows/ci.yml`
- الـ API: `docs/API_NOTES.md` · النشر: `docs/DEPLOY_KATABUMP.md`
