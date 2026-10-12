"""المرحلة 4B: الأسرار، المحادثات الخاصة، callback_data، انتهاء/إلغاء التوجيه."""
import asyncio
import io
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

import bot.handlers as h
import bot.keyboards as kb
from bot.config import ConfigError, load_config
from bot.db import AWAITING_TTL, Database
from bot.errors import ApiError, RedactingFilter, clear_secrets, error_text, register_secrets
from bot.openhands_client import OpenHandsClient
from bot.watcher import Watcher

from tests.test_handlers import make_context, make_update

TOKEN = "123456:ABCdef-ghiJKL_mnoPQR"
KEY = "sk-oh-test-key-123456"


@pytest.fixture(autouse=True)
def _reset_secrets():
    clear_secrets()
    yield
    clear_secrets()


def env(**over):
    base = {"TELEGRAM_BOT_TOKEN": TOKEN, "OPENHANDS_API_KEY": KEY, "ALLOWED_TELEGRAM_ID": "1"}
    base.update(over)
    return base


# ------------------------------------------------------------------- الأسرار
def test_secrets_with_whitespace_and_quotes_are_normalized():
    cfg = load_config(env(TELEGRAM_BOT_TOKEN=f"  {TOKEN} \n", OPENHANDS_API_KEY=f'"{KEY}"\r\n'))
    assert cfg.telegram_bot_token == TOKEN
    assert cfg.openhands_api_key == KEY
    assert cfg.secrets == (TOKEN, KEY)


@pytest.mark.parametrize(
    "over",
    [
        {"TELEGRAM_BOT_TOKEN": "not-a-token-SECRETVALUE"},
        {"OPENHANDS_API_KEY": "has space SECRETVALUE"},
        {"OPENHANDS_API_KEY": "short"},
        {"ALLOWED_TELEGRAM_ID": "SECRETVALUE"},
        {"ALLOWED_TELEGRAM_ID": "-5"},
        {"WATCHER_INTERVAL": "SECRETVALUE"},
        {"WATCHER_INTERVAL": "0"},
        {"WATCHER_INTERVAL": "2"},
        {"WATCHER_INTERVAL": "999999"},
        {"OPENHANDS_BASE_URL": "ftp://SECRETVALUE"},
        {"LOG_LEVEL": "SECRETVALUE"},
    ],
)
def test_malformed_config_fails_clearly_without_echoing_value(over):
    with pytest.raises(ConfigError) as info:
        load_config(env(**over))
    assert "SECRETVALUE" not in str(info.value)
    assert TOKEN not in str(info.value) and KEY not in str(info.value)


def test_config_repr_hides_secrets():
    cfg = load_config(env())
    assert TOKEN not in repr(cfg) and KEY not in repr(cfg)


def test_watcher_interval_validated_at_startup():
    with pytest.raises(ValueError):
        Watcher(None, None, None, chat_id=1, interval=0)
    with pytest.raises(ValueError):
        Watcher(None, None, None, chat_id=1, interval=-3)


def _logged(*calls):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger("test.secrets")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for call in calls:
        call(logger)
    return stream.getvalue()


def test_secrets_never_appear_in_logs_even_with_trailing_whitespace():
    cfg = load_config(env(TELEGRAM_BOT_TOKEN=TOKEN + "  \n", OPENHANDS_API_KEY=KEY + "\t"))
    register_secrets(*cfg.secrets)

    def boom(logger):
        try:
            raise RuntimeError(f"failed with {KEY} at https://api.telegram.org/bot{TOKEN}/getUpdates")
        except RuntimeError:
            logger.exception("خطأ %s", TOKEN)
        logger.warning("مفتاح: %s", KEY)

    out = _logged(boom)
    assert TOKEN not in out and KEY not in out
    assert "RuntimeError" in out  # النوع بس


def test_api_error_and_user_text_redact_secrets():
    register_secrets(TOKEN, KEY)
    err = ApiError(f"server said {KEY}", 500)
    assert KEY not in str(err) and "***" in str(err)
    assert KEY not in error_text(err)
    assert KEY not in error_text(RuntimeError(f"raw {KEY}"))  # غير ApiError: نص عام


