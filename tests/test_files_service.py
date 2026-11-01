"""اختبارات طبقة الملفات الآمنة (OHB2-09-01).

بتغطّي: التفويض (fail closed)، allowlist المسارات، رفض المسارات الخطِرة (مطلق/اجتياز/
NUL/خط عكسي/غير مطبّع)، التصنيف (ثنائي/غير UTF-8/كبير/قص)، والحالات المنظّمة.
بتستخدم عميل وهمي (FakeClient) — مفيش شبكة.
"""
from __future__ import annotations

import asyncio

import pytest

from bot.errors import ApiError
from bot.files import (
    FileService,
    FileStatus,
    classify_text,
    is_listed_path,
    is_safe_workspace_path,
    is_valid_conversation_id,
)

OWNER = "owner-uuid-123"
OTHER = "someone-else-uuid"


class FakeClient:
    """عميل OpenHands وهمي: هوية + شاتات + قوايم ملفات + محتوى نصي."""

    def __init__(self, *, me=None, convs=None, files=None, contents=None, errors=None):
        self._me = me if me is not None else {"id": OWNER}
        self._convs = convs if convs is not None else {}
        self._files = files or {}
        self._contents = contents or {}
        self._errors = errors or {}
        self.calls: list[str] = []

    async def get_current_user(self):
        if "me" in self._errors:
            raise self._errors["me"]
        self.calls.append("me")
        return self._me

    async def get_conversations(self, ids):
        if "convs" in self._errors:
            raise self._errors["convs"]
        return [self._convs[i] for i in ids if i in self._convs]

    async def list_files(self, conversation_id, path=""):
        if "files" in self._errors:
            raise self._errors["files"]
        return list(self._files.get(conversation_id, []))

    async def read_file_text(self, conversation_id, file_path):
        # الطريقة غير المحدودة (قديمة). مسار FileService مابيستخدمهاش خلاص —
        # بنسجّل أي نداء ليها عشان اختبار "مفيش رجوع" يفشل لو حصل.
        self.calls.append("read_file_text")
        if "read" in self._errors:
            raise self._errors["read"]
        return self._contents.get(file_path)

    async def read_file_text_bounded(self, conversation_id, file_path, max_response_bytes=None):
        # النسخة المحدودة اللي FileService بيستخدمها فعلاً.
        self.calls.append("read_file_text_bounded")
        if "read" in self._errors:
            raise self._errors["read"]
        if "read_bounded" in self._errors:
            raise self._errors["read_bounded"]
        return self._contents.get(file_path)


def run(coro):
    return asyncio.run(coro)


def _conv(created_by=OWNER):
    return {"id": "c1", "created_by_user_id": created_by, "selected_repository": "o/r"}


def svc(**kw):
    return FileService(FakeClient(**kw))


# ------------------------------------------------------- conversation id safety
@pytest.mark.parametrize("cid", ["c1", "0bfdc4119eaf423cb39fb61c76b218d4", "a-b_c"])
def test_valid_conversation_ids(cid):
    assert is_valid_conversation_id(cid)


@pytest.mark.parametrize(
    "cid", ["", None, "a/b", "a b", "..", "../x", "a" * 65, "a\x00b", "a:b"]
)
def test_invalid_conversation_ids(cid):
    assert not is_valid_conversation_id(cid)


# ----------------------------------------------------------- path safety (pure)
@pytest.mark.parametrize("p", ["a.py", "dir/a.py", ".github/workflows/ci.yml", "a-b/c_d.txt"])
def test_safe_paths(p):
    assert is_safe_workspace_path(p)


@pytest.mark.parametrize(
    "p",
    [
        "",
        None,
        "/etc/hostname",
        "/workspace/project/a.py",
        "../../../../etc/hostname",
        "a/../../b",
        "a/./b",
        "a//b",
        "a/",
        "/a",
        "..",
        ".",
        "a\\b",
        "a\x00b",
        "a\tb",
        "a" * 1025,
    ],
)
def test_unsafe_paths(p):
    assert not is_safe_workspace_path(p)


def test_is_listed_path_requires_exact_membership():
    listed = ["a.py", "dir/b.py"]
    assert is_listed_path("a.py", listed)
    assert not is_listed_path("a.py ", listed)          # مسافة زايدة ⇒ مش مطابق
    assert not is_listed_path("other.py", listed)        # مش في القايمة
    assert not is_listed_path("/etc/hostname", listed)   # مطلق
    assert not is_listed_path("../../etc/hostname", listed)


