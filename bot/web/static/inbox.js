/* OHB2-08-05 — منطق صندوق الإشعارات (history) للـ Mini App.
 *
 * مستقل عن الـ DOM عشان يتاختبر بـ Node مباشرة (tests/frontend/inbox.test.js)
 * وبنفس الوقت هو **نفس** المنطق اللي الواجهة (app.js) بتستعمله — مش نسخة مكرّرة.
 */
(function (root, factory) {
  if (typeof module === "object" && typeof module.exports === "object") {
    module.exports = factory();
  } else {
    root.RecovoInbox = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // أسماء أنواع الإشعارات بالعربي (زي ما بتتكتب في القاعدة `kind`).
  var KINDS = {
    terminal: "انتهى شات",
    timeout: "انتهت مهلة",
    missing: "شات مفقود",
    stale_report: "بدون تقرير جديد",
    proactive: "إشعار عام"
  };

  // نص شارة العدد في التبويب. صفر/سالب/غير رقم ⇒ "" (مفيش شارة).
  function badgeText(count) {
    var n = Number(count);
    if (!isFinite(n) || n <= 0) { return ""; }
    n = Math.floor(n);
    return n > 99 ? "99+" : String(n);
  }

  function kindLabel(kind) {
    return KINDS[kind] || "إشعار";
  }

  // عنصر غير مقروء: `read` لازم تكون true صراحةً عشان نعتبره مقروء.
  function isUnread(item) {
    return !(item && item.read === true);
  }

  // OHB2-08-05 (Batch 3R): حالة تسليم الإشعار بالعربي. `delivered` (الافتراضي) مش
  // محتاجة شارة؛ `pending`/`failed` بتظهر عشان المستخدم يعرف إن الإشعار لسه ماوصلش.
  function deliveryLabel(status) {
    if (status === "pending") { return "بيتسلّم…"; }
    if (status === "failed") { return "فشل التسليم"; }
    return "";  // delivered أو غير معروف ⇒ مفيش شارة
  }

  // الصفحة الجاية: نزوّد بس لو فيه المزيد. لو لأ، نرجّع نفس الصفحة (مفيش طلب زايد).
  function nextPage(current, hasMore) {
    var page = Number(current);
    if (!isFinite(page) || page < 0) { page = 0; }
    return hasMore ? Math.floor(page) + 1 : Math.floor(page);
  }

  // OHB2-08-07: فاصل التحديث الدوري لصندوق الإشعارات حسب رؤية الصفحة. صفحة مرئية ⇒
  // بنحدّث دوريًا؛ صفحة مخفية (الخلفية) ⇒ صفر (مفيش polling ⇒ توفير شبكة/بطارية).
  var REFRESH_VISIBLE_MS = 30000;

  function refreshInterval(visible) {
    return visible ? REFRESH_VISIBLE_MS : 0;
  }

  // OHB2-08-07: نمنع التحديثات المكرّرة المتلاحقة (رجوع سريع للصفحة + poll في نفس
  // اللحظة). بنرجّع true لو لسه بدري على تحديث جديد. `last`<=0 (أول مرة) ⇒ نسمح.
  var MIN_REFRESH_GAP_MS = 5000;

  function shouldThrottleRefresh(last, now, minGap) {
    var gap = Number(minGap);
    if (!isFinite(gap) || gap < 0) { gap = MIN_REFRESH_GAP_MS; }
    var l = Number(last);
    var n = Number(now);
    if (!isFinite(l) || l <= 0 || !isFinite(n)) { return false; }
    return (n - l) < gap;
  }

  // OHB2-PHASE1C: هل العنصر مؤرشف؟ (حقل `archived` من السيرفر، أو `archived_at` للتوافق).
  function isArchived(item) {
    if (!item) { return false; }
    if (item.archived === true) { return true; }
    return !!(item.archived_at);
  }

  // OHB2-PHASE1C: هل السيرفر/الواجهة يعتبروا العنصر قابلًا للحذف النهائي؟ إشارة للواجهة
  // بس (القرار النهائي على السيرفر). لو السيرفر ما بعتش `deletable`، نستنتج: مُسلَّم + مقروء.
  function canDelete(item) {
    if (!item) { return false; }
    if (typeof item.deletable === "boolean") { return item.deletable; }
    return !isUnread(item) && (item.delivery_status === undefined || item.delivery_status === "delivered");
  }

  // OHB2-PHASE1C: نص استعلام القايمة حسب الفلتر (كل/غير المقروء) والأرشيف. بيُستخدم في
  // **نفس** نداء الـ API الموجود (`unread=1`) — مفيش فلترة مكرّرة في الواجهة.
  function filterQuery(page, unreadOnly, archived) {
    var p = Number(page);
    if (!isFinite(p) || p < 0) { p = 0; }
    var parts = ["page=" + Math.floor(p)];
    if (unreadOnly) { parts.push("unread=1"); }
    if (archived) { parts.push("archived=1"); }
    return parts.join("&");
  }

  // OHB2-PHASE1C: نص الحالة الفاضية حسب الفلتر/العرض.
  function emptyText(unreadOnly, archived) {
    if (archived) { return "مفيش إشعارات مؤرشفة."; }
    if (unreadOnly) { return "مفيش إشعارات غير مقروءة."; }
    return "مفيش إشعارات.";
  }

  return {
    KINDS: KINDS,
    badgeText: badgeText,
    kindLabel: kindLabel,
    isUnread: isUnread,
    isArchived: isArchived,
    canDelete: canDelete,
    filterQuery: filterQuery,
    emptyText: emptyText,
    deliveryLabel: deliveryLabel,
    nextPage: nextPage,
    refreshInterval: refreshInterval,
    shouldThrottleRefresh: shouldThrottleRefresh
  };
});
