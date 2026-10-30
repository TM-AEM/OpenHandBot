/* Mini App shell (OHB2-05). مفيش أي إطار عمل — JS عادي بحجم صغير. */
(function () {
  "use strict";

  var API = "/api/v1";
  var tg = (window.Telegram && window.Telegram.WebApp) || null;
  var REQUEST_TIMEOUT = 12000;

  function $(id) { return document.getElementById(id); }

  function show(name) {
    ["state-loading", "state-error", "state-empty", "state-ready"].forEach(function (id) {
      var el = $(id);
      if (el) { el.hidden = (id !== name); }
    });
    var app = $("app");
    if (app) { app.setAttribute("aria-busy", name === "state-loading" ? "true" : "false"); }
  }

  function setError(message) {
    var el = $("error-msg");
    if (el) { el.textContent = message || "حصل خطأ غير متوقع."; }
    show("state-error");
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

  function friendlyMessage(status, data) {
    if (data && data.message) { return data.message; }
    if (status === 401) { return "محتاج تسجيل دخول."; }
    if (status === 403) { return "الحساب ده مش مسموح له."; }
    if (status >= 500) { return "الخدمة مش متاحة دلوقتي، جرّب تاني."; }
    return "حصل خطأ غير متوقع، جرّب تاني.";
  }

  function withRetry(fn, attempts) {
    var left = attempts || 2;
    return fn().catch(function (err) {
      if (left <= 0) { throw err; }
      return new Promise(function (resolve) { setTimeout(resolve, 800); })
        .then(function () { return withRetry(fn, left - 1); });
    });
  }

  function authenticate() {
    var raw = (tg && tg.initData) ? tg.initData : "";
    if (!raw) {
      // مفيش بيانات تهيئة (فتح مباشر من المتصفح، مش من تيليجرام).
      return Promise.resolve({ status: 401, ok: false, data: { message: "افتح التطبيق من جوه تيليجرام." } });
    }
    return fetchJson(API + "/auth", { method: "POST", body: { initData: raw } });
  }

  function loadBootstrap() {
    return fetchJson(API + "/app/bootstrap", { method: "GET" });
  }

  function renderBootstrap(data) {
    var user = (data && data.user) || {};
    var settings = (data && data.settings) || {};
    var nameEl = $("user-name");
    if (nameEl) { nameEl.textContent = user.display_name || "—"; }

    var notif = $("notif-state");
    if (notif) {
      var on = settings.notifications_enabled !== false;
      notif.textContent = on ? "مفعّلة" : "متوقفة";
      notif.className = "pill " + (on ? "on" : "off");
    }
    show("state-ready");
  }

  function start() {
    show("state-loading");
    if (tg) {
      try { tg.ready(); tg.expand(); } catch (e) { /* تجاهل */ }
    }

    withRetry(authenticate)
      .then(function (auth) {
        if (!auth.ok) {
          setError(friendlyMessage(auth.status, auth.data));
          return null;
        }
        return withRetry(loadBootstrap);
      })
      .then(function (boot) {
        if (!boot) { return; }
        if (!boot.ok) {
          setError(friendlyMessage(boot.status, boot.data));
          return;
        }
        renderBootstrap(boot.data);
      })
      .catch(function () {
        setError("مش قادر أوصل للسيرفر. اتأكد من الاتصال وجرّب تاني.");
      });
  }

  function bindRetry() {
    var btn = $("retry-btn");
    if (btn) {
      btn.addEventListener("click", function () {
        btn.disabled = true;
        start();
        setTimeout(function () { btn.disabled = false; }, 1500);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { bindRetry(); start(); });
  } else {
    bindRetry();
    start();
  }
})();
