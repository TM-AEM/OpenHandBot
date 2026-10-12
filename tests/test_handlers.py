import asyncio
from types import SimpleNamespace

import pytest

import bot.handlers as h
from bot import outbox
from bot.db import Database
from bot.errors import ApiError


class FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append(text)


class FakeQuery:
    def __init__(self):
        self.edits = []
        self.message = SimpleNamespace(chat_id=99)

    async def answer(self):
        pass

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)


def make_update(user_id, text="hi"):
    msg = FakeMessage()
    msg.text = text
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type="private"),
        message=msg,
        callback_query=None,
    )


class FakeConfig:
    def __init__(self, allowed_id):
        self.allowed_telegram_ids = frozenset({allowed_id})
        self.owner_id = allowed_id
        self.openhands_base_url = "https://app.all-hands.dev"

    def is_allowed(self, user_id):
        return user_id in self.allowed_telegram_ids


def make_context(allowed_id, tmp_path, client=None):
    ctx = SimpleNamespace()
    ctx.bot_data = {
        "config": FakeConfig(allowed_id),
        "db": Database(str(tmp_path / "t.sqlite3")),
        "client": client,
    }
    ctx.bot = SimpleNamespace(sent=[], send_message=None)
    return ctx


def test_handle_text_ignores_non_owner(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(999)
    asyncio.run(h.handle_text(update, ctx))
    assert update.message.replies == []


def test_handle_text_owner_without_state_gets_hint(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(1)
    asyncio.run(h.handle_text(update, ctx))
    assert len(update.message.replies) == 1
    assert "/start" in update.message.replies[0]


def test_reply_acks_instantly_then_background(tmp_path, monkeypatch):
    ctx = make_context(1, tmp_path)
    ctx.bot_data["db"].set_awaiting(1, "conv-1", "reply")
    update = make_update(1, text="برومت")

    scheduled = []

    def fake_create_task(coro):
        scheduled.append(coro)
        coro.close()
        return None

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)
    asyncio.run(h.handle_text(update, ctx))

    assert update.message.replies == ["وصل ✅"]
    # مفيش task جديد لكل برومت: الـ worker الواحد هو اللي بياخد السجل.
    assert scheduled == []
    assert ctx.bot_data["db"].count_outbox("pending") == 1
    # الحالة اتشالت بعد الإرسال
    assert ctx.bot_data["db"].get_awaiting(1) == (None, None)


def test_start_ignores_non_owner(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(999)
    asyncio.run(h.start(update, ctx))
    assert update.message.replies == []


def test_start_owner_gets_menu(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(1)
    asyncio.run(h.start(update, ctx))
    assert len(update.message.replies) == 1


class FakeClient:
    def __init__(self, items):
        self._items = items

    async def search_conversations(self, limit=20, page_id=None):
        return {"items": self._items[:limit], "next_page_id": None}


def _list_update(user_id, page):
    msg = FakeMessage()
    q = FakeQuery()
    q.data = f"list:{page}"
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type="private"),
        message=msg,
        callback_query=q,
    )


def test_list_conversations_paginates_locally(tmp_path):
    items = [{"id": f"c{i}", "title": f"شات {i}", "execution_status": "running"} for i in range(15)]
    ctx = make_context(1, tmp_path, client=FakeClient(items))

    update = _list_update(1, 0)
    asyncio.run(h.list_conversations(update, ctx))
    first = update.callback_query.edits[-1]
    assert "صفحة 1" in first

    update = _list_update(1, 1)
    asyncio.run(h.list_conversations(update, ctx))
    second = update.callback_query.edits[-1]
    assert "صفحة 2" in second


def test_list_conversations_ignores_non_owner(tmp_path):
    ctx = make_context(1, tmp_path, client=FakeClient([]))
    update = _list_update(999, 0)
    asyncio.run(h.list_conversations(update, ctx))
    assert update.callback_query.edits == []


class DetailClient:
    def __init__(self, conv, files=None, content="", blob=b"zip"):
        self._conv = conv
        self._files = files or []
        self._content = content
        self._blob = blob

    async def get_conversations(self, ids):
        return [self._conv] if self._conv else []

    async def list_files(self, conversation_id, path=""):
        return self._files

    async def read_file(self, conversation_id, file_path):
        return self._content

    async def export_conversation(self, conversation_id):
        return self._blob


class FakeBotWithDocs:
    def __init__(self):
        self.sent = []
        self.documents = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)

    async def send_document(self, chat_id=None, document=None, **kw):
        self.documents.append(document)


