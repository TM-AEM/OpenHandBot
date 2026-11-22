"""OHB2-PERSISTENT-READY-STATE-AND-STICKY-CONVERSATION-ROUTING.

Deterministic tests: fake OpenHands clients, temp SQLite, no real waits or network.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from telegram.ext import CommandHandler

import bot.handlers as h
from bot import outbox
from bot.app import build_application
from bot.db import AWAITING_TTL, Database
from bot.errors import ApiError
from tests.test_4b import OpenClient, Q, cb_update
from tests.test_app import make_config
from tests.test_handlers import make_context, make_update

OWNER = 1
OTHER = 2


def _aged(minutes: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


def _open(ctx, conversation_id: str, *, title: str = "شات") -> None:
    ctx.bot_data["client"] = OpenClient(
        {"id": conversation_id, "title": title, "execution_status": "finished"}
    )
    asyncio.run(h.open_conversation(cb_update(Q(f"open:{conversation_id}")), ctx))


def _send(ctx, text: str, user_id: int = OWNER):
    update = make_update(user_id, text)
    asyncio.run(h.handle_text(update, ctx))
    return update


def _pending(ctx):
    return ctx.bot_data["db"].list_outbox_by_status("pending")


class _AllowBoth:
    allowed_telegram_ids = frozenset({OWNER, OTHER})
    owner_id = OWNER
    openhands_base_url = "https://app.all-hands.dev"

    def is_allowed(self, user_id):
        return user_id in self.allowed_telegram_ids


class _FailingClient(OpenClient):
    def __init__(self, status_code):
        super().__init__({"id": "A", "title": "A", "execution_status": "finished"})
        self.status_code = status_code

    async def get_conversations(self, ids):
        raise ApiError("upstream unavailable", self.status_code)


# ---------------------------------------------------------------- readiness
def test_message_immediately_after_open_routes_to_opened_conversation(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    update = _send(ctx, "أول رسالة")

    items = _pending(ctx)
    assert len(items) == 1
    assert items[0].conversation_id == "A"
    assert update.message.replies == ["وصل ✅ ← «شات» — تم حفظ طلبك، ولسه هيتبعت."]


def test_message_after_more_than_ten_minutes_routes_without_start(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, "A")
    db.set_awaiting(OWNER, "A", "route", title="A", now=_aged(31))

    _send(ctx, "بعد فترة طويلة")

    assert [i.conversation_id for i in _pending(ctx)] == ["A"]


def test_message_after_more_than_ten_minutes_routes_without_chat_command(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, "A")
    # لا route ولا /chat ولا /start: الهدف المحفوظ وحده كافٍ.
    db.clear_awaiting(OWNER)

    _send(ctx, "بدون أوامر")

    assert [i.conversation_id for i in _pending(ctx)] == ["A"]


def test_route_survives_database_reopen_and_process_restart(tmp_path):
    db_path = str(tmp_path / "restart.sqlite3")
    db = Database(db_path)
    db.set_last_accessed_conversation(OWNER, "A")
    db.set_awaiting(OWNER, "A", "route", title="A", now=_aged(40))
    db.close()

    ctx = make_context(OWNER, tmp_path)
    reopened = Database(db_path)
    ctx.bot_data["db"] = reopened
    try:
        _send(ctx, "بعد إعادة التشغيل")
        assert [i.conversation_id for i in _pending(ctx)] == ["A"]
    finally:
        reopened.close()


def test_route_has_no_hidden_expiry_in_take_awaiting(tmp_path):
    db = Database(str(tmp_path / "route.sqlite3"))
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    db.set_awaiting(OWNER, "A", "route", title="A", now=t0)

    conv, kind, _ = db.take_awaiting(OWNER, now=t0 + timedelta(hours=24))

    assert (conv, kind) == ("A", "route")
    assert AWAITING_TTL == timedelta(minutes=10)  # ما زالت مستخدمة للحالات لمرة واحدة


# ------------------------------------------------------- sticky selection
def test_open_a_then_send_goes_to_a(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    _send(ctx, "إلى A")

    assert [i.conversation_id for i in _pending(ctx)] == ["A"]
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "A"


def test_inactivity_does_not_change_selected_target(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    _send(ctx, "قبل الانتظار")
    ctx.bot_data["db"].set_awaiting(OWNER, "A", "route", title="A", now=_aged(90))
    _send(ctx, "بعد الانتظار")

    rows = _pending(ctx)
    assert len(rows) == 1
    assert rows[0].conversation_id == "A"
    assert rows[0].text == "قبل الانتظار\nبعد الانتظار"
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "A"


def test_open_b_changes_default_target_for_later_messages(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    _send(ctx, "إلى A")
    _open(ctx, "B")
    _send(ctx, "إلى B")

    assert [i.conversation_id for i in _pending(ctx)] == ["A", "B"]
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "B"


def test_sending_does_not_silently_change_selected_target(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    for text in ("واحد", "اتنين", "تلاتة"):
        _send(ctx, text)

    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "A"
    rows = _pending(ctx)
    assert len(rows) == 1
    assert rows[0].conversation_id == "A"
    assert rows[0].text == "واحد\nاتنين\nتلاتة"


def test_last_accessed_is_isolated_per_telegram_user(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["config"] = _AllowBoth()
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, "A")
    db.set_last_accessed_conversation(OTHER, "B")

    _send(ctx, "للمالك", user_id=OWNER)
    _send(ctx, "للمستخدم التاني", user_id=OTHER)

    items = _pending(ctx)
    assert {i.conversation_id for i in items} == {"A", "B"}
    assert db.get_last_accessed_conversation(OWNER) == "A"
    assert db.get_last_accessed_conversation(OTHER) == "B"


def test_no_target_returns_clear_explanation_and_creates_nothing(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    update = _send(ctx, "رسالة بدون هدف")

    assert _pending(ctx) == []
    assert ctx.bot_data["db"].count_creation_jobs() == 0
    assert "مفيش شات محدد" in update.message.replies[0]
    assert "/start" in update.message.replies[0] or "/chat" in update.message.replies[0]


def test_confirmed_deleted_target_is_cleared_without_fallback(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    ctx.bot_data["db"].delete_conversation(
        "A", outbox.now_iso(), remote_confirmed=True
    )

    update = _send(ctx, "بعد الحذف")

    db = ctx.bot_data["db"]
    assert _pending(ctx) == []
    assert db.get_last_accessed_conversation(OWNER) is None
    assert db.get_awaiting(OWNER) == (None, None)
    assert "اتحذف" in update.message.replies[0]


@pytest.mark.parametrize("status_code", [503, 429, None])
def test_transient_upstream_errors_do_not_clear_selected_target(tmp_path, status_code):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, "A")
    ctx.bot_data["client"] = _FailingClient(status_code)

    with pytest.raises(ApiError):
        asyncio.run(h.open_conversation(cb_update(Q("open:A")), ctx))

    assert db.get_last_accessed_conversation(OWNER) == "A"


class _OutboxClient:
    def __init__(
        self, *, empty=False, get_error=None, send_error=None,
        sandbox_status="RUNNING", resume_error=None,
    ):
        self.empty = empty
        self.get_error = get_error
        self.send_error = send_error
        self.sandbox_status = sandbox_status
        self.resume_error = resume_error
        self.resume_calls = []
        self.sent = []

    async def get_conversations(self, ids):
        if self.get_error is not None:
            raise self.get_error
        if self.empty:
            return []
        return [{
            "id": "A", "title": "A", "execution_status": "running",
            "sandbox_status": self.sandbox_status,
            "sandbox_id": "sandbox-A",
        }]

    async def resume_sandbox(self, sandbox_id):
        self.resume_calls.append(sandbox_id)
        if self.resume_error is not None:
            raise self.resume_error

    async def send_message(self, conversation_id, text):
        if self.send_error is not None:
            raise self.send_error
        self.sent.append((conversation_id, text))


class _OutboxBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


def _claimed_outbox(db):
    db.add_outbox("A", OWNER, "برومت", outbox.now_iso())
    claimed = db.claim_outbox(outbox.now_iso())
    assert claimed is not None
    return claimed


def _prepare_unavailable_case(tmp_path):
    db = Database(str(tmp_path / "outbox.sqlite3"))
    db.set_last_accessed_conversation(OWNER, "A")
    db.set_awaiting(OWNER, "A", "route", title="A")
    return db, _claimed_outbox(db), _OutboxBot()


def test_outbox_confirmed_404_target_fails_without_fallback(tmp_path):
    db, item, bot = _prepare_unavailable_case(tmp_path)
    client = _OutboxClient(get_error=ApiError("missing", 404))

    asyncio.run(outbox._post_claimed(client, db, bot, item))

    assert db.get_outbox(item.id).status == outbox.OUTBOX_FAILED
    assert db.get_last_accessed_conversation(OWNER) is None
    assert db.get_awaiting(OWNER) == (None, None)
    assert outbox._TARGET_UNAVAILABLE_NOTICE in bot.sent
    assert client.sent == []


def test_outbox_empty_metadata_is_ambiguous_and_preserves_target(tmp_path):
    db, item, bot = _prepare_unavailable_case(tmp_path)
    client = _OutboxClient(empty=True)

    asyncio.run(outbox._post_claimed(client, db, bot, item))

    assert db.get_outbox(item.id).status == outbox.OUTBOX_PENDING
    assert db.get_last_accessed_conversation(OWNER) == "A"
    assert db.get_awaiting(OWNER) == ("A", "route")
    assert outbox._TARGET_UNCERTAIN_NOTICE in bot.sent
    assert client.sent == []


def test_outbox_sandbox_resume_404_is_not_conversation_deletion(tmp_path):
    db, item, bot = _prepare_unavailable_case(tmp_path)
    client = _OutboxClient(
        sandbox_status="STOPPED",
        resume_error=ApiError("sandbox missing", 404),
    )

    asyncio.run(outbox._post_claimed(client, db, bot, item))

    assert db.get_outbox(item.id).status == outbox.OUTBOX_PENDING
    assert db.get_last_accessed_conversation(OWNER) == "A"
    assert db.get_awaiting(OWNER) == ("A", "route")
    assert outbox._TARGET_UNAVAILABLE_NOTICE not in bot.sent
    assert client.resume_calls == ["sandbox-A"]
    assert client.sent == []


def test_outbox_transient_error_preserves_target_and_retries_safely(tmp_path):
    db, item, bot = _prepare_unavailable_case(tmp_path)
    client = _OutboxClient(get_error=ApiError("temporary", 503))

    asyncio.run(outbox._post_claimed(client, db, bot, item))

    assert db.get_outbox(item.id).status == outbox.OUTBOX_PENDING
    assert db.get_last_accessed_conversation(OWNER) == "A"
    assert db.get_awaiting(OWNER) == ("A", "route")
    assert client.sent == []


def test_outbox_404_after_post_does_not_fallback(tmp_path):
    db, item, bot = _prepare_unavailable_case(tmp_path)
    client = _OutboxClient(send_error=ApiError("missing after CAS", 404))

    asyncio.run(outbox._post_claimed(client, db, bot, item))

    assert db.get_outbox(item.id).status == outbox.OUTBOX_FAILED
    assert db.get_last_accessed_conversation(OWNER) is None
    assert outbox._TARGET_UNAVAILABLE_NOTICE in bot.sent


# ------------------------------------------------------------ path coverage
def test_ordinary_text_follows_selected_target(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    _send(ctx, "نص عادي")

    assert [i.conversation_id for i in _pending(ctx)] == ["A"]


def test_existing_prompt_submission_path_follows_selected_target(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    update = make_update(OWNER, "برومت عبر المسار الحالي")
    update.message.message_id = 501

    asyncio.run(h.handle_text(update, ctx))

    items = _pending(ctx)
    assert [i.conversation_id for i in items] == ["A"]
    assert items[0].telegram_message_ids == (501,)


def test_expired_reply_state_falls_back_to_persisted_target(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, "A")
    db.set_awaiting(OWNER, "A", "reply", now=_aged(30))

    _send(ctx, "رد متأخر")

    assert [i.conversation_id for i in _pending(ctx)] == ["A"]


def test_persisted_target_is_authoritative_over_stale_route(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, "B")
    db.set_awaiting(OWNER, "A", "route", title="A")

    _send(ctx, "يجب أن يذهب إلى B")

    assert [i.conversation_id for i in _pending(ctx)] == ["B"]
    assert db.get_awaiting(OWNER) == ("B", "route")


def test_commands_remain_registered_as_commands(tmp_path):
    app = build_application(make_config(tmp_path))
    commands = {
        command
        for group in app.handlers.values()
        for handler in group
        if isinstance(handler, CommandHandler)
        for command in handler.commands
    }
    assert {"start", "chat", "help"} <= commands


def test_rapid_messages_group_into_one_outbox_batch(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    for text in ("سريع 1", "سريع 2", "سريع 3"):
        _send(ctx, text)

    items = _pending(ctx)
    assert len(items) == 1
    assert items[0].conversation_id == "A"
    assert items[0].text == "سريع 1\nسريع 2\nسريع 3"


# ------------------------------------------------------- command compatibility
def test_chat_opens_last_accessed_without_prompt_or_creation(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    before = ctx.bot_data["db"].count_outbox()
    update = make_update(OWNER, "/chat")

    asyncio.run(h.chat(update, ctx))

    assert ctx.bot_data["db"].count_outbox() == before
    assert ctx.bot_data["db"].count_creation_jobs() == 0
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "A"
    assert update.message.replies


def test_cancel_pauses_default_routing_until_chat_reopens(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    asyncio.run(h.cancel_route(make_update(OWNER, "/cancel"), ctx))
    paused = _send(ctx, "بعد الإلغاء")

    assert _pending(ctx) == []
    assert "التوجيه متوقف" in paused.message.replies[0]
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "A"

    asyncio.run(h.chat(make_update(OWNER, "/chat"), ctx))
    _send(ctx, "بعد إعادة الفتح")

    assert [i.conversation_id for i in _pending(ctx)] == ["A"]


def test_start_is_not_required_after_inactivity(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    asyncio.run(h.start(make_update(OWNER, "/start"), ctx))
    assert ctx.bot_data["db"].get_awaiting(OWNER) == (None, None)

    _send(ctx, "بعد /start")

    assert [i.conversation_id for i in _pending(ctx)] == ["A"]
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "A"


def test_outbox_empty_metadata_exhaustion_fails_without_clearing_target(tmp_path):
    db, item, bot = _prepare_unavailable_case(tmp_path)
    client = _OutboxClient(empty=True)

    claimed = item
    for _ in range(outbox.MAX_OUTBOX_ATTEMPTS):
        assert claimed is not None and claimed.id == item.id
        asyncio.run(outbox._post_claimed(client, db, bot, claimed))
        claimed = db.claim_outbox(outbox.now_iso())

    assert db.get_outbox(item.id).status == outbox.OUTBOX_FAILED
    assert db.get_last_accessed_conversation(OWNER) == "A"
    assert db.get_awaiting(OWNER) == ("A", "route")
    assert outbox._TARGET_UNAVAILABLE_NOTICE not in bot.sent
    assert client.sent == []