def test_client_network_error_does_not_expose_raw_exception_text():
    register_secrets(KEY)

    def handler(request):
        raise httpx.ConnectError(f"boom {KEY}")

    async def go():
        client = OpenHandsClient("https://x.test", KEY, transport=httpx.MockTransport(handler))
        try:
            await client.get_conversations(["c1"])
        finally:
            await client.aclose()

    with pytest.raises(ApiError) as info:
        asyncio.run(go())
    assert KEY not in str(info.value) and "ConnectError" in str(info.value)


class Q:
    """CallbackQuery fake بيحتفظ بالـ markup."""

    def __init__(self, data):
        self.data = data
        self.edits = []
        self.markups = []
        self.message = SimpleNamespace(chat_id=99)

    async def answer(self):
        pass

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


def test_api_error_shown_to_user_has_no_secret(tmp_path):
    register_secrets(KEY)

    class C:
        async def search_conversations(self, limit=100):
            raise ApiError(f"fail {KEY}", 500)

    ctx = make_context(1, tmp_path, client=C())
    q = Q("list:0")
    asyncio.run(h.list_conversations(cb_update(q), ctx))
    assert q.edits and KEY not in q.edits[0]


# ------------------------------------------------------- محادثات خاصة فقط
def test_allowed_user_in_group_is_ignored_for_text(tmp_path):
    ctx = make_context(1, tmp_path)
    ctx.bot_data["db"].set_awaiting(1, "conv-A", "reply")
    update = make_update(1, "برومت")
    update.effective_chat.type = "group"
    asyncio.run(h.handle_text(update, ctx))
    assert update.message.replies == []
    assert ctx.bot_data["db"].count_outbox() == 0
    assert ctx.bot_data["db"].get_awaiting(1) == ("conv-A", "reply")  # ما اتلمسش


@pytest.mark.parametrize("chat_type", ["group", "supergroup", "channel", None])
def test_callbacks_from_non_private_chats_are_ignored(tmp_path, chat_type):
    ctx = make_context(1, tmp_path)
    q = Q("menu")
    asyncio.run(h.show_menu(cb_update(q, chat_type=chat_type), ctx))
    assert q.edits == []


def test_private_chat_still_works(tmp_path):
    ctx = make_context(1, tmp_path)
    q = Q("menu")
    asyncio.run(h.show_menu(cb_update(q), ctx))
    assert q.edits


