"""OHB2-09-A2-04: مراجعة كاش هوية المالك (FileService / IdentityCache).

بعد الفحص المصدري: `OpenHandsClient` بيربط اعتماد خدمة واحد غير قابل للتغيير
(`Authorization: Bearer <api key>` بتتثبّت عند البناء)، ومفيش أي مسار بيبدّل
الاعتماد أو جلسة المستخدم على مستوى العميل. بالتالي هوية `/users/me` ثابتة طول عمر
العميل، والكاش (المقيّد بالكائن) آمن. الاختبارات دي بتثبت:

- Cache hit: نداء `/users/me` **واحد** عبر عمليات كتير.
- Cache miss + فشل مؤقّت ما بيسمّمش الكاش (أول نجاح لاحق بيتخزّن).
- تزامن أول قراءة: نداء واحد بس.
- إعادة إنشاء الخدمة ⇒ كاش جديد (نداء جديد) — مفيش تسريب بين عميلين.
- عدم تطابق/غياب المالك ⇒ فشل مغلق (مفيش تحويل الفشل لنجاح).
- فشل `/users/me` ما بيبقاش نجاح تفويض.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from bot.errors import ApiError
from bot.files import FileService, FileStatus, IdentityCache

OWNER_UUID = "owner-uuid-123"


class CountingClient:
    """عميل وهمي بيعدّ نداءات `/users/me` وبيتحكّم في نتيجتها."""

    def __init__(self, *, uid=OWNER_UUID, me_error=None, conv_owner=OWNER_UUID,
                 convs_present=True, delay=0.0):
        self._uid = uid
        self._me_error = me_error
        self._conv_owner = conv_owner
        self._convs_present = convs_present
        self._delay = delay
        self.me_calls = 0

    async def get_current_user(self):
        self.me_calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._me_error is not None:
            raise self._me_error
        return {"id": self._uid} if self._uid else {}

    async def get_conversations(self, ids):
        if not self._convs_present:
            return []
        conv = {"id": "c1"}
        if self._conv_owner is not None:
            conv["created_by_user_id"] = self._conv_owner
        return [conv]


def test_identity_cache_hit_single_call():
    client = CountingClient()
    cache = IdentityCache(client)
    results = [asyncio.run(cache.owner_id()) for _ in range(5)]
    assert results == [OWNER_UUID] * 5
    assert client.me_calls == 1  # نداء واحد بس


def test_identity_cache_failure_not_cached_then_success_cached():
    client = CountingClient(me_error=ApiError("upstream", 503))
    cache = IdentityCache(client)
    assert asyncio.run(cache.owner_id()) is None  # فشل ⇒ None (fail closed)
    assert asyncio.run(cache.owner_id()) is None
    assert client.me_calls == 2  # الفشل ما اتخزّنش
    # أول نجاح لاحق بيتخزّن.
    client._me_error = None
    assert asyncio.run(cache.owner_id()) == OWNER_UUID
    assert asyncio.run(cache.owner_id()) == OWNER_UUID
    assert client.me_calls == 3  # النجاح اتخزّن ⇒ مفيش نداء رابع


def test_identity_cache_missing_id_not_cached():
    client = CountingClient(uid=None)
    cache = IdentityCache(client)
    assert asyncio.run(cache.owner_id()) is None
    assert asyncio.run(cache.owner_id()) is None
    assert client.me_calls == 2  # هوية ناقصة ما اتخزّنتش


def test_identity_cache_concurrent_first_lookup_single_call():
    client = CountingClient(delay=0.05)
    cache = IdentityCache(client)

    async def run():
        return await asyncio.gather(*(cache.owner_id() for _ in range(10)))

    results = asyncio.run(run())
    assert results == [OWNER_UUID] * 10
    assert client.me_calls == 1  # القفل منع سيل النداءات


def test_identity_cache_scoped_per_client_recreation():
    client = CountingClient()
    cache1 = IdentityCache(client)
    asyncio.run(cache1.owner_id())
    assert client.me_calls == 1
    # خدمة/كاش جديد لنفس العميل = نداء تاني (مفيش حالة عالمية مشتركة).
    cache2 = IdentityCache(client)
    asyncio.run(cache2.owner_id())
    assert client.me_calls == 2


def test_identity_cache_rebuilds_when_client_object_changes():
    """M13 regression (BATCH-C FC3): كاش الهوية المشترك في البوت (`handlers._identity_cache`)
    **مقيّد بالعميل**: لو كائن العميل اتغيّر (بناء جديد)، الكاش القديم مايُستخدمش — كاش
    جديد ⇒ نداء `/users/me` تاني. قبل التقوية كان الفحص `entry[0] is client` ناقص، فكاش
    عميل قديم كان يفضل مستخدمًا عبر عميل جديد (تسريب/تلوّث هوية بين اعتمادين)."""
    import bot.handlers as h

    client1 = CountingClient()
    ctx = SimpleNamespace(bot_data={"client": client1})
    c1 = h._identity_cache(ctx)
    assert asyncio.run(c1.owner_id()) == OWNER_UUID
    assert client1.me_calls == 1
    assert h._identity_cache(ctx) is c1  # نفس العميل ⇒ نفس الكاش

    # العميل اتغيّر (بناء جديد) ⇒ لازم كاش جديد (مش الكاش القديم).
    client2 = CountingClient()
    ctx.bot_data["client"] = client2
    c2 = h._identity_cache(ctx)
    assert c2 is not c1
    assert asyncio.run(c2.owner_id()) == OWNER_UUID
    assert client2.me_calls == 1
    assert client1.me_calls == 1  # الكاش القديم ما اتناداش تاني


# --------------------------------------------------------- FileService integration
def test_fileservice_authorize_uses_cached_identity():
    client = CountingClient()
    svc = FileService(client)
    for _ in range(4):
        conv, status = asyncio.run(svc.authorize("c1"))
        assert status is FileStatus.OK
    assert client.me_calls == 1  # كل عمليات الملفات بتشارك نفس الكاش


def test_fileservice_owner_mismatch_forbidden():
    client = CountingClient(conv_owner="someone-else")
    conv, status = asyncio.run(FileService(client).authorize("c1"))
    assert conv is None and status is FileStatus.UNAUTHORIZED


def test_fileservice_null_owner_forbidden():
    client = CountingClient(conv_owner=None)
    conv, status = asyncio.run(FileService(client).authorize("c1"))
    assert conv is None and status is FileStatus.UNAUTHORIZED


def test_fileservice_identity_failure_is_not_success():
    """OHB2-SW-04: فشل `/users/me` (upstream) يفضل `UPSTREAM_ERROR` مش `UNAUTHORIZED`.

    لسه **مفيش نجاح كاذب** (conv=None) — بس التفصيل محفوظ عشان ما يتلبّسش عطل خدمة
    بوصف «رفض تفويض عادي». ده اللي كان بيسبب 403 بدل 502 قبل الإصلاح.
    """
    client = CountingClient(me_error=ApiError("upstream", 503))
    conv, status = asyncio.run(FileService(client).authorize("c1"))
    assert conv is None and status is FileStatus.UPSTREAM_ERROR  # مفيش نجاح كاذب


def test_fileservice_identity_unknown_is_unauthorized_not_upstream():
    """تحكّم مقابل: غياب الهوية (`{}`) يفضل `UNAUTHORIZED` (مش upstream)."""
    client = CountingClient(uid=None)
    conv, status = asyncio.run(FileService(client).authorize("c1"))
    assert conv is None and status is FileStatus.UNAUTHORIZED


# ------------------------------------------------- credential-model proof
def test_client_credential_is_fixed_at_construction():
    """إثبات إن اعتماد العميل ثابت: الهيدر بيتثبّت من مُعامل البناء، ومفيش تبديل اعتماد.

    ده أساس أمان الكاش: طول ما الاعتماد ثابت، `/users/me` ثابتة، فالكاش المقيّد
    بالعميل ما بيخلطش هويات. (لو اتحقّق شرط "تبديل الاعتماد مستحيل بالبناء" يسقط،
    لازم نعيد تقييم الكاش.)
    """
    import inspect

    import httpx

    from bot import openhands_client as oc

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"id": OWNER_UUID})

    client = oc.OpenHandsClient("https://example.test", "secret-key", transport=httpx.MockTransport(handler))
    asyncio.run(client.get_current_user())
    asyncio.run(client.get_current_user())
    assert seen == ["Bearer secret-key", "Bearer secret-key"]
    # مفيش واجهة عامة لتبديل الاعتماد.
    for banned in ("set_token", "set_api_key", "login", "set_credential", "reauthenticate"):
        assert not hasattr(client, banned), banned
    src = inspect.getsource(oc.OpenHandsClient)
    assert "Authorization" in src
    assert "def set_api_key" not in src and "def set_token" not in src


def test_miniapp_service_shares_single_users_me_across_operations():
    """كل عمليات الشات (تفاصيل/تكلفة/ملفات) بتشارك كاش هوية واحد ⇒ نداء `/users/me` واحد."""
    import httpx
    from starlette.testclient import TestClient

    from bot.config import Config
    from bot.openhands_client import OpenHandsClient
    from bot.web import build_web_app
    from tests._miniapp_helpers import BOT_TOKEN, make_init_data

    calls = {"me": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/users/me":
            calls["me"] += 1
            return httpx.Response(200, json={"id": OWNER_UUID})
        if path == "/api/v1/app-conversations":
            return httpx.Response(200, json=[{"id": "c1", "created_by_user_id": OWNER_UUID}])
        if path.endswith("/events/search"):
            return httpx.Response(200, json={"items": []})
        if path.endswith("/files"):
            return httpx.Response(200, json=["a.py"])
        return httpx.Response(404, json={"detail": "no"})

    client = OpenHandsClient("https://example.test", "k", transport=httpx.MockTransport(handler))
    cfg = Config(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({555}),
        owner_id=555,
        mini_app_cookie_secure=False,
    )
    tc = TestClient(build_web_app(cfg, None, client=client), raise_server_exceptions=False)
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(555)}).status_code == 200
    assert tc.get("/api/v1/conversations/c1").status_code == 200
    assert tc.get("/api/v1/conversations/c1/cost").status_code == 200
    assert tc.get("/api/v1/conversations/c1/files").status_code == 200
    assert calls["me"] == 1  # كاش مشترك عبر العمليات
