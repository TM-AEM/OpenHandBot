/* OHB2-09-BATCH-C (FC2 §4.3) — تغطية إضافية لحرس الردود القديمة في شاشة التفاصيل.
 *
 * الاختبارات دي بتكمّل `detail_stale.test.js` وبتضيف مسارين لسه مش متغطّيين صراحةً
 * (الخطأ والتحميل). وكل اختبار **بيعزل شرط واحد** من الحرس (`detailSeq` أو `currentChat`)
 * عشان إزالة الشرط ده لوحدها تبان (زي متطلّب C4). لو الشرطين اتغيّروا مع بعض (شات مختلف)
 * كانوا بيمنعوا الرد القديم سوا، فمكانوش بيعزلوا شرط واحد.
 *
 * بيشتغل بـ Node المدمج: `node --test tests/frontend/detail_stale_extra.test.js`
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

const M500 = "الخدمة مش متاحة دلوقتي، جرّب تاني.";
const M404 = "حصل خطأ غير متوقع، جرّب تاني.";

// تجهيز قايمة فيها شات واحد (c1) وفتح تبويب الشاتات.
async function openOneChat(env) {
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/conversations?"), () => ({
    status: 200,
    data: { items: [{ id: "c1", title: "T1", status: "running" }], has_more: false },
  }));
  doc.getElementById("tab-chats").click();
  await flush();
  doc.getElementById("chats-refresh").click();
  await flush();
  const rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  assert.equal(rows.length, 1);
  return rows[0];
}

test("خطأ قديم لنفس الشات مايدهسش خطأ أحدث — عزل detailSeq على مسار الخطأ", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  const row = await openOneChat(env);

  // نفس الشات مرتين ⇒ نفس currentChat لكن رقمين تسلسليين مختلفين (عزل detailSeq).
  const resolvers = [];
  fetch.route((c) => c.path === "/conversations/c1", () => new Promise((r) => { resolvers.push(r); }));

  row.click();  // openDetail(c1) — seq 1
  await flush(2);
  row.click();  // openDetail(c1) — seq 2
  await flush(2);
  assert.equal(resolvers.length, 2);

  // الأحدث (seq 2) يرجع خطأ 500 ⇒ رسالة "الخدمة مش متاحة".
  resolvers[1](resp(500, { error: "api_error" }));
  await flush();
  assert.ok(detailText(doc).indexOf(M500) !== -1, "لازم تظهر حالة خطأ الطلب الأحدث");

  // الأقدم (seq 1) يرجع خطأ 404 متأخّر — لازم يتجاهل (نفس currentChat لكن seq أقدم).
  resolvers[0](resp(404, { error: "not_found" }));
  await flush();
  assert.ok(detailText(doc).indexOf(M500) !== -1, "خطأ الطلب الأقدم مايغيّرش خطأ الأحدث");
  assert.ok(detailText(doc).indexOf(M404) === -1, "خطأ الطلب الأقدم مايرسمش خالص");
});

test("اكتمال طلب قديم لنفس الشات مايمسحش تحميل الطلب الأحدث — عزل detailSeq على مسار التحميل", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  const row = await openOneChat(env);

  const resolvers = [];
  fetch.route((c) => c.path === "/conversations/c1", () => new Promise((r) => { resolvers.push(r); }));

  row.click();  // seq 1 (تحميل)
  await flush(2);
  row.click();  // seq 2 (تحميل) — الأحدث، نفس الشات
  await flush(2);
  assert.ok(detailText(doc).indexOf("بيتم التحميل") !== -1, "لازم يبان مؤشّر تحميل الطلب الأحدث");

  // الأقدم (seq 1) يخلص الأول — لازم مايرسمش ومايمسحش تحميل الأحدث (نفس currentChat).
  resolvers[0](resp(200, { id: "c1", title: "قديم", watched: false }));
  await flush();
  assert.ok(detailText(doc).indexOf("بيتم التحميل") !== -1, "اكتمال الطلب الأقدم مايمسحش تحميل الأحدث");
  assert.ok(detailText(doc).indexOf("قديم") === -1, "الرد الأقدم مايرسمش");

  // الأحدث (seq 2) يخلص ⇒ يستبدل التحميل ببياناته.
  resolvers[1](resp(200, { id: "c1", title: "الأحدث", watched: false }));
  await flush();
  assert.ok(detailText(doc).indexOf("الأحدث") !== -1, "الأحدث يرسم بعد ما يخلص");
  assert.ok(detailText(doc).indexOf("بيتم التحميل") === -1, "مؤشّر التحميل اتشال لما الأحدث خلص");
});

test("خطأ جاي بعد مغادرة الشاشة مايرسمش — عزل currentChat على مسار الخطأ", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;
  const row = await openOneChat(env);

  let resolveC1;
  fetch.route((c) => c.path === "/conversations/c1", () => new Promise((r) => { resolveC1 = r; }));
  row.click();  // openDetail(c1) — الطلب معلّق
  await flush(2);

  // نغادر شاشة التفاصيل قبل ما يرجع الخطأ ⇒ currentChat يتصفّر (لكن detailSeq ثابت).
  doc.getElementById("tab-chats").click();
  await flush();

  resolveC1(resp(500, { error: "api_error" }));
  await flush();
  assert.ok(detailText(doc).indexOf(M500) === -1, "خطأ الرد المتأخر مايرسمش بعد مغادرة الشاشة");
});
