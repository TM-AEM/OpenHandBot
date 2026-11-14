/* OHB2-PHASE1B — اختبارات منطق تصدير الشات (export.js).
 *
 * `node --test tests/frontend/export.test.js` — بتختبر **نفس** الوحدة اللي app.js بيستعملها.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const EXPORT = require("../../bot/web/static/export.js");

test("اسم ملف آمن من هيدر Content-Disposition (صيغة مقتبسة)", () => {
  const h = 'attachment; filename="conversation-c1.zip"';
  assert.equal(EXPORT.filenameFromDisposition(h), "conversation-c1.zip");
});

test("اسم ملف آمن من هيدر بدون اقتباس", () => {
  const h = "attachment; filename=conversation-c1.zip";
  assert.equal(EXPORT.filenameFromDisposition(h), "conversation-c1.zip");
});

test("هيدر غايب أو فاضي ⇒ الاسم الافتراضي", () => {
  assert.equal(EXPORT.filenameFromDisposition(null), EXPORT.DEFAULT_NAME);
  assert.equal(EXPORT.filenameFromDisposition(""), EXPORT.DEFAULT_NAME);
  assert.equal(EXPORT.filenameFromDisposition("attachment"), EXPORT.DEFAULT_NAME);
});

test("محاولة حقن مسار/محارف خطر في اسم الملف بتتنقّى", () => {
  const h = 'attachment; filename="../../etc/passwd"\r\nX-Evil: 1';
  const name = EXPORT.filenameFromDisposition(h);
  assert.equal(name.includes(".."), false);
  assert.equal(name.includes("/"), false);
  assert.equal(name.includes("\r"), false);
  assert.equal(name.includes("\n"), false);
});

test("safeFilename بيرجّع الافتراضي للمدخل الفاضي أو النقطي", () => {
  assert.equal(EXPORT.safeFilename(""), EXPORT.DEFAULT_NAME);
  assert.equal(EXPORT.safeFilename("."), EXPORT.DEFAULT_NAME);
  assert.equal(EXPORT.safeFilename(".."), EXPORT.DEFAULT_NAME);
  assert.equal(EXPORT.safeFilename(null), EXPORT.DEFAULT_NAME);
  assert.equal(EXPORT.safeFilename("report.zip"), "report.zip");
});

test("رسائل أخطاء التصدير عربي واضحة وثابتة", () => {
  assert.match(EXPORT.errorLabel("too_large"), /كبير/);
  assert.match(EXPORT.errorLabel("not_found"), /مش موجود/);
  assert.match(EXPORT.errorLabel("unauthorized", "x"), /x/);  // غير معروف ⇒ fallback
  assert.match(EXPORT.errorLabel("whatever", "رسالتي"), /رسالتي/);
});
