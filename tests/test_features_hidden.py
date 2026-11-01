"""TASK 04B-06: القرار 4 — الميزات المؤجّلة مخفية عن المستخدم، والبيانات الأساسية لسه موجودة.

بنثبت إن:
- الأزرار/القوايم مش بتعرض الملفات/التصدير/التكلفة/إدارة المتابعات.
- تسجيل الـ handlers بيرجّع نقاط الدخول دي بعيد (مفيش pattern مستني).
- العمليات الأساسية (شاتاتي/شات جديد/رد/تحديث/حالة/إلغاء التوجيه) لسه متاحة.
- الكود والجداول مش متحذفين (الدوال والجداول لسه موجودين) — يعني إخفاء مش حذف.
"""
import inspect

from bot import features
from bot import handlers as h
from bot import keyboards as kb
from bot.app import build_application
from bot.config import Config


def _callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def _patterns(app):
    out = []
    for group in app.handlers.values():
        for handler in group:
            pat = getattr(handler, "pattern", None)
            if pat is None:
                continue
            out.append(getattr(pat, "pattern", pat))
    return out


def _make_config(tmp_path):
    return Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "t.sqlite3"),
    )


def test_deferred_features_are_restored_by_default():
    """OHB2-09-06/07: الميزات الأربع اتسترجعت (مفعّلة افتراضيًا)."""
    assert not features.is_hidden("files")
    assert not features.is_hidden("export")
    assert not features.is_hidden("cost")
    assert not features.is_hidden("followups")


def test_core_actions_remain_available_in_menu_and_conversation():
    menu = _callbacks(kb.main_menu())
    assert "list:0" in menu and "newchat" in menu  # العمليات الأساسية ظاهرة
    convo = _callbacks(kb.conversation_actions("c1"))
    for cb in ("reply:c1", "open:c1", "status:c1", "list:0", "cancelroute"):
        assert cb in convo


def test_deferred_callbacks_are_restored_in_user_facing_menus():
    """OHB2-09-06: الأزرار المسترجَعة بقت ظاهرة في القوايم."""
    menu = _callbacks(kb.main_menu())
    unwatched = _callbacks(kb.conversation_actions("c1", watched=False))
    watched = _callbacks(kb.conversation_actions("c1", watched=True))
    for cb in ("watched:0", "files:c1:0", "cost:c1", "export:c1"):
        assert cb in (menu + unwatched), cb
    assert "watch:c1" in unwatched
    assert "unwatch:c1" in watched


def test_app_registers_deferred_handlers_when_restored(tmp_path):
    """OHB2-09-06: تسجيل الـ handlers المسترجَعة بيفرّج نقاط الدخول دي."""
    app = build_application(_make_config(tmp_path))
    pats = _patterns(app)
    for prefix in (r"^files:", r"^file:", r"^cost:", r"^export:", r"^watch:", r"^unwatch:", r"^watched:"):
        assert prefix in pats, prefix
    # الأساسيات لسه متسجّلة.
    for prefix in (r"^list:", r"^open:", r"^reply:", r"^status:", r"^newchat$"):
        assert prefix in pats, prefix


def test_hide_switch_still_hides_when_enabled(monkeypatch, tmp_path):
    """آلية الإخفاء لسه شغّالة: لو المفتاح اتشغّل، نقاط الدخول تختفي تاني (بدون حذف)."""
    monkeypatch.setattr(features, "DEFERRED_FEATURES_HIDDEN", True)
    menu = _callbacks(kb.main_menu())
    convo = _callbacks(kb.conversation_actions("c1", watched=True))
    for prefix in ("files:", "file:", "cost:", "export:", "watch:", "unwatch:", "watched:"):
        assert not any(cb.startswith(prefix) for cb in (menu + convo)), prefix
    app = build_application(_make_config(tmp_path))
    pats = _patterns(app)
    for prefix in (r"^files:", r"^file:", r"^cost:", r"^export:", r"^watch:", r"^unwatch:", r"^watched:"):
        assert prefix not in pats, prefix


def test_hiding_does_not_delete_implementations_or_schema():
    # الدوال لسه موجودة (إخفاء مش حذف).
    for fn in ("show_cost", "export_conversation", "list_files", "show_file",
               "list_watches", "watch_conversation", "unwatch_conversation"):
        assert callable(getattr(h, fn))
    # جداول قاعدة البيانات لسه موجودة زي ما هي (نفس الـ schema).
    import bot.db as db
    src = inspect.getsource(db.Database._init_schema)
    assert "CREATE TABLE IF NOT EXISTS watched" in src
    assert "CREATE TABLE IF NOT EXISTS outbox" in src
    assert "CREATE TABLE IF NOT EXISTS creation_jobs" in src
