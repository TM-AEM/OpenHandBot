/* OHB2-PLAN04-UI03 — انحدار: ترقيم قايمة الشاتات لا يتخطّى صفحة عند الضغط المزدوج،
 * وفشل الطلب لا يقدّم رقم الصفحة (يعيد نفس الصفحة الفاشلة).
 *
 * بيشتغل بـ Node المدمج: `node --test tests/frontend/chats_pagination.test.js`
 * بيشغّل **نفس** app.js جوه بيئة DOM/شبكة مصغّرة (dom_stub.js) — مفيش أي نداء إنتاجي.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadApp, descendants } = require("./dom_stub.js");

const flush = async (n = 25) => { for (let i = 0; i < n; i++) { await new Promise((r) => setImmediate(r)); } };

function resp(status, data) {
  return { status, ok: status < 400, json: () => Promise.resolve(data) };
}
function R(status, data) { return { status, data }; }
function listText(doc, id) {
  return descendants(doc.getElementById(id)).map((n) => n.textContent).join(" | ");
}

async function mkEnv() {
  const env = loadApp({});
  const { fetch } = env;
  fetch.route("/auth", () => R(200, { ok: true }));
  fetch.route("/app/bootstrap", () => R(200, {
    user: { display_name: "مستخدم" },
    settings: { notifications_enabled: true },
    features: { watches: true },
    inbox: { unread_count: 0 },
  }));
  fetch.route((c) => c.path.startsWith("/watches"), () => R(200, { items: [], has_more: false }));
  fetch.route((c) => c.path.startsWith("/repositories"), () => R(200, { items: [] }));
  fetch.route((c) => c.path.startsWith("/notifications"), () => R(200, { page: 0, has_more: false, unread_count: 0, items: [] }));
  return env;
}

test("ترقيم الشاتات: الضغط المزدوج على «المزيد» لا يتخطّى صفحة", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  // الصفحة 0 تنجح بـ has_more=true (يفتح «المزيد»).
  fetch.route((c) => c.path.startsWith("/conversations?"), () => R(200, {
    page: 0, items: [{ id: "p0", title: "صفحة0", status: "running" }], has_more: true,
  }));
  doc.getElementById("tab-chats").click();
  await flush(6);

  // نداءان معلّقان على «المزيد».
  const resolvers = [];
  fetch.route((c) => c.path.startsWith("/conversations?"), () => new Promise((r) => { resolvers.push(r); }));
  doc.getElementById("chats-next").click();
  await flush(2);
  doc.getElementById("chats-next").click();
  await flush(2);

  const nextCalls = fetch.all((c) => c.path.startsWith("/conversations?") && c.path.indexOf("page=1") !== -1);
  const skipCalls = fetch.all((c) => c.path.startsWith("/conversations?") && c.path.indexOf("page=2") !== -1);
  assert.ok(nextCalls.length >= 2, "لازم طلبين على صفحة 1 (نفس الصفحة، مفيش تقديم عشوائي)");
  assert.equal(skipCalls.length, 0, "مافيش أي طلب لصفحة 2 (مفيش تخطّي صفحة)");

  // الرد الأحدث (آخر نداء) ينجح ⇒ نزامن الرقم لصفحة 1.
  resolvers[resolvers.length - 1](resp(200, { page: 1, items: [{ id: "p1", title: "صفحة1", status: "running" }], has_more: true }));
  await flush(4);
  assert.ok(listText(doc, "chats-list").indexOf("صفحة1") !== -1, "صفحة 1 تظهر بعد النجاح");
});

test("ترقيم الشاتات: فشل «المزيد» لا يقدّم رقم الصفحة (يعيد نفس الصفحة)", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  fetch.route((c) => c.path.startsWith("/conversations?"), () => R(200, {
    page: 0, items: [{ id: "p0", title: "صفحة0", status: "running" }], has_more: true,
  }));
  doc.getElementById("tab-chats").click();
  await flush(6);

  // طلب صفحة 1 يفشل بـ 500.
  fetch.route((c) => c.path.startsWith("/conversations?"), () => R(500, { message: "الخدمة مش متاحة دلوقتي، جرّب تاني." }));
  doc.getElementById("chats-next").click();
  await flush(6);
  assert.ok(listText(doc, "chats-list").indexOf("مش متاحة") !== -1, "رسالة الفشل تظهر");

  // الضغط التاني يعيد **نفس** الصفحة (1) — لا يتخطاها لصفحة 2.
  doc.getElementById("chats-next").click();
  await flush(6);
  const p2 = fetch.all((c) => c.path.startsWith("/conversations?") && c.path.indexOf("page=2") !== -1);
  assert.equal(p2.length, 0, "مافيش طلب لصفحة 2 بعد فشل صفحة 1");
});

test("ترقيم الشاتات: بلا has_more، «المزيد» لا يبعت أي طلب", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  fetch.route((c) => c.path.startsWith("/conversations?"), () => R(200, {
    page: 0, items: [{ id: "p0", title: "صفحة0", status: "running" }], has_more: false,
  }));
  doc.getElementById("tab-chats").click();
  await flush(6);

  const before = fetch.all((c) => c.path.startsWith("/conversations?")).length;
  doc.getElementById("chats-next").click();
  await flush(4);
  const after = fetch.all((c) => c.path.startsWith("/conversations?")).length;
  assert.equal(after, before, "مفيش طلب ترقيم جديد لما has_more=false");
});
