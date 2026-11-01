/* OHB2-08-05 — اختبارات منطق صندوق الإشعارات في الواجهة.
 *
 * بتشتغل بـ Node المدمج: `node --test tests/frontend/`
 * بتختبر **نفس** الوحدة (bot/web/static/inbox.js) اللي app.js بيستعملها — مش نسخة مكرّرة.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const INBOX = require("../../bot/web/static/inbox.js");

test("badgeText: zero/negative/NaN -> empty (no badge)", () => {
  assert.equal(INBOX.badgeText(0), "");
  assert.equal(INBOX.badgeText(-3), "");
  assert.equal(INBOX.badgeText("abc"), "");
  assert.equal(INBOX.badgeText(null), "");
  assert.equal(INBOX.badgeText(undefined), "");
});

test("badgeText: positive numbers, caps above 99", () => {
  assert.equal(INBOX.badgeText(1), "1");
  assert.equal(INBOX.badgeText(9), "9");
  assert.equal(INBOX.badgeText("12"), "12");
  assert.equal(INBOX.badgeText(99), "99");
  assert.equal(INBOX.badgeText(100), "99+");
  assert.equal(INBOX.badgeText(12345), "99+");
});

test("badgeText: floors fractional counts", () => {
  assert.equal(INBOX.badgeText(2.9), "2");
});

test("kindLabel: known kinds map to Arabic labels", () => {
  assert.equal(INBOX.kindLabel("terminal"), "انتهى شات");
  assert.equal(INBOX.kindLabel("timeout"), "انتهت مهلة");
  assert.equal(INBOX.kindLabel("missing"), "شات مفقود");
  assert.equal(INBOX.kindLabel("stale_report"), "بدون تقرير جديد");
  assert.equal(INBOX.kindLabel("proactive"), "إشعار عام");
});

test("kindLabel: unknown/missing kind falls back", () => {
  assert.equal(INBOX.kindLabel("weird"), "إشعار");
  assert.equal(INBOX.kindLabel(""), "إشعار");
  assert.equal(INBOX.kindLabel(null), "إشعار");
});

test("isUnread: only explicit read===true counts as read", () => {
  assert.equal(INBOX.isUnread({ read: false }), true);
  assert.equal(INBOX.isUnread({}), true);            // الحقل ناقص ⇒ غير مقروء
  assert.equal(INBOX.isUnread({ read: "true" }), true); // نص مش bool ⇒ غير مقروء
  assert.equal(INBOX.isUnread({ read: true }), false);
  assert.equal(INBOX.isUnread(null), true);
});

test("deliveryLabel: pending/failed get a badge, delivered/unknown do not", () => {
  assert.equal(INBOX.deliveryLabel("pending"), "بيتسلّم…");
  assert.equal(INBOX.deliveryLabel("failed"), "فشل التسليم");
  assert.equal(INBOX.deliveryLabel("delivered"), "");
  assert.equal(INBOX.deliveryLabel(undefined), "");
  assert.equal(INBOX.deliveryLabel(null), "");
  assert.equal(INBOX.deliveryLabel("weird"), "");
});

test("nextPage: advances only when has_more", () => {
  assert.equal(INBOX.nextPage(0, true), 1);
  assert.equal(INBOX.nextPage(3, true), 4);
  assert.equal(INBOX.nextPage(3, false), 3);  // مفيش المزيد ⇒ نفس الصفحة
  assert.equal(INBOX.nextPage("2", true), 3); // بتتعامل مع نص
});

test("nextPage: sanitizes invalid current page", () => {
  assert.equal(INBOX.nextPage(-5, true), 1);
  assert.equal(INBOX.nextPage("x", true), 1);
  assert.equal(INBOX.nextPage(null, true), 1);
});


// --- wiring guards: الواجهة فعلاً بتستخدم نفس المنطق المشترك ---------------------

const fs = require("node:fs");
const path = require("node:path");
const STATIC = path.resolve(__dirname, "../../bot/web/static");

test("wiring: index.html loads inbox.js before app.js", () => {
  const html = fs.readFileSync(path.join(STATIC, "index.html"), "utf8");
  const inboxAt = html.indexOf("/mini/inbox.js");
  const appAt = html.indexOf("/mini/app.js");
  assert.ok(inboxAt !== -1, "inbox.js لازم يكون محمّل");
  assert.ok(appAt !== -1, "app.js لازم يكون محمّل");
  assert.ok(inboxAt < appAt, "inbox.js لازم يتحمّل قبل app.js");
});

test("wiring: app.js uses the shared RecovoInbox module (no duplicate logic)", () => {
  const js = fs.readFileSync(path.join(STATIC, "app.js"), "utf8");
  assert.ok(js.includes("RecovoInbox"), "app.js لازم يستعمل RecovoInbox");
  assert.ok(js.includes("INBOX.isUnread"), "app.js لازم يستعمل isUnread المشتركة");
  assert.ok(js.includes("INBOX.nextPage"), "app.js لازم يستعمل nextPage المشتركة");
  assert.ok(js.includes("INBOX.badgeText"), "app.js لازم يستعمل badgeText المشتركة");
  assert.ok(!/function\s+badgeText\b/.test(js), "badgeText المحلي القديم لازم يختفي");
});

// --- OHB2-08-07: منطق الرؤية + التهدئة (مشترك) --------------------------------

test("refreshInterval: visible polls, hidden does not", () => {
  assert.ok(INBOX.refreshInterval(true) > 0, "مرئي ⇒ فاصل موجب");
  assert.equal(INBOX.refreshInterval(false), 0, "مخفي ⇒ صفر (مفيش polling)");
});

test("refreshInterval: stable positive number for visible", () => {
  const a = INBOX.refreshInterval(true);
  assert.equal(typeof a, "number");
  assert.ok(isFinite(a) && a > 0);
});

test("shouldThrottleRefresh: no previous refresh -> allow", () => {
  assert.equal(INBOX.shouldThrottleRefresh(0, 1000, 0), false);
  assert.equal(INBOX.shouldThrottleRefresh(null, 1000, 0), false);
  assert.equal(INBOX.shouldThrottleRefresh(undefined, 1000, 0), false);
  assert.equal(INBOX.shouldThrottleRefresh(-5, 1000, 0), false);
});

test("shouldThrottleRefresh: within min gap -> throttled, after -> allowed", () => {
  // gap الافتراضي 5000 لو مش مبعت
  assert.equal(INBOX.shouldThrottleRefresh(10000, 12000), true, "أقل من الفاصل ⇒ نمنع");
  assert.equal(INBOX.shouldThrottleRefresh(10000, 15000), false, "عند الفاصل بالظبط ⇒ نسمح");
  assert.equal(INBOX.shouldThrottleRefresh(10000, 20000), false, "بعد الفاصل ⇒ نسمح");
});

test("shouldThrottleRefresh: explicit min gap respected + sanitized", () => {
  assert.equal(INBOX.shouldThrottleRefresh(1000, 1500, 1000), true);
  assert.equal(INBOX.shouldThrottleRefresh(1000, 2500, 1000), false);
  // min gap غير صالح ⇒ يرجع للافتراضي
  assert.equal(INBOX.shouldThrottleRefresh(1000, 1500, "x"), true);
});

test("shouldThrottleRefresh: invalid now -> allow (fail-open)", () => {
  assert.equal(INBOX.shouldThrottleRefresh(1000, NaN, 0), false);
});

test("wiring: app.js uses shared visibility + throttle helpers", () => {
  const js = fs.readFileSync(path.join(STATIC, "app.js"), "utf8");
  assert.ok(js.includes("INBOX.refreshInterval"), "app.js لازم يستعمل refreshInterval");
  assert.ok(js.includes("INBOX.shouldThrottleRefresh"), "app.js لازم يستعمل shouldThrottleRefresh");
  assert.ok(js.includes("visibilitychange"), "app.js لازم يسمع visibilitychange");
});
