/* OHB2-09-05 — اختبارات انحدار واجهة تسوية الصندوق (discard/mark_sent).
 *
 * بتشغّل **نفس** app.js جوه بيئة DOM/شبكة مصغّرة (dom_stub.js)، وبتتحقّق إن
 * أزرار التسوية بتظهر للبرومتات المعلّقة وبتنادي المسار المصادَق بالإجراء الصح.
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

async function mkEnv() {
  const fake = new FakeFetch();
  const env = loadApp({ fetch: fake });
  const { doc } = env;
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => bootResponse());
  fake.route((c) => c.path.startsWith("/watches"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/notifications"), () => ({ status: 200, data: { page: 0, has_more: false, unread_count: 0, items: [] } }));
  await flush();
  return env;
}

function findButtonByText(root, text) {
  return descendants(root).find((n) => n.tagName === "BUTTON" && n.textContent === text) || null;
}

// يفتح تفاصيل شات ويرجّع عناصر مطلوبة.
// `opStatus` اختياري: رد مخصّص لاستعلام حالة العملية (GET /operations/outbox) — للاختبار
// تحت فشل شبكة/429 (OHB2-N10-05).
async function openChat(env, { opState, reconcile, opStatus }) {
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [{ id: "c1", title: "T", status: "running" }], has_more: false } }));
  fetch.route((c) => c.path === "/conversations/c1", () => ({ status: 200, data: { id: "c1", title: "T", watched: false } }));
  fetch.route((c) => c.path === "/conversations/c1/prompt", () => ({ status: 200, data: { outbox_id: 7, operation: { kind: "prompt", id: 7, state: "pending" } } }));
  fetch.route((c) => c.path.indexOf("/operations/outbox") === 0 && c.method === "GET", () => (opStatus ? opStatus() : { status: 200, data: { kind: "prompt", id: 7, conversation_id: "c1", state: opState } }));
  fetch.route((c) => c.path === "/operations/outbox/reconcile", () => (reconcile || { status: 200, data: { kind: "prompt", id: 7, state: "accepted" } }));
  doc.getElementById("tab-chats").click();
  await flush();
  const list = doc.getElementById("chats-list");
  list.children.find((c) => c.className.split(" ").includes("row")).click();
  await flush();
  const detail = doc.getElementById("view-detail");
  const textarea = descendants(detail).find((n) => n.tagName === "TEXTAREA");
  textarea.value = "شغل";
  findButtonByText(detail, "إرسال البرومت").click();
  await flush();
  env.runTimers();   // يشغّل poll الاستعلام
  await flush();
  return detail;
}

test("برومت غامض ⇒ أزرار التسوية تظهر (تأكيد الإرسال + شطب)", async () => {
  const env = await mkEnv();
  const detail = await openChat(env, { opState: "ambiguous" });
  assert.ok(findButtonByText(detail, "تأكيد الإرسال"), "زر تأكيد الإرسال لازم يظهر");
  assert.ok(findButtonByText(detail, "شطب العملية"), "زر الشطب لازم يظهر");
});

test("mark_sent بينادي المسار الصح بالإجراء الصح", async () => {
  const env = await mkEnv();
  const detail = await openChat(env, { opState: "unknown" });
  findButtonByText(detail, "تأكيد الإرسال").click();
  await flush();
  const call = env.fetch.last((c) => c.path === "/operations/outbox/reconcile");
  assert.ok(call, "لازم نداء تسوية");
  assert.equal(call.method, "POST");
  assert.deepEqual(JSON.parse(call.body), { id: 7, action: "mark_sent" });
});

test("discard بينادي المسار بالإجراء discard", async () => {
  const env = await mkEnv();
  const detail = await openChat(env, { opState: "ambiguous" });
  findButtonByText(detail, "شطب العملية").click();
  await flush();
  const call = env.fetch.last((c) => c.path === "/operations/outbox/reconcile");
  assert.equal(call.method, "POST");
  assert.deepEqual(JSON.parse(call.body), { id: 7, action: "discard" });
});

test("برومت مقبول ⇒ مفيش أزرار تسوية", async () => {
  const env = await mkEnv();
  const detail = await openChat(env, { opState: "accepted" });
  assert.equal(findButtonByText(detail, "تأكيد الإرسال"), null);
  assert.equal(findButtonByText(detail, "شطب العملية"), null);
});

test("409 من التسوية مايغيّرش الحالة المعروضة (تفضل غامضة)", async () => {
  const env = await mkEnv();
  const detail = await openChat(env, {
    opState: "ambiguous",
    reconcile: { status: 409, data: { error: "already_terminal", message: "x" } },
  });
  findButtonByText(detail, "شطب العملية").click();
  await flush();
  // الحالة المعروضة لسه "مش متأكدين" (مفيش تحديث بعد الفشل).
  const pill = descendants(detail).find((n) => n.className === "op-pill");
  assert.ok(pill && pill.textContent === "مش متأكدين", "الحالة ما اتغيّرتش بعد 409");
});

// OHB2-N10-28C: الشطب لما الإلغاء مش مؤكد (الـ POST ممكن يكون بدأ) ما لازمش يغيّر
// الحالة لـ "اتلغت" — لازم يبلّغ إن الإلغاء غير مؤكد ويسيب الحالة زي ما هي.
test("discard مع not_confirmed ⇒ الحالة ما بتتحوّلش لـ اتلغت", async () => {
  const env = await mkEnv();
  const detail = await openChat(env, {
    opState: "ambiguous",
    reconcile: { status: 200, data: { kind: "prompt", id: 7, state: "ambiguous", cancellation: "not_confirmed" } },
  });
  findButtonByText(detail, "شطب العملية").click();
  await flush();
  const texts = descendants(detail).filter((n) => n.className === "op-pill").map((n) => n.textContent);
  assert.ok(texts.includes("مش متأكدين"), "الحالة تفضل مش متأكدين");
  assert.ok(!texts.includes("اتلغت"), "مايتضافش حالة اتلغت لما الإلغاء مش مؤكد");
  const toast = env.doc.getElementById("toast");
  assert.ok(toast && (toast.textContent || "").includes("غير مؤكد"), "لازم تظهر رسالة إن الإلغاء غير مؤكد");
});

test("discard مؤكد ⇒ الحالة بتتحوّل لـ اتلغت", async () => {
  const env = await mkEnv();
  const detail = await openChat(env, {
    opState: "ambiguous",
    reconcile: { status: 200, data: { kind: "prompt", id: 7, state: "discarded", cancellation: "discarded" } },
  });
  findButtonByText(detail, "شطب العملية").click();
  await flush();
  const texts = descendants(detail).filter((n) => n.className === "op-pill").map((n) => n.textContent);
  assert.ok(texts.includes("اتلغت"), "الشطب المؤكد ⇒ حالة اتلغت تظهر");
});

// OHB2-N10-05 (F9a): ضعف الشبكة أثناء استعلام حالة العملية لازم ما يسبش الواجهة
// عالقة "قيد التنفيذ" للأبد. لازم تظهر إجراءات صريحة (استعلام/إعادة محاولة).
test("429 أثناء استعلام الحالة ⇒ مفيش علوق: إجراءات صريحة تظهر", async () => {
  const env = await mkEnv();
  const detail = await openChat(env, { opStatus: () => ({ status: 429, ok: false, data: {} }) });
  assert.ok(findButtonByText(detail, "استعلام عن الحالة"), "لازم يظهر زر استعلام بدل ما نعلّق");
  assert.ok(findButtonByText(detail, "إعادة المحاولة"), "لازم يظهر زر إعادة المحاولة");
  // الحالة المعروضة لازم تبقى "مش معروف" مش "قيد التنفيذ…" العالقة.
  const pill = descendants(detail).find((n) => n.className === "op-pill");
  assert.ok(pill && pill.textContent === "مش معروف", "الحالة تبقى مش معروف مش قيد التنفيذ");
  // OHB2-N10-05: ضمان "مفيش إعادة إرسال تلقائية" — إرسال واحد بس (الضغطة الصريحة)،
  // مفيش POST إضافي لـ /prompt بعد ما الاستعلام رجع 429.
  assert.equal(
    env.fetch.all((c) => c.method === "POST" && c.path === "/conversations/c1/prompt").length,
    1,
    "429 لازم ما يعملش إعادة إرسال تلقائية (إرسال واحد بس)",
  );
});

test("5xx أثناء استعلام الحالة ⇒ مفيش علوق: إجراءات صريحة تظهر", async () => {
  const env = await mkEnv();
  const detail = await openChat(env, { opStatus: () => ({ status: 503, ok: false, data: {} }) });
  assert.ok(findButtonByText(detail, "استعلام عن الحالة"));
});

test("فشل شبكة (رمي) أثناء استعلام الحالة ⇒ مفيش علوق", async () => {
  const env = await mkEnv();
  const detail = await openChat(env, { opStatus: () => { throw new Error("network"); } });
  assert.ok(findButtonByText(detail, "استعلام عن الحالة"), "لازم نعرض إجراءات حتى مع فشل الشبكة");
});
