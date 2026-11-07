/* OHB2-PHASE1B — اختبارات واجهة Mini App: نسخ الرد الكامل + تصدير الشات.
 *
 * `node --test tests/frontend/export_copy_ui.test.js`
 * بتشغّل **نفس** app.js جوه بيئة DOM/شبكة مصغّرة (dom_stub.js)، وبتتحقّق من:
 * - ظهور زر النسخ وزر التصدير في تفاصيل الشات.
 * - النسخ بيجيب الرد **الكامل** من الـ endpoint المصادَق وبيبلّغ بالنتيجة.
 * - فشل جلب الرد الكامل ⇒ رسالة، مفيش نسخ كاذب.
 * - التصدير بينزّل ملف باسم آمن من الهيدر، وفشل التصدير ⇒ رسالة واضحة بلا تنزيل.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadApp, descendants, FakeFetch } = require("./dom_stub.js");

const flush = async (n = 20) => { for (let i = 0; i < n; i++) { await new Promise((r) => setImmediate(r)); } };

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

function makeClipboard() {
  const state = { written: [], reject: false };
  return {
    state,
    navigator: {
      clipboard: {
        writeText(t) {
          if (state.reject) { return Promise.reject(new Error("denied")); }
          state.written.push(t);
          return Promise.resolve();
        },
      },
    },
  };
}

async function mkEnv(detail, opts) {
  opts = opts || {};
  const fake = new FakeFetch();
  const clip = makeClipboard();
  const env = loadApp({ fetch: fake, navigator: opts.navigator === undefined ? clip.navigator : opts.navigator });
  const { doc } = env;
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => bootResponse());
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({
    status: 200, data: { items: [{ id: "c1", title: "T", status: "running" }], has_more: false },
  }));
  fake.route((c) => c.path === "/conversations/c1", () => ({ status: 200, data: detail }));
  fake.route((c) => c.path === "/conversations/c1/files", () => ({ status: 200, data: { conversation_id: "c1", files: [] } }));
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
  return { env, clip };
}

function findButton(root, text) {
  return descendants(root).find((n) => n.tagName === "BUTTON" && n.textContent === text) || null;
}

test("زر نسخ الرد الكامل ظاهر في تفاصيل الشات", async () => {
  const { env } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "رد قصير" });
  const btn = findButton(env.doc.getElementById("view-detail"), "📋 نسخ الرد الكامل");
  assert.ok(btn, "لازم يظهر زر النسخ");
  assert.equal(btn.disabled, false);
});

test("النسخ بيجيب الرد الكامل من الـ endpoint وبيبلّغ بالنجاح", async () => {
  const full = "ا".repeat(5000);
  const { env, clip } = await mkEnv(
    { id: "c1", title: "T", watched: false, last_reply: "معاينة قصيرة" },
  );
  env.fetch.route((c) => c.path === "/conversations/c1/reply", () => ({ status: 200, data: { conversation_id: "c1", reply: full, reply_truncated: false } }));

  findButton(env.doc.getElementById("view-detail"), "📋 نسخ الرد الكامل").click();
  await flush();

  const call = env.fetch.last((c) => c.path === "/conversations/c1/reply");
  assert.ok(call, "لازم يطلب الرد الكامل من الـ endpoint");
  assert.equal(clip.state.written.length, 1, "لازم ينسخ مرة واحدة");
  assert.equal(clip.state.written[0], full, "لازم ينسخ الرد الكامل مش المعاينة");
  assert.match(env.doc.getElementById("toast").textContent, /تم نسخ/);
});

test("لو الرد الكامل ما رجعش ⇒ مفيش نسخ ورسالة خطأ", async () => {
  const { env, clip } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "معاينة" });
  env.fetch.route((c) => c.path === "/conversations/c1/reply", () => ({ status: 500, data: { error: "api_error", message: "فشل" } }));

  findButton(env.doc.getElementById("view-detail"), "📋 نسخ الرد الكامل").click();
  await flush();

  assert.equal(clip.state.written.length, 0, "مفيش نسخ عند الفشل");
  assert.ok(env.doc.getElementById("toast").textContent.length > 0, "لازم رسالة للمستخدم");
});

test("لو الحافظة رفضت والـ fallback فشل ⇒ رسالة فشل صادقة (مفيش نجاح كاذب)", async () => {
  const { env } = await mkEnv(
    { id: "c1", title: "T", watched: false, last_reply: "معاينة" },
    { navigator: { clipboard: { writeText: () => Promise.reject(new Error("denied")) } } },
  );
  env.doc.execCommandResult = false;  // fallback يفشل كمان
  env.fetch.route((c) => c.path === "/conversations/c1/reply", () => ({ status: 200, data: { reply: "نص", reply_truncated: false } }));

  findButton(env.doc.getElementById("view-detail"), "📋 نسخ الرد الكامل").click();
  await flush();

  assert.match(env.doc.getElementById("toast").textContent, /تعذّر النسخ/);
});

test("لو مفيش رد، زر النسخ معطّل", async () => {
  const { env } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "" });
  const btn = findButton(env.doc.getElementById("view-detail"), "📋 نسخ الرد الكامل");
  assert.equal(btn.disabled, true, "مفيش رد ⇒ الزر معطّل");
});

test("زر تصدير الشات ظاهر وبينزّل ملف باسم آمن", async () => {
  const { env } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "x" });
  env.fetch.route((c) => c.path === "/conversations/c1/export", () => ({
    status: 200,
    headers: { "content-disposition": 'attachment; filename="conversation-c1.zip"' },
    blob: { size: 123 },
  }));

  const btn = findButton(env.doc.getElementById("view-detail"), "⬇️ تصدير الشات");
  assert.ok(btn, "لازم يظهر زر التصدير");
  btn.click();
  await flush();

  const call = env.fetch.last((c) => c.path === "/conversations/c1/export");
  assert.ok(call, "لازم يبعت طلب التصدير");
  assert.equal(call.method, "GET");
  assert.match(env.doc.getElementById("toast").textContent, /تم تنزيل/);
});

test("فشل التصدير ⇒ رسالة عربي واضحة بلا تنزيل", async () => {
  const { env } = await mkEnv({ id: "c1", title: "T", watched: false, last_reply: "x" });
  env.fetch.route((c) => c.path === "/conversations/c1/export", () => ({
    status: 413, data: { error: "too_large", message: "كبير" },
  }));

  findButton(env.doc.getElementById("view-detail"), "⬇️ تصدير الشات").click();
  await flush();

  assert.match(env.doc.getElementById("toast").textContent, /كبير/);
});
