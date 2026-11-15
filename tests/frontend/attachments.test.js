/* OHB2-MT-2 — اختبارات منطق تنزيل المرفقات (attachments.js).
 *
 * `node --test tests/frontend/attachments.test.js` — بتختبر **نفس** الوحدة اللي app.js
 * بيستعملها. مفيش DOM ومفيش شبكة.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const ATTACH = require("../../bot/web/static/attachments.js");

test("اسم ملف آمن من هيدر Content-Disposition (مقتبس/بدون اقتباس)", () => {
  assert.equal(ATTACH.filenameFromDisposition('attachment; filename="note.txt"'), "note.txt");
  assert.equal(ATTACH.filenameFromDisposition("attachment; filename=note.txt"), "note.txt");
});

test("هيدر غايب أو فاضي ⇒ الاسم الافتراضي", () => {
  assert.equal(ATTACH.filenameFromDisposition(null), ATTACH.DEFAULT_NAME);
  assert.equal(ATTACH.filenameFromDisposition(""), ATTACH.DEFAULT_NAME);
  assert.equal(ATTACH.filenameFromDisposition("attachment"), ATTACH.DEFAULT_NAME);
});

test("محاولة حقن مسار/محارف خطر في اسم الملف بتتنقّى", () => {
  const name = ATTACH.filenameFromDisposition(
    'attachment; filename="../../etc/passwd"\r\nX-Evil: 1'
  );
  assert.equal(name.includes(".."), false);
  assert.equal(name.includes("/"), false);
  assert.equal(name.includes("\r"), false);
  assert.equal(name.includes("\n"), false);
});

test("safeFilename بيرجّع الافتراضي للمدخل الفاضي أو النقطي", () => {
  assert.equal(ATTACH.safeFilename(""), ATTACH.DEFAULT_NAME);
  assert.equal(ATTACH.safeFilename("."), ATTACH.DEFAULT_NAME);
  assert.equal(ATTACH.safeFilename(".."), ATTACH.DEFAULT_NAME);
  assert.equal(ATTACH.safeFilename(null), ATTACH.DEFAULT_NAME);
  assert.equal(ATTACH.safeFilename("report.pdf"), "report.pdf");
});

test("humanSize بيقرأ الأحجام بشكل معقول", () => {
  assert.equal(ATTACH.humanSize(0), "0 B");
  assert.equal(ATTACH.humanSize(512), "512 B");
  assert.match(ATTACH.humanSize(2048), /KB/);
  assert.match(ATTACH.humanSize(5 * 1024 * 1024), /MB/);
  assert.equal(ATTACH.humanSize(-1), "");
  assert.equal(ATTACH.humanSize("x"), "");
});

test("remainingLabel للمهلة المتبقّية (بلا تمديد)", () => {
  assert.equal(ATTACH.remainingLabel(0), "");
  assert.equal(ATTACH.remainingLabel(-5), "");
  assert.equal(ATTACH.remainingLabel(30), "أقل من دقيقة");
  assert.equal(ATTACH.remainingLabel(120), "2 د");
});

test("listItems بتتجاهل الحقول الغريبة والمداخل غير الصالحة", () => {
  const out = ATTACH.listItems({
    items: [
      { item_id: "i1", display_name: "../../x.txt", size_bytes: "12", expires_in: "60", staging_token: "SECRET" },
      { item_id: "", display_name: "bad" },
      null,
      { display_name: "no-id" }
    ]
  });
  assert.equal(out.length, 1);
  assert.equal(out[0].item_id, "i1");
  assert.equal(out[0].display_name, "x.txt");
  assert.equal(out[0].size_bytes, 12);
  // مفيش تسريب رمز staging في المخرجات.
  assert.equal(JSON.stringify(out).includes("SECRET"), false);
});

test("listItems بترجّع قايمة فاضية لو الرد فاضي", () => {
  assert.deepEqual(ATTACH.listItems(null), []);
  assert.deepEqual(ATTACH.listItems({}), []);
  assert.deepEqual(ATTACH.listItems({ items: [] }), []);
});

test("رسائل الأخطاء عربي واضحة وتفرّق بين انتهاء الجلسة والمهلة", () => {
  assert.match(ATTACH.errorLabel("unauthenticated"), /الجلسة/);
  assert.match(ATTACH.errorLabel("expired"), /15 دقيقة/);
  assert.match(ATTACH.errorLabel("not_found"), /مش متاح/);
  assert.match(ATTACH.errorLabel("whatever", "رسالتي"), /رسالتي/);
});

test("نصوص UX صادقة: بتفرّق بين التنزيل المحلي والتسليم", () => {
  assert.match(ATTACH.TEXT.localNote, /محلي/);
  assert.match(ATTACH.TEXT.notDelivered, /مش معناه إن OpenHands استلمه/);
  // مفيش أي نص بيدّعي إن التسليم حصل.
  const all = Object.keys(ATTACH.TEXT).map((k) => ATTACH.TEXT[k]).join(" ");
  assert.equal(/اتسلّم|تم التسليم/.test(all), false);
});
