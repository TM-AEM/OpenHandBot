"""NTF-04/05: أزرار وأوامر الإشعارات — العرض، التبديل، الصلاحيات، ودورة الحياة."""
import asyncio
import logging
import re
import sqlite3
from types import SimpleNamespace

import pytest

from telegram.error import BadRequest, TimedOut

from bot import handlers as h
from bot import keyboards as kb
from bot.app import build_application
from bot.config import Config

from tests.test_handlers import make_context, make_update
from tests.test_notifier import make_notifier


class Q:
    def __init__(self, data):
        self.data = data
        self.edits = []
        self.markups = []
        self.answers = []
        self.message = SimpleNamespace(chat_id=99)

    async def answer(self, *args, **kw):
        self.answers.append(args)

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)
        self.markups.append(kw.get("reply_markup"))


def cb_update(q, user_id=1, chat_type="private"):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type=chat_type),
        callback_query=q,
        message=None,
    )


def callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]


def make_config(tmp_path):
    return Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "t.sqlite3"),
    )


# ------------------------------------------------------------------- keyboard
def test_main_menu_has_notifications_entry():
    assert kb.NOTIF_MENU in callbacks(kb.main_menu())


def test_callback_data_within_telegram_limit():
    for cb in (kb.NOTIF_MENU, kb.NOTIF_TOGGLE):
        assert len(cb.encode("utf-8")) <= kb.CALLBACK_DATA_LIMIT


def test_notifications_menu_reflects_state():
    off = callbacks(kb.notifications_menu(True))
    on = callbacks(kb.notifications_menu(False))
    assert kb.NOTIF_TOGGLE in off and kb.NOTIF_TOGGLE in on
    # النص بيعكس الحالة: مفعّل ⇒ زر إيقاف، معطّل ⇒ زر تفعيل.
    texts_off = [b.text for row in kb.notifications_menu(True).inline_keyboard for b in row]
    texts_on = [b.text for row in kb.notifications_menu(False).inline_keyboard for b in row]
    assert kb.NOTIF_TURN_OFF in texts_off and kb.NOTIF_TURN_ON in texts_on


