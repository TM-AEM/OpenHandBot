"""جلسات الـ Mini App بعد التحقق من initData (OHB2-05 / OHB2-PHASE1A).

جلسة = توكن عشوائي غير قابل للتخمين (opaque). التوكن **الخام** بيفضل في الكوكي بس؛
السيرفر **ما بيخزّنش** التوكن الخام أبدًا — بيخزّن **هاش** SHA-256 بس (`token_hash`).
كده أي تسريب للقاعدة ما بيكشفش توكنات جلسات صالحة، ومفيش توقيع أو أسرار في العميل.

**OHB2-PHASE1A:** لما يتوفّر كائن `Database` (الحالة الإنتاجية دايمًا)، التخزين بقى
**دائم في نفس قاعدة SQLite** (نفس مالك العملية الواحد) بدل in-memory. النتيجة: الجلسات
الصالحة بتنجو من إعادة تشغيل العملية/الخدمة، والانتهاء والإلغاء (logout) بيفضلوا فعّالين
بعد إعادة التشغيل. كل عملية = معاملة صغيرة على نفس الاتصال (`with conn`) — مفيش نداء
شبكة جوه أي معاملة، ومفيش worker/قاعدة إضافية.

لو ما اتمرّرش `db` (سياقات مستقلة/اختبارات فقط — مش الإنتاج)، بنرجع لمخزن **في الذاكرة**
بس بنفس الواجهة، عشان التوافق للخلف ما يتكسرش. الإنتاج بيمرّر القاعدة دايمًا.
"""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

_TOKEN_BYTES = 32


def hash_token(token: str) -> str:
    """SHA-256 hex للتوكن. دالة حتمية (بدون سر/ملح) عشان نلاقي الصف بالتوكن الخام.

    التوكن نفسه عشوائي 256-بت، فالبحث بالهاش مباشر وآمن؛ وده معناه إن التوكن الخام
    ما بيتخزّنش ولا بيتسجّلش في أي مكان."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Session:
    token: str
    user_id: int
    created_at: float
    expires_at: float
    profile: dict = field(default_factory=dict)


class SessionStore:
    """مخزن جلسات دائم فوق كائن `Database` المملوك للعملية (مفيش اتصال تاني).

    - `create`: يولّد توكن عشوائي ويخزّن هاشه بس + ختم انتهاء من السيرفر.
    - `get`: يدوّر على **هاش** التوكن، ويرفض المنتهي (fail closed).
    - `revoke`: يحذف الصف ⇒ الإلغاء دائم وينجو من restart.
    - `reset`: يمسح كل الجلسات (يُستخدم في الاختبارات).

    من غير `db` ⇒ رجوع لمخزن في الذاكرة (توافق للخلف للسياقات المستقلة/الاختبارات فقط).
    """

    def __init__(self, ttl: int, db=None) -> None:
        self._ttl = max(1, int(ttl))
        self._db = db
        self._mem: dict[str, Session] = {}

    # ------------------------------------------------------------- lifecycle
    def create(self, user_id: int, profile: dict | None = None, now: float | None = None) -> Session:
        current = now if now is not None else time.time()
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        session = Session(
            token=token,
            user_id=int(user_id),
            created_at=current,
            expires_at=current + self._ttl,
            profile=dict(profile or {}),
        )
        if self._db is None:
            self._mem[hash_token(token)] = session
            self._prune_mem(current)
            return session
        # الكتابة لازم تنجح قبل ما نرجّع الجلسة (ما نرجعش جلسة غير مخزّنة ⇒ فشل مغلق).
        self._db.add_web_session(
            hash_token(token),
            session.user_id,
            session.created_at,
            session.expires_at,
            json.dumps(session.profile, ensure_ascii=False, separators=(",", ":")),
        )
        self._prune_best_effort(current)
        return session

    def get(self, token: str | None, now: float | None = None) -> Session | None:
        if not token:
            return None
        current = now if now is not None else time.time()
        if self._db is None:
            session = self._mem.get(hash_token(token))
            if session is None:
                return None
            if session.expires_at <= current:
                self._mem.pop(hash_token(token), None)
                return None
            return session
        try:
            row = self._db.get_web_session(hash_token(token), current)
        except Exception:  # noqa: BLE001 — خطأ قاعدة ⇒ fail closed (مفيش مصادقة)
            return None
        if row is None:
            return None
        user_id, created_at, expires_at, profile_json = row
        try:
            profile = json.loads(profile_json) if profile_json else {}
        except (ValueError, TypeError):
            profile = {}
        if not isinstance(profile, dict):
            profile = {}
        return Session(
            token=token,
            user_id=user_id,
            created_at=created_at,
            expires_at=expires_at,
            profile=profile,
        )

    def revoke(self, token: str | None) -> bool:
        """يلغي الجلسة. يرجّع `True` لو الإلغاء **اتأكّد** (أو مفيش حاجة تُلغى)،

        و`False` لو فشل حذف الصف من القاعدة. المستدعي (logout) لازم يبلّغ بفشل صريح
        بدل ما يدّعي نجاح تسجيل خروج، لأن الصف ممكن يفضل سارٍ لحد الـ TTL.
        """
        if not token:
            return True
        if self._db is None:
            self._mem.pop(hash_token(token), None)
            return True
        try:
            self._db.delete_web_session(hash_token(token))
        except Exception:  # noqa: BLE001 — الفشل يترجّع كـ False بدل ما يبلع نجاحًا كاذبًا
            # ما نبلعش الخطأ بصمت: لو الحذف فشل، الصف ممكن يفضل سارٍ لحد الـ TTL،
            # فبنسجّل تحذير بلا أي سر (نوع الخطأ بس) عشان يبان في التشغيل.
            log.warning("فشل إلغاء جلسة الـ Mini App (%s)", "db_error")
            return False
        return True

    def reset(self) -> None:
        if self._db is None:
            self._mem.clear()
            return
        try:
            self._db.prune_web_sessions(float("inf"))
        except Exception:  # noqa: BLE001
            pass

    # -------------------------------------------------------------- internals
    def _prune_mem(self, now: float) -> None:
        expired = [h for h, s in self._mem.items() if s.expires_at <= now]
        for h in expired:
            self._mem.pop(h, None)

    def _prune_best_effort(self, now: float) -> None:
        try:
            self._db.prune_web_sessions(now)
        except Exception:  # noqa: BLE001 — التنظيف مش حرج
            pass
