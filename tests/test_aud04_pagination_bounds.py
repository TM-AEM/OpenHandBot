"""AUD-04: حدود الترقيم — منع overflow في `page × size` عبر كل نقاط النهاية المُرقّمة.

الثغرة الأصلية: `page=2**62` كان بيتضرب في حجم الصفحة ⇒ offset أكبر من نطاق SQLite
(64-bit) ⇒ `OverflowError` جوّه SQLite ⇒ HTTP 500. الإصلاح بيتحقق من `page` و`offset`
قبل أي ضرب/ربط، ويرجّع 400 منظّم.

الاختبارات بتستخدم الكود الحقيقي (التطبيق + الخدمة + قاعدة SQLite حقيقية) مع عميل
OpenHands وهمي — مفيش شبكة ولا خدمات خارجية.
"""
from __future__ import annotations

import asyncio

from starlette.testclient import TestClient

from bot.config import Config
from bot.db import (
    INBOX_PAGE_SIZE,
    MAX_PAGE,
    MAX_SQLITE_INT,
    Database,
)
from bot.web import build_web_app
from bot.web import services as services_module
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
ORIGIN = "https://app.test"

# الحالة الأصلية اللي بلّغ عنها التدقيق.
PAGE_2_62 = 2**62
# أرقام ضخمة: أكبر من 64-bit، وقريبة من الحد، وأكبر من سقف الصفحة المسموح.
HUGE = 10**25
ABOVE_MAX_PAGE = MAX_PAGE + 1
NEAR_MAX_SQLITE = MAX_SQLITE_INT


class FakeClient:
    """عميل OpenHands وهمي: قوايم محادثات/مستودعات ثابتة، مفيش شبكة."""

    def __init__(self, items=None, repos=None) -> None:
        self.items = items if items is not None else []
        self.repos = repos if repos is not None else []

    async def search_conversations(self, limit=100, page_id=None):
        return {"items": list(self.items), "next_page_id": None}

    async def search_repositories(self, query="", limit=100):
        return list(self.repos)

    async def get_conversations(self, ids):
        return []

    async def get_current_user(self):
        return {"id": "owner-uuid"}


def make_config(tmp_path, **over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        db_path=str(tmp_path / "t.sqlite3"),
        mini_app_cookie_secure=False,
        mini_app_allowed_origins=frozenset({ORIGIN}),
    )
    base.update(over)
    return Config(**base)


def build(tmp_path, db, client=None):
    app = build_web_app(make_config(tmp_path), db, client=client)
    return TestClient(app, raise_server_exceptions=False)


def authed(tmp_path, db, client=None):
    c = build(tmp_path, db, client)
    r = c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert r.status_code == 200
    return c


def _seed(tmp_path):
    """قاعدة حقيقية فيها إشعار ومتابعة وطلب إنشاء — تغطّي كل نقاط النهاية."""
    db = Database(str(tmp_path / "seed.sqlite3"))
    db.add_inbox_item("c1", "t", "terminal", "m", "t0")
    db.add_watched("c1", title="T")
    db.add_creation_job(OWNER, "repo", "hello", "2026-01-01T00:00:00+00:00")
    return db


PAGINATED_ENDPOINTS = (
    "/api/v1/notifications",
    "/api/v1/operations/creation/list",
    "/api/v1/conversations",
    "/api/v1/watches",
    "/api/v1/repositories",
)


# --------------------------------------------------------- رفض القيم غير الصالحة
def test_huge_page_rejected_on_every_paginated_endpoint(tmp_path):
    """page=2**62 (حالة التدقيق) و10**25 ⇒ 400 على كل نقطة نهاية، مش 500."""
    db = _seed(tmp_path)
    c = authed(tmp_path, db, FakeClient())
    for path in PAGINATED_ENDPOINTS:
        for page in (PAGE_2_62, HUGE, NEAR_MAX_SQLITE):
            r = c.get(f"{path}?page={page}")
            assert r.status_code == 400, f"{path}?page={page} ⇒ {r.status_code} (متوقع 400)"
            assert r.json()["error"] == "bad_request"


def test_page_above_max_page_rejected(tmp_path):
    db = _seed(tmp_path)
    c = authed(tmp_path, db, FakeClient())
    for path in PAGINATED_ENDPOINTS:
        r = c.get(f"{path}?page={ABOVE_MAX_PAGE}")
        assert r.status_code == 400, f"{path}?page={ABOVE_MAX_PAGE} ⇒ {r.status_code}"


def test_zero_and_negative_pages(tmp_path):
    """الصفر صالح (الأولى)؛ السالب مرفوض بـ 400 على كل النقاط."""
    db = _seed(tmp_path)
    c = authed(tmp_path, db, FakeClient())
    for path in PAGINATED_ENDPOINTS:
        assert c.get(f"{path}?page=0").status_code == 200, path
        assert c.get(f"{path}?page=-1").status_code == 400, path