# --------------------------------------------------------------- classify_text
def test_classify_ok_plain():
    st, text, trunc, size = classify_text("hello")
    assert st is FileStatus.OK and text == "hello" and trunc is False and size == 5


def test_classify_empty_is_ok():
    st, text, trunc, size = classify_text("")
    assert st is FileStatus.OK and text == "" and trunc is False and size == 0


def test_classify_binary_on_nul():
    st, _, _, _ = classify_text("abc\x00def")
    assert st is FileStatus.BINARY


def test_classify_not_utf8_on_replacement_char():
    st, _, _, _ = classify_text("bad \ufffd byte")
    assert st is FileStatus.NOT_UTF8


def test_classify_too_large_by_bytes():
    st, text, _, size = classify_text("x" * 10, max_bytes=5)
    assert st is FileStatus.TOO_LARGE and text == "" and size == 10


def test_classify_truncates_by_chars():
    st, text, trunc, _ = classify_text("abcdef", preview_chars=3)
    assert st is FileStatus.OK and text == "abc" and trunc is True


# ----------------------------------------------------------- ownership (fail closed)
def test_list_files_ok():
    res = run(svc(convs={"c1": _conv()}, files={"c1": ["a.py", "dir/b.py"]}).list_files("c1"))
    assert res.status == FileStatus.OK and res.files == ("a.py", "dir/b.py")


def test_list_files_drops_unsafe_listed_paths():
    res = run(
        svc(convs={"c1": _conv()}, files={"c1": ["ok.py", "/etc/passwd", "../x", "a\x00b"]})
        .list_files("c1")
    )
    assert res.status == FileStatus.OK and res.files == ("ok.py",)


def test_list_files_denies_other_owner():
    res = run(svc(convs={"c1": _conv(created_by=OTHER)}).list_files("c1"))
    assert res.status == FileStatus.UNAUTHORIZED


def test_list_files_denies_when_created_by_missing():
    conv = {"id": "c1"}  # مفيش created_by_user_id ⇒ ممنوع (fail closed)
    res = run(svc(convs={"c1": conv}).list_files("c1"))
    assert res.status == FileStatus.UNAUTHORIZED


def test_list_files_denies_when_identity_unknown():
    res = run(svc(me={}, convs={"c1": _conv()}).list_files("c1"))
    assert res.status == FileStatus.UNAUTHORIZED


def test_list_files_denies_when_me_errors():
    res = run(svc(convs={"c1": _conv()}, errors={"me": ApiError("x", 500)}).list_files("c1"))
    assert res.status == FileStatus.UNAUTHORIZED


def test_list_files_not_found_for_unknown_conversation():
    res = run(svc(convs={}).list_files("c1"))
    assert res.status == FileStatus.NOT_FOUND


def test_list_files_rejects_bad_conversation_id():
    res = run(svc(convs={"c1": _conv()}).list_files("a/b"))
    assert res.status == FileStatus.NOT_FOUND


def test_list_files_upstream_error_is_structured():
    res = run(svc(convs={"c1": _conv()}, errors={"files": ApiError("مش متاح", 503)}).list_files("c1"))
    assert res.status == FileStatus.UPSTREAM_ERROR and res.error


# ------------------------------------------------------------- read_preview flow
def _readable(**kw):
    base = dict(
        convs={"c1": _conv()},
        files={"c1": ["a.py", "dir/b.py", "empty.txt"]},
        contents={"a.py": "print('hi')\n", "dir/b.py": "x = 1\n", "empty.txt": ""},
    )
    base.update(kw)
    return svc(**base)


def test_read_preview_ok():
    res = run(_readable().read_preview("c1", "a.py"))
    assert res.status == FileStatus.OK and res.text == "print('hi')\n" and res.path == "a.py"


def test_read_preview_empty_file_is_ok():
    res = run(_readable().read_preview("c1", "empty.txt"))
    assert res.status == FileStatus.OK and res.text == "" and res.truncated is False


def test_read_preview_rejects_absolute_path_before_fetch():
    res = run(_readable().read_preview("c1", "/etc/hostname"))
    assert res.status == FileStatus.INVALID_PATH


