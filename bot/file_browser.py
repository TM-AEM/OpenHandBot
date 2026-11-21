"""OHB2-BOT-FILE-BROWSER: شجرة مجلدات + ترقيم ثابت فوق قايمة مسارات مسطّحة.

الـ OpenHands Cloud V1 بيرجّع **قايمة مسارات نسبية مسطّحة** (`GET /app-conversations/{id}/files`)،
مفيش مدخلات مجلدات ولا صفحات من الـ API. الموديول ده بيبني الشجرة **محليًا** (زي ما الـ Mini App
بيعمل في `bot/web/static/files.js::buildTree`) ويحتفظ بلقطة محدودة في الذاكرة للترقيم الثابت.

حدود الذاكرة (نفس فلسفة `bot/file_cache.py`):
- عدد لقطات محدود + مجموع أحرف محدود + TTL.
- مفيش تحميل متكرر للقايمة الكاملة لكل صفحة: اللقطة بتتبني مرة عند الفتح/التحديث.
- الـ API نفسه بيرجّع القايمة كاملة، فمفيش طريقة لتجنّب تحميلها مرة واحدة؛ بنحمّلها **مرة واحدة**
  لكل جلسة تصفّح ونرقّم محليًا (trade-off موثّق).
"""
from __future__ import annotations

import hashlib
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass

from .files import is_safe_workspace_path

PAGE_SIZE = 10
MAX_ENTRIES = 16
MAX_TOTAL_CHARS = 50_000
MAX_TOKENS = 128
STATE_TTL_SECONDS = 30 * 60


@dataclass(frozen=True)
class BrowserState:
    """لقطة تصفّح ثابتة لشات واحد.

    `dirs` مرتّبة تصاعديًا و`""` (الجذر) أولها. `subdirs[dir]` = مسارات المجلدات الفرعية
    الكاملة المرتّبة، و`dir_files[dir]` = مسارات الملفات المباشرة في المجلد (مش المتداخلة).
    """

    nav: str
    conversation_id: str
    owner_id: int
    dirs: tuple[str, ...]
    dir_index: dict[str, int]
    subdirs: dict[str, tuple[str, ...]]
    dir_files: dict[str, tuple[str, ...]]
    created_at: float

    def entries(self, dir_path: str) -> tuple[tuple[str, str, int], ...]:
        """مدخلات مجلد: المجلدات الأول (مرتّبة) وبعدها الملفات (مرتّبة).

        العنصر = (النوع، المسار الكامل، الفهرس الهدف). للمجلد الفهرس = فهرس المجلد
        العالمي في `dirs`؛ للملف الفهرس = موقعه داخل ملفات هذا المجلد.
        """
        out: list[tuple[str, str, int]] = []
        for child in self.subdirs.get(dir_path, ()):
            out.append(("dir", child, self.dir_index[child]))
        for index, path in enumerate(self.dir_files.get(dir_path, ())):
            out.append(("file", path, index))
        return tuple(out)

    def page_count(self, dir_path: str) -> int:
        count = len(self.entries(dir_path))
        return max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)

    def clamp_page(self, dir_path: str, page: int) -> int:
        return min(max(0, int(page)), self.page_count(dir_path) - 1)

    def page_entries(self, dir_path: str, page: int) -> tuple[tuple[str, str, int], ...]:
        entries = self.entries(dir_path)
        start = self.clamp_page(dir_path, page) * PAGE_SIZE
        return entries[start : start + PAGE_SIZE]


def parent_path(path: str) -> str:
    """المجلد الأب لمسار مجلد (الجذر `""` هو أب كل شيء في المستوى الأول)."""
    return path.rsplit("/", 1)[0] if "/" in path else ""


def build_state(
    nav: str,
    conversation_id: str,
    owner_id: int,
    paths,
    *,
    now: float | None = None,
) -> BrowserState:
    """يبني شجرة من مسارات نسبية مسطّحة.

    المسارات غير الآمنة تُسقط (fail closed) بنفس `is_safe_workspace_path` المستخدم في
    `FileService.list_files`. مفيش اختلاق مجلدات فارغة: المجلد يظهر بس لو مسار ملف
    حقيقي بيمرّ بيه.
    """
    dirs_set: set[str] = {""}
    subdirs: dict[str, set[str]] = {}
    dir_files: dict[str, set[str]] = {}
    clean = sorted({p for p in (paths or ()) if is_safe_workspace_path(p)})
    for path in clean:
        parts = path.split("/")
        parent = ""
        for segment in parts[:-1]:
            child = segment if not parent else f"{parent}/{segment}"
            dirs_set.add(child)
            subdirs.setdefault(parent, set()).add(child)
            parent = child
        dir_files.setdefault(parent, set()).add(path)
    dirs = tuple(sorted(dirs_set))
    return BrowserState(
        nav=nav,
        conversation_id=conversation_id,
        owner_id=int(owner_id),
        dirs=dirs,
        dir_index={path: index for index, path in enumerate(dirs)},
        subdirs={path: tuple(sorted(values)) for path, values in subdirs.items()},
        dir_files={path: tuple(sorted(values)) for path, values in dir_files.items()},
        created_at=time.monotonic() if now is None else float(now),
    )