def _cb_update(user_id, data):
    q = FakeQuery()
    q.data = data
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type="private"),
        message=SimpleNamespace(),
        callback_query=q,
    )


def _ctx_with(tmp_path, client):
    ctx = make_context(1, tmp_path, client=client)
    ctx.bot = FakeBotWithDocs()
    return ctx


class DeliverClient:
    """عميل كفاية لمسار _deliver_outbox: شات + إرسال رسالة."""

    def __init__(self, conv, send_error=None):
        self._conv = conv
        self._send_error = send_error
        self.sent_prompts = []

    async def get_conversations(self, ids):
        return [self._conv] if self._conv else []

    async def resume_sandbox(self, sandbox_id):
        pass

    async def send_message(self, conversation_id, text):
        if self._send_error:
            raise self._send_error
        self.sent_prompts.append((conversation_id, text))


def _seed_outbox(db, conversation_id="c1", chat_id=99, text="برومت"):
    return db.add_outbox(conversation_id, chat_id, text, "2026-01-01T00:00:00+00:00")


def test_deliver_outbox_baselines_actual_state_not_assumed_running(tmp_path):
    # U01 / TASK 04A-3: لو الشات كان منتهي قبل الإرسال، لازم نخزّن الحالة الفعلية
    # (finished) مش "running" مفترضة — عشان المراقب مايدّيش انتقال وهمي ويسلّم تقرير قديم.
    client = DeliverClient(
        {"id": "c1", "title": "شات", "execution_status": "finished", "sandbox_status": "RUNNING"}
    )
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    oid = _seed_outbox(db)
    asyncio.run(h._deliver_outbox(client, db, ctx.bot, oid))

    watched = db.list_watched()
    assert len(watched) == 1
    assert watched[0].conversation_id == "c1"
    assert watched[0].last_state == "finished"
    assert watched[0].last_state != "running"
    assert client.sent_prompts == [("c1", "برومت")]
    assert db.get_outbox(oid).status == "sent"


def test_deliver_outbox_baselines_running_state(tmp_path):
    client = DeliverClient(
        {"id": "c1", "title": "شات", "execution_status": "running", "sandbox_status": "RUNNING"}
    )
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    oid = _seed_outbox(db)
    asyncio.run(h._deliver_outbox(client, db, ctx.bot, oid))

    assert db.list_watched()[0].last_state == "running"


def test_deliver_outbox_handles_missing_state_as_unknown(tmp_path):
    # حالة malformed/مفقودة → برضه مش "running" (fail closed).
    client = DeliverClient({"id": "c1", "title": "شات", "sandbox_status": "RUNNING"})
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    oid = _seed_outbox(db)
    asyncio.run(h._deliver_outbox(client, db, ctx.bot, oid))

    assert db.list_watched()[0].last_state == ""


def test_show_status_reports_state(tmp_path):
    client = DetailClient({"id": "c1", "title": "شات", "execution_status": "running", "sandbox_status": "RUNNING"})
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "status:c1")
    asyncio.run(h.show_status(update, ctx))
    assert "شغال" in update.callback_query.edits[-1]
    assert "RUNNING" in update.callback_query.edits[-1]


def test_show_cost_reports_metrics(tmp_path):
    client = DetailClient({"id": "c1", "metrics": {"model_name": "m", "accumulated_cost": 2.5}})
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "cost:c1")
    asyncio.run(h.show_cost(update, ctx))
    assert "$2.5" in update.callback_query.edits[-1]


def test_list_files_caches_and_paginates(tmp_path):
    files = [f"f{i}.py" for i in range(12)]
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}, files=files))
    update = _cb_update(1, "files:c1:0")
    asyncio.run(h.list_files(update, ctx))
    assert ctx.bot_data["file_cache"]["c1"] == files
    assert "صفحة 1" in update.callback_query.edits[-1]


def test_show_file_sends_document(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}, files=["a/b/main.py"], content="hello"))
    ctx.bot_data["file_cache"] = {"c1": ["a/b/main.py"]}
    update = _cb_update(1, "file:c1:0")
    asyncio.run(h.show_file(update, ctx))
    assert len(ctx.bot.documents) == 1


def test_export_sends_zip(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}))
    update = _cb_update(1, "export:c1")
    asyncio.run(h.export_conversation(update, ctx))
    assert len(ctx.bot.documents) == 1


def test_list_watches_empty(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient(None))
    update = _cb_update(1, "watched:0")
    asyncio.run(h.list_watches(update, ctx))
    assert "مفيش" in update.callback_query.edits[-1]


