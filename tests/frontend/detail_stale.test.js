/* OHB2-09-07 (B-07-07) — انحدار: رد تفاصيل قديم مايدهسش شات أحدث.
 *
 * بيشتغل بـ Node المدمج: `node --test tests/frontend/detail_stale.test.js`
 * بيشغّل **نفس** app.js جوه بيئة DOM/شبكة مصغّرة (dom_stub.js).
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadApp, descendants, FakeFetch } = require("./dom_stub.js");

const flush = async (n = 14) => { for (let i = 0; i < n; i++) { await new Promise((r) => setImmediate(r)); } };

function resp(status, data) {
  return { status, ok: status < 400, json: () => Promise.resolve(data) };
}

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

function detailText(doc) {
  return descendants(doc.getElementById("view-detail")).map((n) => n.textContent).join(" ");
}

test("رد تفاصيل قديم مايدهسش شات أحدث اتفتح بعده", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  // قايمة فيها شاتين.
  fetch.route((c) => c.path.startsWith("/conversations?"), () => ({
    status: 200,
    data: { items: [{ id: "c1", title: "T1", status: "running" }, { id: "c2", title: "T2", status: "running" }], has_more: false },
  }));
  doc.getElementById("tab-chats").click();
  await flush();
  doc.getElementById("chats-refresh").click();
  await flush();

  // تفاصيل كل شات معلّقة لحد ما نتحكّم في ترتيب الرجوع.
  let resolveC1, resolveC2;
  fetch.route((c) => c.path === "/conversations/c1", () => new Promise((r) => { resolveC1 = r; }));
  fetch.route((c) => c.path === "/conversations/c2", () => new Promise((r) => { resolveC2 = r; }));

  const rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  assert.equal(rows.length, 2);

  rows[0].click();  // openDetail("c1") — الطلب معلّق
  await flush(2);
  rows[1].click();  // openDetail("c2") — الطلب معلّق
  await flush(2);

  // الأحدث (c2) يرجع الأول.
  resolveC2(resp(200, { id: "c2", title: "الأحدث", watched: false }));
  await flush();
  assert.ok(detailText(doc).indexOf("الأحدث") !== -1, "لازم يظهر الشات الأحدث");

  // القديم (c1) يرجع متأخّر — لازم يتجاهل.
  resolveC1(resp(200, { id: "c1", title: "قديم", watched: false }));
  await flush();
  assert.ok(detailText(doc).indexOf("الأحدث") !== -1, "عرض الشات الأحدث لازم يفضل");
  assert.ok(detailText(doc).indexOf("قديم") === -1, "رد الشات القديم مايدهسش الأحدث");
});


// C4 (BATCH-C): كل شرط في الحرس (`detailSeq` و `currentChat`) لازم يكون **قابل للرصد
// لوحده**. قبل كده كانوا متكرّرين (فتح شات مختلف = الشرطين بيمنعوا)، فإزالة شرط واحد
// ماكانتش بتتكتشف. الاختبارين دول بيعزلوا كل شرط.

test("رد فتح قديم لنفس الشات (ضغط مزدوج) مايدهسش الفتح الأحدث — عزل detailSeq", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  fetch.route((c) => c.path.startsWith("/conversations?"), () => ({
    status: 200,
    data: { items: [{ id: "c1", title: "T1", status: "running" }], has_more: false },
  }));
  doc.getElementById("tab-chats").click();
  await flush();
  doc.getElementById("chats-refresh").click();
  await flush();

  // نفس الشات مرتين ⇒ نفس currentChat لكن رقمين تسلسليين مختلفين (عزل detailSeq).
  const resolvers = [];
  fetch.route((c) => c.path === "/conversations/c1", () => new Promise((r) => { resolvers.push(r); }));
  const rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  assert.equal(rows.length, 1);

  rows[0].click();  // openDetail(c1) — seq 1
  await flush(2);
  rows[0].click();  // openDetail(c1) — seq 2 (نفس الشات)
  await flush(2);
  assert.equal(resolvers.length, 2);

  resolvers[1](resp(200, { id: "c1", title: "الأحدث", watched: false }));
  await flush();
  assert.ok(detailText(doc).indexOf("الأحدث") !== -1, "لازم يظهر الرد الأحدث");

  // الرد الأقدم (نفس الشات) يرجع متأخّر — لازم يتجاهل لأن رقمه التسلسلي أقدم.
  resolvers[0](resp(200, { id: "c1", title: "قديم", watched: false }));
  await flush();
  assert.ok(detailText(doc).indexOf("الأحدث") !== -1, "الرد الأحدث لازم يفضل");
  assert.ok(detailText(doc).indexOf("قديم") === -1, "الرد الأقدم لنفس الشات مايدهسش");
});

test("رد تفاصيل جاي بعد مغادرة الشاشة مايرسمش — عزل currentChat", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  fetch.route((c) => c.path.startsWith("/conversations?"), () => ({
    status: 200,
    data: { items: [{ id: "c1", title: "T1", status: "running" }], has_more: false },
  }));
  doc.getElementById("tab-chats").click();
  await flush();
  doc.getElementById("chats-refresh").click();
  await flush();

  let resolveC1;
  fetch.route((c) => c.path === "/conversations/c1", () => new Promise((r) => { resolveC1 = r; }));
  const rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  rows[0].click();  // openDetail(c1) — الطلب معلّق
  await flush(2);

  // نغادر شاشة التفاصيل (تنقّل) قبل ما يرجع الرد ⇒ currentChat يتصفّر.
  doc.getElementById("tab-chats").click();
  await flush();

  resolveC1(resp(200, { id: "c1", title: "متأخر", watched: false }));
  await flush();
  assert.ok(detailText(doc).indexOf("متأخر") === -1, "الرد المتأخر مايرسمش بعد مغادرة الشاشة");
});
