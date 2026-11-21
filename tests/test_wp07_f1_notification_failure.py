"""OHB2-WP07-F1 — اختبارات انحدار على **فشل إشعار تيليجرام بعد الالتزام المحلي**.

السياق (F-1، قرار المالك: الخيار C): المسارات الستة
(`cancel_route`، `cancel_route_button`، `reply_prompt`، `repo_search_prompt`، `pick_repo`،
`new_chat_no_repo`) بتلتزم بحالة SQLite المحلية **مع** نتيجة `durable_completed` في معاملة
واحدة (WP-07)، **وبعدين** تبعت رسالة/تعدّل رسالة تيليجرام. لو الإرسال فشل، الالتزام المحلي
والنتيجة **يفضلوا كما هما** (مفيش تراجع/تخفيض/حذف)، والتحديث يفضل **مؤهّلًا للإقرار**
(الديدَب في `processed_updates`)، **و** يتحفظ دليل فشل منفصل في `update_failures` عبر مسار
معالج أخطاء PTB الموجود (`handle_processing_error` ⇒ `record_update_failure`).

الخيار C **ما بيعملش**:
- إعادة تشغيل الـ handler المحلي بسبب فشل الإشعار؛
- إعادة إرسال تلقائية أو أي worker/طابور/جدول جديد؛
- ادّعاء exactly-once أو ذرّية SQLite+تيليجرام.

هذه الاختبارات **سلوكية** (بتقود `Application.process_update` الحقيقي بالمعالجات الحقيقية)
و**مميِّزة**: لو غيّرنا السلوك ليُسقط النتيجة المحلية أو يُعيد تشغيل الـ handler أو يحجب
الإقرار، بتفشل.

ملاحظة نطاق: مفيش شبكة؛ `Bot.send_message`/`Message.edit_text`/`answer_callback_query`
بتُعترض، وقاعدة SQLite معزولة في `tmp_path`.
"""
from __future__ import annotations

import asyncio
import sqlite3

import pytest
from telegram import CallbackQuery, Chat, Message, MessageEntity, Update, User
from telegram.error import BadRequest, TimedOut

import bot.app as app_mod
import bot.handlers as h
from bot import outbox
from bot import update_outcomes as uo
from bot.db import Database
from tests.test_duplicate_update_dispatch import (
    CHAT_ID,
    CID_A,
    OWNER_ID,
    FakeOpenHands,
    _conv,
    make_config,
)

USER = User(id=OWNER_ID, first_name="o", is_bot=False)


# ============================================================================
# أدوات مساعدة
# ============================================================================
async def _anoop(*_a, **_k):
    return True


def _patch_telegram(monkeypatch, *, send_exc=None, edit_exc=None):
    """يعترض نداءات تيليجرام؛ عند تمرير استثناء يرفعه من الإرسال/التعديل (فشل إشعار)."""

    async def _send_message(self, chat_id=None, text=None, **kw):
        if send_exc is not None:
            raise send_exc
        m = Message(message_id=1, date=None, chat=Chat(id=chat_id or CHAT_ID, type="private"))
        m.set_bot(self)
        return m

    async def _edit_message_text(self, *a, **kw):
        if edit_exc is not None:
            raise edit_exc
        m = Message(message_id=1, date=None, chat=Chat(id=CHAT_ID, type="private"))
        m.set_bot(self)
        return m

    monkeypatch.setattr("telegram.Bot.send_message", _send_message)
    monkeypatch.setattr("telegram.Message.edit_text", _edit_message_text)
    monkeypatch.setattr("telegram.Bot.answer_callback_query", _anoop)
    monkeypatch.setattr("telegram.Bot.set_my_commands", _anoop)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _anoop)


def _build_app(tmp_path, monkeypatch, *, client=None, send_exc=None, edit_exc=None):
    app = app_mod.build_application(make_config(tmp_path))
    app._initialized = True  # نتخطّى initialize() (شبكة حقيقية)
    # `CommandHandler.check_update` بيقرا `bot.username` ⇒ لازم مستخدم بوت باسم مضبوط بلا شبكة.
    app.bot._bot_user = User(id=1, first_name="bot", is_bot=True, username="ohb_test_bot")
    if client is not None:
        app.bot_data["client"] = client
    _patch_telegram(monkeypatch, send_exc=send_exc, edit_exc=edit_exc)
    return app