def test_unauthorized_user_in_private_chat_is_ignored(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(555, "x")
    asyncio.run(h.handle_text(update, ctx))
    assert update.message.replies == []


class Bot:
    def __init__(self):
        self.chat_ids = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.chat_ids.append(chat_id)


def test_watcher_never_notifies_a_group_destination(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "t", chat_id=-100999)  # شات متابَع محفوظ له جروب
    db.set_last_state("c1", "running")

    class C:
        async def get_conversations(self, ids):
            return [{"id": "c1", "title": "t", "execution_status": "finished"}]

        async def get_last_reply(self, cid):
            return "تم"

    bot = Bot()
    asyncio.run(Watcher(C(), db, bot, chat_id=1, allowed_chats={1}).tick())
    assert bot.chat_ids == [1]


# --------------------------------------------------------- callback_data
LONG_REPO = "very-long-organization-name-" * 4 + "/" + "ريبو-طويل-جداً-" * 8


def test_button_helper_rejects_oversized_callback_data():
    with pytest.raises(ValueError):
        kb._btn("x", "a" * 65)
    kb._btn("x", "a" * 64)  # الحد نفسه مقبول
    with pytest.raises(ValueError):
        kb._btn("x", "ش" * 33)  # 66 بايت UTF-8


def test_repositories_menu_callbacks_never_exceed_limit_for_long_unicode_names():
    items = [{"full_name": LONG_REPO} for _ in range(8)]
    cbs = callbacks(kb.repositories_menu(items, page=11, has_more=True, gen=123456, start=88))
    assert cbs and all(len(cb.encode("utf-8")) <= 64 for cb in cbs)
    assert not any(LONG_REPO in cb for cb in cbs)


def test_conversation_menus_stay_within_limit_for_uuid_ids():
    cid = "123e4567-e89b-12d3-a456-426614174000"
    for markup in (
        kb.conversation_actions(cid, True),
        kb.conversation_actions(cid, False),
        kb.files_menu(cid, ["a.py"] * 10, start=990, page=99, has_more=True),
    ):
        assert all(len(cb.encode("utf-8")) <= 64 for cb in callbacks(markup))


class RepoClient:
    def __init__(self, repos):
        self._repos = repos
        self.queries = []

    async def search_repositories(self, query="", limit=100):
        self.queries.append(query)
        return self._repos


def _shown(ctx, q, page=0, query=""):
    asyncio.run(h._show_repos(q, ctx, page=page, query=query, user_id=1))


def test_pick_repo_resolves_full_name_server_side(tmp_path):
    repos = [{"full_name": LONG_REPO}, {"full_name": "a/b"}]
    ctx = make_context(1, tmp_path, client=RepoClient(repos))
    q = Q("x")
    _shown(ctx, q)
    cbs = callbacks(q.markups[-1])
    pick = [c for c in cbs if c.startswith("pickrepo:")]
    assert all(len(c.encode()) <= 64 for c in cbs)

    q2 = Q(pick[0])
    asyncio.run(h.pick_repo(cb_update(q2), ctx))
    assert ctx.bot_data["db"].get_awaiting(1) == (LONG_REPO, "newchat")


def test_stale_repo_buttons_are_ignored_safely(tmp_path):
    repos = [{"full_name": "a/b"}, {"full_name": "c/d"}]
    ctx = make_context(1, tmp_path, client=RepoClient(repos))
    q = Q("x")
    _shown(ctx, q)
    old_pick = [c for c in callbacks(q.markups[-1]) if c.startswith("pickrepo:")][1]  # c/d
    _shown(ctx, Q("x"))  # قايمة جديدة ⇒ نسخة جديدة

    q2 = Q(old_pick)
    asyncio.run(h.pick_repo(cb_update(q2), ctx))
    assert ctx.bot_data["db"].get_awaiting(1) == (None, None)  # مش اتحدد مستودع غلط
    assert "انتهت" in q2.edits[0]


@pytest.mark.parametrize("data", ["pickrepo:1:99", "pickrepo:abc", "pickrepo:", "pickrepo:1:-1", "repos:x:y"])
def test_malformed_or_out_of_range_repo_callbacks_are_safe(tmp_path, data):
    ctx = make_context(1, tmp_path, client=RepoClient([{"full_name": "a/b"}]))
    _shown(ctx, Q("x"))
    q = Q(data)
    handler = h.repos_page if data.startswith("repos") else h.pick_repo
    asyncio.run(handler(cb_update(q), ctx))
    assert ctx.bot_data["db"].get_awaiting(1) == (None, None)


def test_unicode_search_query_stays_server_side_and_paginates(tmp_path):
    query = "مستودع-" * 30
    repos = [{"full_name": f"o/r{i}"} for i in range(20)]
    client = RepoClient(repos)
    ctx = make_context(1, tmp_path, client=client)
    q = Q("x")
    _shown(ctx, q, query=query)
    cbs = callbacks(q.markups[-1])
    assert all(len(c.encode("utf-8")) <= 64 for c in cbs)
    nxt = [c for c in cbs if c.startswith("repos:")]
    assert nxt

    q2 = Q(nxt[0])
    asyncio.run(h.repos_page(cb_update(q2), ctx))
    assert client.queries[-1] == query  # البحث اتسترجع من حالة السيرفر
    assert all(len(c.encode("utf-8")) <= 64 for c in callbacks(q2.markups[-1]))


# ------------------------------------------------ انتهاء/إلغاء حالة التوجيه
def aged(minutes):
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


def test_expired_one_shot_state_cannot_redirect_later_message(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "conv-A", "reply", now=aged(11))
    update = make_update(1, "رسالة متأخرة")

    asyncio.run(h.handle_text(update, ctx))

    assert db.count_outbox() == 0  # ما اتبعتتش لأي شات
    assert "انتهت مهلة" in update.message.replies[0]
    assert db.get_awaiting(1) == (None, None)
    # الرسالة اللي بعدها كمان ما بتتوجّهش
    update2 = make_update(1, "تاني")
    asyncio.run(h.handle_text(update2, ctx))
    assert db.count_outbox() == 0


def test_expired_newchat_state_does_not_create_chat(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "o/r", "newchat", now=aged(30))
    asyncio.run(h.handle_text(make_update(1, "x"), ctx))
    assert db.list_open_creation_jobs() == []


def test_state_within_ttl_still_works(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "conv-A", "reply", now=aged(9))
    asyncio.run(h.handle_text(make_update(1, "x"), ctx))
    assert db.count_outbox("pending") == 1


def test_ttl_is_ten_minutes():
    assert AWAITING_TTL == timedelta(minutes=10)


def test_route_is_sticky_refreshes_and_shows_chat_name(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "conv-A", "route", title="مشروع الموقع", now=aged(8))

    u1 = make_update(1, "أول")
    asyncio.run(h.handle_text(u1, ctx))
    u2 = make_update(1, "تاني")
    asyncio.run(h.handle_text(u2, ctx))

    assert [i.conversation_id for i in db.list_outbox_by_status("pending")] == ["conv-A", "conv-A"]
    assert "مشروع الموقع" in u1.message.replies[0]  # اسم الشات المستهدف ظاهر
    assert db.get_awaiting(1) == ("conv-A", "route")  # لسه شغال (اتجدّد وقته)


def test_route_expires_after_ten_minutes_of_inactivity(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "conv-A", "route", title="t", now=aged(10) - timedelta(seconds=5))
    update = make_update(1, "متأخر")
    asyncio.run(h.handle_text(update, ctx))
    assert db.count_outbox() == 0
    assert "انتهت مهلة" in update.message.replies[0]


def test_route_with_activity_does_not_expire_while_in_use(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    t0 = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
    db.set_awaiting(1, "A", "route", title="t", now=t0)
    for minutes in (6, 12, 18, 24):  # كل رسالة بعد 6 دقايق من اللي قبلها
        conv, kind, _ = db.take_awaiting(1, now=t0 + timedelta(minutes=minutes))
        assert (conv, kind) == ("A", "route")
    assert db.take_awaiting(1, now=t0 + timedelta(minutes=40))[1] == "expired"


def test_cancel_command_and_button_clear_route(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "conv-A", "route", title="t")
    update = make_update(1, "/cancel")
    asyncio.run(h.cancel_route(update, ctx))
    assert db.get_awaiting(1) == (None, None)
    assert "اتلغى" in update.message.replies[0]

    db.set_awaiting(1, "conv-A", "route", title="t")
    asyncio.run(h.cancel_route_button(cb_update(Q("cancelroute")), ctx))
    assert db.get_awaiting(1) == (None, None)
    follow = make_update(1, "بعد الإلغاء")
    asyncio.run(h.handle_text(follow, ctx))
    assert db.count_outbox() == 0


def test_cancel_ignored_for_non_private_or_unauthorized(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "conv-A", "route", title="t")
    update = make_update(999, "/cancel")
    asyncio.run(h.cancel_route(update, ctx))
    assert db.get_awaiting(1) == ("conv-A", "route")


def test_navigation_clears_pending_state(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "conv-A", "route", title="t")
    asyncio.run(h.show_menu(cb_update(Q("menu")), ctx))
    assert db.get_awaiting(1) == (None, None)


def test_start_command_clears_pending_state(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "conv-A", "reply")
    asyncio.run(h.start(make_update(1, "/start"), ctx))
    assert db.get_awaiting(1) == (None, None)


class OpenClient:
    def __init__(self, conv):
        self._conv = conv

    async def get_conversations(self, ids):
        return [self._conv]

    async def get_last_reply(self, cid):
        return "رد"


def test_opening_a_chat_routes_following_messages_to_it_and_replaces_previous(tmp_path):
    client = OpenClient({"id": "A", "title": "شات A", "execution_status": "finished"})
    ctx = make_context(1, tmp_path, client=client)
    db = ctx.bot_data["db"]

    q = Q("open:A")
    asyncio.run(h.open_conversation(cb_update(q), ctx))
    assert db.get_awaiting(1) == ("A", "route")
    assert "10 دقايق" in q.edits[0] or "10 دقايق" in "".join(q.edits)

    ctx.bot_data["client"] = OpenClient({"id": "B", "title": "شات B", "execution_status": "finished"})
    asyncio.run(h.open_conversation(cb_update(Q("open:B")), ctx))
    asyncio.run(h.handle_text(make_update(1, "للشات B"), ctx))

    assert [i.conversation_id for i in db.list_outbox_by_status("pending")] == ["B"]


def test_concurrent_messages_on_route_all_reach_the_same_chat(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "A", "route", title="t")
    updates = [make_update(1, f"m{i}") for i in range(10)]

    async def go():
        await asyncio.gather(*(h.handle_text(u, ctx) for u in updates))

    asyncio.run(go())
    assert {i.conversation_id for i in db.list_outbox_by_status("pending")} == {"A"}
    assert db.count_outbox("pending") == 10


# =====================================================================
# TASK 04B-2 — U40: صمود فتح الشات ضد ردود غير صالحة/تعديل تيليجرام فاشل
# =====================================================================
from telegram.error import BadRequest, TelegramError  # noqa: E402


class OpenFlowClient:
    """عميل فتح شات: conversation + آخر رد، مع عدّادات نداءات ومسارات خطأ/تعليق."""

    def __init__(self, conv, reply="رد", *, list_calls=None, open_error=None,
                 reply_error=None, hang=False):
        self._conv = conv
        self._reply = reply
        self._list_calls = list_calls if list_calls is not None else []
        self._open_error = open_error
        self._reply_error = reply_error
        self._hang = hang

    async def get_conversations(self, ids):
        self._list_calls.append(list(ids))
        if self._hang:
            await asyncio.Event().wait()  # تعليق (اختبار المهلة)
        if self._open_error:
            raise self._open_error
        return [self._conv] if self._conv else []

    async def get_last_reply(self, conversation_id):
        if self._reply_error:
            raise self._reply_error
        return self._reply


class FailQuery:
    """CallbackQuery بيحفظ نداءات التعديل ويرمي خطأ تيليجرام متوقّع."""

    def __init__(self, data, edit_error):
        self.data = data
        self.edits = []
        self.message = SimpleNamespace(chat_id=99)
        self._edit_error = edit_error

    async def answer(self):
        pass

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)
        raise self._edit_error


class RecordingBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


def _open_update(q, user_id=1):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type="private"),
        callback_query=q,
        message=None,
    )


