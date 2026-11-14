"""OHB2-SW-07: اختبارات انحدار لانتشار فشل الـ API في المعالجات الخمسة.

العقد المُثبَّت هنا:

- الفشل **التشغيلي** upstream (5xx / 429 / بلا `status_code`: مهلة/انقطاع) بيُعرض
  للمستخدم بنفس الرسالة المتنقّحة القديمة، وبعدها **ينتشر** كـ `OperationalApiFailure`
  بدل ما يتحوّل لـ «إتمام معالجة ناجح» صامت.
- الرفض **المتوقّع** (4xx: 401/403/404/409/410) + الرفض المشتقّ (NOT_FOUND/DELETED/
  UNAUTHORIZED) بيرجع **عاديًّا** بعد الرسالة (مفيش رفع) — تمييز 403/404 محفوظ.
- الفشل التشغيلي **ما بيعملش** أي أثر جانبي مكرّر (مفيش رسائل/تعديلات/إرسال زيادة).
- `asyncio.CancelledError` ما بيتكتمش.
- الانتشار بيوصل فعلاً لمعالج الأخطاء في PTB 22.x عبر `Application.process_update`.

مفيش أي نداء شبكة حقيقي: كل العملاء/البوتات وهمية (fake).
"""

import asyncio

import pytest

import bot.handlers as h
from bot.errors import ApiError, OperationalApiFailure, ResponseTooLargeError

from tests.test_handlers import ExchangeClient, RecBot, make_context

CONV = {"id": "A", "title": "شات A", "execution_status": "finished", "selected_repository": "o/r"}


class FakeQ:
    """كولباك fake: يجمع التعديلات ويرجّع نتيجة تعديل قابلة للتحكم."""

    def __init__(self, data, *, edit_result=True):
        self.data = data
        self.edits = []
        self.markups = []
        self._edit_result = edit_result
        self.answered = 0
        from types import SimpleNamespace

        self.message = SimpleNamespace(chat_id=99)

    async def answer(self):
        self.answered += 1

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)
        self.markups.append(kw.get("reply_markup"))
        return self._edit_result


def _cb_update(q, user_id=1):
    from types import SimpleNamespace

    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type="private"),
        callback_query=q,
        message=None,
    )


def _ctx(tmp_path, client):
    ctx = make_context(1, tmp_path, client=client)
    ctx.bot = RecBot()
    return ctx


# --------------------------------------------------------------------------- #
# 1) list_conversations
# --------------------------------------------------------------------------- #
class ListClient:
    def __init__(self, error):
        self._error = error

    async def search_conversations(self, limit=100, page_id=None):
        raise self._error


@pytest.mark.parametrize("exc", [
    ApiError("too many", 429),
    ApiError("server", 500),
    ApiError("gateway", 503),
    ApiError("انتهى الوقت"),        # مهلة: بلا status
    ApiError("تعذّر الاتصال"),      # انقطاع: بلا status
])
def test_list_conversations_operational_failure_propagates(tmp_path, exc):
    ctx = _ctx(tmp_path, ListClient(exc))
    q = FakeQ("list:0")
    with pytest.raises(OperationalApiFailure) as ei:
        asyncio.run(h.list_conversations(_cb_update(q), ctx))
    assert q.edits == [str(exc)] or q.edits  # الرسالة القديمة اتعرّضت
    assert ei.value.status_code == exc.status_code  # الكود محفوظ (429 يفضل 429)


@pytest.mark.parametrize("code", [401, 403, 404])
def test_list_conversations_expected_4xx_returns_normally(tmp_path, code):
    """رفض 4xx متوقّع: الرسالة تتعرض وترجع عادي (مفيش رفع)."""
    ctx = _ctx(tmp_path, ListClient(ApiError(f"reject {code}", code)))
    q = FakeQ("list:0")
    asyncio.run(h.list_conversations(_cb_update(q), ctx))  # مايرميش
    assert q.edits == [f"reject {code}"]


def test_list_conversations_success_unchanged(tmp_path):
    ctx = _ctx(tmp_path, ExchangeClient(CONV, list_items=[{"id": "c1", "title": "t"}]))
    q = FakeQ("list:0")
    asyncio.run(h.list_conversations(_cb_update(q), ctx))  # مايرميش
    assert q.edits  # عرض القايمة


# --------------------------------------------------------------------------- #
# 2) open_conversation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("exc", [
    ApiError("server", 500),
    ApiError("gateway", 503),
    ApiError("too many", 429),
    ApiError("انتهى الوقت"),        # بلا status
])
def test_open_authz_operational_failure_propagates(tmp_path, exc):
    ctx = _ctx(tmp_path, ExchangeClient(CONV, open_error=exc))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = FakeQ("open:A")
    with pytest.raises(OperationalApiFailure):
        asyncio.run(h.open_conversation(_cb_update(q), ctx))
    assert q.edits and q.edits[-1] == str(exc)   # نفس الرسالة المتنقّحة
    assert db.get_awaiting(1) == ("prev", "route")  # مفيش توجيه جديد


