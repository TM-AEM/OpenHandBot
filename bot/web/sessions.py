"""جلسات الـ Mini App بعد التحقق من initData (OHB2-05).

جلسة = توكن عشوائي غير قابل للتخمين (opaque) بيتخزّن **في الذاكرة** بس. مفيش أي
بيانات حساسة في الكوكي نفسه؛ الكوكي بيحمل التوكن، والسيرفر بيدوّر عليه. كده مفيش
توقيع أو أسرار ممكن تتسرّب للعميل، ومفيش بيانات مصادقة في localStorage.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

_TOKEN_BYTES = 32


@dataclass(frozen=True)
class Session:
    token: str
    user_id: int
    created_at: float
    expires_at: float
    profile: dict = field(default_factory=dict)


class SessionStore:
    """مخزن جلسات في الذاكرة مع TTL. مقصود إنه in-memory: عملية واحدة، مفيش مشاركة."""

    def __init__(self, ttl: int) -> None:
        self._ttl = max(1, int(ttl))
        self._sessions: dict[str, Session] = {}

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
        self._sessions[token] = session
        self._prune(current)
        return session

    def get(self, token: str | None, now: float | None = None) -> Session | None:
        if not token:
            return None
        current = now if now is not None else time.time()
        session = self._sessions.get(token)
        if session is None:
            return None
        if session.expires_at <= current:
            self._sessions.pop(token, None)
            return None
        return session

    def revoke(self, token: str | None) -> None:
        if token:
            self._sessions.pop(token, None)

    def reset(self) -> None:
        self._sessions.clear()

    def _prune(self, now: float) -> None:
        expired = [t for t, s in self._sessions.items() if s.expires_at <= now]
        for token in expired:
            self._sessions.pop(token, None)
