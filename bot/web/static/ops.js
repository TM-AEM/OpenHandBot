/* OHB2-07-FIX — منطق دورة حياة معرّف العملية (idempotency) للـ Mini App.
 *
 * مستقل عن الـ DOM عشان يتاختبر بـ Node مباشرة (tests/frontend/ops.test.js) وبنفس
 * الوقت هو **نفس** المنطق اللي الواجهة (app.js) بتستعمله — مش نسخة مكرّرة في الاختبار.
 *
 * الفكرة: كل عملية (برومت أو إنشاء شات) ليها "مفتاح هوية" (identity key) + معرّف
 * (client_ref) السيرفر بيستخدمه لعمل idempotency. القاعدة:
 *   - فيه عملية **نشطة** (pending/ambiguous) بنفس المفتاح ⇒ نعيد نفس المعرّف
 *     (إعادة محاولة/ضغط مزدوج مايكرّرش العملية).
 *   - العملية وصلت حالة **نهائية** (accepted/failed) ⇒ أول إرسال جديد بنفس المفتاح
 *     بياخد معرّف **جديد** (مايتلغاش بسبب عملية قديمة خلصت).
 */
(function (root, factory) {
  if (typeof module === "object" && typeof module.exports === "object") {
    module.exports = factory();
  } else {
    root.RecovoOps = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // الحالات النهائية: بعدها العملية ما بقتش نشطة، فأول إرسال جديد بنفس المفتاح
  // بياخد معرّف جديد. (pending/ambiguous لسه نشطة ⇒ نعيد نفس المعرّف.)
  var TERMINAL = { accepted: true, failed: true };

  function defaultNewRef() {
    var rnd = "";
    try {
      if (typeof crypto !== "undefined" && crypto.getRandomValues) {
        var a = new Uint8Array(16);
        crypto.getRandomValues(a);
        for (var i = 0; i < a.length; i++) {
          rnd += ("0" + a[i].toString(16)).slice(-2);
        }
        return rnd;
      }
    } catch (e) { /* fallback تحت */ }
    rnd = String(Date.now().toString(16)) + Math.random().toString(16).slice(2, 10);
    return rnd.replace(/[^a-z0-9]/gi, "").slice(0, 32);
  }

  // مفتاح هوية ثابت من أجزاء متعدّدة (يستخدم فاصل مش ممكن يظهر في المدخلات).
  // للبرومت: [conversationId, text]. لإنشاء شات: [repository, text].
  function identityKey(parts) {
    return parts
      .map(function (p) { return String(p === undefined || p === null ? "" : p); })
      .join("\u0000");
  }

  // مدير معرّف العملية لتدفّق واحد (برومت لكل شات، أو إنشاء شات).
  function createRefManager(newRefFn) {
    var makeRef = newRefFn || defaultNewRef;
    var current = null;
    return {
      // عملية جديدة بمعرّف جديد، أو نفس المعرّف لو فيه عملية **نشطة** بنفس المفتاح.
      acquire: function (key, payload) {
        if (current && current.key === key && current.active) {
          return current.ref;
        }
        current = { ref: makeRef(), key: key, payload: payload, active: true, state: "pending" };
        return current.ref;
      },
      // إعادة محاولة/استعلام عن العملية الحالية: دايمًا نفس المعرّف (idempotent).
      ref: function () { return current ? current.ref : null; },
      payload: function () { return current ? current.payload : null; },
      key: function () { return current ? current.key : null; },
      active: function () { return !!(current && current.active); },
      state: function () { return current ? current.state : null; },
      // تسجيل الحالة اللي رصدناها. الحالات النهائية بتوقف العملية؛
      // pending/ambiguous بتسيبها نشطة (المعرّف يتحفظ لحد ما تتحسم).
      // `ref` بيتأكد إننا بنحدّث **نفس** العملية (مش عملية أحدث بدأت بعدها).
      resolve: function (ref, state) {
        if (!current || current.ref !== ref) { return; }
        current.state = state || current.state;
        if (TERMINAL[current.state]) { current.active = false; }
      }
    };
  }

  return {
    defaultNewRef: defaultNewRef,
    identityKey: identityKey,
    createRefManager: createRefManager
  };
});