CONV = {"id": "A", "title": "شات A", "execution_status": "finished", "selected_repository": "o/r"}


# 1) فتح ناجح: عرض سليم + توجيه صحيح -----------------------------------------
def test_open_success_renders_view_and_activates_route(tmp_path):
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV, reply="آخر رد"))
    q = Q("open:A")
    asyncio.run(h.open_conversation(cb_update(q), ctx))
    assert q.edits and "شات A" in q.edits[0] and "آخر رد" in q.edits[0]
    assert ctx.bot_data["db"].get_awaiting(1) == ("A", "route")


# 2) شات مش موجود: رسالة متوقعة + الحفاظ على التوجيه القائم -------------------
def test_open_missing_returns_message_and_preserves_route(tmp_path):
    ctx = make_context(1, tmp_path, client=OpenFlowClient(None))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = Q("open:missing")
    asyncio.run(h.open_conversation(cb_update(q), ctx))
    assert q.edits == ["الشات مش موجود."]
    assert db.get_awaiting(1) == ("prev", "route")  # ما اتلمسش


# 3) 401/403: فشل آمن بدون تفعيل توجيه غلط -----------------------------------
@pytest.mark.parametrize("code", [401, 403])
def test_open_auth_failures_do_not_activate_route(tmp_path, code):
    err = ApiError(f"auth {code}", code)
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV, open_error=err))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = Q("open:A")
    asyncio.run(h.open_conversation(cb_update(q), ctx))
    assert q.edits == [f"auth {code}"]        # رسالة خطأ آمنة واحدة
    assert db.get_awaiting(1) == ("prev", "route")  # ما اتغيّرش لـ A


