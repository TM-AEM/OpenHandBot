/* OHB2-PHASE1C — اختبارات واجهة صندوق الإشعارات: فلتر الكل/غير المقروء/المؤرشف،
 * أزرار الأرشفة/الاسترجاع، والحذف النهائي بتأكيد صريح.
 *
 * بتشتغل بـ Node المدمج: `node --test tests/frontend/inbox_manage.test.js`
 * (من غير npm). بتشغّل **نفس** bot/web/static/app.js جوه dom_stub.js وبتتحقّق من
 * السلوك المُلاحَظ: الـ DOM + طلبات الشبكة.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadApp, descendants, FakeFetch } = require("./dom_stub.js");

const flush = async (n = 12) => { for (let i = 0; i < n; i++) { await new Promise((r) => setImmediate(r)); } };

function bootResponse(extra) {
  return {
    status: 200,
    data: Object.assign({
      user: { display_name: "مستخدم" },
      settings: { notifications_enabled: true },
      features: { watches: true },
      inbox: { unread_count: 0 },
    }, extra || {}),
  };
}

function inboxPage(items, extra) {
  return { status: 200, data: Object.assign({ page: 0, has_more: false, unread_count: 0, items }, extra || {}) };
}

async function mkEnv(opts) {
  opts = opts || {};
  const fake = new FakeFetch({ deferred: !!opts.deferred });
  const env = loadApp({ fetch: fake, telegram: opts.telegram });
  const { doc } = env;
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => bootResponse(opts.bootstrap));
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/watches"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/notifications"), () => inboxPage([]));
  fake.route((c) => c.path.startsWith("/conversations/"), () => ({ status: 200, data: { id: "c1", title: "T", watched: false } }));
  if (!opts.deferred) { await flush(); }
  return env;
}

function inboxList(doc) { return doc.getElementById("inbox-list"); }
function isRow(li) { return li.className.split(" ").includes("row"); }
function dataRows(list) { return list.children.filter(isRow); }
function findButtonByText(root, text) {
  return descendants(root).find((n) => n.tagName === "BUTTON" && n.textContent === text) || null;
}
function rowByTitle(list, title) {
  return dataRows(list).find((li) => li.textContent.includes(title)) || null;
}

function item(over) {
  return Object.assign({
    id: 1, conversation_id: "c1", title: "T", kind: "terminal",
    read: true, archived: false, deletable: true, delivery_status: "delivered",
  }, over || {});
}

async function openInbox(env, pageFn) {
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), pageFn);
  doc.getElementById("tab-inbox").click();
  await flush();
}

// ==================================================== فلتر الكل / غير المقروء
test("F1: فلتر 'غير المقروء' يبعت unread=1 ويغيّر المعروض", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  const pages = {
    "/notifications?page=0": inboxPage([item({ id: 1, title: "ZREAD", read: true }), item({ id: 2, title: "ZUNREAD", read: false })], { unread_count: 1 }),
    "/notifications?page=0&unread=1": inboxPage([item({ id: 2, title: "ZUNREAD", read: false })], { unread_count: 1 }),
  };
  fetch.route((c) => c.path.startsWith("/notifications?"), (c) => pages[c.path] || inboxPage([]));
  doc.getElementById("tab-inbox").click();
  await flush();
  assert.equal(dataRows(inboxList(doc)).length, 2, "الكل: صفّين");

  doc.getElementById("inbox-filter-unread").click();
  await flush();
  const call = fetch.last((c) => c.path.startsWith("/notifications?"));
  assert.equal(call.path, "/notifications?page=0&unread=1", "يستخدم الـ API الموجود");
  assert.equal(dataRows(inboxList(doc)).length, 1, "غير المقروء: صف واحد");
  assert.ok(inboxList(doc).textContent.includes("ZUNREAD"));
  assert.ok(!inboxList(doc).textContent.includes("ZREAD"));
});

test("F2: الرجوع لفلتر 'الكل' يبعت طلب بدون unread", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => inboxPage([item({ id: 1, title: "أ" })]));
  doc.getElementById("tab-inbox").click();
  await flush();
  doc.getElementById("inbox-filter-unread").click();
  await flush();
  doc.getElementById("inbox-filter-all").click();
  await flush();
  const call = fetch.last((c) => c.path.startsWith("/notifications?"));
  assert.equal(call.path, "/notifications?page=0", "بدون unread");
});

test("F3: تغيير الفلتر بيصفّر الترقيم لصفحة 0", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), (c) =>
    c.path.includes("page=0") ? inboxPage([item({ id: 1 })], { page: 0, has_more: true }) : inboxPage([item({ id: 2 })], { page: 1 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  doc.getElementById("inbox-next").click();
  await flush();
  assert.ok(fetch.last((c) => c.path.startsWith("/notifications?")).path.includes("page=1"));
  doc.getElementById("inbox-filter-unread").click();
  await flush();
  const call = fetch.last((c) => c.path.startsWith("/notifications?"));
  assert.equal(call.path, "/notifications?page=0&unread=1", "الفلتر الجديد من صفحة 0");
});

test("F4: فلتر المؤرشف يبعت archived=1", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => inboxPage([item({ id: 9, title: "قديم", archived: true })]));
  doc.getElementById("tab-inbox").click();
  await flush();
  doc.getElementById("inbox-filter-archived").click();
  await flush();
  const call = fetch.last((c) => c.path.startsWith("/notifications?"));
  assert.equal(call.path, "/notifications?page=0&archived=1");
});

test("F5: الحالة الفاضية بتختلف حسب الفلتر", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => inboxPage([]));
  doc.getElementById("tab-inbox").click();
  await flush();
  assert.equal(inboxList(doc).children[0].textContent, "مفيش إشعارات.");
  doc.getElementById("inbox-filter-unread").click();
  await flush();
  assert.equal(inboxList(doc).children[0].textContent, "مفيش إشعارات غير مقروءة.");
  doc.getElementById("inbox-filter-archived").click();
  await flush();
  assert.equal(inboxList(doc).children[0].textContent, "مفيش إشعارات مؤرشفة.");
});

test("F6: الفلتر المختار عليه 'active' والباقي لأ", async () => {
  const env = await mkEnv();
  const { doc } = env;
  await openInbox(env, () => inboxPage([]));
  doc.getElementById("inbox-filter-unread").click();
  await flush();
  assert.equal(doc.getElementById("inbox-filter-unread").className, "chip active");
  assert.equal(doc.getElementById("inbox-filter-all").className, "chip");
  assert.equal(doc.getElementById("inbox-filter-archived").className, "chip");
});

test("F7: فشل طلب الفلتر بيعرض رسالة الخطأ (مفيش وميض نجاح)", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => ({ status: 500, ok: false, data: {} }));
  doc.getElementById("tab-inbox").click();
  await flush();
  doc.getElementById("inbox-filter-unread").click();
  await flush();
  assert.equal(inboxList(doc).children[0].className, "empty-row");
});

// ============================================================== الأرشفة
test("A1: زر الأرشفة يبعت /archive ويعيد التحميل", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => inboxPage([item({ id: 5, title: "خمسة" })]));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route("/notifications/5/archive", () => ({ status: 200, data: { ok: true, archived: true, unread_count: 0 } }));
  const btn = findButtonByText(dataRows(inboxList(doc))[0], "أرشفة");
  assert.ok(btn, "لازم زر أرشفة");
  btn.click();
  await flush();
  const call = fetch.last((c) => c.path === "/notifications/5/archive");
  assert.ok(call && call.method === "POST");
  assert.ok(fetch.last((c) => c.path.startsWith("/notifications?")) !== null, "أعاد التحميل");
});

test("A2: العنصر المؤرشف بيعرض زر 'استرجاع'", async () => {
  const env = await mkEnv();
  const { doc } = env;
  await openInbox(env, () => inboxPage([item({ id: 6, title: "مؤرشف", archived: true })]));
  const row = dataRows(inboxList(doc))[0];
  assert.ok(findButtonByText(row, "استرجاع"), "زر استرجاع للمؤرشف");
  assert.ok(!findButtonByText(row, "أرشفة"));
});

test("A3: الاسترجاع يبعت /unarchive", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => inboxPage([item({ id: 7, title: "مؤرشف", archived: true })]));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route("/notifications/7/unarchive", () => ({ status: 200, data: { ok: true, archived: false, unread_count: 0 } }));
  findButtonByText(dataRows(inboxList(doc))[0], "استرجاع").click();
  await flush();
  assert.ok(fetch.last((c) => c.path === "/notifications/7/unarchive"));
});

test("A4: فشل الأرشفة يعرض رسالة ومفيش نجاح كاذب", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => inboxPage([item({ id: 8, title: "ثمانية" })]));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route("/notifications/8/archive", () => ({ status: 500, ok: false, data: {} }));
  findButtonByText(dataRows(inboxList(doc))[0], "أرشفة").click();
  await flush();
  const toast = doc.getElementById("toast");
  assert.equal(toast.hidden, false, "التوست ظهر");
  assert.ok(!String(toast.textContent).includes("✅"), "مفيش رسالة نجاح كاذبة");
  assert.ok(rowByTitle(inboxList(doc), "ثمانية"), "الصف فضل معروضًا");
});

// ===================================================== الحذف النهائي
test("D1: زر الحذف يظهر بس للعنصر القابل للحذف (deletable=true)", async () => {
  const env = await mkEnv();
  const { doc } = env;
  await openInbox(env, () => inboxPage([
    item({ id: 1, title: "قابل", deletable: true }),
    item({ id: 2, title: "محمي", read: false, deletable: false }),
  ]));
  const rows = dataRows(inboxList(doc));
  assert.ok(findButtonByText(rowByTitle(inboxList(doc), "قابل"), "🗑 حذف"), "القابل عليه زر حذف");
  assert.ok(!findButtonByText(rowByTitle(inboxList(doc), "محمي"), "🗑 حذف"), "المحمي من غير زر حذف");
});

test("D2: الحذف بيتطلب تأكيد صريح (خطوتين) قبل أي نداء", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => inboxPage([item({ id: 3, title: "ثلاثة" })]));
  doc.getElementById("tab-inbox").click();
  await flush();
  const row = dataRows(inboxList(doc))[0];
  const delBtn = findButtonByText(row, "🗑 حذف");
  delBtn.click();
  await flush();
  // بعد الضغطة الأولى: زر التأكيد ظهر، ولسه مفيش أي نداء DELETE.
  assert.ok(findButtonByText(row, "أكّد الحذف"), "زر التأكيد ظهر");
  assert.equal(fetch.all((c) => c.method === "DELETE").length, 0, "مفيش حذف قبل التأكيد");
});

test("D3: الإلغاء بيرجّع زر الحذف من غير نداء", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => inboxPage([item({ id: 4, title: "أربعة" })]));
  doc.getElementById("tab-inbox").click();
  await flush();
  const row = dataRows(inboxList(doc))[0];
  findButtonByText(row, "🗑 حذف").click();
  await flush();
  findButtonByText(row, "إلغاء").click();
  await flush();
  assert.ok(findButtonByText(row, "🗑 حذف"), "زر الحذف رجع");
  assert.equal(fetch.all((c) => c.method === "DELETE").length, 0);
});

test("D4: تأكيد الحذف يبعت DELETE ويعيد التحميل", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => inboxPage([item({ id: 5, title: "خمسة" })]));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route("/notifications/5", () => ({ status: 200, data: { ok: true, deleted: true, unread_count: 0 } }));
  const row = dataRows(inboxList(doc))[0];
  findButtonByText(row, "🗑 حذف").click();
  await flush();
  findButtonByText(row, "أكّد الحذف").click();
  await flush();
  const call = fetch.last((c) => c.method === "DELETE");
  assert.ok(call && call.path === "/notifications/5", "DELETE صح");
  assert.ok(fetch.last((c) => c.path.startsWith("/notifications?")) !== null, "أعاد التحميل");
});

test("D5: رفض السيرفر (409) بيعرض رسالة ومفيش حذف وهمي", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => inboxPage([item({ id: 6, title: "محمي" })]));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route("/notifications/6", () => ({ status: 409, ok: false, data: {} }));
  const row = dataRows(inboxList(doc))[0];
  findButtonByText(row, "🗑 حذف").click();
  await flush();
  findButtonByText(row, "أكّد الحذف").click();
  await flush();
  const toast = doc.getElementById("toast");
  assert.equal(toast.hidden, false);
  assert.ok(!String(toast.textContent).includes("✅"), "مفيش نجاح كاذب");
  assert.ok(rowByTitle(inboxList(doc), "محمي"), "الصف فضل");
});

test("D6: انقطاع الشبكة عند الحذف يعرض رسالة قابلة لإعادة المحاولة", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications?"), () => inboxPage([item({ id: 7, title: "سبعة" })]));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route("/notifications/7", () => { throw new Error("network down"); });
  const row = dataRows(inboxList(doc))[0];
  findButtonByText(row, "🗑 حذف").click();
  await flush();
  findButtonByText(row, "أكّد الحذف").click();
  await flush();
  const toast = doc.getElementById("toast");
  assert.equal(toast.hidden, false);
  assert.ok(!String(toast.textContent).includes("✅"));
});

test("D7: الصف بيحمل صنف archived + أزرار في حاوية row-actions", async () => {
  const env = await mkEnv();
  const { doc } = env;
  await openInbox(env, () => inboxPage([item({ id: 8, title: "قديم", archived: true, read: false })]));
  const row = dataRows(inboxList(doc))[0];
  assert.ok(row.className.split(" ").includes("archived"), "صنف archived");
  assert.ok(row.className.split(" ").includes("unread"), "صنف unread");
  const actions = descendants(row).find((n) => n.className && n.className.split(" ").includes("row-actions"));
  assert.ok(actions, "حاوية row-actions موجودة");
});
