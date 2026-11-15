/* OHB2-MT-2 — منطق تنزيل المرفقات المحلية في الـ Mini App.
 *
 * مستقل عن الـ DOM عشان يتاختبر بـ Node مباشرة (tests/frontend/attachments.test.js)،
 * وبنفس الوقت هو **نفس** المنطق اللي الواجهة (app.js) بتستعمله — مش نسخة مكرّرة.
 *
 * مبدأ أمني/صادق: التنزيل **محلي** بس (المتصفّح حفظ الملف على الجهاز). ده **مش**
 * تسليم لـ OpenHands، ومفيش أي رسالة بتدّعي التسليم. الرسائل الثلاثة مميّزة:
 *   - «جاهز للتنزيل» = المخزن عنده نسخة محلية (بس).
 *   - «اتنزّل على جهازك» = السيرفر بعث الرد للمتصفّح (بس).
 *   - «اتسلّم لـ OpenHands» = **مش** مُرصود من الـ Mini App ⇒ ما بنقولوش أبدًا.
 */
(function (root, factory) {
  if (typeof module === "object" && typeof module.exports === "object") {
    module.exports = factory();
  } else {
    root.RecovoAttachments = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var DEFAULT_NAME = "attachment";
  // نفس مجموعة السيرفر الآمنة: ASCII فقط (حروف/أرقام/`-`/`_`/`.`).
  var SAFE = /[^A-Za-z0-9._-]/g;

  // نصوص عربية صادقة (مفيش ادّعاء تسليم).
  var TEXT = {
    ready: "📎 الملف جاهز للتنزيل من هنا.",
    localNote: "⚠️ ده تخزين محلي عندنا، مش تسليم لـ OpenHands.",
    starting: "⏳ بيتم تجهيز الملف للتنزيل…",
    done: "✅ نزّلنا الملف على جهازك.",
    notDelivered: "⚠️ ده مش معناه إن OpenHands استلمه — لازم ترفعه بنفسك.",
    empty: "مفيش مرفقات جاهزة للتنزيل دلوقتي.",
    expiredSession: "🔒 الجلسة انتهت. سجّل دخول تاني وجرّب.",
    expiredAttachment: "⌛ الملف المحلي مش متاح (انتهت الـ 15 دقيقة). ابعت الملف تاني لو محتاجه.",
    unavailable: "⚠️ الملف مش متاح دلوقتي. جرّب تاني.",
    network: "⚠️ التنزيل اتقطع. جرّب تاني.",
    retry: "لو استمرّت المشكلة، ابعت الملف من جديد."
  };

  // رموز أخطاء الـ API ⇒ رسالة عربية واضحة.
  var ERROR_LABELS = {
    unauthenticated: TEXT.expiredSession,
    forbidden: "الحساب ده مش مسموح له.",
    bad_origin: "الطلب جاي من أصل غير مسموح.",
    rate_limited: "طلبات كتير، استنى شوية وجرّب تاني.",
    not_found: TEXT.unavailable,
    expired: TEXT.expiredAttachment,
    unavailable: TEXT.unavailable,
    integrity: TEXT.unavailable,
    upstream_error: TEXT.unavailable,
    api_error: TEXT.unavailable
  };

  function errorLabel(code, fallback) {
    if (Object.prototype.hasOwnProperty.call(ERROR_LABELS, code)) { return ERROR_LABELS[code]; }
    return fallback || "حصل خطأ غير متوقع، جرّب تاني.";
  }

  // اسم ملف آمن من هيدر Content-Disposition (نفس قواعد التصدير، بلا اعتماد على نص).
  function safeFilename(name) {
    if (typeof name !== "string") { return DEFAULT_NAME; }
    var trimmed = name.replace(/^.*[\\/]/, "").trim();
    var cleaned = trimmed.replace(SAFE, "");
    if (!cleaned || cleaned === "." || cleaned === "..") { return DEFAULT_NAME; }
    return cleaned;
  }

  function filenameFromDisposition(header) {
    if (typeof header !== "string" || header === "") { return DEFAULT_NAME; }
    var quoted = /filename\s*=\s*"([^"]*)"/i.exec(header);
    if (quoted) { return safeFilename(quoted[1]); }
    var bare = /filename\s*=\s*([^;]+)/i.exec(header);
    if (bare) { return safeFilename(bare[1]); }
    return DEFAULT_NAME;
  }

  // حجم مقروء (KB/MB) — للعرض فقط.
  function humanSize(bytes) {
    var n = Number(bytes);
    if (!isFinite(n) || n < 0) { return ""; }
    if (n < 1024) { return n + " B"; }
    if (n < 1024 * 1024) { return (n / 1024).toFixed(1) + " KB"; }
    return (n / (1024 * 1024)).toFixed(2) + " MB";
  }

  // ثواني متبقّية ⇒ نص مختصر (مثلاً "12 د"). للعرض فقط؛ مش بيُمدّد أي مهلة.
  function remainingLabel(seconds) {
    var s = Number(seconds);
    if (!isFinite(s) || s <= 0) { return ""; }
    if (s < 60) { return "أقل من دقيقة"; }
    return Math.floor(s / 60) + " د";
  }

  // قايمة المرفقات من رد الـ API ⇒ عناصر آمنة (تجاهل أي حقل غريب).
  function listItems(data) {
    var items = (data && data.items) || [];
    var out = [];
    for (var i = 0; i < items.length; i++) {
      var it = items[i] || {};
      if (typeof it.item_id !== "string" || it.item_id === "") { continue; }
      out.push({
        item_id: it.item_id,
        display_name: safeFilename(it.display_name),
        size_bytes: Number(it.size_bytes) || 0,
        expires_in: Number(it.expires_in) || 0
      });
    }
    return out;
  }

  return {
    DEFAULT_NAME: DEFAULT_NAME,
    TEXT: TEXT,
    ERROR_LABELS: ERROR_LABELS,
    errorLabel: errorLabel,
    safeFilename: safeFilename,
    filenameFromDisposition: filenameFromDisposition,
    humanSize: humanSize,
    remainingLabel: remainingLabel,
    listItems: listItems
  };
});
