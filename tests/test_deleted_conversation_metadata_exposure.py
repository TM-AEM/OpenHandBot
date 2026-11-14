"""OHB2-RESIDUAL: إفصاح ميتاداتا/محتوى شات محذوف عبر الصندوق وقوايم المتابعة.

العيب: `delete_conversation` بتسيّب صفوف `notification_inbox` **كأثر تدقيق** (بس بتوسم
تسليمها المعلّق `superseded`)، والصفوف دي **بتحمل عنوان الشات + نص الإشعار**. وقبل الحذف
المؤكّد (نافذة `deleting`/`uncertain`) صف المتابعة كمان بيفضل بعنوانه. قبل الإصلاح،
`list_inbox`/`count_inbox`/`list_watched` كانت بترجّعها عادي ⇒ واجهة إشعارات الـ Mini App
وقوايم «متابعاتي» (بوت + Mini App) كانت بتعرض عنوان/محتوى شات **اتحذف** أو بيتم حذفه.

الإصلاح: استبعاد أي `conversation_id` عليه شاهد حذف دائم (`deleted_conversations`) من
`list_inbox`/`count_inbox` (عبر `_inbox_visibility_clause`) ومن `list_watched` — الصفوف
تفضل (أثر تدقيق + دعم الاسترجاع/الإحياء) لكن ما تظهرش ولا تتعدّ.

كل الاختبارات على قاعدة معزولة (tmp_path) وتطبيق الـ API الحقيقي؛ لا شبكة ولا تيليجرام.
"""
from __future__ import annotations

from starlette.testclient import TestClient

from bot.config import Config
from bot.db import Database
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
ORIGIN = "https://app.test"
CID = "conv-secret-1"
CID2 = "conv-ok-2"
NOW = "2026-01-01T00:00:00+00:00"
SECRET_TITLE = "TOP_SECRET_INBOX_TITLE"
SECRET_MESSAGE = "TOP_SECRET_INBOX_MESSAGE"


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


def authed(tmp_path):
    cfg = make_config(tmp_path)
    db = Database(cfg.db_path)
    client = TestClient(build_web_app(cfg, db), raise_server_exceptions=False)
    r = client.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert r.status_code == 200
    return client, db


def seed(db, cid=CID, title="عنوان", message="رسالة", event_key=None):
    return db.add_inbox_event(
        cid, title, "terminal", message, NOW, event_key=event_key, chat_id=OWNER
    )