def _state_chars(state: BrowserState) -> int:
    return sum(len(path) for path in state.dirs) + sum(
        len(path) for files in state.dir_files.values() for path in files
    )


class BrowserCache:
    """ذاكرة لقطات التصفّح + ربط رموز قصيرة بمعرّفات الشاتات.

    الرمز (`token_for`) ثابت لكل شات (SHA-256 مختصر) عشان زر «الملفات» يفضل شغّال
    من غير ما نضع معرّف الشات الطويل في `callback_data` (DEF-010). رمز التصفّح (`nav`)
    عشوائي لكل لقطة، واللقطة نفسها بتفضل صالحة عبر الصفحات/المجلدات لحد الإخلاء أو
    الـ TTL أو التحديث.
    """

    def __init__(
        self,
        *,
        max_entries: int = MAX_ENTRIES,
        max_total_chars: int = MAX_TOTAL_CHARS,
        max_tokens: int = MAX_TOKENS,
        ttl_seconds: float | None = STATE_TTL_SECONDS,
    ) -> None:
        self._max_entries = max(1, int(max_entries))
        self._max_total_chars = max(0, int(max_total_chars))
        self._max_tokens = max(1, int(max_tokens))
        self._ttl_seconds = ttl_seconds
        self._states: OrderedDict[str, BrowserState] = OrderedDict()
        self._chars = 0
        self._tokens: OrderedDict[str, str] = OrderedDict()
        self._cid_tokens: dict[str, str] = {}

    # ---------------------------------------------------------- conversation token
    def token_for(self, conversation_id: str) -> str:
        existing = self._cid_tokens.get(conversation_id)
        if existing is not None and self._tokens.get(existing) == conversation_id:
            self._tokens.move_to_end(existing)
            return existing
        token = hashlib.sha256(
            ("ohb2-files:" + str(conversation_id)).encode("utf-8")
        ).hexdigest()[:16]
        while token in self._tokens and self._tokens[token] != conversation_id:
            token = hashlib.sha256(
                (token + ":" + str(conversation_id)).encode("utf-8")
            ).hexdigest()[:16]
        self._tokens[token] = conversation_id
        self._cid_tokens[conversation_id] = token
        self._evict_tokens()
        return token

    def conversation_for(self, token: str) -> str | None:
        if not isinstance(token, str):
            return None
        conversation_id = self._tokens.get(token)
        if conversation_id is not None:
            self._tokens.move_to_end(token)
        return conversation_id

    # ------------------------------------------------------------------- snapshots
    def put(self, conversation_id: str, owner_id: int, paths) -> BrowserState:
        # اللقطة القديمة لنفس الشات تُسقط (تحديث)، لكن رمز الشات يفضل صالح عشان زر
        # «الملفات» ما يبوظش بعد أول فتح.
        self._drop_states_for(conversation_id)
        nav = secrets.token_hex(8)
        while nav in self._states:
            nav = secrets.token_hex(8)
        state = build_state(nav, conversation_id, owner_id, paths)
        self._states[nav] = state
        self._chars += _state_chars(state)
        self._evict_states()
        return state

    def get(self, nav: str) -> BrowserState | None:
        state = self._states.get(nav)
        if state is None:
            return None
        if self._ttl_seconds is not None and time.monotonic() - state.created_at > self._ttl_seconds:
            self._drop_state(nav)
            return None
        self._states.move_to_end(nav)
        return state

    def invalidate(self, conversation_id: str) -> None:
        self._drop_states_for(conversation_id)
        token = self._cid_tokens.pop(conversation_id, None)
        if token is not None:
            self._tokens.pop(token, None)

    def clear(self) -> None:
        self._states.clear()
        self._tokens.clear()
        self._cid_tokens.clear()
        self._chars = 0

    def __len__(self) -> int:
        return len(self._states)

    def __contains__(self, nav: object) -> bool:
        return nav in self._states

    # ---------------------------------------------------------------------- internals
    def _drop_state(self, nav: str) -> None:
        state = self._states.pop(nav, None)
        if state is not None:
            self._chars -= _state_chars(state)

    def _drop_states_for(self, conversation_id: str) -> None:
        for nav in [n for n, s in self._states.items() if s.conversation_id == conversation_id]:
            self._drop_state(nav)

    def _evict_states(self) -> None:
        while self._states and (
            len(self._states) > self._max_entries or self._chars > self._max_total_chars
        ):
            _, state = self._states.popitem(last=False)
            self._chars -= _state_chars(state)

    def _evict_tokens(self) -> None:
        while len(self._tokens) > self._max_tokens:
            token, conversation_id = self._tokens.popitem(last=False)
            if self._cid_tokens.get(conversation_id) == token:
                self._cid_tokens.pop(conversation_id, None)