# 4) 429/5xx/مهلة/انقطاع: بدون إعادة محاولة تلقائية --------------------------
@pytest.mark.parametrize("exc", [
    ApiError("too many", 429),
    ApiError("server", 500),
    ApiError("gateway", 503),
    ApiError("انتهى الوقت"),          # مهلة: بدون status
    ApiError("تعذّر الاتصال"),        # انقطاع: بدون status
])
def test_open_transient_errors_do_not_retry_and_preserve_state(tmp_path, exc):
    calls = []
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV, open_error=exc, list_calls=calls))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = Q("open:A")
    asyncio.run(h.open_conversation(cb_update(q), ctx))
    assert len(calls) == 1                     # نداء API واحد بالظبط — مفيش retry
    assert db.get_awaiting(1) == ("prev", "route")
    assert db.count_outbox() == 0 and db.list_open_creation_jobs() == []


def test_open_timeout_does_not_retry(tmp_path):
    calls = []
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV, hang=True, list_calls=calls))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = Q("open:A")

    async def go():
        try:
            await asyncio.wait_for(h.open_conversation(cb_update(q), ctx), timeout=0.2)
        except asyncio.TimeoutError:
            pass

    asyncio.run(go())
    assert len(calls) == 1                     # نداء واحد، مفيش محاولة تانية
    assert db.get_awaiting(1) == ("prev", "route")