# ------------------------------------------------------------------ DB layer
def test_deleted_conversation_inbox_rows_hidden_from_list(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed(db, CID, SECRET_TITLE, SECRET_MESSAGE, event_key="e1")
    seed(db, CID2, "OK_TITLE", "OK_MESSAGE", event_key="e2")
    db.delete_conversation(CID, NOW)
    assert db.is_deleted(CID) is True

    items = db.list_inbox()
    cids = {i.conversation_id for i in items}
    assert CID not in cids and CID2 in cids
    assert SECRET_TITLE not in str([i.title for i in items])
    assert SECRET_MESSAGE not in str([i.message for i in items])
    # الصف لسه موجود كأثر تدقيق (ما اتحذفش) لكن مخفي من العرض.
    assert db.get_inbox_item(1) is not None


def test_deleted_conversation_inbox_excluded_from_counts(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed(db, CID, SECRET_TITLE, SECRET_MESSAGE, event_key="e1")
    seed(db, CID2, "OK_TITLE", "OK_MESSAGE", event_key="e2")
    db.delete_conversation(CID, NOW)
    assert db.count_inbox() == 1
    assert db.count_inbox(unread_only=True) == 1


def test_deleted_conversation_hidden_in_archived_view_too(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    iid = seed(db, CID, SECRET_TITLE, SECRET_MESSAGE, event_key="e1")
    db.archive_inbox_item(iid, NOW)
    db.delete_conversation(CID, NOW)
    assert db.list_inbox(archived=True) == []
    assert db.count_inbox(archived=True) == 0


def test_non_deleted_conversation_unaffected(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed(db, CID2, "OK_TITLE", "OK_MESSAGE", event_key="e2")
    assert len(db.list_inbox()) == 1
    assert db.count_inbox() == 1


# ------------------------------------------------------------------ API layer
def test_miniapp_notifications_hides_deleted_conversation(tmp_path):
    client, db = authed(tmp_path)
    seed(db, CID, SECRET_TITLE, SECRET_MESSAGE, event_key="e1")
    seed(db, CID2, "OK_TITLE", "OK_MESSAGE", event_key="e2")
    db.delete_conversation(CID, NOW)

    r = client.get("/api/v1/notifications")
    assert r.status_code == 200
    body = r.json()
    joined = str(body)
    assert SECRET_TITLE not in joined and SECRET_MESSAGE not in joined
    assert CID not in joined
    assert {it["conversation_id"] for it in body["items"]} == {CID2}
    # الشارة (غير المقروء) ما تتأثّرش بالشات المحذوف.
    assert body["unread_count"] == 1


def test_miniapp_notifications_archived_view_hides_deleted(tmp_path):
    client, db = authed(tmp_path)
    iid = seed(db, CID, SECRET_TITLE, SECRET_MESSAGE, event_key="e1")
    # مسار تغيير حالة ⇒ لازم Origin مطابق، وإلا الرد 403 bad_origin ومايتأرشفش الصف
    # (وقتها الاختبار يعدّي غلط لأن الصف يفضل في الصندوق النشط مش الأرشيف).
    ra = client.post(
        f"/api/v1/notifications/{iid}/archive", headers={"Origin": ORIGIN}
    )
    assert ra.status_code == 200, ra.text
    db.delete_conversation(CID, NOW)
    r = client.get("/api/v1/notifications?archived=true")
    assert r.status_code == 200
    assert SECRET_TITLE not in str(r.json())
    assert r.json()["items"] == []


# --------------------------------------------------------- watch list exposure
def test_watch_title_hidden_while_remote_deletion_pending(tmp_path):
    """خلال نافذة deleting (شاهد فعّال، الصف لسه موجود) العنوان ما يظهرش."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched(CID, SECRET_TITLE, chat_id=OWNER)
    db.add_watched(CID2, "OK_WATCH_TITLE", chat_id=OWNER)
    db.begin_remote_deletion(CID, NOW)
    assert db.is_deleted(CID) is True
    assert db.get_watched(CID) is not None  # الصف الخام لسه موجود (استرجاع/إحياء)
    ids = {w.conversation_id for w in db.list_watched()}
    assert ids == {CID2}
    assert SECRET_TITLE not in str([w.title for w in db.list_watched()])


def test_watch_row_gone_after_confirmed_delete(tmp_path):
    """ضابط (control): الحذف المؤكّد بيمسح صف المتابعة نفسه ⇒ القايمة فاضية.

    ملاحظة: ده بيعمل pass مع أو من غير استبعاد `list_watched` الجديد (الصف مابقاش
    موجود أصلاً)؛ اللي **بيفرّق** فعلاً هو `test_watch_title_hidden_while_remote_deletion_pending`
    (نافذة deleting/uncertain والصف لسه موجود).
    """
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched(CID, SECRET_TITLE, chat_id=OWNER)
    db.delete_conversation(CID, NOW)
    assert db.list_watched() == []


def test_miniapp_watches_hides_deleted_conversation(tmp_path):
    client, db = authed(tmp_path)
    db.add_watched(CID, SECRET_TITLE, chat_id=OWNER)
    db.add_watched(CID2, "OK_WATCH_TITLE", chat_id=OWNER)
    db.begin_remote_deletion(CID, NOW)
    r = client.get("/api/v1/watches")
    assert r.status_code == 200
    body = r.json()
    assert SECRET_TITLE not in str(body)
    assert {it["id"] for it in body["items"]} == {CID2}


# --------------------------------------------- creation-job (repository) exposure
SECRET_REPO = "owner/TOP_SECRET_REPO"


def test_creation_job_list_hides_deleted_conversation(tmp_path):
    """طلب شات جديد بيحمل `repo` + `conversation_id`؛ لو الشات اتحذف مايظهرش في القايمة."""
    client, db = authed(tmp_path)
    jid = db.add_creation_job(OWNER, SECRET_REPO, "برومت", NOW)
    db.set_creation_done(jid, NOW, CID)
    jid2 = db.add_creation_job(OWNER, "owner/OK_REPO", "برومت 2", NOW)
    db.set_creation_done(jid2, NOW, CID2)
    db.delete_conversation(CID, NOW)
    assert db.is_deleted(CID) is True

    r = client.get("/api/v1/operations/creation/list")
    assert r.status_code == 200
    body = r.json()
    assert SECRET_REPO not in str(body)
    assert CID not in str(body)
    ids = {it["id"] for it in body["items"]}
    assert jid not in ids and jid2 in ids


def test_creation_job_list_hides_pending_remote_deletion(tmp_path):
    """خلال نافذة deleting (شاهد فعّال، الصف لسه) مايظهرش الطلب في قايمة الـ Mini App."""
    db = Database(str(tmp_path / "t.sqlite3"))
    jid = db.add_creation_job(OWNER, SECRET_REPO, "برومت", NOW)
    db.set_creation_done(jid, NOW, CID)
    db.begin_remote_deletion(CID, NOW)
    jobs, _ = db.list_creation_jobs_for_owner(OWNER)
    assert jobs == []
