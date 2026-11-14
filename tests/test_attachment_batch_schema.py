"""OHB2-P0-A0 — اختبارات مخطّط نموذج بيانات دفعات المرفقات (المخطّط فقط).

نطاق A0: جدولان محليان جديدان (`attachment_batches`, `attachment_items`) + الترحيل
الإضافي غير المدمّر + ثابت `ATTACHMENT_BATCH_TTL`. لا دورة حياة، لا تخزين ملفات، لا
إرسال، لا اتصال بأي خدمة خارجية.

مرجع التصميم: `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` (R4) §3.3/§5/§6 (A0).
"""

import sqlite3
from datetime import timedelta

from bot import files
from bot.db import (
    ATTACHMENT_BATCH_INTENT_RECORDED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_BATCH_STATUSES,
    ATTACHMENT_BATCH_TTL,
    AWAITING_TTL,
    Database,
)


def make_db(tmp_path):
    return Database(str(tmp_path / "t.sqlite3"))


def _table_info(path, table):
    conn = sqlite3.connect(path)
    try:
        return {r[1]: r for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def _index_names(path, table):
    conn = sqlite3.connect(path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA index_list({table})")}
    finally:
        conn.close()


# ------------------------------------------------------------------ TTL constant
def test_ttl_constant_is_15_minutes_and_distinct_from_awaiting_ttl():
    # ثابت P0: 15 دقيقة بالظبط، ومنفصل عن مهلة التوجيه (10 دقايق).
    assert ATTACHMENT_BATCH_TTL == timedelta(minutes=15)
    assert ATTACHMENT_BATCH_TTL != AWAITING_TTL
    assert AWAITING_TTL == timedelta(minutes=10)


def test_status_constants_are_the_documented_set():
    # OHB2-P0-A3/D-27: أُضيفت `intent_recorded` (نيّة محلية متينة) بجانب الحالات السبع الأصلية.
    assert ATTACHMENT_BATCH_PENDING == "pending"
    assert ATTACHMENT_BATCH_INTENT_RECORDED == "intent_recorded"
    assert ATTACHMENT_BATCH_STATUSES == (
        "pending",
        "intent_recorded",
        "dispatching",
        "uncertain",
        "delivered",
        "expired",
        "rejected",
        "failed",
    )


# ------------------------------------------------------------ fresh DB creation
def test_fresh_db_creates_both_tables(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    Database(path)
    conn = sqlite3.connect(path)
    try:
        names = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()
    assert "attachment_batches" in names
    assert "attachment_items" in names


def test_batches_table_columns_and_not_null(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    Database(path)
    info = _table_info(path, "attachment_batches")
    assert set(info) == {
        "batch_id",
        "telegram_id",
        "conversation_id",
        "t0",
        "status",
        "created_at",
        "updated_at",
        "intent_text",
    }
    # الحقول الإلزامية NOT NULL (الملكية + T0 + الحالة). `batch_id` مفتاح أساسي
    # (تفرّد مفروض) بنفس نمط جداول الهوية القائمة (`TEXT PRIMARY KEY` بدون NOT NULL).
    for col in ("telegram_id", "conversation_id", "t0", "status"):
        assert info[col][3] == 1, f"{col} must be NOT NULL"
    assert info["batch_id"][5] == 1  # PK
    assert info["status"][4] == "'pending'"  # DEFAULT
    # الأعمدة الوصفية الزمنية قابلة للـ NULL. `intent_text` كمان nullable (OHB2-P0-A3/D-27).
    assert info["created_at"][3] == 0 and info["updated_at"][3] == 0
    assert info["intent_text"][3] == 0


def test_items_table_columns_and_not_null(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    Database(path)
    info = _table_info(path, "attachment_items")
    assert set(info) == {
        "item_id",
        "batch_id",
        "staging_token",
        "display_name",
        "size_bytes",
        "status",
        "created_at",
        "updated_at",
    }
    assert info["item_id"][5] == 1  # PK
    assert info["batch_id"][3] == 1  # مرجع الدفعة الأب إلزامي
    assert info["status"][3] == 1
    assert info["status"][4] == "'pending'"
    # المراجع الاختيارية قابلة للـ NULL (تُملأ في A1).
    for col in ("staging_token", "display_name", "size_bytes"):
        assert info[col][3] == 0, f"{col} should be nullable"


def test_expected_indexes_present(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    Database(path)
    assert "idx_attachment_batches_owner" in _index_names(path, "attachment_batches")
    assert "idx_attachment_items_batch" in _index_names(path, "attachment_items")


# ------------------------------------------------------------------- round-trip
def test_batch_roundtrip_defaults_and_t0_fixed(tmp_path):
    db = make_db(tmp_path)
    db.create_attachment_batch("b1", 111, "conv-a", "2026-11-11T00:00:00+00:00")
    batch = db.get_attachment_batch("b1")
    assert batch is not None
    assert batch.telegram_id == 111
    assert batch.conversation_id == "conv-a"
    assert batch.t0 == "2026-11-11T00:00:00+00:00"
    assert batch.status == ATTACHMENT_BATCH_PENDING
    assert batch.created_at is not None


def test_owner_scope_hides_batch_from_other_user(tmp_path):
    db = make_db(tmp_path)
    db.create_attachment_batch("b1", 111, "conv-a", "2026-11-11T00:00:00+00:00")
    # المالك نفسه يشوفها.
    assert db.get_attachment_batch("b1", telegram_id=111) is not None
    # مستخدم تاني **مايشوفهاش** (عزل بين المستخدمين — §5 بند 8).
    assert db.get_attachment_batch("b1", telegram_id=222) is None


def test_batches_isolated_per_conversation(tmp_path):
    db = make_db(tmp_path)
    db.create_attachment_batch("b1", 111, "conv-a", "2026-11-11T00:00:00+00:00")
    db.create_attachment_batch("b2", 111, "conv-b", "2026-11-11T00:00:00+00:00")
    assert db.get_attachment_batch("b1").conversation_id == "conv-a"
    assert db.get_attachment_batch("b2").conversation_id == "conv-b"


def test_item_roundtrip_and_list_order(tmp_path):
    db = make_db(tmp_path)
    db.create_attachment_batch("b1", 111, "conv-a", "2026-11-11T00:00:00+00:00")
    db.add_attachment_item("i1", "b1", staging_token="tok1", display_name="a.txt",
                           size_bytes=10, now="2026-11-11T00:00:01+00:00")
    db.add_attachment_item("i2", "b1", staging_token="tok2", display_name="b.txt",
                           size_bytes=20, now="2026-11-11T00:00:02+00:00")
    items = db.list_attachment_items("b1")
    assert [i.item_id for i in items] == ["i1", "i2"]
    assert items[0].staging_token == "tok1"
    assert items[0].size_bytes == 10
    assert items[0].status == ATTACHMENT_BATCH_PENDING


def test_items_isolated_per_batch(tmp_path):
    db = make_db(tmp_path)
    db.create_attachment_batch("b1", 111, "conv-a", "2026-11-11T00:00:00+00:00")
    db.create_attachment_batch("b2", 111, "conv-b", "2026-11-11T00:00:00+00:00")
    db.add_attachment_item("i1", "b1")
    db.add_attachment_item("i2", "b2")
    assert [i.item_id for i in db.list_attachment_items("b1")] == ["i1"]
    assert [i.item_id for i in db.list_attachment_items("b2")] == ["i2"]


def test_batch_id_is_primary_key_unique(tmp_path):
    db = make_db(tmp_path)
    db.create_attachment_batch("b1", 111, "conv-a", "2026-11-11T00:00:00+00:00")
    try:
        db.create_attachment_batch("b1", 222, "conv-b", "2026-11-11T00:00:00+00:00")
    except sqlite3.IntegrityError:
        pass
    else:  # pragma: no cover
        raise AssertionError("duplicate batch_id must violate the PRIMARY KEY")


def test_conversation_id_validation_hook_accepts_stored_ids(tmp_path):
    # المخطّط ما بيفرضش التحقق (نطاق A2/A3)، لكن المعرّفات المخزّنة لازم تعدّي
    # `files.is_valid_conversation_id` اللي هيفرض العزل لاحقًا.
    db = make_db(tmp_path)
    conv = "3f2a1b0c-4d5e-6f70-8192-a3b4c5d6e7f8"
    assert files.is_valid_conversation_id(conv)
    db.create_attachment_batch("b1", 111, conv, "2026-11-11T00:00:00+00:00")
    assert db.get_attachment_batch("b1").conversation_id == conv


# ------------------------------------------------------- migration / upgrade path
def test_migration_adds_tables_to_old_database_non_destructively(tmp_path):
    # قاعدة قديمة فيها `watched`/`outbox` بس (قبل A0) مع بيانات موجودة.
    path = str(tmp_path / "old.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT, chat_id INTEGER, submitted_at TEXT);"
        "CREATE TABLE user_state (telegram_id INTEGER PRIMARY KEY, awaiting_conversation_id TEXT,"
        " awaiting_kind TEXT, awaiting_at TEXT, awaiting_title TEXT);"
    )
    conn.execute("INSERT INTO watched(conversation_id, title) VALUES('c1','قديم')")
    conn.commit()
    conn.close()

    db = Database(path)
    # (1) الجدولان الجديدان اتعملوا.
    info_b = _table_info(path, "attachment_batches")
    info_i = _table_info(path, "attachment_items")
    assert "batch_id" in info_b and "item_id" in info_i
    # (2) البيانات القديمة **اتحفظت** (ترحيل غير مدمّر).
    assert db.list_watched()[0].conversation_id == "c1"
    # (3) الجداول الجديدة قابلة للاستخدام بعد الترقية.
    db.create_attachment_batch("b1", 111, "c1", "2026-11-11T00:00:00+00:00")
    db.add_attachment_item("i1", "b1")
    assert db.get_attachment_batch("b1").telegram_id == 111
    assert [i.item_id for i in db.list_attachment_items("b1")] == ["i1"]


def test_reinit_is_idempotent_and_preserves_attachment_rows(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    db1 = Database(path)
    db1.create_attachment_batch("b1", 111, "conv-a", "2026-11-11T00:00:00+00:00")
    db1.add_attachment_item("i1", "b1", staging_token="tok1")
    # إعادة الفتح على نفس المسار = إعادة تهيئة/ترحيل تاني ⇒ ما يفشلش ولا يمسح.
    db2 = Database(path)
    assert db2.get_attachment_batch("b1").batch_id == "b1"
    assert [i.item_id for i in db2.list_attachment_items("b1")] == ["i1"]
    # إنشاء الدفعة تاني بياخد PRIMARY KEY (مفيش ازدواج صامت).
    try:
        db2.create_attachment_batch("b1", 111, "conv-a", "2026-11-11T00:00:00+00:00")
    except sqlite3.IntegrityError:
        pass
    else:  # pragma: no cover
        raise AssertionError("re-init must not silently duplicate rows")


def test_existing_rows_survive_upgrade(tmp_path):
    # قاعدة فيها صفوف `watched`/`outbox` قبل الترقية ⇒ تتأكد إنها اتّحفظت بعد A0.
    path = str(tmp_path / "old.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT, chat_id INTEGER);"
        "CREATE TABLE user_state (telegram_id INTEGER PRIMARY KEY, awaiting_conversation_id TEXT,"
        " awaiting_kind TEXT);"
        "CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,"
        " chat_id INTEGER NOT NULL, text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',"
        " error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
    )
    conn.execute("INSERT INTO watched(conversation_id, title) VALUES('c1','قديم')")
    conn.execute(
        "INSERT INTO outbox(conversation_id, chat_id, text, created_at, updated_at)"
        " VALUES('c1', 9, 'برومت', 't', 't')"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    assert db.list_watched()[0].conversation_id == "c1"
    assert db.list_outbox_by_status("pending")[0].text == "برومت"


def test_migration_adds_intent_text_to_pre_a3_database(tmp_path):
    # OHB2-P0-A3/D-27: قاعدة أُنشئت قبل A3 فيها جدول `attachment_batches` **بدون**
    # `intent_text` ⇒ الترقية تضيف العمود إضافيًّا وتخلي الصفوف القديمة NULL (fail-closed).
    path = str(tmp_path / "pre_a3.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE attachment_batches (batch_id TEXT PRIMARY KEY, telegram_id INTEGER NOT NULL,"
        " conversation_id TEXT NOT NULL, t0 TEXT NOT NULL,"
        " status TEXT NOT NULL DEFAULT 'pending', created_at TEXT, updated_at TEXT);"
        "CREATE TABLE attachment_items (item_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL);"
    )
    conn.execute(
        "INSERT INTO attachment_batches(batch_id, telegram_id, conversation_id, t0)"
        " VALUES('b0', 1, 'c1', '2026-11-11T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    info = _table_info(path, "attachment_batches")
    assert "intent_text" in info
    # الصفّ القديم اتّحفظ ونصّه المصاحب NULL (بلا نيّة).
    old = db.get_attachment_batch("b0")
    assert old is not None and old.telegram_id == 1 and old.intent_text is None
    # والعمود قابل للاستخدام بعد الترقية.
    db._conn.execute(
        "UPDATE attachment_batches SET intent_text=? WHERE batch_id=?", ("نصّ", "b0")
    )
    db._conn.commit()
    assert db.get_attachment_batch("b0").intent_text == "نصّ"