def _command_update(app, update_id: int, text: str) -> Update:
    """تحديث أمر حقيقي (`/cancel`): لازم `bot_command` entity عشان `CommandHandler` يطابقه."""
    chat = Chat(id=CHAT_ID, type="private")
    msg = Message(
        message_id=5, date=None, chat=chat, from_user=USER, text=text,
        entities=[MessageEntity(type=MessageEntity.BOT_COMMAND, offset=0, length=len(text))],
    )
    msg.set_bot(app.bot)
    up = Update(update_id=update_id, message=msg)
    up.set_bot(app.bot)
    return up


def _cb_update(app, update_id: int, data: str) -> Update:
    chat = Chat(id=CHAT_ID, type="private")
    msg = Message(message_id=5, date=None, chat=chat, from_user=USER, text=None)
    msg.set_bot(app.bot)
    cq = CallbackQuery(id="cq", from_user=USER, chat_instance="ci", data=data, message=msg)
    cq.set_bot(app.bot)
    up = Update(update_id=update_id, callback_query=cq)
    up.set_bot(app.bot)
    return up


def _drive(app, update: Update) -> None:
    """يوجّه تحديثًا حقيقيًّا عبر PTB (نفس مسار الإنتاج: dedupe + handler + معالج الأخطاء)."""

    async def go():
        await app.process_update(update)
        # بعض المعالجات غير حاجزة (block=False ضمنيًّا) ⇒ نسمح للمهمّة بالإكمال.
        await asyncio.sleep(0.05)

    asyncio.run(go())


def _assert_f1_preserved(db: Database, update_id: int, *, failure: str) -> None:
    """التأكيدات المشتركة للخيار C بعد فشل الإشعار."""
    # 1) الالتزام المحلي والنتيجة المؤهّلة محفوظان (مفيش تراجع/تخفيض/حذف).
    assert db.update_outcome(update_id) == uo.DURABLE_COMPLETED
    assert db.is_update_acknowledgment_eligible(update_id) is True
    # 2) صف الديدَب (مصدر الحقيقة) موجود ⇒ إعادة التسليم تُرفض كمكرّرة.
    assert db.update_is_processed(update_id) is True
    # 3) دليل فشل الإشعار منفصل في `update_failures` (مش في جدول الديدَب).
    assert db.update_failure(update_id) == failure


# ============================================================================
# 1) لكل مسار: فشل الإشعار بعد الالتزام ⇒ durable_completed + مؤهّل + دليل فشل منفصل
# ============================================================================
def test_cancel_route_notification_failure_preserves_commit(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, send_exc=TimedOut())
    db = app.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    _drive(app, _command_update(app, 9001, "/cancel"))

    assert db.get_awaiting(OWNER_ID) == (None, None)  # الحالة اتمسحت واتثبتت
    _assert_f1_preserved(db, 9001, failure=uo.FAILED_TRANSIENT)
    db.close()


def test_cancel_route_button_notification_failure_preserves_commit(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, edit_exc=TimedOut())
    db = app.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    _drive(app, _cb_update(app, 9002, "cancelroute"))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    _assert_f1_preserved(db, 9002, failure=uo.FAILED_TRANSIENT)
    db.close()


def test_reply_prompt_notification_failure_preserves_commit(tmp_path, monkeypatch):
    client = FakeOpenHands({CID_A: _conv(CID_A)})
    app = _build_app(tmp_path, monkeypatch, client=client, edit_exc=TimedOut())
    db = app.bot_data["db"]

    _drive(app, _cb_update(app, 9003, f"reply:{CID_A}"))

    assert db.get_awaiting(OWNER_ID) == (CID_A, "reply")
    _assert_f1_preserved(db, 9003, failure=uo.FAILED_TRANSIENT)
    db.close()


def test_repo_search_prompt_notification_failure_preserves_commit(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, edit_exc=TimedOut())
    db = app.bot_data["db"]

    _drive(app, _cb_update(app, 9004, "reposearch"))

    assert db.get_awaiting(OWNER_ID) == ("", "reposearch")
    _assert_f1_preserved(db, 9004, failure=uo.FAILED_TRANSIENT)
    db.close()


def test_pick_repo_notification_failure_preserves_commit(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, edit_exc=TimedOut())
    db = app.bot_data["db"]
    app.bot_data["repo_nav"] = {OWNER_ID: {"gen": 0, "names": ["owner/repo"]}}

    _drive(app, _cb_update(app, 9005, "pickrepo:0:0"))

    assert db.get_awaiting(OWNER_ID) == ("owner/repo", "newchat")
    _assert_f1_preserved(db, 9005, failure=uo.FAILED_TRANSIENT)
    db.close()


