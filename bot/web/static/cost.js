/* OHB2-09-04 — منطق عرض التكلفة/الاستهلاك في الـ Mini App.
 *
 * مستقل عن الـ DOM عشان يتاختبر بـ Node مباشرة (tests/frontend/cost.test.js)
 * وبنفس الوقت هو **نفس** المنطق اللي الواجهة (app.js) بتستعمله — مش نسخة مكرّرة.
 */
(function (root, factory) {
  if (typeof module === "object" && typeof module.exports === "object") {
    module.exports = factory();
  } else {
    root.RecovoCost = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function isNum(v) {
    return typeof v === "number" && isFinite(v);
  }

  // هل فيه أي بيانات تكلفة/استهلاك معروضة؟
  function hasCost(payload) {
    if (!payload || typeof payload !== "object") { return false; }
    return isNum(payload.accumulated_cost) || isNum(payload.prompt_tokens) ||
      isNum(payload.completion_tokens) || isNum(payload.total_tokens) ||
      (typeof payload.model === "string" && payload.model !== "");
  }

  // سطر تكلفة منظّم بالعربي (بدون HTML). قيمة ناقصة ⇒ السطر مايظهرش.
  // **العملة مش محدّدة** (عقد `accumulated_cost` مافيهوش عملة مثبتة) ⇒ ما بنعرضش أي
  // رمز عملة زي $ عشان ما ندّعيش وحدة نقدية غير مثبتة (OHB2-09-04-R1).
  function formatCost(payload) {
    if (!hasCost(payload)) { return "مفيش بيانات تكلفة."; }
    var lines = [];
    if (typeof payload.model === "string" && payload.model !== "") {
      lines.push("الموديل: " + payload.model);
    }
    if (isNum(payload.accumulated_cost)) {
      lines.push("التكلفة التراكمية: " + payload.accumulated_cost.toFixed(4));
    }
    if (isNum(payload.prompt_tokens)) {
      lines.push("توكنز الإدخال: " + Math.trunc(payload.prompt_tokens));
    }
    if (isNum(payload.completion_tokens)) {
      lines.push("توكنز الإخراج: " + Math.trunc(payload.completion_tokens));
    }
    if (!isNum(payload.prompt_tokens) && !isNum(payload.completion_tokens) && isNum(payload.total_tokens)) {
      lines.push("إجمالي التوكنز: " + Math.trunc(payload.total_tokens));
    }
    return lines.join("\n");
  }

  return {
    hasCost: hasCost,
    formatCost: formatCost
  };
});
