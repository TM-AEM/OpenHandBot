"""اختبارات أوامر المراجعة اليدوية للصندوق: صلاحية المالك، تأكيد، idempotency، أمان."""
import asyncio
from types import SimpleNamespace

import bot.handlers as h
from bot.db import Database
from bot.outbox import OutboxWorker


class FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append(text)


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


class FakeConfig:
    def __init__(self, allowed_id):
        self.allowed_telegram_ids = frozenset({allowed_id})
        self.owner_id = allowed_id
        self.openhands_base_url = "https://app.all-hands.dev"

    def is_allowed(self, user_id):
        return user_id in self.allowed_telegram_ids


def make_update(user_id, text=""):
    msg = FakeMessage()
    msg.text = text
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type="private"),
        message=msg,
        callback_query=None,
    )


def make_ctx(tmp_path, allowed_id=1):
    ctx = SimpleNamespace()
    ctx.bot_data = {
        "config": FakeConfig(allowed_id),
        "db": Database(str(tmp_path / "t.sqlite3")),
        "client": None,
    }
    ctx.bot = FakeBot()
    ctx.args = []
    return ctx


def run(coro):
    return asyncio.run(coro)


SECRET = "سر-البرومت-الحساس"


# ------------------------------------------------------------ authorization
def test_list_non_owner_cannot_see_records(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.bot_data["db"].add_outbox("c1", 99, SECRET, "t")
    update = make_update(999)
    run(h.outbox_list(update, ctx))
    assert update.message.replies == []


def test_status_non_owner_cannot_see_record(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.bot_data["db"].add_outbox("c1", 99, SECRET, "t")
    ctx.args = ["prompt:1"]
    update = make_update(999)
    run(h.outbox_status(update, ctx))
    assert update.message.replies == []


def test_discard_non_owner_has_no_effect(tmp_path):
    ctx = make_ctx(tmp_path)
    oid = ctx.bot_data["db"].add_outbox("c1", 99, SECRET, "t")
    ctx.args = ["prompt:1", "confirm"]
    update = make_update(999)
    run(h.outbox_discard(update, ctx))
    assert ctx.bot_data["db"].get_outbox(oid).status == "pending"
    assert update.message.replies == []


def test_mark_sent_non_owner_has_no_effect(tmp_path):
    ctx = make_ctx(tmp_path)
    oid = ctx.bot_data["db"].add_outbox("c1", 99, SECRET, "t")
    ctx.bot_data["db"].set_outbox_status(oid, "unknown", "t")
    ctx.args = ["prompt:1", "confirm"]
    update = make_update(999)
    run(h.outbox_mark_sent(update, ctx))
    assert ctx.bot_data["db"].get_outbox(oid).status == "unknown"


# ------------------------------------------------------------ listing
def test_list_shows_open_records_without_prompt_text(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.bot_data["db"].add_outbox("c1", 99, SECRET, "t")
    ctx.bot_data["db"].add_creation_job(99, "o/r", SECRET, "t")
    update = make_update(1)
    run(h.outbox_list(update, ctx))
    out = update.message.replies[-1]
    assert "prompt:1" in out and "creation:1" in out and "pending" in out
    assert SECRET not in out  # مفيش نص البرومت


def test_list_is_bounded_and_empty_message(tmp_path):
    ctx = make_ctx(tmp_path)
    update = make_update(1)
    run(h.outbox_list(update, ctx))
    out = update.message.replies[-1]
    assert "مفيش" in out


def test_list_excludes_terminal_records(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    oid = db.add_outbox("c1", 99, SECRET, "t")
    db.set_outbox_status(oid, "sent", "t")
    update = make_update(1)
    run(h.outbox_list(update, ctx))
    assert "prompt:1" not in update.message.replies[-1]


# ------------------------------------------------------------ status details
def test_status_shows_details_without_prompt(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    oid = db.add_outbox("c1", 99, SECRET, "t")
    db.set_outbox_status(oid, "unknown", "t", "HTTP 503")
    ctx.args = ["prompt:1"]
    update = make_update(1)
    run(h.outbox_status(update, ctx))
    out = update.message.replies[-1]
    assert "unknown" in out and "HTTP 503" in out
    assert SECRET not in out


def test_status_shows_creation_task_id(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    jid = db.add_creation_job(99, "o/r", SECRET, "t")
    db.set_creation_starting(jid, "t", task_id="task-xyz")
    ctx.args = ["creation:1"]
    update = make_update(1)
    run(h.outbox_status(update, ctx))
    out = update.message.replies[-1]
    assert "task-xyz" in out
    assert SECRET not in out


# ------------------------------------------------------------ malformed / missing
def test_commands_reject_missing_id(tmp_path):
    ctx = make_ctx(tmp_path)
    for fn in (h.outbox_status, h.outbox_discard, h.outbox_mark_sent):
        ctx.args = []
        update = make_update(1)
        run(fn(update, ctx))
        assert "استخدام" in update.message.replies[-1]


def test_commands_reject_malformed_id(tmp_path):
    ctx = make_ctx(tmp_path)
    # مرجع مجرّد أو نوع غلط أو معرّف غلط ⇒ استخدام (مفيش تغيير).
    bad_refs = (
        "abc", "-1", "0", "1.5", "1", "prompt:", "prompt:0", "prompt:-1", "prompt:x",
        "prompt:1.5", "Prompt:1", "foo:1", ":1", "creation", "prompt",
    )
    for fn in (h.outbox_status, h.outbox_discard, h.outbox_mark_sent):
        for bad in bad_refs:
            ctx.args = [bad, "confirm"]
            update = make_update(1)
            run(fn(update, ctx))
            assert "استخدام" in update.message.replies[-1], (fn.__name__, bad)


def test_status_nonexistent_record_is_safe(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.args = ["prompt:999"]
    update = make_update(1)
    run(h.outbox_status(update, ctx))
    assert "مفيش" in update.message.replies[-1]


# ------------------------------------------------------------ discard
def test_discard_requires_confirmation(tmp_path):
    ctx = make_ctx(tmp_path)
    oid = ctx.bot_data["db"].add_outbox("c1", 99, SECRET, "t")
    ctx.bot_data["db"].set_outbox_status(oid, "unknown", "t")
    ctx.args = ["prompt:1"]
    update = make_update(1)
    run(h.outbox_discard(update, ctx))
    assert ctx.bot_data["db"].get_outbox(oid).status == "unknown"  # مفيش تغيير
    assert "تأكيد" in update.message.replies[-1]


def test_discard_confirmed_marks_discarded(tmp_path):
    ctx = make_ctx(tmp_path)
    oid = ctx.bot_data["db"].add_outbox("c1", 99, SECRET, "t")
    ctx.bot_data["db"].set_outbox_status(oid, "unknown", "t")
    ctx.args = ["prompt:1", "confirm"]
    update = make_update(1)
    run(h.outbox_discard(update, ctx))
    assert ctx.bot_data["db"].get_outbox(oid).status == "discarded"


def test_discard_is_idempotent_on_terminal(tmp_path):
    ctx = make_ctx(tmp_path)
    oid = ctx.bot_data["db"].add_outbox("c1", 99, SECRET, "t")
    ctx.bot_data["db"].set_outbox_status(oid, "sent", "t")
    ctx.args = ["prompt:1", "confirm"]
    update = make_update(1)
    run(h.outbox_discard(update, ctx))
    assert ctx.bot_data["db"].get_outbox(oid).status == "sent"  # مايتحوّلش من نهائي
    assert "نهائية" in update.message.replies[-1]


def test_discard_creation_job(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    jid = db.add_creation_job(99, "o/r", SECRET, "t")
    db.set_creation_status(jid, "unknown", "t")
    ctx.args = ["creation:1", "confirm"]
    update = make_update(1)
    run(h.outbox_discard(update, ctx))
    assert db.get_creation_job(jid).status == "discarded"


# ------------------------------------------------------------ mark sent
def test_mark_sent_requires_confirmation(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    oid = db.add_outbox("c1", 99, SECRET, "t")
    db.set_outbox_status(oid, "unknown", "t")
    ctx.args = ["prompt:1"]
    update = make_update(1)
    run(h.outbox_mark_sent(update, ctx))
    assert db.get_outbox(oid).status == "unknown"
    assert "تأكيد" in update.message.replies[-1]


def test_mark_sent_confirmed_unknown_to_sent(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    oid = db.add_outbox("c1", 99, SECRET, "t")
    db.set_outbox_status(oid, "unknown", "t")
    ctx.args = ["prompt:1", "confirm"]
    update = make_update(1)
    run(h.outbox_mark_sent(update, ctx))
    assert db.get_outbox(oid).status == "sent"
    assert "مش إثبات" in update.message.replies[-1]  # تأكيد مش إثبات


def test_mark_sent_is_idempotent(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    oid = db.add_outbox("c1", 99, SECRET, "t")
    db.set_outbox_status(oid, "unknown", "t")
    ctx.args = ["prompt:1", "confirm"]
    run(h.outbox_mark_sent(make_update(1), ctx))
    update = make_update(1)
    run(h.outbox_mark_sent(update, ctx))
    assert db.get_outbox(oid).status == "sent"
    assert "بالفعل" in update.message.replies[-1]


def test_mark_sent_refuses_non_unknown(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    oid = db.add_outbox("c1", 99, SECRET, "t")  # pending
    ctx.args = ["prompt:1", "confirm"]
    update = make_update(1)
    run(h.outbox_mark_sent(update, ctx))
    assert db.get_outbox(oid).status == "pending"  # مايتغيّرش
    assert "unknown" in update.message.replies[-1]


def test_mark_sent_creation_job(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    jid = db.add_creation_job(99, "o/r", SECRET, "t")
    db.set_creation_status(jid, "unknown", "t")
    ctx.args = ["creation:1", "confirm"]
    run(h.outbox_mark_sent(make_update(1), ctx))
    assert db.get_creation_job(jid).status == "done"


# ------------------------------------------------------------ id collisions (prompt vs creation)
def _seed_collision(ctx):
    """ينشئ سجل برومت وسجل شات بنفس المعرّف الرقمي 1 (تقاطع مقصود)."""
    db = ctx.bot_data["db"]
    pid = db.add_outbox("c1", 99, SECRET, "t")          # prompt:1
    cid = db.add_creation_job(99, "o/r", SECRET, "t")   # creation:1
    assert pid == 1 and cid == 1
    return db, pid, cid


def test_parse_ref_accepts_valid_and_rejects_ambiguous():
    assert h._parse_ref("prompt:12") == ("prompt", 12)
    assert h._parse_ref("creation:7") == ("creation", 7)
    assert h._parse_ref("  prompt:3  ") == ("prompt", 3)
    for bad in (None, "", "1", "prompt", "prompt:", "prompt:0", "prompt:-1", "prompt:1.5",
                "Prompt:1", "foo:1", ":1", "prompt:1:2", "creation:x"):
        assert h._parse_ref(bad) is None, bad


def test_list_emits_type_prefixed_refs_for_collision(tmp_path):
    ctx = make_ctx(tmp_path)
    _seed_collision(ctx)
    update = make_update(1)
    run(h.outbox_list(update, ctx))
    out = update.message.replies[-1]
    assert "prompt:1" in out
    assert "creation:1" in out


def test_status_routes_collision_to_exact_record(tmp_path):
    ctx = make_ctx(tmp_path)
    db, pid, cid = _seed_collision(ctx)
    db.set_outbox_status(pid, "unknown", "t", "prompt-err")
    db.set_creation_status(cid, "starting", "t", "creation-err")

    ctx.args = ["prompt:1"]
    update = make_update(1)
    run(h.outbox_status(update, ctx))
    out = update.message.replies[-1]
    assert "برومت prompt:1" in out and "prompt-err" in out
    assert "creation-err" not in out  # مايقرأش سجل الجدول التاني

    ctx.args = ["creation:1"]
    update2 = make_update(1)
    run(h.outbox_status(update2, ctx))
    out2 = update2.message.replies[-1]
    assert "creation:1" in out2 and "creation-err" in out2
    assert "prompt-err" not in out2


def test_discard_collision_mutates_only_selected(tmp_path):
    ctx = make_ctx(tmp_path)
    db, pid, cid = _seed_collision(ctx)
    db.set_outbox_status(pid, "unknown", "t")
    db.set_creation_status(cid, "unknown", "t")

    ctx.args = ["prompt:1", "confirm"]
    run(h.outbox_discard(make_update(1), ctx))
    assert db.get_outbox(pid).status == "discarded"   # البرومت بس
    assert db.get_creation_job(cid).status == "unknown"  # الشات ماتغيرش

    ctx.args = ["creation:1", "confirm"]
    run(h.outbox_discard(make_update(1), ctx))
    assert db.get_creation_job(cid).status == "discarded"
    assert db.get_outbox(pid).status == "discarded"


def test_mark_sent_collision_mutates_only_selected(tmp_path):
    ctx = make_ctx(tmp_path)
    db, pid, cid = _seed_collision(ctx)
    db.set_outbox_status(pid, "unknown", "t")
    db.set_creation_status(cid, "unknown", "t")

    ctx.args = ["creation:1", "confirm"]
    run(h.outbox_mark_sent(make_update(1), ctx))
    assert db.get_creation_job(cid).status == "done"   # الشات بس
    assert db.get_outbox(pid).status == "unknown"      # البرومت ماتغيرش

    ctx.args = ["prompt:1", "confirm"]
    run(h.outbox_mark_sent(make_update(1), ctx))
    assert db.get_outbox(pid).status == "sent"
    assert db.get_creation_job(cid).status == "done"


def test_bare_numeric_ref_fails_closed_with_collision(tmp_path):
    # معرّف مجرّد "1" غامض (موجود في الجدولين) ⇒ مرفوض من غير أي تغيير.
    ctx = make_ctx(tmp_path)
    db, pid, cid = _seed_collision(ctx)
    db.set_outbox_status(pid, "unknown", "t")
    db.set_creation_status(cid, "unknown", "t")
    for fn in (h.outbox_status, h.outbox_discard, h.outbox_mark_sent):
        ctx.args = ["1", "confirm"]
        update = make_update(1)
        run(fn(update, ctx))
        assert "استخدام" in update.message.replies[-1]
    assert db.get_outbox(pid).status == "unknown"
    assert db.get_creation_job(cid).status == "unknown"


def test_missing_ref_type_fails_closed(tmp_path):
    # "creation:" بدون رقم ⇒ مرجع غير صالح ⇒ مرفوض بلا تغيير في أي جدول.
    ctx = make_ctx(tmp_path)
    db, pid, cid = _seed_collision(ctx)
    ctx.args = ["creation:", "confirm"]
    update = make_update(1)
    run(h.outbox_discard(update, ctx))
    assert "استخدام" in update.message.replies[-1]
    assert db.get_creation_job(cid).status == "pending"
    assert db.get_outbox(pid).status == "pending"


# ------------------------------------------------------------ never auto-resubmit
class SendClient:
    def __init__(self):
        self.sent = []

    async def get_conversations(self, ids):
        return [{"id": "c1", "sandbox_status": "RUNNING", "execution_status": "running"}]

    async def resume_sandbox(self, sandbox_id):
        pass

    async def send_message(self, conversation_id, text):
        self.sent.append((conversation_id, text))


def test_unknown_record_never_resubmitted_by_worker(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    oid = db.add_outbox("c1", 99, SECRET, "t")
    db.set_outbox_status(oid, "unknown", "t")
    client = SendClient()
    worker = OutboxWorker(client, db, ctx.bot)
    asyncio.run(worker._tick())
    asyncio.run(worker._tick())
    assert client.sent == []  # 'unknown' مش مؤهّل ⇒ مفيش إرسال
    assert db.get_outbox(oid).status == "unknown"


def test_mark_sent_then_worker_never_resubmits(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    oid = db.add_outbox("c1", 99, SECRET, "t")
    db.set_outbox_status(oid, "unknown", "t")
    ctx.args = ["prompt:1", "confirm"]
    run(h.outbox_mark_sent(make_update(1), ctx))
    client = SendClient()
    worker = OutboxWorker(client, db, ctx.bot)
    asyncio.run(worker._tick())
    assert client.sent == []
    assert db.get_outbox(oid).status == "sent"


def test_discard_never_resubmits(tmp_path):
    ctx = make_ctx(tmp_path)
    db = ctx.bot_data["db"]
    oid = db.add_outbox("c1", 99, SECRET, "t")
    db.set_outbox_status(oid, "unknown", "t")
    ctx.args = ["prompt:1", "confirm"]
    run(h.outbox_discard(make_update(1), ctx))
    client = SendClient()
    worker = OutboxWorker(client, db, ctx.bot)
    asyncio.run(worker._tick())
    assert client.sent == []
    assert db.get_outbox(oid).status == "discarded"
