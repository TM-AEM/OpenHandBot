"""OHB2-09-06 (B-06-04): مسار ملفات/تفاصيل البوت لازم يعدّي من `FileService`.

المشكلة اللي بنغطّيها: معالجات البوت (`list_files`/`show_file`/`show_status`/`show_cost`/
`watch_conversation`/`open_conversation`/`copy_reply`/`full_reply`/`export_conversation`)
كانت بتستخدم عميل خام (`client.list_files`/`client.read_file` غير المحدود) وتفويض مكرّر.
الاختبارات دي بتثبت إن المسار بقى يعدّي من **نفس** عقد `FileService`:

- تفويض الملكية (fail closed) قبل أي قراءة.
- allowlist المسارات (نتخطّى المطلق/الاجتياز).
- عضوية القايمة (مفيش قراءة لملف مش في القايمة).
- قراءة **محدودة** (`read_file_text_bounded`) مش `read_file` غير المحدود.
- حالات TOO_LARGE/BINARY/NOT_UTF8 بتتعامل بأمان (مفيش مستند).
- كاش الهوية مشترك (نداء `/users/me` واحد عبر عمليات كتير).
"""
from __future__ import annotations

import asyncio

import bot.handlers as h
from bot.errors import ApiError, ResponseTooLargeError
from bot.file_cache import FileCache
from tests.test_handlers import _cb_update, _ctx_with

OWNER_UUID = "owner-uuid-123"


class FileFlowClient:
    """عميل وهمي بيعدّ النداءات وبيتحكّم في الملكية/القايمة/المحتوى.

    `read_file` (غير المحدود) بيرمي AssertionError لو البوت استخدمه — إثبات إن المسار
    بقى محدود. كل نداءات `/users/me` بتتعدّ في `me_calls`.
    """

    def __init__(self, *, conv_owner=OWNER_UUID, identity=OWNER_UUID, convs_present=True,
                 files=None, content="hello", read_error=None):
        self._conv_owner = conv_owner
        self._identity = identity
        self._convs_present = convs_present
        self._files = list(files) if files is not None else ["a/b/main.py"]
        self._content = content
        self._read_error = read_error
        self.list_calls = 0
        self.read_calls = 0
        self.me_calls = []

    async def get_conversations(self, ids):
        if not self._convs_present:
            return []
        conv = {"id": "c1", "title": "شات", "execution_status": "running"}
        if self._conv_owner is not None:
            conv["created_by_user_id"] = self._conv_owner
        return [conv]

    async def get_current_user(self):
        self.me_calls.append(1)
        return {"id": self._identity} if self._identity else {}

    async def list_files(self, conversation_id, path=""):
        self.list_calls += 1
        return list(self._files)

    async def read_file_text_bounded(self, conversation_id, file_path, max_response_bytes=None):
        self.read_calls += 1
        if self._read_error is not None:
            raise self._read_error
        return self._content

    async def read_file(self, conversation_id, file_path):
        raise AssertionError("البوت مايستخدمش read_file غير المحدود بعد OHB2-09-06")

    async def get_last_exchange(self, conversation_id):
        return ("برومت", "رد")


def _seed_files(context, paths):
    cache = FileCache()
    gen = cache.put("c1", list(paths))
    context.bot_data["file_cache"] = cache
    return gen


def _run_show_file(tmp_path, client, paths, index=0):
    ctx = _ctx_with(tmp_path, client)
    gen = _seed_files(ctx, paths)
    update = _cb_update(1, f"file:c1:{gen}:{index}")
    asyncio.run(h.show_file(update, ctx))
    return update, ctx


# ---------------------------------------------------------------- list_files
def test_list_files_filters_unsafe_paths(tmp_path):
    client = FileFlowClient(files=["ok/main.py", "/etc/passwd", "../secret", "a/../b"])
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "files:c1:0")
    asyncio.run(h.list_files(update, ctx))
    cached = ctx.bot_data["file_cache"].get("c1")
    assert cached is not None
    assert cached[0] == ["ok/main.py"]  # المسارات غير الآمنة اتشالت من العرض


