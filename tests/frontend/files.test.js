/* OHB2-09-02 — اختبارات منطق عرض الملفات في الواجهة.
 *
 * بتشتغل بـ Node المدمج: `node --test tests/frontend/`
 * بتختبر **نفس** الوحدة (bot/web/static/files.js) اللي app.js بيستعملها.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const FILES = require("../../bot/web/static/files.js");

test("contentStatusLabel: known statuses -> Arabic, unknown -> fallback", () => {
  assert.equal(FILES.contentStatusLabel("ok"), "");
  assert.equal(FILES.contentStatusLabel("binary"), "محتوى ثنائي — مش قابل للعرض.");
  assert.equal(FILES.contentStatusLabel("not_utf8"), "ترميز الملف مش UTF-8.");
  assert.equal(FILES.contentStatusLabel("too_large"), "الملف كبير أوي للعرض.");
  assert.equal(FILES.contentStatusLabel("weird"), "حالة ملف غير معروفة.");
});

test("errorLabel: maps stable error codes, falls back safely", () => {
  assert.equal(FILES.errorLabel("unauthorized"), "مش مسموح لك بالوصول لملفات الشات ده.");
  assert.equal(FILES.errorLabel("too_large"), "الملف كبير أوي للعرض.");
  assert.equal(FILES.errorLabel("upstream_error"), "تعذّر الوصول لملفات الشات دلوقتي، جرّب تاني.");
  assert.equal(FILES.errorLabel("nope", "مخصص"), "مخصص");
  assert.equal(FILES.errorLabel("nope"), "حصل خطأ غير متوقع، جرّب تاني.");
});

test("previewText: ok shows text, empty shows placeholder", () => {
  assert.equal(FILES.previewText({ status: "ok", text: "مرحبا" }), "مرحبا");
  assert.equal(FILES.previewText({ status: "ok", text: "" }), "الملف فاضي.");
  assert.equal(FILES.previewText({ status: "ok" }), "الملف فاضي.");
});

test("previewText: non-ok statuses show the status message not the raw text", () => {
  assert.equal(FILES.previewText({ status: "binary", text: "x" }), "محتوى ثنائي — مش قابل للعرض.");
  assert.equal(FILES.previewText({ status: "not_utf8", text: "x" }), "ترميز الملف مش UTF-8.");
  assert.equal(FILES.previewText(null), "مفيش محتوى.");
  assert.equal(FILES.previewText({}), "الملف فاضي.");
});

test("isTruncated: only explicit true", () => {
  assert.equal(FILES.isTruncated({ truncated: true }), true);
  assert.equal(FILES.isTruncated({ truncated: false }), false);
  assert.equal(FILES.isTruncated({}), false);
  assert.equal(FILES.isTruncated(null), false);
});

test("createDeduper: concurrent calls share one promise (no duplicate request)", async () => {
  const d = FILES.createDeduper();
  let calls = 0;
  let resolve;
  const fn = () => { calls += 1; return new Promise((r) => { resolve = r; }); };
  const p1 = d.run("k", fn);
  const p2 = d.run("k", fn);
  assert.equal(p1, p2); // نفس الوعد بالحرف
  assert.equal(calls, 1);
  assert.equal(d.active("k"), true);
  resolve("ok");
  assert.equal(await p1, "ok");
  assert.equal(await p2, "ok");
  // بعد الخلاص: المفتاح اتحرّر ⇒ طلب جديد يشتغل من جديد.
  await Promise.resolve();
  assert.equal(d.active("k"), false);
  const p3 = d.run("k", () => { calls += 1; return Promise.resolve("second"); });
  assert.equal(await p3, "second");
  assert.equal(calls, 2);
});

test("createDeduper: clears the key on rejection too", async () => {
  const d = FILES.createDeduper();
  await assert.rejects(d.run("k", () => Promise.reject(new Error("boom"))));
  assert.equal(d.active("k"), false);
});

test("createDeduper: different keys run independently", async () => {
  const d = FILES.createDeduper();
  let calls = 0;
  const a = d.run("a", () => { calls += 1; return Promise.resolve(1); });
  const b = d.run("b", () => { calls += 1; return Promise.resolve(2); });
  assert.equal(await a, 1);
  assert.equal(await b, 2);
  assert.equal(calls, 2);
});
