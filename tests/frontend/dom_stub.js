/* OHB2-08-06 — بيئة DOM/شبكة مصغّرة (dependency-free) لاختبار app.js في Node.
 *
 * مفيش npm ولا مكتبات خارجية (CI بيشغّل `node --test tests/frontend/*.test.js` من غير
 * `npm install`). ده بديل بسيط كفاية لتشغيل app.js: عناصر، كلاسات، أحداث، وfetch مزيف.
 * الهدف اختبار **السلوك المُلاحَظ** (الـ DOM + طلبات الشبكة) مش تفاصيل المتصفح.
 */
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// ------------------------------------------------------------------ عناصر DOM
class ClassList {
  constructor(el) { this.el = el; this._set = new Set(); }
  add(...names) { names.forEach((n) => this._set.add(n)); this._sync(); }
  remove(...names) { names.forEach((n) => this._set.delete(n)); this._sync(); }
  contains(name) { return this._set.has(name); }
  toggle(name, force) {
    const want = force === undefined ? !this._set.has(name) : !!force;
    if (want) { this._set.add(name); } else { this._set.delete(name); }
    this._sync();
    return want;
  }
  _sync() { this.el._className = [...this._set].join(" "); }
}

class El {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this._className = "";
    this.classList = new ClassList(this);
    this._text = "";
    this.hidden = false;
    this._listeners = {};
    this.style = {};
    this.value = "";
    this.disabled = false;
    this.href = "";
    this.target = "";
    this.rel = "";
    this.rows = 0;
    this.placeholder = "";
    this._innerHTML = "";
  }
  get className() { return this._className; }
  set className(v) {
    this._className = v == null ? "" : String(v);
    this.classList._set = new Set(this._className.split(/\s+/).filter(Boolean));
  }
  get textContent() {
    if (this.children.length) { return this.children.map((c) => c.textContent).join(""); }
    return this._text;
  }
  set textContent(v) { this._text = v == null ? "" : String(v); this.children = []; }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(v) { this._innerHTML = v == null ? "" : String(v); this.children = []; }
  appendChild(child) {
    if (child.parentNode) { child.parentNode.removeChild(child); }
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  removeChild(child) {
    const i = this.children.indexOf(child);
    if (i !== -1) { this.children.splice(i, 1); child.parentNode = null; }
    return child;
  }
  remove() { if (this.parentNode) { this.parentNode.removeChild(this); } }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name)
      ? this.attributes[name] : null;
  }
  hasAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name); }
  addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); }
  removeEventListener(type, fn) {
    const arr = this._listeners[type] || [];
    const i = arr.indexOf(fn);
    if (i !== -1) { arr.splice(i, 1); }
  }
  dispatch(type, event) {
    (this._listeners[type] || []).slice().forEach((fn) => fn.call(this, event || {}));
  }
  // زرّ: click() بيطلق الحدث (والأزرار المعطّلة ما بتطلقهاش زي المتصفح).
  click() { if (this.disabled) { return undefined; } return this.dispatch("click", { type: "click" }); }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  // نستعمل textContent المباشر (مفيش عرض فعلي).
  get descendantText() { return this.textContent; }
}

function descendants(node, out = []) {
  node.children.forEach((c) => { out.push(c); descendants(c, out); });
  return out;
}

class Document {
  constructor() {
    this._ids = new Map();
    this._byClass = new Map();
    this.readyState = "complete";
    this._listeners = {};
    // OHB2-08-07: رؤية الصفحة (افتراضي: مرئية زي المتصفح في المقدمة).
    this.hidden = false;
    this.visibilityState = "visible";
  }
  createElement(tag) { return new El(tag); }
  getElementById(id) { return this._ids.get(id) || null; }
  register(el, id) {
    el.id = id;
    this._ids.set(id, el);
    return el;
  }
  addClass(el, cls) {
    (cls || "").split(/\s+/).filter(Boolean).forEach((c) => {
      if (!this._byClass.has(c)) { this._byClass.set(c, []); }
      this._byClass.get(c).push(el);
    });
    return el;
  }
  querySelector(sel) {
    const all = this.querySelectorAll(sel);
    return all.length ? all[0] : null;
  }
  querySelectorAll(sel) {
    if (sel.startsWith(".")) {
      return (this._byClass.get(sel.slice(1)) || []).slice();
    }
    return [];
  }
  addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); }
  removeEventListener(type, fn) {
    const arr = this._listeners[type] || [];
    const i = arr.indexOf(fn);
    if (i !== -1) { arr.splice(i, 1); }
  }
  dispatch(type, event) {
    (this._listeners[type] || []).slice().forEach((fn) => fn.call(this, event || {}));
  }
  // OHB2-08-07: محاكاة تغيير رؤية الصفحة. `hidden=true` يعني مخفية (زي document.hidden).
  setHidden(hidden) {
    this.hidden = !!hidden;
    this.visibilityState = hidden ? "hidden" : "visible";
    this.dispatch("visibilitychange", { type: "visibilitychange" });
  }
}

// ------------------------------------------------------------------ بناء الصفحة
// نفس معرّفات/كلاسات index.html المهمة لـ app.js (مش تحليل HTML كامل).
const IDS = [
  "app", "user-name",
  "state-loading", "state-error", "error-msg", "retry-btn", "state-ready",
  "view-chats", "view-detail", "view-watches", "view-inbox", "view-new", "view-settings",
  "chats-list", "chats-more", "chats-next", "chats-refresh",
  "watches-list", "watches-refresh",
  "inbox-list", "inbox-more", "inbox-next", "inbox-refresh", "inbox-read-all", "inbox-badge",
  "repo-search", "repo-search-btn", "repo-list",
  "newchat-form", "newchat-repo", "newchat-text", "newchat-send", "newchat-op", "newchat-norepo",
  "notif-toggle", "toast",
];
const TABS = [
  { view: "chats", label: "الشاتات" },
  { view: "watches", label: "المتابعات" },
  { view: "inbox", label: "الإشعارات" },
  { view: "new", label: "شات جديد" },
  { view: "settings", label: "الإعدادات" },
];

