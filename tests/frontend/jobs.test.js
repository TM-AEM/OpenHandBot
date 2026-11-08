/* OHB2-PHASE1D — اختبارات منطق عرض/إدارة طلبات الشات الجديد (jobs.js + view-jobs).
 *
 * بيتحقّق من قواعد الأمان في طبقة العرض: الإلغاء/الحسم بيظهروا **بس** حسب أعلام
 * السيرفر (`cancellable`/`resolvable`)، والحالة الغامضة ما بتعرضش أي ادّعاء نجاح/فشل.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const JOBS = require(path.resolve(__dirname, "../../bot/web/static/jobs.js"));

test("stateLabel: كل حالة داخلية ليها وصف عربي", () => {
  assert.equal(JOBS.stateLabel("pending"), "قيد التنفيذ");
  assert.equal(JOBS.stateLabel("accepted"), "اتعمل");
  assert.equal(JOBS.stateLabel("ambiguous"), "مش متأكدين");
  assert.equal(JOBS.stateLabel("discarded"), "اتلغى");
  assert.equal(JOBS.stateLabel("weird"), "مش معروف");  // fail closed
});

test("canCancel: بس لما السيرفر يقول قابل للإلغاء صراحةً", () => {
  assert.equal(JOBS.canCancel({ cancellable: true }), true);
  assert.equal(JOBS.canCancel({ cancellable: false }), false);
  assert.equal(JOBS.canCancel({}), false);          // مفيش علم ⇒ مفيش إجراء
  assert.equal(JOBS.canCancel(null), false);
});

test("canResolve: بس للطلب الغامض", () => {
  assert.equal(JOBS.canResolve({ resolvable: true }), true);
  assert.equal(JOBS.canResolve({ resolvable: false }), false);
  assert.equal(JOBS.canResolve({}), false);
});

test("hasConversation: بس لما فيه معرّف محادثة فعلي", () => {
  assert.equal(JOBS.hasConversation({ conversation_id: "c1" }), true);
  assert.equal(JOBS.hasConversation({ conversation_id: "" }), false);
  assert.equal(JOBS.hasConversation({}), false);
});

test("isAmbiguous: الغموض حالة خاصة", () => {
  assert.equal(JOBS.isAmbiguous({ state: "ambiguous" }), true);
  assert.equal(JOBS.isAmbiguous({ state: "accepted" }), false);
});

test("note: رسالة الغموض بتحذّر من إعادة الإرسال من غير ادّعاء", () => {
  const n = JOBS.note({ state: "ambiguous" });
  assert.ok(n.includes("غامض"));
  assert.ok(!n.includes("اتعمل") && !n.includes("فشل"));
});

test("postStateLabel: وصف آمن لحدّ الإرسال", () => {
  assert.equal(JOBS.postStateLabel("not_started"), "لسه مابدأش");
  assert.equal(JOBS.postStateLabel("uncertain"), "ممكن يكون بدأ");
  assert.equal(JOBS.postStateLabel("started"), "بدأ فعلاً");
  assert.equal(JOBS.postStateLabel("bogus"), "");
});
