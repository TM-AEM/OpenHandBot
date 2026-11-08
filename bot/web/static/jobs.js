/* OHB2-PHASE1D — منطق عرض/إدارة طلبات الشات الجديد (creation jobs) للـ Mini App.
 *
 * مستقل عن الـ DOM عشان يتاختبر بـ Node مباشرة (tests/frontend/jobs.test.js) وبنفس
 * الوقت هو **نفس** المنطق اللي الواجهة (app.js) بتستعمله — مش نسخة مكرّرة.
 *
 * قاعدة السلامة الجوهرية: ده طبقة **عرض** بس. القرار الحقيقي (هل الإلغاء مؤهّل؟ هل
 * النتيجة الغامضة تتحسم؟) بيتّاخد على السيرفر (parity مع أوامر البوت). الواجهة بتقرأ
 * حقول السيرفر (`cancellable`/`resolvable`/`post_state`) — لو الحقل مش `true` صراحةً،
 * الإجراء **مايتعرضش** (fail closed). مستحيل إجراء واجهة يتجاوز حرس السيرفر.
 */
(function (root, factory) {
  if (typeof module === "object" && typeof module.exports === "object") {
    module.exports = factory();
  } else {
    root.RecovoJobs = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // حالة الطلب بالعربي (نفس مفردات خريطة السيرفر).
  var STATES = {
    pending: "قيد التنفيذ",
    accepted: "اتعمل",
    failed: "فشل",
    ambiguous: "مش متأكدين",
    discarded: "اتلغى",
    unknown: "مش معروف"
  };

  // وصف آمن لحدّ POST البدء (مشتق على السيرفر من الحالة الحقيقية).
  var POST_STATES = {
    not_started: "لسه مابدأش",
    uncertain: "ممكن يكون بدأ",
    started: "بدأ فعلاً",
    failed: "فشل مؤكد",
    cancelled: "اتلغى قبل الإرسال"
  };

  // رسالة توضيحية آمنة لكل حالة — من غير أي ادّعاء نجاح/فشل بدون دليل.
  var NOTES = {
    pending: "الطلب في الطابور. لو لسه مابدأش تقدر تلغيه بأمان.",
    accepted: "الشات بدأ فعلاً واتأكد. مفيش أي إعادة إرسال.",
    failed: "البدء فشل بشكل مؤكد (مفيش إعادة تلقائية).",
    ambiguous: "النتيجة غامضة: ممكن يكون الشات بدأ فعلاً. استعلم عن الحالة من الموقع، ولو مش متأكد علّم الطلب كـ«بدأ».",
    discarded: "اتلغى قبل ما يتبعت. مفيش أي إرسال حصل.",
    unknown: "حالة الطلب مش معروفة."
  };

  function stateLabel(state) {
    return STATES[state] || "مش معروف";
  }

  function postStateLabel(postState) {
    return POST_STATES[postState] || "";
  }

  function note(item) {
    var state = (item && item.state) || "unknown";
    return NOTES[state] || NOTES.unknown;
  }

  // الإلغاء معروض **بس** لو السيرفر قال صراحةً إنه مؤهّل (pre-POST).
  function canCancel(item) {
    return !!(item && item.cancellable === true);
  }

  // حسم الغموض («بدأ») معروض **بس** لو السيرفر قال إن الطلب `ambiguous`.
  function canResolve(item) {
    return !!(item && item.resolvable === true);
  }

  // فيه محادثة بعيدة معروفة (بدليل من السيرفر) ⇒ نعرض زرار فتحها.
  function hasConversation(item) {
    return !!(item && typeof item.conversation_id === "string" && item.conversation_id);
  }

  // النتيجة غامضة (ممكن يكون الشات بدأ) — نعرض تحذير واضح بعدم إعادة المحاولة.
  function isAmbiguous(item) {
    return !!item && item.state === "ambiguous";
  }

  return {
    stateLabel: stateLabel,
    postStateLabel: postStateLabel,
    note: note,
    canCancel: canCancel,
    canResolve: canResolve,
    hasConversation: hasConversation,
    isAmbiguous: isAmbiguous
  };
});