def test_list_files_other_owner_denied_no_upstream(tmp_path):
    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "files:c1:0")
    asyncio.run(h.list_files(update, ctx))
    assert "مش مسموح" in update.callback_query.edits[-1]
    assert client.list_calls == 0  # مفيش جلب ملفات قبل التفويض


def test_list_files_null_owner_denied(tmp_path):
    client = FileFlowClient(conv_owner=None)  # created_by_user_id ناقص ⇒ فشل مغلق
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "files:c1:0")
    asyncio.run(h.list_files(update, ctx))
    assert "مش مسموح" in update.callback_query.edits[-1]
    assert client.list_calls == 0


# ---------------------------------------------------------------- show_file
def test_show_file_uses_bounded_read_not_unbounded(tmp_path):
    client = FileFlowClient(files=["a/b/main.py"], content="hello")
    update, ctx = _run_show_file(tmp_path, client, ["a/b/main.py"])
    assert len(ctx.bot.documents) == 1
    assert client.read_calls == 1  # قرأ محدود
    assert client.list_calls == 1  # allowlist membership


def test_show_file_path_not_in_listing_is_denied(tmp_path):
    # الملف اللي في الكاش مش في القايمة الفعلية ⇒ allowlist بترفض القراءة.
    client = FileFlowClient(files=["other.py"])
    update, ctx = _run_show_file(tmp_path, client, ["a/b/main.py"])
    assert ctx.bot.documents == []
    assert client.read_calls == 0  # مفيش قراءة لملف مش في القايمة
    assert "مش موجود" in update.callback_query.edits[-1]


def test_show_file_too_large_is_safe(tmp_path):
    client = FileFlowClient(files=["big.py"], read_error=ResponseTooLargeError())
    update, ctx = _run_show_file(tmp_path, client, ["big.py"])
    assert ctx.bot.documents == []
    assert "كبير" in update.callback_query.edits[-1]


def test_show_file_binary_is_safe(tmp_path):
    client = FileFlowClient(files=["bin.dat"], content="a\x00b")
    update, ctx = _run_show_file(tmp_path, client, ["bin.dat"])
    assert ctx.bot.documents == []
    assert "مش نص" in update.callback_query.edits[-1]


def test_show_file_upstream_error_is_safe(tmp_path):
    client = FileFlowClient(files=["a.py"], read_error=ApiError("خدمة مش متاحة", 503))
    update, ctx = _run_show_file(tmp_path, client, ["a.py"])
    assert ctx.bot.documents == []
    assert update.callback_query.edits


def test_show_file_other_owner_denied_no_read(tmp_path):
    client = FileFlowClient(conv_owner="someone-else", files=["a.py"])
    update, ctx = _run_show_file(tmp_path, client, ["a.py"])
    assert ctx.bot.documents == []
    assert client.read_calls == 0
    assert "مش مسموح" in update.callback_query.edits[-1]


# ---------------------------------------------------------------- detail/cost
def test_show_status_other_owner_denied(tmp_path):
    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "status:c1")
    asyncio.run(h.show_status(update, ctx))
    assert "مش مسموح" in update.callback_query.edits[-1]


def test_show_cost_other_owner_denied(tmp_path):
    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "cost:c1")
    asyncio.run(h.show_cost(update, ctx))
    assert "مش مسموح" in update.callback_query.edits[-1]


# ---------------------------------------------------------------- watch
def test_watch_other_owner_not_added(tmp_path):
    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "watch:c1")
    asyncio.run(h.watch_conversation(update, ctx))
    assert ctx.bot_data["db"].is_watched("c1") is False
    assert "مش مسموح" in update.callback_query.edits[-1]


def test_watch_owner_adds(tmp_path):
    client = FileFlowClient()
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "watch:c1")
    asyncio.run(h.watch_conversation(update, ctx))
    assert ctx.bot_data["db"].is_watched("c1") is True


# ---------------------------------------------------------------- identity cache
def test_identity_cache_shared_single_users_me_call(tmp_path):
    client = FileFlowClient(files=["a.py"])
    ctx = _ctx_with(tmp_path, client)

    async def go():
        for data in ("status:c1", "cost:c1", "files:c1:0"):
            await _dispatch(data, ctx)

    asyncio.run(go())
    # نداء `/users/me` واحد بس رغم ٣ عمليات (كاش الهوية المشترك).
    assert len(client.me_calls) == 1