# --------------------------------------------------------------------- command
def test_notifications_command_shows_state(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(1)
    asyncio.run(h.notifications_command(update, ctx))
    assert len(update.message.replies) == 1
    assert "مفعّلة" in update.message.replies[0]


def test_notifications_command_ignores_non_owner(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(999)
    asyncio.run(h.notifications_command(update, ctx))
    assert update.message.replies == []


def test_notifications_command_ignores_group(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(1)
    update.effective_chat.type = "group"
    asyncio.run(h.notifications_command(update, ctx))
    assert update.message.replies == []


# -------------------------------------------------------------------- callbacks
def test_menu_callback_shows_current_state(tmp_path):
    ctx = make_context(1, tmp_path)
    q = Q(kb.NOTIF_MENU)
    asyncio.run(h.notifications_menu(cb_update(q), ctx))
    assert len(q.edits) == 1
    assert "مفعّلة" in q.edits[0]


def test_toggle_disables_then_enables_and_persists(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]

    q = Q(kb.NOTIF_TOGGLE)
    asyncio.run(h.notifications_toggle(cb_update(q), ctx))
    assert db.get_notifications_enabled() is False
    assert "متوقفة" in q.edits[0]
    assert q.answers  # تأكيد فوري

    q2 = Q(kb.NOTIF_TOGGLE)
    asyncio.run(h.notifications_toggle(cb_update(q2), ctx))
    assert db.get_notifications_enabled() is True
    assert "مفعّلة" in q2.edits[0]


def test_toggle_ignored_for_non_owner(tmp_path):
    ctx = make_context(1, tmp_path)
    q = Q(kb.NOTIF_TOGGLE)
    asyncio.run(h.notifications_toggle(cb_update(q, user_id=999), ctx))
    assert q.edits == []
    assert ctx.bot_data["db"].get_notifications_enabled() is True  # مااتغيّرش


def test_toggle_ignored_in_group(tmp_path):
    ctx = make_context(1, tmp_path)
    q = Q(kb.NOTIF_TOGGLE)
    asyncio.run(h.notifications_toggle(cb_update(q, chat_type="group"), ctx))
    assert q.edits == []
    assert ctx.bot_data["db"].get_notifications_enabled() is True


# ------------------------------------------- OHB2-SW09: فشل تأكيد الكولباك بعد الـ commit
class _AnswerRaisesQ(Q):
    """Q تأكيده (بعد الـ commit) يرمي استثناء، ويسجّل عدد المحاولات."""

    def __init__(self, data, exc):
        super().__init__(data)
        self.exc = exc
        self.answer_attempts = 0

    async def answer(self, *args, **kw):
        self.answer_attempts += 1
        raise self.exc


def _counting_toggle(monkeypatch, db):
    """يلفّ `toggle_notifications_once` بعدّاد للتحقق من «مرة واحدة بالظبط»."""
    calls = {"n": 0}
    real = db.toggle_notifications_once

    def counting(update_id, now):
        calls["n"] += 1
        return real(update_id, now)

    monkeypatch.setattr(db, "toggle_notifications_once", counting)
    return calls


def test_sw09_post_commit_answer_failure_still_edits(tmp_path, monkeypatch, caplog):
    """A: فشل تأكيد الكولباك بعد الـ commit مايوقفش تعديل الواجهة، والتبديل مرة واحدة."""
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    calls = _counting_toggle(monkeypatch, db)
    q = _AnswerRaisesQ(kb.NOTIF_TOGGLE, TimedOut("timed out"))
    with caplog.at_level(logging.WARNING, logger="bot.handlers"):
        asyncio.run(h.notifications_toggle(cb_update(q), ctx))  # مايرميش (الفشل مُحتوى)
    # المعالج كمّل وعدّل الرسالة بالحالة **المعمّلة** (كانت مفعّلة ⇒ بقت متوقفة).
    assert len(q.edits) == 1
    assert "متوقفة" in q.edits[0]
    assert kb.NOTIF_TURN_ON in [
        b.text for row in q.markups[0].inline_keyboard for b in row
    ]
    # التبديل حصل **مرة واحدة بالظبط** (مفيش ازدواج بسبب فشل الكولباك).
    assert calls["n"] == 1
    assert db.get_notifications_enabled() is False
    # تأكيد واحد اتحاول، مفيش إعادة محاولة.
    assert q.answer_attempts == 1
    # سجل: نوع الخطأ فقط، بدون نص الاستثناء (ممكن يحتوي أسرار).
    assert "تعذّر الرد على الكولباك" in caplog.text
    assert "TimedOut" in caplog.text
    assert "timed out" not in caplog.text


def test_sw09_bad_request_failure_still_edits(tmp_path, monkeypatch, caplog):
    """A (نوع استثناء آخر): رفض تيليجرام (كولباك منتهي) كذلك مايوقفش تعديل الواجهة."""
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    calls = _counting_toggle(monkeypatch, db)
    q = _AnswerRaisesQ(kb.NOTIF_TOGGLE, BadRequest("Query is too old and response timeout expired"))
    with caplog.at_level(logging.WARNING, logger="bot.handlers"):
        asyncio.run(h.notifications_toggle(cb_update(q), ctx))
    assert len(q.edits) == 1 and "متوقفة" in q.edits[0]
    assert calls["n"] == 1
    assert db.get_notifications_enabled() is False
    assert "BadRequest" in caplog.text


def test_sw09_db_failure_no_success_ack(tmp_path, monkeypatch):
    """B: فشل القاعدة قبل التأكيد ⇒ مفيش تأكيد نجاح، مفيش عرض «اتحدّثت»، الحالة مااتغيّرتش."""
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]

    def boom(update_id, now):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(db, "toggle_notifications_once", boom)
    q = Q(kb.NOTIF_TOGGLE)
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(h.notifications_toggle(cb_update(q), ctx))
    assert q.answers == []  # مفيش تأكيد نجاح
    assert q.edits == []  # مفيش عرض نجاح
    assert db.get_notifications_enabled() is True  # مااتغيّرش


def test_sw09_normal_success_unchanged(tmp_path, monkeypatch):
    """C: المسار العادي — التبديل مرة واحدة، تأكيد النجاح، والتعديل المتوقّع."""
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    calls = _counting_toggle(monkeypatch, db)
    q = Q(kb.NOTIF_TOGGLE)
    asyncio.run(h.notifications_toggle(cb_update(q), ctx))
    assert calls["n"] == 1
    assert q.answers == [("تم التحديث ✅",)]  # تأكيد النجاح زي ما هو
    assert len(q.edits) == 1 and "متوقفة" in q.edits[0]
    assert db.get_notifications_enabled() is False


def test_sw09_failed_answer_no_duplicate_toggle(tmp_path, monkeypatch):
    """D: فشل الكولباك مايعملش تبديل تاني ولا يعيد محاولة القاعدة."""
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    calls = _counting_toggle(monkeypatch, db)
    q = _AnswerRaisesQ(kb.NOTIF_TOGGLE, TimedOut("timed out"))
    asyncio.run(h.notifications_toggle(cb_update(q), ctx))
    assert calls["n"] == 1  # مفيش إعادة محاولة للقاعدة بسبب فشل الكولباك
    assert q.answer_attempts == 1  # مفيش إعادة محاولة للكولباك كذلك


def test_sw09_cancellation_not_swallowed(tmp_path):
    """E: `CancelledError` ينتشر (مفيش ابتلاع بـ `except Exception`)."""
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    q = _AnswerRaisesQ(kb.NOTIF_TOGGLE, asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(h.notifications_toggle(cb_update(q), ctx))
    # الـ commit حصل قبل الـ answer (تصميم)، لكن الإلغاء مااتبلعش.
    assert db.get_notifications_enabled() is False
    assert q.edits == []  # ماوصلش للتعديل (الإلغاء قطع التنفيذ)


@pytest.mark.parametrize("data", ["notif:toggle", "notif:", "notif", "menu", "", "list:0", "notif:menuX"])
def test_menu_callback_rejects_non_menu_data(tmp_path, data):
    """بيانات قديمة/غريبة مش بتطابق نمط `^notif:menu$` فماينفعش تصل للمعالج."""
    assert not re.fullmatch("^notif:menu$", data)


def test_menu_callback_with_missing_user_is_ignored(tmp_path):
    ctx = make_context(1, tmp_path)
    q = Q(kb.NOTIF_MENU)
    update = cb_update(q)
    update.effective_user = None  # تحديث قديم/ناقص
    asyncio.run(h.notifications_menu(update, ctx))
    assert q.edits == []


# --------------------------------------------- interactive use while disabled
def test_interactive_commands_work_while_notifications_disabled(tmp_path):
    """تعطيل الإشعارات الاستباقية ما يأثّرش على الأوامر/الأزرار التفاعلية."""
    ctx = make_context(1, tmp_path)
    ctx.bot_data["db"].set_notifications_enabled(False)

    # /start لسه بيرد بالمينيو
    update = make_update(1)
    asyncio.run(h.start(update, ctx))
    assert len(update.message.replies) == 1

    # show_menu لسه بيعدّل الرسالة
    q = Q("menu")
    asyncio.run(h.show_menu(cb_update(q), ctx))
    assert q.edits

    # /notifications لسه شغّال وبيسجّل الحالة المعطّلة
    update2 = make_update(1)
    asyncio.run(h.notifications_command(update2, ctx))
    assert "متوقفة" in update2.message.replies[0]


# --------------------------------------------------------------- no conflicts
def test_app_registers_notification_handlers_with_intended_routing(tmp_path):
    app = build_application(make_config(tmp_path))
    handlers = [h_ for group in app.handlers.values() for h_ in group]

    # الأمر /notifications متسجّل بمعالج notifications_command.
    commands = {}
    for h_ in handlers:
        for cmd in (getattr(h_, "commands", None) or set()):
            commands[cmd] = getattr(h_, "callback", None)
    assert commands.get("notifications") is h.notifications_command

    # أنماط الأزرار متسجّلة بالمعالجات الصح، والنمط الكامل `^...$` مايطابقش الأزرار التانية.
    patterns = {}
    for h_ in handlers:
        pat = getattr(h_, "pattern", None)
        if pat is not None:
            patterns[pat.pattern] = getattr(h_, "callback", None)
    assert patterns.get("^notif:menu$") is h.notifications_menu
    assert patterns.get("^notif:toggle$") is h.notifications_toggle
    # التوجيه الفعلي: النمط الكامل مايطابقش غير الزر بتاعه.
    assert re.fullmatch("^notif:menu$", "notif:menu")
    assert not re.fullmatch("^notif:menu$", "notif:toggle")
    assert not re.fullmatch("^notif:toggle$", "notif:menu")
    assert not re.fullmatch("^menu$", "notif:menu")


# ------------------------------------------------------------------- lifecycle
def test_start_stop_creates_and_cancels_the_task(tmp_path):
    n, db, bot = make_notifier(tmp_path, {None: {"items": [], "next_page_id": None}})

    async def run():
        n.start()
        task = n._task
        assert task is not None
        # بنسيب الحلقة تدّي الـ task فرصة يبدأ فعلًا.
        await asyncio.sleep(0)
        assert not task.done()
        await n.stop()
        assert task.cancelled()  # اتلغى فعلًا (مش بس العدّاد اتزوّد)
        # إعادة التشغيل بعد الإيقاف بتعمل task جديد.
        n.start()
        assert n._task is not task and not n._task.done()
        await n.stop()

    asyncio.run(run())


def test_repeated_post_init_starts_single_watcher_and_notifier(tmp_path, monkeypatch):
    """إعادة تهيئة مكرّرة ما تعملش task مراقب/مُبلّغ تاني (NTF-07.4)."""
    starts = {"watcher": 0, "notifier": 0}

    def w_start(self):
        starts["watcher"] += 1

    def n_start(self):
        starts["notifier"] += 1

    async def noop_stop(self):
        pass

    monkeypatch.setattr("bot.watcher.Watcher.start", w_start)
    monkeypatch.setattr("bot.watcher.Watcher.stop", noop_stop)
    monkeypatch.setattr("bot.notifier.Notifier.start", n_start)
    monkeypatch.setattr("bot.notifier.Notifier.stop", noop_stop)
    monkeypatch.setattr("bot.outbox.OutboxWorker.start", lambda self: None)
    monkeypatch.setattr("bot.outbox.CreationWorker.start", lambda self: None)
    monkeypatch.setattr("bot.outbox.OutboxWorker.stop", noop_stop)
    monkeypatch.setattr("bot.outbox.CreationWorker.stop", noop_stop)

    app = build_application(make_config(tmp_path))

    async def lifecycle():
        await app.post_init(app)
        await app.post_init(app)
        await app.post_shutdown(app)

    asyncio.run(lifecycle())
    assert starts["watcher"] == 1
    assert starts["notifier"] == 1
