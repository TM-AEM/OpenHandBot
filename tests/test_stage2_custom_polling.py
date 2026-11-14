"""OHB2-STAGE2 — اختبارات انحدار لحلقة الاستطلاع المخصّصة وحدّ الإقرار الدائم.

بتغطّي قرارات Stage 2 (D0/D1/D2/D4/D5) وقائمة المتطلبات §5 في المهمة:
- بناء التطبيق بـ `updater(None)` (مفيش Updater ⇒ مفيش poller تاني).
- `deleteWebhook(drop_pending_updates=False)` + سياسة `allowed_updates`.
- offset من الحدّ (`B+1`) أو `None` (حفظ المعلّق).
- fallback للتحديثات غير المطابقة (بدون الكتابة فوق نتيجة محفوظة).
- الفشل مايتحوّلش لتجاهل/نجاح.
- مونوتونية الحدّ وذرّية تثبيت النتائج + الحدّ.
- سلوك crash/restart/idempotency/شبكة/قاعدة.

مفيش شبكة: `Bot.get_updates`/`delete_webhook`/الإرسال بتُعترض، وقاعدة معزولة في `tmp_path`.
"""
from __future__ import annotations

import asyncio
import sqlite3

import pytest
from telegram import CallbackQuery, Chat, Document, Location, Message, Update, User
from telegram.error import TimedOut
from telegram.ext import TypeHandler

import bot.app as app_mod
import bot.handlers as h
import bot.polling as polling
from bot import outbox
from bot import update_outcomes as uo
from bot.polling import TelegramPoller
from tests.test_duplicate_update_dispatch import (
    CHAT_ID,
    OWNER_ID,
    FakeOpenHands,
    _conv,
    make_config,
)
from tests.test_one_shot_awaiting_atomicity import (
    CID_A,
    _harness,
    _patch_telegram,
)


# ============================================================================
# أدوات مساعدة
# ============================================================================
def _patch_bot_init(monkeypatch):
    """يخلي `Bot.initialize()`/`shutdown()` تشتغل بدون شبكة (بدون `get_me` حقيقي)."""

    async def _get_me(self, *a, **k):
        user = User(id=1, first_name="bot", is_bot=True)
        self._bot_user = user  # زي `Bot.get_me` الحقيقي (بيخزّن المستخدم)
        return user

    async def _noop(self, *a, **k):
        return None

    monkeypatch.setattr("telegram.Bot.get_me", _get_me)
    monkeypatch.setattr("telegram.request.BaseRequest.initialize", _noop)
    monkeypatch.setattr("telegram.request.BaseRequest.shutdown", _noop)


def _app(tmp_path, monkeypatch):
    _patch_telegram(monkeypatch)
    return app_mod.build_application(make_config(tmp_path))


def _user() -> User:
    return User(id=OWNER_ID, first_name="o", is_bot=False)


def _bind(update: Update, app) -> Update:
    """يربط الـ update/الرسالة بالبوت (زي ما PTB بيعمل عند الـ deserialization)."""
    update.set_bot(app.bot)
    if update.message is not None:
        update.message.set_bot(app.bot)
    if update.callback_query is not None:
        update.callback_query.set_bot(app.bot)
        if update.callback_query.message is not None:
            update.callback_query.message.set_bot(app.bot)
    return update


def _text(app, update_id: int, text: str = "نص حر") -> Update:
    chat = Chat(id=CHAT_ID, type="private")
    msg = Message(message_id=5, date=None, chat=chat, from_user=_user(), text=text)
    return _bind(Update(update_id=update_id, message=msg), app)


def _location(app, update_id: int) -> Update:
    chat = Chat(id=CHAT_ID, type="private")
    msg = Message(
        message_id=5, date=None, chat=chat, from_user=_user(),
        location=Location(longitude=1.0, latitude=2.0),
    )
    return _bind(Update(update_id=update_id, message=msg), app)


