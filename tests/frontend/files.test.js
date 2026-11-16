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

// =============================================== تنقّل المجلدات (OHB2-PLAN-13-WS-01)
const PATHS = ["src/main.py", "src/util/helper.js", "notes.txt", ".github/workflows/ci.yml"];

test("buildTree: يبني هرمية من مسارات نسبية (مجلدات/ملفات)", () => {
  const t = FILES.buildTree(PATHS);
  const root = FILES.entryRows(t).map((r) => r.type + ":" + r.name);
  assert.deepEqual(root, ["folder:.github", "folder:src", "file:notes.txt"]);
  const src = FILES.entryRows(FILES.resolveNode(t, "src")).map((r) => r.type + ":" + r.name);
  assert.deepEqual(src, ["folder:util", "file:main.py"]);
});

test("buildTree: يتجاهل المقاطع الفارغة/النقطية (fail-closed)", () => {
  const t = FILES.buildTree(["a//b.py", "a/../x.py", "", "good.txt", "a/./y.py"]);
  const root = FILES.entryRows(t).map((r) => r.type + ":" + r.name);
  assert.deepEqual(root, ["file:good.txt"]);
});

test("resolveNode: الجذر للمسار الفاضي، null لمسار مش مجلد", () => {
  const t = FILES.buildTree(PATHS);
  assert.ok(FILES.resolveNode(t, ""));
  assert.ok(FILES.resolveNode(t, "src/util"));
  assert.equal(FILES.resolveNode(t, "src/main.py"), null, "الملف مش مجلد");
  assert.equal(FILES.resolveNode(t, "nope"), null);
});

test("hasFiles: false للعقدة الفاضية/غير الموجودة", () => {
  const t = FILES.buildTree(PATHS);
  assert.equal(FILES.hasFiles(FILES.resolveNode(t, "src")), true);
  assert.equal(FILES.hasFiles(FILES.resolveNode(t, "nope")), false);
  assert.equal(FILES.hasFiles(null), false);
});

test("parentPath: لأعلى أو null في الجذر", () => {
  assert.equal(FILES.parentPath("src/util"), "src");
  assert.equal(FILES.parentPath("src"), "");
  assert.equal(FILES.parentPath(""), null);
});

test("childPath: يبني مسار فرعي نسبةً للمجلد الحالي", () => {
  assert.equal(FILES.childPath("", "src"), "src");
  assert.equal(FILES.childPath("src", "util"), "src/util");
});

test("breadcrumbs: من الرئيسية لآخر مقطع، وكل عنصر فيه مساره", () => {
  assert.deepEqual(FILES.breadcrumbs("").map((c) => c.label), ["الرئيسية"]);
  assert.deepEqual(FILES.breadcrumbs("src/util").map((c) => c.label), ["الرئيسية", "src", "util"]);
  assert.deepEqual(FILES.breadcrumbs("src/util").map((c) => c.path), ["", "src", "src/util"]);
});

test("safeDir: يقبل مجلد معروف فقط ويرفض الملف/غير الموجود (fail-closed)", () => {
  const t = FILES.buildTree(PATHS);
  assert.equal(FILES.safeDir("", t), "");
  assert.equal(FILES.safeDir("src", t), "src");
  assert.equal(FILES.safeDir("src/util", t), "src/util");
  assert.equal(FILES.safeDir("src/main.py", t), null, "ملف مرفوض كمجلد");
  assert.equal(FILES.safeDir("nope", t), null);
  assert.equal(FILES.safeDir("../../etc", t), null);
  assert.equal(FILES.safeDir(null, t), "");
  assert.equal(FILES.safeDir(123, t), null);
});

test("readDir/writeDir: حفظ/استرجاع/مسح لكل شات (fail-safe لو التخزين راح)", () => {
  const m = new Map();
  const store = {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
  };
  assert.equal(FILES.readDir(store, "c1"), "");
  FILES.writeDir(store, "c1", "src/util");
  assert.equal(FILES.readDir(store, "c1"), "src/util");
  assert.equal(FILES.readDir(store, "c2"), "", "كل شات ليه مفتاح مستقل");
  FILES.writeDir(store, "c1", "");
  assert.equal(FILES.readDir(store, "c1"), "", "المسح يرجّع الجذر");
  // تخزين بيرمي (مثلاً وضع خاص/مقفول) ⇒ مايكسرش (fail-open للعرض فقط).
  const bad = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); } };
  assert.equal(FILES.readDir(bad, "c1"), "");
  FILES.writeDir(bad, "c1", "src");
  assert.equal(FILES.readDir(null, "c1"), "");
});
