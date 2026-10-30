# Mini App (OHB2-05/06) — خلفية ASGI + مصادقة initData + ميزات البوت + تحصين أمني

> **النطاق:** الـ Mini App دلوقتي **واجهة عملية** لقدرات البوت (الشاتات، البرومتات،
> الشات الجديد، المتابعات، الإشعارات) — مش تطبيق منفصل. كل الطلبات بتنادي **نفس**
> طبقة الخدمات وقاعدة البيانات بتاعة البوت (مفيش منطق أعمال مكرّر).
> OHB2-06 ضاف كمان: تحصين توقيع initData، تحديد معدّل، حماية Origin، وتحديد IP العميل.

## 1. نظرة عامة

الـ Mini App بيتقدّم من **نفس عملية البوت الواحدة** (OHB2-04 اختار Option A):

```
Telegram WebView ──HTTPS──▶ ingress (TLS) ──HTTP──▶ الحاوية:MINI_APP_PORT
                                                          │
                                        عملية asyncio واحدة:
                                        • long polling بتاع البوت (زي ما هو)
                                        • سيرفر Uvicorn/Starlette (task جنب البوت)
                                        • نفس كائن Database الواحد
                                        • نفس كائن OpenHandsClient
```

- مفيش عملية تانية، مفيش worker تاني، مفيش اتصال SQLite تاني.
- الواجهة والـ API على **نفس الأصل** (same-origin) ⇒ كوكي جلسة `SameSite=Strict` بدون تعقيدات CORS.
- كل الردود JSON، والأخطاء بشكل موحّد `{"error": code, "message": ...}`.

## 2. التبعيات

| الحزمة | الإصدار | ليه |
| --- | --- | --- |
| `starlette` | `0.41.3` | إطار ASGI صغير (راوتنج + responses) بدون أي إطار ثقيل |
| `uvicorn` | `0.34.0` | سيرفر ASGI قياسي، بيشتغل كـ task جوه event loop الموجود |

مقصور إننا **ما ضفناش FastAPI** ولا مكتبة rate-limiting خارجية — كل حاجة صغيرة وبدون تبعيات.

## 3. دمج السيرفر مع عملية البوت

- `bot/app.py::_wire_mini_app` بيربط خلفية الـ Mini App بدورة حياة البوت، **بس لما `MINI_APP_ENABLED=1`**،
  وبيمرّر `client` (OpenHandsClient) و`application` للخدمة (عشان تنبّه الـ workers المالكين الموجودين).
- `bot/web/runner.py::web_server_lifespan`:
  - بيربط الـ socket بنفسه (`_bind_socket`) ويمرّره لـ Uvicorn. كده فشل الربط (منفذ مستخدم)
    يطلع `OSError` عادي ⇒ **التشغيل كله يفشل بوضوح** (fail-fast).
  - بيعطّل `uvicorn.Server.capture_signals` وقت التشغيل المشترك، عشان **البوت** هو اللي
    يمسك SIGINT/SIGTERM ويعمل إغلاق نظيف.
  - `proxy_headers=False` (شوف القسم 8 — قرار أمني مقصود).
- الترتيب في `post_init`: البوت بيعمل تعافيه ويشغّل الـ workers/المراقب **قبل** ما سيرفر الويب
  يبدأ. في `post_shutdown`: السيرفر يقف **قبل** ما البوت يقفل الموارد (`client`, `db`).
- حرس تكرار: إعادة تهيئة مكرّرة (`post_init` اتنادت مرتين) **ما بتبدأش سيرفر تاني**.

## 4. المسارات (API)

