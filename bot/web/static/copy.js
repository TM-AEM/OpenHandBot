/* OHB2-PHASE1B — نسخ الرد الكامل للـ assistant في الـ Mini App.
 *
 * مستقل عن الـ DOM عشان يتاختبر بـ Node مباشرة (tests/frontend/copy.test.js)
 * وبنفس الوقت هو **نفس** المنطق اللي الواجهة (app.js) بتستعمله — مش نسخة مكرّرة.
 *
 * المبدأ: **مفيش نجاح كاذب**. الدالة بترجّع نجاح بس لما مسار نسخ حقيقي ينجح
 * (Clipboard API أو fallback `execCommand`)، وأي فشل/رفض صلاحية بيرجّع سبب واضح.
 * العربي/RTL مابيتغيّرش: بننسخ **النص الخام** زي ما هو (بفواصل أسطره).
 */
(function (root, factory) {
  if (typeof module === "object" && typeof module.exports === "object") {
    module.exports = factory();
  } else {
    root.RecovoCopy = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MESSAGES = {
    success: "تم نسخ الرد الكامل ✅",
    failed: "تعذّر النسخ — انسخ يدويًا.",
    empty: "لسه مفيش رد للنسخ."
  };

  function _result(ok, reason, method) {
    return { ok: !!ok, reason: reason || "", method: method || "" };
  }

  // fallback آمن: <textarea> خارج الشاشة + execCommand("copy"). بيرجّع نتيجة حقيقية.
  function _fallback(text, deps) {
    var doc = deps && deps.document;
    if (!doc || typeof doc.createElement !== "function" || typeof doc.execCommand !== "function") {
      return _result(false, "unsupported");
    }
    var ta = null;
    var ok = false;
    try {
      ta = doc.createElement("textarea");
      ta.value = text;
      if (typeof ta.setAttribute === "function") {
        ta.setAttribute("readonly", "");
        ta.setAttribute("aria-hidden", "true");
      }
      var host = doc.body || doc;
      if (host && typeof host.appendChild === "function") { host.appendChild(ta); }
      if (typeof ta.select === "function") { ta.select(); }
      if (typeof ta.setSelectionRange === "function") { ta.setSelectionRange(0, text.length); }
      ok = doc.execCommand("copy") === true;
    } catch (err) {
      ok = false;
    } finally {
      if (ta && typeof ta.remove === "function") {
        try { ta.remove(); } catch (err) { /* نتنضّف بأفضل جهد */ }
      }
    }
    return ok ? _result(true, "", "fallback") : _result(false, "failed");
  }

  // بينسخ `text`، وبيرجّع Promise<{ok, reason, method}>. مايرميش أبدًا.
  function copyText(text, deps) {
    deps = deps || {};
    return new Promise(function (resolve) {
      if (typeof text !== "string" || text === "") {
        resolve(_result(false, "empty"));
        return;
      }
      var nav = deps.navigator;
      var clip = nav && nav.clipboard;
      if (clip && typeof clip.writeText === "function") {
        var p = null;
        try { p = clip.writeText(text); } catch (err) { p = null; }
        if (p && typeof p.then === "function") {
          p.then(
            function () { resolve(_result(true, "", "clipboard")); },
            function () { resolve(_fallback(text, deps)); }
          );
          return;
        }
      }
      resolve(_fallback(text, deps));
    });
  }

  // رسالة عربية واضحة من نتيجة النسخ (للعرض في الواجهة).
  function feedback(result) {
    if (result && result.ok) { return MESSAGES.success; }
    if (result && result.reason === "empty") { return MESSAGES.empty; }
    return MESSAGES.failed;
  }

  return {
    MESSAGES: MESSAGES,
    copyText: copyText,
    feedback: feedback
  };
});