def _document(app, update_id: int) -> Update:
    chat = Chat(id=CHAT_ID, type="private")
    msg = Message(
        message_id=5, date=None, chat=chat, from_user=_user(),
        document=Document(file_id="f", file_unique_id="u"),
    )
    return _bind(Update(update_id=update_id, message=msg), app)


def _callback(app, update_id: int, data: str) -> Update:
    chat = Chat(id=CHAT_ID, type="private")
    msg = Message(message_id=5, date=None, chat=chat, from_user=_user(), text=None)
    cq = CallbackQuery(id="cq", from_user=_user(), chat_instance="ci", data=data, message=msg)
    return _bind(Update(update_id=update_id, callback_query=cq), app)


def _text_stub(update_id: int) -> Update:
    chat = Chat(id=CHAT_ID, type="private")
    msg = Message(message_id=5, date=None, chat=chat, from_user=_user(), text="x")
    return Update(update_id=update_id, message=msg)


class FakeBot:
    """وكيل رقيق فوق البوت الحقيقي: بيعترض السحب/الحذف فقط وبيفوّض الباقي.

    مهم: PTB بيستخدم `application.bot.id` (وكمان `bot.shutdown/initialize`) جوه مسار
    المعالجة، فلازم الوكيل يرجّعهم من البوت الحقيقي (`__getattr__`) عشان مفيش `task_done`
    ناقص (لو `id` مش موجود، `create_task` بيرمي قبل التنفيذ ⇒ الطابور مايتفرّغش).
    """

    def __init__(self, real, batches=None, *, delete_error=None, get_error_once=None):
        self._real = real
        self.batches = list(batches or [])
        self.deleted: list[bool] = []
        self.get_calls: list[dict] = []
        self._delete_error = delete_error
        self._get_error_once = get_error_once

    def __getattr__(self, name):
        return getattr(self._real, name)

    async def delete_webhook(self, **kwargs):
        self.deleted.append(kwargs.get("drop_pending_updates"))
        if self._delete_error is not None:
            err, self._delete_error = self._delete_error, None
            raise err

    async def get_updates(self, **kwargs):
        self.get_calls.append(kwargs)
        if self._get_error_once is not None:
            err, self._get_error_once = self._get_error_once, None
            raise err
        return self.batches.pop(0) if self.batches else []


async def _with_started_app(tmp_path, monkeypatch, coro_factory):
    """يشغّل التطبيق الحقيقي (handlers + db) ثم ينفّذ coro_factory(app, install_bot).

    `install_bot(**kw)` بتركّب وكيل بوت فوق البوت الحقيقي وترجّعه (للاختبارات اللي محتاجة
    تتحكّم في السحب/الحذف)، وبعدين app.bot بيرجع للبوت الحقيقي عند الإغلاق.
    """
    _patch_bot_init(monkeypatch)
    app = _app(tmp_path, monkeypatch)
    await app.initialize()
    await app.start()
    real_bot = app.bot

    def install_bot(**kw):
        proxy = FakeBot(real_bot, **kw)
        app.bot = proxy
        return proxy

    try:
        return await coro_factory(app, install_bot)
    finally:
        app.bot = real_bot
        await app.stop()
        await app.shutdown()