function buildDocument() {
  const doc = new Document();
  IDS.forEach((id) => doc.register(new El("div"), id));
  TABS.forEach((t) => {
    const b = new El("button");
    b.setAttribute("data-view", t.view);
    b.className = "tab";
    doc.addClass(b, "tab");
    doc.register(b, "tab-" + t.view);
  });
  // القيم الابتدائية زي index.html
  doc.getElementById("state-loading").hidden = false;
  doc.getElementById("state-error").hidden = true;
  doc.getElementById("state-ready").hidden = true;
  doc.getElementById("inbox-badge").hidden = true;
  doc.getElementById("toast").hidden = true;
  ["view-chats", "view-detail", "view-watches", "view-inbox", "view-new", "view-settings"]
    .forEach((id) => { doc.getElementById(id).hidden = true; });
  return doc;
}

// ------------------------------------------------------------------ fetch مزيّف
// نموذج مُوجَّه بالمسار: كل route له matcher (نص = تطابق تام، أو دالة(call)->bool)
// وresponder(call)->{status,data} . الأحدث أولوية (prepend)، فالتست يقدر يOverride.
class FakeFetch {
  constructor(opts) {
    opts = opts || {};
    this.calls = [];
    this.routes = [];
    this.deferred = !!opts.deferred;
  }
  route(matcher, responder) { this.routes.unshift({ matcher, responder }); return this; }
  install() { this._impl = makeFetchImpl(this); return this._impl; }
  last(pred) { return [...this.calls].reverse().find(pred) || null; }
  all(pred) { return this.calls.filter(pred); }
  pending() { return this.calls.filter((c) => !c.settled); }
}

function matchRoute(matcher, call) {
  if (typeof matcher === "function") { return !!matcher(call); }
  return call.path === matcher;
}

function makeFetchImpl(fake) {
  return function fetch(url, init) {
    const call = {
      url,
      path: url.replace(/^\/api\/v1/, ""),
      method: (init && init.method) || "GET",
      body: init && init.body,
      options: init,
      settled: false,
    };
    fake.calls.push(call);
    // رد مؤجّل: الاختبار بيستنّى call.resolve(...) عشان يتحكّم في التوقيت (الطلبات الجارية).
    if (fake.deferred) {
      return new Promise((resolve, reject) => {
        call.resolve = (result) => { call.settled = true; resolve(toResponse(result)); };
        call.reject = (err) => { call.settled = true; reject(err); };
      });
    }
    const route = fake.routes.find((r) => matchRoute(r.matcher, call));
    let result;
    try {
      result = route ? route.responder(call) : { status: 200, data: {} };
    } catch (err) {
      call.settled = true;
      return Promise.reject(err);
    }
    if (result && typeof result.then === "function") { return result; }
    call.settled = true;
    return Promise.resolve(toResponse(result));
  };
}

function toResponse(result) {
  return {
    status: result.status === undefined ? 200 : result.status,
    ok: result.ok !== undefined ? result.ok : (result.status === undefined || result.status < 400),
    json: () => Promise.resolve(result.data === undefined ? {} : result.data),
  };
}

// ------------------------------------------------------------------ تحميل app.js
function loadApp(opts) {
  opts = opts || {};
  const doc = opts.document || buildDocument();
  const fake = opts.fetch || new FakeFetch();
  const fetchImpl = opts.fetchImpl || fake.install();
  const timers = [];
  const intervals = new Map();   // OHB2-08-07: معرّف حقيقي للمؤقّتات الدورية
  let nextIntervalId = 1;
  const sandbox = {
    console,
    document: doc,
    fetch: fetchImpl,
    AbortController: class { constructor() { this.signal = {}; } abort() {} },
    setTimeout: (fn, ms) => { timers.push({ fn, ms: ms || 0 }); return timers.length; },
    clearTimeout: () => {},
    setInterval: (fn, ms) => { const id = nextIntervalId++; intervals.set(id, { fn, ms: ms || 0 }); return id; },
    clearInterval: (id) => { intervals.delete(id); },
    Promise,
    JSON,
    Math,
    Date,
    Number,
    String,
    Object,
    Array,
    isFinite,
    encodeURIComponent,
  };
  sandbox.window = sandbox;
  sandbox.self = sandbox;
  sandbox.globalThis = sandbox;
  const tg = opts.telegram || { initData: "init", ready() {}, expand() {} };
  sandbox.Telegram = { WebApp: tg };

  const root = path.resolve(__dirname, "../../bot/web/static");
  const ctx = vm.createContext(sandbox);
  for (const file of ["ops.js", "inbox.js", "files.js", "cost.js", "app.js"]) {
    const code = fs.readFileSync(path.join(root, file), "utf8");
    vm.runInContext(code, ctx, { filename: file });
  }
  // تشغيل المؤقّتات المخزّنة (اختبار auto-hide للتوست مثلاً).
  function runTimers() {
    const pending = timers.splice(0, timers.length);
    pending.forEach((t) => t.fn());
  }
  // OHB2-08-07: تشغيل كل المؤقّتات الدورية المسجّلة (poll الإشعارات).
  function runIntervals() {
    [...intervals.values()].forEach((iv) => iv.fn());
  }
  function intervalCount() { return intervals.size; }
  return { sandbox, doc, fetch: fake, timers, telegram: tg, runTimers, runIntervals, intervalCount };
}

module.exports = { El, Document, buildDocument, FakeFetch, loadApp, descendants, IDS };