| المسار | الميثود | مصادقة | تغيير حالة | الوصف |
| --- | --- | --- | --- | --- |
| `/health` | GET | لأ | لأ | فحص صحة. مفيش أسرار. **بدون تحديد معدّل** |
| `/api/v1/auth` | POST | لأ | لأ | يستقبل `{"initData": "..."}` ⇒ كوكي جلسة |
| `/api/v1/auth/logout` | POST | كوكي | ✔ | يلغي الجلسة ويمسح الكوكي |
| `/api/v1/app/bootstrap` | GET | كوكي | لأ | اسم العرض + الإشعارات + ميتا |
| `/api/v1/app/notifications` | POST | كوكي | ✔ | `{"enabled": bool}` يضبط الإشعارات |
| `/api/v1/conversations` | GET | كوكي | لأ | آخر الشاتات (صفحات، `?page=&refresh=1`) |
| `/api/v1/conversations/{id}` | GET | كوكي | لأ | تفاصيل شات + آخر برومت/رد + رابط PR |
| `/api/v1/conversations/{id}/status` | GET | كوكي | لأ | حالة شات بس |
| `/api/v1/conversations/{id}/prompt` | POST | كوكي | ✔ | `{"text": "..."}` ⇒ يسجّل البرومت في الصندوق |
| `/api/v1/conversations/{id}/watch` | POST | كوكي | ✔ | يضيف الشات للمتابعة |
| `/api/v1/conversations/{id}/watch` | DELETE | كوكي | ✔ | يلغي المتابعة |
| `/api/v1/watches` | GET | كوكي | لأ | قائمة المتابعات |
| `/api/v1/repositories` | GET | كوكي | لأ | بحث المستودعات (`?q=&page=`) |
| `/api/v1/chats` | POST | كوكي | ✔ | `{"repository": "owner/repo", "text": "..."}` ⇒ شات جديد |
| `/api/v1/*` (غير معروف) | أي | — | — | `404` JSON موحّد |
| `/`, `/mini/`, `/mini/<asset>` | GET | لأ | لأ | الواجهة والأصول الثابتة (**بدون تحديد معدّل**) |

## 5. إعادة استخدام منطق البوت (مفيش تكرار)

`bot/web/services.py::MiniAppService` هي الطبقة الرقيقة الوحيدة فوق المكوّنات الموجودة:

| عملية الـ Mini App | المنطق المُعاد استخدامه |
| --- | --- |
| قائمة الشاتات | `OpenHandsClient.search_conversations` + نفس كاش البوت القصير (`list_cache`) |
| تفاصيل شات | `get_conversations` + `get_last_exchange` + `messages.get_status/state_label/truncate` |
| إرسال برومت | **`db.add_or_group_outbox`** (نفس الصندوق المتين + التجميع) ثم `worker.wake()` |
| شات جديد | **`db.add_creation_job`** ثم `worker.wake()` |
| متابعة/إلغاء | `db.add_watched` / `db.remove_watched` (أو `watcher.unwatch` لو موجود) |
| الإشعارات | `db.get/set_notifications_enabled` |
| الحالة | `messages.get_status` (نفس مصدر الحقيقة) |

- **مفيش إرسال مباشر من الـ API**: البرومتات والشاتات الجديدة بتمر بنفس الـ workers المالكين
  (at-most-once، تعافي عند إعادة التشغيل، تجميع) — مفيش ازدواج ولا سلوكين مختلفين.
- الخدمة **ما بتبدأش أي worker**؛ بس بتنبّه الموجود عبر `application.bot_data`.

## 6. تدفّق المصادقة (initData) + التحصين (S1)

بيتّبع [إجراء تيليجرام الرسمي](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app):

1. الواجهة تاخد `Telegram.WebApp.initData` الخام (**مش** `initDataUnsafe`) وتبعتها في `POST /api/v1/auth`.
2. السيرفر (`bot/web/initdata.py`):
   - يشتق المفتاح السري: `secret = HMAC_SHA256("WebAppData", bot_token)`.
   - يبني `data_check_string` (كل الحقول ما عدا `hash`/`signature`، مرتبة أبجديًا، مفصولة بـ `\n`).
   - **S1 (OHB2-06):** يتحقق إن `hash` **64 حرف hex بالظبط** (`^[0-9a-fA-F]{64}$`) **قبل** أي مقارنة.
     أي قيمة فاضية/قصيرة/طويلة/غير hex/بأحرف غير ASCII ⇒ `InitDataError` منظّم (401)، وما توصلش
     لـ `hmac.compare_digest` (اللي كان بيرمي `TypeError` ⇒ 500).
   - يقارن بمقارنة **ثابتة الزمن** (`hmac.compare_digest`)، وملفوفة في `try` كأمان إضافي.
   - يتحقق من `auth_date`: يرفض المستقبلي (بهامش 30 ثانية) ويرفض الأقدم من `MINI_APP_INITDATA_MAX_AGE`.
   - **بعد** نجاح التوقيع بس بيقرأ `id` المستخدم من حقل `user`.
