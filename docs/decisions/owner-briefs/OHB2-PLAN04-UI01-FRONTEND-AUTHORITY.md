# OHB2-PLAN04-UI01 — سلطة الواجهة الأمامية (Frontend Authority) + اقتراح إزالة scaffold

> **النوع:** مذكّرة تحليلية (evidence-backed) — **مش** قرار مالك ولا تعديل على سجلّ القرارات.
> **الغرض:** توثيق أي واجهة أمامية هي **السلطة الفعلية**، وتوضيح دور كل مصدر واجهة
> مُحتفَظ به، وتقديم **اقتراح إزالة** مدعوم بالأدلة لسقالة React/Vite الجذرية **بدون
> حذفها** (الحذف خارج النطاق المصرّح به في Plan 04).
> **التاريخ:** 2026-11-14 · **المهمة:** `OHB2-PLAN04-UI01-FRONTEND-AUTHORITY`.

## 1. الخلاصة (القرار المؤصَّل)

الواجهة الأمامية **السلطة الفعلية** هي الواجهة **الخام (vanilla JS/HTML/CSS)** تحت
`bot/web/static/`، واللي بيتقدّمها تطبيق **Starlette** في **نفس عملية البوت الواحدة**
(`bot/web/app.py`). أما scaffold **React/Vite** الجذري (`/src`, `/vite.config.ts`,
`/package.json`, `index.html`, `tsconfig.json`, `metadata.json`, القفلان `bun.lock`/
`package-lock.json`) فهو **سقالة مستوردة غير مستخدمة** (AI-Studio import) **لا تمثّل
المنتج ولا تُبنى في أي مسار تشغيل/نشر/CI**، والتخطيط المعتمد يمنع إدخال React من غير
دليل مقيس (`docs/plan-openhandBot-2.md` §4.2).

## 2. الأدلة (source-backed)

### 2.1 الواجهة الفعلية = `bot/web/static/`
- `bot/web/app.py`:
  - `STATIC_DIR = Path(__file__).resolve().parent / "static"`، `INDEX_FILE = STATIC_DIR / "index.html"`.
  - مسارات: `Route("/", self.index)`, `Route("/mini/", self.index)`,
    `Route("/mini/{path:path}", self.static_file)` — كلها بتقدّم ملفات `bot/web/static/`
    بنوع MIME صريح (`_MIME_TYPES`) ورؤوس أمنية (`_STATIC_CSP`).
- `bot/web/static/index.html` يحمّل الوحدات بالترتيب:
  `jobs.js → ops.js → inbox.js → files.js → cost.js → copy.js → export.js → app.js`
  (كلها `defer`، من نفس الأصل `/mini/…`). و`app.js` بيفشل صريحًا لو أي وحدة مش محمّلة
  (`throw new Error("RecovoX مش محمّل")`).
- حجم/تغطية: ~2440 سطر (app.js 1472 + الوحدات) و**250** اختبار Node (`tests/frontend/*.test.js`).

### 2.2 سقالة React/Vite غير مستخدمة
- `src/App.tsx` = مكوّن **فاضي** (`return <div></div>;`)، و`src/main.tsx` بيعمل
  `createRoot(document.getElementById('root'))`. مفيش أي منطق منتج.
- `index.html` الجذري عنوانه «OpenHandBot» لكن وصفه `"Imported TM-AEM/OpenHandBot
  repository workspace."` و`metadata.json` `"Imported … workspace."` ⇒ **استيراد مساحة
  عمل AI Studio**، مش واجهة منتج.
- `package.json` اسمه `"react-example"` وسكربتاته `dev/build/preview/clean/lint` (Vite/tsc)
  — **مفيش** أي سكربت مرتبط بالبوت/الـ Mini App.
- **صفر مراجع** للسقالة في كود التشغيل أو CI: البحث الشامل
  (`git grep -e vite -e react -e App.tsx -e main.tsx -e bun.lock -e package-lock`) لا يرجّع
  أي مرجع فعلي في `bot/`, `automation/`, `main.py`, `tests/`, `.github/workflows/ci.yml`
  (المطابقات الوحيدة كانت كلمات إنجليزية داخل نصوص عربية مثل «reactivate»).
- `.github/workflows/ci.yml` **مفيهوش** أي خطوة `npm ci`/`vite build`/`tsc`؛ خطوة الواجهة
  الوحيدة هي `node --test tests/frontend/*.test.js` (بدون `npm install`، بلا تبعيات).