def test_list_watches_shows_items(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient(None))
    ctx.bot_data["db"].add_watched("c1", "شات", chat_id=99)
    update = _cb_update(1, "watched:0")
    asyncio.run(h.list_watches(update, ctx))
    assert "متابعاتي" in update.callback_query.edits[-1]


def test_watch_conversation_adds_to_db(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1", "title": "شات", "execution_status": "running"}))
    update = _cb_update(1, "watch:c1")
    asyncio.run(h.watch_conversation(update, ctx))
    assert ctx.bot_data["db"].is_watched("c1")
    assert ctx.bot_data["db"].list_watched()[0].chat_id == 99


def test_unwatch_conversation_removes(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient(None))
    ctx.bot_data["db"].add_watched("c1")
    update = _cb_update(1, "unwatch:c1")
    asyncio.run(h.unwatch_conversation(update, ctx))
    assert not ctx.bot_data["db"].is_watched("c1")


# ------------------------------------------------------- outbox delivery (U03)
class OutboxBot:
    """بوت تيليجرام fake مع رسائل مرصودة وفشل اختياري."""

    def __init__(self, fail_contains=None):
        self.sent = []
        self._fail_contains = fail_contains

    async def send_message(self, chat_id=None, text=None, **kw):
        if self._fail_contains and self._fail_contains in (text or ""):
            from telegram.error import TelegramError

            raise TelegramError("boom")
        self.sent.append(text)


def _deliver(conv, db, bot, oid, send_error=None):
    client = DeliverClient(conv, send_error=send_error)
    asyncio.run(h._deliver_outbox(client, db, bot, oid))
    return client


def test_outbox_persisted_before_post_attempt(tmp_path):
    # لازم يكون فيه سجل outbox قبل ما الـ POST يبدأ: نتحقق من جوه الـ client نفسه.
    db = Database(str(tmp_path / "t.sqlite3"))
    seen = {}

    class ProbeClient:
        async def get_conversations(self, ids):
            return [{"id": "c1", "title": "شات", "sandbox_status": "RUNNING"}]

        async def send_message(self, conversation_id, text):
            seen["rows_at_post"] = db.count_outbox()

    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())
    asyncio.run(h._deliver_outbox(ProbeClient(), db, OutboxBot(), oid))
    assert seen["rows_at_post"] == 1  # السجل موجود قبل الـ POST
    assert db.get_outbox(oid).status == "sent"


def test_outbox_confirmed_success_is_sent(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())
    bot = OutboxBot()
    client = _deliver(
        {"id": "c1", "title": "شات", "execution_status": "running", "sandbox_status": "RUNNING"},
        db, bot, oid,
    )
    assert db.get_outbox(oid).status == "sent"
    assert client.sent_prompts == [("c1", "برومت")]
    assert any("اتبعت" in s for s in bot.sent)


def test_outbox_definite_rejection_is_failed_and_not_retried(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())
    bot = OutboxBot()
    _deliver(
        {"id": "c1", "title": "شات", "sandbox_status": "RUNNING"}, db, bot, oid,
        send_error=ApiError("طلب غير صحيح", 422),
    )
    item = db.get_outbox(oid)
    assert item.status == "failed"
    assert item.error == "HTTP 422"
    assert not db.is_watched("c1")
    assert db.list_outbox_by_status("pending") == []  # مايتعادش تلقائياً


def test_outbox_timeout_after_post_is_unknown_and_not_retried(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())
    _deliver(
        {"id": "c1", "title": "شات", "sandbox_status": "RUNNING"}, db, OutboxBot(), oid,
        send_error=ApiError("تعذّر الاتصال", None),
    )
    assert db.get_outbox(oid).status == "unknown"
    assert not db.is_watched("c1")


def test_outbox_connection_failure_ambiguous_is_not_blindly_retried(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())
    _deliver(
        {"id": "c1", "title": "شات", "sandbox_status": "RUNNING"}, db, OutboxBot(), oid,
        send_error=ApiError("تعذّر الاتصال بـ OpenHands", None),
    )
    assert db.get_outbox(oid).status == "unknown"
    # 'unknown' ⇒ recovery مش هيعيده.
    app = SimpleNamespace(bot_data={"db": db, "client": None}, bot=OutboxBot())
    asyncio.run(h.outbox_recover(app))
    assert db.get_outbox(oid).status == "unknown"


