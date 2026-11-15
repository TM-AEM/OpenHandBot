/* OHB2-PLAN04-UI03 — فحوص إتاحة (a11y) على **مستوى المصدر** (مش متصفّح حقيقي).
 *
 * بتتحقق إن الواجهة الثابتة فيها الضمانات الأساسية: RTL عربي، حالة تحميل معلنة
 * لقارئ الشاشة، حلقة تركيز مرئية للكيبورد، وأهداف لمس بحجم كافٍ. دي فحوص مصدرية
 * (تتحقق من وجود القواعد/السمات)، ومش بديل عن تحقّق متصفّح حقيقي — اللي مذكور
 * صراحةً كغير مُتحقَّق منه في التقرير.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const STATIC = path.resolve(__dirname, "../../bot/web/static");
const html = fs.readFileSync(path.join(STATIC, "index.html"), "utf8");
const css = fs.readFileSync(path.join(STATIC, "styles.css"), "utf8");

test("a11y: الصفحة عربية RTL (lang=ar, dir=rtl)", () => {
  assert.match(html, /<html[^>]*lang="ar"/);
  assert.match(html, /<html[^>]*dir="rtl"/);
});

test("a11y: حالة التحميل معلنة لقارئ الشاشة (role=status + aria-live)", () => {
  assert.match(html, /id="state-loading"[^>]*role="status"/);
  assert.match(html, /id="state-loading"[^>]*aria-live="polite"/);
});

test("a11y: حالة الخطأ معلنة (role=alert) وليها زر إعادة محاولة", () => {
  assert.match(html, /id="state-error"[^>]*role="alert"/);
  assert.match(html, /id="retry-btn"/);
});

test("a11y: حلقة تركيز مرئية معرّفة للعناصر التفاعلية", () => {
  assert.match(css, /:focus-visible/);
  assert.match(css, /outline:\s*2px solid/);
});

test("a11y: أهداف لمس بزر بارتفاع أدنى 44px", () => {
  assert.match(css, /min-height:\s*44px/);
});
