/* Mini App (OHB2-06) — JS عادي بحجم صغير، مفيش إطار عمل. */
(function () {
  "use strict";

  var API = "/api/v1";
  var tg = (window.Telegram && window.Telegram.WebApp) || null;
  var REQUEST_TIMEOUT = 12000;
  var state = { chatsPage: 0, currentChat: null, selectedRepo: null };

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
    ["view-chats", "view-detail", "view-watches", "view-new", "view-settings"].forEach(function (id) {
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
  }

  function renderNotif(enabled) {
    var btn = $("notif-toggle");
    if (!btn) { return; }
    btn.textContent = enabled ? "مفعّلة ✅" : "متوقفة ⛔";
    btn.setAttribute("data-enabled", enabled ? "1" : "0");
    btn.classList.toggle("on", enabled);
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
    get("/conversations/" + encodeURIComponent(id)).then(function (res) {
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
      send.addEventListener("click", function () {
        var text = prompt.value.trim();
        if (!text) { toast("اكتب نص الأول."); return; }
        send.disabled = true;
        post("/conversations/" + encodeURIComponent(id) + "/prompt", { text: text }).then(function (res) {
          send.disabled = false;
          if (res.ok) { prompt.value = ""; toast("وصل ✅"); }
          else { toast(friendlyMessage(res.status, res.data)); }
        }).catch(function () { send.disabled = false; toast("مش قادر أوصل للسيرفر."); });
      });
      box.appendChild(send);

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
    }).catch(function () {
      box.innerHTML = "";
      box.appendChild(el("p", "empty-row", "مش قادر أوصل للسيرفر."));
    });
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

  function createChat() {
    var text = ($("newchat-text").value || "").trim();
    if (!state.selectedRepo) { toast("اختار مستودع الأول."); return; }
    if (!text) { toast("اكتب البرومت الأول."); return; }
    var btn = $("newchat-send");
    btn.disabled = true;
    post("/chats", { repository: state.selectedRepo, text: text }).then(function (res) {
      btn.disabled = false;
      if (res.ok) { $("newchat-text").value = ""; toast("وصل ✅ جاري بدء الشات."); showView("view-chats"); loadChats(true); }
      else { toast(friendlyMessage(res.status, res.data)); }
    }).catch(function () { btn.disabled = false; toast("مش قادر أوصل للسيرفر."); });
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
          if (view === "new") { loadRepos(""); }
        });
      })(tabs[i]);
    }
    $("chats-refresh").addEventListener("click", function () { state.chatsPage = 0; loadChats(true); });
    $("chats-next").addEventListener("click", function () { state.chatsPage += 1; loadChats(false); });
    $("watches-refresh").addEventListener("click", loadWatches);
    $("repo-search-btn").addEventListener("click", function () { loadRepos($("repo-search").value); });
    $("repo-search").addEventListener("keydown", function (e) { if (e.key === "Enter") { loadRepos($("repo-search").value); } });
    $("newchat-send").addEventListener("click", createChat);
    $("notif-toggle").addEventListener("click", toggleNotif);
    $("retry-btn").addEventListener("click", start);
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
