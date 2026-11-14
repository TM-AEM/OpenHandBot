/* OHB2-PHASE1D — اختبارات واجهة "طلبات البدء" في الـ Mini App.
 *
 * بتشغّل **نفس** app.js جوه بيئة DOM/شبكة مصغّرة (dom_stub.js)، وبتتحقّق إن:
 *   - القايمة بتعرض حالة كل طلب مع وصف حدّ الإرسال.
 *   - أزرار الإلغاء/الحسم بتظهر بس حسب أعلام السيرفر، وبتنادي المسار المصادَق بالإجراء الصح.
 *   - الطلب الغامض ما بيعرضش زرار إلغاء (fail closed) وبيظهر له زرار تأكيد البدء.
 *   - الطلب النهائي مفيش عليه أي أزرار تغيير حالة.
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

function job(over) {
  return Object.assign({
    kind: "creation", id: 1, repository: "o/r", state: "pending",
    post_state: "not_started", terminal: false, cancellable: true, resolvable: false,
    conversation_id: "", created_at: "t", updated_at: "t",
  }, over || {});
}

async function mkEnv(listResponse) {
  const fake = new FakeFetch();
  const env = loadApp({ fetch: fake });
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => bootResponse());
  fake.route((c) => c.path.startsWith("/watches"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/operations/creation/list"), () => (listResponse || { status: 200, data: { page: 0, has_more: false, items: [job()] } }));
  fake.route((c) => c.path === "/operations/creation/reconcile", () => ({ status: 200, data: job({ state: "discarded", post_state: "cancelled", terminal: true, cancellable: false, cancellation: "discarded" }) }));
  await flush();
  env.doc.getElementById("tab-jobs").click();
  await flush();
  return env;
}

function findButtonByText(root, text) {
  return descendants(root).find((n) => n.tagName === "BUTTON" && n.textContent === text) || null;
}

test("قايمة الطلبات بتعرض الحالة ووصف حدّ الإرسال", async () => {
  const env = await mkEnv();
  const list = env.doc.getElementById("jobs-list");
  const text = descendants(list).map((n) => n.textContent).join(" ");
  assert.ok(text.includes("قيد التنفيذ"), "لازم تعرض الحالة");
  assert.ok(text.includes("لسه مابدأش"), "لازم تعرض حدّ الإرسال");
});

test("طلب pending ⇒ زرار الإلغاء يظهر (بعد علم السيرفر)", async () => {
  const env = await mkEnv();
  const list = env.doc.getElementById("jobs-list");
  assert.ok(findButtonByText(list, "إلغاء الطلب"), "زرار الإلغاء لازم يظهر للطلب المؤهّل");
  assert.equal(findButtonByText(list, "أكّد إنه بدأ"), null, "مفيش حسم لطلب مش غامض");
});

test("الإلغاء بينادي المسار الصح بالإجراء cancel (بتأكيد خطوتين)", async () => {
  const env = await mkEnv();
  const list = env.doc.getElementById("jobs-list");
  findButtonByText(list, "إلغاء الطلب").click();
  await flush();
  findButtonByText(list, "أكّد الإلغاء").click();
  await flush();
  const call = env.fetch.last((c) => c.path === "/operations/creation/reconcile");
  assert.ok(call, "لازم نداء تسوية");
  assert.equal(call.method, "POST");
  assert.deepEqual(JSON.parse(call.body), { id: 1, action: "cancel" });
});

test("طلب غامض ⇒ مفيش زرار إلغاء، وبيظهر زرار تأكيد البدء", async () => {
  const env = await mkEnv({ status: 200, data: { page: 0, has_more: false, items: [job({ state: "ambiguous", post_state: "uncertain", cancellable: false, resolvable: true })] } });
  const list = env.doc.getElementById("jobs-list");
  assert.equal(findButtonByText(list, "إلغاء الطلب"), null, "مايعرضش إلغاء لطلب غامض (fail closed)");
  assert.ok(findButtonByText(list, "أكّد إنه بدأ"), "لازم يظهر تأكيد البدء");
});

test("تأكيد البدء بينادي mark_sent (بتأكيد خطوتين)", async () => {
  const env = await mkEnv({ status: 200, data: { page: 0, has_more: false, items: [job({ state: "ambiguous", post_state: "uncertain", cancellable: false, resolvable: true })] } });
  const list = env.doc.getElementById("jobs-list");
  findButtonByText(list, "أكّد إنه بدأ").click();
  await flush();
  findButtonByText(list, "تأكيد نهائي").click();
  await flush();
  const call = env.fetch.last((c) => c.path === "/operations/creation/reconcile");
  assert.deepEqual(JSON.parse(call.body), { id: 1, action: "mark_sent" });
});

test("طلب نهائي (done) ⇒ مفيش أي أزرار تغيير حالة", async () => {
  const env = await mkEnv({ status: 200, data: { page: 0, has_more: false, items: [job({ state: "accepted", post_state: "started", terminal: true, cancellable: false, resolvable: false, conversation_id: "c1" })] } });
  const list = env.doc.getElementById("jobs-list");
  assert.equal(findButtonByText(list, "إلغاء الطلب"), null);
  assert.equal(findButtonByText(list, "أكّد إنه بدأ"), null);
  assert.ok(findButtonByText(list, "افتح الشات"), "لازم يظهر فتح الشات لما فيه معرّف");
});

test("409 من الإلغاء مايغيّرش الواجهة لعرض نجاح كاذب", async () => {
  const env = await mkEnv();
  env.fetch.route((c) => c.path === "/operations/creation/reconcile", () => ({ status: 409, data: { error: "already_terminal", message: "x" } }));
  const list = env.doc.getElementById("jobs-list");
  findButtonByText(list, "إلغاء الطلب").click();
  await flush();
  findButtonByText(list, "أكّد الإلغاء").click();
  await flush();
  const toast = env.doc.getElementById("toast");
  assert.ok(toast && !(toast.textContent || "").includes("اتلغى قبل الإرسال"), "مايظهرش نجاح كاذب بعد 409");
});

test("wiring: index.html بيحمّل jobs.js قبل app.js", () => {
  const fs = require("node:fs");
  const path = require("node:path");
  const html = fs.readFileSync(path.resolve(__dirname, "../../bot/web/static/index.html"), "utf8");
  const jobsIdx = html.indexOf('src="/mini/jobs.js');
  const appIdx = html.indexOf('src="/mini/app.js');
  assert.ok(jobsIdx !== -1 && appIdx !== -1 && jobsIdx < appIdx, "jobs.js لازم يتحمّل قبل app.js");
});

test("قايمة الحذف البعيد المعلّق بتتعرض وتسوّي يدويًا بتأكيد خطوتين", async () => {
  const fake = new FakeFetch();
  const env = loadApp({ fetch: fake });
  let pendingItems = [{ conversation_id: "c-pend", state: "uncertain", updated_at: "2026-01-01T00:00:00Z" }];
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => bootResponse());
  fake.route((c) => c.path.startsWith("/watches"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/operations/creation/list"), () => ({ status: 200, data: { page: 0, has_more: false, items: [] } }));
  fake.route("/operations/deletions/list", () => ({ status: 200, data: { items: pendingItems } }));
  fake.route("/operations/deletions/reconcile", () => {
    pendingItems = [];
    return { status: 200, data: { ok: true, deleted: true, status: "deleted", message: "اتحذف الشات نهائيًا من OpenHands ✅" } };
  });

  await flush();
  env.doc.getElementById("tab-jobs").click();
  await flush();

  const delList = env.doc.getElementById("deletions-list");
  const text = descendants(delList).map((n) => n.textContent).join(" ");
  assert.ok(text.includes("c-pend"));
  assert.ok(text.includes("غير محسوم"));

  findButtonByText(delList, "تحقق الآن").click();
  await flush();
  const confirm = findButtonByText(delList, "أكّد التحقق");
  assert.ok(confirm);
  confirm.click();
  confirm.click(); // منع الضغط المزدوج
  await flush();

  const calls = env.fetch.all((c) => c.path === "/operations/deletions/reconcile");
  assert.equal(calls.length, 1);
  assert.deepEqual(JSON.parse(calls[0].body), { conversation_id: "c-pend" });
  assert.match(env.doc.getElementById("toast").textContent, /اتحذف/);
});

test("فشل تسوية الحذف (503/502) ما يعرضش نجاح كاذب", async () => {
  const fake = new FakeFetch();
  const env = loadApp({ fetch: fake });
  fake.route("/auth", () => ({ status: 200, data: { ok: true } }));
  fake.route("/app/bootstrap", () => bootResponse());
  fake.route((c) => c.path.startsWith("/watches"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/conversations?"), () => ({ status: 200, data: { items: [], has_more: false } }));
  fake.route((c) => c.path.startsWith("/operations/creation/list"), () => ({ status: 200, data: { page: 0, has_more: false, items: [] } }));
  fake.route("/operations/deletions/list", () => ({
    status: 200,
    data: { items: [{ conversation_id: "c-wait", state: "deleting", updated_at: "t" }] },
  }));
  fake.route("/operations/deletions/reconcile", () => ({
    status: 503,
    data: { error: "remote_delete_pending", message: "طلب الحذف لسه مش متأكد." },
  }));

  await flush();
  env.doc.getElementById("tab-jobs").click();
  await flush();

  const delList = env.doc.getElementById("deletions-list");
  findButtonByText(delList, "تحقق الآن").click();
  await flush();
  findButtonByText(delList, "أكّد التحقق").click();
  await flush();

  const toast = env.doc.getElementById("toast").textContent;
  assert.ok(toast.includes("لسه مش متأكد"));
  assert.ok(!toast.includes("اتحذف"));
});