# ============================================================================
# 1) بناء التطبيق + عدم وجود poller مزدوج
# ============================================================================
def test_application_built_without_updater(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    assert app.updater is None
    assert app.update_queue is not None


def test_no_run_polling_available_without_updater(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError):
        app.run_polling()  # مفيش Updater ⇒ ممنوع مسار الاستطلاع القديم


def test_fallback_handler_registered_last_in_group_zero(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    group0 = app.handlers[0]
    assert group0[-1].callback is h.handle_unmatched_update
    assert isinstance(group0[-1], TypeHandler)
    assert -1 in app.handlers  # الحاجز في group=-1 زي ما هو


# ============================================================================
# 2) الإقلاع: deleteWebhook(False) + allowed_updates + offset البداية
# ============================================================================
def test_bootstrap_deletes_webhook_without_dropping_and_no_boundary_starts_none(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    bot = FakeBot(app.bot)
    app.bot = bot  # type: ignore[assignment]
    poller = TelegramPoller(app, app.bot_data["db"])
    asyncio.run(poller.bootstrap())
    assert bot.deleted == [False]  # ممنوع drop_pending_updates=True
    assert poller._next_offset is None


def test_bootstrap_resumes_from_boundary_plus_one(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    app.bot_data["db"].commit_batch_outcomes([(10, uo.DURABLE_COMPLETED)], outbox.now_iso())
    bot = FakeBot(app.bot)
    app.bot = bot  # type: ignore[assignment]
    poller = TelegramPoller(app, app.bot_data["db"])
    asyncio.run(poller.bootstrap())
    assert poller._next_offset == 11  # B+1


def test_allowed_updates_policy_is_message_and_callback():
    assert polling.ALLOWED_UPDATES == ("message", "callback_query")


def test_fetch_passes_allowed_updates_and_offset(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    bot = FakeBot(app.bot)
    app.bot = bot  # type: ignore[assignment]
    poller = TelegramPoller(app, app.bot_data["db"])
    poller._next_offset = 42
    asyncio.run(poller.fetch())
    assert bot.get_calls[-1]["allowed_updates"] == ("message", "callback_query")
    assert bot.get_calls[-1]["offset"] == 42


# ============================================================================
# 3) التوزيع + النتائج + الـ fallback
# ============================================================================
def test_text_without_route_is_ignored_and_advances_boundary(tmp_path, monkeypatch):
    async def run(app, install_bot):
        poller = TelegramPoller(app, app.bot_data["db"])
        boundary = await poller.process_updates([_text(app, 101)])
        assert boundary == 101
        assert app.bot_data["db"].update_outcome(101) == uo.EXPLICITLY_IGNORED
        assert poller._next_offset == 102

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_unmatched_message_location_recorded_by_fallback(tmp_path, monkeypatch):
    async def run(app, install_bot):
        poller = TelegramPoller(app, app.bot_data["db"])
        boundary = await poller.process_updates([_location(app, 202)])
        assert app.bot_data["db"].update_outcome(202) == uo.EXPLICITLY_IGNORED
        assert boundary == 202

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_unmatched_callback_recorded_by_fallback(tmp_path, monkeypatch):
    async def run(app, install_bot):
        poller = TelegramPoller(app, app.bot_data["db"])
        boundary = await poller.process_updates([_callback(app, 203, "unknown:pattern")])
        assert app.bot_data["db"].update_outcome(203) == uo.EXPLICITLY_IGNORED
        assert boundary == 203

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_matched_callback_uses_handler_outcome_not_fallback(tmp_path, monkeypatch):
    async def run(app, install_bot):
        poller = TelegramPoller(app, app.bot_data["db"])
        boundary = await poller.process_updates([_callback(app, 204, "menu")])
        assert app.bot_data["db"].update_outcome(204) == uo.EXPLICITLY_IGNORED
        assert boundary == 204

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_fallback_does_not_overwrite_successful_outcome(tmp_path, monkeypatch):
    from bot.db import Database

    db = Database(str(tmp_path / "x.sqlite3"))
    db.mark_update_outcome(300, outbox.now_iso(), uo.DURABLE_COMPLETED)
    ctx = type("C", (), {"bot_data": {"db": db}})()
    asyncio.run(h.handle_unmatched_update(_text_stub(300), ctx))
    assert db.update_outcome(300) == uo.DURABLE_COMPLETED  # مااتكتبش فوقها
    db.close()


def test_fallback_does_not_overwrite_failed_outcome(tmp_path, monkeypatch):
    from bot.db import Database

    db = Database(str(tmp_path / "x.sqlite3"))
    db.mark_update_outcome(301, outbox.now_iso(), uo.FAILED_PERMANENT, reason="x")
    ctx = type("C", (), {"bot_data": {"db": db}})()
    asyncio.run(h.handle_unmatched_update(_text_stub(301), ctx))
    assert db.update_outcome(301) == uo.FAILED_PERMANENT  # الفشل محفوظ (مش تجاهل)
    db.close()


def test_handler_exception_stays_failure_not_ignored(tmp_path, monkeypatch):
    """استثناء handler ⇒ معالج الأخطاء يسجّل فشل ⇒ **مش** تجاهل، والحدّ مايتقدّمش."""
    async def run(app, install_bot):
        async def boom(update, context):
            raise RuntimeError("boom")

        # نستبدل handler النص (في مكانه) بواحد بيرمي ⇒ PTB بيروح لمعالج الأخطاء.
        group0 = app.handlers[0]
        idx = next(i for i, hh in enumerate(group0) if getattr(hh, "callback", None) is h.handle_text)
        group0[idx] = TypeHandler(Update, boom, strict=False)
        poller = TelegramPoller(app, app.bot_data["db"])
        boundary = await poller.process_updates([_text(app, 302)])
        assert app.bot_data["db"].update_failure(302) == uo.FAILED_PERMANENT
        assert boundary is None
        assert poller._next_offset is None

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_unsupported_attachment_still_rejected(tmp_path, monkeypatch):
    async def run(app, install_bot):
        poller = TelegramPoller(app, app.bot_data["db"])
        boundary = await poller.process_updates([_document(app, 303)])
        assert app.bot_data["db"].update_outcome(303) == uo.EXPLICITLY_IGNORED
        assert boundary == 303

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_collect_outcomes_defaults_missing_to_unknown(tmp_path, monkeypatch):
    """مفيش نتيجة مُسجَّلة (كتابة فشلت) ⇒ PARTIAL_OR_UNKNOWN (غير مؤهّل، مش تجاهل كاذب)."""
    app = _app(tmp_path, monkeypatch)
    poller = TelegramPoller(app, app.bot_data["db"])
    assert poller.collect_outcomes([_text_stub(404)]) == [(404, uo.PARTIAL_OR_UNKNOWN)]


# ============================================================================
# 4) مونوتونية الحدّ + الذرّية
# ============================================================================
def test_boundary_never_moves_backwards(tmp_path, monkeypatch):
    from bot.db import Database

    db = Database(str(tmp_path / "b.sqlite3"))
    assert db.commit_batch_outcomes([(50, uo.DURABLE_COMPLETED)], outbox.now_iso()) == 50
    db.commit_batch_outcomes([(30, uo.DURABLE_COMPLETED)], outbox.now_iso())
    assert db.get_acknowledgment_boundary() == 50
    db.close()


def test_missing_boundary_does_not_erase_existing(tmp_path, monkeypatch):
    from bot.db import Database

    db = Database(str(tmp_path / "b.sqlite3"))
    db.commit_batch_outcomes([(60, uo.DURABLE_COMPLETED)], outbox.now_iso())
    assert db.commit_batch_outcomes([(70, uo.FAILED_PERMANENT)], outbox.now_iso()) is None
    assert db.get_acknowledgment_boundary() == 60
    db.close()


def test_equal_boundary_is_safe(tmp_path, monkeypatch):
    from bot.db import Database

    db = Database(str(tmp_path / "b.sqlite3"))
    db.commit_batch_outcomes([(80, uo.DURABLE_COMPLETED)], outbox.now_iso())
    assert db.commit_batch_outcomes([(80, uo.DURABLE_COMPLETED)], outbox.now_iso()) == 80
    assert db.get_acknowledgment_boundary() == 80
    db.close()


def test_outcomes_and_boundary_are_atomic(tmp_path, monkeypatch):
    from bot.db import Database

    db = Database(str(tmp_path / "b.sqlite3"))

    def boom(_uid):
        raise sqlite3.OperationalError("crash")

    monkeypatch.setattr(db, "_outcome_in_txn", boom)
    with pytest.raises(sqlite3.OperationalError):
        db.commit_batch_outcomes([(90, uo.DURABLE_COMPLETED)], outbox.now_iso())
    monkeypatch.undo()
    assert db.update_outcome(90) is None
    assert db.get_acknowledgment_boundary() is None
    db.close()


def test_longest_contiguous_prefix_under_out_of_order(tmp_path, monkeypatch):
    from bot.db import Database

    db = Database(str(tmp_path / "b.sqlite3"))
    boundary = db.commit_batch_outcomes(
        [(5, uo.DURABLE_COMPLETED), (7, uo.FAILED_PERMANENT), (9, uo.DURABLE_COMPLETED)],
        outbox.now_iso(),
    )
    assert boundary == 5
    assert db.get_acknowledgment_boundary() == 5
    db.close()


# ============================================================================
# 5) الاسترجاع/التكرار/الشبكة/القاعدة/إعادة التشغيل/الترقية
# ============================================================================
def test_crash_before_outcome_recording_redelivery_reprocesses(tmp_path, monkeypatch):
    hh = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    hh.db.set_awaiting(OWNER_ID, CID_A, "reply")
    update = hh.text_update(500, "برومت مايضيعش")
    calls = {"n": 0}
    original = hh.db.add_or_group_outbox

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.OperationalError("crash before commit")
        return original(*a, **k)

    monkeypatch.setattr(hh.db, "add_or_group_outbox", flaky)
    hh.process(update)
    assert hh.db.update_outcome(500) != uo.DURABLE_INTENT_RECORDED
    hh.process(update)
    assert hh.db.update_outcome(500) == uo.DURABLE_INTENT_RECORDED


def test_crash_after_outcome_before_boundary_redelivery_is_duplicate(tmp_path, monkeypatch):
    hh = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    hh.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    update = hh.text_update(600, "برومت")
    hh.process(update)
    assert hh.db.count_outbox() == 1
    assert hh.db.update_outcome(600) == uo.DURABLE_INTENT_RECORDED
    hh.process(update)
    assert hh.db.count_outbox() == 1


def test_duplicate_update_not_dispatched_twice(tmp_path, monkeypatch):
    async def run(app, install_bot):
        poller = TelegramPoller(app, app.bot_data["db"])
        await poller.process_updates([_text(app, 700)])
        first = app.bot_data["db"].update_outcome(700)
        await poller.process_updates([_text(app, 700)])
        assert app.bot_data["db"].update_outcome(700) == first

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_network_error_then_recovery(tmp_path, monkeypatch):
    async def run(app, install_bot):
        bot = install_bot(batches=[[_text(app, 800)]], get_error_once=TimedOut("x"))
        poller = TelegramPoller(app, app.bot_data["db"])
        poller.poll_timeout = 0
        original_process = poller.process_updates

        async def stop_after(updates):
            result = await original_process(updates)
            poller.stop()
            return result

        poller.process_updates = stop_after  # type: ignore[assignment]
        await poller.run()
        assert app.bot_data["db"].update_outcome(800) == uo.EXPLICITLY_IGNORED
        assert len(bot.get_calls) == 2

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_transient_db_error_leaves_boundary_and_offset(tmp_path, monkeypatch):
    async def run(app, install_bot):
        poller = TelegramPoller(app, app.bot_data["db"])

        def boom(*a, **k):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(app.bot_data["db"], "commit_batch_outcomes", boom)
        with pytest.raises(sqlite3.OperationalError):
            await poller.process_updates([_text(app, 900)])
        assert poller._next_offset is None
        assert app.bot_data["db"].get_acknowledgment_boundary() is None

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_restart_with_boundary_resumes(tmp_path, monkeypatch):
    from bot.db import Database

    p = str(tmp_path / "r.sqlite3")
    db = Database(p)
    db.commit_batch_outcomes([(1000, uo.DURABLE_COMPLETED)], outbox.now_iso())
    db.close()
    reopened = Database(p)
    assert reopened.get_acknowledgment_boundary() == 1000
    reopened.close()


def test_restart_without_boundary_starts_from_none(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    bot = FakeBot(app.bot)
    app.bot = bot  # type: ignore[assignment]
    poller = TelegramPoller(app, app.bot_data["db"])
    asyncio.run(poller.bootstrap())
    assert poller._next_offset is None


# ============================================================================
# 6) الإيقاف/الإلغاء
# ============================================================================
def test_stop_prevents_further_fetching(tmp_path, monkeypatch):
    async def run(app, install_bot):
        bot = install_bot(batches=[[_text(app, 1100)], [_text(app, 1101)]])
        poller = TelegramPoller(app, app.bot_data["db"])
        poller.poll_timeout = 0
        original_process = poller.process_updates

        async def stop_after(updates):
            result = await original_process(updates)
            poller.stop()
            return result

        poller.process_updates = stop_after  # type: ignore[assignment]
        await poller.run()
        assert len(bot.get_calls) == 1
        assert app.bot_data["db"].update_outcome(1101) is None

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


# ============================================================================
# 7) تنظيم دورة الحياة (`run_bot`)
# ============================================================================
def _fake_lifecycle_app(events, *, fail_post_init=False, startup_failed=False):
    class FakeApp:
        def __init__(self):
            self.bot_data = {"db": object()}
            if startup_failed:
                self.bot_data["startup_failed"] = "database_integrity"
            self.post_init = self._post_init
            self.post_stop = self._post_stop
            self.post_shutdown = self._post_shutdown

        async def initialize(self):
            events.append("initialize")

        async def _post_init(self, app):
            events.append("post_init")
            if fail_post_init:
                raise RuntimeError("post_init boom")

        async def start(self):
            events.append("start")

        async def stop(self):
            events.append("stop")

        async def _post_stop(self, app):
            events.append("post_stop")

        async def shutdown(self):
            events.append("shutdown")

        async def _post_shutdown(self, app):
            events.append("post_shutdown")

    return FakeApp()


def test_run_bot_orchestrates_lifecycle(monkeypatch):
    events: list[str] = []

    async def fake_run(self):
        events.append("poller.run")

    monkeypatch.setattr(polling.TelegramPoller, "run", fake_run)
    asyncio.run(polling.run_bot(_fake_lifecycle_app(events)))
    assert events == [
        "initialize", "post_init", "start", "poller.run",
        "stop", "post_stop", "shutdown", "post_shutdown",
    ]


def test_run_bot_shuts_down_when_post_init_fails(monkeypatch):
    events: list[str] = []

    async def fake_run(self):  # pragma: no cover — المفروض مايُتناداش
        events.append("poller.run")

    monkeypatch.setattr(polling.TelegramPoller, "run", fake_run)
    with pytest.raises(RuntimeError):
        asyncio.run(polling.run_bot(_fake_lifecycle_app(events, fail_post_init=True)))
    assert "start" not in events
    assert "poller.run" not in events
    assert events[-2:] == ["shutdown", "post_shutdown"]  # مفيش تسريب موارد


def test_run_bot_skips_polling_when_startup_failed(monkeypatch):
    events: list[str] = []

    async def fake_run(self):  # pragma: no cover — المفروض مايُتناداش
        events.append("poller.run")

    monkeypatch.setattr(polling.TelegramPoller, "run", fake_run)
    asyncio.run(polling.run_bot(_fake_lifecycle_app(events, startup_failed=True)))
    assert "start" not in events
    assert "poller.run" not in events
    assert events[-2:] == ["shutdown", "post_shutdown"]