def test_outbox_failure_before_post_is_safe_to_retry(tmp_path):
    # فشل قراءة الشات قبل الـ POST ⇒ البرومت ماتبعتش ⇒ 'pending' (آمن يتعاود).
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())

    class BoomClient:
        async def get_conversations(self, ids):
            raise ApiError("تعذّر الاتصال", None)

    asyncio.run(h._deliver_outbox(BoomClient(), db, OutboxBot(), oid))
    assert db.get_outbox(oid).status == "pending"


def test_outbox_cancellation_during_post_is_unknown(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())

    class CancelClient:
        async def get_conversations(self, ids):
            return [{"id": "c1", "title": "شات", "sandbox_status": "RUNNING"}]

        async def send_message(self, conversation_id, text):
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(h._deliver_outbox(CancelClient(), db, OutboxBot(), oid))
    assert db.get_outbox(oid).status == "unknown"


def test_outbox_sandbox_not_ready_stays_pending(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())
    _deliver({"id": "c1", "title": "شات", "sandbox_status": "PAUSED"}, db, OutboxBot(), oid)
    assert db.get_outbox(oid).status == "pending"
    assert not db.is_watched("c1")


def test_outbox_notification_failure_does_not_change_status(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())
    bot = OutboxBot(fail_contains="اتبعت")
    _deliver(
        {"id": "c1", "title": "شات", "execution_status": "running", "sandbox_status": "RUNNING"},
        db, bot, oid,
    )
    assert db.get_outbox(oid).status == "sent"  # فشل الإشعار مايغيّرش الحالة


# ------------------------------------------------------- recovery (startup)
def _recover_app(db, client=None, bot=None):
    return SimpleNamespace(bot_data={"db": db, "client": client}, bot=bot or OutboxBot())


def test_recovery_leaves_pending_for_worker(tmp_path):
    # 'pending' مالمستش خالص ⇒ آمن: التعافي مايعملش حاجة بيه، والـ worker بياخده بعدين.
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())
    client = DeliverClient({"id": "c1", "title": "شات", "sandbox_status": "RUNNING"})
    asyncio.run(h.outbox_recover(_recover_app(db, client)))
    assert db.get_outbox(oid).status == "pending"
    assert client.sent_prompts == []  # التعافي نفسه مابعتش حاجة


def test_recovery_marks_sending_as_unknown_and_notifies(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())
    db.set_outbox_status(oid, "sending", outbox.now_iso())  # قطع أثناء الإرسال
    bot = OutboxBot()
    asyncio.run(h.outbox_recover(_recover_app(db, bot=bot)))
    assert db.get_outbox(oid).status == "unknown"
    assert any("مش متأكدين" in s for s in bot.sent)


def test_recovery_never_resends_sent_unknown_failed(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ids = {}
    for st in ("sent", "unknown", "failed"):
        oid = db.add_outbox("c1", 99, f"برومت {st}", outbox.now_iso())
        db.set_outbox_status(oid, st, outbox.now_iso())
        ids[st] = oid

    class ExplodeClient:
        async def get_conversations(self, ids):
            raise AssertionError("ماينفعش نلمس 'sent'/'unknown'/'failed'")

        async def send_message(self, conversation_id, text):
            raise AssertionError("ماينفعش نرسل 'sent'/'unknown'/'failed'")

    asyncio.run(h.outbox_recover(_recover_app(db, ExplodeClient())))
    for st, oid in ids.items():
        assert db.get_outbox(oid).status == st


def test_recovery_is_idempotent_no_duplicate_rows(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())
    db.set_outbox_status(oid, "sending", outbox.now_iso())
    app = _recover_app(db, client=None)
    asyncio.run(h.outbox_recover(app))
    asyncio.run(h.outbox_recover(app))  # إعادة تشغيل تانية
    assert db.get_outbox(oid).status == "unknown"
    assert db.count_outbox() == 1  # مفيش سجل مكرّر


def test_recovery_sending_without_client_still_marks_unknown(tmp_path):
    # عنصر 'sending' اتحوّل 'unknown' من غير أي محاولة إرسال (حتى لو الـ client None).
    db = Database(str(tmp_path / "t.sqlite3"))
    oid = db.add_outbox("c1", 99, "برومت", outbox.now_iso())
    db.set_outbox_status(oid, "sending", outbox.now_iso())
    asyncio.run(h.outbox_recover(_recover_app(db, client=None)))
    assert db.get_outbox(oid).status == "unknown"



# ------------------------------------------- outbox + awaiting / authorization
def test_send_prompt_persists_outbox_then_wakes_worker(tmp_path, monkeypatch):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "conv-1", "reply")
    update = make_update(1, text="برومت")

    scheduled = []

    def fake_create_task(coro):
        scheduled.append(coro)
        coro.close()
        return None

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    class Worker:
        def __init__(self):
            self.woken = 0

        def wake(self):
            self.woken += 1

    worker = Worker()
    ctx.bot_data["outbox_worker"] = worker
    asyncio.run(h.handle_text(update, ctx))

    assert update.message.replies == ["وصل ✅"]
    assert scheduled == []  # مفيش task لكل برومت — الـ worker الواحد هو المسؤول
    assert worker.woken == 1  # اتوقّظ بدل ما نعمل task جديد
    assert db.count_outbox("pending") == 1  # اتسجّل قبل ما التسليم يبدأ
    item = db.list_outbox_by_status("pending")[0]
    assert item.conversation_id == "conv-1"
    assert item.text == "برومت"
    assert db.get_awaiting(1) == (None, None)  # awaiting اتشالت (السلوك الأصلي)