def test_read_preview_rejects_traversal_before_fetch():
    res = run(_readable().read_preview("c1", "../../../../etc/hostname"))
    assert res.status == FileStatus.INVALID_PATH


def test_read_preview_rejects_unlisted_but_safe_path():
    res = run(_readable().read_preview("c1", "not_in_list.py"))
    assert res.status == FileStatus.NOT_FOUND


def test_read_preview_denies_other_owner_before_any_read():
    res = run(_readable(convs={"c1": _conv(created_by=OTHER)}).read_preview("c1", "a.py"))
    assert res.status == FileStatus.UNAUTHORIZED


def test_read_preview_upstream_read_error():
    res = run(_readable(errors={"read": ApiError("فشل", 500)}).read_preview("c1", "a.py"))
    assert res.status == FileStatus.UPSTREAM_ERROR


def test_read_preview_non_string_response_is_upstream_error():
    # read_file_text بيرجّع None للرد غير النصي ⇒ UPSTREAM_ERROR (مش ملف فاضي).
    res = run(_readable(contents={"a.py": None}).read_preview("c1", "a.py"))
    assert res.status == FileStatus.UPSTREAM_ERROR


def test_read_preview_binary_and_utf8_and_large():
    s = _readable(
        files={"c1": ["bin.dat", "bad.txt", "big.txt"]},
        contents={"bin.dat": "a\x00b", "bad.txt": "x\ufffdy", "big.txt": "z" * 100},
    )
    assert run(s.read_preview("c1", "bin.dat")).status is FileStatus.BINARY
    assert run(s.read_preview("c1", "bad.txt")).status is FileStatus.NOT_UTF8
    big = FileService(
        FakeClient(
            convs={"c1": _conv()},
            files={"c1": ["big.txt"]},
            contents={"big.txt": "z" * 100},
        ),
        max_bytes=10,
    )
    res = run(big.read_preview("c1", "big.txt"))
    assert res.status is FileStatus.TOO_LARGE


# ------------------------------------------- integration over the real client
def test_integration_over_real_client_and_mock_transport():
    """مسار كامل: FileService فوق OpenHandsClient الحقيقي مع MockTransport.

    بيثبت إن الدوال الجديدة (`get_current_user` / `read_file_text`) + التحقق المحلي
    شغالين مع بعض من غير شبكة.
    """
    import httpx

    from bot.openhands_client import OpenHandsClient

    seen = {"files": 0, "read": 0}

    class _AsyncBody(httpx.AsyncByteStream):
        def __init__(self, data: bytes) -> None:
            self._data = data

        async def __aiter__(self):
            yield self._data

    def handler(request):
        path = request.url.path
        if path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": OWNER, "role": "owner"})
        if path == "/api/v1/app-conversations":
            return httpx.Response(200, json=[{"id": "c1", "created_by_user_id": OWNER}])
        if path.endswith("/files"):
            seen["files"] += 1
            return httpx.Response(200, json=["src/main.py", "/etc/passwd"])
        if path.endswith("/file"):
            seen["read"] += 1
            assert request.url.params.get("file_path") == "src/main.py"
            # جسم بثّي حقيقي: العميل بقى يقرا `aiter_raw()` (بدون فكّ ضغط)،
            # فمينفعش نستخدم `Response(json=...)` (بيتقرا مقدمًا ⇒ StreamConsumed).
            import json as _json

            payload = _json.dumps("print('hi')\n").encode()
            return httpx.Response(200, stream=_AsyncBody(payload))
        return httpx.Response(404, json={"detail": "no"})

    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(handler)
    )
    service = FileService(client)
    listing = run(service.list_files("c1"))
    assert listing.status is FileStatus.OK and listing.files == ("src/main.py",)
    content = run(service.read_preview("c1", "src/main.py"))
    assert content.status is FileStatus.OK and content.text == "print('hi')\n"
    assert seen["files"] == 2 and seen["read"] == 1
    # مسار مطلق مستحيل يوصل للـ endpoint (اترفض محليًا قبل أي نداء شبكة).
    before = seen["read"]
    assert run(service.read_preview("c1", "/etc/passwd")).status is FileStatus.INVALID_PATH
    assert seen["read"] == before

