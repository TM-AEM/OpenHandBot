/* OHB2-PHASE1B — مساعدات تصدير الشات في الـ Mini App (مستقلة عن الـ DOM).
 *
 * بتتاختبر بـ Node مباشرة (tests/frontend/export.test.js) وهي **نفس** المنطق اللي
 * app.js بيستعمله. الهدف: اسم ملف تنزيل آمن + رسائل أخطاء عربي واضحة، من غير أي
 * اعتماد على نص الرد اللي جاي من السيرفر (بنقراه بحذر).
 */
(function (root, factory) {
  if (typeof module === "object" && typeof module.exports === "object") {
    module.exports = factory();
  } else {
    root.RecovoExport = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var DEFAULT_NAME = "conversation.zip";
  // نفس مجموعة البوت الآمنة: حروف/أرقام/`-`/`_`/`.`
  var SAFE = /[^A-Za-z0-9._-]/g;

  var ERROR_LABELS = {
    unauthenticated: "محتاج تسجيل دخول.",
    forbidden: "الحساب ده مش مسموح له.",
    bad_origin: "الطلب جاي من أصل غير مسموح.",
    rate_limited: "طلبات كتير، استنى شوية وجرّب تاني.",
    not_found: "الشات مش موجود.",
    invalid_conversation: "معرّف الشات غير صالح.",
    too_large: "التصدير كبير أوي للتنزيل الآمن. جرّب شات أصغر.",
    upstream_error: "تعذّر الوصول للشات دلوقتي، جرّب تاني.",
    api_error: "تعذّر تصدير الشات دلوقتي، جرّب تاني."
  };

  // اسم ملف آمن (نفس قواعد السيرفر) — بيتنقّى لمحارف ASCII آمنة بس.
  function safeFilename(name) {
    if (typeof name !== "string") { return DEFAULT_NAME; }
    var trimmed = name.replace(/^.*[\\/]/, "").trim();  // نمنع أي مكوّن مسار
    var cleaned = trimmed.replace(SAFE, "");
    if (!cleaned || cleaned === "." || cleaned === "..") { return DEFAULT_NAME; }
    return cleaned;
  }

  // يقرأ `filename` من هيدر `Content-Disposition` بأمان، وإلا اسم افتراضي.
  function filenameFromDisposition(header) {
    if (typeof header !== "string" || header === "") { return DEFAULT_NAME; }
    var quoted = /filename\s*=\s*"([^"]*)"/i.exec(header);
    if (quoted) { return safeFilename(quoted[1]); }
    var bare = /filename\s*=\s*([^;]+)/i.exec(header);
    if (bare) { return safeFilename(bare[1]); }
    return DEFAULT_NAME;
  }

  function errorLabel(code, fallback) {
    if (Object.prototype.hasOwnProperty.call(ERROR_LABELS, code)) { return ERROR_LABELS[code]; }
    return fallback || "حصل خطأ غير متوقع، جرّب تاني.";
  }

  return {
    DEFAULT_NAME: DEFAULT_NAME,
    ERROR_LABELS: ERROR_LABELS,
    safeFilename: safeFilename,
    filenameFromDisposition: filenameFromDisposition,
    errorLabel: errorLabel
  };
});
