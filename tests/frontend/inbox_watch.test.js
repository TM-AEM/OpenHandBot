/* OHB2-08-06 — اختبارات انحدار الواجهة لصندوق الإشعارات والمتابعة.
 *
 * بتشتغل بـ Node المدمج: `node --test tests/frontend/inbox_watch.test.js`
 * (من غير npm — مفيش أي اعتماد خارجي).
 *
 * بتشغّل **نفس** `bot/web/static/app.js` جوه بيئة DOM/شبكة مصغّرة (dom_stub.js)،
 * وبتتحقّق من السلوك المُلاحَظ: الـ DOM الناتج + طلبات الشبكة + عقد الـ API.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadApp, descendants, FakeFetch } = require("./dom_stub.js");

const flush = async (n = 12) => { for (let i = 0; i < n; i++) { await new Promise((r) => setImmediate(r)); } };

// ------------------------------------------------------------------ أدوات مساعدة
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

// بيبني بيئة + مسارات افتراضية، وبيكمّل الإقلاع (نمط غير-مؤجّل).
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

// يحلّ كل الطلبات المعلّقة للـ boot (نمط مؤجّل).
async function resolveBoot(env, opts) {
  for (let i = 0; i < 30; i++) {
    const pend = env.fetch.pending();
    if (!pend.length) { break; }
    for (const c of pend) {
      if (c.path === "/auth") { c.resolve({ status: 200, data: { ok: true } }); }
      else if (c.path === "/app/bootstrap") { c.resolve(bootResponse(opts && opts.bootstrap)); }
      else if (c.path.startsWith("/conversations")) { c.resolve({ status: 200, data: { items: [], has_more: false } }); }
      else { c.resolve({ status: 200, data: {} }); }
    }
    await flush();
  }
}

function inboxList(doc) { return doc.getElementById("inbox-list"); }
function rowTexts(list) { return list.children.map((c) => c.textContent); }
function isRow(li) { return li.className.split(" ").includes("row"); }
function dataRows(list) { return list.children.filter(isRow); }

function findButtonByText(root, text) {
  return descendants(root).find((n) => n.tagName === "BUTTON" && n.textContent === text) || null;
}

// يفتح تفاصيل محادثة عبر تبويب الشاتات.
async function openDetail(env, cid, detail) {
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [{ id: cid, title: "T", repository: "r", status: "running" }], has_more: false } }));
  fetch.route((c) => c.path.startsWith("/conversations/"), () => ({ status: 200, data: detail }));
  doc.getElementById("tab-chats").click();
  await flush();
  dataRows(doc.getElementById("chats-list"))[0].click();
  await flush();
}

// ==================================================================== A. التحميل الأولي
test("A1: التحميل الأولي — حالة التحميل ظاهرة قبل وصول الرد", async () => {
  const env = await mkEnv({ deferred: true });
  const { doc, fetch } = env;
  await resolveBoot(env);
  doc.getElementById("tab-inbox").click();
  const list = inboxList(doc);
  assert.equal(list.children.length, 1, "لازم يظهر صف تحميل واحد");
  assert.equal(list.children[0].className, "loading-row");
  assert.equal(list.children[0].textContent, "بيتم التحميل…");
  const call = fetch.last((c) => c.path.startsWith("/notifications"));
  assert.ok(call, "لازم يتبعت طلب إشعارات");
  call.resolve(inboxPage([]));
  await flush();
});

test("A2: التحميل الأولي — الطلب بيستخدم page=0 (عقد الـ API)", async () => {
  const env = await mkEnv({ deferred: true });
  const { doc, fetch } = env;
  await resolveBoot(env);
  doc.getElementById("tab-inbox").click();
  await flush();
  const call = fetch.last((c) => c.path.startsWith("/notifications"));
  assert.equal(call.method, "GET");
  assert.equal(call.path, "/notifications?page=0");
  call.resolve(inboxPage([]));
  await flush();
});

test("A3: التحميل الأولي — رد ناجح يعرض الإشعارات + الشارة", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "شات أ", kind: "terminal", read: false, delivery_status: "delivered" },
    { id: 2, conversation_id: "c2", title: "شات ب", kind: "timeout", read: true, delivery_status: "delivered" },
  ], { unread_count: 2 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  const list = inboxList(doc);
  assert.equal(dataRows(list).length, 2, "لازم يظهر صفّين");
  assert.equal(list.children[0].className, "row unread", "غير المقروء عليه unread");
  assert.equal(list.children[1].className, "row", "المقروء من غير unread");
  assert.ok(rowTexts(list)[0].includes("شات أ"));
  assert.ok(rowTexts(list)[0].includes("انتهى شات"), "نوع الإشعار يتحوّل لعربي");
  const badge = doc.getElementById("inbox-badge");
  assert.equal(badge.hidden, false);
  assert.equal(badge.textContent, "2");
});

test("A4: التحميل الأولي — رد فاضي يعرض الحالة الفاضية", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([]));
  doc.getElementById("tab-inbox").click();
  await flush();
  const list = inboxList(doc);
  assert.equal(dataRows(list).length, 0);
  assert.equal(list.children.length, 1);
  assert.equal(list.children[0].className, "empty-row");
  assert.equal(list.children[0].textContent, "مفيش إشعارات.");
});

test("A5: التحميل الأولي — رد فاشل يعرض خطأ قابل للاسترجاع", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 500, ok: false, data: {} }));
  doc.getElementById("tab-inbox").click();
  await flush();
  const list = inboxList(doc);
  assert.equal(list.children.length, 1);
  assert.equal(list.children[0].className, "empty-row");
  assert.equal(list.children[0].textContent, "الخدمة مش متاحة دلوقتي، جرّب تاني.");
  // قابل للاسترجاع: تحديث ناجح بعد كده يعرض الإشعارات.
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 9, conversation_id: "c9", title: "رجعت", kind: "terminal", read: false, delivery_status: "delivered" },
  ], { unread_count: 1 }));
  doc.getElementById("inbox-refresh").click();
  await flush();
  assert.equal(dataRows(list).length, 1, "بعد إعادة المحاولة لازم تظهر الإشعارات");
});

test("A5b: فشل الشبكة (رفض الوعد) يعرض خطأ قابل للاسترجاع", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => { throw new Error("network"); });
  doc.getElementById("tab-inbox").click();
  await flush();
  const list = inboxList(doc);
  assert.equal(list.children.length, 1);
  assert.equal(list.children[0].textContent, "مش قادر أوصل للسيرفر.");
  // والحارس اتصفّر: تحديث لاحق بيشتغل.
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 7, conversation_id: "c7", title: "t", kind: "terminal", read: true, delivery_status: "delivered" },
  ]));
  doc.getElementById("inbox-refresh").click();
  await flush();
  assert.equal(dataRows(list).length, 1);
});

// ==================================================================== B. الترقيم
test("B1: زر المزيد بيطلب الصفحة الجاية بالظبط (page=1)", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  assert.equal(doc.getElementById("inbox-more").hidden, false, "فيه المزيد ⇒ الزر ظاهر");
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 200, data: { page: 1, has_more: false, unread_count: 0, items: [
    { id: 2, conversation_id: "c2", title: "B", kind: "timeout", read: true, delivery_status: "delivered" },
  ] } }));
  doc.getElementById("inbox-next").click();
  await flush();
  const call = fetch.last((c) => c.path.startsWith("/notifications"));
  assert.equal(call.path, "/notifications?page=1");
});

test("B2: المزيد بيضيف من غير ما يمسح الصفوف الموجودة", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
    { id: 2, conversation_id: "c2", title: "B", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 200, data: { page: 1, has_more: false, unread_count: 0, items: [
    { id: 3, conversation_id: "c3", title: "C", kind: "terminal", read: true, delivery_status: "delivered" },
  ] } }));
  doc.getElementById("inbox-next").click();
  await flush();
  const list = inboxList(doc);
  assert.equal(dataRows(list).length, 3, "لازم يتضافوا (2+1) مش يستبدلوا");
  const texts = rowTexts(list).join("|");
  ["A", "B", "C"].forEach((t) => assert.ok(texts.includes(t), "لازم " + t + " يفضل موجود"));
});

test("B3: معرّفات الإشعارات المكرّرة ما تتكرّرش في العرض (تداخل offset)", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
    { id: 2, conversation_id: "c2", title: "B", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  // الصفحة 1 بترجّع id=2 تاني (تداخل) + id=3 جديد.
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 200, data: { page: 1, has_more: false, unread_count: 0, items: [
    { id: 2, conversation_id: "c2", title: "B", kind: "terminal", read: true, delivery_status: "delivered" },
    { id: 3, conversation_id: "c3", title: "C", kind: "terminal", read: true, delivery_status: "delivered" },
  ] } }));
  doc.getElementById("inbox-next").click();
  await flush();
  const list = inboxList(doc);
  assert.equal(dataRows(list).length, 3, "id=2 مايتكرّرش ⇒ 3 صفوف مش 4");
  const bCount = rowTexts(list).filter((t) => t.includes("B")).length;
  assert.equal(bCount, 1, "صف B يظهر مرة واحدة بس");
});

test("B4: الترقيم بيقف لما مفيش المزيد (has_more=false)", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: false }));
  doc.getElementById("tab-inbox").click();
  await flush();
  assert.equal(doc.getElementById("inbox-more").hidden, true, "مفيش المزيد ⇒ الزر مخفي");
});

test("B5: فشل طلب المزيد بيحافظ على الإشعارات المحمّلة قبل كده", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 500, ok: false, data: {} }));
  doc.getElementById("inbox-next").click();
  await flush();
  const list = inboxList(doc);
  assert.equal(dataRows(list).length, 1, "الصف المحمّل يفضل موجود");
  assert.ok(rowTexts(list)[0].includes("A"));
});

test("B6: الضغط المتكرّر السريع على المزيد مايعملش طلبات متداخلة", async () => {
  const env = await mkEnv({ deferred: true });
  const { doc, fetch } = env;
  await resolveBoot(env);
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.last((c) => c.path.startsWith("/notifications")).resolve(inboxPage([], { has_more: true }));
  await flush();
  // ضغطتين متتاليتين قبل ما يتحلّ أول طلب
  doc.getElementById("inbox-next").click();
  doc.getElementById("inbox-next").click();
  await flush();
  const calls = fetch.all((c) => c.path.startsWith("/notifications"));
  const pages = calls.map((c) => c.path);
  assert.equal(pages.filter((p) => p === "/notifications?page=1").length, 1, "طلب واحد بس للصفحة 1");
  assert.equal(pages.filter((p) => p === "/notifications?page=2").length, 0, "مفيش طلب للصفحة 2 (تخطّي)");
  calls.forEach((c) => { if (!c.settled) { c.resolve({ status: 200, data: { page: 1, has_more: false, unread_count: 0, items: [] } }); } });
  await flush();
});

// ==================================================================== C. حالة القراءة
test("C1: الضغط على إشعار غير مقروء بيبعت معرّفه الصح للمارك-ريد", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 42, conversation_id: "c42", title: "T", kind: "terminal", read: false, delivery_status: "delivered" },
  ], { unread_count: 1 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.includes("/read"), () => ({ status: 200, data: { ok: true, unread_count: 0 } }));
  dataRows(inboxList(doc))[0].click();
  await flush();
  const call = fetch.last((c) => c.path.includes("/read"));
  assert.ok(call, "لازم يبعت طلب قراءة");
  assert.equal(call.method, "POST");
  assert.equal(call.path, "/notifications/42/read");
});

test("C2: نجاح المارك-ريد بيحدّث شارة غير المقروء", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 5, conversation_id: "c5", title: "T", kind: "terminal", read: false, delivery_status: "delivered" },
  ], { unread_count: 1 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.includes("/read"), () => ({ status: 200, data: { ok: true, unread_count: 0 } }));
  dataRows(inboxList(doc))[0].click();
  await flush();
  assert.equal(doc.getElementById("inbox-badge").hidden, true, "الشارة تختفي لما العدد يوصل صفر");
});

test("C3: فشل المارك-ريد مايعلّمش الإشعار مقروء (العرض لسه غير مقروء)", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 8, conversation_id: "c8", title: "T", kind: "terminal", read: false, delivery_status: "delivered" },
  ], { unread_count: 1 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.includes("/read"), () => ({ status: 500, ok: false, data: {} }));
  const before = doc.getElementById("inbox-badge").textContent;
  dataRows(inboxList(doc))[0].click();
  await flush();
  assert.equal(doc.getElementById("inbox-badge").textContent, before, "الشارة ما تتغيّرش عند الفشل");
  assert.equal(doc.getElementById("inbox-badge").hidden, false, "لسه فيه غير مقروء");
});

test("C4: تعليم الكل كمقروء بيستخدم الـ endpoint الصح", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: false, delivery_status: "delivered" },
    { id: 2, conversation_id: "c2", title: "B", kind: "terminal", read: false, delivery_status: "delivered" },
  ], { unread_count: 2 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route("/notifications/read-all", () => ({ status: 200, data: { ok: true, marked: 2, unread_count: 0 } }));
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([]));
  doc.getElementById("inbox-read-all").click();
  await flush();
  const call = fetch.last((c) => c.path === "/notifications/read-all");
  assert.ok(call, "لازم يبعت read-all");
  assert.equal(call.method, "POST");
  assert.equal(call.path, "/notifications/read-all");
  assert.equal(doc.getElementById("inbox-badge").hidden, true, "الشارة تختفي بعد read-all");
});

test("C5: فشل تعليم الكل بيحافظ على الحالة السابقة + الزر يترجّع", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: false, delivery_status: "delivered" },
  ], { unread_count: 2 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route("/notifications/read-all", () => ({ status: 500, ok: false, data: {} }));
  const btn = doc.getElementById("inbox-read-all");
  btn.click();
  assert.equal(btn.disabled, true, "الزر يتعطّل أثناء الطلب");
  await flush();
  assert.equal(btn.disabled, false, "الزر يترجّع بعد الفشل");
  assert.equal(doc.getElementById("inbox-badge").hidden, false, "الشارة تفضل (2 غير مقروء)");
  assert.equal(doc.getElementById("inbox-badge").textContent, "2");
});

test("C6: تعليم الكل ناجح بيعمل reload للصفحة 0", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: false, delivery_status: "delivered" },
  ], { unread_count: 1 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route("/notifications/read-all", () => ({ status: 200, data: { ok: true, marked: 1, unread_count: 0 } }));
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([]));
  doc.getElementById("inbox-read-all").click();
  await flush();
  const reload = fetch.last((c) => c.path.startsWith("/notifications?"));
  assert.equal(reload.path, "/notifications?page=0", "يعيد تحميل الصفحة 0");
});

test("C7: الضغط على الإشعار بيفتح تفاصيل المحادثة المرتبطة", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 3, conversation_id: "cX", title: "T", kind: "terminal", read: false, delivery_status: "delivered" },
  ], { unread_count: 1 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.includes("/read"), () => ({ status: 200, data: { ok: true, unread_count: 0 } }));
  fetch.route((c) => c.path.startsWith("/conversations/"), () => ({ status: 200, data: { id: "cX", title: "التفاصيل", watched: false } }));
  dataRows(inboxList(doc))[0].click();
  await flush();
  // OHB2-09-02: عرض التفاصيل بقى بيجيب الملفات كمان، فبندوّر على نداء التفاصيل بالظبط.
  const detailCall = fetch.last((c) => c.path === "/conversations/cX");
  assert.equal(detailCall.path, "/conversations/cX");
  assert.equal(doc.getElementById("view-detail").hidden, false, "العرض انتقل للتفاصيل");
});

// ==================================================================== D. المتابعة
test("D1: زر المتابعة بيعكس الحالة الحالية (watched=true ⇒ إلغاء المتابعة)", async () => {
  const env = await mkEnv();
  const { doc } = env;
  await openDetail(env, "c1", { id: "c1", title: "T", watched: true });
  const btn = findButtonByText(doc.getElementById("view-detail"), "إلغاء المتابعة");
  assert.ok(btn, "لازم الزر يعرض 'إلغاء المتابعة' لما watched=true");
});

test("D2: المتابعة بتستخدم POST على المسار الصح + تحدّث العرض", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  await openDetail(env, "c1", { id: "c1", title: "T", watched: false });
  fetch.route((c) => c.path.includes("/watch"), () => ({ status: 200, data: { ok: true, watched: true } }));
  const btn = findButtonByText(doc.getElementById("view-detail"), "متابعة");
  btn.click();
  await flush();
  const call = fetch.last((c) => c.path.includes("/watch"));
  assert.equal(call.method, "POST", "متابعة = POST");
  assert.equal(call.path, "/conversations/c1/watch");
  assert.equal(btn.textContent, "إلغاء المتابعة", "الحالة المعروضة اتغيّرت");
});

test("D3: إلغاء المتابعة بيستخدم DELETE على المسار الصح", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  await openDetail(env, "c1", { id: "c1", title: "T", watched: true });
  fetch.route((c) => c.path.includes("/watch"), () => ({ status: 200, data: { ok: true, watched: false } }));
  const btn = findButtonByText(doc.getElementById("view-detail"), "إلغاء المتابعة");
  btn.click();
  await flush();
  const call = fetch.last((c) => c.path.includes("/watch"));
  assert.equal(call.method, "DELETE", "إلغاء المتابعة = DELETE");
  assert.equal(call.path, "/conversations/c1/watch");
  assert.equal(btn.textContent, "متابعة");
});

test("D4: فشل المتابعة (HTTP) مايغيّرش الحالة المعروضة", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  await openDetail(env, "c1", { id: "c1", title: "T", watched: false });
  fetch.route((c) => c.path.includes("/watch"), () => ({ status: 500, ok: false, data: {} }));
  const btn = findButtonByText(doc.getElementById("view-detail"), "متابعة");
  btn.click();
  await flush();
  assert.equal(btn.textContent, "متابعة", "لسه 'متابعة' (ما اتغيّرش كذبًا)");
  assert.equal(btn.disabled, false, "الزر يترجّع بعد الفشل");
});

test("D5: فشل الشبكة في المتابعة مايغيّرش الحالة المعروضة", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  await openDetail(env, "c1", { id: "c1", title: "T", watched: true });
  fetch.route((c) => c.path.includes("/watch"), () => { throw new Error("net"); });
  const btn = findButtonByText(doc.getElementById("view-detail"), "إلغاء المتابعة");
  btn.click();
  await flush();
  assert.equal(btn.textContent, "إلغاء المتابعة", "الحالة ما اتغيّرتش");
});

test("D6: الضغط المتكرّر على زر المتابعة مايعملش طلبات متعدّدة", async () => {
  const env = await mkEnv({ deferred: true });
  const { doc, fetch } = env;
  await resolveBoot(env);
  doc.getElementById("tab-chats").click();
  await flush();
  fetch.last((c) => c.path.startsWith("/conversations?")).resolve({ status: 200, data: { items: [{ id: "c1", title: "T", repository: "r", status: "running" }], has_more: false } });
  await flush();
  dataRows(doc.getElementById("chats-list"))[0].click();
  await flush();
  fetch.last((c) => c.path.startsWith("/conversations/")).resolve({ status: 200, data: { id: "c1", title: "T", watched: false } });
  await flush();
  const btn = findButtonByText(doc.getElementById("view-detail"), "متابعة");
  assert.ok(btn);
  btn.click();
  btn.click();  // الزر اتعطّل ⇒ الضغطة التانية تتجاهل
  await flush();
  const watchCalls = fetch.all((c) => c.path.includes("/watch"));
  assert.equal(watchCalls.length, 1, "طلب متابعة واحد بس");
  watchCalls.forEach((c) => { if (!c.settled) { c.resolve({ status: 200, data: { ok: true, watched: true } }); } });
  await flush();
});

test("D7: عرض حالة المتابعة — 'متابعة' لما watched=false", async () => {
  const env = await mkEnv();
  const { doc } = env;
  await openDetail(env, "c1", { id: "c1", title: "T", watched: false });
  assert.ok(findButtonByText(doc.getElementById("view-detail"), "متابعة"), "لازم 'متابعة'");
  assert.equal(findButtonByText(doc.getElementById("view-detail"), "إلغاء المتابعة"), null, "مش 'إلغاء المتابعة'");
});

test("D8: تبويب المتابعات بيعرض الحالة من عقد /watches", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/watches"), () => ({ status: 200, data: { page: 0, has_more: false, items: [
    { id: "w1", title: "متابَعة أ", last_state: "running", added_at: "t" },
    { id: "w2", title: "متابَعة ب", last_state: "finished", added_at: "t" },
  ] } }));
  doc.getElementById("tab-watches").click();
  await flush();
  const list = doc.getElementById("watches-list");
  assert.equal(dataRows(list).length, 2);
  const texts = rowTexts(list).join("|");
  assert.ok(texts.includes("متابَعة أ") && texts.includes("running"));
  assert.ok(texts.includes("متابَعة ب") && texts.includes("finished"));
});

test("D9: فشل تحميل المتابعات يعرض خطأ", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/watches"), () => ({ status: 500, ok: false, data: {} }));
  doc.getElementById("tab-watches").click();
  await flush();
  const list = doc.getElementById("watches-list");
  assert.equal(list.children.length, 1);
  assert.equal(list.children[0].textContent, "الخدمة مش متاحة دلوقتي، جرّب تاني.");
});

test("D10: تحديث الإشعارات مايغيّرش حالة المتابعة المعروضة", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  await openDetail(env, "c1", { id: "c1", title: "T", watched: true });
  const before = findButtonByText(doc.getElementById("view-detail"), "إلغاء المتابعة");
  assert.ok(before, "الحالة الابتدائية متابَعة");
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([]));
  doc.getElementById("tab-inbox").click();
  await flush();
  doc.getElementById("inbox-refresh").click();
  await flush();
  assert.equal(findButtonByText(doc.getElementById("view-detail"), "إلغاء المتابعة"), before, "حالة المتابعة ما اتغيّرتش");
});

// ==================================================================== E. التحديث والدورة الحياتية
test("E1: زر تحديث الإشعارات يعيد التحميل من الصفحة 0 (واستبدال مش تراكم)", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 2, conversation_id: "c2", title: "جديد", kind: "terminal", read: true, delivery_status: "delivered" },
  ]));
  doc.getElementById("inbox-refresh").click();
  await flush();
  const call = fetch.last((c) => c.path.startsWith("/notifications"));
  assert.equal(call.path, "/notifications?page=0", "التحديث من الصفحة 0");
  const list = inboxList(doc);
  assert.equal(dataRows(list).length, 1, "القايمة اتستبدلت (مش اتراكمت)");
  assert.ok(rowTexts(list)[0].includes("جديد"));
});

test("E2: التحديث بيصفّر الترقيم — 'المزيد' بعد التحديث يطلب page=1 من جديد", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  doc.getElementById("inbox-next").click();
  await flush();
  // بعد ما وصلنا صفحة 1، نحدّث (يرجّعنا 0)
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: true }));
  doc.getElementById("inbox-refresh").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 200, data: { page: 1, has_more: false, unread_count: 0, items: [] } }));
  doc.getElementById("inbox-next").click();
  await flush();
  const call = fetch.last((c) => c.path.startsWith("/notifications"));
  assert.equal(call.path, "/notifications?page=1");
});

test("E3: شارة التبويب تبدأ من bootstrap وتتحدّث بالتحديث", async () => {
  const env = await mkEnv({ bootstrap: { inbox: { unread_count: 7 } } });
  const { doc, fetch } = env;
  assert.equal(doc.getElementById("inbox-badge").textContent, "7");
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([], { unread_count: 3 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  assert.equal(doc.getElementById("inbox-badge").textContent, "3");
});

test("E4: التحديث أثناء طلب جاري مايعملش طلب متداخل", async () => {
  const env = await mkEnv({ deferred: true });
  const { doc, fetch } = env;
  await resolveBoot(env);
  doc.getElementById("tab-inbox").click();
  await flush();
  const first = fetch.last((c) => c.path.startsWith("/notifications"));
  doc.getElementById("inbox-refresh").click();   // طلب جاري ⇒ يتجاهل
  await flush();
  const notifCalls = fetch.all((c) => c.path.startsWith("/notifications"));
  assert.equal(notifCalls.length, 1, "طلب واحد بس (الجاري)");
  first.resolve(inboxPage([]));
  await flush();
});

test("E5: التوست بيظهر ويتخفي بعد المهلة", async () => {
  const env = await mkEnv();
  const { doc, fetch, runTimers } = env;
  await openDetail(env, "c1", { id: "c1", title: "T", watched: false });
  fetch.route((c) => c.path.includes("/watch"), () => ({ status: 200, data: { ok: true, watched: true } }));
  findButtonByText(doc.getElementById("view-detail"), "متابعة").click();
  await flush();
  const toast = doc.getElementById("toast");
  assert.equal(toast.hidden, false, "التوست ظهر");
  runTimers();
  assert.equal(toast.hidden, true, "التوست اختفى بعد المهلة");
});

test("E6: تبديل التبويبات مايكسّر عرض الإشعارات", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: false, delivery_status: "delivered" },
  ], { unread_count: 1 }));
  doc.getElementById("tab-inbox").click();
  doc.getElementById("tab-chats").click();
  doc.getElementById("tab-inbox").click();
  await flush();
  assert.equal(dataRows(inboxList(doc)).length, 1, "لسه بيعرض الإشعارات صح بعد التنقّل");
});

// ==================================================================== F. ترقيم محسّن (OHB2-08-08)
test("F1: رقم الصفحة بيتزامن مع رد السيرفر — الترقيم يكمّل صح", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: true, page: 0 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 200, data: { page: 1, has_more: true, unread_count: 0, items: [
    { id: 2, conversation_id: "c2", title: "B", kind: "terminal", read: true, delivery_status: "delivered" },
  ] } }));
  doc.getElementById("inbox-next").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 200, data: { page: 2, has_more: false, unread_count: 0, items: [
    { id: 3, conversation_id: "c3", title: "C", kind: "terminal", read: true, delivery_status: "delivered" },
  ] } }));
  doc.getElementById("inbox-next").click();
  await flush();
  const pages = fetch.all((c) => c.path.startsWith("/notifications")).map((c) => c.path);
  assert.deepEqual(pages, ["/notifications?page=0", "/notifications?page=1", "/notifications?page=2"]);
  assert.equal(dataRows(inboxList(doc)).length, 3);
});

test("F2: لو السيرفر رجع للأولى (تجاوز الحد) نزامن الرقم ومانطلبش صفحة مش موجودة", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: true, page: 0 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  // صفحة 1 مش موجودة ⇒ السيرفر بيرجع للأولى (page=0, has_more=false).
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: false, page: 0 }));
  doc.getElementById("inbox-next").click();
  await flush();
  assert.equal(doc.getElementById("inbox-more").hidden, true, "has_more=false ⇒ الزر مخفي");
  assert.equal(dataRows(inboxList(doc)).length, 1, "التكرار اتشال (id=1 مرة واحدة)");
  const callsBefore = fetch.all((c) => c.path.startsWith("/notifications")).length;
  doc.getElementById("inbox-next").click();   // مفيش المزيد ⇒ مفيش طلب
  await flush();
  assert.equal(fetch.all((c) => c.path.startsWith("/notifications")).length, callsBefore, "مفيش طلب صفحة مش موجودة");
});

test("F3: مفيش المزيد من الأول ⇒ الضغط على 'المزيد' مايبعتش أي طلب", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: false }));
  doc.getElementById("tab-inbox").click();
  await flush();
  const callsBefore = fetch.all((c) => c.path.startsWith("/notifications")).length;
  doc.getElementById("inbox-next").click();
  await flush();
  assert.equal(fetch.all((c) => c.path.startsWith("/notifications")).length, callsBefore, "مفيش طلب زايد");
});

test("F4: التحديث بيصفّر الترقيم ويزامن تاني مع السيرفر", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: true, page: 0 }));
  doc.getElementById("tab-inbox").click();
  await flush();
  doc.getElementById("inbox-next").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 5, conversation_id: "c5", title: "جديد", kind: "terminal", read: true, delivery_status: "delivered" },
  ], { has_more: false, page: 0 }));
  doc.getElementById("inbox-refresh").click();
  await flush();
  const call = fetch.last((c) => c.path.startsWith("/notifications"));
  assert.equal(call.path, "/notifications?page=0", "التحديث من الصفحة 0");
  assert.equal(dataRows(inboxList(doc)).length, 1, "القايمة اتستبدلت");
});

// ==================================================================== G. تحديث حسب الرؤية (OHB2-08-07)
test("G1: poll بيشتغل بس والصفحة مرئية (مخفي ⇒ مفيش مؤقّت)", async () => {
  const env = await mkEnv();
  const { doc } = env;
  assert.equal(env.intervalCount(), 1, "مرئي ⇒ poll شغال");
  doc.setHidden(false);
  assert.equal(env.intervalCount(), 1, "لسه مرئي ⇒ poll واحد");
  doc.setHidden(true);
  assert.equal(env.intervalCount(), 0, "مخفي ⇒ poll متوقف");
  doc.setHidden(false);
  assert.equal(env.intervalCount(), 1, "رجعت مرئي ⇒ poll رجع");
});

test("G2: الرجوع للصفحة المرئية بيعمل تحديث فوري للتبويب المفتوح", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  let clk = 1e15;
  env.sandbox.Date = { now: () => clk };
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ]));
  doc.getElementById("tab-inbox").click();   // lastRefresh = clk
  await flush();
  const before = fetch.all((c) => c.path.startsWith("/notifications")).length;
  clk += 10000;                              // عدّى وقت كفاية
  doc.setHidden(false);                   // رجع للصفحة
  await flush();
  const after = fetch.all((c) => c.path.startsWith("/notifications")).length;
  assert.equal(after, before + 1, "لازم يعمل تحديث واحد عند الرجوع");
});

test("G3: الرجوع للصفحة بسرعة مايكرّرش التحديث (تهدئة)", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  let clk = 1e15;
  env.sandbox.Date = { now: () => clk };
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ]));
  doc.getElementById("tab-inbox").click();   // lastRefresh = clk
  await flush();
  const before = fetch.all((c) => c.path.startsWith("/notifications")).length;
  clk += 1000;                               // لسه بدري (< الفاصل)
  doc.setHidden(false);
  await flush();
  assert.equal(fetch.all((c) => c.path.startsWith("/notifications")).length, before, "مفيش تحديث مكرّر");
});

test("G4: poll مش بيعمل تحديث لو تبويب الإشعارات مش مفتوح", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  let clk = 1e15;
  env.sandbox.Date = { now: () => clk };
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([]));
  // نفتح تبويب الشاتات (الإشعارات مش مفتوح)، بعدين نشغّل الـ poll.
  doc.getElementById("tab-chats").click();
  await flush();
  const before = fetch.all((c) => c.path.startsWith("/notifications")).length;
  clk += 60000;
  env.runIntervals();                        // poll
  await flush();
  assert.equal(fetch.all((c) => c.path.startsWith("/notifications")).length, before, "مفيش تحديث والتبويب مقفول");
});

test("G5: تحديث خلفي (silent) مابيعرضش صف تحميل ومابيمسحش المعروض", async () => {
  const env = await mkEnv({ deferred: true });
  const { doc, fetch } = env;
  await resolveBoot(env);
  let clk = 1e15;
  env.sandbox.Date = { now: () => clk };
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.last((c) => c.path.startsWith("/notifications")).resolve(inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ]));
  await flush();
  assert.equal(dataRows(inboxList(doc)).length, 1);
  // تحديث خلفي معلّق: لازم الصف القديم يفضل ظاهر (مفيش loading-row).
  clk += 60000;
  doc.setHidden(false);
  await flush();
  const list = inboxList(doc);
  assert.equal(dataRows(list).length, 1, "الصف القديم لسه ظاهر أثناء التحديث الخلفي");
  assert.equal(list.children.filter((c) => c.className === "loading-row").length, 0, "مفيش صف تحميل");
  const pending = fetch.pending().find((c) => c.path.startsWith("/notifications"));
  assert.ok(pending, "فيه طلب خلفي معلّق");
  pending.resolve(inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
    { id: 2, conversation_id: "c2", title: "B", kind: "terminal", read: true, delivery_status: "delivered" },
  ]));
  await flush();
  assert.equal(dataRows(list).length, 2, "التحديث الخلفي جاب الإشعارات الجديدة");
});

test("G6: فشل التحديث الخلفي مايمسحش المعروض", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  let clk = 1e15;
  env.sandbox.Date = { now: () => clk };
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([
    { id: 1, conversation_id: "c1", title: "A", kind: "terminal", read: true, delivery_status: "delivered" },
  ]));
  doc.getElementById("tab-inbox").click();
  await flush();
  // التحديث الخلفي هيفشل
  fetch.route((c) => c.path.startsWith("/notifications"), () => { throw new Error("net"); });
  clk += 60000;
  doc.setHidden(false);
  await flush();
  const list = inboxList(doc);
  assert.equal(dataRows(list).length, 1, "المعروض فضل زي ما هو");
  assert.equal(list.children.filter((c) => c.className === "empty-row").length, 0, "مفيش رسالة خطأ للتحديث الخلفي");
});

// ==================================================================== H. إصلاح R5-01: إعادة المحاولة بعد فشل الترقيم
// الفكرة: `state.inboxPage` = آخر صفحة **نجحت**، وبيتكتب بس في مسار النجاح. لو أي
// طلب فشل (HTTP/شبكة)، "المزيد" التالي يعيد **نفس** الصفحة الفاشلة، مش اللي بعدها.
function nrow(id) {
  return { id, conversation_id: "c" + id, title: "N" + id, kind: "terminal", read: true, delivery_status: "delivered" };
}
function listPages(fetch) {
  return fetch.all((c) => c.path.startsWith("/notifications?")).map((c) => c.path);
}

test("H1: فشل صفحة 1 بـ HTTP 500 ⇒ إعادة المحاولة تطلب صفحة 1 تاني", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(1)], { page: 0, has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 500, ok: false, data: {} }));
  doc.getElementById("inbox-next").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(2)], { page: 1, has_more: false }));
  doc.getElementById("inbox-next").click();
  await flush();
  assert.deepEqual(listPages(fetch), ["/notifications?page=0", "/notifications?page=1", "/notifications?page=1"]);
});

test("H2: فشل صفحة 1 برفض الشبكة ⇒ إعادة المحاولة تطلب صفحة 1 تاني", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(1)], { page: 0, has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => { throw new Error("net"); });
  doc.getElementById("inbox-next").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(2)], { page: 1, has_more: false }));
  doc.getElementById("inbox-next").click();
  await flush();
  assert.deepEqual(listPages(fetch), ["/notifications?page=0", "/notifications?page=1", "/notifications?page=1"]);
});

test("H3: صفحة 2 تفشل بعد نجاح صفحة 1 ⇒ إعادة المحاولة تطلب صفحة 2 تاني", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(1)], { page: 0, has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(2)], { page: 1, has_more: true }));
  doc.getElementById("inbox-next").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 503, ok: false, data: {} }));
  doc.getElementById("inbox-next").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(3)], { page: 2, has_more: false }));
  doc.getElementById("inbox-next").click();
  await flush();
  assert.deepEqual(listPages(fetch), [
    "/notifications?page=0", "/notifications?page=1", "/notifications?page=2", "/notifications?page=2",
  ]);
});

test("H4: إعادة المحاولة الناجحة تضيف الصفوف مرة واحدة بس", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(1)], { page: 0, has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 500, ok: false, data: {} }));
  doc.getElementById("inbox-next").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(2), nrow(3)], { page: 1, has_more: false }));
  doc.getElementById("inbox-next").click();
  await flush();
  const rows = dataRows(inboxList(doc));
  // OHB2-PHASE1C: الصف بقى فيه أزرار أرشفة/حذف كمان (لكل صف مُسلَّم+مقروء).
  assert.deepEqual(rows.map((r) => r.textContent), [
    "N1انتهى شاتمقروءأرشفة🗑 حذفأكّد الحذفإلغاء",
    "N2انتهى شاتمقروءأرشفة🗑 حذفأكّد الحذفإلغاء",
    "N3انتهى شاتمقروءأرشفة🗑 حذفأكّد الحذفإلغاء",
  ]);
  assert.equal(rows.length, 3, "3 صفوف بالظبط (مفيش تكرار)");
});

test("H5: فشل طلب الصفحة يحافظ على الصفوف والمعرّفات الموجودة", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(1), nrow(2)], { page: 0, has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  assert.equal(dataRows(inboxList(doc)).length, 2);
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 500, ok: false, data: {} }));
  doc.getElementById("inbox-next").click();
  await flush();
  assert.equal(dataRows(inboxList(doc)).length, 2, "الصفوف القديمة فضلت");
  // إعادة المحاولة بترجّع نفس المعرّفات ⇒ مايتكرّرش (dedup) + الجديد يتضاف.
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(2), nrow(3)], { page: 1, has_more: false }));
  doc.getElementById("inbox-next").click();
  await flush();
  const rows = dataRows(inboxList(doc));
  assert.equal(rows.length, 3, "id=2 ما اتكرّرش، id=3 اتضاف");
});

test("H6: فشل تحديث الصفحة 0 مايفسدش خط الأساس للترقيم", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(1)], { page: 0, has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(2)], { page: 1, has_more: true }));
  doc.getElementById("inbox-next").click();
  await flush();
  // تحديث الصفحة 0 يفشل ⇒ خط الأساس يفضل صفحة 1.
  fetch.route((c) => c.path.startsWith("/notifications"), () => ({ status: 500, ok: false, data: {} }));
  doc.getElementById("inbox-refresh").click();
  await flush();
  // "المزيد" التالي لازم يطلب صفحة 2 (مش صفحة 1 تاني).
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(3)], { page: 2, has_more: false }));
  doc.getElementById("inbox-next").click();
  await flush();
  assert.deepEqual(listPages(fetch), [
    "/notifications?page=0", "/notifications?page=1", "/notifications?page=0", "/notifications?page=2",
  ]);
});

test("H7: نجاح تحديث الصفحة 0 يعيد ضبط خط الأساس للترقيم", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(1)], { page: 0, has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(2)], { page: 1, has_more: true }));
  doc.getElementById("inbox-next").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(9)], { page: 0, has_more: true }));
  doc.getElementById("inbox-refresh").click();
  await flush();
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(10)], { page: 1, has_more: false }));
  doc.getElementById("inbox-next").click();
  await flush();
  assert.deepEqual(listPages(fetch), [
    "/notifications?page=0", "/notifications?page=1", "/notifications?page=0", "/notifications?page=1",
  ]);
});

test("H8: has_more=false يمنع أي طلب ترقيم إضافي", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(1)], { page: 0, has_more: false }));
  doc.getElementById("tab-inbox").click();
  await flush();
  const before = listPages(fetch).length;
  doc.getElementById("inbox-next").click();
  await flush();
  assert.equal(listPages(fetch).length, before, "مفيش طلب زايد");
});

test("H9: مزامنة الصفحة الراجعة من السيرفر بتمنع حلقة لا نهائية عند الرجوع للأولى", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(1)], { page: 0, has_more: true }));
  doc.getElementById("tab-inbox").click();
  await flush();
  // السيرفر بيرجع للأولى (page=0) لطلب صفحة مش موجودة.
  fetch.route((c) => c.path.startsWith("/notifications"), () => inboxPage([nrow(1)], { page: 0, has_more: true }));
  doc.getElementById("inbox-next").click();
  await flush();
  doc.getElementById("inbox-next").click();
  await flush();
  assert.deepEqual(listPages(fetch), [
    "/notifications?page=0", "/notifications?page=1", "/notifications?page=1",
  ], "بعد الرجوع للأولى، الطلب التالي يفضل صفحة 1 (مش بيتقدّم)");
});

test("H10: حارس الطلب الجاري يمنع الطلبات المتداخلة عبر مسار الترقيم", async () => {
  const env = await mkEnv({ deferred: true });
  const { doc, fetch } = env;
  await resolveBoot(env);
  doc.getElementById("tab-inbox").click();
  await flush();
  // صفحة 0 معلّقة: الضغط على "المزيد" مايعملش طلب.
  doc.getElementById("inbox-next").click();
  await flush();
  assert.equal(listPages(fetch).length, 1, "مفيش طلب ترقيم أثناء انتظار صفحة 0");
  fetch.last((c) => c.path.startsWith("/notifications?")).resolve(inboxPage([nrow(1)], { page: 0, has_more: true }));
  await flush();
  doc.getElementById("inbox-next").click();
  await flush();
  const callsAfterFirstNext = listPages(fetch).length;
  assert.equal(callsAfterFirstNext, 2, "طلب صفحة 1 اتsend");
  doc.getElementById("inbox-next").click();   // صفحة 1 لسه معلّقة ⇒ مفيش طلب تاني
  await flush();
  assert.equal(listPages(fetch).length, callsAfterFirstNext, "مفيش طلب متداخل");
});
