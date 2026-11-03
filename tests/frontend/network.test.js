/* OHB2-N10-05 — اختبارات انحدار شبكة الـ Mini App (شبكة ضعيفة/فشل عابر).
 *
 * بتشتغل بـ Node المدمج: `node --test tests/frontend/network.test.js`
 * (من غير npm — مفيش أي اعتماد خارجي).
 *
 * بتشغّل **نفس** `bot/web/static/app.js` جوه بيئة DOM/شبكة مصغّرة (dom_stub.js)،
 * وبتتحقّق من السلوك المُلاحَظ عند: فشل الإقلاع (offline)، وردّ 429/5xx، ونجاح
 * بعد فشل عابر. الهدف: تأكيد إن الواجهة بتتعامل بأمان مع الشبكة الضعيفة (مفيش
 * انهيار، رسالة عربي واضحة، وإعادة محاولة عند الطلب).
 *
 * ملاحظة: بنسجّل المسارات **قبل** `loadApp` لأن `app.js` بيبدأ الإقلاع فورًا عند
 * التحميل (`start()`)، فلو سجّلنا المسارات بعده أول طلب هياخد الرد الافتراضي.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadApp, FakeFetch } = require("./dom_stub.js");

const flush = async (n = 16) => { for (let i = 0; i < n; i++) { await new Promise((r) => setImmediate(r)); } };

function bootResponse() {
  return {
    status: 200,
    data: {
      user: { display_name: "مستخدم" },
      settings: { notifications_enabled: true },
      features: { watches: true },
      inbox: { unread_count: 0 },
    },
  };
}

// بيجهّز بيئة: مسارات مسجّلة قبل الإقلاع، ثم ننتظر الـ microtasks.
async function boot(fake) {
  const env = loadApp({ fetch: fake });
  await flush();
  return env;
}

// ==================================================================== offline
test("N1: فشل الإقلاع (offline) يعرض حالة خطأ برسالة واضحة ولا ينهار", async () => {
  const fake = new FakeFetch();
  fake.route("/auth", () => { throw new Error("network"); });
  fake.route("/app/bootstrap", () => { throw new Error("network"); });
  const env = await boot(fake);
  env.runTimers();      // تشغيل إعادة المحاولة (700ms) — تفشل هي كمان
  await flush();

  const { doc } = env;
  assert.equal(doc.getElementById("state-error").hidden, false, "لازم تظهر حالة الخطأ");
  assert.equal(doc.getElementById("state-ready").hidden, true, "مافيش حالة جاهزة");
  const msg = doc.getElementById("error-msg").textContent;
  assert.ok(msg && msg.length > 0, "لازم رسالة خطأ مرئية");
  assert.ok(msg.includes("مش قادر") || msg.includes("الاتصال"), "رسالة الشبكة العربية");
});

// ==================================================================== 429 / 5xx
test("N2: رد 429 على الإقلاع يعرض رسالة rate limit", async () => {
  const fake = new FakeFetch();
  fake.route("/auth", () => ({ status: 429, ok: false, data: {} }));
  fake.route("/app/bootstrap", () => bootResponse());
  const env = await boot(fake);

  const { doc } = env;
  assert.equal(doc.getElementById("state-error").hidden, false);
  assert.equal(doc.getElementById("error-msg").textContent, "طلبات كتير، استنى شوية وجرّب تاني.");
});

test("N3: رد 5xx على الإقلاع يعرض رسالة خدمة غير متاحة", async () => {
  const fake = new FakeFetch();
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => ({ status: 503, ok: false, data: {} }));
  const env = await boot(fake);

  const { doc } = env;
  assert.equal(doc.getElementById("state-error").hidden, false);
  assert.equal(doc.getElementById("error-msg").textContent, "الخدمة مش متاحة دلوقتي، جرّب تاني.");
});

// ==================================================================== recovery
test("N4: الإقلاع ينجح بعد فشل عابر واحد (إعادة محاولة تلقائية)", async () => {
  const fake = new FakeFetch();
  let attempts = 0;
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => {
    attempts += 1;
    if (attempts === 1) { throw new Error("network"); }  // فشل عابر ⇒ withRetry
    return bootResponse();
  });
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [], has_more: false } }));
  const env = await boot(fake);
  env.runTimers();      // تشغيل إعادة المحاولة (700ms) ⇒ تنجح
  await flush();

  const { doc } = env;
  assert.ok(attempts >= 2, "لازم إعادة محاولة واحدة على الأقل");
  assert.equal(doc.getElementById("state-ready").hidden, false, "الوصول للحالة الجاهزة بعد التعافي");
});

// ==================================================================== retry button
test("N5: زر إعادة المحاولة يعيد المحاولة ويصل للحالة الجاهزة", async () => {
  const fake = new FakeFetch();
  let ok = false;
  fake.route("/auth", () => (ok ? { status: 200, data: { ok: true } } : { status: 503, ok: false, data: {} }));
  fake.route("/app/bootstrap", () => bootResponse());
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [], has_more: false } }));
  const env = await boot(fake);
  assert.equal(env.doc.getElementById("state-error").hidden, false, "فشل أول مرة");

  ok = true;
  env.doc.getElementById("retry-btn").click();
  await flush();
  assert.equal(env.doc.getElementById("state-ready").hidden, false, "نجاح بعد إعادة المحاولة اليدوية");
});

// ==================================================================== weak network: late data
test("N6: الواجهة تتحمّل ردًّا متأخّرًا (شبكة بطيئة) بدون انهيار", async () => {
  const fake = new FakeFetch({ deferred: true });
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => bootResponse());
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [], has_more: false } }));
  const env = loadApp({ fetch: fake });
  const { doc } = env;
  await flush();
  assert.equal(doc.getElementById("state-loading").hidden, false, "حالة تحميل أثناء انتظار الشبكة");
  for (let i = 0; i < 30; i++) {
    const pend = fake.pending();
    if (!pend.length) { break; }
    for (const c of pend) {
      if (c.path === "/auth") { c.resolve({ status: 200, data: { ok: true } }); }
      else if (c.path === "/app/bootstrap") { c.resolve(bootResponse()); }
      else if (c.path.startsWith("/conversations")) { c.resolve({ status: 200, data: { items: [], has_more: false } }); }
      else { c.resolve({ status: 200, data: {} }); }
    }
    await flush();
  }
  assert.equal(doc.getElementById("state-ready").hidden, false, "الوصول للحالة الجاهزة بعد وصول الردود");
});

// ==================================================================== no crash on non-JSON
test("N7: رد غير JSON لا ينهار الواجهة (يُعامَل كخطأ مضبوط)", async () => {
  const fake = new FakeFetch();
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => ({ status: 200, data: undefined }));  // json() ⇒ {}
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [], has_more: false } }));
  const env = await boot(fake);

  const { doc } = env;
  const ready = doc.getElementById("state-ready").hidden === false;
  const errored = doc.getElementById("state-error").hidden === false;
  assert.ok(ready || errored, "لازم نهاية مضبوطة (جاهز أو خطأ) بدون انهيار");
});