3. لو التحقق نجح **و** الـ id ∈ `ALLOWED_TELEGRAM_ID` ⇒ توكن جلسة عشوائي (opaque)
   في كوكي `ohb_session` (`HttpOnly; Secure; SameSite=Strict; Path=/`).
4. الطلبات اللاحقة بتيجي بالكوكي؛ السيرفر يدوّر على الجلسة في **مخزن في الذاكرة** (TTL).
5. `logout` بيلغي الجلسة ويمسح الكوكي.

### ضمانات أمنية

- مفيش ثقة في أي `id` جاي من الجافاسكريبت — بيُقرأ بعد التوقيع، وبيتحقق من `ALLOWED_TELEGRAM_ID`.
- مفيش بيانات مصادقة في `localStorage`؛ الجلسة كوكي HTTP-only فقط.
- مفيش أسرار أو توقيعات في الكوكي نفسه (توكن عشوائي، والسيرفر هو اللي يعرف معناه).
- مستخدم غير مسموح ⇒ `403` (ومفيش أي تفاصيل حساسة في الرسالة). أي جلسة لمستخدم اتشال من
  القايمة بتتبطّل وتترفض.

## 7. تحديد المعدّل (S2)

`bot/web/ratelimit.py::SlidingWindowLimiter` — نافذة منزلقة في الذاكرة، بدون تبعيات، بساعة قابلة للحقن.

- **`/auth`:** لكل **IP** — افتراضيًا **10/دقيقة** و**30/ساعة** (`MINI_APP_AUTH_RATE_PER_MINUTE`,
  `MINI_APP_AUTH_RATE_PER_HOUR`).
- **باقي الـ API المصادَقة:** لكل **جلسة** — افتراضيًا **60/دقيقة** (`MINI_APP_API_RATE_PER_MINUTE`).
- التجاوز ⇒ **`429`** مع هيدر **`Retry-After`** صحيح (بالثواني).
- **الانفجارات مسموحة**: الحدود متسامحة مع دفعات صغيرة، والواجهة بتعمل retry واحد بسيط (700ms)،
  فالاتصال الضعيف ما بيتعاقبش.
- **تنضيف المدخلات المنتهية**: كل فحص بيشيل الطوابع الأقدم من أوسع نافذة.
- **حد للذاكرة**: `MINI_APP_RATE_MAX_KEYS` (افتراضي 4096) مع طرد الأقدم (LRU) ⇒ مفيش نمو بلا حد.
- **`/health` والأصول الثابتة مش متحدّدين** عشان فحص الصحة وتحميل الواجهة يفضلوا شغالين.
- **مفيش تسجيل بيانات حساسة**: المفاتيح معرّفات مستعارة (توكن الجلسة أو `ip:...`)، مش توكنات.
- الطلب المرفوض **ما بيتسجّلش** (عشان ما يمدّدش الحظر).

## 8. تحديد IP العميل + الـ proxy (S3)

**اكتشاف فعلي (probe على الـ runtime):** الـ ingress (Traefik) **ما بينضّفش** أي `X-Forwarded-For`
جاي من العميل — بيعمل **إلحاق** للند الحقيقي على اليمين:

```
عميل مزوّر:  X-Forwarded-For: 203.0.113.7            (من العميل)
اللي وصل:    X-Forwarded-For: 203.0.113.7, 10.1.1.62 (Traefik لحق 10.1.1.62)
وكمان:       X-Real-Ip: 10.1.1.62 ، TCP client = 10.2.97.6 (hop داخلي تاني)
```

النتيجة: `X-Forwarded-For` كله **غير موثوق** هنا. لو منحنا Uvicorn ثقة (`proxy_headers=True`)،
كان هياخد أول قيمة غير موثوقة من اليمين = **القيمة المزوّرة من العميل** ⇒ انتحال IP.
لذلك:

