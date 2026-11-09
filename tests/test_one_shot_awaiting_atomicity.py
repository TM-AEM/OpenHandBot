"""OHB2-ONE-SHOT-ROUTING-CRASH-CONSISTENCY: اختبارات انحدار على **ذرّية استهلاك حالة
الانتظار مع كتابة العمل الدائم**.

المشكلة المُبلَّغ عنها (تأكيد مستقل): الحالات لمرة واحدة (`reply`/`newchat`/`reposearch`)
كانت بتتستهلك في `take_awaiting` **قبل** كتابة السجل الدائم. عطل في النافذة بينهم = فقد
دائم للبرومت (الحالة اتمسحت، مفيش سجل، وإعادة التسليم بتلاقي مفيش حالة فتتجاهل).

الإصلاح: `handle_text` بقى **يقرأ بدون استهلاك** (`awaiting_state`)، والاستهلاك بقى
**ذرّيًا مع كتابة السجل الدائم** (`add_or_group_outbox`/`add_creation_job` عبر
`consume_awaiting`، وبحث المستودعات عبر `consume_one_shot_awaiting`) — كلهم `BEGIN IMMEDIATE`
واحدة. عطل قبل الكتابة ⇒ الاتنين يتراجعوا ⇒ إعادة التسليم تنفّذ (مفيش فقد).

الاختبارات بتستخدم قاعدة SQLite حقيقية ومدخل `Application.process_update` الحقيقي.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from telegram import Chat, Message

from bot import outbox
from bot.db import Database

from tests.test_duplicate_update_dispatch import (
    CHAT_ID,
    CID_A,
    OWNER_ID,
    FakeOpenHands,
    Harness,
    _conv,
)

# معرّفات تحديث فريدة عبر الملف (تجنّب التصادم مع ملفات اختبار تانية).
U_REPLY = 1_101_001
U_NEWCHAT = 1_101_002
U_REPOS = 1_101_003
U_ROUTE = 1_101_004


class ReposClient(FakeOpenHands):
    """عميل بيدّعي بحث مستودعات حقيقي (بدون شبكة)."""

    def __init__(self) -> None:
        super().__init__()
        self.searches: list[str] = []

    async def search_repositories(self, query="", limit=100):
        self.searches.append(query)
        return [{"full_name": "owner/repoA"}, {"full_name": "owner/repoB"}]


def _patch_telegram(monkeypatch):
    """يعترض نداءات تيليجرام (بدون شبكة)، ويرجّع رسائل **مربوطة بالبوت** عشان
    `_show_repos` يقدر يعدّلها (edit_text) زي المسار الحقيقي."""

    async def _send_message(self, chat_id=None, text=None, **kw):
        m = Message(message_id=1, date=None, chat=Chat(id=chat_id or CHAT_ID, type="private"))
        m.set_bot(self)
        return m

    async def _edit_message_text(self, *a, **kw):
        m = Message(message_id=1, date=None, chat=Chat(id=CHAT_ID, type="private"))
        m.set_bot(self)
        return m

    async def _noop(self, *a, **kw):
        return True

    monkeypatch.setattr("telegram.Bot.send_message", _send_message)
    monkeypatch.setattr("telegram.Bot.edit_message_text", _edit_message_text)
    monkeypatch.setattr("telegram.Bot.answer_callback_query", _noop)
    monkeypatch.setattr("telegram.Bot.set_my_commands", _noop)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _noop)


def _harness(tmp_path, monkeypatch, client=None) -> Harness:
    _patch_telegram(monkeypatch)
    return Harness(tmp_path, client=client)


def _raise_operational(*_a, **_k):
    raise sqlite3.OperationalError("simulated crash before commit")


# ============================================================================
# 1) نافذة الفقد للحالات لمرة واحدة: عطل قبل الكتابة الدائمة ⇒ الحالة تفضل ⇒ إعادة التسليم تنفّذ
# ============================================================================
def test_reply_crash_before_durable_write_keeps_state_and_redelivery_sends(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "reply")
    update = h.text_update(U_REPLY, "برومت مايضيعش")

    calls = {"n": 0}
    original = h.db.add_or_group_outbox

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            _raise_operational()
        return original(*a, **k)

    monkeypatch.setattr(h.db, "add_or_group_outbox", flaky)

    h.process(update)  # العطل: الاستثناء بيتابتلع في PTB
    assert calls["n"] == 1
    assert h.db.get_awaiting(OWNER_ID) == (CID_A, "reply")  # الحالة **مااتستهلكتش** (مفيش فقد)
    assert h.db.count_outbox() == 0
    assert h.db.update_is_processed(U_REPLY) is False

    h.process(update)  # إعادة تسليم نفس التحديث ⇒ لازم تنفّذ
    h.deliver_pending()
    assert h.client.sends == [(CID_A, "برومت مايضيعش")]
    assert h.db.get_awaiting(OWNER_ID) == (None, None)  # اتستهلكت مع الكتابة
    assert h.db.update_is_processed(U_REPLY) is True


def test_newchat_crash_before_durable_write_keeps_state_and_redelivery_creates(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands())
    h.db.set_awaiting(OWNER_ID, "owner/repo", "newchat")
    update = h.text_update(U_NEWCHAT, "برومت مايضيعش")

    calls = {"n": 0}
    original = h.db.add_creation_job

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            _raise_operational()
        return original(*a, **k)

    monkeypatch.setattr(h.db, "add_creation_job", flaky)

    h.process(update)
    assert calls["n"] == 1
    assert h.db.get_awaiting(OWNER_ID) == ("owner/repo", "newchat")  # الحالة باقية
    assert h.db.list_open_creation_jobs() == []
    assert h.db.update_is_processed(U_NEWCHAT) is False

    h.process(update)  # إعادة التسليم ⇒ شات واحد
    h.run_creation_worker_once()
    assert h.client.creates == [("برومت مايضيعش", "owner/repo")]
    assert h.db.get_awaiting(OWNER_ID) == (None, None)


def test_reposearch_crash_before_consume_keeps_state_and_redelivery_resends(tmp_path, monkeypatch):
    client = ReposClient()
    h = _harness(tmp_path, monkeypatch, client)
    h.db.set_awaiting(OWNER_ID, "", "reposearch")
    update = h.text_update(U_REPOS, "bot")

    calls = {"n": 0}
    original = h.db.consume_one_shot_awaiting

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            _raise_operational()
        return original(*a, **k)

    monkeypatch.setattr(h.db, "consume_one_shot_awaiting", flaky)

    h.process(update)  # العطل بعد إرسال القايمة وقبل الاستهلاك
    assert calls["n"] == 1
    assert h.db.get_awaiting(OWNER_ID) == ("", "reposearch")  # الحالة باقية
    assert h.db.update_is_processed(U_REPOS) is False

    h.process(update)  # إعادة التسليم ⇒ تنفّذ وتستهلك
    assert h.db.get_awaiting(OWNER_ID) == (None, None)
    assert h.db.update_is_processed(U_REPOS) is True
    assert client.searches == ["bot", "bot"]  # البحث اتنفّذ مرتين (مفيش فقد)


def test_route_crash_before_durable_write_renewed_and_redelivery_sends(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    update = h.text_update(U_ROUTE, "برومت route")

    calls = {"n": 0}
    original = h.db.add_or_group_outbox

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            _raise_operational()
        return original(*a, **k)

    monkeypatch.setattr(h.db, "add_or_group_outbox", flaky)

    h.process(update)
    assert h.db.get_awaiting(OWNER_ID) == (CID_A, "route")  # route مستمر: لسه قائم
    h.process(update)
    h.deliver_pending()
    assert h.client.sends == [(CID_A, "برومت route")]
    assert h.db.get_awaiting(OWNER_ID) == (CID_A, "route")  # لسه قائم (route مايتستهلكش)


# ============================================================================
# 2) النجاح: يستهلك الحالة المتوقعة بالظبط ويعمل سجلًا دائمًا **واحد**
# ============================================================================
def test_successful_reply_consumes_state_and_one_record(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "reply")
    h.process(h.text_update(U_REPLY + 10, "برومت"))
    assert h.db.count_outbox() == 1
    assert h.db.get_awaiting(OWNER_ID) == (None, None)
    assert h.db.update_is_processed(U_REPLY + 10) is True


def test_successful_newchat_consumes_state_and_one_record(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands())
    h.db.set_awaiting(OWNER_ID, "owner/repo", "newchat")
    h.process(h.text_update(U_NEWCHAT + 10, "برومت"))
    assert len(h.db.list_open_creation_jobs()) == 1
    assert h.db.get_awaiting(OWNER_ID) == (None, None)


def test_successful_reposearch_consumes_state(tmp_path, monkeypatch):
    client = ReposClient()
    h = _harness(tmp_path, monkeypatch, client)
    h.db.set_awaiting(OWNER_ID, "", "reposearch")
    h.process(h.text_update(U_REPOS + 10, "bot"))
    assert h.db.get_awaiting(OWNER_ID) == (None, None)
    assert h.db.update_is_processed(U_REPOS + 10) is True


# ============================================================================
# 3) إعادة تسليم نفس `update_id` ⇒ مفيش سجل دائم تاني (الحماية القديمة محفوظة)
# ============================================================================
def test_duplicate_update_id_creates_no_second_record(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "reply")
    update = h.text_update(U_REPLY + 20, "برومت")
    h.process(update)
    h.process(update)  # نفس التحديث تاني
    assert h.db.count_outbox() == 1  # سجل واحد بس
    h.deliver_pending()
    assert h.client.sends == [(CID_A, "برومت")]  # إرسال واحد بس


def test_duplicate_newchat_update_id_creates_no_second_job(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands())
    h.db.set_awaiting(OWNER_ID, "owner/repo", "newchat")
    update = h.text_update(U_NEWCHAT + 20, "برومت")
    h.process(update)
    h.process(update)
    assert len(h.db.list_open_creation_jobs()) == 1


# ============================================================================
# 4) التراجع: استثناء قبل الـ commit يرجّع **الاتنين** (الحالة + العمل الدائم)
# ============================================================================
def test_db_exception_rolls_back_both_state_and_durable_work(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "reply")

    # عطل جوه المعاملة **بعد** كتابة الصندوق وقبل الـ commit.
    monkeypatch.setattr(h.db, "_mark_processed_nocommit", _raise_operational)

    with pytest.raises(sqlite3.OperationalError):
        h.db.add_or_group_outbox(
            CID_A, CHAT_ID, "برومت", outbox.now_iso(), reengage=True,
            update_id=U_REPLY + 30, consume_awaiting=(OWNER_ID, "reply"),
        )

    assert h.db.count_outbox() == 0  # الكتابة اتراجعت
    assert h.db.get_awaiting(OWNER_ID) == (CID_A, "reply")  # والاستهلاك اتراجع
    assert h.db.update_is_processed(U_REPLY + 30) is False  # والعلامة اتراجعت


# ============================================================================
# 5) استرجاع بعد إعادة تشغيل: العمل الدائم المكتمل بيفضل (مسار الاسترجاع الموجود)
# ============================================================================
def test_restart_recovery_preserves_pending_work(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "reply")
    h.process(h.text_update(U_REPLY + 40, "برومت"))  # اتحفظ 'pending' (قبل أي إرسال)

    # إعادة تشغيل: اتصال جديد على نفس الملف.
    reopened = Database(str(Path(tmp_path) / "t.sqlite3"))
    assert len(reopened.list_outbox_by_status("pending")) == 1
    assert reopened.update_is_processed(U_REPLY + 40) is True  # العلامة دائمة كمان


# ============================================================================
# 6) حالة غير متوقّعة/متغيّرة ما تتستهلكش
# ============================================================================
def test_changed_awaiting_kind_not_consumed(tmp_path, monkeypatch):
    """الحالة بقت `route` (اتغيّرت) لكن الطلب بيستهلك `reply` ⇒ مفيش استهلاك ولا كتابة."""
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    out_id = h.db.add_or_group_outbox(
        CID_A, CHAT_ID, "برومت", outbox.now_iso(), reengage=True,
        update_id=U_ROUTE + 10, consume_awaiting=(OWNER_ID, "reply"),
    )
    assert out_id == 0  # مرفوض: النوع مش متوقّع
    assert h.db.count_outbox() == 0
    assert h.db.get_awaiting(OWNER_ID) == (CID_A, "route")  # الحالة اتسابت زي ما هي
    assert h.db.update_is_processed(U_ROUTE + 10) is False


def test_missing_awaiting_not_consumed(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    out_id = h.db.add_or_group_outbox(
        CID_A, CHAT_ID, "برومت", outbox.now_iso(), reengage=True,
        update_id=U_REPLY + 50, consume_awaiting=(OWNER_ID, "reply"),
    )
    assert out_id == 0
    assert h.db.count_outbox() == 0


def test_expired_awaiting_consumed_without_durable_work(tmp_path, monkeypatch):
    """حالة منتهية: تتشال (نفس السلوك الأصلي) بدون إنشاء سجل دائم."""
    from datetime import datetime, timedelta, timezone

    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    aged = datetime.now(timezone.utc) - timedelta(minutes=30)
    h.db.set_awaiting(OWNER_ID, CID_A, "reply", now=aged)
    out_id = h.db.add_or_group_outbox(
        CID_A, CHAT_ID, "برومت", outbox.now_iso(), reengage=True,
        update_id=U_REPLY + 60, consume_awaiting=(OWNER_ID, "reply"),
    )
    assert out_id == 0
    assert h.db.count_outbox() == 0
    assert h.db.get_awaiting(OWNER_ID) == (None, None)  # اتشالت


def test_consume_one_shot_awaiting_kind_mismatch(tmp_path):
    db = Database(str(Path(tmp_path) / "t.sqlite3"))
    db.set_awaiting(1, "c", "newchat")
    assert db.consume_one_shot_awaiting(1, "reposearch", 900, outbox.now_iso()) is False
    assert db.get_awaiting(1) == ("c", "newchat")
    assert db.consume_one_shot_awaiting(1, "newchat", 900, outbox.now_iso()) is True
    assert db.get_awaiting(1) == (None, None)
    assert db.update_is_processed(900) is True


# ============================================================================
# 7) P3: تبديل الإشعارات ذرّيًا (مرة واحدة لكل `update_id`)
# ============================================================================
def test_notif_toggle_once_atomic_direct(tmp_path):
    db = Database(str(Path(tmp_path) / "t.sqlite3"))
    assert db.get_notifications_enabled() is True  # الافتراضي مفعّل
    assert db.toggle_notifications_once(1, "t") is False  # بقى متوقف
    assert db.get_notifications_enabled() is False
    assert db.toggle_notifications_once(1, "t") is None  # نفس التحديث ⇒ مرفوض
    assert db.get_notifications_enabled() is False  # ما اتعكستش تاني
    assert db.toggle_notifications_once(2, "t") is True  # تحديث مختلف ⇒ تبديل عادي
    assert db.get_notifications_enabled() is True


def test_notif_toggle_rolls_back_on_error(tmp_path, monkeypatch):
    db = Database(str(Path(tmp_path) / "t.sqlite3"))
    monkeypatch.setattr(db, "_mark_processed_nocommit", _raise_operational)
    with pytest.raises(sqlite3.OperationalError):
        db.toggle_notifications_once(1, "t")
    assert db.get_notifications_enabled() is True  # التبديل اتراجع
    assert db.update_is_processed(1) is False


def test_notif_toggle_duplicate_update_id_toggles_once(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch)
    h.process(h.callback_update(U_REPLY + 70, "notif:toggle"))
    assert h.db.get_notifications_enabled() is False
    h.process(h.callback_update(U_REPLY + 70, "notif:toggle"))  # نفس التحديث
    assert h.db.get_notifications_enabled() is False  # ما اتعكستش تاني


def test_notif_toggle_distinct_update_ids_toggle_each_time(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch)
    h.process(h.callback_update(U_REPLY + 80, "notif:toggle"))
    assert h.db.get_notifications_enabled() is False
    h.process(h.callback_update(U_REPLY + 81, "notif:toggle"))
    assert h.db.get_notifications_enabled() is True  # تحديث مختلف ⇒ تبديل عادي