def test_non_owner_text_does_not_create_outbox_row(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(999, "conv-1", "reply")
    update = make_update(999, text="برومت")
    asyncio.run(h.handle_text(update, ctx))
    assert db.count_outbox() == 0
    assert update.message.replies == []



# ------------------------------------------------------ new-chat creation (04A-6)
class CreationClient:
    """عميل fake لمسار الشات الجديد."""

    def __init__(self, task_id="task-1", conv="conv-1", start_error=None):
        self._task_id = task_id
        self._conv = conv
        self._start_error = start_error
        self.start_calls = 0

    async def start_conversation(self, text, repo, branch=None):
        self.start_calls += 1
        if self._start_error is not None:
            raise self._start_error
        return self._task_id

    async def wait_for_start(self, task_id, timeout=180.0, interval=3.0):
        return self._conv


class _SendBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


def test_new_chat_persists_job_then_wakes_creation_worker(tmp_path, monkeypatch):
    ctx = make_context(1, tmp_path)
    ctx.bot_data["db"].set_awaiting(1, "o/r", "newchat")
    update = make_update(1, text="ابدأ شات")

    scheduled = []

    def fake_create_task(coro):
        scheduled.append(coro)
        coro.close()
        return None

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    class Worker:
        def __init__(self):
            self.woken = 0

        def wake(self):
            self.woken += 1

    worker = Worker()
    ctx.bot_data["creation_worker"] = worker
    asyncio.run(h.handle_text(update, ctx))

    assert update.message.replies == ["وصل ✅ جاري بدء شات جديد."]
    assert scheduled == []  # مفيش task لكل طلب — worker الإنشاء هو المسؤول
    assert worker.woken == 1
    jobs = ctx.bot_data["db"].list_creation_jobs_by_status("pending")
    assert len(jobs) == 1  # اتسجّل قبل ما POST البدء يبدأ
    assert jobs[0].repo == "o/r"
    assert jobs[0].text == "ابدأ شات"
    assert ctx.bot_data["db"].get_awaiting(1) == (None, None)


def test_non_owner_new_chat_creates_no_job(tmp_path):
    ctx = make_context(1, tmp_path)
    ctx.bot_data["db"].set_awaiting(999, "o/r", "newchat")
    update = make_update(999, text="ابدأ شات")
    asyncio.run(h.handle_text(update, ctx))
    assert ctx.bot_data["db"].count_creation_jobs() == 0
    assert update.message.replies == []


def test_create_chat_direct_persists_and_finishes(tmp_path):
    client = CreationClient(conv="conv-42")
    ctx = make_context(1, tmp_path, client=client)
    ctx.bot = _SendBot()
    asyncio.run(h._create_chat(ctx, 99, "o/r", "برومت"))
    db = ctx.bot_data["db"]
    jobs = db.list_creation_jobs_by_status("done")
    assert len(jobs) == 1
    assert jobs[0].conversation_id == "conv-42"
    assert db.is_watched("conv-42")


def test_create_chat_direct_ambiguous_is_unknown(tmp_path):
    client = CreationClient(start_error=ApiError("timeout", None))
    ctx = make_context(1, tmp_path, client=client)
    ctx.bot = _SendBot()
    asyncio.run(h._create_chat(ctx, 99, "o/r", "برومت"))
    db = ctx.bot_data["db"]
    assert db.count_creation_jobs("unknown") == 1
    assert client.start_calls == 1

