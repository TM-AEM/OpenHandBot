# Mini App (OHB2-05) — خلفية ASGI + مصادقة initData

> **النطاق:** ده **الأساس بس** للـ Mini App. مفيش أي ميزات بوت كاملة هنا لسه
> (الشاتات/البرومتات/الملفات جاية في مهام OHB2 لاحقة). راجع قسم «اللي فاضل» تحت.

## 1. نظرة عامة

الـ Mini App بيتقدّم من **نفس عملية البوت الواحدة** (OHB2-04 اختار Option A):

```
Telegram WebView ──HTTPS──▶ ingress (TLS) ──HTTP──▶ الحاوية:MINI_APP_PORT
                                                          │
                                        عملية asyncio واحدة:
                                        • long polling بتاع البوت (زي ما هو)
                                        • سيرفر Uvicorn/Starlette (task جنب البوت)
                                        • نفس كائن Database الواحد
```

- مفيش عملية تانية، مفيش worker تاني، مفيش اتصال SQLite تاني.
- الواجهة والـ API على **نفس الأصل** (same-origin) ⇒ كوكي جلسة `SameSite=Strict` بدون تعقيدات CORS.
- كل الردود JSON، والأخطاء بشكل موحّد `{"error": code, "message": ...}`.

## 2. التبعيات الجديدة

| الحزمة | الإصدار | ليه |
| --- | --- | --- |
| `starlette` | `0.41.3` | إطار ASGI صغير (راوتنج + responses) بدون أي إطار ثقيل |
| `uvicorn` | `0.34.0` | سيرفر ASGI قياسي، بيشتغل كـ task جوه event loop الموجود |

اتضافوا في `requirements.txt`. مقصود إننا **ما ضفناش FastAPI** — مش محتاجينه لأساس بسيط.

## 3. دمج السيرفر مع عملية البوت

- `bot/app.py::_wire_mini_app` بيربط خلفية الـ Mini App بدورة حياة البوت، **بس لما `MINI_APP_ENABLED=1`**.
- `bot/web/runner.py::web_server_lifespan`:
  - بيربط الـ socket بنفسه (`_bind_socket`) ويمرّره لـ Uvicorn. كده فشل الربط (منفذ مستخدم)
    يطلع `OSError` عادي ⇒ **التشغيل كله يفشل بوضوح** (fail-fast) بدل ما يكمل بحالة غير متسقة.
    (سبب اختيارنا ده: Uvicorn لما يفشل الربط بينادي `sys.exit(1)` جوه الـ event loop،
    وasyncio بيعيد رميه ويقتل العملية فجأة.)
  - بيعطّل `uvicorn.Server.capture_signals` وقت التشغيل المشترك، عشان **البوت** هو اللي
    يمسك SIGINT/SIGTERM ويعمل إغلاق نظيف (السيرفر بيتقفل عبر الـ lifespan).
- الترتيب في `post_init`: البوت بيعمل تعافيه ويشغّل الـ workers/المراقب **قبل** ما سيرفر الويب
  يبدأ. في `post_shutdown`: السيرفر يقف **قبل** ما البوت يقفل الموارد (`client`, `db`).
- حرس تكرار: إعادة تهيئة مكرّرة (`post_init` اتنادت مرتين) **ما بتبدأش سيرفر تاني**.

## 4. المسارات (API)

| المسار | الميثود | مصادقة | الوصف |
| --- | --- | --- | --- |
| `/health` | GET | لأ | فحص صحة. مفيش أي أسرار/إعدادات في الرد |
| `/api/v1/auth` | POST | لأ | يستقبل `{"initData": "..."}`، يتحقق منه، ويعمل كوكي جلسة |
| `/api/v1/auth/logout` | POST | كوكي | يلغي الجلسة ويمسح الكوكي |
| `/api/v1/app/bootstrap` | GET | كوكي | بيانات أولية للواجهة (اسم العرض + الإشعارات + الميتا) |
| `/api/v1/*` (غير معروف) | أي | — | `404` بشكل JSON موحّد |
| `/`, `/mini/`, `/mini/<asset>` | GET | لأ | الواجهة والأصول الثابتة |

### الأمان في الردود

- **مفيش أسرار** في أي رد: توكن البوت ومفتاح OpenHands بيتخزّنوا على السيرفر بس.
- `/api/v1/app/bootstrap` بيرجّع **اسم العرض بس** — مش معرّف المستخدم ولا أي حقل داخلي.
- كل ردود الـ API بترجّع `Cache-Control: no-store` (مفيش كاش لبيانات خاصة).
- الأصول الثابتة (`/mini/*.css`, `*.js`) بتتكاش (`immutable`, سنة)؛ الـ HTML لأ (`no-store`).
- هيدرات أمان على كل الردود: `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`,
  و`Content-Security-Policy` (الواجهة بتسمح بس لـ `self` + `telegram.org`؛ الـ API `default-src 'none'`).
- حد حجم الطلب `16 KiB` (زيادة ⇒ `413`).

## 5. تدفّق المصادقة (initData)

بيتّبع [إجراء تيليجرام الرسمي](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app):

