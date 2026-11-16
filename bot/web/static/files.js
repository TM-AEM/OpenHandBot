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

  // ======================================================= تنقّل المجلدات (OHB2-PLAN-13-WS-01)
  // القايمة من الخادم **مسطّحة** (مسارات نسبية آمنة زي `src/main.py`). الهرمية
  // بتتبني **محليًا** من نص المسار (تقسيم على `/`) — مفيش راوت جديد ولا قراءة
  // إضافية، وكل مسار هنا عدّى بالفعل allowlist الخادم (`is_safe_workspace_path`).

  function splitPath(path) {
    if (typeof path !== "string" || path === "") { return []; }
    return path.split("/");
  }

  function joinPath(parts) {
    return (parts || []).join("/");
  }

  // بنية شجرة: {folders: {name: node}, files: [name]}. كل مسار ملف بينزل في مكانه.
  // المسار بيتفحص **كله** الأول (fail-closed) قبل أي إدخال، فمسار غير صالح مايسيبش
  // مجلدات جزئية فاضية في الشجرة.
  function buildTree(paths) {
    var root = { folders: {}, files: [] };
    var list = paths || [];
    for (var i = 0; i < list.length; i++) {
      var path = list[i];
      if (typeof path !== "string" || path === "") { continue; }
      var parts = path.split("/");
      var valid = true;
      for (var v = 0; v < parts.length; v++) {
        if (parts[v] === "" || parts[v] === "." || parts[v] === "..") { valid = false; break; }
      }
      if (!valid) { continue; }
      var node = root;
      for (var j = 0; j < parts.length - 1; j++) {
        var seg = parts[j];
        if (!node.folders[seg]) { node.folders[seg] = { folders: {}, files: [] }; }
        node = node.folders[seg];
      }
      node.files.push(parts[parts.length - 1]);
    }
    return root;
  }

  // العقدة عند مسار مجلد معيّن ("" = الجذر)، أو null لو المسار مش مجلد معروف.
  function resolveNode(root, path) {
    var node = root;
    var parts = splitPath(path);
    for (var i = 0; i < parts.length; i++) {
      var seg = parts[i];
      if (!node || !node.folders[seg]) { return null; }
      node = node.folders[seg];
    }
    return node;
  }

  function hasFiles(node) {
    return !!(node && (node.files.length > 0 || Object.keys(node.folders).length > 0));
  }

  // المجلد الأعلى للمسار، أو null لو إحنا في الجذر (مفيش «لأعلى»).
  function parentPath(path) {
    var parts = splitPath(path);
    if (!parts.length) { return null; }
    return joinPath(parts.slice(0, -1));
  }

  // صفوف العرض لمجلد: المجلدات الأول (مرتّبة) وبعدها الملفات (مرتّبة). الاسم بس؛
  // المستدعي بيبني المسار الكامل بـ `childPath(dir, name)`.
  function entryRows(node) {
    var rows = [];
    if (!node) { return rows; }
    var folders = Object.keys(node.folders).sort();
    for (var i = 0; i < folders.length; i++) {
      rows.push({ name: folders[i], type: "folder" });
    }
    var files = node.files.slice().sort();
    for (var k = 0; k < files.length; k++) {
      rows.push({ name: files[k], type: "file" });
    }
    return rows;
  }

  // فتات التنقّل: [{label, path}] من الجذر (مسمّى "الرئيسية") لآخر مقطع.
  function breadcrumbs(path) {
    var crumbs = [{ label: "الرئيسية", path: "" }];
    var parts = splitPath(path);
    var acc = [];
    for (var i = 0; i < parts.length; i++) {
      acc.push(parts[i]);
      crumbs.push({ label: parts[i], path: joinPath(acc) });
    }
    return crumbs;
  }

  // مسار مجلد فرعي نسبةً للمجلد الحالي.
  function childPath(dir, name) {
    var base = splitPath(dir);
    base.push(name);
    return joinPath(base);
  }

  // تنقّل آمن داخل المجلدات (fail-closed): بنقبل بس مجلد معروف في الشجرة،
  // وبنرفض أي مسار مش مجلد (ملف/غير موجود) — مفيش اجتياز خارج القايمة المصرّح بها.
  function safeDir(target, root) {
    if (target === "" || target === null || target === undefined) { return ""; }
    if (typeof target !== "string") { return null; }
    return resolveNode(root, target) ? target : null;
  }

  // حالة تنقّل محفوظة لكل شات عبر إعادة تحميل الصفحة (بيتفشل بأمان لو التخزين مقفول).
  function storageKey(conversationId) { return "ohb2.files.dir." + String(conversationId); }
  function readDir(store, conversationId) {
    try {
      var v = store && store.getItem(storageKey(conversationId));
      return typeof v === "string" ? v : "";
    } catch (e) { return ""; }
  }
  function writeDir(store, conversationId, path) {
    try {
      if (path) { store.setItem(storageKey(conversationId), path); }
      else { store.removeItem(storageKey(conversationId)); }
    } catch (e) { /* التخزين مش متاح ⇒ التنقّل يفضل شغّال من غير حفظ (fail-open للعرض فقط) */ }
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
    createDeduper: createDeduper,
    // OHB2-PLAN-13-WS-01: تنقّل المجلدات (هرمي محلي فوق القايمة المسطّحة).
    buildTree: buildTree,
    resolveNode: resolveNode,
    hasFiles: hasFiles,
    parentPath: parentPath,
    entryRows: entryRows,
    breadcrumbs: breadcrumbs,
    childPath: childPath,
    safeDir: safeDir,
    readDir: readDir,
    writeDir: writeDir
  };
});