- `start.sh` (نقطة التشغيل الرسمية) بتشغّل `main.py` بس (Python) — **مفيش** أي خطوة Node/build.
- `docs/plan-openhandBot-2.md` §4.2: «Default to plain TypeScript/JavaScript, semantic HTML,
  and small CSS. **Do not introduce React, Next.js, a component framework … without measured
  evidence that it is needed.**» ⇒ السقالة **مخالفة للتخطيط المعتمد** لو اعتُبرت المنتج.

### 2.3 تصنيف السقالة
حسب خيارات المهمة الخمسة: السقالة هي **(5) غير مستخدمة وغير مرتبطة بالـ Mini App الحيّ**،
مع كونها أصلًا **(2) سقالة مهجورة/تجريبية** مستوردة. **ليست** واجهة منتج ولا تبعية بناء
ولا مرجع اختبار/CI فعلي.

## 3. دور كل مصدر واجهة مُحتفَظ به

| المصدر | الدور | مسار التحقّق |
| --- | --- | --- |
| `bot/web/static/index.html` | هيكل الصفحة (RTL عربي) + تحميل الوحدات + SDK تيليجرام | `tests/test_miniapp_api.py` (static/index/SDK)، `tests/frontend/a11y.test.js` |
| `bot/web/static/app.js` | منطق العرض/التنقّل/الطلبات (view layer) | `tests/frontend/*.test.js` (stale/detail/inbox/jobs/delete/network…) |
| `bot/web/static/ops.js` | دورة حياة معرّف العملية (idempotency) | `tests/frontend/ops.test.js` |
| `bot/web/static/inbox.js` | منطق صندوق الإشعارات | `tests/frontend/inbox*.test.js` |
| `bot/web/static/jobs.js` | عرض/إدارة طلبات البدء | `tests/frontend/jobs*.test.js` |
| `bot/web/static/files.js` | عرض الملفات + dedupe + رسائل الأخطاء | `tests/frontend/files*.test.js` |
| `bot/web/static/cost.js` | عرض التكلفة/الاستهلاك | `tests/frontend/cost.test.js` |
| `bot/web/static/copy.js` | نسخ الرد الكامل (بلا نجاح كاذب) | `tests/frontend/copy.test.js` |
| `bot/web/static/export.js` | اسم تنزيل آمن + رسائل أخطاء التصدير | `tests/frontend/export.test.js` |
| `bot/web/static/styles.css` | التنسيق (RTL، أهداف لمس، تركيز) | `tests/frontend/a11y.test.js` |
| `/src/*`, `/vite.config.ts`, `/package.json`, `/index.html`, `/tsconfig.json`, `/metadata.json`, `/bun.lock`, `/package-lock.json` | **سقالة React/Vite مستوردة غير مستخدمة** — دور: لا شيء في المنتج | لا يوجد (صفر مراجع) |

## 4. اقتراح إزالة السقالة (Removal Proposal) — **لم تُنفَّذ**

> **تأكيد صريح:** لم يتم حذف أي ملف من السقالة ولا قفلها في هذه المهمة. الحذف يتطلّب
> موافقة مالك صريحة (خارج نطاق Plan 04).

**المقترح:** إزالة الملفات التالية في تغيير مستقل مُراجَع، بعد موافقة المالك:
`src/` (App.tsx, main.tsx, index.css)، `index.html`، `vite.config.ts`، `tsconfig.json`،
`metadata.json`، `package.json`، `bun.lock`، `package-lock.json`.

**المبرّر:** صفر مراجع في كود/CI/تشغيل، سقالة فاضية، وتخالف التخطيط المعتمد (§4.2).
إزالتها تُلغي غموض «أي واجهة هي المنتج» وتقلّل سطح التبعية/الالتباس.

**المخاطر/الاحتياط:**
- **حذف `package.json`/الأقفال** مايأثّرش على أي مسار تشغيل/نشر (مفيش `npm` في CI أو `start.sh`).
- **`index.html` الجذري** غير مُستخدَم (الـ Mini App بتستخدم `bot/web/static/index.html`).
- الإزالة **قابلة للعكس** عبر Git لو حصلت.
- لو المالك عايز يبقيها كمرجع، البديل: نقلها لمجلد `docs/`/فرع أرشيف + تعليق واضح، أو
  إضافتها إلى `.gitignore` — أيًّا كان، **مش** جزء من هذه المهمة.

## 5. التوصية

1. اعتماد الواجهة الخام (`bot/web/static/`) رسميًا كواجهة المنتج (موثّقة في `docs/MINI_APP.md`).
2. قرار مالك على **إزالة** سقالة React/Vite (بند §4) — منفصل عن Plan 04.
3. **مفيش** إدخال React/إطار واجهة من غير دليل مقيس (متّسق مع §4.2 المعتمد).
