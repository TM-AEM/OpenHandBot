"""قاعدة بيانات SQLite لحفظ الشاتات المتابَعة وحالة الحوار وصندوق الصادر."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

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


@dataclass
class Watched:
    conversation_id: str
    title: str
    last_state: str | None
    chat_id: int | None = None


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
                chat_id         INTEGER
            );
            CREATE TABLE IF NOT EXISTS user_state (
                telegram_id INTEGER PRIMARY KEY,
                awaiting_conversation_id TEXT,
                awaiting_kind            TEXT
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
        # outbox اتعمل في 04A-4 من غير attempts؛ نضيفه لقواعد موجودة.
        outbox_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(outbox)")}
        if outbox_cols and "attempts" not in outbox_cols:
            self._conn.execute("ALTER TABLE outbox ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        # creation_jobs اتعمل في 04A-6 (جدول جديد)؛ CREATE IF NOT EXISTS فوق بيكفّي
        # للقواعد القديمة، وبنضمن عمود attempts لو الجدول موجود من نسخة أقدم.

    # ----------------------------------------------------------------- watched
    def add_watched(self, conversation_id: str, title: str = "", chat_id: int | None = None) -> None:
        self._conn.execute(
            "INSERT INTO watched(conversation_id, title, chat_id) VALUES(?, ?, ?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET title=excluded.title, "
            "chat_id=COALESCE(excluded.chat_id, watched.chat_id)",
            (conversation_id, title, chat_id),
        )
        self._conn.commit()

    def remove_watched(self, conversation_id: str) -> None:
        self._conn.execute("DELETE FROM watched WHERE conversation_id=?", (conversation_id,))
        self._conn.commit()

    def list_watched(self) -> list[Watched]:
        rows = self._conn.execute(
            "SELECT conversation_id, title, last_state, chat_id FROM watched"
        ).fetchall()
        return [
            Watched(r["conversation_id"], r["title"], r["last_state"], r["chat_id"]) for r in rows
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

    # -------------------------------------------------------------- user state
    def set_awaiting(self, telegram_id: int, conversation_id: str | None, kind: str | None) -> None:
        self._conn.execute(
            "INSERT INTO user_state(telegram_id, awaiting_conversation_id, awaiting_kind) "
            "VALUES(?, ?, ?) ON CONFLICT(telegram_id) DO UPDATE SET "
            "awaiting_conversation_id=excluded.awaiting_conversation_id, "
            "awaiting_kind=excluded.awaiting_kind",
            (telegram_id, conversation_id, kind),
        )
        self._conn.commit()

    def clear_awaiting(self, telegram_id: int) -> None:
        self.set_awaiting(telegram_id, None, None)

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

    def claim_outbox(self, now: str) -> OutboxItem | None:
        """ياخد ذرّياً أقدم عنصر 'pending' ويحوّله 'claimed' (atomic claim).

        الـ SELECT والـ UPDATE في جملة واحدة، فمفيش سباق بين اتنين workers/iterations.
        بترجّع العنصر (بحالته بعد الحجز) أو None لو مفيش 'pending'. 'claimed' مش
        مؤهّل، فمستحيل ناخد نفس السجل مرتين. الـ 'claimed' معناه ملكية ولسه POST
        مابدأش ⇒ لو العملية اتقطعت هنا يتعافى 'pending' (آمن). الـ 'sending' بيتسجّل
        بثبات قبل الـ POST مباشرة (شوف outbox._post_claimed).
        """
        row = self._conn.execute(
            "UPDATE outbox SET status=?, updated_at=? "
            "WHERE id=(SELECT id FROM outbox WHERE status=? ORDER BY id LIMIT 1) "
            "RETURNING *",
            (OUTBOX_CLAIMED, now, OUTBOX_PENDING),
        ).fetchone()
        self._conn.commit()
        return self._row_to_outbox(row) if row else None

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
