"""TASK 04C-14 / FINAL-01 / FINAL-03: ذاكرة ملفات محدودة (LRU) مع نسخ (generations).

بنغطّي: الإخلاء، التحديث، الإبطال، النسخ (النسخة الأقدم بتبقى بايتة)، أمان التعديل
(get بيرجّع نسخة مش المرجع الداخلي)، وأمان الأزرار القديمة (stale/evicted) على مستوى
الـ handlers، وعزل الشاتات، وحد 64 بايت.
"""
import asyncio

import bot.handlers as h
import bot.keyboards as kb
from bot.file_cache import FileCache
from tests.test_handlers import DetailClient, _cb_update, _ctx_with


def _keys(cache):
    return [k for k in ("a", "b", "c", "d") if k in cache]


def test_evicts_least_recently_used_when_over_capacity():
    cache = FileCache(max_entries=3)
    for cid in ("a", "b", "c"):
        cache.put(cid, [f"{cid}.py"])
    cache.get("a")  # لمسة ⇒ a بقت الأحدث استخدامًا
    cache.put("d", ["d.py"])  # زيادة ⇒ نطرد الأقدم استخدامًا (b)
    assert "b" not in cache
    assert set(["a", "c", "d"]) <= set(_keys(cache))
    assert len(cache) == 3


def test_refresh_replaces_not_stacks_and_keeps_lru():
    cache = FileCache(max_entries=2)
    cache.put("a", ["old.py"])
    cache.put("a", ["new.py", "x.py"])  # تحديث نفس الشات
    got = cache.get("a")
    assert got is not None and got[0] == ["new.py", "x.py"]
    assert len(cache) == 1


def test_invalidate_removes_entry():
    cache = FileCache()
    cache.put("a", ["a.py"])
    cache.invalidate("a")
    assert cache.get("a") is None
    assert "a" not in cache


def test_char_budget_evicts_old_entries():
    cache = FileCache(max_entries=100, max_total_chars=10)
    cache.put("a", ["12345678"])  # 8 أحرف
    cache.put("b", ["12345678"])  # +8 ⇒ 16 > 10 ⇒ يطرد a
    assert cache.get("a") is None
    got = cache.get("b")
    assert got is not None and got[0] == ["12345678"]


def test_put_empty_list_is_bounded_and_retrievable():
    cache = FileCache()
    cache.put("a", [])
    got = cache.get("a")
    assert got is not None and got[0] == []


# ------------------------------------------------------------------ generations
def test_put_returns_increasing_generation_and_get_matches():
    cache = FileCache()
    g1 = cache.put("c1", ["a.py"])
    got = cache.get("c1", g1)
    assert got == (["a.py"], g1)
    g2 = cache.put("c1", ["a.py", "b.py"])  # تحديث نفس الشات
    assert g2 != g1


def test_stale_generation_after_refresh_is_rejected():
    # FINAL-01: زر اتولّد على نسخة قديمة مايقدرش يقرأ محتوى النسخة الجديدة.
    cache = FileCache()
    old = cache.put("c1", ["old.py"])
    cache.put("c1", ["secret_new.py"])  # تحديث ⇒ النسخة القديمة بايتة
    assert cache.get("c1", old) is None  # نسخة أقدم ⇒ مرفوض
    fresh = cache.get("c1")  # بدون قيد نسخة ⇒ أحدث محتوى
    assert fresh is not None and fresh[0] == ["secret_new.py"]


def test_generation_is_isolated_between_conversations():
    cache = FileCache()
    g_a = cache.put("conv-A", ["secret_a.py"])
    cache.put("conv-B", ["b.py"])
    # نسخة A مستحيل تفتح شات B، والعكس.
    assert cache.get("conv-B", g_a) is None
    assert cache.get("conv-A", g_a) is not None
    assert cache.get("conv-B") is not None


def test_evicted_conversation_rejects_any_generation():
    cache = FileCache(max_entries=1)
    g_old = cache.put("a", ["a.py"])
    cache.put("b", ["b.py"])  # يطرد a
    assert cache.get("a", g_old) is None
    assert cache.get("a") is None


# --------------------------------------------------------------- mutation safety
def test_get_returns_copy_and_mutation_does_not_affect_cache():
    # FINAL-03: تعديل القايمة المُرجّعة مايغيّرش الحالة الداخلية.
    cache = FileCache()
    cache.put("c1", ["a.py", "b.py"])
    got = cache.get("c1")
    got[0].append("evil.py")
    got[0].clear()
    again = cache.get("c1")
    assert again[0] == ["a.py", "b.py"]


def test_put_copies_input_list_so_later_mutation_is_ignored():
    cache = FileCache()
    src = ["a.py"]
    cache.put("c1", src)
    src.append("later.py")
    assert cache.get("c1")[0] == ["a.py"]


# ------------------------------------------------------------------ callback limit
def test_files_menu_generation_callbacks_stay_within_limit():
    cid = "123e4567-e89b-12d3-a456-426614174000"
    markup = kb.files_menu(cid, ["a.py"] * 10, start=990, page=99, has_more=True, gen=123456789)
    cbs = [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]
    assert cbs and all(len(cb.encode("utf-8")) <= 64 for cb in cbs)


# ------------------------------------------------------------------ handler level
def test_stale_callback_after_eviction_returns_not_found(tmp_path):
    # شات اتشال من الذاكرة (eviction) ⇒ زر «file» قديم بيرجّع «مش موجود»، مش محتوى شات تاني.
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}))
    update = _cb_update(1, "file:c1:1:0")
    asyncio.run(h.show_file(update, ctx))
    assert ctx.bot.documents == []
    assert "مش موجود" in update.callback_query.edits[-1]


def test_stale_callback_after_refresh_is_rejected(tmp_path):
    # FINAL-01 (مستوى الـ handler): بعد تحديث قايمة الملفات، زر من النسخة القديمة يتجاهل،
    # ومايقرأش محتوى النسخة الجديدة.
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}, files=["old.py"], content="NEW"))
    cache = FileCache()
    old_gen = cache.put("c1", ["old.py"])
    cache.put("c1", ["new.py"])  # تحديث
    ctx.bot_data["file_cache"] = cache
    update = _cb_update(1, f"file:c1:{old_gen}:0")
    asyncio.run(h.show_file(update, ctx))
    assert ctx.bot.documents == []
    assert "مش موجود" in update.callback_query.edits[-1]


def test_malformed_file_callback_is_safe(tmp_path):
    # FINAL-01: صيغة قديمة/مشوهة (بدون نسخة) ⇒ رسالة انتهت القايمة، من غير أي كشف محتوى.
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}, files=["a.py"]))
    cache = FileCache(); cache.put("c1", ["a.py"]); ctx.bot_data["file_cache"] = cache
    update = _cb_update(1, "file:c1:0")
    asyncio.run(h.show_file(update, ctx))
    assert ctx.bot.documents == []
    assert update.callback_query.edits  # رسالة بأمان


def test_cache_key_isolation_no_cross_conversation_leak():
    cache = FileCache()
    cache.put("conv-A", ["secret_a.py"])
    assert cache.get("conv-B") is None


def test_handler_cache_is_bounded_instance(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}, files=["a.py"]))
    asyncio.run(h.list_files(_cb_update(1, "files:c1:0"), ctx))
    assert isinstance(ctx.bot_data["file_cache"], FileCache)
