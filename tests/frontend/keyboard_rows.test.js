/* OHB2-PLAN04-LOW1 — انحدار: الصفوف التفاعلية (شاتات/ملفات/متابعات/مستودعات/إشعارات)
 * بقت قابلة للوصول بالكيبورد (role=button + tabindex=0)، وEnter/Space بيفعّلوا **نفس**
 * فعل الماوس **مرّة واحدة بالظبط**، وSpace بيمنع التمرير الافتراضي (preventDefault)،
 * والصفوف غير التفاعلية (طلبات البدء) تفضل غير تفاعلية.
 *
 * بيشتغل بـ Node المدمج: `node --test tests/frontend/keyboard_rows.test.js`
 * بيشغّل **نفس** app.js جوه بيئة DOM/شبكة مصغّرة (dom_stub.js) — مفيش أي نداء إنتاجي.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadApp, descendants } = require("./dom_stub.js");

const flush = async (n = 25) => { for (let i = 0; i < n; i++) { await new Promise((r) => setImmediate(r)); } };

function R(status, data) { return { status, data }; }

function findByClass(root, cls) {
  return descendants(root).find((n) => n.className.split(" ").includes(cls)) || null;
}
// صفوف القايمة الفعلية (className فيه الرمز "row" بالظبط، مش "row-main"/"row-actions"…).
function rowsOf(container) {
  return descendants(container).filter((n) => n.className.split(" ").includes("row"));
}
function kd(key) {
  const calls = [];
  return { key: key, preventDefault: () => calls.push("prevented"), _calls: calls };
}
function bootResponse() {
  return R(200, {
    user: { display_name: "مستخدم" },
    settings: { notifications_enabled: true },
    features: { watches: true },
    inbox: { unread_count: 0 },
  });
}

async function mkEnv(over) {
  over = over || {};
  const env = loadApp({});
  const { doc, fetch } = env;
  fetch.route("/auth", () => R(200, { ok: true }));
  fetch.route("/app/bootstrap", () => bootResponse());
  fetch.route((c) => c.path.startsWith("/conversations?"), () => R(200, over.conversations || { page: 0, items: [], has_more: false }));
  fetch.route((c) => c.path === "/conversations/c1", () => R(200, over.detail || { id: "c1", title: "شات", repository: "owner/repo", status: "running", last_reply: "رد" }));
  fetch.route((c) => c.path.startsWith("/conversations/c1/files"), () => R(200, over.files || { files: ["src/main.py"] }));
  fetch.route((c) => c.path.startsWith("/conversations/c1/file?"), () => R(200, over.preview || { text: "hello" }));
  fetch.route((c) => c.path.startsWith("/watches"), () => R(200, over.watches || { items: [], has_more: false }));
  fetch.route((c) => c.path.startsWith("/repositories"), () => R(200, over.repos || { items: [] }));
  fetch.route((c) => c.path.startsWith("/notifications?"), () => R(200, over.inbox || { page: 0, has_more: false, unread_count: 0, items: [] }));
  fetch.route((c) => c.path.startsWith("/notifications/"), () => R(200, { unread_count: 0 }));
  fetch.route((c) => c.path.startsWith("/operations/creation/list"), () => R(200, over.jobs || { page: 0, items: [], has_more: false }));
  fetch.route((c) => c.path.startsWith("/operations/deletions/list"), () => R(200, { items: [] }));
  await flush();
  return env;
}

function countCalls(fetch, pred) { return fetch.all(pred).length; }

// ------------------------------------------------------------------- chats
test("LOW1: صف الشات قابل للتركيز (role=button + tabindex=0) وEnter يفتح التفاصيل مرّة واحدة", async () => {
  const env = await mkEnv({ conversations: { page: 0, items: [{ id: "c1", title: "شات", repository: "owner/repo", status: "running" }], has_more: false } });
  const { doc, fetch } = env;
  const row = rowsOf(doc.getElementById("chats-list"))[0];
  assert.ok(row, "لازم صف شات يظهر");
  assert.equal(row.getAttribute("role"), "button");
  assert.equal(row.getAttribute("tabindex"), "0");

  const before = countCalls(fetch, (c) => c.path === "/conversations/c1");
  const ev = kd("Enter");
  row.dispatch("keydown", ev);
  await flush(6);
  assert.equal(ev._calls.length, 1, "Enter لازم يمنع الافتراضي (مفيش click مكرّر من المتصفح)");
  assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1") - before, 1, "Enter يفتح التفاصيل مرّة واحدة بالظبط");
});

test("LOW1: صف الشات — Space يفعّل مرّة واحدة ويمنع التمرير الافتراضي", async () => {
  const env = await mkEnv({ conversations: { page: 0, items: [{ id: "c1", title: "شات", repository: "owner/repo", status: "running" }], has_more: false } });
  const { doc, fetch } = env;
  const row = rowsOf(doc.getElementById("chats-list"))[0];
  const before = countCalls(fetch, (c) => c.path === "/conversations/c1");
  const ev = kd(" ");
  row.dispatch("keydown", ev);
  await flush(6);
  assert.equal(ev._calls.length, 1, "Space لازم يمنع التمرير الافتراضي (preventDefault)");
  assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1") - before, 1, "Space يفتح التفاصيل مرّة واحدة بالظبط");
});

test("LOW1: صف الشات — نقر الماوس لسه شغّال، والمفتاح غير المهم ما بيفعّلش", async () => {
  const env = await mkEnv({ conversations: { page: 0, items: [{ id: "c1", title: "شات", repository: "owner/repo", status: "running" }], has_more: false } });
  const { doc, fetch } = env;
  const row = rowsOf(doc.getElementById("chats-list"))[0];
  // مفتاح غير معني: لا فعل ولا preventDefault.
  const other = kd("a");
  row.dispatch("keydown", other);
  await flush(4);
  assert.equal(other._calls.length, 0, "مفتاح غير مهم مايمنعش الافتراضي");
  assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1"), 0, "مفتاح غير مهم مايفعّلش الصف");
  // نقر الماوس (السلوك القديم) لسه شغّال.
  row.click();
  await flush(6);
  assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1"), 1, "الماوس لسه بيفتح التفاصيل");
});

// ----------------------------------------------------------------- watches
test("LOW1: صف المتابعة قابل للتركيز وEnter يفتح التفاصيل", async () => {
  const env = await mkEnv({ watches: { items: [{ id: "w1", title: "متابعة", last_state: "running" }], has_more: false } });
  const { doc, fetch } = env;
  doc.getElementById("tab-watches").click();
  await flush(6);
  const row = rowsOf(doc.getElementById("watches-list"))[0];
  assert.ok(row, "لازم صف متابعة يظهر");
  assert.equal(row.getAttribute("role"), "button");
  assert.equal(row.getAttribute("tabindex"), "0");
  const before = countCalls(fetch, (c) => c.path === "/conversations/w1");
  const ev = kd("Enter");
  row.dispatch("keydown", ev);
  await flush(6);
  assert.equal(countCalls(fetch, (c) => c.path === "/conversations/w1") - before, 1);
});

// --------------------------------------------------------------- repos
test("LOW1: صف المستودع قابل للتركيز وEnter يختاره (يظهر نموذج الشات الجديد)", async () => {
  const env = await mkEnv({ repos: { items: [{ full_name: "owner/repo", private: false }] } });
  const { doc } = env;
  doc.getElementById("tab-new").click();
  await flush(6);
  const row = rowsOf(doc.getElementById("repo-list"))[0];
  assert.ok(row, "لازم صف مستودع يظهر");
  assert.equal(row.getAttribute("role"), "button");
  assert.equal(row.getAttribute("tabindex"), "0");
  // الافتراضي في index.html: النموذج مخفي لحد اختيار المستودع (الـ stub مابيضبطهوش).
  doc.getElementById("newchat-form").hidden = true;
  row.dispatch("keydown", kd("Enter"));
  await flush(4);
  assert.equal(doc.getElementById("newchat-form").hidden, false, "Enter يختار المستودع فيظهر النموذج");
  assert.ok(doc.getElementById("newchat-repo").textContent.indexOf("owner/repo") !== -1);
});

// --------------------------------------------------------------- files
test("LOW1: صف الملف قابل للتركيز وEnter يحمّل المعاينة", async () => {
  const env = await mkEnv({ conversations: { page: 0, items: [{ id: "c1", title: "شات", repository: "owner/repo", status: "running" }], has_more: false } });
  const { doc, fetch } = env;
  const chatRow = rowsOf(doc.getElementById("chats-list"))[0];
  chatRow.click();
  await flush(10);
  const filesSection = findByClass(doc.getElementById("view-detail"), "files-section");
  assert.ok(filesSection, "لازم قسم الملفات يظهر في التفاصيل");
  // WS-01: في الجذر بيظهر مجلد `src` — لازم يكون قابل للتركيز بالكيبورد.
  const folderRow = rowsOf(filesSection)[0];
  assert.ok(folderRow, "لازم صف مجلد يظهر");
  assert.equal(folderRow.getAttribute("role"), "button");
  assert.equal(folderRow.getAttribute("tabindex"), "0");
  // ندخل المجلد بالكيبورد.
  folderRow.dispatch("keydown", kd("Enter"));
  await flush(6);
  const fileRow = rowsOf(filesSection)[0];
  assert.ok(fileRow, "لازم صف ملف يظهر جوه المجلد");
  assert.equal(fileRow.getAttribute("role"), "button");
  assert.equal(fileRow.getAttribute("tabindex"), "0");
  const before = countCalls(fetch, (c) => c.path.startsWith("/conversations/c1/file?"));
  fileRow.dispatch("keydown", kd("Enter"));
  await flush(6);
  assert.equal(countCalls(fetch, (c) => c.path.startsWith("/conversations/c1/file?")) - before, 1);
});

  // --------------------------------------------------------------- inbox (F-1)
  // OHB2-PLAN04-F1: صف الإشعار = عنصر قايمة بنيوي `<li>` (مفيش role=button/tabindex)،
  // والفعل الرئيسي زر `<button>` حقيقي شقيق لأزرار الأرشفة/الحذف. الاختبارات دي بتتحقّق من
  // الدلالات + السلوك **مع محاكاة الفقاعة الحقيقية** (dom_stub بيفقّس الأحداث).

  async function inboxRowEnv(over) {
    over = over || {};
    const env = await mkEnv({ inbox: Object.assign({ page: 0, has_more: false, unread_count: 1,
      items: [{ id: 7, title: "إشعار", kind: "done", unread: true, conversation_id: "c1", deletable: true, archived: false }] }, over) });
    const { doc } = env;
    doc.getElementById("tab-inbox").click();
    await flush(6);
    return env;
  }
  function mainBtn(row) { return descendants(row).find((n) => n.className.split(" ").includes("row-open")) || null; }
  function actionBtn(row, text) { return descendants(row).find((n) => n.tagName === "BUTTON" && n.textContent === text) || null; }
  function keyEv(key) {
    const e = { key: key };
    e.preventDefault = function () { e.defaultPrevented = true; };
    e.stopPropagation = function () { e._stop = true; };
    return e;
  }

  test("F-1: الحاوية <li> عنصر قايمة بنيوي (مفيش role=button ولا tabindex)", async () => {
    const env = await inboxRowEnv();
    const row = rowsOf(env.doc.getElementById("inbox-list"))[0];
    assert.ok(row, "لازم صف إشعار يظهر");
    assert.equal(row.getAttribute("role"), null, "الحاوية ما بقتش role=button");
    assert.equal(row.getAttribute("tabindex"), null, "الحاوية مالها tabindex");
  });

  test("F-1: الفعل الرئيسي زر <button type=button> باسم متاح من المحتوى، ومفيهوش عناصر تفاعلية جوّاه", async () => {
    const env = await inboxRowEnv();
    const row = rowsOf(env.doc.getElementById("inbox-list"))[0];
    const main = mainBtn(row);
    assert.ok(main, "لازم زر الفعل الرئيسي (.row-open)");
    assert.equal(main.tagName, "BUTTON", "الفعل الرئيسي عنصر <button> حقيقي");
    assert.equal(main.getAttribute("type"), "button");
    assert.equal(main.getAttribute("tabindex"), null, "الأزرار الحقيقية مش محتاجة tabindex");
    assert.ok(main.textContent.indexOf("إشعار") !== -1, "الاسم المتاح فيه عنوان الإشعار");
    assert.ok(main.textContent.indexOf("جديد") !== -1, "الاسم المتاح فيه حالة القراءة");
    const nested = descendants(main).filter((n) => n.tagName === "BUTTON" || n.getAttribute("role") === "button" || n.getAttribute("tabindex") !== null);
    assert.equal(nested.length, 0, "مافيش عناصر تفاعلية متداخلة جوه الفعل الرئيسي");
  });

  test("F-1: أزرار الأرشفة/الحذف إخوة للفعل الرئيسي (مش جواه) وبأسماء مستقلة", async () => {
    const env = await inboxRowEnv();
    const row = rowsOf(env.doc.getElementById("inbox-list"))[0];
    const main = mainBtn(row);
    const archive = actionBtn(row, "أرشفة");
    const del = actionBtn(row, "🗑 حذف");
    assert.ok(archive && del, "لازم زرّي أرشفة وحذف");
    assert.ok(!descendants(main).includes(archive), "زر الأرشفة مش جوه الفعل الرئيسي");
    assert.ok(!descendants(main).includes(del), "زر الحذف مش جوه الفعل الرئيسي");
    assert.equal(archive.textContent, "أرشفة");
    assert.equal(del.textContent, "🗑 حذف");
  });

  test("F-1: Enter على الفعل الرئيسي ينفّذ الفعل الرئيسي مرّة واحدة (read + فتح الشات)", async () => {
    const env = await inboxRowEnv();
    const { doc, fetch } = env;
    const main = mainBtn(rowsOf(doc.getElementById("inbox-list"))[0]);
    const beforeRead = countCalls(fetch, (c) => c.path === "/notifications/7/read");
    const beforeDetail = countCalls(fetch, (c) => c.path === "/conversations/c1");
    main.dispatch("keydown", keyEv("Enter"));   // المتصفح: Enter على button ⇒ click
    main.click();
    await flush(6);
    assert.equal(countCalls(fetch, (c) => c.path === "/notifications/7/read") - beforeRead, 1, "read مرّة واحدة");
    assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1") - beforeDetail, 1, "فتح الشات مرّة واحدة");
  });

  test("F-1: Space على الفعل الرئيسي ينفّذ الفعل الرئيسي مرّة واحدة", async () => {
    const env = await inboxRowEnv();
    const { doc, fetch } = env;
    const main = mainBtn(rowsOf(doc.getElementById("inbox-list"))[0]);
    const beforeRead = countCalls(fetch, (c) => c.path === "/notifications/7/read");
    main.dispatch("keydown", keyEv(" "));
    main.click();                                 // المتصفح: Space على button ⇒ click عند الرفع
    await flush(6);
    assert.equal(countCalls(fetch, (c) => c.path === "/notifications/7/read") - beforeRead, 1, "read مرّة واحدة");
  });

  test("F-1: Enter على زر الأرشفة ينفّذ الأرشفة بس، ومايفعّلش الفعل الرئيسي", async () => {
    const env = await inboxRowEnv();
    const { doc, fetch } = env;
    const row = rowsOf(doc.getElementById("inbox-list"))[0];
    const archive = actionBtn(row, "أرشفة");
    const beforeDetail = countCalls(fetch, (c) => c.path === "/conversations/c1");
    const beforeRead = countCalls(fetch, (c) => c.path === "/notifications/7/read");
    archive.dispatch("keydown", keyEv("Enter"));  // يفقّس للحاوية (زي المتصفح) — لكن مفيش مستمع keydown عليها
    archive.click();
    await flush(6);
    assert.equal(countCalls(fetch, (c) => c.path === "/notifications/7/archive"), 1, "الأرشفة اتنفّذت مرّة واحدة");
    assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1") - beforeDetail, 0, "مافتحش الشات (الفعل الرئيسي مااتفعّلش)");
    assert.equal(countCalls(fetch, (c) => c.path === "/notifications/7/read") - beforeRead, 0, "مااتعلّمش مقروء");
  });

  test("F-1: Space على زر الأرشفة ينفّذ الأرشفة بس، ومايفعّلش الفعل الرئيسي", async () => {
    const env = await inboxRowEnv();
    const { doc, fetch } = env;
    const row = rowsOf(doc.getElementById("inbox-list"))[0];
    const archive = actionBtn(row, "أرشفة");
    const beforeDetail = countCalls(fetch, (c) => c.path === "/conversations/c1");
    archive.dispatch("keydown", keyEv(" "));
    archive.click();
    await flush(6);
    assert.equal(countCalls(fetch, (c) => c.path === "/notifications/7/archive"), 1, "الأرشفة مرّة واحدة");
    assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1") - beforeDetail, 0, "مافتحش الشات");
  });

  test("F-1: Enter على زر الحذف يفتح التأكيد بس (خطوتين)، ومايفعّلش الفعل الرئيسي", async () => {
    const env = await inboxRowEnv();
    const { doc, fetch } = env;
    const row = rowsOf(doc.getElementById("inbox-list"))[0];
    const del = actionBtn(row, "🗑 حذف");
    const beforeDetail = countCalls(fetch, (c) => c.path === "/conversations/c1");
    del.dispatch("keydown", keyEv("Enter"));
    del.click();
    await flush(4);
    const confirm = actionBtn(row, "أكّد الحذف");
    assert.equal(confirm.hidden, false, "ظهر زر التأكيد");
    assert.equal(countCalls(fetch, (c) => c.path === "/notifications/7"), 0, "لسه مفيش DELETE (خطوتين)");
    assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1") - beforeDetail, 0, "مافتحش الشات");
  });

  test("F-1: Enter على زر التأكيد ينفّذ DELETE مرّة واحدة، ومايفعّلش الفعل الرئيسي", async () => {
    const env = await inboxRowEnv();
    const { doc, fetch } = env;
    const row = rowsOf(doc.getElementById("inbox-list"))[0];
    actionBtn(row, "🗑 حذف").click();
    await flush(4);
    const confirm = actionBtn(row, "أكّد الحذف");
    const beforeDetail = countCalls(fetch, (c) => c.path === "/conversations/c1");
    confirm.dispatch("keydown", keyEv("Enter"));
    confirm.click();
    await flush(6);
    assert.equal(countCalls(fetch, (c) => c.path === "/notifications/7"), 1, "DELETE مرّة واحدة");
    assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1") - beforeDetail, 0, "مافتحش الشات");
  });

  test("F-1: Space على زر الإلغاء يرجّع الحالة بس، ومايفعّلش الفعل الرئيسي", async () => {
    const env = await inboxRowEnv();
    const { doc, fetch } = env;
    const row = rowsOf(doc.getElementById("inbox-list"))[0];
    actionBtn(row, "🗑 حذف").click();
    await flush(4);
    const cancel = actionBtn(row, "إلغاء");
    const beforeDetail = countCalls(fetch, (c) => c.path === "/conversations/c1");
    cancel.dispatch("keydown", keyEv(" "));
    cancel.click();
    await flush(4);
    assert.equal(actionBtn(row, "🗑 حذف").hidden, false, "زر الحذف رجع");
    assert.equal(countCalls(fetch, (c) => c.path === "/notifications/7"), 0, "مفيش DELETE");
    assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1") - beforeDetail, 0, "مافتحش الشات");
  });

  test("F-1: نقر الماوس على زر إجراء مايفعّلش الفعل الرئيسي (فحص e.target)", async () => {
    const env = await inboxRowEnv();
    const { doc, fetch } = env;
    const row = rowsOf(doc.getElementById("inbox-list"))[0];
    const beforeDetail = countCalls(fetch, (c) => c.path === "/conversations/c1");
    actionBtn(row, "أرشفة").click();
    await flush(6);
    assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1") - beforeDetail, 0, "مافتحش الشات");
  });

  test("F-1: نقر الماوس على الحاوية نفسها يفتح الإشعار (سلوك الماوس محفوظ)", async () => {
    const env = await inboxRowEnv();
    const { doc, fetch } = env;
    const row = rowsOf(doc.getElementById("inbox-list"))[0];
    const beforeDetail = countCalls(fetch, (c) => c.path === "/conversations/c1");
    row.click();   // هدف النقر = الحاوية (padding)
    await flush(6);
    assert.equal(countCalls(fetch, (c) => c.path === "/conversations/c1") - beforeDetail, 1, "فتح الشات مرّة واحدة");
  });


// --------------------------------------------------- non-interactive rows
test("LOW1: صفوف طلبات البدء (غير التفاعلية) ما بقتش تفاعلية زورًا", async () => {
  const env = await mkEnv({ jobs: { page: 0, items: [{ id: 3, state: "pending", post_state: "pending", repository: "owner/repo" }], has_more: false } });
  const { doc } = env;
  doc.getElementById("tab-jobs").click();
  await flush(6);
  const row = rowsOf(doc.getElementById("jobs-list"))[0];
  assert.ok(row, "لازم صف طلب بدء يظهر");
  assert.equal(row.getAttribute("role"), null, "صف غير تفاعلي مالهوش role=button");
  assert.equal(row.getAttribute("tabindex"), null, "صف غير تفاعلي مالوش tabindex");
});
