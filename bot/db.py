"""قاعدة بيانات SQLite لحفظ الشاتات المتابَعة وحالة الحوار وصندوق الصادر."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

# حالات صندوق الصادر (outbox) — كل انتقال مع سلوك التعافي بعد إعادة التشغيل:
#   pending  : اتسجّل بثبات ولسه ماتحاولش الإرسال. آمن يتعاود بعد restart.
#   claimed  : الـ worker اخده ذرّياً (ملكه)، والـ POST لسه مابدأش. آمن يرجع
#              pending بعد restart (الإرسال مابدأش ⇒ مفيش احتمال ازدواج).
#   sending  : بدأت محاولة الإرسال والنتيجة لسه ماتحسمتش بثبات. بعد restart ⇒ unknown.
#   sent     : اتأكد نجاح الإرسال (رد POST سليم). مايتعادش أبداً.
#   unknown  : نتيجة الإرسال غامضة (timeout/انقطاع/إلغاء) وماينفعش نأكد إن
#              الـ server ماخدش البرومت ⇒ مايتعادش تلقائياً (at-most-once).
#   failed   : رفض نهائي مؤكد (رد 4xx). مايتعادش تلقائياً.

OUTBOX_PENDING = "pending"
OUTBOX_CLAIMED = "claimed"
OUTBOX_SENDING = "sending"
OUTBOX_SENT = "sent"
OUTBOX_UNKNOWN = "unknown"
OUTBOX_FAILED = "failed"
OUTBOX_DISCARDED = "discarded"

# حالات طلب الشات الجديد (creation job) — الجدول منفصل عن outbox عشان الطلب
# مالوش conversation_id لسه وقت التسجيل. نفس منطق الحجز/الغموض:
#   pending   : اتسجّل بثبات ولسه POST البدء مابدأش. آمن يتعاود بعد restart.
#   claimed   : الـ worker اخده ذرّياً (ملكه)، وPOST البدء لسه مابدأش. آمن يرجع pending.
#   starting  : بدأ POST البدء (أو استطلاع مهمة معروفة) والنتيجة لسه ماتحسمتش.
#               لو فيه task_id محفوظ ⇒ الاستطلاع (GET آمن) بس هو اللي يتعاود.
#   done      : اتأكد بدء الشات واتعرف conversation_id. مايتعادش أبداً.
#   unknown   : نتيجة البدء غامضة (timeout/انقطاع/إلغاء/بدون task_id) ⇒ مايتعادش تلقائياً.
#   failed    : رفض نهائي مؤكد (4xx) أو فشل مهمة مؤكد ⇒ مايتعادش تلقائياً.
CREATION_PENDING = "pending"
CREATION_CLAIMED = "claimed"
CREATION_STARTING = "starting"
CREATION_DONE = "done"
CREATION_UNKNOWN = "unknown"
CREATION_FAILED = "failed"
CREATION_DISCARDED = "discarded"


# مهلة أي حالة توجيه (من آخر نشاط). القرار 1: توجيه 10 دقايق.
AWAITING_TTL = timedelta(minutes=10)


# نافذة تجميع الرسايل المتتالية (القرار 2): أي رسالة جاية خلال 1.5 ثانية من آخر تحديث
# لبرومت لسه 'pending' لنفس الوجهة بتتجمّع معاه في سجل واحد (مش إرسال منفصل).
GROUP_WINDOW = timedelta(seconds=1.5)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class Watched:
    conversation_id: str
    title: str
    last_state: str | None
    chat_id: int | None = None
    # وقت (UTC ISO) آخر برومبت اتبعت للشات ده. لو موجود، المراقب ما يعلنش الانتهاء
    # غير لو لقى تقرير أحدث منه (U01). NULL = متابعة يدوية بدون برومبت.
    submitted_at: str | None = None
    added_at: str | None = None


@dataclass
class OutboxItem:
    id: int
    conversation_id: str
    chat_id: int
    text: str
    status: str
    error: str | None
    created_at: str
    updated_at: str
    attempts: int = 0


@dataclass
class CreationJob:
    id: int
    chat_id: int
    repo: str | None
    text: str
    status: str
    task_id: str | None
    conversation_id: str | None
    error: str | None
    created_at: str
    updated_at: str
    attempts: int = 0


class Database:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL + busy_timeout عشان الكتابة من الـ handlers والمراقب في وقت واحد
        # ما ترميش "database is locked".
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS watched (
                conversation_id TEXT PRIMARY KEY,
                title           TEXT NOT NULL DEFAULT '',
                last_state      TEXT,
                chat_id         INTEGER,
                submitted_at    TEXT,
                added_at        TEXT
            );
            CREATE TABLE IF NOT EXISTS user_state (
                telegram_id INTEGER PRIMARY KEY,
                awaiting_conversation_id TEXT,
                awaiting_kind            TEXT,
                awaiting_at              TEXT,
                awaiting_title           TEXT
            );
            CREATE TABLE IF NOT EXISTS outbox (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                chat_id         INTEGER NOT NULL,
                text            TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                error           TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                attempts        INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status);
            CREATE TABLE IF NOT EXISTS creation_jobs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id         INTEGER NOT NULL,
                repo            TEXT,
                text            TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                task_id         TEXT,
                conversation_id TEXT,
                error           TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                attempts        INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_creation_jobs_status ON creation_jobs(status);
            """
        )
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """يضيف الأعمدة/الجداول الجديدة لقواعد موجودة من نسخ أقدم (غير مدمّر)."""
        columns = {r["name"] for r in self._conn.execute("PRAGMA table_info(watched)")}
        if "chat_id" not in columns:
            self._conn.execute("ALTER TABLE watched ADD COLUMN chat_id INTEGER")
        state_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(user_state)")}
        if state_cols and "awaiting_at" not in state_cols:
            self._conn.execute("ALTER TABLE user_state ADD COLUMN awaiting_at TEXT")
        if state_cols and "awaiting_title" not in state_cols:
            self._conn.execute("ALTER TABLE user_state ADD COLUMN awaiting_title TEXT")
        if "submitted_at" not in columns:
            self._conn.execute("ALTER TABLE watched ADD COLUMN submitted_at TEXT")
        if "added_at" not in columns:
            self._conn.execute("ALTER TABLE watched ADD COLUMN added_at TEXT")
        # outbox اتعمل في 04A-4 من غير attempts؛ نضيفه لقواعد موجودة.
        outbox_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(outbox)")}
        if outbox_cols and "attempts" not in outbox_cols:
            self._conn.execute("ALTER TABLE outbox ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        # creation_jobs اتعمل في 04A-6 (جدول جديد)؛ CREATE IF NOT EXISTS فوق بيكفّي
        # للقواعد القديمة، وبنضمن عمود attempts لو الجدول موجود من نسخة أقدم.

    # ----------------------------------------------------------------- watched
    def add_watched(self, conversation_id: str, title: str = "", chat_id: int | None = None) -> None:
        self._conn.execute(
            "INSERT INTO watched(conversation_id, title, chat_id, added_at) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET title=excluded.title, "
            "chat_id=COALESCE(excluded.chat_id, watched.chat_id), "
            "added_at=COALESCE(watched.added_at, excluded.added_at)",
            (conversation_id, title, chat_id, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def mark_submitted(self, conversation_id: str, submitted_at: str) -> None:
        """يسجّل وقت إرسال آخر برومبت للشات (بيتحدّث مع كل برومبت جديد)."""
        self._conn.execute(
            "UPDATE watched SET submitted_at=? WHERE conversation_id=?",
            (submitted_at, conversation_id),
        )
        self._conn.commit()

    def remove_watched(self, conversation_id: str) -> None:
        self._conn.execute("DELETE FROM watched WHERE conversation_id=?", (conversation_id,))
        self._conn.commit()

    def list_watched(self) -> list[Watched]:
        rows = self._conn.execute(
            "SELECT conversation_id, title, last_state, chat_id, submitted_at, added_at FROM watched"
        ).fetchall()
        return [
            Watched(
                r["conversation_id"], r["title"], r["last_state"], r["chat_id"],
                r["submitted_at"], r["added_at"],
            )
            for r in rows
        ]

    def is_watched(self, conversation_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM watched WHERE conversation_id=?", (conversation_id,)
        ).fetchone()
        return row is not None

    def set_last_state(self, conversation_id: str, state: str) -> None:
        self._conn.execute(
            "UPDATE watched SET last_state=? WHERE conversation_id=?", (state, conversation_id)
        )
        self._conn.commit()

    def update_watched_title(self, conversation_id: str, title: str) -> bool:
        """يحدّث عنوان شات متابَع (القرار: المراقب بيخزّن العنوان الطازج).

        - تحديث السجل المطابق بس.
        - مفيش كتابة لو العنوان مش موجود/فاضي أو ما اتغيّرش (مفيش كتابات زيادة).
        - مفيش كتابة لو السجل مش موجود (اتشال/اتمسح) — ما بنعملش صف جديد.
        بيرجّع True لو فيه كتابة فعليّة، وFalse غير كده.
        """
        title = (title or "").strip()
        if not title:
            return False
        row = self._conn.execute(
            "SELECT title FROM watched WHERE conversation_id=?", (conversation_id,)
        ).fetchone()
        if row is None:
            return False
        if (row["title"] or "").strip() == title:
            return False
        self._conn.execute(
            "UPDATE watched SET title=? WHERE conversation_id=?", (title, conversation_id)
        )
        self._conn.commit()
        return True

    # -------------------------------------------------------------- user state
    # حالة توجيه الرسالة الجاية. كل حالة ليها وقت (awaiting_at) وتنتهي بعد AWAITING_TTL.
    #   reply / newchat / reposearch : لمرة واحدة (بتتستهلك أول رسالة).
    #   route : توجيه مستمر لشات معيّن؛ كل رسالة بتجدّد المهلة، وبينتهي بعد AWAITING_TTL
    #           من آخر نشاط أو بالإلغاء.
    def set_awaiting(
        self,
        telegram_id: int,
        conversation_id: str | None,
        kind: str | None,
        title: str | None = None,
        now: datetime | None = None,
    ) -> None:
        stamp = (now or datetime.now(timezone.utc)).isoformat() if kind else None
        self._conn.execute(
            "INSERT INTO user_state(telegram_id, awaiting_conversation_id, awaiting_kind, "
            "awaiting_at, awaiting_title) VALUES(?, ?, ?, ?, ?) ON CONFLICT(telegram_id) DO UPDATE SET "
            "awaiting_conversation_id=excluded.awaiting_conversation_id, "
            "awaiting_kind=excluded.awaiting_kind, awaiting_at=excluded.awaiting_at, "
            "awaiting_title=excluded.awaiting_title",
            (telegram_id, conversation_id, kind, stamp, title),
        )
        self._conn.commit()

    def clear_awaiting(self, telegram_id: int) -> None:
        self.set_awaiting(telegram_id, None, None)

    def take_awaiting(
        self, telegram_id: int, now: datetime | None = None
    ) -> tuple[str | None, str | None, str | None]:
        """يقرأ حالة التوجيه ويستهلكها (أو يجدّدها لو route) في معاملة ذرّية واحدة.

        بيرجّع (conversation_id, kind, title). لو الحالة انتهت مهلتها بيمسحها ويرجّع
        kind="expired". الحالات اللي لمرة واحدة بتتمسح، وrouting المستمر بيتجدّد وقته.
        BEGIN IMMEDIATE بياخد قفل الكتابة قبل القراءة، فرسالتين متزامنتين ما يقدروش
        ياخدوا نفس الحالة المستهلكة.
        """
        now = now or datetime.now(timezone.utc)
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT awaiting_conversation_id, awaiting_kind, awaiting_at, awaiting_title "
                "FROM user_state WHERE telegram_id=?",
                (telegram_id,),
            ).fetchone()
            result: tuple[str | None, str | None, str | None] = (None, None, None)
            if row and row["awaiting_kind"]:
                kind = row["awaiting_kind"]
                since = _parse_iso(row["awaiting_at"])
                expired = since is None or now - since > AWAITING_TTL
                if expired:
                    conn.execute(
                        "UPDATE user_state SET awaiting_conversation_id=NULL, awaiting_kind=NULL, "
                        "awaiting_at=NULL, awaiting_title=NULL WHERE telegram_id=?",
                        (telegram_id,),
                    )
                    result = (None, "expired", None)
                elif kind == "route":
                    conn.execute(
                        "UPDATE user_state SET awaiting_at=? WHERE telegram_id=?",
                        (now.isoformat(), telegram_id),
                    )
                    result = (row["awaiting_conversation_id"], kind, row["awaiting_title"])
                else:
                    conn.execute(
                        "UPDATE user_state SET awaiting_conversation_id=NULL, awaiting_kind=NULL, "
                        "awaiting_at=NULL, awaiting_title=NULL WHERE telegram_id=?",
                        (telegram_id,),
                    )
                    result = (row["awaiting_conversation_id"], kind, row["awaiting_title"])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return result

    def pop_awaiting(self, telegram_id: int) -> tuple[str | None, str | None]:
        """نفس take_awaiting من غير العنوان؛ المنتهي بيرجّع (None, None)."""
        conv, kind, _title = self.take_awaiting(telegram_id)
        if kind == "expired":
            return None, None
        return conv, kind

    def get_awaiting(self, telegram_id: int) -> tuple[str | None, str | None]:
        row = self._conn.execute(
            "SELECT awaiting_conversation_id, awaiting_kind FROM user_state WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()
        if not row:
            return None, None
        return row["awaiting_conversation_id"], row["awaiting_kind"]

    # ------------------------------------------------------------------- outbox
    def add_outbox(self, conversation_id: str, chat_id: int, text: str, now: str) -> int:
        """يسجّل البرومت في الصندوق (status='pending') قبل أي محاولة إرسال."""
        cur = self._conn.execute(
            "INSERT INTO outbox(conversation_id, chat_id, text, status, created_at, updated_at) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (conversation_id, chat_id, text, OUTBOX_PENDING, now, now),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def add_or_group_outbox(
        self,
        conversation_id: str,
        chat_id: int,
        text: str,
        now: str,
        window: timedelta | None = None,
    ) -> int:
        """تجميع (القرار 2): لو فيه برومت 'pending' لنفس الوجهة اتحدّث خلال `window`،

        نضيف النص عليه بدل ما نعمل سجل جديد. غير كده نسجّل سجل 'pending' جديد.

        الوجهة = (conversation_id, chat_id). العملية كلها جوه BEGIN IMMEDIATE عشان
        رسالتين متزامنتين مايعملوش سجلين منفصلين لنفس الدفعة. بنرجّع id السجل.
        """
        window = window if window is not None else GROUP_WINDOW
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT id, text, updated_at FROM outbox "
                "WHERE conversation_id=? AND chat_id=? AND status=? ORDER BY id DESC LIMIT 1",
                (conversation_id, chat_id, OUTBOX_PENDING),
            ).fetchone()
            now_dt = _parse_iso(now)
            row_dt = _parse_iso(row["updated_at"]) if row else None
            within = (
                row is not None
                and now_dt is not None
                and row_dt is not None
                and now_dt - row_dt <= window
            )
            if within:
                merged = row["text"] + "\n" + text
                conn.execute(
                    "UPDATE outbox SET text=?, updated_at=? WHERE id=?",
                    (merged, now, row["id"]),
                )
                out_id = int(row["id"])
            else:
                cur = conn.execute(
                    "INSERT INTO outbox(conversation_id, chat_id, text, status, created_at, updated_at) "
                    "VALUES(?, ?, ?, ?, ?, ?)",
                    (conversation_id, chat_id, text, OUTBOX_PENDING, now, now),
                )
                out_id = int(cur.lastrowid)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return out_id

    def set_outbox_status(
        self, outbox_id: int, status: str, now: str, error: str | None = None, bump: bool = False
    ) -> None:
        if bump:
            self._conn.execute(
                "UPDATE outbox SET status=?, error=?, updated_at=?, attempts=attempts+1 WHERE id=?",
                (status, error, now, outbox_id),
            )
        else:
            self._conn.execute(
                "UPDATE outbox SET status=?, error=?, updated_at=? WHERE id=?",
                (status, error, now, outbox_id),
            )
        self._conn.commit()

    def claim_outbox(self, now: str, mature_before: str | None = None) -> OutboxItem | None:
        """ياخد ذرّياً أقدم عنصر 'pending' ويحوّله 'claimed' (atomic claim).

        الـ SELECT والـ UPDATE في جملة واحدة، فمفيش سباق بين اتنين workers/iterations.
        بترجّع العنصر (بحالته بعد الحجز) أو None لو مفيش 'pending'. 'claimed' مش
        مؤهّل، فمستحيل ناخد نفس السجل مرتين. الـ 'claimed' معناه ملكية ولسه POST
        مابدأش ⇒ لو العملية اتقطعت هنا يتعافى 'pending' (آمن). الـ 'sending' بيتسجّل
        بثبات قبل الـ POST مباشرة (شوف outbox._post_claimed).

        لو `mature_before` اتحدّد، بنحجز بس السجلات اللي updated_at <= mature_before
        (نافذة تجميع القرار 2: نسيب الدفعة تستقر قبل الإرسال). القيمة None بتحافظ على
        السلوك القديم (أي 'pending').
        """
        if mature_before is None:
            sql = (
                "UPDATE outbox SET status=?, updated_at=? "
                "WHERE id=(SELECT id FROM outbox WHERE status=? ORDER BY id LIMIT 1) "
                "RETURNING *"
            )
            params = (OUTBOX_CLAIMED, now, OUTBOX_PENDING)
        else:
            sql = (
                "UPDATE outbox SET status=?, updated_at=? "
                "WHERE id=(SELECT id FROM outbox WHERE status=? AND updated_at<=? ORDER BY id LIMIT 1) "
                "RETURNING *"
            )
            params = (OUTBOX_CLAIMED, now, OUTBOX_PENDING, mature_before)
        row = self._conn.execute(sql, params).fetchone()
        self._conn.commit()
        return self._row_to_outbox(row) if row else None

    def seconds_until_mature(self, now: str, window: timedelta) -> float | None:
        """كم ثانية فاضلة لحد ما أقدم عنصر 'pending' يستوفي نافذة التجميع؟

        None لو مفيش 'pending' خالص. 0.0 لو أقدم عنصر مستوفي بالفعل (جاهز للحجز).
        """
        return self._seconds_until_mature(_parse_iso(now), window)

    def seconds_until_mature_at(self, now_dt: datetime, window: timedelta) -> float | None:
        """زي `seconds_until_mature` بس بياخد datetime محسوب مقدماً (قراءة ساعة واحدة).

        بنستخدمه في worker التجميع: نفس الطابع الزمني بيتحسب مرة واحدة وبيتمرّر هنا
        وبيتحجز بيه، فمفيش قراءتين للساعة ممكن يخلّوا التأخير غير متّسق مع حدّ النضج.
        """
        return self._seconds_until_mature(now_dt, window)

    def _seconds_until_mature(self, now_dt: datetime | None, window: timedelta) -> float | None:
        row = self._conn.execute(
            "SELECT updated_at FROM outbox WHERE status=? ORDER BY updated_at LIMIT 1",
            (OUTBOX_PENDING,),
        ).fetchone()
        if row is None:
            return None
        row_dt = _parse_iso(row["updated_at"])
        if now_dt is None or row_dt is None:
            return 0.0
        return max(0.0, (row_dt + window - now_dt).total_seconds())

    def oldest_pending_id(self) -> int | None:
        """أقدم عنصر 'pending' (للجدولة الفورية من الـ handlers) أو None."""
        row = self._conn.execute(
            "SELECT id FROM outbox WHERE status=? ORDER BY id LIMIT 1", (OUTBOX_PENDING,)
        ).fetchone()
        return int(row["id"]) if row else None

    def get_outbox(self, outbox_id: int) -> OutboxItem | None:
        row = self._conn.execute("SELECT * FROM outbox WHERE id=?", (outbox_id,)).fetchone()
        return self._row_to_outbox(row) if row else None

    def list_outbox_by_status(self, status: str) -> list[OutboxItem]:
        rows = self._conn.execute(
            "SELECT * FROM outbox WHERE status=? ORDER BY id", (status,)
        ).fetchall()
        return [self._row_to_outbox(r) for r in rows]

    def list_open_outbox(self) -> list[OutboxItem]:
        """كل البرومتات غير المنتهية (pending/claimed/sending) — للعرض والعدّ."""
        rows = self._conn.execute(
            "SELECT * FROM outbox WHERE status IN (?, ?, ?) ORDER BY id",
            (OUTBOX_PENDING, OUTBOX_CLAIMED, OUTBOX_SENDING),
        ).fetchall()
        return [self._row_to_outbox(r) for r in rows]

    def count_outbox(self, status: str | None = None) -> int:
        if status is None:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM outbox").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM outbox WHERE status=?", (status,)
            ).fetchone()
        return int(row["n"])

    @staticmethod
    def _row_to_outbox(row: sqlite3.Row) -> OutboxItem:
        return OutboxItem(
            id=row["id"],
            conversation_id=row["conversation_id"],
            chat_id=row["chat_id"],
            text=row["text"],
            status=row["status"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            attempts=row["attempts"],
        )

    # ----------------------------------------------------------- creation jobs
    def add_creation_job(self, chat_id: int, repo: str | None, text: str, now: str) -> int:
        """يسجّل طلب شات جديد (status='pending') قبل أي POST بدء (مفيش conversation_id)."""
        cur = self._conn.execute(
            "INSERT INTO creation_jobs(chat_id, repo, text, status, created_at, updated_at) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (chat_id, repo, text, CREATION_PENDING, now, now),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get_creation_job(self, job_id: int) -> CreationJob | None:
        row = self._conn.execute("SELECT * FROM creation_jobs WHERE id=?", (job_id,)).fetchone()
        return self._row_to_creation(row) if row else None

    def list_creation_jobs_by_status(self, status: str) -> list[CreationJob]:
        rows = self._conn.execute(
            "SELECT * FROM creation_jobs WHERE status=? ORDER BY id", (status,)
        ).fetchall()
        return [self._row_to_creation(r) for r in rows]

    def list_open_creation_jobs(self) -> list[CreationJob]:
        """كل الطلبات غير المنتهية (pending/claimed/starting) — للعرض والعدّ."""
        rows = self._conn.execute(
            "SELECT * FROM creation_jobs WHERE status IN (?, ?, ?) ORDER BY id",
            (CREATION_PENDING, CREATION_CLAIMED, CREATION_STARTING),
        ).fetchall()
        return [self._row_to_creation(r) for r in rows]

    def count_creation_jobs(self, status: str | None = None) -> int:
        if status is None:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM creation_jobs").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM creation_jobs WHERE status=?", (status,)
            ).fetchone()
        return int(row["n"])

    def claim_creation_job(self, now: str) -> CreationJob | None:
        """حجز ذرّي لأقدم طلب شات جديد 'pending' ⇒ 'claimed' (جملة واحدة)."""
        row = self._conn.execute(
            "UPDATE creation_jobs SET status=?, updated_at=? "
            "WHERE id=(SELECT id FROM creation_jobs WHERE status=? ORDER BY id LIMIT 1) "
            "RETURNING *",
            (CREATION_CLAIMED, now, CREATION_PENDING),
        ).fetchone()
        self._conn.commit()
        return self._row_to_creation(row) if row else None

    def oldest_pending_creation_id(self) -> int | None:
        row = self._conn.execute(
            "SELECT id FROM creation_jobs WHERE status=? ORDER BY id LIMIT 1", (CREATION_PENDING,)
        ).fetchone()
        return int(row["id"]) if row else None

    def set_creation_status(
        self, job_id: int, status: str, now: str, error: str | None = None, bump: bool = False
    ) -> None:
        if bump:
            self._conn.execute(
                "UPDATE creation_jobs SET status=?, error=?, updated_at=?, attempts=attempts+1 "
                "WHERE id=?",
                (status, error, now, job_id),
            )
        else:
            self._conn.execute(
                "UPDATE creation_jobs SET status=?, error=?, updated_at=? WHERE id=?",
                (status, error, now, job_id),
            )
        self._conn.commit()

    def set_creation_starting(self, job_id: int, now: str, task_id: str | None = None) -> None:
        """يسجّل 'starting' فوراً قبل POST البدء. الـ task_id يتسجّل بس لو الـ API رجّعه."""
        if task_id:
            self._conn.execute(
                "UPDATE creation_jobs SET status=?, task_id=?, updated_at=? WHERE id=?",
                (CREATION_STARTING, task_id, now, job_id),
            )
        else:
            self._conn.execute(
                "UPDATE creation_jobs SET status=?, updated_at=? WHERE id=?",
                (CREATION_STARTING, now, job_id),
            )
        self._conn.commit()

    def set_creation_done(self, job_id: int, now: str, conversation_id: str) -> None:
        self._conn.execute(
            "UPDATE creation_jobs SET status=?, conversation_id=?, updated_at=? WHERE id=?",
            (CREATION_DONE, conversation_id, now, job_id),
        )
        self._conn.commit()

    @staticmethod
    def _row_to_creation(row: sqlite3.Row) -> CreationJob:
        return CreationJob(
            id=row["id"],
            chat_id=row["chat_id"],
            repo=row["repo"],
            text=row["text"],
            status=row["status"],
            task_id=row["task_id"],
            conversation_id=row["conversation_id"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            attempts=row["attempts"],
        )

    def close(self) -> None:
        self._conn.close()

    # -------------------------------------------------------- integrity / upkeep
    def quick_check(self) -> bool:
        """فحص سريع للتكامل (PRAGMA quick_check). True = سليم.

        بيرمي sqlite3.DatabaseError لو فيه تلف في القرص/الملف — ما بنسكتش عليه.
        """
        row = self._conn.execute("PRAGMA quick_check").fetchone()
        return bool(row) and row[0] == "ok"

    def integrity_check(self) -> bool:
        """فحص تكامل كامل (PRAGMA integrity_check). True = سليم."""
        row = self._conn.execute("PRAGMA integrity_check").fetchone()
        return bool(row) and row[0] == "ok"

    def optimize(self) -> None:
        """تحسين دوري: ANALYZE + تفريغ مساحة (incremental vacuum لو مفعّل)."""
        self._conn.execute("PRAGMA optimize")
        try:
            self._conn.execute("PRAGMA incremental_vacuum")
        except sqlite3.OperationalError:
            # incremental_vacuum بيتطلب auto_vacuum؛ لو مش مفعّل نتجاهله بهدوء.
            pass
        self._conn.commit()

    def checkpoint(self, mode: str = "TRUNCATE") -> None:
        """يرجّع بيانات WAL لقاعدة البيانات الرئيسية ويقصّر الـ WAL (upkeep آمن)."""
        self._conn.execute(f"PRAGMA wal_checkpoint({mode})")
        self._conn.commit()

    def run_startup_maintenance(self) -> bool:
        """صيانة تشغيل آمنة: فحص سريع ثم تحسين + checkpoint.

        بيرجّع True لو الفحص السريع سليم، وFalse لو القاعدة تالفة (وبيسجّل تحذير).
        ما بيرميش: أي خطأ فحص/صيانة بيتسجّل بس عشان البوت يشتغل لو القاعدة سليمة.
        """
        try:
            healthy = self.quick_check()
        except sqlite3.DatabaseError as exc:
            log.error("فحص قاعدة البيانات فشل (%s)", type(exc).__name__)
            return False
        if not healthy:
            log.error("قاعدة البيانات فحصها فشل (quick_check != ok)")
            return False
        try:
            self.optimize()
            self.checkpoint()
        except sqlite3.Error as exc:
            # الصيانة مش حرجة: القاعدة سليمة، فمنعطّلش البوت عشانها.
            log.warning("صيانة قاعدة البيانات اتخطّت (%s)", type(exc).__name__)
        return True