def test_non_numeric_page_rejected(tmp_path):
    db = _seed(tmp_path)
    c = authed(tmp_path, db, FakeClient())
    for path in PAGINATED_ENDPOINTS:
        assert c.get(f"{path}?page=abc").status_code == 400, path


def test_missing_page_defaults_to_first(tmp_path):
    db = _seed(tmp_path)
    c = authed(tmp_path, db, FakeClient())
    for path in PAGINATED_ENDPOINTS:
        r = c.get(path)
        assert r.status_code == 200, path
        assert r.json()["page"] == 0


# --------------------------------------------------------- الحدود المسموحة بالضبط
def test_max_page_allowed_and_just_above_rejected(tmp_path):
    db = _seed(tmp_path)
    c = authed(tmp_path, db, FakeClient())
    for path in PAGINATED_ENDPOINTS:
        assert c.get(f"{path}?page={MAX_PAGE}").status_code == 200, path
        assert c.get(f"{path}?page={MAX_PAGE + 1}").status_code == 400, path


def test_normal_first_middle_final_pages(tmp_path):
    """سلوك الترقيم الطبيعي محفوظ: صفحات 0/1/2 مع عناصر كفاية."""
    db = Database(str(tmp_path / "many.sqlite3"))
    for i in range(25):
        db.add_inbox_item(f"c{i}", "t", "terminal", f"m{i}", "t0")
    c = authed(tmp_path, db, FakeClient())
    p0 = c.get("/api/v1/notifications?page=0").json()
    p1 = c.get("/api/v1/notifications?page=1").json()
    p2 = c.get("/api/v1/notifications?page=2").json()
    assert p0["page"] == 0 and len(p0["items"]) == INBOX_PAGE_SIZE and p0["has_more"] is True
    assert p1["page"] == 1 and len(p1["items"]) == INBOX_PAGE_SIZE
    # الصفحة الأخيرة: أقل من حجم الصفحة ومفيش المزيد.
    assert len(p2["items"]) == 5 and p2["has_more"] is False
    # مفيش تداخل: معرّفات الصفحات مختلفة.
    ids0 = {it["id"] for it in p0["items"]}
    ids1 = {it["id"] for it in p1["items"]}
    assert ids0.isdisjoint(ids1)


def test_empty_page_falls_back_to_first(tmp_path):
    """رقم صفحة كبير لكن داخل السقف ⇒ صفحة فاضية ⇒ ترجع للأولى (السلوك القائم)."""
    db = _seed(tmp_path)
    c = authed(tmp_path, db, FakeClient())
    r = c.get(f"/api/v1/notifications?page={MAX_PAGE}").json()
    assert r["page"] == 0 and len(r["items"]) == 1


# --------------------------------------------------------- ضمان عدم تنفيذ SQL بإزاحة ضخمة
def test_no_sql_offset_exceeds_sqlite_range(tmp_path):
    """نلتقط الـ offset الفعلي الواصل لقاعدة البيانات عند أقصى صفحة مسموحة."""
    db = _seed(tmp_path)
    seen: list[int] = []
    real = db.list_inbox

    def spy(*, limit, offset, unread_only, archived):
        seen.append(offset)
        return real(limit=limit, offset=offset, unread_only=unread_only, archived=archived)

    db.list_inbox = spy  # type: ignore[assignment]
    c = authed(tmp_path, db, FakeClient())
    assert c.get(f"/api/v1/notifications?page={MAX_PAGE}").status_code == 200
    assert seen and all(0 <= o <= MAX_SQLITE_INT for o in seen)


def test_service_rejects_overflow_before_sql(tmp_path):
    """طبقة الخدمة ترفض الإزاحة الضخمة بـ ValidationError (مفيش ربط لـ SQLite)."""
    import pytest

    db = _seed(tmp_path)
    svc = services_module.MiniAppService(make_config(tmp_path), db, client=FakeClient())
    for page in (PAGE_2_62, HUGE, ABOVE_MAX_PAGE):
        with pytest.raises(services_module.ValidationError):
            svc.list_notifications(page=page)


def test_db_layer_defence_in_depth_rejects_bad_offset(tmp_path):
    """آخر خط دفاع: طبقة القاعدة ترفض limit/offset خارج نطاق 64-bit بـ ValueError."""
    import pytest

    db = _seed(tmp_path)
    with pytest.raises(ValueError):
        db.list_inbox(limit=INBOX_PAGE_SIZE, offset=MAX_SQLITE_INT + 1)
    with pytest.raises(ValueError):
        db.list_inbox(limit=INBOX_PAGE_SIZE, offset=-1)
    with pytest.raises(ValueError):
        db.list_creation_jobs_for_owner(OWNER, page=MAX_PAGE + 1)


def test_overflow_boundary_arithmetic_documented():
    """توثيق حدّ الضرب: page=2**62 × حجم الصفحة يتجاوز نطاق SQLite (سبب الـ 500 القديم)."""
    assert PAGE_2_62 * INBOX_PAGE_SIZE > MAX_SQLITE_INT
    assert MAX_PAGE * INBOX_PAGE_SIZE <= MAX_SQLITE_INT