# 5) JSON غير صالح / شكل غير متوقع: فشل مضبوط مش استثناء خام ------------------
def test_client_invalid_json_raises_apierror():
    def handler(request):
        return httpx.Response(200, content=b"<html>not json</html>")

    async def go():
        client = OpenHandsClient("https://x.test", "k", transport=httpx.MockTransport(handler))
        try:
            return await client.get_conversations(["c1"])
        finally:
            await client.aclose()

    with pytest.raises(ApiError):
        asyncio.run(go())


def test_client_unexpected_shape_raises_apierror():
    def handler(request):
        return httpx.Response(200, json={"unexpected": True})

    async def go():
        client = OpenHandsClient("https://x.test", "k", transport=httpx.MockTransport(handler))
        try:
            return await client.get_conversations(["c1"])
        finally:
            await client.aclose()

    with pytest.raises(ApiError):
        asyncio.run(go())


def test_client_non_dict_entries_are_dropped():
    def handler(request):
        return httpx.Response(200, json=[None, {"id": "c1", "title": "t"}, "bad"])

    async def go():
        client = OpenHandsClient("https://x.test", "k", transport=httpx.MockTransport(handler))
        try:
            return await client.get_conversations(["c1"])
        finally:
            await client.aclose()

    assert asyncio.run(go()) == [{"id": "c1", "title": "t"}]


def test_open_malformed_response_shows_controlled_error_no_route(tmp_path):
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV, open_error=ApiError("رد غير متوقع من OpenHands")))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = Q("open:A")
    asyncio.run(h.open_conversation(cb_update(q), ctx))  # مايرميش JSONDecodeError
    assert q.edits and "غير متوقع" in q.edits[0]
    assert db.get_awaiting(1) == ("prev", "route")


# 6) فشل تعديل تيليجرام متوقّع: مفيش انهيار في الـ callback --------------------
def test_open_edit_failure_is_handled_without_crash(tmp_path):
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV))
    ctx.bot = RecordingBot()
    q = FailQuery("open:A", BadRequest("Message is not modified"))
    asyncio.run(h.open_conversation(_open_update(q), ctx))  # مايرميش
    assert ctx.bot_data["db"].get_awaiting(1) == ("A", "route")  # العرض موجود => التوجيه اتفعّل


def test_open_edit_expired_message_is_handled_without_crash(tmp_path):
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV))
    ctx.bot = RecordingBot()
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = FailQuery("open:A", BadRequest("message to edit not found"))
    asyncio.run(h.open_conversation(_open_update(q), ctx))  # مايرميش
    assert db.get_awaiting(1) == ("prev", "route")  # العرض فشل => مفيش توجيه جديد


# 7) فشل العرض ما يسبش توجيه غير مقصود ---------------------------------------
def test_open_render_failure_leaves_no_route(tmp_path):
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV))
    ctx.bot = RecordingBot()
    q = FailQuery("open:A", TelegramError("boom secret-token-xyz"))
    asyncio.run(h.open_conversation(_open_update(q), ctx))
    assert ctx.bot_data["db"].get_awaiting(1) == (None, None)  # مفيش توجيه جديد


# 8) الفشل ما بيلمسش watched/outbox/creation ---------------------------------
def test_open_failure_preserves_watched_and_does_not_touch_jobs(tmp_path):
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV, open_error=ApiError("server", 500)))
    db = ctx.bot_data["db"]
    db.add_watched("w1", "عنوان", chat_id=99)
    db.set_last_state("w1", "running")
    before = [(w.conversation_id, w.last_state, w.chat_id) for w in db.list_watched()]
    oid = db.add_outbox("c1", 99, "نص", "2026-01-01T00:00:00+00:00")
    job = db.add_creation_job(99, "o/r", "نص", "2026-01-01T00:00:00+00:00")

    q = Q("open:A")
    asyncio.run(h.open_conversation(cb_update(q), ctx))

    after = [(w.conversation_id, w.last_state, w.chat_id) for w in db.list_watched()]
    assert after == before                                   # المتابعة زي ما هي
    assert db.get_outbox(oid).status == "pending"            # مفيش تغيير
    assert db.get_creation_job(job).status == "pending"      # مفيش تغيير
    assert db.get_awaiting(1) == (None, None)