- **`proxy_headers=False`** في `bot/web/runner.py` — بنستخدم `request.client.host` (الند الحقيقي).
- `bot/web/clientip.py::resolve_client_ip` بيسقط أي IP محلي/غير صالح تحت مفتاح واحد `"unknown"`.
- **القيد الموثّق:** في الـ topology دي، كل العملاء المباشرين بيمرّوا عبر نفس الـ hop الداخلي،
  فـ IP المستخدم النهائي **مش ممكن نستخرجه بثقة**. يعني تحديد المعدّل «لكل IP» بيقرب من «عام».
  ده **الخيار المتحفّظ الآمن (fail closed)**: ما بنصدّقش أي هيدر يزوّره العميل، وما بنفترضش إن IP
  شفناه هو المستخدم النهائي. لو النشر بقى خلف proxy موثوق إحنا نتحكّم فيه، بيتضاف نطاقه هنا
  ونستخدم XFF بأمان.
- **افتراض النشر:** الـ Mini App خلف ingress واحد بيتحكم فيه المشغّل، والوصول مقصور على المالك
  المسموح بعد مصادقة initData. تحديد المعدّل دفاع إضافي (طبقة داخل العملية)، مش خط الدفاع الوحيد.

## 9. حماية Origin (S4)

طلبات **تغيّر الحالة** لازم تكون من أصل مسموح (`bot/web/app.py::_origin_ok`):

- `Origin` لازم يطابق `mini_app_allowed_origins` (بتتشتق من `MINI_APP_URL`، أو صريحة في
  `MINI_APP_ALLOWED_ORIGINS`). شبكة أمان للتطوير: نفس الـ host المطلق.
- `Sec-Fetch-Site: cross-site` ⇒ رفض فوري (إشارة إضافية، مش بديل عن فحص الـ Origin).
- الطلبات **قراءة** (GET) ما بتتطلبش Origin.
- `SameSite=Strict` **ما اتضعّفش** — ده خط دفاع أول، وفحص الـ Origin خط تاني.
- الرد الرفض: `403 {"error": "bad_origin"}`.

## 10. متغيرات البيئة

```
MINI_APP_URL=                 # رابط عام https (مطلوب لما MINI_APP_ENABLED=1)
MINI_APP_ENABLED=0            # 1 لتشغيل خلفية ASGI جوه عملية البوت
MINI_APP_PORT=12000
MINI_APP_INITDATA_MAX_AGE=300
MINI_APP_SESSION_TTL=3600
MINI_APP_COOKIE_SECURE=1      # 1 إنتاج، 0 تطوير محلي على http فقط
# OHB2-06:
MINI_APP_ALLOWED_ORIGINS=     # فاضية = بتتشتق من MINI_APP_URL (فواصل للزيادة)
MINI_APP_AUTH_RATE_PER_MINUTE=10
MINI_APP_AUTH_RATE_PER_HOUR=30
MINI_APP_API_RATE_PER_MINUTE=60
MINI_APP_RATE_MAX_KEYS=4096
```

## 11. التطوير المحلي والاختبار

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # املأ القيم، وحط MINI_APP_ENABLED=1 للتجربة المحلية
python main.py
```

للتجربة المحلية على http: خلي `MINI_APP_COOKIE_SECURE=0`، وأضف `http://localhost:12000`
لـ `MINI_APP_ALLOWED_ORIGINS`.

اختبارات الـ Mini App:

```bash
python -m pytest -q tests/test_miniapp_initdata.py tests/test_miniapp_api.py \
    tests/test_miniapp_features.py tests/test_miniapp_ratelimit.py \
    tests/test_miniapp_integration.py tests/test_miniapp_config.py
```

## 12. القيد غير المحلول: اسم مضيف مرتبط بالجلسة

الـ runtime بتاع OpenHands **مؤقّت**: اسم المضيف (الـ work host) مرتبط بالجلسة وممكن يتغيّر عند
إعادة تهيئة الـ sandbox ⇒ الرابط الحالي **مش رابط إنتاج دائم** (راجع OHB2-04 §8/§9).

## 13. اللي فاضل لمهام OHB2 اللاحقة

- جلسات **ثابتة عبر إعادة التشغيل** (المخزن الحالي في الذاكرة ⇒ أي restart بيلغي الجلسات).
- ميزات لسه مش معروضة في الـ Mini App: الملفات، التكلفة، تصدير الشات (موجودة في البوت، ومخفية
  بـ `features.is_hidden`)، ونسخ الرد الكامل.
- تفعيل `MINI_APP_ENABLED` في الإنتاج + تحديث `/app` يشاور على الواجهة الفعلية.
- معالجة الرابط الثابت (القسم 12).
