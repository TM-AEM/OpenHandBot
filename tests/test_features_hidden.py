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


def test_deferred_features_are_hidden_by_default():
    assert features.is_hidden("files")
    assert features.is_hidden("export")
    assert features.is_hidden("cost")
    assert features.is_hidden("followups")


def test_core_actions_remain_available_in_menu_and_conversation():
    menu = _callbacks(kb.main_menu())
    assert "list:0" in menu and "newchat" in menu  # العمليات الأساسية ظاهرة
    convo = _callbacks(kb.conversation_actions("c1"))
    for cb in ("reply:c1", "open:c1", "status:c1", "list:0", "cancelroute"):
        assert cb in convo


def test_no_deferred_callbacks_in_any_user_facing_menu():
    menu = _callbacks(kb.main_menu())
    convo = _callbacks(kb.conversation_actions("c1", watched=True))
    all_cbs = menu + convo
    for prefix in ("files:", "file:", "cost:", "export:", "watch:", "unwatch:", "watched:"):
        assert not any(cb.startswith(prefix) for cb in all_cbs), prefix


def test_app_does_not_register_deferred_handlers(tmp_path):
    app = build_application(_make_config(tmp_path))
    pats = _patterns(app)
    for prefix in (r"^files:", r"^file:", r"^cost:", r"^export:", r"^watch:", r"^unwatch:", r"^watched:"):
        assert prefix not in pats, prefix
    # الأساسيات متسجّلة فعلاً.
    for prefix in (r"^list:", r"^open:", r"^reply:", r"^status:", r"^newchat$"):
        assert prefix in pats, prefix


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