# =====================================================================
# TASK 04B-2R — فروع open_conversation الطرفية: فشل تعديل تيليجرام المتوقّع
# =====================================================================
def test_open_missing_edit_failure_is_handled(tmp_path):
    # شات مش موجود + تعديل الرسالة فشل (رسالة قديمة/مش قابلة للتعديل): مفيش انهيار.
    ctx = make_context(1, tmp_path, client=OpenFlowClient(None))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = FailQuery("open:missing", BadRequest("message to edit not found"))
    asyncio.run(h.open_conversation(_open_update(q), ctx))  # مايرميش
    assert q.edits == ["الشات مش موجود."]        # الرسالة اتجرّبت فعلاً
    assert db.get_awaiting(1) == ("prev", "route")  # التوجيه القائم ما اتلمسش


def test_open_api_error_edit_failure_is_handled(tmp_path):
    # خطأ API (5xx) + تعديل رسالة الخطأ فشل: مفيش انهيار ولا توجيه جديد.
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV, open_error=ApiError("server", 500)))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = FailQuery("open:A", BadRequest("message to edit not found"))
    asyncio.run(h.open_conversation(_open_update(q), ctx))  # مايرميش
    assert q.edits == ["server"]                 # رسالة الخطأ الآمنة اتجرّبت
    assert db.get_awaiting(1) == ("prev", "route")  # ما اتغيّرش لـ A


def test_open_missing_not_modified_is_handled(tmp_path):
    # شات مش موجود + "message is not modified": نتيجة حميدة، مفيش توجيه.
    ctx = make_context(1, tmp_path, client=OpenFlowClient(None))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = FailQuery("open:missing", BadRequest("Message is not modified"))
    asyncio.run(h.open_conversation(_open_update(q), ctx))  # مايرميش
    assert db.get_awaiting(1) == ("prev", "route")


def test_open_api_error_not_modified_is_handled(tmp_path):
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV, open_error=ApiError("x", 500)))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = FailQuery("open:A", BadRequest("Message is not modified"))
    asyncio.run(h.open_conversation(_open_update(q), ctx))  # مايرميش
    assert db.get_awaiting(1) == ("prev", "route")


def test_open_api_error_edit_failure_preserves_all_state(tmp_path):
    # فشل تعديل على مسار خطأ الـ API: التوجيه + المتابعة + الصندوق + الإنشاء ما بيتغيّروش.
    ctx = make_context(1, tmp_path, client=OpenFlowClient(CONV, open_error=ApiError("server", 500)))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    db.add_watched("w1", "عنوان", chat_id=99)
    db.set_last_state("w1", "running")
    before = [(w.conversation_id, w.last_state, w.chat_id) for w in db.list_watched()]
    oid = db.add_outbox("c1", 99, "نص", "2026-01-01T00:00:00+00:00")
    job = db.add_creation_job(99, "o/r", "نص", "2026-01-01T00:00:00+00:00")

    q = FailQuery("open:A", BadRequest("message to edit not found"))
    asyncio.run(h.open_conversation(_open_update(q), ctx))  # مايرميش

    assert db.get_awaiting(1) == ("prev", "route")
    assert [(w.conversation_id, w.last_state, w.chat_id) for w in db.list_watched()] == before
    assert db.get_outbox(oid).status == "pending"
    assert db.get_creation_job(job).status == "pending"


def test_conversation_actions_has_cancel_route_button():
    assert "cancelroute" in callbacks(kb.conversation_actions("c1"))


def test_main_logging_setup_redacts_and_silences_url_loggers():
    import main

    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    try:
        root.handlers = []
        main._setup_logging("INFO", (TOKEN, KEY))
        assert root.handlers and all(
            any(isinstance(f, RedactingFilter) for f in hd.filters) for hd in root.handlers
        )
        # httpx بيسجّل URL كامل (فيه توكن تيليجرام) عند INFO
        assert logging.getLogger("httpx").level >= logging.WARNING
        assert logging.getLogger("httpcore").level >= logging.WARNING
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_level)
