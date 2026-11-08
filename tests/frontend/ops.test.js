/* OHB2-07-FIX — اختبارات منطق دورة حياة معرّف العملية في الواجهة.
 *
 * بتشتغل بـ Node المدمج: `node --test tests/frontend/`
 * بتختبر **نفس** الوحدة (bot/web/static/ops.js) اللي app.js بيستعملها — مش نسخة مكرّرة.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const OPS = require("../../bot/web/static/ops.js");

const STATIC = path.resolve(__dirname, "../../bot/web/static");

// عدّاد معرّفات حتمي عشان نتأكد إن كل معرّف جديد فعلاً مختلف.
function countingRefFn() {
  let n = 0;
  return function () { n += 1; return "ref-" + n; };
}

// مفاتيح الهوية زي ما الواجهة بتبنيها.
function promptKey(conversationId, text) { return OPS.identityKey([conversationId, text]); }
function createKey(repo, text) { return OPS.identityKey([repo, text]); }

test("1) same prompt twice as two completed operations -> two distinct refs", () => {
  const mgr = OPS.createRefManager(countingRefFn());
  const key = promptKey("c1", "أكمل");
  const r1 = mgr.acquire(key, "أكمل");
  mgr.resolve(r1, "accepted");            // العملية الأولى خلصت
  const r2 = mgr.acquire(key, "أكمل");    // نفس النص، نيّة جديدة
  assert.notEqual(r1, r2, "المعرّف الجديد لازم يختلف بعد النهاية");
});

test("2) retrying one pending operation reuses its original ref", () => {
  const mgr = OPS.createRefManager(countingRefFn());
  const key = promptKey("c1", "شغل");
  const r1 = mgr.acquire(key, "شغل");
  mgr.resolve(r1, "pending");
  const r2 = mgr.acquire(key, "شغل");     // إعادة محاولة/ضغط تاني
  assert.equal(r2, r1, "إعادة المحاولة لازم تعيد نفس المعرّف");
  assert.equal(mgr.ref(), r1);
  assert.equal(mgr.active(), true);
});

test("3) ambiguous operation retains its ref until explicitly resolved", () => {
  const mgr = OPS.createRefManager(countingRefFn());
  const key = promptKey("c1", "متابعة");
  const r1 = mgr.acquire(key, "متابعة");
  mgr.resolve(r1, "ambiguous");
  assert.equal(mgr.acquire(key, "متابعة"), r1, "غامضة ⇒ نفس المعرّف");
  assert.equal(mgr.active(), true, "غامضة ⇒ لسه نشطة");
  // لحد ما تتحسم كنهاية
  mgr.resolve(r1, "accepted");
  assert.notEqual(mgr.acquire(key, "متابعة"), r1, "بعد الحسم ⇒ معرّف جديد");
});

test("4) two creations, identical prompt, same repo, after separate terminals -> distinct", () => {
  const mgr = OPS.createRefManager(countingRefFn());
  const key = createKey("o/repoA", "ابدأ");
  const r1 = mgr.acquire(key, "ابدأ");
  mgr.resolve(r1, "accepted");
  const r2 = mgr.acquire(key, "ابدأ");
  assert.notEqual(r1, r2);
});

test("5) identical prompts in different repos -> distinct refs", () => {
  const mgr = OPS.createRefManager(countingRefFn());
  const r1 = mgr.acquire(createKey("o/repoA", "ابدأ"), "ابدأ");
  const r2 = mgr.acquire(createKey("o/repoB", "ابدأ"), "ابدأ");
  assert.notEqual(r1, r2, "مستودع مختلف ⇒ عملية مختلفة حتى بدون نهاية");
  assert.equal(mgr.payload(), "ابدأ");
});

test("6) double taps during one active operation do not create duplicate logical ops", () => {
  const mgr = OPS.createRefManager(countingRefFn());
  const key = promptKey("c1", "دوس مرتين");
  const r1 = mgr.acquire(key, "دوس مرتين");
  const r2 = mgr.acquire(key, "دوس مرتين");
  const r3 = mgr.acquire(key, "دوس مرتين");
  assert.equal(r1, r2);
  assert.equal(r2, r3);
});

test("7) a failed terminal operation does not suppress a later new operation", () => {
  const mgr = OPS.createRefManager(countingRefFn());
  const key = promptKey("c1", "جرّب");
  const r1 = mgr.acquire(key, "جرّب");
  mgr.resolve(r1, "failed");
  assert.equal(mgr.active(), false);
  const r2 = mgr.acquire(key, "جرّب");
  assert.notEqual(r1, r2, "الفشل النهائي مايلغيش عملية جديدة بنفس النص");
});

test("stale resolve for a superseded ref is ignored", () => {
  const mgr = OPS.createRefManager(countingRefFn());
  const key = promptKey("c1", "x");
  const r1 = mgr.acquire(key, "x");
  mgr.resolve(r1, "accepted");
  const r2 = mgr.acquire(key, "x");       // عملية أحدث
  mgr.resolve(r1, "pending");             // وصول متأخّر للعملية القديمة
  assert.equal(mgr.ref(), r2, "الحالة المتأخّرة مايجبش تغيّر العملية الحالية");
  assert.equal(mgr.active(), true);
});

test("identityKey separates repo/text and conversation/text boundaries", () => {
  assert.notEqual(OPS.identityKey(["a", "bc"]), OPS.identityKey(["ab", "c"]));
  assert.notEqual(OPS.identityKey(["r1", "t"]), OPS.identityKey(["r2", "t"]));
  assert.equal(OPS.identityKey(["r1", "t"]), OPS.identityKey(["r1", "t"]));
});

test("defaultNewRef is server-valid (charset + length)", () => {
  for (let i = 0; i < 50; i += 1) {
    const ref = OPS.defaultNewRef();
    assert.match(ref, /^[A-Za-z0-9_-]+$/);
    assert.ok(ref.length > 0 && ref.length <= 64);
  }
});

// --- wiring guards: الواجهة فعلاً بتستخدم نفس المنطق المشترك ---------------------

test("wiring: index.html loads ops.js before app.js", () => {
  const html = fs.readFileSync(path.join(STATIC, "index.html"), "utf8");
  const opsAt = html.indexOf("/mini/ops.js");
  const appAt = html.indexOf("/mini/app.js");
  assert.ok(opsAt !== -1, "ops.js لازم يكون محمّل");
  assert.ok(appAt !== -1, "app.js لازم يكون محمّل");
  assert.ok(opsAt < appAt, "ops.js لازم يتحمّل قبل app.js");
});

test("wiring: app.js uses the shared manager and dropped the old local state", () => {
  const js = fs.readFileSync(path.join(STATIC, "app.js"), "utf8");
  assert.ok(js.includes("OPS.createRefManager"), "app.js لازم يستعمل createRefManager");
  assert.ok(js.includes(".acquire("), "app.js لازم يستدعي acquire");
  assert.ok(js.includes("manager.resolve("), "app.js لازم يسجّل الحالة على المدير");
  // مايكونش فيه متغيّرات دورة الحياة القديمة اللي كانت بتلغى العمليات.
  assert.ok(!/\bcurrentRef\b/.test(js), "currentRef القديم لازم يختفي");
  assert.ok(!/\bcurrentText\b/.test(js), "currentText القديم لازم يختفي");
  assert.ok(!/\bcreateOpRef\b/.test(js), "createOpRef القديم لازم يختفي");
});

// OHB2-PHASE1D-F4: العملية الملغاة نهائية ⇒ أول إرسال جديد بنفس المفتاح ياخد معرّف
// جديد (وإلا معرّف ملغي كان بيسدّ نفس (مستودع+نص) للأبد).
test("discarded is terminal -> a new acquire after discard gets a fresh ref", () => {
  const mgr = OPS.createRefManager(countingRefFn());
  const key = createKey("o/r", "شات");
  const r1 = mgr.acquire(key, "شات");
  mgr.resolve(r1, "discarded");
  const r2 = mgr.acquire(key, "شات");
  assert.notEqual(r1, r2, "معرّف ملغي مايفضلش نشط");
});

test("a late pending for the discarded ref does not reactivate it", () => {
  const mgr = OPS.createRefManager(countingRefFn());
  const key = createKey("o/r", "شات");
  const r1 = mgr.acquire(key, "شات");
  mgr.resolve(r1, "discarded");
  mgr.resolve(r1, "pending");  // وصول متأخّر للعملية القديمة
  const r2 = mgr.acquire(key, "شات");
  assert.notEqual(r1, r2);
});
