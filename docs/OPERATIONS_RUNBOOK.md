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
python -m pyflakes bot/ main.py tests/
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
  - لو الفحص فشل: **البوت بيفضل شغّال** بس بيسجّل `ERROR` واضح (ما بيرميش استثناء).
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
  (`outbox_recover`, `creation_recover`) قبل أي معالجة → 3) بدء **worker واحد مالك**
  لصندوق البرومتات، و**worker واحد مالك** لطلبات الشات الجديد، و**المراقب**. فيه حرس
  يمنع إنشاء worker مكرّر لو `post_init` اتنادت تاني.
- **الاستقبال:** long polling على تيليجرام (`app.run_polling(drop_pending_updates=True)`)
  مع `concurrent_updates(True)` عشان تأكيد «وصل ✅» مايتأخّرش بسبب أمر بطيء.
- **الحالة المستقرة:** الـ workers بيعالجوا من الطوابير؛ المراقب بيسأل كل
  `WATCHER_INTERVAL` ثانية في طلب واحد لكل الشاتات المتابَعة.
- **الإغلاق:** `Ctrl+C` (SIGINT) أو SIGTERM ⇒ `post_shutdown` بيوقف كل حاجة بأمان
  (أي إرسال كان شغّال بيتعلّم حالة آمنة — انظر §7).
- **إعادة التشغيل:** آمنة. التعافي في `post_init` بيحوّل الحالات المتروكة لقيم آمنة
  قبل ما أي worker يشتغل، فمفيش ازدواج إرسال ولا إنشاء مكرّر.

## 6) بوابة الانحدار والتحقّق

المصدر: `docs/REGRESSION_GATE.md` و`.github/workflows/ci.yml`.

```bash
pip install -r requirements-dev.txt
python -m pyflakes bot/ main.py tests/   # لازم يخرج من غير أي تحذير
python -m pytest -q                      # كل الاختبارات لازم تعدّي
```

- نفس الخطوتين بتشتغلوا تلقائيًا في CI على `push`/`pull_request` لـ `main`، على
  **Python 3.11 و3.13** (وظيفتان: «Tests & lint»).
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
| `failed` | رفض نهائي مؤكّد (4xx) | نهائي |
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
| `failed` | رفض نهائي (4xx) أو فشل مهمة | نهائي |
| `discarded` | شال المالك السجل يدويًا | نهائي |

### المراقب (`watcher`) وإشعارات الانتهاء

- `MAX_WATCH_NOTIFY_RETRIES = 5` (`bot/watcher.py`): أقصى عدد محاولات فاشلة متتالية
  لإشعار انتهاء **واحد**. العدّاد متخزّن في `watched.retry_count` (SQLite) فما يتصفّرش
  بإعادة التشغيل، وبيرجع 0 لما تبدأ دورة إشعار جديدة (حالة غير منتهية جديدة / إضافة
  متابعة). عند بلوغ الحد: البوت يستسلم ويشيل المتابعة (ما يحاولش كل دورة).
- **مش exactly-once:** لو العملية اتقطعت بين ما تيليجرام يقبل الرسالة وما نسجّل النجاح
  (شيل المتابعة)، ممكن الإشعار يتبعت تاني بعد إعادة التشغيل — مفيش آلية idempotency
  مثبّتة بين تيليجرام والقاعدة. ده قيد معروف ومقصود، مش عطل.

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
| «طلبات كتير على OpenHands» (429) | rate limit | استنى شوية وحدّل التكرار |
| «خطأ داخلي في OpenHands» (500) | عطل مؤقّت عند OpenHands | يتعاود في دورة لاحقة؛ السجل غامض ⇒ §8 |
| «فيه برومت ممكن يكون اتبعت قبل إعادة التشغيل» | تعافي `sending` ⇒ `unknown` | §8: تأكّد من الموقع قبل أي إعادة إرسال |
| رسالة إشعار ما وصلتش للشات | فشل تيليجرام متكرّر | البوت يعيد المحاولة حتى `MAX_WATCH_NOTIFY_RETRIES=5` ثم يوقف المتابعة |
| الشات «لم يعد موجوداً» | اتمسح من OpenHands | المراقب بيلاحظ غيابه `MISSING_LIMIT=3` دورات ثم يبلّغ ويوقف المتابعة |
| `database is locked` | كتابة متزامنة | WAL + `busy_timeout=5000` بيتعاملوا معاه؛ لو استمر راجع مساحة القرص/الصلاحيات |
| القاعدة «فحصها فشل» في اللوج | تلف ملف SQLite | أوقف البوت، خد نسخة من الملفات التلاتة (§4)، وافحص بـ `integrity_check` |

ملاحظات تشخيص عامة:

- البوت **مابيسجّلش** نص البرومتات كامل، ولا التوكن/المفتاح (فلتر `RedactingFilter`
  بيخفي أي سر مسجَّل من الرسالة والمعاملات والـ traceback).
- الأخطاء غير المتوقعة في شات واحد **معزولة**: ما توقفش باقي دورة المراقب.
- أي `500`/`429` عابر من OpenHands وارد؛ السجلات بتفضل متّسقة والـ worker بيتعافى
  في الدورة الجاية.

## 10) مرجع سريع

- الإعداد: `bot/config.py` · البيئة: `.env.example`
- القاعدة والترحيلات/الصيانة: `bot/db.py`
- تجميع التطبيق ودورة الحياة: `bot/app.py` · التشغيل: `main.py`
- الصندوق وحدود المحاولات: `bot/outbox.py`
- المراقب وإشعارات الانتهاء: `bot/watcher.py`
- أوامر التشغيل: `bot/handlers.py` (`/outbox*`)
- بوابة الانحدار: `docs/REGRESSION_GATE.md` · CI: `.github/workflows/ci.yml`
- الـ API: `docs/API_NOTES.md` · النشر: `docs/DEPLOY_KATABUMP.md`