def test_page_offset_helper_rejects_non_int(tmp_path):
    import pytest

    for bad in (None, "abc", 1.5, [1], {}):
        with pytest.raises(services_module.ValidationError):
            services_module._page_offset(bad, 10)


def test_page_offset_helper_rejects_overflow_offset(tmp_path):
    """AUD-04: حتى لو مرّ `page` داخل `[0, MAX_PAGE]`، لازم نتحقق إن `page × size`
    نفسه جوه نطاق SQLite — فرع `offset > MAX_SQLITE_INT` مش كود ميّت."""
    import pytest

    with pytest.raises(services_module.ValidationError):
        services_module._page_offset(MAX_PAGE, MAX_SQLITE_INT)
    # حدّ صحيح: أعلى (page,size) لسه داخل النطاق ⇒ مسموح.
    assert services_module._page_offset(MAX_PAGE, INBOX_PAGE_SIZE) == MAX_PAGE * INBOX_PAGE_SIZE


# --------------------------------------------------------- حدود حجم الصفحة (AUD-04)
def test_oversized_page_size_rejected_at_db_layer(tmp_path):
    """حجم صفحة ضخم لازم يترفض قبل الـ binding (`size+1` ممكن يعدّي نطاق SQLite)."""
    import pytest

    db = _seed(tmp_path)
    with pytest.raises(ValueError):
        db.list_creation_jobs_for_owner(OWNER, page=0, page_size=MAX_SQLITE_INT)
    with pytest.raises(ValueError):
        db.list_creation_jobs_for_owner(OWNER, page=0, page_size=0)
    with pytest.raises(ValueError):
        db.list_creation_jobs_for_owner(OWNER, page=0, page_size=-3)


def test_multiplication_overflow_boundary(tmp_path):
    """حدّ الضرب: أقصى صفحة مسموحة × حجم الصفحة يفضل داخل نطاق SQLite؛
    أي (page,size) يتعدّاه يترفض قبل الوصول لـ SQL."""
    import pytest

    db = _seed(tmp_path)
    # (MAX_PAGE, INBOX_PAGE_SIZE) داخل النطاق ⇒ مسموح (صفحة فاضية، مش خطأ).
    assert MAX_PAGE * INBOX_PAGE_SIZE <= MAX_SQLITE_INT
    assert db.list_inbox(limit=INBOX_PAGE_SIZE, offset=MAX_PAGE * INBOX_PAGE_SIZE) == []
    # أكبر من نطاق SQLite ⇒ مرفوض (لا OverflowError).
    with pytest.raises(ValueError):
        db.list_inbox(limit=INBOX_PAGE_SIZE, offset=MAX_SQLITE_INT + 1)


def test_service_rejects_invalid_page_on_every_endpoint(tmp_path):
    """كل دوال الخدمة المُرقّمة ترفض page السالب/الضخم بـ ValidationError
    (بدل التكميم الصامت لصفر) — اتساق كامل عبر المسارات."""
    import pytest

    db = _seed(tmp_path)
    svc = services_module.MiniAppService(make_config(tmp_path), db, client=FakeClient())
    for bad in (-1, PAGE_2_62, HUGE, MAX_PAGE + 1):
        for call in (
            lambda: svc.list_notifications(page=bad),
            lambda: asyncio.run(svc.list_conversations(page=bad)),
            lambda: svc.list_creation_jobs(bad),
            lambda: svc.list_watches(page=bad),
            lambda: asyncio.run(svc.list_repositories(page=bad)),
        ):
            with pytest.raises(services_module.ValidationError):
                call()


def test_negative_page_never_silently_clamped_to_first(tmp_path):
    """AUD-04: صفحة سالبة ⇒ رفض منظّم، مش صفحة أولى مضلّلة (مفيش تكميم صامت)."""
    db = _seed(tmp_path)
    c = authed(tmp_path, db, FakeClient())
    for path in PAGINATED_ENDPOINTS:
        r = c.get(f"{path}?page=-1")
        assert r.status_code == 400, path
        assert r.json()["error"] == "bad_request", path


def test_invalid_input_never_reaches_sql_as_offset(tmp_path):
    """إثبات أن المدخل غير الصالح ما يوصلش SQL كـ LIMIT/OFFSET مطلقًا:
    نلفّ db.list_inbox ونتأكد إنه ما اتناداش خالص عند صفحة ضخمة/سالبة."""
    db = _seed(tmp_path)
    calls: list[tuple] = []
    real = db.list_inbox

    def spy(*, limit, offset, unread_only, archived):
        calls.append((limit, offset))
        return real(limit=limit, offset=offset, unread_only=unread_only, archived=archived)

    db.list_inbox = spy  # type: ignore[assignment]
    c = authed(tmp_path, db, FakeClient())
    for bad in (PAGE_2_62, HUGE, -1, ABOVE_MAX_PAGE):
        assert c.get(f"/api/v1/notifications?page={bad}").status_code == 400
    assert calls == []  # مفيش أي استعلام اتنفّذ بقيمة غير صالحة
