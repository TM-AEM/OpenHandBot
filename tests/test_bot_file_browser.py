"""OHB2-BOT-FILE-BROWSER: اختبارات معالجات المتصفح الهرمي + رسائل الثنائي + DEF-010."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import bot.handlers as h
from bot import keyboards as kb
from bot.db import Database
from bot.file_cache import FileCache
from bot.files import FileListing, FileStatus

OWNER = 1
OWNER_UUID = "owner-uuid"


class FakeConfig:
    def __init__(self, allowed: int = OWNER):
        self.allowed_telegram_ids = frozenset({allowed})
        self.owner_id = allowed
        self.mini_app_enabled = False
        self.mini_app_url = ""

    def is_allowed(self, user_id: int) -> bool:
        return user_id in self.allowed_telegram_ids


class FakeQuery:
    def __init__(self):
        self.edits = []
        self.edits_markup = []
        self.message = SimpleNamespace(chat_id=99)

    async def answer(self):
        pass

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)
        self.edits_markup.append(kw.get("reply_markup"))


class FakeBot:
    def __init__(self):
        self.documents = []
        self.sent = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)

    async def send_document(self, chat_id=None, document=None, **kw):
        self.documents.append(document)


class FakeClient:
    OWNER_UUID = OWNER_UUID

    def __init__(self, files, content="", content_map=None, cid="c1"):
        self.files = list(files)
        self.content = content
        self.content_map = content_map or {}
        self.conv = {"id": cid, "title": "شات", "created_by_user_id": OWNER_UUID}
        self.calls = []

    async def get_conversations(self, ids):
        self.calls.append(("get_conversations", tuple(ids)))
        return [self.conv] if self.conv else []

    async def get_current_user(self):
        self.calls.append(("get_current_user",))
        return {"id": OWNER_UUID}

    async def list_files(self, conversation_id, path=""):
        self.calls.append(("list_files", conversation_id, path))
        return list(self.files)

    async def read_file_text_bounded(self, conversation_id, file_path, max_response_bytes=None):
        self.calls.append(("read_file_text_bounded", conversation_id, file_path))
        return self.content_map.get(file_path, self.content)

    async def export_conversation(self, conversation_id):
        self.calls.append(("export_conversation", conversation_id))
        return b"PK\x03\x04zip"


def _ctx(tmp_path, client):
    ctx = SimpleNamespace()
    ctx.bot_data = {
        "config": FakeConfig(),
        "db": Database(str(tmp_path / "t.sqlite3")),
        "client": client,
    }
    ctx.bot = FakeBot()
    return ctx


def _cb(data, user_id=OWNER):
    q = FakeQuery()
    q.data = data
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type="private"),
        message=SimpleNamespace(),
        callback_query=q,
        update_id=1,
    )


def _callbacks(markup):
    if markup is None:
        return []
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]


def _open(ctx, cid="c1"):
    token = h._files_open_cb(ctx, cid)  # already "fbo:<token>"
    update = _cb(token)
    asyncio.run(h.browse_open(update, ctx))
    return update, token


def _nav_from(update):
    for cb in _callbacks(update.callback_query.edits_markup[-1]):
        if cb.startswith(("fbd:", "fbf:", "fbp:", "fbu:", "fbx:", "fbb:")):
            return cb.split(":")[1]
    raise AssertionError("no browser callback found")


def _file_indices(markup, nav, dir_index=0):
    prefix = f"fbf:{nav}:{dir_index}:"
    return [int(cb.split(":")[3]) for cb in _callbacks(markup) if cb.startswith(prefix)]


def _patch_listing(monkeypatch, result):
    async def fake_list_files(conversation_id):
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(
        h, "_files_service", lambda context: SimpleNamespace(list_files=fake_list_files)
    )


def _assert_old_nav_rejected(ctx, nav):
    for handler, data in (
        (h.browse_page, f"fbp:{nav}:0:0"),
        (h.browse_dir, f"fbd:{nav}:0"),
        (h.browse_file, f"fbf:{nav}:0:0"),
    ):
        update = _cb(data)
        asyncio.run(handler(update, ctx))
        assert "قديمة" in update.callback_query.edits[-1]


def test_open_root_shows_dirs_then_files_and_callbacks_fit(tmp_path):
    client = FakeClient(["b.txt", "a/x.py", "docs/readme.md"])
    ctx = _ctx(tmp_path, client)
    update, token = _open(ctx)
    assert token.startswith("fbo:")
    assert len(token.encode()) <= 64
    assert "📁 /" in update.callback_query.edits[-1]
    assert "صفحة 1/1" in update.callback_query.edits[-1]
    cbs = _callbacks(update.callback_query.edits_markup[-1])
    nav = _nav_from(update)
    state = ctx.bot_data["file_browser_cache"].get(nav)
    assert cbs[0] == f"fbd:{nav}:{state.dir_index['a']}"
    assert cbs[1] == f"fbd:{nav}:{state.dir_index['docs']}"
    assert f"fbf:{nav}:0:0" in cbs
    assert all(len(cb.encode()) <= 64 for cb in cbs)


def test_navigate_into_dir_up_and_root(tmp_path):
    client = FakeClient(["a/x.py", "a/y.py", "docs/readme.md"])
    ctx = _ctx(tmp_path, client)
    update, _ = _open(ctx)
    nav = _nav_from(update)
    state = ctx.bot_data["file_browser_cache"].get(nav)
    a_index = state.dir_index["a"]

    u = _cb(f"fbd:{nav}:{a_index}")
    asyncio.run(h.browse_dir(u, ctx))
    assert "📁 a" in u.callback_query.edits[-1]
    cbs = _callbacks(u.callback_query.edits_markup[-1])
    assert f"fbf:{nav}:{a_index}:0" in cbs
    assert f"fbf:{nav}:{a_index}:1" in cbs
    assert f"fbu:{nav}:{a_index}" in cbs
    assert f"fbr:{nav}" in cbs

    up = _cb(f"fbu:{nav}:{a_index}")
    asyncio.run(h.browse_up(up, ctx))
    assert "📁 /" in up.callback_query.edits[-1]

    root = _cb(f"fbr:{nav}")
    asyncio.run(h.browse_root(root, ctx))
    assert "📁 /" in root.callback_query.edits[-1]


def test_duplicate_names_in_different_dirs_are_distinct(tmp_path):
    client = FakeClient(
        ["a/x.py", "b/x.py"], content_map={"a/x.py": "AAA", "b/x.py": "BBB"}
    )
    ctx = _ctx(tmp_path, client)
    update, _ = _open(ctx)
    nav = _nav_from(update)
    state = ctx.bot_data["file_browser_cache"].get(nav)
    for name, expected in (("a", "AAA"), ("b", "BBB")):
        index = state.dir_index[name]
        u = _cb(f"fbd:{nav}:{index}")
        asyncio.run(h.browse_dir(u, ctx))
        f = _cb(f"fbf:{nav}:{index}:0")
        asyncio.run(h.browse_file(f, ctx))
        doc = ctx.bot.documents[-1]
        assert doc.filename == "x.py"
        assert doc.input_file_content.decode() == expected


def test_pagination_previous_next_and_no_duplicates(tmp_path):
    files = [f"f{i:02d}.txt" for i in range(25)]
    client = FakeClient(files)
    ctx = _ctx(tmp_path, client)
    update, _ = _open(ctx)
    nav = _nav_from(update)
    assert "صفحة 1/3" in update.callback_query.edits[-1]
    cbs = _callbacks(update.callback_query.edits_markup[-1])
    assert f"fbp:{nav}:0:1" in cbs
    assert f"fbp:{nav}:0:-1" not in cbs
    seen = _file_indices(update.callback_query.edits_markup[-1], nav)
    assert seen == list(range(0, 10))

    u = _cb(f"fbp:{nav}:0:1")
    asyncio.run(h.browse_page(u, ctx))
    assert "صفحة 2/3" in u.callback_query.edits[-1]
    cbs2 = _callbacks(u.callback_query.edits_markup[-1])
    assert f"fbp:{nav}:0:0" in cbs2
    assert f"fbp:{nav}:0:2" in cbs2
    seen.extend(_file_indices(u.callback_query.edits_markup[-1], nav))
    assert seen == list(range(0, 20))

    u2 = _cb(f"fbp:{nav}:0:2")
    asyncio.run(h.browse_page(u2, ctx))
    assert "صفحة 3/3" in u2.callback_query.edits[-1]
    cbs3 = _callbacks(u2.callback_query.edits_markup[-1])
    assert f"fbp:{nav}:0:1" in cbs3
    assert f"fbp:{nav}:0:3" not in cbs3
    seen.extend(_file_indices(u2.callback_query.edits_markup[-1], nav))
    assert seen == list(range(0, 25))
    assert len(seen) == len(set(seen))

    u3 = _cb(f"fbp:{nav}:0:99")
    asyncio.run(h.browse_page(u3, ctx))
    assert "صفحة 3/3" in u3.callback_query.edits[-1]


def test_snapshot_is_stable_and_refresh_rebuilds(tmp_path):
    client = FakeClient(["a.txt", "b.txt"])
    ctx = _ctx(tmp_path, client)
    update, _ = _open(ctx)
    nav = _nav_from(update)
    client.files.append("c.txt")

    u = _cb(f"fbp:{nav}:0:0")
    asyncio.run(h.browse_page(u, ctx))
    assert len(_file_indices(u.callback_query.edits_markup[-1], nav)) == 2

    u2 = _cb(f"fbx:{nav}:0")
    asyncio.run(h.browse_refresh(u2, ctx))
    new_nav = _nav_from(u2)
    assert new_nav != nav
    assert len(_file_indices(u2.callback_query.edits_markup[-1], new_nav)) == 3

    u3 = _cb(f"fbp:{nav}:0:0")
    asyncio.run(h.browse_page(u3, ctx))
    assert "قديمة" in u3.callback_query.edits[-1]


def test_refresh_preserves_current_directory(tmp_path):
    client = FakeClient(["a/x.py"])
    ctx = _ctx(tmp_path, client)
    update, _ = _open(ctx)
    nav = _nav_from(update)
    state = ctx.bot_data["file_browser_cache"].get(nav)
    a_index = state.dir_index["a"]

    u = _cb(f"fbd:{nav}:{a_index}")
    asyncio.run(h.browse_dir(u, ctx))
    client.files.append("a/y.py")
    u2 = _cb(f"fbx:{nav}:{a_index}")
    asyncio.run(h.browse_refresh(u2, ctx))
    assert "📁 a" in u2.callback_query.edits[-1]
    new_nav = _nav_from(u2)
    new_state = ctx.bot_data["file_browser_cache"].get(new_nav)
    assert len(_file_indices(u2.callback_query.edits_markup[-1], new_nav, new_state.dir_index["a"])) == 2


def test_expired_invalid_and_non_owner_are_safe(tmp_path):
    client = FakeClient(["a.txt"])
    ctx = _ctx(tmp_path, client)

    u = _cb("fbd:deadbeefdeadbeef:0")
    asyncio.run(h.browse_dir(u, ctx))
    assert "قديمة" in u.callback_query.edits[-1]

    u = _cb("fbd:not-a-nav:x")
    asyncio.run(h.browse_dir(u, ctx))
    assert "قديمة" in u.callback_query.edits[-1]

    u = _cb("fbo:unknown")
    asyncio.run(h.browse_open(u, ctx))
    assert "قديمة" in u.callback_query.edits[-1]

    u = _cb("fbd:deadbeefdeadbeef:0", user_id=999)
    asyncio.run(h.browse_dir(u, ctx))
    assert u.callback_query.edits == []


def test_binary_zip_message_no_document_no_download(tmp_path):
    client = FakeClient(["archive.zip"], content="PK\x03\x04\x00")
    ctx = _ctx(tmp_path, client)
    update, _ = _open(ctx)
    nav = _nav_from(update)

    u = _cb(f"fbf:{nav}:0:0")
    asyncio.run(h.browse_file(u, ctx))
    message = u.callback_query.edits[-1]
    assert "ثنائي" in message
    assert "Cloud V1" in message
    assert "ZIP" in message
    assert ctx.bot.documents == []
    assert all("download" not in str(call) for call in client.calls)


def test_not_utf8_and_too_large_messages(tmp_path):
    ctx = _ctx(tmp_path, FakeClient(["bad.txt"], content="x\ufffdy"))
    update, _ = _open(ctx)
    nav = _nav_from(update)
    u = _cb(f"fbf:{nav}:0:0")
    asyncio.run(h.browse_file(u, ctx))
    assert "ترميز" in u.callback_query.edits[-1]
    assert ctx.bot.documents == []

    ctx = _ctx(tmp_path, FakeClient(["big.txt"], content="z" * (256 * 1024 + 1)))
    update, _ = _open(ctx)
    nav = _nav_from(update)
    u = _cb(f"fbf:{nav}:0:0")
    asyncio.run(h.browse_file(u, ctx))
    assert "256 KiB" in u.callback_query.edits[-1]
    assert ctx.bot.documents == []


def test_text_preview_still_sends_document(tmp_path):
    client = FakeClient(["main.py"], content="print('hi')\n")
    ctx = _ctx(tmp_path, client)
    update, _ = _open(ctx)
    nav = _nav_from(update)
    u = _cb(f"fbf:{nav}:0:0")
    asyncio.run(h.browse_file(u, ctx))
    assert len(ctx.bot.documents) == 1
    doc = ctx.bot.documents[0]
    assert doc.filename == "main.py"
    assert doc.input_file_content.decode() == "print('hi')\n"


def test_long_conversation_id_callbacks_stay_within_64_bytes(tmp_path):
    cid = "x" * 64
    client = FakeClient([f"f{i}.txt" for i in range(15)], cid=cid)
    ctx = _ctx(tmp_path, client)
    token = h._files_open_cb(ctx, cid)  # already "fbo:<token>"
    assert len(token.encode()) <= 64

    update = _cb(token)
    asyncio.run(h.browse_open(update, ctx))
    cbs = _callbacks(update.callback_query.edits_markup[-1])
    assert cbs and all(len(cb.encode()) <= 64 for cb in cbs)
    nav = _nav_from(update)

    u = _cb(f"fbp:{nav}:0:1")
    asyncio.run(h.browse_page(u, ctx))
    assert all(len(cb.encode()) <= 64 for cb in _callbacks(u.callback_query.edits_markup[-1]))

    u2 = _cb(f"fbf:{nav}:0:0")
    asyncio.run(h.browse_file(u2, ctx))
    assert len(ctx.bot.documents) == 1

    markup = kb.conversation_actions("c" * 32, files_cb=token)
    cbs2 = _callbacks(markup)
    assert token in cbs2
    assert all(len(cb.encode()) <= 64 for cb in cbs2)


def test_browse_back_returns_conversation_actions(tmp_path):
    client = FakeClient(["a.txt"])
    ctx = _ctx(tmp_path, client)
    update, token = _open(ctx)
    nav = _nav_from(update)
    u = _cb(f"fbb:{nav}")
    asyncio.run(h.browse_back(u, ctx))
    assert "رجعت للشات" in u.callback_query.edits[-1]
    assert token in _callbacks(u.callback_query.edits_markup[-1])


def test_long_cid_browse_back_uses_short_fallback(tmp_path):
    cid = "x" * 64
    client = FakeClient(["a.txt"], cid=cid)
    ctx = _ctx(tmp_path, client)
    update, token = _open(ctx, cid=cid)
    nav = _nav_from(update)
    u = _cb(f"fbb:{nav}")
    asyncio.run(h.browse_back(u, ctx))
    cbs = _callbacks(u.callback_query.edits_markup[-1])
    assert token in cbs
    assert "list:0" in cbs
    assert all(len(cb.encode()) <= 64 for cb in cbs)


def test_long_cid_empty_root_uses_short_fallback(tmp_path):
    cid = "x" * 64
    client = FakeClient([], cid=cid)
    ctx = _ctx(tmp_path, client)
    update, token = _open(ctx, cid=cid)
    cbs = _callbacks(update.callback_query.edits_markup[-1])
    assert token in cbs
    assert "list:0" in cbs
    assert all(len(cb.encode()) <= 64 for cb in cbs)


def test_oversized_listing_is_bounded_and_reported(tmp_path):
    from bot.file_browser import BrowserCache

    client = FakeClient([f"f{i}.txt" for i in range(10)])
    ctx = _ctx(tmp_path, client)
    ctx.bot_data["file_browser_cache"] = BrowserCache(max_total_chars=0)
    update, _ = _open(ctx)
    assert "أكبر من حد التصفح" in update.callback_query.edits[-1]


def test_empty_root_reports_no_files(tmp_path):
    client = FakeClient([])
    ctx = _ctx(tmp_path, client)
    update, token = _open(ctx)
    assert "ما فيهاش ملفات" in update.callback_query.edits[-1]
    assert token in _callbacks(update.callback_query.edits_markup[-1])


def test_directory_with_only_nested_directories(tmp_path):
    client = FakeClient(["a/b/c.txt"])
    ctx = _ctx(tmp_path, client)
    update, _ = _open(ctx)
    nav = _nav_from(update)
    state = ctx.bot_data["file_browser_cache"].get(nav)
    a_index = state.dir_index["a"]

    u = _cb(f"fbd:{nav}:{a_index}")
    asyncio.run(h.browse_dir(u, ctx))
    assert "📁 a" in u.callback_query.edits[-1]
    assert f"fbd:{nav}:{state.dir_index['a/b']}" in _callbacks(u.callback_query.edits_markup[-1])

    ab_index = state.dir_index["a/b"]
    u2 = _cb(f"fbd:{nav}:{ab_index}")
    asyncio.run(h.browse_dir(u2, ctx))
    assert "📁 a/b" in u2.callback_query.edits[-1]
    assert f"fbf:{nav}:{ab_index}:0" in _callbacks(u2.callback_query.edits_markup[-1])


def test_unicode_and_space_paths(tmp_path):
    client = FakeClient(["مجلد/ملف نصي.txt", "dir with space/a b.py"])
    ctx = _ctx(tmp_path, client)
    update, _ = _open(ctx)
    nav = _nav_from(update)
    state = ctx.bot_data["file_browser_cache"].get(nav)
    for name in ("مجلد", "dir with space"):
        index = state.dir_index[name]
        u = _cb(f"fbd:{nav}:{index}")
        asyncio.run(h.browse_dir(u, ctx))
        assert "📁" in u.callback_query.edits[-1]
        assert f"fbf:{nav}:{index}:0" in _callbacks(u.callback_query.edits_markup[-1])


def test_conversation_zip_export_still_works(tmp_path):
    client = FakeClient([])
    ctx = _ctx(tmp_path, client)
    u = _cb("export:c1")
    asyncio.run(h.export_conversation(u, ctx))
    assert len(ctx.bot.documents) == 1
    assert ctx.bot.documents[0].filename.endswith(".zip")


def test_legacy_show_file_binary_message(tmp_path):
    client = FakeClient(["archive.zip"], content="PK\x03\x04\x00")
    ctx = _ctx(tmp_path, client)
    cache = FileCache()
    gen = cache.put("c1", ["archive.zip"])
    ctx.bot_data["file_cache"] = cache
    u = _cb(f"file:c1:{gen}:0")
    asyncio.run(h.show_file(u, ctx))
    assert "ثنائي" in u.callback_query.edits[-1]
    assert ctx.bot.documents == []


def test_evicted_state_callback_is_safe(tmp_path):
    from bot.file_browser import BrowserCache

    client = FakeClient(["a.txt"])
    ctx = _ctx(tmp_path, client)
    ctx.bot_data["file_browser_cache"] = BrowserCache(max_entries=1)
    update, _ = _open(ctx)
    nav = _nav_from(update)
    ctx.bot_data["file_browser_cache"].put("c2", 1, ["b.txt"])
    u = _cb(f"fbp:{nav}:0:0")
    asyncio.run(h.browse_page(u, ctx))
    assert "قديمة" in u.callback_query.edits[-1]


def test_confirmed_deletion_invalidates_browser_cache(tmp_path, monkeypatch):
    client = FakeClient(["a.txt"])
    ctx = _ctx(tmp_path, client)
    update, token = _open(ctx)
    nav = _nav_from(update)
    cache = ctx.bot_data["file_browser_cache"]
    assert cache.get(nav) is not None

    async def fake_status(client, context, conversation_id, *, allow_deleted=False):
        return {"id": conversation_id, "title": "شات"}, h.FileStatus.OK, None, None

    async def fake_delete(client, db, conversation_id):
        return h.deletion.DeletionResult(
            status=h.deletion.STATUS_DELETED,
            message=h.deletion.DELETED_MESSAGE,
            conversation_id=conversation_id,
        )

    monkeypatch.setattr(h, "_authorized_conversation_status", fake_status)
    monkeypatch.setattr(h.deletion, "delete_conversation_remote", fake_delete)
    u = _cb("deleteok:c1")
    asyncio.run(h.delete_conversation_confirm(u, ctx))
    assert cache.get(nav) is None
    assert cache.conversation_for(token.removeprefix("fbo:")) is None


def test_refresh_success_invalidates_old_snapshot_and_publishes_new(tmp_path):
    client = FakeClient(["a.txt", "b.txt"])
    ctx = _ctx(tmp_path, client)
    update, token = _open(ctx)
    old_nav = _nav_from(update)
    cache = ctx.bot_data["file_browser_cache"]
    assert cache.get(old_nav) is not None

    client.files.append("c.txt")
    u = _cb(f"fbx:{old_nav}:0")
    asyncio.run(h.browse_refresh(u, ctx))

    new_nav = _nav_from(u)
    assert new_nav != old_nav
    assert cache.get(old_nav) is None
    assert cache.get(new_nav) is not None
    assert cache.conversation_for(token.removeprefix("fbo:")) == "c1"
    _assert_old_nav_rejected(ctx, old_nav)

    page = _cb(f"fbp:{new_nav}:0:0")
    asyncio.run(h.browse_page(page, ctx))
    assert "📁 /" in page.callback_query.edits[-1]


def test_empty_refresh_invalidates_old_snapshot(tmp_path):
    client = FakeClient(["a.txt"])
    ctx = _ctx(tmp_path, client)
    update, token = _open(ctx)
    old_nav = _nav_from(update)
    cache = ctx.bot_data["file_browser_cache"]

    client.files = []
    u = _cb(f"fbx:{old_nav}:0")
    asyncio.run(h.browse_refresh(u, ctx))

    assert "ما فيهاش ملفات" in u.callback_query.edits[-1]
    assert cache.get(old_nav) is None
    assert cache.conversation_for(token.removeprefix("fbo:")) == "c1"
    callbacks = _callbacks(u.callback_query.edits_markup[-1])
    assert token in callbacks
    assert not any(
        cb.startswith(("fbp:", "fbd:", "fbf:", "fbx:", "fbb:")) for cb in callbacks
    )
    _assert_old_nav_rejected(ctx, old_nav)


def test_failed_refresh_invalidates_old_snapshot(tmp_path, monkeypatch):
    client = FakeClient(["a.txt"])
    ctx = _ctx(tmp_path, client)
    update, token = _open(ctx)
    old_nav = _nav_from(update)
    cache = ctx.bot_data["file_browser_cache"]
    _patch_listing(monkeypatch, FileListing(FileStatus.UPSTREAM_ERROR, error="boom"))

    u = _cb(f"fbx:{old_nav}:0")
    asyncio.run(h.browse_refresh(u, ctx))

    assert "boom" in u.callback_query.edits[-1]
    assert cache.get(old_nav) is None
    assert u.callback_query.edits_markup[-1] is None
    assert cache.conversation_for(token.removeprefix("fbo:")) == "c1"
    _assert_old_nav_rejected(ctx, old_nav)


def test_refresh_exception_invalidates_old_snapshot(tmp_path, monkeypatch):
    client = FakeClient(["a.txt"])
    ctx = _ctx(tmp_path, client)
    update, _ = _open(ctx)
    old_nav = _nav_from(update)
    cache = ctx.bot_data["file_browser_cache"]
    _patch_listing(monkeypatch, RuntimeError("boom"))

    u = _cb(f"fbx:{old_nav}:0")
    asyncio.run(h.browse_refresh(u, ctx))

    assert "تعذّر" in u.callback_query.edits[-1]
    assert cache.get(old_nav) is None
    assert u.callback_query.edits_markup[-1] is None
    _assert_old_nav_rejected(ctx, old_nav)


def test_open_empty_invalidates_existing_snapshot(tmp_path):
    client = FakeClient(["a.txt"])
    ctx = _ctx(tmp_path, client)
    update, token = _open(ctx)
    old_nav = _nav_from(update)
    cache = ctx.bot_data["file_browser_cache"]

    client.files = []
    u = _cb(token)
    asyncio.run(h.browse_open(u, ctx))

    assert "ما فيهاش ملفات" in u.callback_query.edits[-1]
    assert cache.get(old_nav) is None
    assert cache.conversation_for(token.removeprefix("fbo:")) == "c1"
    callbacks = _callbacks(u.callback_query.edits_markup[-1])
    assert token in callbacks
    assert not any(
        cb.startswith(("fbp:", "fbd:", "fbf:", "fbx:", "fbb:")) for cb in callbacks
    )
    _assert_old_nav_rejected(ctx, old_nav)

    client.files = ["b.txt"]
    retry = _cb(token)
    asyncio.run(h.browse_open(retry, ctx))
    new_nav = _nav_from(retry)
    assert cache.get(new_nav) is not None


def test_open_error_invalidates_existing_snapshot(tmp_path, monkeypatch):
    client = FakeClient(["a.txt"])
    ctx = _ctx(tmp_path, client)
    update, token = _open(ctx)
    old_nav = _nav_from(update)
    cache = ctx.bot_data["file_browser_cache"]
    _patch_listing(monkeypatch, FileListing(FileStatus.UPSTREAM_ERROR, error="boom"))

    u = _cb(token)
    asyncio.run(h.browse_open(u, ctx))

    assert "boom" in u.callback_query.edits[-1]
    assert cache.get(old_nav) is None
    assert u.callback_query.edits_markup[-1] is None
    _assert_old_nav_rejected(ctx, old_nav)


def test_failed_refresh_leaves_other_conversation_usable(tmp_path, monkeypatch):
    client = FakeClient(["a.txt"])
    ctx = _ctx(tmp_path, client)
    first, _ = _open(ctx, "c1")
    first_nav = _nav_from(first)
    second, second_token = _open(ctx, "c2")
    second_nav = _nav_from(second)
    cache = ctx.bot_data["file_browser_cache"]
    _patch_listing(monkeypatch, FileListing(FileStatus.UPSTREAM_ERROR, error="boom"))

    u = _cb(f"fbx:{first_nav}:0")
    asyncio.run(h.browse_refresh(u, ctx))

    assert cache.get(first_nav) is None
    assert cache.get(second_nav) is not None
    assert cache.conversation_for(second_token.removeprefix("fbo:")) == "c2"

    page = _cb(f"fbp:{second_nav}:0:0")
    asyncio.run(h.browse_page(page, ctx))
    assert "📁 /" in page.callback_query.edits[-1]
