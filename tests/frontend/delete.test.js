/* OHB2-C7 — اختبارات انحدار واجهة حذف الشات (Mini App).
 *
 * بتشتغل بـ Node المدمج: `node --test tests/frontend/delete.test.js`
 * بتشغّل **نفس** app.js جوه بيئة DOM/شبكة مصغّرة (dom_stub.js).
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadApp, descendants, FakeFetch } = require("./dom_stub.js");

const flush = async (n = 14) => { for (let i = 0; i < n; i++) { await new Promise((r) => setImmediate(r)); } };

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

async function mkEnv() {
  const fake = new FakeFetch();
  const env = loadApp({ fetch: fake });
  const { doc } = env;
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => bootResponse());
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/watches"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/notifications"), () => ({ status: 200, data: { page: 0, has_more: false, unread_count: 0, items: [] } }));
  await flush();
  return env;
}

function findButton(root, text) {
  return descendants(root).find((n) => n.tagName === "BUTTON" && n.textContent === text) || null;
}

async function openDetail(env, detail) {
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/conversations?"), () => ({
    status: 200, data: { items: [{ id: "c1", title: "T", status: "running" }], has_more: false },
  }));
  fetch.route((c) => c.path === "/conversations/c1", () => ({ status: 200, data: detail }));
  fetch.route((c) => c.path === "/conversations/c1/files", () => ({ status: 200, data: { conversation_id: "c1", files: [] } }));
  doc.getElementById("tab-chats").click();
  await flush();
  doc.getElementById("chats-refresh").click();
  await flush();
  const rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  rows[0].click();
  await flush();
  return env;
}

test("زر الحذف ظاهر ويطلب تأكيد قبل التنفيذ (مفيش حذف فوري)", async () => {
  const env = await mkEnv();
  await openDetail(env, { id: "c1", title: "T", watched: false });
  const { doc, fetch } = env;

  const delBtn = findButton(doc.getElementById("view-detail"), "🗑 حذف الشات");
  assert.ok(delBtn, "لازم يظهر زر الحذف");
  delBtn.click();
  await flush();

  // لسه مفيش أي نداء DELETE اتبعت.
  assert.equal(fetch.all((c) => c.method === "DELETE").length, 0, "الضغطة الأولى ما بتحذفش");
  const confirm = findButton(doc.getElementById("view-detail"), "🗑 أكّد الحذف");
  assert.ok(confirm && confirm.hidden === false, "لازم يظهر زر التأكيد");
});

test("التأكيد يبعت DELETE ويرجّع لقايمة الشاتات", async () => {
  const env = await mkEnv();
  await openDetail(env, { id: "c1", title: "T", watched: false });
  const { doc, fetch } = env;

  findButton(doc.getElementById("view-detail"), "🗑 حذف الشات").click();
  await flush();
  findButton(doc.getElementById("view-detail"), "🗑 أكّد الحذف").click();
  await flush();

  const call = fetch.last((c) => c.method === "DELETE" && c.path === "/conversations/c1");
  assert.ok(call, "لازم يبعت DELETE على مسار الشات");
  assert.equal(doc.getElementById("view-detail").hidden, true, "نرجع لقايمة الشاتات");
  assert.equal(doc.getElementById("view-chats").hidden, false);
});

test("إلغاء التأكيد مايبعتش أي DELETE", async () => {
  const env = await mkEnv();
  await openDetail(env, { id: "c1", title: "T", watched: false });
  const { doc, fetch } = env;

  findButton(doc.getElementById("view-detail"), "🗑 حذف الشات").click();
  await flush();
  findButton(doc.getElementById("view-detail"), "إلغاء").click();
  await flush();

  assert.equal(fetch.all((c) => c.method === "DELETE").length, 0, "الإلغاء مايحذفش");
  assert.ok(findButton(doc.getElementById("view-detail"), "🗑 حذف الشات").hidden === false, "زر الحذف رجع ظاهر");
});

test("الضغط المزدوج على التأكيد مايبعتش DELETE مرتين", async () => {
  const env = await mkEnv();
  await openDetail(env, { id: "c1", title: "T", watched: false });
  const { doc, fetch } = env;

  findButton(doc.getElementById("view-detail"), "🗑 حذف الشات").click();
  await flush();
  const confirm = findButton(doc.getElementById("view-detail"), "🗑 أكّد الحذف");
  confirm.click();
  confirm.click();  // ضغط مزدوج
  await flush();

  const dels = fetch.all((c) => c.method === "DELETE" && c.path === "/conversations/c1");
  assert.equal(dels.length, 1, "الحذف مرة واحدة بس (منع التكرار)");
});

test("فشل الحذف (403) يعرض رسالة ويفضل على الشاشة (retryable)", async () => {
  const env = await mkEnv();
  await openDetail(env, { id: "c1", title: "T", watched: false });
  const { doc, fetch } = env;

  fetch.route((c) => c.method === "DELETE", () => ({ status: 403, data: { error: "unauthorized" } }));
  findButton(doc.getElementById("view-detail"), "🗑 حذف الشات").click();
  await flush();
  findButton(doc.getElementById("view-detail"), "🗑 أكّد الحذف").click();
  await flush();

  assert.equal(doc.getElementById("view-detail").hidden, false, "نفضل على التفاصيل عند الفشل");
  const toast = doc.getElementById("toast");
  assert.equal(toast.hidden, false, "لازم تبان رسالة خطأ");
  assert.ok(toast.textContent.indexOf("مش مسموح") !== -1, "رسالة عربية واضحة (مش تفاصيل خام)");
});

// ---------------------------------------------- PHASE6-UI: reachability & naming
function findText(root, needle) {
  return descendants(root).find(
    (n) => typeof n.textContent === "string" && n.textContent.indexOf(needle) !== -1
  ) || null;
}

test("زر الحذف متاح من قايمة الشاتات نفسها (reachable من القايمة)", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/conversations?"), () => ({
    status: 200,
    data: { items: [{ id: "c1", title: "T", status: "running" }], has_more: false },
  }));
  fetch.route((c) => c.path === "/conversations/c1", () => ({ status: 200, data: { id: "c1", title: "T" } }));
  fetch.route((c) => c.path === "/conversations/c1/files", () => ({ status: 200, data: { conversation_id: "c1", files: [] } }));

  // من قايمة الشاتات: نضغط على صف الشات (مش نداء مباشر للتفاصيل).
  doc.getElementById("tab-chats").click();
  await flush();
  doc.getElementById("chats-refresh").click();
  await flush();
  const rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  assert.equal(rows.length, 1, "صف الشات ظاهر في القايمة");
  rows[0].click();
  await flush();

  // بعد الوصول من القايمة، زر الحذف لازم يكون ظاهر ومرئي.
  const delBtn = findButton(doc.getElementById("view-detail"), "🗑 حذف الشات");
  assert.ok(delBtn, "زر الحذف لازم يكون متاح من القايمة");
  assert.equal(delBtn.hidden, false, "زر الحذف ظاهر مش مخفي");
});

test("التأكيد بيسمّي الشات المطلوب حذفه (مفيش حذف بالغلط)", async () => {
  const env = await mkEnv();
  await openDetail(env, { id: "c1", title: "مشروع أبولو", watched: false });
  const { doc, fetch } = env;
  const view = doc.getElementById("view-detail");

  const note = findText(view, "متأكد إنك عايز تحذف");
  assert.ok(note, "لازم يكون فيه نص تأكيد");
  assert.ok(note.textContent.indexOf("مشروع أبولو") !== -1, "نص التأكيد بيسمّي الشات");
  assert.equal(note.hidden, true, "نص التأكيد مخفي قبل الضغط");

  findButton(view, "🗑 حذف الشات").click();
  await flush();
  assert.equal(note.hidden, false, "نص التأكيد يظهر بعد الضغط");
  assert.equal(fetch.all((c) => c.method === "DELETE").length, 0, "لسه مفيش DELETE قبل التأكيد");
});

test("إلغاء التأكيد يخفي نص التأكيد ويرجّع زر الحذف من غير DELETE", async () => {
  const env = await mkEnv();
  await openDetail(env, { id: "c1", title: "T", watched: false });
  const { doc, fetch } = env;
  const view = doc.getElementById("view-detail");

  findButton(view, "🗑 حذف الشات").click();
  await flush();
  findButton(view, "إلغاء").click();
  await flush();

  assert.equal(fetch.all((c) => c.method === "DELETE").length, 0, "الإلغاء مايبعتش DELETE");
  assert.equal(findText(view, "متأكد إنك عايز تحذف").hidden, true, "نص التأكيد اتخفي بعد الإلغاء");
  assert.equal(findButton(view, "🗑 حذف الشات").hidden, false, "زر الحذف رجع ظاهر");

  // إعادة الفتح شغّالة عادي.
  findButton(view, "🗑 حذف الشات").click();
  await flush();
  assert.equal(findButton(view, "🗑 أكّد الحذف").hidden, false, "نقدر نعيد فتح التأكيد");
});

test("بعد نجاح الحذف الشات بيختفي من القايمة فورًا (من غير restart)", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  let deleted = false;
  fetch.route((c) => c.path.startsWith("/conversations?"), () => ({
    status: 200,
    data: deleted
      ? { items: [], has_more: false }
      : { items: [{ id: "c1", title: "T", status: "running" }], has_more: false },
  }));
  fetch.route((c) => c.path === "/conversations/c1", () => ({ status: 200, data: { id: "c1", title: "T" } }));
  fetch.route((c) => c.path === "/conversations/c1/files", () => ({ status: 200, data: { conversation_id: "c1", files: [] } }));
  fetch.route((c) => c.method === "DELETE" && c.path === "/conversations/c1", () => {
    deleted = true;
    return { status: 200, data: { ok: true, deleted: true, remote_deleted: true } };
  });

  doc.getElementById("tab-chats").click();
  await flush();
  doc.getElementById("chats-refresh").click();
  await flush();
  let rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  assert.equal(rows.length, 1, "الشات ظاهر قبل الحذف");
  rows[0].click();
  await flush();

  findButton(doc.getElementById("view-detail"), "🗑 حذف الشات").click();
  await flush();
  findButton(doc.getElementById("view-detail"), "🗑 أكّد الحذف").click();
  await flush();

  rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  assert.equal(rows.length, 0, "الشات اختفى من القايمة بعد الحذف");
  assert.equal(doc.getElementById("view-chats").hidden, false, "رجعنا لقايمة الشاتات");
});

// ---------------------------------------------- OHB2-MINIAPP: remote deletion UX
test("نص التأكيد بيقول إن الحذف من OpenHands (مش محلي)", async () => {
  const env = await mkEnv();
  await openDetail(env, { id: "c1", title: "T", watched: false });
  const { doc } = env;
  const view = doc.getElementById("view-detail");

  const note = findText(view, "متأكد إنك عايز تحذف");
  assert.ok(note, "لازم يكون فيه نص تأكيد");
  assert.ok(note.textContent.indexOf("OpenHands") !== -1, "النص يوضّح إن الحذف من OpenHands");
  assert.equal(note.textContent.indexOf("حذف محلي"), -1, "مفيش ادّعاء حذف محلي");
});

test("نجاح الحذف البعيد يرجّع للقايمة برسالة نجاح", async () => {
  const env = await mkEnv();
  await openDetail(env, { id: "c1", title: "T", watched: false });
  const { doc, fetch } = env;

  fetch.route((c) => c.method === "DELETE" && c.path === "/conversations/c1", () => ({
    status: 200, data: { ok: true, deleted: true, remote_deleted: true },
  }));

  findButton(doc.getElementById("view-detail"), "🗑 حذف الشات").click();
  await flush();
  findButton(doc.getElementById("view-detail"), "🗑 أكّد الحذف").click();
  await flush();

  assert.equal(doc.getElementById("view-chats").hidden, false, "رجعنا لقايمة الشاتات");
  const toast = doc.getElementById("toast");
  assert.equal(toast.hidden, false, "لازم تبان رسالة نجاح");
  assert.ok(toast.textContent.indexOf("OpenHands") !== -1, "الرسالة تذكر OpenHands");
});
