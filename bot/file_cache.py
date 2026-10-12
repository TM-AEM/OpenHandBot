"""ذاكرة مؤقتة محدودة لقوايم ملفات الشاتات (حد ذاكرة صغير وحتمي).

- كل سجل مربوط بـ conversation_id، فزر قديم مستني مستحيل يعرض محتوى شات تاني —
  يا إما يرجّع نفس الشات، يا إما «مش موجود» (لو اتشال بالـ eviction).
- سياسة الإخلاء LRU (الأقدم استخدامًا أولًا)، محدودة بعدد السجلات *و* مجموع الأحرف،
  بقيم متحفظة مناسبة لبوت خفيف.
- كل سجل ليه «نسخة» (generation) بتزيد لما نفس الشات يتحدّث. كل نداء get/put
  بيرجّع/بيسجّل (قايمة، نسخة)، عشان الأزرار اللي بتحمل نسخة قديمة تتجاهل بأمان
  (تحديث القايمة خلال نفس الشات بيلغي الأزرار القديمة).
- get بيرجّع **نسخة** من القايمة، فتعديل الرجوع مايغيّرش الحالة الداخلية للذاكرة.
"""
from __future__ import annotations

from collections import OrderedDict

MAX_ENTRIES = 16  # أقصى عدد شاتات مخزّنة في نفس الوقت
MAX_TOTAL_CHARS = 50_000  # أقصى مجموع أحرف لمسارات الملفات المخزّنة (حماية إضافية)


class FileCache:
    """LRU محدود لقوايم ملفات الشاتات، مفتاحه conversation_id، مع نسخة لكل سجل."""

    def __init__(self, max_entries: int = MAX_ENTRIES, max_total_chars: int = MAX_TOTAL_CHARS) -> None:
        self._max_entries = max(1, int(max_entries))
        self._max_total_chars = max(0, int(max_total_chars))
        self._entries: OrderedDict[str, list[str]] = OrderedDict()
        self._gen: dict[str, int] = {}
        self._cursor = 0
        self._chars = 0

    def put(self, conversation_id: str, files: list[str]) -> int:
        """يخزّن/يحدّث قايمة ملفات شات ويرجّع نسختها الجديدة.

        التحديث بيستبدل القديم (مش تكديس نسخ) وبيزوّد النسخة، فالأزرار اللي شالت
        النسخة القديمة بتبقى بايتة.
        """
        files = list(files or [])
        self._drop(conversation_id)
        self._cursor += 1
        self._gen[conversation_id] = self._cursor
        self._entries[conversation_id] = files
        self._chars += sum(len(f) for f in files)
        self._entries.move_to_end(conversation_id)
        self._evict()
        return self._cursor

    def get(self, conversation_id: str, gen: int | None = None) -> tuple[list[str], int] | None:
        """يرجّع (نسخة من القايمة, النسخة الحالية)، ولمسة LRU.

        None لو مش موجودة/اتشالت. لو gen اتحدّد ومالويسش النسخة الحالية، بيرجّع None
        (زر من تحديث/نسخة أقدم ⇒ يتعامل معاه كإنه مش موجود بأمان).
        """
        if conversation_id not in self._entries:
            return None
        current = self._gen[conversation_id]
        if gen is not None and gen != current:
            return None
        self._entries.move_to_end(conversation_id)  # لمسة LRU
        return list(self._entries[conversation_id]), current

    def invalidate(self, conversation_id: str) -> None:
        self._drop(conversation_id)

    def clear(self) -> None:
        self._entries.clear()
        self._gen.clear()
        self._chars = 0

    def __contains__(self, conversation_id: object) -> bool:
        return conversation_id in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def _drop(self, conversation_id: str) -> None:
        old = self._entries.pop(conversation_id, None)
        if old is not None:
            self._chars -= sum(len(f) for f in old)
        self._gen.pop(conversation_id, None)

    def _evict(self) -> None:
        while self._entries and (
            len(self._entries) > self._max_entries or self._chars > self._max_total_chars
        ):
            cid, old = self._entries.popitem(last=False)  # الأقدم استخدامًا
            self._chars -= sum(len(f) for f in old)
            self._gen.pop(cid, None)