def test_new_chat_no_repo_notification_failure_preserves_commit(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, edit_exc=TimedOut())
    db = app.bot_data["db"]

    _drive(app, _cb_update(app, 9006, "norepo"))

    assert db.get_awaiting(OWNER_ID) == (None, "newchat")
    _assert_f1_preserved(db, 9006, failure=uo.FAILED_TRANSIENT)
    db.close()


# ============================================================================
# 2) رفض تيليجرام صريح (BadRequest) ⇒ فشل دائم مسجّل، والالتزام المحلي محفوظ
# ============================================================================
def test_notification_permanent_rejection_preserves_commit(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, send_exc=BadRequest("chat not found"))
    db = app.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    _drive(app, _command_update(app, 9007, "/cancel"))

    _assert_f1_preserved(db, 9007, failure=uo.FAILED_PERMANENT)
    db.close()


# ============================================================================
# 3) الإشعار الناجح ⇒ durable_completed بلا أي دليل فشل (مفيش تلويث)
# ============================================================================
def test_successful_notification_no_failure_record(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)  # بلا استثناءات
    db = app.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    _drive(app, _command_update(app, 9008, "/cancel"))

    assert db.update_outcome(9008) == uo.DURABLE_COMPLETED
    assert db.is_update_acknowledgment_eligible(9008) is True
    assert db.update_failure(9008) is None  # مفيش فشل كاذب
    db.close()


# ============================================================================
# 4) إعادة تسليم نفس التحديث ⇒ **ما تعيدش** الالتزام المحلي (الديدَب يمنعها)
# ============================================================================
def test_duplicate_delivery_does_not_repeat_local_transition(tmp_path, monkeypatch):
    """فشل الإشعار لا يُرخّص بإعادة التنفيذ: إعادة التسليم تُوقفها حاجز الديدَب."""
    app = _build_app(tmp_path, monkeypatch, edit_exc=TimedOut())
    db = app.bot_data["db"]
    app.bot_data["repo_nav"] = {OWNER_ID: {"gen": 0, "names": ["owner/repo"]}}

    upd = _cb_update(app, 9009, "pickrepo:0:0")
    _drive(app, upd)
    assert db.get_awaiting(OWNER_ID) == ("owner/repo", "newchat")

    # محاكاة إعادة تسليم نفس `update_id`: نغيّر الحالة يدويًّا، ثم نعيد التسليم.
    db.set_awaiting(OWNER_ID, "sentinel", "route", title="t")
    _drive(app, upd)

    # الـ handler **ما اتنفّذش** تاني (الديدَب أوقفه) ⇒ الحالة اليدوية لسه زي ما هي.
    assert db.get_awaiting(OWNER_ID) == ("sentinel", "route")
    _assert_f1_preserved(db, 9009, failure=uo.FAILED_TRANSIENT)
    db.close()


# ============================================================================
# 5) فشل تسجيل الفشل نفسه ⇒ **ما يُخفّضش** النتيجة الملتزمة (آمن)
# ============================================================================
def test_failure_recording_error_does_not_downgrade_commit(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, edit_exc=TimedOut())
    db = app.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    real = db.mark_update_outcome

    def _boom(update_id, *a, **k):
        outcome = a[1] if len(a) > 1 else k.get("outcome")
        if outcome is not None and outcome.startswith("failed"):
            raise sqlite3.OperationalError("simulated failure-record write error")
        return real(update_id, *a, **k)

    monkeypatch.setattr(db, "mark_update_outcome", _boom)

    _drive(app, _cb_update(app, 9010, "cancelroute"))

    # النتيجة الملتزمة محفوظة (اتكتبت قبل الإشعار)، ومعالج الأخطاء فشل بأمان (مفيش تخفيض).
    assert db.update_outcome(9010) == uo.DURABLE_COMPLETED
    assert db.is_update_acknowledgment_eligible(9010) is True
    assert db.update_failure(9010) is None  # فشل التسجيل ما عملش صف فشل
    db.close()


# ============================================================================
# 6) استمرارية الدليل بعد إعادة فتح القاعدة (restart)
# ============================================================================
def test_failure_evidence_survives_reopen(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, send_exc=TimedOut())
    db = app.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")
    _drive(app, _command_update(app, 9011, "/cancel"))
    db_path = db.path if hasattr(db, "path") else str(tmp_path / "t.sqlite3")
    db.close()

    db2 = Database(db_path)
    assert db2.update_outcome(9011) == uo.DURABLE_COMPLETED
    assert db2.is_update_acknowledgment_eligible(9011) is True
    assert db2.update_failure(9011) == uo.FAILED_TRANSIENT
    db2.close()


