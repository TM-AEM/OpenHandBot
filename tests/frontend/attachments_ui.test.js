/* OHB2-MT-2 — اختبارات واجهة Mini App: قسم المرفقات المحلية + التنزيل.
 *
 * `node --test tests/frontend/attachments_ui.test.js`
 * بتشغّل **نفس** app.js جوه بيئة DOM/شبكة مصغّرة (dom_stub.js)، وبتتحقّق من:
 * - ظهور قسم المرفقات وقايمة العناصر الآمنة.
 * - التنزيل بيبعت طلب same-origin للمسار المصادَق وبيعمله blob download.
 * - فشل/انتهاء المهلة/شبكة ⇒ رسالة عربي واضحة **بلا** تنزيل.
 * - الصدق: الرسائل بتفرّق بين التنزيل المحلي والتسليم لـ OpenHands.
 * - ضغط مكرّر ⇒ طلب واحد بس (مفيش تنزيلات مكرّرة).
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadApp, descendants, FakeFetch } = require("./dom_stub.js");

const flush = async (n = 25) => { for (let i = 0; i < n; i++) { await new Promise((r) => setImmediate(r)); } };

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

async function mkEnv(detail, opts) {
  opts = opts || {};
  const fake = new FakeFetch();
  const env = loadApp({ fetch: fake, navigator: opts.navigator || null });
  const { doc } = env;
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => bootResponse());
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({
    status: 200, data: { items: [{ id: "c1", title: "T", status: "running" }], has_more: false },
  }));
  fake.route((c) => c.path === "/conversations/c1", () => ({ status: 200, data: detail }));
  fake.route((c) => c.path === "/conversations/c1/files", () => ({ status: 200, data: { conversation_id: "c1", files: [] } }));
  fake.route((c) => c.path === "/conversations/c1/attachments", () => ({ status: 200, data: { items: [], expires_in: 0 } }));
  fake.route((c) => c.path.startsWith("/watches"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/notifications"), () => ({ status: 200, data: { page: 0, has_more: false, unread_count: 0, items: [] } }));
  await flush();
  doc.getElementById("tab-chats").click();
  await flush();
  doc.getElementById("chats-refresh").click();
  await flush();
  const rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  rows[0].click();
  await flush();
  return { env };
}

function findButton(root, text) {
  return descendants(root).find((n) => n.tagName === "BUTTON" && n.textContent === text) || null;
}

const ITEM = { item_id: "i1", display_name: "note.txt", size_bytes: 2048, expires_in: 600 };

test("قسم المرفقات بيظهر وبيسرد العناصر الآمنة", async () => {
  const { env } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "x" });
  env.fetch.route((c) => c.path === "/conversations/c1/attachments", () => ({
    status: 200, data: { items: [ITEM], expires_in: 600 },
  }));
  // نعيد فتح التفاصيل لتحديث القسم بالبيانات الجديدة.
  env.doc.getElementById("chats-list").children
    .filter((c) => c.className.split(" ").includes("row"))[0].click();
  await flush();

  const detail = env.doc.getElementById("view-detail");
  const btn = findButton(detail, "⬇️ تنزيل");
  assert.ok(btn, "لازم يظهر زر تنزيل للعنصر");
  const text = descendants(detail).map((n) => n.textContent).join(" ");
  assert.match(text, /note\.txt/, "اسم الملف يظهر");
  assert.match(text, /محلي/, "النص يوضّح إنه تخزين محلي مش تسليم");
});

test("التنزيل بيبعت طلب same-origin وبيعمل blob download برسالة صادقة", async () => {
  const { env } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "x" });
  env.fetch.route((c) => c.path === "/conversations/c1/attachments", () => ({
    status: 200, data: { items: [ITEM], expires_in: 600 },
  }));
  env.fetch.route((c) => c.path === "/conversations/c1/attachments/i1/download", () => ({
    status: 200,
    headers: { "content-disposition": 'attachment; filename="note.txt"' },
    blob: { size: 2048 },
  }));
  env.doc.getElementById("chats-list").children
    .filter((c) => c.className.split(" ").includes("row"))[0].click();
  await flush();

  const btn = findButton(env.doc.getElementById("view-detail"), "⬇️ تنزيل");
  assert.ok(btn);
  btn.click();
  await flush();

  const call = env.fetch.last((c) => c.path === "/conversations/c1/attachments/i1/download");
  assert.ok(call, "لازم يبعت طلب التنزيل");
  assert.equal(call.method, "GET");
  assert.equal(call.options.credentials, "same-origin", "الطلب same-origin مصادَق");
  // عمل objectURL (تنزيل فعلي) ثم بيبطّله بعد مؤقّت (تشغيل المؤقّتات المخزّنة).
  assert.equal(Object.keys(env.sandbox.URL._urls).length, 1, "اتعمل objectURL للتنزيل");
  env.runTimers();
  assert.equal(Object.keys(env.sandbox.URL._urls).length, 0, "الـ objectURL اتبطّل بعد الاستخدام");
  const toast = env.doc.getElementById("toast").textContent;
  assert.match(toast, /نزّلنا الملف/, "رسالة نجاح التنزيل");
  assert.match(toast, /مش معناه إن OpenHands استلمه/, "الصدق: مش تسليم");
});

test("ضغط مكرّر سريع ⇒ طلب تنزيل واحد بس", async () => {
  const { env } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "x" });
  env.fetch.route((c) => c.path === "/conversations/c1/attachments", () => ({
    status: 200, data: { items: [ITEM], expires_in: 600 },
  }));
  env.fetch.route((c) => c.path === "/conversations/c1/attachments/i1/download", () => ({
    status: 200, headers: { "content-disposition": 'attachment; filename="note.txt"' }, blob: { size: 1 },
  }));
  env.doc.getElementById("chats-list").children
    .filter((c) => c.className.split(" ").includes("row"))[0].click();
  await flush();

  const btn = findButton(env.doc.getElementById("view-detail"), "⬇️ تنزيل");
  btn.click();
  btn.click();
  btn.click();
  await flush();
  const calls = env.fetch.all((c) => c.path === "/conversations/c1/attachments/i1/download");
  assert.equal(calls.length, 1, "ضغط مكرّر ⇒ طلب واحد");
});

test("انتهاء المهلة (410) ⇒ رسالة واضحة بلا تنزيل", async () => {
  const { env } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "x" });
  env.fetch.route((c) => c.path === "/conversations/c1/attachments", () => ({
    status: 200, data: { items: [ITEM], expires_in: 600 },
  }));
  env.fetch.route((c) => c.path === "/conversations/c1/attachments/i1/download", () => ({
    status: 410, data: { error: "expired", message: "انتهت" },
  }));
  env.doc.getElementById("chats-list").children
    .filter((c) => c.className.split(" ").includes("row"))[0].click();
  await flush();

  findButton(env.doc.getElementById("view-detail"), "⬇️ تنزيل").click();
  await flush();
  assert.match(env.doc.getElementById("toast").textContent, /15 دقيقة/);
});

test("انتهاء الجلسة (401) ⇒ رسالة إعادة الدخول", async () => {
  const { env } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "x" });
  env.fetch.route((c) => c.path === "/conversations/c1/attachments", () => ({
    status: 200, data: { items: [ITEM], expires_in: 600 },
  }));
  env.fetch.route((c) => c.path === "/conversations/c1/attachments/i1/download", () => ({
    status: 401, data: { error: "unauthenticated", message: "لا" },
  }));
  env.doc.getElementById("chats-list").children
    .filter((c) => c.className.split(" ").includes("row"))[0].click();
  await flush();

  findButton(env.doc.getElementById("view-detail"), "⬇️ تنزيل").click();
  await flush();
  assert.match(env.doc.getElementById("toast").textContent, /الجلسة/);
});

test("فشل الشبكة ⇒ رسالة انقطاع بلا تنزيل", async () => {
  const { env } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "x" });
  env.fetch.route((c) => c.path === "/conversations/c1/attachments", () => ({
    status: 200, data: { items: [ITEM], expires_in: 600 },
  }));
  env.fetch.route((c) => c.path === "/conversations/c1/attachments/i1/download", () => {
    throw new Error("network down");
  });
  env.doc.getElementById("chats-list").children
    .filter((c) => c.className.split(" ").includes("row"))[0].click();
  await flush();

  findButton(env.doc.getElementById("view-detail"), "⬇️ تنزيل").click();
  await flush();
  assert.match(env.doc.getElementById("toast").textContent, /التنزيل اتقطع/);
  assert.equal(Object.keys(env.sandbox.URL._urls).length, 0, "مفيش تنزيل عند الفشل");
});

test("قايمة فاضية ⇒ رسالة «مفيش مرفقات»", async () => {
  const { env } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "x" });
  const detail = env.doc.getElementById("view-detail");
  const text = descendants(detail).map((n) => n.textContent).join(" ");
  assert.match(text, /مفيش مرفقات جاهزة/, "حالة القايمة الفاضية واضحة");
});
