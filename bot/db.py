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
    # TASK 54: عدد محاولات إشعار الانتهاء الفاشلة المتتالية. بيترجع 0 عند بداية دورة
    # إشعار جديدة (حالة غير منتهية جديدة) أو عند إضافة/تحديث المتابعة، وبيمنع تكرار
    # نفس الإشعار بلا حد بعد استنفاد ميزانية المحاولات.
    retry_count: int = 0
    # NTF-13: حالة انتهاء اتّبعت لتليجرام (اتقبلت) لكن تسجيلها الدائم لسه معلّق. NULL =
    # مفيش تسليم معلّق. بتتكتب بعد نجاح الإرسال وقبل التسجيل، وبتتمسح بعد التسجيل الدائم.
    pending_delivery_state: str | None = None
    # NTF-19: معرّف ثابت لكل دورة متابعة (عمود دائم `watch_seq`)، بيتولّد عند الإنشاء/التجديد.
    # التلميحات in-memory (`_marker_pending`) بتتبط بيه، فمتابعة جديدة بمعرّف جديد ما تتأثّرش
    # بتلميح قديم. مش مشتقّ من hash() ولا من الوقت.
    watch_seq: str = ""


@dataclass
class NotificationState:
    conversation_id: str
    status: str | None = None
    # آخر حالة اتّبعت/اتخطّت لها إشعار (تمنع التكرار). None = لسه ماتبلّغش عنها أبدًا.
    notified_status: str | None = None
    retry_count: int = 0
    updated_at: str | None = None


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
        # NTF-20: hook اختياري ينسّق التلميح in-memory للتسليم المعلّق قبل بدء دورة متابعة
        # جديدة. المراقب بيسجّله (زي set_owner_delivery) عشان كل مستدعي `add_watched`
        # (handlers/outbox/creation) يستفيد من غير ما يعرف المراقب.
        self.on_new_watch_lifecycle = None
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
                added_at        TEXT,
                retry_count     INTEGER NOT NULL DEFAULT 0,
                pending_delivery_state TEXT,
                watch_seq       TEXT
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
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notification_state (
                conversation_id TEXT PRIMARY KEY,
                status          TEXT,
                notified_status TEXT,
                retry_count     INTEGER NOT NULL DEFAULT 0,
                updated_at      TEXT
            );
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
        # TASK 54: عدّاد محاولات إشعار الانتهاء. عمود إضافي بقيمة افتراضية 0، فالصفوف
        # القديمة بتاخد ميزانية محاولات كاملة من غير أي فقد بيانات.
        if "retry_count" not in columns:
            self._conn.execute(
                "ALTER TABLE watched ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"
            )
        # NTF-13: علامة تسليم معلّق (write-ahead). بتتكتب **بعد** ما تيليجرام يقبل رسالة
        # انتهاء و**قبل** التسجيل الدائم، عشان إزالة المتابعة من أي مسار (أو إعادة تشغيل)
        # تكمّل التسجيل الدائم بدل ما تتسيب حالة قديمة يعيد المُبلّغ إرسالها. عمود إضافي
        # بقيمة NULL افتراضية ⇒ مفيش فقد بيانات للصفوف القديمة.
        if "pending_delivery_state" not in columns:
            self._conn.execute("ALTER TABLE watched ADD COLUMN pending_delivery_state TEXT")
        # NTF-19: معرّف دورة المتابعة (عمود إضافي غير مدمّر). الصفوف القديمة بتاخد NULL ثم
        # تتعبّى فورًا بمعرّف ثابت مولّد من SQLite (تحت)، فكل قراءة ترجّع نفس المعرّف.
        if "watch_seq" not in columns:
            self._conn.execute("ALTER TABLE watched ADD COLUMN watch_seq TEXT")
        # NTF-19: نعبّي المعرّف للصفوف القديمة بمعرّف ثابت **مولّد من SQLite** (randomblob)
        # عشان القراءات المتكرّرة ترجّع نفس المعرّف (مايتولّدش عشوائيًا في كل قراءة).
        self._conn.execute(
            "UPDATE watched SET watch_seq = lower(hex(randomblob(16))) WHERE watch_seq IS NULL"
        )
        # outbox اتعمل في 04A-4 من غير attempts؛ نضيفه لقواعد موجودة.
        outbox_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(outbox)")}
        if outbox_cols and "attempts" not in outbox_cols:
            self._conn.execute("ALTER TABLE outbox ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        # creation_jobs اتعمل في 04A-6 (جدول جديد)؛ CREATE IF NOT EXISTS فوق بيكفّي
        # للقواعد القديمة، وبنضمن عمود attempts لو الجدول موجود من نسخة أقدم.

    # ----------------------------------------------------------------- watched
    def add_watched(
        self, conversation_id: str, title: str = "", chat_id: int | None = None,
        *, new_lifecycle: bool = True,
    ) -> None:
        # TASK 54: إضافة/تحديث المتابعة = بداية دورة إشعار جديدة ⇒ نصفّر عدّاد المحاولات
        # عشان الإشعار الجديد ياخد ميزانية كاملة (مش ميزانية محاولات إشعار قديم).
        # NTF-19: `new_lifecycle=True` (الافتراضي) = دورة متابعة جديدة ⇒ معرّف جديد
        # (`watch_seq`)، فمتابعة جديدة ما تتأثّرش بتلميح in-memory قديم.
        # NTF-20: لو فيه علامة تسليم معلّق **دائمة** (تسليم ممكن تيليجرام يكون قبله بالفعل
        # بس تسجيله الدائم لسه معلّق)، ما نمسحهاش ونرميها — بنسجّلها (`notified_status=الحالة`)
        # وبنمسح العلامة **في نفس المعاملة**، قبل ما نعمل الدورة الجديدة. كده الدليل ما
        # يتفقدش (مفيش إشعار مكرّر من المُبلّغ) والدورة الجديدة تبدأ نظيفة. لو التسجيل فشل،
        # المعاملة كلها بترجع والعلامة تفضل ⇒ إعادة محاولة آمنة (مفيش حذف صامت).
        # `new_lifecycle=False` = إعادة نداء مكرّرة لنفس المتابعة (double-tap/إعادة محاولة):
        # بنحدّث العنوان/الشات بس، وبنحافظ على المعرّف والعلامة المعلّقة وعدّاد المحاولات.
        now = datetime.now(timezone.utc).isoformat()
        # NTF-20: قبل بدء دورة جديدة، ننسّق أي تلميح in-memory للتسليم المعلّق (لو المراقب
        # سجّل الـ hook). ده بيمنع فقد دليل تسليم اتّبعت فعلاً لما الـ handlers/outbox
        # يبدأوا دورة جديدة من غير ما يعرفوا المراقب.
        if new_lifecycle and self.on_new_watch_lifecycle is not None:
            self.on_new_watch_lifecycle(conversation_id)
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            if new_lifecycle:
                row = conn.execute(
                    "SELECT pending_delivery_state FROM watched WHERE conversation_id=?",
                    (conversation_id,),
                ).fetchone()
                if row is not None and row["pending_delivery_state"]:
                    # تسجيل التسليم القديم قبل بدء الدورة الجديدة (نفس المعاملة).
                    self._mark_pending_delivered(
                        conversation_id, row["pending_delivery_state"], now
                    )
                conn.execute(
                    "INSERT INTO watched"
                    "(conversation_id, title, chat_id, added_at, retry_count, watch_seq) "
                    "VALUES(?, ?, ?, ?, 0, lower(hex(randomblob(16)))) "
                    "ON CONFLICT(conversation_id) DO UPDATE SET title=excluded.title, "
                    "chat_id=COALESCE(excluded.chat_id, watched.chat_id), "
                    "added_at=COALESCE(watched.added_at, excluded.added_at), "
                    "retry_count=0, pending_delivery_state=NULL, "
                    "watch_seq=lower(hex(randomblob(16)))",
                    (conversation_id, title, chat_id, now),
                )
            else:
                conn.execute(
                    "INSERT INTO watched"
                    "(conversation_id, title, chat_id, added_at, retry_count, watch_seq) "
                    "VALUES(?, ?, ?, ?, 0, lower(hex(randomblob(16)))) "
                    "ON CONFLICT(conversation_id) DO UPDATE SET title=excluded.title, "
                    "chat_id=COALESCE(excluded.chat_id, watched.chat_id)",
                    (conversation_id, title, chat_id, now),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _mark_pending_delivered(self, conversation_id: str, status: str, now: str) -> None:
        """NTF-20: يسجّل حالة تسليم معلّقة (`notified_status`) **داخل معاملة المستدعي**
        بدون commit مستقل — يُستخدم لتسوية التسليم قبل بدء دورة متابعة جديدة."""
        self.record_notification_sent(conversation_id, status, now, _commit=False)

    def reconcile_pending_delivery(self, conversation_id: str) -> str | None:
        """NTF-20: يسوّي أي علامة تسليم معلّق **دائمة** قبل بدء دورة متابعة جديدة.

        بيرجّع الحالة اللي اتسجّلت (أو None لو مفيش علامة معلّقة). التسجيل والمسح في
        معاملة واحدة (`BEGIN IMMEDIATE`): لو التسجيل فشل، العلامة تفضل ⇒ إعادة محاولة
        آمنة. كتابة ضيّقة (عمود واحد + `notification_state`)، ما بتلمسش `watch_seq` ولا
        دورة المتابعة. المراقب بيستخدمها عشان ينسّق الدورة الجديدة مع التلميح in-memory.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT pending_delivery_state FROM watched WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if row is None or not row["pending_delivery_state"]:
                conn.commit()
                return None
            status = row["pending_delivery_state"]
            self._mark_pending_delivered(
                conversation_id, status, datetime.now(timezone.utc).isoformat()
            )
            conn.execute(
                "UPDATE watched SET pending_delivery_state=NULL WHERE conversation_id=?",
                (conversation_id,),
            )
            conn.commit()
            return status
        except Exception:
            conn.rollback()
            raise

    def set_pending_delivery(self, conversation_id: str, state: str) -> None:
        """NTF-13: علامة write-ahead — تسليم انتهاء اتّبعت (اتقبل) لكن لسه ماتسجّلش دائمًا.

        بتتكتب **بعد** نجاح الإرسال و**قبل** التسجيل الدائم. بتستخدمها إزالة المتابعة
        لإكمال التسجيل من أي مسار، والمراقب للاسترجاع بعد إعادة التشغيل. كتابة ضيّقة
        (عمود واحد) عشان مايتدهسش باقي الأعمدة.
        """
        self._conn.execute(
            "UPDATE watched SET pending_delivery_state=? WHERE conversation_id=?",
            (state, conversation_id),
        )
        self._conn.commit()

    def clear_pending_delivery(self, conversation_id: str) -> None:
        """NTF-13: يمسح علامة التسليم المعلّق (بعد نجاح التسجيل الدائم)."""
        self._conn.execute(
            "UPDATE watched SET pending_delivery_state=NULL WHERE conversation_id=?",
            (conversation_id,),
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
        """يشيل المتابعة، ويكمّل تسجيل أي تسليم معلّق — في معاملة ذرّية واحدة (NTF-15).

        لو فيه علامة تسليم معلّق (اتّبعت لتليجرام بس تسجيله الدائم فشل)، بنسجّلها في
        `notification_state` **قبل** حذف الصف، والاتنين في معاملة واحدة (`BEGIN IMMEDIATE`
        + commit/rollback). كده لو التسجيل فشل، الحذف ما بيحصلش (مفيش ازدواج صامت)،
        والاستثناء بيطلع للمستدعي. لو مفيش صف أصلاً، الحذف بيكمل عادي (سلوك متسق).
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT pending_delivery_state FROM watched WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            pending = row["pending_delivery_state"] if row else None
            if pending:
                # كتابة ضيّقة جوه نفس المعاملة (مفيش commit مستقل)، عشان التسجيل والحذف
                # ينجحوا أو يفشلوا مع بعض.
                self.record_notification_sent(
                    conversation_id, pending, datetime.now(timezone.utc).isoformat(),
                    _commit=False,
                )
            conn.execute("DELETE FROM watched WHERE conversation_id=?", (conversation_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def remove_watched_completing(
        self, conversation_id: str, pending_status: str, now: str | None = None
    ) -> bool:
        """يزيل المتابعة ويكمّل تسليمًا معلّقًا **معروفًا للمستدعي** في معاملة واحدة (NTF-17).

        زي `remove_watched` بس الحالة المعلّقة بتيجي من المستدعي (الحالة اللي اتّبعت فعلًا
        لما كتابة العلامة الدائمة نفسها فشلت). العلامة الدائمة، لو موجودة، بتاخد الأولوية
        على القيمة المارّرة. بيرجّع True لو كان فيه صف واتشال، وFalse لو مفيش صف (no-op).
        بيرمي لو التسجيل فشل (مفيش حذف جزئي — الذرّية محفوظة).
        """
        now = now or datetime.now(timezone.utc).isoformat()
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT pending_delivery_state FROM watched WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if row is None:
                conn.commit()
                return False
            status = row["pending_delivery_state"] or pending_status
            self.record_notification_sent(conversation_id, status, now, _commit=False)
            conn.execute("DELETE FROM watched WHERE conversation_id=?", (conversation_id,))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise

    def remove_watched_if_seq(self, conversation_id: str, expected_watch_seq: str) -> bool:
        """NTF-23: إزالة ذرّية **مشروطة** بمعرّف دورة المتابعة (compare-and-swap).

        بتحذف الصف بس لو `watch_seq` لسه مطابق للمعرّف الملتقَط (`expected_watch_seq`)،
        وبتكمّل أي تسليم معلّق في نفس المعاملة. بتمنع سباق الإزالة من لقطة قديمة (NTF-22
        M-1): لو دورة جديدة اتعملت أثناء `await` الشبكة، الـ `DELETE ... AND watch_seq=?`
        بيفشل (صفري) فالدورة الجديدة تفضل سليمة.

        القرار كله في جملة `DELETE` ذرّية واحدة (مفيش SELECT ثم DELETE). لو الدورة اتغيّرت
        (أو الصف مش موجود)، بنرجّع False **بدون أي أثر** — مفيش لمس للعلامة المعلّقة ولا
        `notification_state` (ما نكمّلش/نمسحش دليل دورة تانية).

        بيرجّع True لو الصف المطابق اتشال، وFalse لو الصف مش موجود أو الدورة اتغيّرت.
        بيرمي لو التسجيل فشل (المعاملة كلها بترجع، والصف بيفضل — retry آمن).
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT pending_delivery_state FROM watched "
                "WHERE conversation_id=? AND watch_seq=?",
                (conversation_id, expected_watch_seq),
            ).fetchone()
            if row is None:
                conn.commit()
                return False  # الصف مش موجود أو الدورة اتغيّرت ⇒ مفيش أثر
            pending = row["pending_delivery_state"]
            cur = conn.execute(
                "DELETE FROM watched WHERE conversation_id=? AND watch_seq=?",
                (conversation_id, expected_watch_seq),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return False  # اتغيّر بين الـ SELECT والـ DELETE ⇒ مفيش أثر
            if pending:
                # التسجيل جوه نفس المعاملة، **بعد** تثبيت الحذف المطابق (مفيش commit مستقل).
                self.record_notification_sent(
                    conversation_id, pending, datetime.now(timezone.utc).isoformat(),
                    _commit=False,
                )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise

    def list_watched(self) -> list[Watched]:
        rows = self._conn.execute(
            "SELECT conversation_id, title, last_state, chat_id, submitted_at, added_at, "
            "retry_count, pending_delivery_state, watch_seq FROM watched"
        ).fetchall()
        return [
            Watched(
                r["conversation_id"], r["title"], r["last_state"], r["chat_id"],
                r["submitted_at"], r["added_at"], r["retry_count"],
                r["pending_delivery_state"], r["watch_seq"],
            )
            for r in rows
        ]

    def get_watched(self, conversation_id: str) -> Watched | None:
        """يجيب صف متابعة واحد (بالحقول الطازجة، خاصة pending_delivery_state) أو None."""
        r = self._conn.execute(
            "SELECT conversation_id, title, last_state, chat_id, submitted_at, added_at, "
            "retry_count, pending_delivery_state, watch_seq FROM watched WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        if r is None:
            return None
        return Watched(
            r["conversation_id"], r["title"], r["last_state"], r["chat_id"],
            r["submitted_at"], r["added_at"], r["retry_count"], r["pending_delivery_state"],
            r["watch_seq"],
        )

    def increment_watched_retry(self, conversation_id: str) -> int:
        """يزوّد عدّاد محاولات إشعار الانتهاء ذرّياً ويرجّع القيمة الجديدة (TASK 54).

        الـ UPDATE والقراءة في جملة واحدة (RETURNING)، فالقرار "استنفدنا الحد؟" مبني على
        عدّاد حقيقي مش snapshot قديم — مستحيل يتخطّى الحد أو يتكرّر الإشعار النهائي.
        """
        row = self._conn.execute(
            "UPDATE watched SET retry_count=retry_count+1 WHERE conversation_id=? "
            "RETURNING retry_count",
            (conversation_id,),
        ).fetchone()
        self._conn.commit()
        return int(row["retry_count"]) if row else 0

    def increment_watched_retry_if_seq(self, conversation_id: str, expected_watch_seq: str) -> int:
        """NTF-23: يزوّد عدّاد المحاولات ذرّياً **مشروطًا** بمعرّف دورة المتابعة.

        زي `increment_watched_retry` بس بشرط `watch_seq` (compare-and-swap). لو الدورة
        اتغيّرت (متابعة جديدة أثناء await)، ما بنزوّدش العدّاد الجديد بقرار قديم —
        بنرجّع 0 (يعني «مافيش صف مطابق»). الـ UPDATE والقراءة في جملة واحدة.
        """
        row = self._conn.execute(
            "UPDATE watched SET retry_count=retry_count+1 "
            "WHERE conversation_id=? AND watch_seq=? RETURNING retry_count",
            (conversation_id, expected_watch_seq),
        ).fetchone()
        self._conn.commit()
        return int(row["retry_count"]) if row else 0

    def advance_watched_state(self, conversation_id: str, state: str) -> None:
        """يسجّل الحالة المسجَّلة ويصفّر عدّاد المحاولات (TASK 54).

        الحالة اللي بتوصل هنا دايمًا مش منتهية (المسار المنتهي بيخرج قبلها)، فتسجيلها
        معناه إن إشعار الانتهاء القديم مات أو ما اتولدش ⇒ بداية دورة إشعار جديدة بميزانية
        كاملة. التصفير والكتابة في جملة واحدة (ذرّية) عشان مفيش حالة وسطية.
        """
        self._conn.execute(
            "UPDATE watched SET last_state=?, retry_count=0 WHERE conversation_id=?",
            (state, conversation_id),
        )
        self._conn.commit()

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

    def bump_outbox_attempt(self, outbox_id: int, now: str, error: str | None = None) -> int:
        """يزوّد attempts ذرّياً ويسيب الحالة 'pending' (محاولة إرسال مابدأتش ⇒ آمنة).

        الـ UPDATE والقراءة في جملة واحدة (RETURNING)، فالقيمة الراجعة هي العدّاد الفعلي
        بعد الزيادة — حتى لو أكتر من caller نادوها. ده بيخلّي قرار "وصلنا الحد؟" مبني على
        عدّاد حقيقي مش على snapshot قديم، فمستحيل يتخطّى الحد أو يتكرّر الإشعار النهائي.
        بترجّع العدّاد الجديد.
        """
        row = self._conn.execute(
            "UPDATE outbox SET status=?, error=?, updated_at=?, attempts=attempts+1 "
            "WHERE id=? RETURNING attempts",
            (OUTBOX_PENDING, error, now, outbox_id),
        ).fetchone()
        self._conn.commit()
        return int(row["attempts"]) if row else 0

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

    # ------------------------------------------------------------- preferences
    # إعدادات عامة مفاتيح/قيم. منفصلة عن الأسرار (الأسرار متغيرات بيئة بس). تفضيل
    # الإشعارات الافتراضي «مفعّل» (الميزة شغّالة افتراضيًا)، وبيبقى موجود بعد إعادة التشغيل.
    NOTIFICATIONS_KEY = "notifications_enabled"
    _TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self._conn.commit()

    def get_notifications_enabled(self) -> bool:
        """تفضيل الإشعارات الاستباقية. الافتراضي True (مفعّل) لو المفتاح مش موجود."""
        raw = self.get_setting(self.NOTIFICATIONS_KEY)
        if raw is None:
            return True
        return raw.strip().lower() in self._TRUE_VALUES

    def set_notifications_enabled(self, enabled: bool) -> None:
        self.set_setting(self.NOTIFICATIONS_KEY, "1" if enabled else "0")

    # ------------------------------------------------- notification snapshots
    # لقطة حالة كل محادثة (للمُبلّغ العام). `notified_status` = آخر حالة اتّبعت/اتخطّى
    # لها إشعار، وده اللي يمنع التكرار. منفصلة عن جدول watched (مفيش اقتران ضمني).
    _UNCHANGED = object()

    def has_notification_states(self) -> bool:
        """هل فيه أي لقطة إشعار مخزّنة؟ استعلام EXISTS خفيف بدل تحميل كل الصفوف."""
        row = self._conn.execute(
            "SELECT 1 FROM notification_state LIMIT 1"
        ).fetchone()
        return row is not None

    def list_notification_states(self) -> dict[str, NotificationState]:
        rows = self._conn.execute(
            "SELECT conversation_id, status, notified_status, retry_count, updated_at "
            "FROM notification_state"
        ).fetchall()
        return {
            r["conversation_id"]: NotificationState(
                r["conversation_id"], r["status"], r["notified_status"],
                r["retry_count"], r["updated_at"],
            )
            for r in rows
        }

    def get_notification_state(self, conversation_id: str) -> NotificationState | None:
        row = self._conn.execute(
            "SELECT conversation_id, status, notified_status, retry_count, updated_at "
            "FROM notification_state WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None
        return NotificationState(
            row["conversation_id"], row["status"], row["notified_status"],
            row["retry_count"], row["updated_at"],
        )

    def upsert_notification_state(
        self,
        conversation_id: str,
        *,
        status=_UNCHANGED,
        notified_status=_UNCHANGED,
        retry_count=_UNCHANGED,
        updated_at: str | None = None,
        _commit: bool = True,
    ) -> None:
        """يحدّث لقطة محادثة واحدة بأعمدة ضيّقة (مفيش استبدال صف كامل ببيانات قديمة).

        بيبني `UPDATE` بالأعمدة المتمرّرة بس، فكاتب متزامن (زي المراقب بيسجّل إشعار
        نجح) مايتدهسش. الصف بيتعمل لو مش موجود (INSERT OR IGNORE)، وبعدها تحديث ضيّق.

        `_commit=False` بيخلي النداء ينضمّ لمعاملة المستدعي بدل ما يعمل commit خاص بيه
        (مستخدم في `remove_watched` عشان التسجيل والحذف يبقوا معاملة واحدة).
        """
        self._conn.execute(
            "INSERT OR IGNORE INTO notification_state(conversation_id) VALUES(?)",
            (conversation_id,),
        )
        sets: list[str] = []
        params: list[object] = []
        if status is not self._UNCHANGED:
            sets.append("status=?")
            params.append(status)
        if notified_status is not self._UNCHANGED:
            sets.append("notified_status=?")
            params.append(notified_status)
        if retry_count is not self._UNCHANGED:
            sets.append("retry_count=?")
            params.append(retry_count)
        if updated_at is not None:
            sets.append("updated_at=?")
            params.append(updated_at)
        if sets:
            params.append(conversation_id)
            self._conn.execute(
                f"UPDATE notification_state SET {', '.join(sets)} WHERE conversation_id=?",
                params,
            )
        if _commit:
            self._conn.commit()

    def bump_notification_retry(self, conversation_id: str, now: str) -> int:
        """يزوّد عدّاد محاولات إشعار فاشلة ذرّياً ويرجّع القيمة الجديدة (جملة واحدة)."""
        row = self._conn.execute(
            "INSERT INTO notification_state(conversation_id, retry_count, updated_at) "
            "VALUES(?, 1, ?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET "
            "retry_count=notification_state.retry_count+1, updated_at=excluded.updated_at "
            "RETURNING retry_count",
            (conversation_id, now),
        ).fetchone()
        self._conn.commit()
        return int(row["retry_count"]) if row else 0

    def record_notification_sent(
        self, conversation_id: str, status: str, now: str, *, _commit: bool = True
    ) -> None:
        """يسجّل إن إشعار الحالة ده اتبعت فعلًا (تليجرام أكّد النجاح).

        بيتنادى من أي مالك إشعار (المراقب أو المُبلّغ) بعد نجاح الإرسال بس، عشان المُبلّغ
        العام ما يعيدش إشعار نفس الحالة لو المتابعة اتشالت بعد ما المراقب بلّغ. النداء ده
        صريح ومقصود (مش أثر جانبي مستتر): نقطة التنسيق الوحيدة بين النظامين.

        `_commit=False` بيخلي الكتابة تنضمّ لمعاملة المستدعي (مستخدم في `remove_watched`).
        """
        self.upsert_notification_state(
            conversation_id, status=status, notified_status=status, retry_count=0,
            updated_at=now, _commit=_commit,
        )

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