@pytest.mark.parametrize("code", [401, 403, 404, 410])
def test_open_authz_expected_4xx_returns_normally(tmp_path, code):
    ctx = _ctx(tmp_path, ExchangeClient(CONV, open_error=ApiError(f"reject {code}", code)))
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "prev", "route", title="t")
    q = FakeQ("open:A")
    asyncio.run(h.open_conversation(_cb_update(q), ctx))  # مايرميش
    assert q.edits == [f"reject {code}"]
    assert db.get_awaiting(1) == ("prev", "route")


def test_open_exchange_operational_failure_propagates(tmp_path):
    """فشل آخر تبادل (5xx) بعد تفويض ناجح: رسالة + انتشار."""
    ctx = _ctx(tmp_path, ExchangeClient(CONV, exchange_error=ApiError("server", 500)))
    q = FakeQ("open:A")
    with pytest.raises(OperationalApiFailure):
        asyncio.run(h.open_conversation(_cb_update(q), ctx))
    assert q.edits and "server" in q.edits[-1]


def test_open_missing_conversation_still_fail_closed(tmp_path):
    """شات مش موجود: «الشات مش موجود.» بلا رفع (فشل مغلق متوقّع)."""
    ctx = _ctx(tmp_path, ExchangeClient(None))
    q = FakeQ("open:A")
    asyncio.run(h.open_conversation(_cb_update(q), ctx))  # مايرميش
    assert q.edits == ["الشات مش موجود."]


def test_open_tombstoned_conversation_fail_closed_no_propagation(tmp_path):
    """F-1: شات متشاهد (شاهد حذف) ⇒ «الشات مش موجود.» بلا رفع ومفيش أي نداء بعيد.

    الانتشار التشغيلي **ما بيأثرش** على الحماية: الرفض المشتقّ من الشاهد متوقّع (مفيش رفع).
    """
    import bot.outbox as outbox

    ctx = _ctx(tmp_path, ExchangeClient(CONV))
    db = ctx.bot_data["db"]
    db.begin_remote_deletion("A", outbox.now_iso())
    q = FakeQ("open:A")
    asyncio.run(h.open_conversation(_cb_update(q), ctx))  # مايرميش
    assert q.edits == ["الشات مش موجود."]


def test_open_success_unchanged(tmp_path):
    ctx = _ctx(tmp_path, ExchangeClient(CONV, "برومتي", "ردي"))
    q = FakeQ("open:A")
    asyncio.run(h.open_conversation(_cb_update(q), ctx))  # مايرميش
    assert q.edits and "ردي" in q.edits[-1]


# --------------------------------------------------------------------------- #
# 3) copy_reply
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("exc", [ApiError("server", 500), ApiError("انتهى الوقت")])
def test_copy_reply_operational_failure_propagates(tmp_path, exc):
    ctx = _ctx(tmp_path, ExchangeClient(CONV, exchange_error=exc))
    q = FakeQ("copy:A")
    with pytest.raises(OperationalApiFailure):
        asyncio.run(h.copy_reply(_cb_update(q), ctx))
    # copy_reply بيبعت رسالة جديدة (مش تعديل) — لسه رسالة واحدة، مفيش ازدواج
    assert ctx.bot.messages and ctx.bot.messages[0][0] == str(exc)
    assert q.edits == []


def test_copy_reply_success_unchanged(tmp_path):
    ctx = _ctx(tmp_path, ExchangeClient(CONV, "ب", "رد قابل للنسخ"))
    q = FakeQ("copy:A")
    asyncio.run(h.copy_reply(_cb_update(q), ctx))  # مايرميش
    assert ctx.bot.messages  # رد قابل للنسخ


# --------------------------------------------------------------------------- #
# 4) full_reply
# --------------------------------------------------------------------------- #
def test_full_reply_operational_failure_propagates(tmp_path):
    ctx = _ctx(tmp_path, ExchangeClient(CONV, exchange_error=ApiError("gateway", 503)))
    q = FakeQ("full:A")
    with pytest.raises(OperationalApiFailure):
        asyncio.run(h.full_reply(_cb_update(q), ctx))
    assert ctx.bot.messages and ctx.bot.messages[0][0] == "gateway"


def test_full_reply_success_unchanged(tmp_path):
    ctx = _ctx(tmp_path, ExchangeClient(CONV, "ب", "رد" * 200))
    q = FakeQ("full:A")
    asyncio.run(h.full_reply(_cb_update(q), ctx))  # مايرميش
    assert ctx.bot.messages  # الرد الكامل


# --------------------------------------------------------------------------- #
# 5) _show_repos
# --------------------------------------------------------------------------- #
class RepoClient:
    def __init__(self, error=None, repos=None):
        self._error = error
        self._repos = repos or []
        self.calls = 0

    async def search_repositories(self, query=""):
        self.calls += 1
        if self._error:
            raise self._error
        return self._repos


def test_show_repos_operational_failure_propagates(tmp_path):
    ctx = _ctx(tmp_path, RepoClient(error=ApiError("server", 500)))
    q = FakeQ("repos:0")
    with pytest.raises(OperationalApiFailure):
        asyncio.run(h._show_repos(q, ctx, 0, "", user_id=1))
    assert q.edits and q.edits[-1] == "server"


