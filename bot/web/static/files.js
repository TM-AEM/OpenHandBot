/* OHB2-09-02 — منطق عرض ملفات الشات في الـ Mini App.
 *
 * مستقل عن الـ DOM عشان يتاختبر بـ Node مباشرة (tests/frontend/files.test.js)
 * وبنفس الوقت هو **نفس** المنطق اللي الواجهة (app.js) بتستعمله — مش نسخة مكرّرة.
 * كل النصوص بالعربي وبتشتغل في سياق RTL.
 */
(function (root, factory) {
  if (typeof module === "object" && typeof module.exports === "object") {
    module.exports = factory();
  } else {
    root.RecovoFiles = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // حالة محتوى الملف (من حقل `status` في رد المعاينة).
  var CONTENT_STATUS = {
    ok: "",
    binary: "محتوى ثنائي — مش قابل للعرض.",
    not_utf8: "ترميز الملف مش UTF-8.",
    too_large: "الملف كبير أوي للعرض."
  };

  // رموز أخطاء الـ Files API (من حقل `error`).
  var ERROR_LABELS = {
    unauthenticated: "محتاج تسجيل دخول.",
    forbidden: "الحساب ده مش مسموح له.",
    bad_origin: "الطلب جاي من أصل غير مسموح.",
    rate_limited: "طلبات كتير، استنى شوية وجرّب تاني.",
    invalid_conversation: "معرّف الشات غير صالح.",
    invalid_path: "مسار الملف غير صالح.",
    not_found: "الملف أو الشات مش موجود.",
    unauthorized: "مش مسموح لك بالوصول لملفات الشات ده.",
    too_large: "الملف كبير أوي للعرض.",
    upstream_error: "تعذّر الوصول لملفات الشات دلوقتي، جرّب تاني.",
    api_error: "تعذّر الوصول لملفات الشات دلوقتي، جرّب تاني."
  };

  function contentStatusLabel(status) {
    return Object.prototype.hasOwnProperty.call(CONTENT_STATUS, status)
      ? CONTENT_STATUS[status]
      : "حالة ملف غير معروفة.";
  }

  function errorLabel(code, fallback) {
    if (Object.prototype.hasOwnProperty.call(ERROR_LABELS, code)) { return ERROR_LABELS[code]; }
    return fallback || "حصل خطأ غير متوقع، جرّب تاني.";
  }

  // نص المعاينة اللي يتحطّ في الشاشة، أو رسالة بديلة لو مفيش نص معروض.
  function previewText(payload) {
    if (!payload || typeof payload !== "object") { return "مفيش محتوى."; }
    var status = payload.status;
    if (status && status !== "ok") { return contentStatusLabel(status); }
    var text = payload.text;
    if (typeof text !== "string" || text === "") { return "الملف فاضي."; }
    return text;
  }

  function isTruncated(payload) {
    return !!(payload && payload.truncated === true);
  }

  // منع الطلبات المكرّرة المتزامنة لنفس المفتاح: أول نداء بيسجّل الوعد الجاري،
  // وأي نداء تاني بنفس المفتاح بيرجّع نفس الوعد (مفيش طلب شبكة زايد).
  function createDeduper() {
    var inflight = {};
    return {
      run: function (key, fn) {
        if (Object.prototype.hasOwnProperty.call(inflight, key)) { return inflight[key]; }
        var p;
        try {
          p = Promise.resolve(fn());
        } catch (err) {
          p = Promise.reject(err);
        }
        inflight[key] = p;
        var clear = function () { delete inflight[key]; };
        p.then(clear, clear);
        return p;
      },
      active: function (key) {
        return Object.prototype.hasOwnProperty.call(inflight, key);
      },
      size: function () { return Object.keys(inflight).length; }
    };
  }

  return {
    CONTENT_STATUS: CONTENT_STATUS,
    ERROR_LABELS: ERROR_LABELS,
    contentStatusLabel: contentStatusLabel,
    errorLabel: errorLabel,
    previewText: previewText,
    isTruncated: isTruncated,
    createDeduper: createDeduper
  };
});
