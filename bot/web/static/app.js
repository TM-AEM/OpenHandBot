/* Mini App (OHB2-06) — JS عادي بحجم صغير، مفيش إطار عمل. */
(function () {
  "use strict";

  var API = "/api/v1";
  var tg = (window.Telegram && window.Telegram.WebApp) || null;
  var REQUEST_TIMEOUT = 12000;
  var state = { chatsPage: 0, currentChat: null, selectedRepo: null, inboxPage: 0, inboxLoading: false, inboxIds: {}, inboxHasMore: false, inboxVisible: false, inboxLastRefreshAt: 0, detailSeq: 0 };
  // OHB2-08-07: مؤقّت التحديث الدوري (مرئي فقط) + آخر وقت تحديث (للتهدئة).
  var inboxPollTimer = null;

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined && text !== null) { n.textContent = text; }
    return n;
  }

  function show(name) {
    ["state-loading", "state-error", "state-ready"].forEach(function (id) {
      var n = $(id);
      if (n) { n.hidden = (id !== name); }
    });
    var app = $("app");
    if (app) { app.setAttribute("aria-busy", name === "state-loading" ? "true" : "false"); }
  }

  function showView(name) {
    // C4 (BATCH-C): لما نخرج من شاشة التفاصيل، نبطّل الشات الحالي. ده بيخلي حرس
    // الردود القديمة (`currentChat`) فعالًا لوحده: رد تفاصيل جاي بعد ما المستخدم ساب
    // الشاشة (تنقّل/رجوع) مايدهسش الشاشة الجديدة، مش بس لو فتح شات تاني.
    if (name !== "view-detail") { state.currentChat = null; }
    ["view-chats", "view-detail", "view-watches", "view-inbox", "view-new", "view-settings"].forEach(function (id) {
      var n = $(id);
      if (n) { n.hidden = (id !== name); }
    });
    var tabs = document.querySelectorAll(".tab");
    for (var i = 0; i < tabs.length; i++) {
      var active = tabs[i].getAttribute("data-view") === name.replace("view-", "");
      tabs[i].classList.toggle("active", active);
      tabs[i].setAttribute("aria-selected", active ? "true" : "false");
    }
  }

  function setError(message) {
    var n = $("error-msg");
    if (n) { n.textContent = message || "حصل خطأ غير متوقع."; }
    show("state-error");
  }

  var toastTimer = null;
  function toast(message) {
    var n = $("toast");
    if (!n) { return; }
    n.textContent = message;
    n.hidden = false;
    if (toastTimer) { clearTimeout(toastTimer); }
    toastTimer = setTimeout(function () { n.hidden = true; }, 2600);
  }

  function friendlyMessage(status, data) {
    if (data && data.message) { return data.message; }
    if (status === 401) { return "محتاج تسجيل دخول."; }
    if (status === 403) { return "الحساب ده مش مسموح له."; }
    if (status === 429) { return "طلبات كتير، استنى شوية وجرّب تاني."; }
    if (status >= 500) { return "الخدمة مش متاحة دلوقتي، جرّب تاني."; }
    return "حصل خطأ غير متوقع، جرّب تاني.";
  }

  function fetchJson(path, options) {
    var opts = options || {};
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, REQUEST_TIMEOUT);
    var init = {
      method: opts.method || "GET",
      headers: { "Accept": "application/json" },
      credentials: "same-origin",
      signal: controller.signal,
      cache: "no-store"
    };
    if (opts.body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(opts.body);
    }
    return fetch(path, init).then(function (res) {
      clearTimeout(timer);
      return res.json().catch(function () { return {}; }).then(function (data) {
        return { status: res.status, ok: res.ok, data: data };
      });
    }).catch(function (err) {
      clearTimeout(timer);
      throw err;
    });
  }

  function get(path) { return fetchJson(API + path); }
  function post(path, body) { return fetchJson(API + path, { method: "POST", body: body }); }
  function del(path) { return fetchJson(API + path, { method: "DELETE" }); }

  function withRetry(fn) {
    return fn().catch(function () {
      return new Promise(function (r) { setTimeout(r, 700); }).then(fn);
    });
  }

  // منطق دورة حياة معرّف العملية (OHB2-07-FIX) — مشترك ومُختبر في ops.js.
  var OPS = window.RecovoOps;
  if (!OPS) { throw new Error("RecovoOps مش محمّل (ops.js)"); }
  var INBOX = window.RecovoInbox;
  if (!INBOX) { throw new Error("RecovoInbox مش محمّل (inbox.js)"); }
  var FILES = window.RecovoFiles;
  if (!FILES) { throw new Error("RecovoFiles مش محمّل (files.js)"); }
  var COST = window.RecovoCost;
  if (!COST) { throw new Error("RecovoCost مش محمّل (cost.js)"); }
  // OHB2-09-02: منع طلبات الملفات المكرّرة المتزامنة (نفس الشات/الملف).
  var filesDeduper = FILES.createDeduper();
  function opKey(parts) { return OPS.identityKey(parts); }

  // حالات العملية اللي السيرفر بيرجّعها: pending/accepted/failed/ambiguous/unknown.
  var OP_TEXT = {
    pending: "قيد التنفيذ…",
    accepted: "وصل ✅",
    failed: "فشل",
    ambiguous: "مش متأكدين",
    unknown: "مش معروف"
  };

  function opPill(op) {
    var state = (op && op.state) || "unknown";
    var pill = el("span", "op-pill", OP_TEXT[state] || state);
    pill.setAttribute("data-op", state);
    return pill;
  }

  // يستعلم عن حالة العملية (GET آمن، idempotent) باستخدام معرّف العملية.
  function queryOperation(kind, ref, conversationId) {
    var q = "?client_ref=" + encodeURIComponent(ref);
    if (kind === "prompt") { q += "&conversation_id=" + encodeURIComponent(conversationId); }
    var path = kind === "prompt" ? "/operations/outbox" : "/operations/creation";
    return get(path + q).then(function (res) {
      if (res.status === 404) { return { ok: true, data: { state: "unknown" } }; }
      return res;
    });
  }

  // يعرض حالة العملية جوه صندوق، ويستعلم بتراجع محدود (مفيش إعادة إرسال تلقائية).
  // `resend` دالة بتعيد إرسال نفس العملية بنفس المعرّف (idempotent) عند الطلب الصريح.
  function trackOperation(box, kind, ref, conversationId, onAccepted, resend, manager) {
    var status = el("div", "op-status");
    status.appendChild(el("span", "op-label", "حالة العملية: "));
    status.appendChild(opPill({ state: "pending" }));
    box.appendChild(status);
    var attempts = 0;
    var maxAttempts = 6;
    function poll() {
      queryOperation(kind, ref, conversationId).then(function (res) {
        if (!res.ok) { return; }
        var op = res.data || {};
        var state = op.state || "unknown";
        // نسجّل الحالة اللي رصدناها: نهائية ⇒ العملية خلصت، فإرسال جديد بنفس
        // المفتاح ياخد معرّف جديد. غامضة ⇒ تفضل نشطة (المعرّف يتحفظ).
        if (manager) { manager.resolve(ref, state); }
        status.innerHTML = "";
        status.appendChild(el("span", "op-label", "حالة العملية: "));
        status.appendChild(opPill(op));
        if (state === "accepted") {
          if (onAccepted) { onAccepted(op); }
          return;
        }
        attempts += 1;
        if (state !== "pending" || attempts >= maxAttempts) {
          // فشل/غامض/مش معروف — أو لسه pending بعد ما استنفدنا المحاولات: نعرض
          // إجراءات صريحة (استعلام + إعادة محاولة بنفس المعرّف). مفيش إعادة تلقائية.
          showOpActions(box, kind, ref, conversationId, state, onAccepted, resend, manager, op);
          return;
        }
        setTimeout(poll, 1500 + attempts * 500);
      }).catch(function () { /* نتجاهل أخطاء الاستعلام — نعرض آخر حالة معروفة */ });
    }
    setTimeout(poll, 800);
  }

  var OP_NOTE = {
    ambiguous: "النتيجة غامضة (ممكن يكون وصل). استعلم عن الحالة الأول قبل أي إعادة إرسال.",
    failed: "العملية فشلت بشكل مؤكد.",
    pending: "لسه قيد التنفيذ. استعلم تاني بعد شوية.",
    unknown: "حالة العملية مش معروفة. استعلم عنها."
  };

  // عند نتيجة غامضة/فاشلة/لسه معلّقة: نعرض إجراءات صريحة — استعلام (قراءة) وإعادة
  // محاولة بنفس معرّف العملية (idempotent، مفيش تكرار). مفيش أي إعادة تلقائية.
  function showOpActions(box, kind, ref, conversationId, state, onAccepted, resend, manager, op) {
    if (box.querySelector(".op-actions")) { return; }
    var note = el("p", "op-note", OP_NOTE[state] || OP_NOTE.unknown);
    var actions = el("div", "op-actions");
    var checkBtn = el("button", "btn ghost small", "استعلام عن الحالة");
    checkBtn.addEventListener("click", function () {
      checkBtn.disabled = true;
      queryOperation(kind, ref, conversationId).then(function (res) {
        checkBtn.disabled = false;
        var op2 = (res && res.data) || {};
        var s = op2.state || "unknown";
        if (manager) { manager.resolve(ref, s); }
        box.querySelectorAll(".op-status").forEach(function (n) { n.remove(); });
        var line = el("div", "op-status");
        line.appendChild(el("span", "op-label", "حالة العملية: "));
        line.appendChild(opPill(op2));
        box.appendChild(line);
        box.querySelectorAll(".op-actions, .op-note").forEach(function (n) { n.remove(); });
        if (s === "accepted") { if (onAccepted) { onAccepted(op2); } }
        else { showOpActions(box, kind, ref, conversationId, s, onAccepted, resend, manager, op2); }
      }).catch(function () { checkBtn.disabled = false; toast("مش قادر أوصل للسيرفر."); });
    });
    actions.appendChild(checkBtn);
    var retryBtn = el("button", "btn small", "إعادة المحاولة");
    retryBtn.addEventListener("click", function () {
      retryBtn.disabled = true;
      resend(ref).then(function (res) {
        retryBtn.disabled = false;
        if (res.ok) {
          box.querySelectorAll(".op-status, .op-actions, .op-note").forEach(function (n) { n.remove(); });
          trackOperation(box, kind, ref, conversationId, onAccepted, resend, manager);
          toast("اتعادت المحاولة بنفس العملية ✅");
        } else {
          toast(friendlyMessage(res.status, res.data));
        }
      }).catch(function () { retryBtn.disabled = false; toast("مش قادر أوصل للسيرفر."); });
    });
    actions.appendChild(retryBtn);

    // OHB2-09-05: تسوية يدوية للبرومتات المعلّقة (نفس أوامر البوت). بتظهر بس لما
    // يبقى عندنا id، وبتعمل تحديث للحالة بعد النجاح. 409 (حالة نهائية/غير مناسبة)
    // بيترجم لرسالة عربية من غير ما نغيّر حاجة محليًا.
    if (kind === "prompt" && op && op.id !== undefined && op.id !== null && state !== "accepted") {
      var markSent = el("button", "btn ghost small", "تأكيد الإرسال");
      markSent.addEventListener("click", function () {
        markSent.disabled = true;
        reconcileOperation(op.id, "mark_sent").then(function (res) {
          markSent.disabled = false;
          if (!res.ok) { toast(friendlyMessage(res.status, res.data)); return; }
          toast("اتعلّم كمُرسل ✅");
          if (manager && res.data) { manager.resolve(ref, res.data.state || "accepted"); }
          box.querySelectorAll(".op-status, .op-actions, .op-note").forEach(function (n) { n.remove(); });
          var line = el("div", "op-status");
          line.appendChild(el("span", "op-label", "حالة العملية: "));
          line.appendChild(opPill(res.data));
          box.appendChild(line);
        }).catch(function () { markSent.disabled = false; toast("مش قادر أوصل للسيرفر."); });
      });
      actions.appendChild(markSent);

      var discard = el("button", "btn ghost small", "شطب العملية");
      discard.addEventListener("click", function () {
        discard.disabled = true;
        reconcileOperation(op.id, "discard").then(function (res) {
          discard.disabled = false;
          if (!res.ok) { toast(friendlyMessage(res.status, res.data)); return; }
          toast("اتشالت العملية.");
          if (manager && res.data) { manager.resolve(ref, res.data.state || "failed"); }
          box.querySelectorAll(".op-status, .op-actions, .op-note").forEach(function (n) { n.remove(); });
          var line = el("div", "op-status");
          line.appendChild(el("span", "op-label", "حالة العملية: "));
          line.appendChild(opPill(res.data));
          box.appendChild(line);
        }).catch(function () { discard.disabled = false; toast("مش قادر أوصل للسيرفر."); });
      });
      actions.appendChild(discard);
    }

    box.appendChild(note);
    box.appendChild(actions);
  }

  // OHB2-09-05: تسوية عملية برومت معلّقة (discard/mark_sent) عبر مسار مصادَق (POST).
  function reconcileOperation(id, action) {
    return post("/operations/outbox/reconcile", { id: id, action: action });
  }

  // -------------------------------------------------------------- auth
  function authenticate() {
    var raw = (tg && tg.initData) ? tg.initData : "";
    if (!raw) {
      return Promise.resolve({ status: 401, ok: false, data: { message: "افتح التطبيق من جوه تيليجرام." } });
    }
    return post("/auth", { initData: raw });
  }

  function renderBootstrap(data) {
    var user = (data && data.user) || {};
    var nameEl = $("user-name");
    if (nameEl && user.display_name) {
      nameEl.textContent = user.display_name;
      nameEl.hidden = false;
    }
    var settings = (data && data.settings) || {};
    renderNotif(settings.notifications_enabled !== false);
    // القرار 4: نطابق إخفاء ميزات البوت (المتابعات) في الواجهة كمان.
    var feats = (data && data.features) || {};
    var watchesTab = document.querySelector('.tab[data-view="watches"]');
    if (watchesTab && feats.watches === false) { watchesTab.hidden = true; }
    // OHB2-08-05: شارة غير المقروء في تبويب الإشعارات.
    var inbox = (data && data.inbox) || {};
    renderInboxBadge(inbox.unread_count);
  }

  function renderNotif(enabled) {
    var btn = $("notif-toggle");
    if (!btn) { return; }
    btn.textContent = enabled ? "مفعّلة ✅" : "متوقفة ⛔";
    btn.setAttribute("data-enabled", enabled ? "1" : "0");
    btn.classList.toggle("on", enabled);
  }

  // --------------------------------------------------------------- inbox
  function renderInboxBadge(count) {
    var badge = $("inbox-badge");
    if (!badge) { return; }
    var text = INBOX.badgeText(count);
    if (text) {
      badge.textContent = text;
      badge.hidden = false;
    } else {
      badge.hidden = true;
    }
  }

  function kindLabel(kind) {
    return INBOX.kindLabel(kind);
  }

  // OHB2-08-07: `silent` للتحديثات الخلفية (الرجوع للصفحة / poll) عشان ما نعرضش صف
  // "بيتم التحميل…" وميضيء الشاشة من غير داعي. `page` بيتزامن مع اللي السيرفر رجّعه
  // (السيرفر بيرجع للأولى لو تجاوزنا الحد) — OHB2-08-08.
  function loadInbox(page, silent) {
    var list = $("inbox-list");
    if (!list) { return; }
    // OHB2-08-06: حارس الطلب الجاري — الضغط المتكرّر على "المزيد"/"تحديث" مايعملش
    // طلبات متداخلة (page=1 و page=2 في نفس اللحظة). الحارس أول حاجة عشان ما نلمسش
    // حالة التحميل الجاري. بيتصفّر في then/catch تحت.
    if (state.inboxLoading) { return; }
    state.inboxLoading = true;
    if (page === 0) { state.inboxIds = {}; if (!silent) { list.innerHTML = ""; list.appendChild(el("li", "loading-row", "بيتم التحميل…")); } }
    get("/notifications?page=" + (page || 0)).then(function (res) {
      state.inboxLoading = false;
      var data = res.data || {};
      if (!res.ok) {
        // فشل تحديث خلفي ⇒ نتجاهله ونحافظ على المعروض (مفيش وميض/مسح).
        if (silent) { return; }
        if (page === 0) { list.innerHTML = ""; }
        list.appendChild(el("li", "empty-row", friendlyMessage(res.status, res.data)));
        return;
      }
      // OHB2-08-08: نزامن رقم الصفحة مع رد السيرفر (لو رجع للأولى بسبب تجاوز الحد)
      // عشان "المزيد" يكمّل من المكان الصح بدل ما يطلب صفحة مش موجودة.
      // R5-01: `state.inboxPage` = آخر صفحة **نجحت**، وهو المصدر الوحيد للحقيقة
      // (بيتكتب هنا بس). كده فشل أي طلب (HTTP/شبكة) مايقدّمش الصفحة، و"المزيد" يعيد
      // نفس الصفحة الفاشلة بدل ما يتخطاها.
      if (typeof data.page === "number" && data.page >= 0) { state.inboxPage = data.page; }
      state.inboxHasMore = !!data.has_more;
      renderInboxBadge(data.unread_count);
      var items = data.items || [];
      if (page === 0) { list.innerHTML = ""; }
      if (page === 0 && !items.length) { list.appendChild(el("li", "empty-row", "مفيش إشعارات.")); }
      items.forEach(function (it) {
        // OHB2-08-06: منع تكرار نفس الإشعار — الترقيم بـ offset ممكن يتداخل لما
        // إشعارات جديدة تتصدّر القايمة، فنفس المعرّف يظهر في صفحتين.
        var idKey = String(it.id);
        if (state.inboxIds[idKey]) { return; }
        state.inboxIds[idKey] = true;
        var unread = INBOX.isUnread(it);
        var li = el("li", "row" + (unread ? " unread" : ""));
        var main = el("div", "row-main");
        main.appendChild(el("span", "row-title", it.title || it.conversation_id || ""));
        main.appendChild(el("span", "row-sub", kindLabel(it.kind)));
        li.appendChild(main);
        // OHB2-08-05 (Batch 3R): شارة حالة التسليم (مفيش شارة لو اتسلّم).
        var delivery = INBOX.deliveryLabel(it.delivery_status);
        if (delivery) { li.appendChild(el("span", "pill delivery", delivery)); }
        li.appendChild(el("span", "pill", unread ? "جديد" : "مقروء"));
        li.addEventListener("click", function () {
          if (unread) {
            post("/notifications/" + encodeURIComponent(it.id) + "/read", {}).then(function (r2) {
              if (r2.ok) { renderInboxBadge(r2.data && r2.data.unread_count); }
            }).catch(function () { /* نتجاهل: العرض لسه شغال */ });
          }
          if (it.conversation_id) { openDetail(it.conversation_id); }
        });
        list.appendChild(li);
      });
      var more = $("inbox-more");
      if (more) { more.hidden = !data.has_more; }
    }).catch(function () {
      state.inboxLoading = false;
      if (page === 0 && !silent) { list.innerHTML = ""; list.appendChild(el("li", "empty-row", "مش قادر أوصل للسيرفر.")); }
    });
  }

  // OHB2-08-07: تحديث صندوق الإشعارات لو الصفحة مرئية وتبويب الإشعارات مفتوح فعلاً،
  // مع تهدئة (ما نكرّرش التحديث في نفس اللحظة). بيتنادى من poll / رجوع الصفحة.
  function refreshInboxIfVisible() {
    if (!state.inboxVisible) { return; }
    var view = $("view-inbox");
    if (!view || view.hidden) { return; }
    if (INBOX.shouldThrottleRefresh(state.inboxLastRefreshAt, Date.now())) { return; }
    state.inboxLastRefreshAt = Date.now();
    loadInbox(state.inboxPage, true);
  }

  // OHB2-08-07: نبدأ/نوقف poll حسب رؤية الصفحة. مخفية ⇒ نوقف (مفيش طلبات خلفية).
  function setInboxPolling(visible) {
    if (inboxPollTimer) { clearInterval(inboxPollTimer); inboxPollTimer = null; }
    if (visible) {
      var ms = INBOX.refreshInterval(true);
      inboxPollTimer = setInterval(refreshInboxIfVisible, ms);
    }
  }

  // OHB2-08-07: لما الصفحة ترجع مرئية نحدّث فورًا (لو التبويب مفتوح) + نرجّع الـ poll.
  function onVisibilityChange() {
    var visible = !document.hidden;
    state.inboxVisible = visible;
    setInboxPolling(visible);
    if (visible) { refreshInboxIfVisible(); }
  }

  function markAllRead() {
    var btn = $("inbox-read-all");
    if (btn) { btn.disabled = true; }
    post("/notifications/read-all", {}).then(function (res) {
      if (btn) { btn.disabled = false; }
      if (res.ok) {
        renderInboxBadge(res.data && res.data.unread_count);
        // R5-01: نفس الثابت — خط الأساس بيتضبط من مسار النجاح بس (loadInbox(0)).
        loadInbox(0);
      } else {
        toast(friendlyMessage(res.status, res.data));
      }
    }).catch(function () { if (btn) { btn.disabled = false; } toast("مش قادر أوصل للسيرفر."); });
  }

  // -------------------------------------------------------------- chats
  function statusPill(item) {
    var pill = el("span", "pill", item.state_label || item.status || "");
    pill.setAttribute("data-status", item.status || "");
    return pill;
  }

  function loadChats(refresh) {
    var list = $("chats-list");
    list.innerHTML = "";
    list.appendChild(el("li", "loading-row", "بيتم التحميل…"));
    var q = "?page=" + state.chatsPage + (refresh ? "&refresh=1" : "");
    return get("/conversations" + q).then(function (res) {
      if (!res.ok) { list.innerHTML = ""; list.appendChild(el("li", "empty-row", friendlyMessage(res.status, res.data))); return; }
      var data = res.data || {};
      list.innerHTML = "";
      var items = data.items || [];
      if (!items.length) { list.appendChild(el("li", "empty-row", "مفيش شاتات.")); }
      items.forEach(function (item) {
        var li = el("li", "row");
        var main = el("div", "row-main");
        main.appendChild(el("span", "row-title", item.title || "بدون عنوان"));
        main.appendChild(el("span", "row-sub", item.repository || "بدون مستودع"));
        li.appendChild(main);
        li.appendChild(statusPill(item));
        li.addEventListener("click", function () { openDetail(item.id); });
        list.appendChild(li);
      });
      var more = $("chats-more");
      if (more) { more.hidden = !data.has_more; }
    });
  }

  function openDetail(id) {
    var box = $("view-detail");
    box.innerHTML = "";
    box.appendChild(el("div", "loading-row", "بيتم التحميل…"));
    showView("view-detail");
    state.currentChat = id;
    // OHB2-09-07 (B-07-07): حرس ضد الردود القديمة. لو المستخدم فتح شات تاني قبل ما
    // يرجع رد الأول، بنتجاهل الرد القديم عشان مايدهسش عرض الشات الأحدث (مفيش تسريب
    // حالة بين الشاتات). بنقارن الرقم التسلسلي قبل أي تحديث للـ DOM.
    var seq = ++state.detailSeq;
    function current() { return state.detailSeq === seq && state.currentChat === id; }
    get("/conversations/" + encodeURIComponent(id)).then(function (res) {
      if (!current()) { return; }
      if (!res.ok) { box.innerHTML = ""; box.appendChild(el("p", "empty-row", friendlyMessage(res.status, res.data))); return; }
      var d = res.data || {};
      box.innerHTML = "";
      var back = el("button", "btn ghost small", "→ رجوع");
      back.addEventListener("click", function () { showView("view-chats"); });
      box.appendChild(back);

      var card = el("div", "card");
      card.appendChild(el("p", "card-value", d.title || "بدون عنوان"));
      card.appendChild(el("p", "card-label", (d.repository || "بدون مستودع") + " · " + (d.state_label || d.status || "")));
      if (d.pr_url) {
        var a = el("a", "link", "افتح الـ PR");
        a.href = d.pr_url; a.target = "_blank"; a.rel = "noopener noreferrer";
        card.appendChild(a);
      }
      box.appendChild(card);

      if (d.last_prompt) {
        var pb = el("div", "bubble user");
        pb.appendChild(el("span", "bubble-label", "آخر برومت"));
        pb.appendChild(el("p", "bubble-text", d.last_prompt));
        box.appendChild(pb);
      }
      var rb = el("div", "bubble agent");
      rb.appendChild(el("span", "bubble-label", "آخر رد"));
      rb.appendChild(el("p", "bubble-text", d.last_reply || "لسه مفيش رد."));
      box.appendChild(rb);

      var prompt = el("textarea", "textarea");
      prompt.rows = 3;
      prompt.placeholder = "اكتب برومت للشات ده…";
      box.appendChild(prompt);
      var send = el("button", "btn", "إرسال البرومت");
      var opBox = el("div", "op-box");
      box.appendChild(send);
      box.appendChild(opBox);
      // مدير معرّف العملية: نفس المفتاح (نص البرومت) + عملية نشطة ⇒ نفس المعرّف
      // (إعادة محاولة/ضغط مزدوج مايكرّرش). عملية نهائية ⇒ معرّف جديد لنفس النص.
      var promptOps = OPS.createRefManager();
      function promptKey(text) { return opKey([id, text]); }
      function resend(ref) {
        return post(
          "/conversations/" + encodeURIComponent(id) + "/prompt",
          { text: promptOps.payload(), client_ref: ref }
        );
      }
      send.addEventListener("click", function () {
        var text = prompt.value.trim();
        if (!text) { toast("اكتب نص الأول."); return; }
        if (send.disabled) { return; }
        // عملية نشطة بنفس النص ⇒ نفس المعرّف؛ غير كده ⇒ معرّف جديد.
        var ref = promptOps.acquire(promptKey(text), text);
        send.disabled = true;
        opBox.innerHTML = "";
        resend(ref).then(function (res) {
          send.disabled = false;
          if (res.ok) {
            prompt.value = "";
            trackOperation(opBox, "prompt", ref, id, null, resend, promptOps);
          } else {
            // فشل مؤكّد (مثلاً 400) ⇒ العملية خلصت، فإعادة الإرسال بنفس النص
            // تعمل عملية جديدة بدل ما تتلغى.
            promptOps.resolve(ref, "failed");
            toast(friendlyMessage(res.status, res.data));
          }
        }).catch(function () {
          // انقطاع الشبكة: النتيجة غامضة. ما نعيدش الإرسال تلقائياً — نستعلم عن
          // الحالة بمعرّف العملية (نفس النص ما اتبعتش مرتين).
          send.disabled = false;
          trackOperation(opBox, "prompt", ref, id, null, resend, promptOps);
        });
      });

      var watchBtn = el("button", "btn ghost small", d.watched ? "إلغاء المتابعة" : "متابعة");
      watchBtn.addEventListener("click", function () {
        watchBtn.disabled = true;
        var req = d.watched
          ? del("/conversations/" + encodeURIComponent(id) + "/watch")
          : post("/conversations/" + encodeURIComponent(id) + "/watch", {});
        req.then(function (res) {
          watchBtn.disabled = false;
          if (res.ok) { d.watched = !d.watched; watchBtn.textContent = d.watched ? "إلغاء المتابعة" : "متابعة"; toast("تم ✅"); }
          else { toast(friendlyMessage(res.status, res.data)); }
        }).catch(function () { watchBtn.disabled = false; toast("مش قادر أوصل للسيرفر."); });
      });
      box.appendChild(watchBtn);

      // OHB2-09-02: قسم الملفات (قايمة + معاينة). كل حاجة عبر الـ Files API المصادَق،
      // والواجهة ما بتفترضش إن ملف قابل للقراءة لمجرد ظهوره في القايمة.
      box.appendChild(renderFilesSection(id));

      // OHB2-09-04: قسم التكلفة/الاستهلاك (نداء منفصل، ومابيفشّلش التفاصيل لو فشل).
      box.appendChild(renderCostSection(id));
    }).catch(function () {
      if (!current()) { return; }
      box.innerHTML = "";
      box.appendChild(el("p", "empty-row", "مش قادر أوصل للسيرفر."));
    });
  }

  // ------------------------------------------------------------ files (OHB2-09-02)
  function filesErrorText(res) {
    var data = (res && res.data) || {};
    return FILES.errorLabel(data.error, friendlyMessage(res && res.status, data));
  }

  function renderFilesSection(id) {
    var wrap = el("div", "files-section");
    var head = el("div", "toolbar");
    head.appendChild(el("span", "card-label", "ملفات الشات"));
    var refresh = el("button", "btn ghost small", "تحديث");
    head.appendChild(refresh);
    wrap.appendChild(head);

    var list = el("ul", "list");
    var previewBox = el("div", "file-preview");
    wrap.appendChild(list);
    wrap.appendChild(previewBox);

    function showLoading(container, text) {
      container.innerHTML = "";
      container.appendChild(el("li", "loading-row", text || "بيتم التحميل…"));
    }

    function loadPreview(path) {
      previewBox.innerHTML = "";
      previewBox.appendChild(el("p", "loading-row", "بيتم تحميل الملف…"));
      // نفس المفتاح (شات/مسار) أثناء التحميل ⇒ نفس الطلب (مفيش تكرار).
      filesDeduper.run("preview:" + id + ":" + path, function () {
        return get(
          "/conversations/" + encodeURIComponent(id) + "/file?path=" + encodeURIComponent(path)
        );
      }).then(function (res) {
        previewBox.innerHTML = "";
        if (!res.ok) { previewBox.appendChild(el("p", "empty-row", filesErrorText(res))); return; }
        var pre = el("pre", "file-text", FILES.previewText(res.data));
        previewBox.appendChild(pre);
        if (FILES.isTruncated(res.data)) {
          previewBox.appendChild(el("p", "hint", "المعاينة مقصوصة (الملف أكبر)."));
        }
      }).catch(function () {
        previewBox.innerHTML = "";
        previewBox.appendChild(el("p", "empty-row", "مش قادر أوصل للسيرفر."));
      });
    }

    function load() {
      showLoading(list);
      previewBox.innerHTML = "";
      filesDeduper.run("files:" + id, function () {
        return get("/conversations/" + encodeURIComponent(id) + "/files");
      }).then(function (res) {
        list.innerHTML = "";
        if (!res.ok) { list.appendChild(el("li", "empty-row", filesErrorText(res))); return; }
        var files = (res.data && res.data.files) || [];
        if (!files.length) { list.appendChild(el("li", "empty-row", "مفيش ملفات.")); return; }
        files.forEach(function (path) {
          var li = el("li", "row");
          li.appendChild(el("span", "row-title", path));
          li.addEventListener("click", function () { loadPreview(path); });
          list.appendChild(li);
        });
      }).catch(function () {
        list.innerHTML = "";
        list.appendChild(el("li", "empty-row", "مش قادر أوصل للسيرفر."));
      });
    }

    refresh.addEventListener("click", load);
    load();
    return wrap;
  }

  // ------------------------------------------------------------ cost (OHB2-09-04)
  function renderCostSection(id) {
    var wrap = el("div", "cost-section");
    wrap.appendChild(el("span", "card-label", "التكلفة والاستهلاك"));
    var body = el("div", "cost-body");
    body.appendChild(el("p", "loading-row", "بيتم التحميل…"));
    wrap.appendChild(body);
    get("/conversations/" + encodeURIComponent(id) + "/cost").then(function (res) {
      body.innerHTML = "";
      if (!res.ok) {
        body.appendChild(el("p", "empty-row", filesErrorText(res)));
        return;
      }
      body.appendChild(el("pre", "cost-text", COST.formatCost(res.data)));
    }).catch(function () {
      body.innerHTML = "";
      body.appendChild(el("p", "empty-row", "مش قادر أوصل للسيرفر."));
    });
    return wrap;
  }

  // ------------------------------------------------------------ watches
  function loadWatches() {
    var list = $("watches-list");
    list.innerHTML = "";
    list.appendChild(el("li", "loading-row", "بيتم التحميل…"));
    get("/watches").then(function (res) {
      list.innerHTML = "";
      if (!res.ok) { list.appendChild(el("li", "empty-row", friendlyMessage(res.status, res.data))); return; }
      var items = (res.data && res.data.items) || [];
      if (!items.length) { list.appendChild(el("li", "empty-row", "مفيش متابعات.")); }
      items.forEach(function (w) {
        var li = el("li", "row");
        var main = el("div", "row-main");
        main.appendChild(el("span", "row-title", w.title || w.id));
        main.appendChild(el("span", "row-sub", w.last_state || ""));
        li.appendChild(main);
        li.addEventListener("click", function () { openDetail(w.id); });
        list.appendChild(li);
      });
    }).catch(function () { list.innerHTML = ""; list.appendChild(el("li", "empty-row", "مش قادر أوصل للسيرفر.")); });
  }

  // ----------------------------------------------------------- new chat
  function loadRepos(query) {
    var list = $("repo-list");
    list.innerHTML = "";
    list.appendChild(el("li", "loading-row", "بيتم التحميل…"));
    get("/repositories?q=" + encodeURIComponent(query || "")).then(function (res) {
      list.innerHTML = "";
      if (!res.ok) { list.appendChild(el("li", "empty-row", friendlyMessage(res.status, res.data))); return; }
      var items = (res.data && res.data.items) || [];
      if (!items.length) { list.appendChild(el("li", "empty-row", "مفيش مستودعات.")); }
      items.forEach(function (r) {
        var li = el("li", "row");
        li.appendChild(el("span", "row-title", r.full_name + (r.private ? " 🔒" : "")));
        li.addEventListener("click", function () { pickRepo(r.full_name); });
        list.appendChild(li);
      });
    }).catch(function () { list.innerHTML = ""; list.appendChild(el("li", "empty-row", "مش قادر أوصل للسيرفر.")); });
  }

  function pickRepo(fullName) {
    state.selectedRepo = fullName;
    var label = $("newchat-repo");
    if (label) { label.textContent = "المستودع: " + fullName; }
    var form = $("newchat-form");
    if (form) { form.hidden = false; }
  }

  // إنشاء شات جديد: نسجّل في طابور الإنشاء المتين، وبعدها نتابع حالة العملية
  // (pending/accepted/failed/ambiguous). عند النجاح ننتقل لصفحة تفاصيل الشات.
  // المفتاح بيشمل المستودع + النص: نفس البرومت في مستودع مختلف = عملية جديدة.
  var createOps = OPS.createRefManager();
  function createKey(repo, text) { return opKey([repo, text]); }
  function resendCreate(ref) {
    return post("/chats", {
      repository: state.selectedRepo,
      text: createOps.payload(),
      client_ref: ref
    });
  }
  function createChat() {
    var text = ($("newchat-text").value || "").trim();
    if (!state.selectedRepo) { toast("اختار مستودع الأول."); return; }
    if (!text) { toast("اكتب البرومت الأول."); return; }
    var btn = $("newchat-send");
    if (btn.disabled) { return; }
    // عملية نشطة بنفس (مستودع + نص) ⇒ نفس المعرّف؛ غير كده ⇒ معرّف جديد.
    var ref = createOps.acquire(createKey(state.selectedRepo, text), text);
    var opBox = $("newchat-op");
    opBox.innerHTML = "";
    btn.disabled = true;
    function accepted(op) {
      if (op && op.conversation_id) {
        toast("اتبدأ الشات ✅");
        $("newchat-text").value = "";
        openDetail(op.conversation_id);
      } else {
        toast("اتبدأ الشات ✅ — حدّث القايمة.");
        showView("view-chats");
        loadChats(true);
      }
    }
    resendCreate(ref).then(function (res) {
      btn.disabled = false;
      if (res.ok) {
        trackOperation(opBox, "creation", ref, null, accepted, resendCreate, createOps);
      } else {
        createOps.resolve(ref, "failed");
        toast(friendlyMessage(res.status, res.data));
      }
    }).catch(function () {
      // انقطاع الشبكة: النتيجة غامضة ⇒ ما نعيدش الإنشاء تلقائياً، نتابع بالمعرّف.
      btn.disabled = false;
      trackOperation(opBox, "creation", ref, null, accepted, resendCreate, createOps);
    });
  }

  // ------------------------------------------------------------ settings
  function toggleNotif() {
    var btn = $("notif-toggle");
    var enabled = btn.getAttribute("data-enabled") === "1";
    btn.disabled = true;
    post("/app/notifications", { enabled: !enabled }).then(function (res) {
      btn.disabled = false;
      if (res.ok) { renderNotif(res.data.notifications_enabled); toast("تم التحديث ✅"); }
      else { toast(friendlyMessage(res.status, res.data)); }
    }).catch(function () { btn.disabled = false; toast("مش قادر أوصل للسيرفر."); });
  }

  // ---------------------------------------------------------------- boot
  function bind() {
    var tabs = document.querySelectorAll(".tab");
    for (var i = 0; i < tabs.length; i++) {
      (function (tab) {
        tab.addEventListener("click", function () {
          var view = tab.getAttribute("data-view");
          showView("view-" + view);
          if (view === "chats") { state.chatsPage = 0; loadChats(false); }
          if (view === "watches") { loadWatches(); }
          if (view === "inbox") { state.inboxLastRefreshAt = Date.now(); loadInbox(0); }
          if (view === "new") { loadRepos(""); }
        });
      })(tabs[i]);
    }
    $("chats-refresh").addEventListener("click", function () { state.chatsPage = 0; loadChats(true); });
    $("chats-next").addEventListener("click", function () { state.chatsPage += 1; loadChats(false); });
    $("watches-refresh").addEventListener("click", loadWatches);
    $("inbox-refresh").addEventListener("click", function () { state.inboxLastRefreshAt = Date.now(); loadInbox(0); });
    $("inbox-next").addEventListener("click", function () {
      if (state.inboxLoading) { return; }
      if (!state.inboxHasMore) { return; }  // OHB2-08-08: مفيش المزيد ⇒ ما نطلبش صفحة مش موجودة.
      // R5-01: نطلب الصفحة الجاية من غير ما نقدّم `state.inboxPage` — بيتقدّم بس لما
      // الطلب ينجح (في مسار النجاح جوه loadInbox). لو فشل، الضغط التاني يعيد نفس الصفحة.
      loadInbox(INBOX.nextPage(state.inboxPage, true));
    });
    $("inbox-read-all").addEventListener("click", markAllRead);
    $("repo-search-btn").addEventListener("click", function () { loadRepos($("repo-search").value); });
    $("repo-search").addEventListener("keydown", function (e) { if (e.key === "Enter") { loadRepos($("repo-search").value); } });
    $("newchat-send").addEventListener("click", createChat);
    $("notif-toggle").addEventListener("click", toggleNotif);
    $("retry-btn").addEventListener("click", start);
    // OHB2-08-07: نربط رؤية الصفحة (تبويب المتصفح/الخلفية) + نبدأ الحالة الابتدائية.
    document.addEventListener("visibilitychange", onVisibilityChange);
    state.inboxVisible = !document.hidden;
    setInboxPolling(state.inboxVisible);
  }

  function start() {
    show("state-loading");
    if (tg) { try { tg.ready(); tg.expand(); } catch (e) { /* تجاهل */ } }
    withRetry(authenticate).then(function (auth) {
      if (!auth.ok) { setError(friendlyMessage(auth.status, auth.data)); return null; }
      return withRetry(function () { return get("/app/bootstrap"); });
    }).then(function (boot) {
      if (!boot) { return; }
      if (!boot.ok) { setError(friendlyMessage(boot.status, boot.data)); return; }
      renderBootstrap(boot.data);
      show("state-ready");
      showView("view-chats");
      loadChats(false);
    }).catch(function () {
      setError("مش قادر أوصل للسيرفر. اتأكد من الاتصال وجرّب تاني.");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { bind(); start(); });
  } else {
    bind();
    start();
  }
})();