async def _dispatch(data, ctx):
    if data.startswith("status:"):
        await h.show_status(_cb_update(1, data), ctx)
    elif data.startswith("cost:"):
        await h.show_cost(_cb_update(1, data), ctx)
    elif data.startswith("files:"):
        await h.list_files(_cb_update(1, data), ctx)


# ---------------------------------------------------------------- open/copy/full/export
def test_open_other_owner_denied_no_exchange(tmp_path):
    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "open:c1")
    asyncio.run(h.open_conversation(update, ctx))
    assert ctx.bot_data["db"].get_awaiting(1) == (None, None)  # مفيش توجيه
    assert "مش مسموح" in update.callback_query.edits[-1]


def test_copy_other_owner_denied(tmp_path):
    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "copy:c1")
    asyncio.run(h.copy_reply(update, ctx))
    assert any("مش مسموح" in m for m in ctx.bot.sent)


def test_full_other_owner_denied(tmp_path):
    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "full:c1")
    asyncio.run(h.full_reply(update, ctx))
    assert any("مش مسموح" in m for m in ctx.bot.sent)


def test_export_other_owner_denied_no_download(tmp_path):
    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "export:c1")
    asyncio.run(h.export_conversation(update, ctx))
    assert ctx.bot.documents == []
    assert "مش مسموح" in update.callback_query.edits[-1]


# ---------------------------------------------------------------- invalid id
def test_status_invalid_conversation_id_denied_no_upstream(tmp_path):
    # معرّف غير آمن (مسافة) ⇒ يترفض محليًا قبل أي نداء upstream (حماية حقن المسار).
    client = FileFlowClient()
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "status:bad id!")
    asyncio.run(h.show_status(update, ctx))
    assert client.list_calls == 0
    assert "مش موجود" in update.callback_query.edits[-1]


def test_list_files_invalid_conversation_id_denied_no_upstream(tmp_path):
    client = FileFlowClient()
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "files:bad/../id:0")
    asyncio.run(h.list_files(update, ctx))
    assert client.list_calls == 0
    assert "مش موجود" in update.callback_query.edits[-1]


# ------------------------------------------------------------ reply routing (B2)
def test_reply_prompt_owner_sets_awaiting(tmp_path):
    """المالك: بعد التفويض بيتفتح توجيه البرومت (awaiting=reply)."""
    client = FileFlowClient()
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "prompt:c1")
    asyncio.run(h.reply_prompt(update, ctx))
    conv_id, kind = ctx.bot_data["db"].get_awaiting(1)
    assert conv_id == "c1" and kind == "reply"


def test_reply_prompt_other_owner_denied_no_awaiting(tmp_path):
    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "prompt:c1")
    asyncio.run(h.reply_prompt(update, ctx))
    conv_id, kind = ctx.bot_data["db"].get_awaiting(1)
    assert conv_id is None and kind is None  # مفيش توجيه برومت
    assert "مش مسموح" in update.callback_query.edits[-1]


def test_reply_prompt_null_owner_denied(tmp_path):
    client = FileFlowClient(conv_owner=None)  # فشل مغلق
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "prompt:c1")
    asyncio.run(h.reply_prompt(update, ctx))
    conv_id, kind = ctx.bot_data["db"].get_awaiting(1)
    assert conv_id is None and kind is None
    assert "مش مسموح" in update.callback_query.edits[-1]


def test_reply_prompt_missing_conversation_denied(tmp_path):
    client = FileFlowClient(convs_present=False)
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "prompt:c1")
    asyncio.run(h.reply_prompt(update, ctx))
    conv_id, kind = ctx.bot_data["db"].get_awaiting(1)
    assert conv_id is None and kind is None
    assert "مش موجود" in update.callback_query.edits[-1]


def test_reply_prompt_invalid_conversation_id_denied_no_upstream(tmp_path):
    client = FileFlowClient()
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "prompt:bad id!")
    asyncio.run(h.reply_prompt(update, ctx))
    conv_id, kind = ctx.bot_data["db"].get_awaiting(1)
    assert conv_id is None and kind is None
    assert "مش موجود" in update.callback_query.edits[-1]
