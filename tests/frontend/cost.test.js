/* OHB2-09-04 — اختبارات منطق عرض التكلفة/الاستهلاك في الواجهة.
 *
 * بتشتغل بـ Node المدمج: `node --test tests/frontend/`
 * بتختبر **نفس** الوحدة (bot/web/static/cost.js) اللي app.js بيستعملها.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const COST = require("../../bot/web/static/cost.js");

test("hasCost: false when nothing usable", () => {
  assert.equal(COST.hasCost(null), false);
  assert.equal(COST.hasCost({}), false);
  assert.equal(COST.hasCost({ accumulated_cost: null, model: null }), false);
});

test("hasCost: true with any numeric field or model", () => {
  assert.equal(COST.hasCost({ accumulated_cost: 0 }), true);
  assert.equal(COST.hasCost({ prompt_tokens: 5 }), true);
  assert.equal(COST.hasCost({ model: "gpt-4o" }), true);
});

test("formatCost: empty payload -> message", () => {
  assert.equal(COST.formatCost({}), "مفيش بيانات تكلفة.");
  assert.equal(COST.formatCost(null), "مفيش بيانات تكلفة.");
});

test("formatCost: full payload renders Arabic lines", () => {
  const text = COST.formatCost({
    accumulated_cost: 1.5,
    model: "gpt-4o",
    prompt_tokens: 100,
    completion_tokens: 40,
  });
  assert.equal(
    text,
    "الموديل: gpt-4o\nالتكلفة التراكمية: 1.5000\nتوكنز الإدخال: 100\nتوكنز الإخراج: 40"
  );
});

test("formatCost: total_tokens only when prompt/completion missing", () => {
  assert.equal(COST.formatCost({ total_tokens: 250 }), "إجمالي التوكنز: 250");
  // لو فيه prompt/completion، ما نعرضش total.
  const text = COST.formatCost({ prompt_tokens: 1, completion_tokens: 2, total_tokens: 3 });
  assert.equal(text, "توكنز الإدخال: 1\nتوكنز الإخراج: 2");
});

test("formatCost: floors fractional token counts", () => {
  assert.equal(COST.formatCost({ prompt_tokens: 2.9 }), "توكنز الإدخال: 2");
});

test("formatCost: ignores non-numeric junk", () => {
  const text = COST.formatCost({ accumulated_cost: "x", model: "m", prompt_tokens: null });
  assert.equal(text, "الموديل: m");
});

test("formatCost: no currency symbol is fabricated (OHB2-09-04-R1)", () => {
  const text = COST.formatCost({ accumulated_cost: 1.5, model: "gpt-4o" });
  assert.equal(text.indexOf("$"), -1, "مافيش رمز عملة");
  assert.equal(/usd/i.test(text), false, "مافيش اسم عملة");
  assert.ok(text.indexOf("التكلفة التراكمية: 1.5000") !== -1);
});

test("formatCost/hasCost: non-finite numbers are rejected client-side too (OHB2-09-A2-03)", () => {
  // السيرفر بيرفض NaN/±Infinity، والواجهة كمان ما تعتبرهم قيم صالحة (دفاع مزدوج).
  for (const bad of [NaN, Infinity, -Infinity]) {
    assert.equal(COST.hasCost({ accumulated_cost: bad }), false);
    assert.equal(COST.hasCost({ prompt_tokens: bad }), false);
    const text = COST.formatCost({ accumulated_cost: bad });
    assert.equal(text, "مفيش بيانات تكلفة.");
  }
});