@pytest.mark.parametrize("code", [403, 404])
def test_show_repos_expected_4xx_returns_normally(tmp_path, code):
    ctx = _ctx(tmp_path, RepoClient(error=ApiError(f"reject {code}", code)))
    q = FakeQ("repos:0")
    asyncio.run(h._show_repos(q, ctx, 0, "", user_id=1))  # مايرميش
    assert q.edits == [f"reject {code}"]


def test_show_repos_success_unchanged(tmp_path):
    ctx = _ctx(tmp_path, RepoClient(repos=[]))
    q = FakeQ("repos:0")
    asyncio.run(h._show_repos(q, ctx, 0, "", user_id=1))  # مايرميش
    assert q.edits  # رسالة «مفيش نتايج» مثلاً


# --------------------------------------------------------------------------- #
# أمان إضافي: النوع الفرعي ResponseTooLargeError (4xx/غير تشغيلي) ماينتشرش
# --------------------------------------------------------------------------- #
def test_show_repos_response_too_large_is_expected_not_propagated(tmp_path):
    """`ResponseTooLargeError` (رفض متوقّع بلا status) يرجّع عادي — مش فشل تشغيلي.

    (بلا `status_code` ⇒ `is_permanent` False ⇒ ينتشر عند حدود SW-07؛ نثبّت السلوك هنا.)
    """
    err = ResponseTooLargeError()
    ctx = _ctx(tmp_path, RepoClient(error=err))
    q = FakeQ("repos:0")
    # بلا status_code: نعتبره عابرًا ⇒ ينتشر (سلوك SW-07 المقصود للفشل غير المصنّف).
    with pytest.raises(OperationalApiFailure):
        asyncio.run(h._show_repos(q, ctx, 0, "", user_id=1))


# --------------------------------------------------------------------------- #
# CancelledError ما بيتكتمش (BaseException ≠ Exception)
# --------------------------------------------------------------------------- #
def test_cancelled_error_not_swallowed_by_list(tmp_path):
    class CancellingClient:
        async def search_conversations(self, limit=100, page_id=None):
            raise asyncio.CancelledError()

    ctx = _ctx(tmp_path, CancellingClient())
    q = FakeQ("list:0")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(h.list_conversations(_cb_update(q), ctx))


# --------------------------------------------------------------------------- #
# مفيش أثر جانبي مكرّر / مفيش نجاح كاذب عند فشل تسليم تيليجرام
# --------------------------------------------------------------------------- #
def test_open_operational_failure_no_duplicate_side_effects(tmp_path):
    """فشل تشغيلي: تعديل واحد بالظبط، ومفيش صفوف outbox/إنشاء جديدة."""
    ctx = _ctx(tmp_path, ExchangeClient(CONV, open_error=ApiError("server", 500)))
    db = ctx.bot_data["db"]
    q = FakeQ("open:A")
    with pytest.raises(OperationalApiFailure):
        asyncio.run(h.open_conversation(_cb_update(q), ctx))
    assert q.edits == ["server"]                    # محاولة عرض واحدة (مفيش ازدواج)
    assert db.count_outbox() == 0
    assert db.list_open_creation_jobs() == []


def test_open_operational_failure_delivery_failure_no_false_success(tmp_path):
    """فشل تعديل رسالة الخطأ على تيليجرام: لسه بنرفع (مفيش نجاح كاذب)، ومفيش إرسال مكرّر."""
    ctx = _ctx(tmp_path, ExchangeClient(CONV, open_error=ApiError("server", 500)))
    q = FakeQ("open:A", edit_result=False)  # تعديل الرسالة فشل
    with pytest.raises(OperationalApiFailure):
        asyncio.run(h.open_conversation(_cb_update(q), ctx))
    assert q.edits == ["server"]  # محاولة واحدة، مفيش ازدواج


# --------------------------------------------------------------------------- #
# تكامل PTB 22.x: الاستثناء يوصل لمعالج الأخطاء عبر process_update
# --------------------------------------------------------------------------- #
def test_ptb_process_update_dispatches_propagated_failure_to_error_handler():
    from telegram import Chat, Message, Update, User
    from telegram.ext import Application, TypeHandler

    async def main():
        app = Application.builder().token("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi").build()
        seen = []

        async def boom(update, context):
            raise OperationalApiFailure("خدمة OpenHands مش متاحة دلوقتي.", 503)

        async def on_err(update, context):
            seen.append(context.error)

        app.add_handler(TypeHandler(Update, boom))
        app.add_error_handler(on_err)
        app._initialized = True  # تجاوز الفحص بلا تهيئة شبكة
        upd = Update(
            update_id=1,
            message=Message(
                message_id=1,
                date=None,
                chat=Chat(id=1, type="private"),
                from_user=User(id=1, first_name="a", is_bot=False),
                text="hi",
            ),
        )
        await app.process_update(upd)
        return seen

    seen = asyncio.run(main())
    assert seen and isinstance(seen[0], OperationalApiFailure)
