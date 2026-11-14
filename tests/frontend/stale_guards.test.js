/* OHB2-MINIAPP-STALE-FIX — انحدار: الردود القديمة مايدهسوش حالة أحدث في الشاتات
 * والمستودعات والمتابعات ومعاينة الملفات.
 *
 * بيشتغل بـ Node المدمج: `node --test tests/frontend/stale_guards.test.js`
 * بيشغّل **نفس** app.js جوه بيئة DOM/شبكة مصغّرة (dom_stub.js)، وبنتحكّم في ترتيب
 * رجوع الطلبات بوعود مؤجّلة — مفيش أي نداء إنتاجي.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadApp, descendants } = require("./dom_stub.js");

const flush = async (n = 25) => { for (let i = 0; i < n; i++) { await new Promise((r) => setImmediate(r)); } };

// رد مؤجّل (للـ resolver اليدوي): لازم يحمل status/ok/json زي ما fetchJson بيتوقّع.
function resp(status, data) {
  return { status, ok: status < 400, json: () => Promise.resolve(data) };
}
// رد فوري (لمُستجيب route): FakeFetch بيغلّفه لـ {status,data}.
function R(status, data) { return { status, data }; }

function listText(doc, id) {
  return descendants(doc.getElementById(id)).map((n) => n.textContent).join(" | ");
}
function rowTexts(doc, id) {
  return doc.getElementById(id).children
    .filter((c) => c.className.split(" ").includes("row"))
    .map((c) => c.textContent);
}
function buttonByText(root, text) {
  return descendants(root).filter((n) => n.tagName === "BUTTON" && n.textContent.indexOf(text) !== -1);
}

function bootResponse() {
  return R(200, {
    user: { display_name: "مستخدم" },
    settings: { notifications_enabled: true },
    features: { watches: true },
    inbox: { unread_count: 0 },
  });
}

async function mkEnv() {
  const env = loadApp({});
  const { doc, fetch } = env;
  fetch.route("/auth", () => R(200, { ok: true }));
  fetch.route("/app/bootstrap", () => bootResponse());
  fetch.route((c) => c.path.startsWith("/conversations?"), () => R(200, { items: [], has_more: false }));
  fetch.route((c) => c.path.startsWith("/watches"), () => R(200, { items: [], has_more: false }));
  fetch.route((c) => c.path.startsWith("/repositories"), () => R(200, { items: [] }));
  fetch.route((c) => c.path.startsWith("/notifications"), () => R(200, { page: 0, has_more: false, unread_count: 0, items: [] }));
  await flush();
  return env;
}

// ---------------------------------------------------------------- chats

test("شاتات: رد قديم (يرجع أخير) مايدهسش قايمة أحدث", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  const resolvers = [];
  fetch.route((c) => c.path.startsWith("/conversations?"), () => new Promise((r) => { resolvers.push(r); }));

  doc.getElementById("tab-chats").click();       // طلب A (قديم)
  await flush(2);
  doc.getElementById("chats-refresh").click();   // طلب B (أحدث)
  await flush(2);
  assert.equal(resolvers.length, 2, "لازم طلبين معلّقين");

  resolvers[1](resp(200, { items: [{ id: "b", title: "الأحدث", status: "running" }], has_more: false }));
  await flush(3);
  assert.ok(listText(doc, "chats-list").indexOf("الأحدث") !== -1, "الأحدث لازم يظهر");

  resolvers[0](resp(200, { items: [{ id: "a", title: "قديم", status: "done" }], has_more: false }));
  await flush(3);
  assert.ok(listText(doc, "chats-list").indexOf("الأحدث") !== -1, "الأحدث لازم يفضل");
  assert.ok(listText(doc, "chats-list").indexOf("قديم") === -1, "الرد القديم مايدهسش الأحدث");
});

test("شاتات: فشل قديم (500) مايدهسش نجاح أحدث ولا يعرض خطأ قديم", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  const resolvers = [];
  fetch.route((c) => c.path.startsWith("/conversations?"), () => new Promise((r) => { resolvers.push(r); }));

  doc.getElementById("tab-chats").click();
  await flush(2);
  doc.getElementById("chats-refresh").click();
  await flush(2);

  resolvers[1](resp(200, { items: [{ id: "b", title: "سليم", status: "running" }], has_more: false }));
  await flush(3);
  assert.ok(listText(doc, "chats-list").indexOf("سليم") !== -1);

  resolvers[0](resp(500, { message: "الخدمة مش متاحة دلوقتي، جرّب تاني." }));
  await flush(3);
  assert.ok(listText(doc, "chats-list").indexOf("سليم") !== -1, "النجاح الأحدث لازم يفضل");
  assert.ok(listText(doc, "chats-list").indexOf("مش متاحة") === -1, "خطأ قديم مايظهرش");
});

test("شاتات: رد قايمة قديم مايرجّعش شات اتحذف بعد بداية الطلب", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  fetch.route((c) => c.path.startsWith("/conversations?"), () => R(200, {
    items: [{ id: "c1", title: "مهدد", status: "running" }], has_more: false,
  }));
  doc.getElementById("tab-chats").click();
  await flush(4);
  assert.ok(listText(doc, "chats-list").indexOf("مهدد") !== -1, "الشات ظاهر قبل الحذف");

  // تفاصيل c1 (ردود فورية).
  fetch.route((c) => c.path === "/conversations/c1" && c.method === "GET", () => R(200, { id: "c1", title: "مهدد", watched: false, last_reply: "x" }));
  fetch.route((c) => c.path === "/conversations/c1/files", () => R(200, { files: [] }));
  fetch.route((c) => c.path === "/conversations/c1/cost", () => R(200, {}));
  const rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  rows[0].click();
  await flush(5);

  // طلب قايمة قديم معلّق (لسه فيه c1).
  let staleList;
  fetch.route((c) => c.path.startsWith("/conversations?"), () => new Promise((r) => { staleList = r; }));
  doc.getElementById("chats-refresh").click();
  await flush(2);
  assert.equal(typeof staleList, "function", "طلب القايمة القديم معلّق");

  // حذف c1 (يُنجح) ⇒ loadChats(true) بقايمة فاضية.
  fetch.route((c) => c.path === "/conversations/c1" && c.method === "DELETE", () => R(200, { ok: true }));
  fetch.route((c) => c.path.startsWith("/conversations?"), () => R(200, { items: [], has_more: false }));
  buttonByText(doc.getElementById("view-detail"), "حذف الشات")[0].click();
  await flush(1);
  buttonByText(doc.getElementById("view-detail"), "أكّد الحذف")[0].click();
  await flush(5);
  assert.ok(listText(doc, "chats-list").indexOf("مهدد") === -1, "الشات اتحذف من العرض");

  // الرد القديم يوصل أخير — مايرجّعش الشات المحذوف.
  staleList(resp(200, { items: [{ id: "c1", title: "مهدد", status: "running" }], has_more: false }));
  await flush(5);
  assert.ok(listText(doc, "chats-list").indexOf("مهدد") === -1, "شات محذوف مايرجعش بسبب رد قديم");
});

test("شاتات: رد صفحة قديمة مايدهسش تحديث الصفحة 0 الأحدث", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  fetch.route((c) => c.path.startsWith("/conversations?"), () => R(200, {
    items: [{ id: "p0", title: "صفحة0", status: "running" }], has_more: true,
  }));
  doc.getElementById("tab-chats").click();
  await flush(4);

  let pg1;
  fetch.route((c) => c.path.startsWith("/conversations?"), () => new Promise((r) => { pg1 = r; }));
  doc.getElementById("chats-next").click();       // صفحة 1 (معلّق)
  await flush(2);

  let pg0;
  fetch.route((c) => c.path.startsWith("/conversations?"), () => new Promise((r) => { pg0 = r; }));
  doc.getElementById("chats-refresh").click();    // تحديث صفحة 0 (معلّق)
  await flush(2);
  assert.equal(typeof pg0, "function");
  assert.equal(typeof pg1, "function");

  pg0(resp(200, { items: [{ id: "r0", title: "تحديث0", status: "running" }], has_more: false }));
  await flush(3);
  assert.ok(listText(doc, "chats-list").indexOf("تحديث0") !== -1);

  pg1(resp(200, { items: [{ id: "p1", title: "صفحة1", status: "running" }], has_more: true }));
  await flush(3);
  assert.ok(listText(doc, "chats-list").indexOf("تحديث0") !== -1, "تحديث الصفحة 0 لازم يفضل");
  assert.ok(listText(doc, "chats-list").indexOf("صفحة1") === -1, "رد الصفحة القديمة مايدهسش");
});

test("شاتات: رفض الشبكة يستبدل صف التحميل برسالة قابلة للاسترجاع وبلا unhandled rejection", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  const rejections = [];
  const onRej = (e) => { rejections.push(e); };
  process.on("unhandledRejection", onRej);
  try {
    fetch.route((c) => c.path.startsWith("/conversations?"), () => Promise.reject(new Error("network down")));
    doc.getElementById("tab-chats").click();
    await flush(15);

    const text = listText(doc, "chats-list");
    assert.ok(text.indexOf("بيتم التحميل") === -1, "صف التحميل مايفضلش معلّق");
    assert.ok(text.indexOf("مش قادر أوصل للسيرفر") !== -1, "رسالة قابلة للاسترجاع تظهر");
    assert.equal(rejections.length, 0, "مفيش unhandled rejection");
  } finally {
    process.removeListener("unhandledRejection", onRej);
  }
});

// ------------------------------------------------------------ repositories

test("مستودعات: بحث أحدث يلغي رد البحث الأقدم", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  const resolvers = [];
  fetch.route((c) => c.path.startsWith("/repositories"), () => new Promise((r) => { resolvers.push(r); }));

  doc.getElementById("tab-new").click();          // loadRepos("") — A
  await flush(2);
  doc.getElementById("repo-search").value = "zzz";
  doc.getElementById("repo-search-btn").click();  // loadRepos("zzz") — B
  await flush(2);
  assert.equal(resolvers.length, 2);

  resolvers[1](resp(200, { items: [{ full_name: "org/NEW", private: false }] }));
  await flush(3);
  assert.ok(listText(doc, "repo-list").indexOf("org/NEW") !== -1);

  resolvers[0](resp(200, { items: [{ full_name: "org/OLD", private: false }] }));
  await flush(3);
  assert.ok(listText(doc, "repo-list").indexOf("org/NEW") !== -1, "نتيجة البحث الأحدث تفضل");
  assert.ok(listText(doc, "repo-list").indexOf("org/OLD") === -1, "نتيجة البحث الأقدم مايدهسش");
});

test("مستودعات: فشل بحث قديم مايدهسش نتيجة أحدث", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  const resolvers = [];
  fetch.route((c) => c.path.startsWith("/repositories"), () => new Promise((r) => { resolvers.push(r); }));

  doc.getElementById("tab-new").click();
  await flush(2);
  doc.getElementById("repo-search").value = "zzz";
  doc.getElementById("repo-search-btn").click();
  await flush(2);

  resolvers[1](resp(200, { items: [{ full_name: "org/OK", private: false }] }));
  await flush(3);
  assert.ok(listText(doc, "repo-list").indexOf("org/OK") !== -1);

  resolvers[0](resp(500, { message: "الخدمة مش متاحة دلوقتي، جرّب تاني." }));
  await flush(3);
  assert.ok(listText(doc, "repo-list").indexOf("org/OK") !== -1, "النتيجة الأحدث تفضل");
  assert.ok(listText(doc, "repo-list").indexOf("مش متاحة") === -1, "خطأ قديم مايظهرش");
});

// ------------------------------------------------------------------ watches

test("متابعات: رد قديم مايدهسش قايمة أحدث", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  const resolvers = [];
  fetch.route((c) => c.path.startsWith("/watches"), () => new Promise((r) => { resolvers.push(r); }));

  doc.getElementById("tab-watches").click();      // A
  await flush(2);
  doc.getElementById("watches-refresh").click();  // B
  await flush(2);
  assert.equal(resolvers.length, 2);

  resolvers[1](resp(200, { items: [{ id: "n", title: "متابعة-جديدة", last_state: "s" }] }));
  await flush(3);
  assert.ok(listText(doc, "watches-list").indexOf("متابعة-جديدة") !== -1);

  resolvers[0](resp(200, { items: [{ id: "o", title: "متابعة-قديمة", last_state: "s" }] }));
  await flush(3);
  assert.ok(listText(doc, "watches-list").indexOf("متابعة-جديدة") !== -1, "الأحدث تفضل");
  assert.ok(listText(doc, "watches-list").indexOf("متابعة-قديمة") === -1, "القديم مايدهسش");
});

test("متابعات: فشل قديم مايدهسش نجاح أحدث", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  const resolvers = [];
  fetch.route((c) => c.path.startsWith("/watches"), () => new Promise((r) => { resolvers.push(r); }));

  doc.getElementById("tab-watches").click();
  await flush(2);
  doc.getElementById("watches-refresh").click();
  await flush(2);

  resolvers[1](resp(200, { items: [{ id: "n", title: "سليمة", last_state: "s" }] }));
  await flush(3);
  assert.ok(listText(doc, "watches-list").indexOf("سليمة") !== -1);

  resolvers[0](resp(500, { message: "الخدمة مش متاحة دلوقتي، جرّب تاني." }));
  await flush(3);
  assert.ok(listText(doc, "watches-list").indexOf("سليمة") !== -1, "النجاح الأحدث يفضل");
  assert.ok(listText(doc, "watches-list").indexOf("مش متاحة") === -1, "خطأ قديم مايظهرش");
});

// ------------------------------------------------------------------ preview

// بيفتح تفاصيل c1 بقايمة ملفات معطاة، ويرجّع (env, detailBox).
async function openDetailWithFiles(files) {
  const env = await mkEnv();
  const { doc, fetch } = env;
  fetch.route((c) => c.path.startsWith("/conversations?"), () => R(200, {
    items: [{ id: "c1", title: "شات1", status: "running" }], has_more: false,
  }));
  fetch.route((c) => c.path === "/conversations/c1" && c.method === "GET", () => R(200, { id: "c1", title: "شات1", watched: false, last_reply: "r" }));
  fetch.route((c) => c.path === "/conversations/c1/files", () => R(200, { files: files }));
  fetch.route((c) => c.path === "/conversations/c1/cost", () => R(200, {}));
  doc.getElementById("tab-chats").click();
  await flush(4);
  const rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  rows[0].click();
  await flush(6);
  return env;
}

function fileRows(doc, path) {
  return descendants(doc.getElementById("view-detail"))
    .filter((n) => n.tagName === "LI" && n.textContent === path);
}

test("معاينة: رد ملف قديم (مسار مختلف) مايدهسش معاينة أحدث", async () => {
  const env = await openDetailWithFiles(["A.txt", "B.txt"]);
  const { doc, fetch } = env;

  let rA;
  fetch.route((c) => c.path === "/conversations/c1/file?path=A.txt", () => new Promise((r) => { rA = r; }));
  fetch.route((c) => c.path === "/conversations/c1/file?path=B.txt", () => R(200, { status: "ok", text: "محتوى-B" }));

  fileRows(doc, "A.txt")[0].click();   // A (بطيء)
  await flush(2);
  fileRows(doc, "B.txt")[0].click();   // B (سريع)
  await flush(4);
  assert.ok(listText(doc, "view-detail").indexOf("محتوى-B") !== -1, "معاينة B لازم تظهر");

  rA(resp(200, { status: "ok", text: "محتوى-A" }));
  await flush(5);
  assert.ok(listText(doc, "view-detail").indexOf("محتوى-B") !== -1, "معاينة B تفضل");
  assert.ok(listText(doc, "view-detail").indexOf("محتوى-A") === -1, "معاينة A القديمة مايدهسش");
});

test("معاينة: فشل قديم مايدهسش معاينة أحدث ناجحة", async () => {
  const env = await openDetailWithFiles(["A.txt", "B.txt"]);
  const { doc, fetch } = env;

  let rA;
  fetch.route((c) => c.path === "/conversations/c1/file?path=A.txt", () => new Promise((r) => { rA = r; }));
  fetch.route((c) => c.path === "/conversations/c1/file?path=B.txt", () => R(200, { status: "ok", text: "محتوى-B" }));

  fileRows(doc, "A.txt")[0].click();
  await flush(2);
  fileRows(doc, "B.txt")[0].click();
  await flush(4);
  assert.ok(listText(doc, "view-detail").indexOf("محتوى-B") !== -1);

  rA(resp(500, { error: "api_error" }));
  await flush(5);
  assert.ok(listText(doc, "view-detail").indexOf("محتوى-B") !== -1, "معاينة B الناجحة تفضل");
});

test("معاينة: ضغط مكرّر على نفس المسار مايكرّرش الطلب، ورد نفس المسار القديم مايدهسش معاينة أحدث", async () => {
  const env = await openDetailWithFiles(["A.txt", "B.txt"]);
  const { doc, fetch } = env;

  let rA;
  fetch.route((c) => c.path === "/conversations/c1/file?path=A.txt", () => new Promise((r) => { rA = r; }));
  fetch.route((c) => c.path === "/conversations/c1/file?path=B.txt", () => R(200, { status: "ok", text: "محتوى-B" }));

  fileRows(doc, "A.txt")[0].click();   // A (معلّق)
  await flush(2);
  fileRows(doc, "A.txt")[0].click();   // نفس المسار تاني (لسه معلّق) ⇒ نفس الطلب
  await flush(2);

  const aCalls = fetch.all((c) => c.path === "/conversations/c1/file?path=A.txt");
  assert.equal(aCalls.length, 1, "نفس المفتاح المعلّق ⇒ طلب واحد بس (dedupe)");

  fileRows(doc, "B.txt")[0].click();   // مسار مختلف أحدث
  await flush(4);
  assert.ok(listText(doc, "view-detail").indexOf("محتوى-B") !== -1, "معاينة B لازم تظهر");

  // رد A (نفس المسار المكرّر) يوصل أخير — مايدهسش B.
  rA(resp(200, { status: "ok", text: "محتوى-A" }));
  await flush(5);
  const dt = listText(doc, "view-detail");
  assert.ok(dt.indexOf("محتوى-B") !== -1, "معاينة B تفضل");
  assert.ok(dt.indexOf("محتوى-A") === -1, "رد نفس المسار القديم مايدهسش المعاينة الأحدث");
  const pres = descendants(doc.getElementById("view-detail")).filter((n) => n.tagName === "PRE" && n.textContent === "محتوى-A");
  assert.equal(pres.length, 0, "مفيش كتابة قديمة لنفس المسار");
});

// -------------------------------------------------------------- protections

test("حماية: حرس التفاصيل والصندوق لسه شغّال (لا انحدار)", async () => {
  const env = await mkEnv();
  const { doc, fetch } = env;

  // تفاصيل: رد قديم مايدهسش الأحدث.
  fetch.route((c) => c.path.startsWith("/conversations?"), () => R(200, {
    items: [{ id: "c1", title: "T1", status: "running" }, { id: "c2", title: "T2", status: "running" }], has_more: false,
  }));
  doc.getElementById("tab-chats").click();
  await flush(4);
  let rc1, rc2;
  fetch.route((c) => c.path === "/conversations/c1", () => new Promise((r) => { rc1 = r; }));
  fetch.route((c) => c.path === "/conversations/c2", () => new Promise((r) => { rc2 = r; }));
  const rows = doc.getElementById("chats-list").children.filter((c) => c.className.split(" ").includes("row"));
  rows[0].click(); await flush(2);
  rows[1].click(); await flush(2);
  rc2(resp(200, { id: "c2", title: "الأحدث", watched: false }));
  await flush(3);
  rc1(resp(200, { id: "c1", title: "قديم", watched: false }));
  await flush(3);
  const dt = listText(doc, "view-detail");
  assert.ok(dt.indexOf("الأحدث") !== -1 && dt.indexOf("قديم") === -1, "حرس التفاصيل شغّال");
});
