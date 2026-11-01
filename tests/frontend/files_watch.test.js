/* OHB2-09-02 — اختبارات انحدار واجهة ملفات الشات.
 *
 * بتشتغل بـ Node المدمج: `node --test tests/frontend/files_watch.test.js`
 * بتشغّل **نفس** app.js + files.js جوه بيئة DOM/شبكة مصغّرة (dom_stub.js).
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadApp, descendants, FakeFetch } = require("./dom_stub.js");

const flush = async (n = 12) => { for (let i = 0; i < n; i++) { await new Promise((r) => setImmediate(r)); } };

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

async function mkEnv(opts) {
  opts = opts || {};
  const fake = new FakeFetch({ deferred: !!opts.deferred });
  const env = loadApp({ fetch: fake, telegram: opts.telegram });
  const { doc } = env;
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => bootResponse());
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/watches"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/notifications"), () => ({ status: 200, data: { page: 0, has_more: false, unread_count: 0, items: [] } }));
  if (!opts.deferred) { await flush(); }
  return env;
}

function filesSection(doc) {
  return descendants(doc.getElementById("view-detail")).find((n) => n.className === "files-section") || null;
}
function filesList(doc) {
  const sec = filesSection(doc);
  return sec ? descendants(sec).find((n) => n.tagName === "UL") : null;
}
function fileRows(list) { return list.children.filter((c) => c.className.split(" ").includes("row")); }
function findButtonByText(root, text) {
  return descendants(root).find((n) => n.tagName === "BUTTON" && n.textContent === text) || null;
}
function textOf(node) { return node ? node.textContent : null; }

// يفتح تفاصيل محادثة بملفات/معاينة قابلة للضبط.
const FILE_PREVIEW_MATCH = (c) => c.path === "/conversations/c1/file" || c.path.indexOf("/conversations/c1/file?") === 0;

async function openFiles(env, { files, preview } = {}) {
  const { doc, fetch } = env;
  fetch.route((c) => c.path === "/conversations/c1", () => ({ status: 200, data: { id: "c1", title: "T", watched: false } }));
  fetch.route((c) => c.path === "/conversations/c1/files", () => (files || { status: 200, data: { conversation_id: "c1", files: ["src/main.py", "notes.txt"] } }));
  fetch.route(FILE_PREVIEW_MATCH, () => (preview || { status: 200, data: { status: "ok", text: "print('hi')\n", truncated: false } }));
  doc.getElementById("tab-chats").click();
  await flush();
  // فتح أول شات من القايمة.
  fetch.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [{ id: "c1", title: "T", status: "running" }], has_more: false } }));
  doc.getElementById("chats-refresh").click();
  await flush();
  const chatList = doc.getElementById("chats-list");
  const row = chatList.children.find((c) => c.className.split(" ").includes("row"));
  if (row) { row.click(); await flush(); }
  return env;
}

test("يفتح التفاصيل ⇒ قسم الملفات يجيب القايمة من المسار المصادَق", async () => {
  const env = await mkEnv();
  await openFiles(env);
  const call = env.fetch.last((c) => c.path === "/conversations/c1/files");
  assert.ok(call, "لازم يكون فيه نداء لقايمة الملفات");
  const list = filesList(env.doc);
  assert.ok(list, "قسم الملفات لازم يظهر");
  assert.deepEqual(fileRows(list).map(textOf), ["src/main.py", "notes.txt"]);
});

test("الضغط على ملف يجيب المعاينة ويعرض النص", async () => {
  const env = await mkEnv();
  await openFiles(env);
  const list = filesList(env.doc);
  fileRows(list)[0].click();
  await flush();
  const call = env.fetch.last(FILE_PREVIEW_MATCH);
  assert.ok(call && call.url.indexOf("path=src%2Fmain.py") !== -1, "لازم يطلب المسار الصح");
  const pre = descendants(env.doc.getElementById("view-detail")).find((n) => n.className === "file-text");
  assert.equal(textOf(pre), "print('hi')\n");
});

test("المعاينة المقصوصة تعرض تنبيه", async () => {
  const env = await mkEnv();
  await openFiles(env, { preview: { status: 200, data: { status: "ok", text: "abc", truncated: true } } });
  fileRows(filesList(env.doc))[0].click();
  await flush();
  const hint = descendants(env.doc.getElementById("view-detail")).find((n) => n.className === "hint");
  assert.ok(hint && hint.textContent.indexOf("مقصوصة") !== -1, "لازم يبان تنبيه القصّ");
});

test("قايمة فاضية ⇒ 'مفيش ملفات.'", async () => {
  const env = await mkEnv();
  await openFiles(env, { files: { status: 200, data: { conversation_id: "c1", files: [] } } });
  const list = filesList(env.doc);
  assert.deepEqual(fileRows(list).length, 0);
  assert.ok(textOf(list.children[0]).indexOf("مفيش ملفات") !== -1);
});

test("خطأ التفويض في القايمة يعرض نص عربي مش تفاصيل خام", async () => {
  const env = await mkEnv();
  await openFiles(env, { files: { status: 403, data: { error: "unauthorized", message: "x" } } });
  const list = filesList(env.doc);
  assert.ok(textOf(list.children[0]).indexOf("مش مسموح") !== -1);
});

test("خطأ 'كبير أوي' في المعاينة يعرض نص عربي", async () => {
  const env = await mkEnv();
  await openFiles(env, { preview: { status: 413, data: { error: "too_large", message: "x" } } });
  fileRows(filesList(env.doc))[0].click();
  await flush();
  const box = descendants(env.doc.getElementById("view-detail")).find((n) => n.className === "file-preview");
  assert.ok(textOf(box).indexOf("كبير أوي") !== -1);
});

test("الضغط المتكرّر على نفس الملف مايكرّرش الطلب (dedupe)", async () => {
  const env = await mkEnv();
  await openFiles(env);
  const { fetch } = env;
  // نخلي المعاينة معلّقة (وعد لسه ما اتحلّش) عشان نضغط مرتين بسرعة.
  let resolvePreview;
  fetch.route(FILE_PREVIEW_MATCH, () => new Promise((r) => { resolvePreview = r; }));
  const target = fileRows(filesList(env.doc))[0];
  target.click();
  target.click(); // ضغط تاني بسرعة قبل ما الأول يخلص
  const previewCalls = fetch.all(FILE_PREVIEW_MATCH);
  assert.equal(previewCalls.length, 1, "لازم طلب معاينة واحد بس لنفس الملف");
  resolvePreview({ status: 200, data: { status: "ok", text: "x", truncated: false } });
  await flush();
});

// ============================================================ OHB2-09-04 التكلفة
function costText(doc) {
  return descendants(doc.getElementById("view-detail")).find((n) => n.className === "cost-text") || null;
}

test("قسم التكلفة يجيب /cost ويعرض الأسطر", async () => {
  const env = await mkEnv();
  env.fetch.route((c) => c.path === "/conversations/c1/cost", () => ({
    status: 200,
    data: { conversation_id: "c1", accumulated_cost: 1.5, model: "gpt-4o", prompt_tokens: 10, completion_tokens: 5 },
  }));
  await openFiles(env);
  const call = env.fetch.last((c) => c.path === "/conversations/c1/cost");
  assert.ok(call, "لازم يكون فيه نداء تكلفة");
  const node = costText(env.doc);
  assert.ok(node, "نص التكلفة لازم يظهر");
  assert.ok(node.textContent.indexOf("التكلفة التراكمية: 1.5000") !== -1);
  assert.ok(node.textContent.indexOf("توكنز الإدخال: 10") !== -1);
});

test("فشل التكلفة مايكسّر عرض الملفات", async () => {
  const env = await mkEnv();
  env.fetch.route((c) => c.path === "/conversations/c1/cost", () => ({ status: 500, data: { error: "upstream_error", message: "x" } }));
  await openFiles(env);
  // قسم الملفات لسه شغّال.
  assert.equal(fileRows(filesList(env.doc)).length, 2);
  // وقسم التكلفة بيعرض رسالة خطأ عربية.
  const section = descendants(env.doc.getElementById("view-detail")).find((n) => n.className === "cost-section");
  assert.ok(section && section.textContent.indexOf("تعذّر الوصول") !== -1);
});
