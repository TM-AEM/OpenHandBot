/* OHB2-PHASE1B — اختبارات منطق «نسخ الرد الكامل» (copy.js).
 *
 * بتشتغل بـ Node المدمج: `node --test tests/frontend/copy.test.js`
 * بتختبر **نفس** الوحدة اللي الواجهة بتستعملها (bot/web/static/copy.js).
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const COPY = require("../../bot/web/static/copy.js");

function fakeDoc(execResult) {
  const calls = [];
  const doc = {
    execCommandCalls: calls,
    execCommandResult: execResult,
    body: { children: [], appendChild(c) { this.children.push(c); } },
    createElement(tag) {
      return {
        tagName: tag.toUpperCase(),
        value: "",
        setAttribute() {},
        select() {},
        setSelectionRange() {},
        remove() {},
      };
    },
    execCommand(cmd) { calls.push(cmd); return execResult; },
  };
  return doc;
}

test("بيستخدم Clipboard API لما يكون متاح وينجح", async () => {
  let written = null;
  const navigator = { clipboard: { writeText: (t) => { written = t; return Promise.resolve(); } } };
  const r = await COPY.copyText("نص كامل", { navigator, document: fakeDoc(false) });
  assert.equal(r.ok, true);
  assert.equal(r.method, "clipboard");
  assert.equal(written, "نص كامل");
});

test("لو Clipboard API رفض بيرجع للـ fallback وينجح بصدق", async () => {
  const navigator = { clipboard: { writeText: () => Promise.reject(new Error("denied")) } };
  const doc = fakeDoc(true);
  const r = await COPY.copyText("نص", { navigator, document: doc });
  assert.equal(r.ok, true);
  assert.equal(r.method, "fallback");
  assert.deepEqual(doc.execCommandCalls, ["copy"]);
});

test("لو الاتنين فشلوا ⇒ مفيش نجاح كاذب", async () => {
  const navigator = { clipboard: { writeText: () => Promise.reject(new Error("denied")) } };
  const r = await COPY.copyText("نص", { navigator, document: fakeDoc(false) });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "failed");
});

test("من غير Clipboard API خالص بيرجع للـ fallback", async () => {
  const r = await COPY.copyText("نص", { navigator: null, document: fakeDoc(true) });
  assert.equal(r.ok, true);
  assert.equal(r.method, "fallback");
});

test("نص فاضي ⇒ رفض واضح (مفيش نسخ صامت)", async () => {
  const navigator = { clipboard: { writeText: () => Promise.resolve() } };
  const r = await COPY.copyText("", { navigator, document: fakeDoc(true) });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "empty");
});

test("مفيش أي مسار نسخ متاح ⇒ فشل صادق (unsupported)", async () => {
  const r = await COPY.copyText("نص", { navigator: null, document: null });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "unsupported");
});

test("رسائل الـ feedback عربي واضحة لكل حالة", () => {
  assert.equal(COPY.feedback({ ok: true }), COPY.MESSAGES.success);
  assert.equal(COPY.feedback({ ok: false, reason: "empty" }), COPY.MESSAGES.empty);
  assert.equal(COPY.feedback({ ok: false, reason: "failed" }), COPY.MESSAGES.failed);
  assert.equal(COPY.feedback(null), COPY.MESSAGES.failed);
});

test("الـ fallback بيمسح الـ textarea المؤقّت (مايسيبش أثر في الـ DOM)", async () => {
  const doc = fakeDoc(true);
  await COPY.copyText("نص", { navigator: null, document: doc });
  assert.equal(doc.body.children.length, 1, "اتضاف مؤقّتًا");
  assert.equal(typeof doc.body.children[0].remove, "function");
});