1. الواجهة تاخد `Telegram.WebApp.initData` الخام (**مش** `initDataUnsafe`) وتبعتها في `POST /api/v1/auth`.
2. السيرفر (`bot/web/initdata.py`):
   - يشتق المفتاح السري: `secret = HMAC_SHA256("WebAppData", bot_token)`.
   - يبني `data_check_string` (كل الحقول ما عدا `hash`/`signature`، مرتبة أبجديًا، مفصولة بـ `\n`).
   - يقارن `HMAC_SHA256(secret, data_check_string)` مع `hash` بمقارنة **ثابتة الزمن** (`hmac.compare_digest`).
   - يتحقق من `auth_date`: يرفض المستقبلي (بهامش 30 ثانية) ويرفض الأقدم من `MINI_APP_INITDATA_MAX_AGE`.
   - **بعد** نجاح التوقيع بس بيقرأ `id` المستخدم من حقل `user`.
3. لو التحقق نجح **و** الـ id ∈ `ALLOWED_TELEGRAM_ID` ⇒ يتعمل توكن جلسة عشوائي (opaque)
   ويتحطّ في كوكي `ohb_session` (`HttpOnly; Secure; SameSite=Strict; Path=/`).
4. الطلبات اللاحقة بتيجي بالكوكي؛ السيرفر يدوّر على الجلسة في **مخزن في الذاكرة** (TTL).
5. `logout` بيلغي الجلسة ويمسح الكوكي.

### ضمانات أمنية

- مفيش ثقة في أي `id` جاي من الجافاسكريبت — بيُقرأ بعد التوقيع، وبيتحقق من `ALLOWED_TELEGRAM_ID` على السيرفر.
- مفيش بيانات مصادقة في `localStorage`؛ الجلسة كوكي HTTP-only فقط.
- مفيش أسرار أو توقيعات في الكوكي نفسه (توكن عشوائي، والسيرفر هو اللي يعرف معناه).
- مستخدم غير مسموح ⇒ `403` (ومفيش أي تفاصيل حساسة في الرسالة).

## 6. متغيرات البيئة المطلوبة

راجع الجدول في `README.md` و`.env.example`. الجديد:

```
MINI_APP_URL=                 # رابط عام https (مطلوب لما MINI_APP_ENABLED=1)
MINI_APP_ENABLED=0            # 1 لتشغيل خلفية ASGI جوه عملية البوت
MINI_APP_PORT=12000           # منفذ الاستماع داخل الحاوية
MINI_APP_INITDATA_MAX_AGE=300 # أقصى عمر initData بالثواني
MINI_APP_SESSION_TTL=3600     # عمر الجلسة بالثواني
MINI_APP_COOKIE_SECURE=1      # 1 إنتاج، 0 تطوير محلي على http فقط
```

## 7. التطوير المحلي والاختبار

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # املأ القيم، وحط MINI_APP_ENABLED=1 للتجربة المحلية
python main.py
```

للتجربة المحلية على http: خلي `MINI_APP_COOKIE_SECURE=0` (وإلا المتصفح مش هيقبل الكوكي على http).
`MINI_APP_URL` لازم يفضل رابط https عام حتى في التطوير (ده نفس الرابط اللي تيليجرام بيفتحه).

اختبارات الـ Mini App:

```bash
python -m pytest -q tests/test_miniapp_initdata.py tests/test_miniapp_api.py \
    tests/test_miniapp_integration.py tests/test_miniapp_config.py
```

المساعد `tests/_miniapp_helpers.py` بيولّد `initData` موقّع صح بنفس خوارزمية تيليجرام، فالاختبارات
بتختبر الكود الحقيقي مش نسخة مزيّفة.

## 8. ضبط رابط HTTPS العام

- الرابط اللي بيدخل `MINI_APP_URL` هو رابط الـ ingress العام اللي بيوصل لـ `MINI_APP_PORT` جوه الحاوية.
  في بيئة OpenHands runtime ده زي `https://work-1-<id>.prod-runtime.all-hands.dev/` (منفذ محلي 12000).
- الـ ingress بيعمل TLS termination بشهادة `Let's Encrypt` عامة (مطلوبة لـ Telegram WebView)،
  والسيرفر بيتكلم HTTP محلي بس.
- **مهم:** `MINI_APP_URL` لازم يكون رابط عام (مش loopback) — فيه تحقق في `bot/config.py` بيمنع غير كده.

## 9. القيد غير المحلول: اسم مضيف مرتبط بالجلسة

الـ runtime بتاع OpenHands **مؤقّت**: اسم المضيف (الـ work host) مرتبط بالجلسة وممكن يتغيّر عند
إعادة تهيئة الـ sandbox. يعني الرابط الحالي **مش رابط إنتاج دائم**. لو محتاجين رابط ثابت، ده
لسه **غير محلول** (راجع OHB2-04 §8/§9) — الحلول المحتملة: تثبيت runtime/رابط، أو واجهة ثابتة على
مستضيف مجاني (GitHub Pages) مع الـ API على الـ runtime.

## 10. اللي فاضل لمهام OHB2 اللاحقة

- ميزات البوت الكاملة جوه الـ Mini App (الشاتات، فتح شات، إرسال برومت، شات جديد، الملفات…).
- جلسات **ثابتة عبر إعادة التشغيل** (المخزن الحالي في الذاكرة ⇒ أي restart بيلغي الجلسات).
- Rate limiting أوضح للـ API، وربما CSRF token لعمليات الكتابة.
- تفعيل `MINI_APP_ENABLED` في الإنتاج + تحديث `/app` يشاور على الواجهة الفعلية.
- معالجة الرابط الثابت (القسم 9).