# ============================================================================
# 7) انتشار الإلغاء (CancelledError) بلا كتم، والالتزام المحلي محفوظ
# ============================================================================
def test_cancellation_propagates_and_commit_preserved(tmp_path, monkeypatch):
    """`CancelledError` مش `Exception` ⇒ `_safe_edit` ما بتلتقطهوش ⇒ ينتشر.

    الالتزام المحلي (حالة + نتيجة) حصل **قبل** الإرسال ⇒ محفوظ رغم الانتشار.
    """
    from types import SimpleNamespace

    db = Database(str(tmp_path / "cancel.sqlite3"))
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    class _Q:
        data = "cancelroute"

        async def answer(self):
            pass

        async def edit_message_text(self, *a, **k):
            raise asyncio.CancelledError()

    ctx = SimpleNamespace(
        bot_data={"db": db, "config": SimpleNamespace(is_allowed=lambda _u: True)},
    )
    update = SimpleNamespace(
        update_id=9012,
        effective_user=SimpleNamespace(id=OWNER_ID),
        effective_chat=SimpleNamespace(id=CHAT_ID, type="private"),
        callback_query=_Q(),
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(h.cancel_route_button(update, ctx))

    assert db.update_outcome(9012) == uo.DURABLE_COMPLETED
    assert db.is_update_acknowledgment_eligible(9012) is True
    assert db.get_awaiting(OWNER_ID) == (None, None)
    db.close()


# ============================================================================
# 8) تفاعل الدفعة: أول تحديث فاشل الإشعار لكنه مؤهّل ⇒ الحدّ يتقدّم (مفيش حجب)
# ============================================================================
def test_acknowledgment_boundary_advances_after_notification_failure(tmp_path, monkeypatch):
    """الفشل المنفصل **ما يحجبش** حدّ الإقرار (النتيجة المؤهّلة هي الحاكمة)."""
    app = _build_app(tmp_path, monkeypatch, edit_exc=TimedOut())
    db = app.bot_data["db"]
    app.bot_data["repo_nav"] = {OWNER_ID: {"gen": 0, "names": ["owner/repo"]}}

    upd = _cb_update(app, 9013, "pickrepo:0:0")
    _drive(app, upd)
    # إعادة بناء أزواج الدفعة زي `TelegramPoller.collect_outcomes`.
    pairs = [(9013, db.update_outcome(9013) or uo.PARTIAL_OR_UNKNOWN)]
    boundary = db.commit_batch_outcomes(pairs, outbox.now_iso())
    assert boundary == 9013  # الحدّ تقدّم (مفيش حجب head-of-line)
    assert db.update_failure(9013) == uo.FAILED_TRANSIENT
    db.close()


# ============================================================================
# 9) مسار الإنتاج الحقيقي (`TelegramPoller` بالطابور) — نفس النتيجة
# ============================================================================
def test_production_poller_records_evidence_and_advances(tmp_path, monkeypatch):
    """يشغّل `TelegramPoller.process_updates` الحقيقي (طابور + معالج أخطاء PTB).

    ده المسار الفعلي في الإنتاج (`updater(None)` + حلقة مخصّصة)، فبيأكّد إن الدليل
    المنفصل بيتحفظ وإن الحدّ بيتقدّم رغم فشل الإشعار.
    """
    from bot.polling import TelegramPoller
    from tests.test_stage2_custom_polling import _patch_bot_init

    async def run():
        _patch_bot_init(monkeypatch)
        app = app_mod.build_application(make_config(tmp_path))
        await app.initialize()
        await app.start()
        try:
            db = app.bot_data["db"]
            app.bot_data["repo_nav"] = {OWNER_ID: {"gen": 0, "names": ["owner/repo"]}}
            _patch_telegram(monkeypatch, edit_exc=TimedOut())
            upd = _cb_update(app, 9020, "pickrepo:0:0")
            poller = TelegramPoller(app, db)
            boundary = await poller.process_updates([upd])
            assert boundary == 9020  # الحدّ اتقدّم (مفيش إعادة تسليم)
            _assert_f1_preserved(db, 9020, failure=uo.FAILED_TRANSIENT)
        finally:
            await app.stop()
            await app.shutdown()

    asyncio.run(run())

