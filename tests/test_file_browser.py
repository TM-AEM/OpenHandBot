"""OHB2-BOT-FILE-BROWSER: اختبارات وحدة لشجرة المجلدات والترقيم والذاكرة."""
from __future__ import annotations

from bot.file_browser import (
    BrowserCache,
    BrowserState,
    build_state,
    parent_path,
    PAGE_SIZE,
)


def _state(paths, *, cid="c1", owner=1, nav="n1"):
    return build_state(nav, cid, owner, paths)


def test_root_mixed_dirs_and_files_sorted():
    state = _state(["b.txt", "a.txt", "src/z.py", "docs/readme.md", "src/util/h.py"])
    assert state.dirs == ("", "docs", "src", "src/util")
    root = state.entries("")
    assert [kind for kind, _, _ in root] == ["dir", "dir", "file", "file"]
    assert [path for _, path, _ in root] == ["docs", "src", "a.txt", "b.txt"]
    assert state.entries("src") == (
        ("dir", "src/util", state.dir_index["src/util"]),
        ("file", "src/z.py", 0),
    )
    assert state.entries("src/util") == (("file", "src/util/h.py", 0),)


def test_nested_paths_and_duplicate_names_are_distinct():
    state = _state(["a/x.py", "b/x.py"])
    assert state.entries("") == (
        ("dir", "a", state.dir_index["a"]),
        ("dir", "b", state.dir_index["b"]),
    )
    assert state.entries("a") == (("file", "a/x.py", 0),)
    assert state.entries("b") == (("file", "b/x.py", 0),)


def test_directory_with_only_nested_directories():
    state = _state(["a/b/c.txt"])
    assert state.entries("") == (("dir", "a", state.dir_index["a"]),)
    assert state.entries("a") == (("dir", "a/b", state.dir_index["a/b"]),)
    assert state.entries("a/b") == (("file", "a/b/c.txt", 0),)


def test_unicode_and_spaces_are_supported():
    state = _state(["مجلد/ملف نصي.txt", "dir with space/a b.py"])
    names = {path for _, path, _ in state.entries("")}
    assert names == {"dir with space", "مجلد"}
    assert state.entries("dir with space") == (("file", "dir with space/a b.py", 0),)
    assert state.entries("مجلد") == (("file", "مجلد/ملف نصي.txt", 0),)


def test_unsafe_paths_are_dropped_fail_closed():
    state = _state(["../etc/passwd", "/abs", "a/../b", "a//b", "ok.txt"])
    assert state.dirs == ("",)
    assert state.entries("") == (("file", "ok.txt", 0),)


def test_empty_root_has_one_empty_page():
    state = _state([])
    assert state.dirs == ("",)
    assert state.entries("") == ()
    assert state.page_count("") == 1
    assert state.page_entries("", 0) == ()
    assert state.page_entries("", 99) == ()


def test_pagination_boundaries_no_duplicates_or_skips():
    paths = [f"f{i:02d}.txt" for i in range(25)]
    state = _state(paths)
    assert state.page_count("") == 3
    seen = []
    for page in range(3):
        chunk = state.page_entries("", page)
        assert len(chunk) == (PAGE_SIZE if page < 2 else 5)
        seen.extend(path for _, path, _ in chunk)
    assert seen == paths
    assert len(set(seen)) == len(seen)
    assert state.clamp_page("", -5) == 0
    assert state.clamp_page("", 99) == 2


def test_parent_path():
    assert parent_path("a/b/c") == "a/b"
    assert parent_path("a") == ""
    assert parent_path("") == ""


def test_browser_cache_token_is_stable_and_short():
    cache = BrowserCache()
    cid = "x" * 64
    token = cache.token_for(cid)
    assert len(token) == 16
    assert cache.token_for(cid) == token
    assert cache.conversation_for(token) == cid
    assert cache.conversation_for("nope") is None


def test_browser_cache_put_get_invalidate():
    cache = BrowserCache()
    token = cache.token_for("c1")
    state = cache.put("c1", 1, ["a.txt"])
    assert cache.get(state.nav) is state
    assert len(cache) == 1
    cache.invalidate("c1")
    assert cache.get(state.nav) is None
    assert len(cache) == 0
    assert cache.conversation_for(token) is None


def test_browser_cache_ttl_expires_state():
    cache = BrowserCache(ttl_seconds=-1)
    state = cache.put("c1", 1, ["a.txt"])
    assert cache.get(state.nav) is None
    assert len(cache) == 0


def test_browser_cache_lru_evicts_oldest_state():
    cache = BrowserCache(max_entries=1)
    first = cache.put("c1", 1, ["a.txt"])
    second = cache.put("c2", 1, ["b.txt"])
    assert cache.get(first.nav) is None
    assert cache.get(second.nav) is second


def test_browser_cache_char_budget_evicts():
    cache = BrowserCache(max_total_chars=0)
    state = cache.put("c1", 1, ["a.txt"])
    assert cache.get(state.nav) is None
    assert len(cache) == 0


def test_browser_cache_token_lru_bounds_mapping():
    cache = BrowserCache(max_tokens=1)
    first = cache.token_for("c1")
    second = cache.token_for("c2")
    assert cache.conversation_for(first) is None
    assert cache.conversation_for(second) == "c2"


def test_new_snapshot_invalidates_old_snapshot_for_same_conversation():
    cache = BrowserCache()
    first = cache.put("c1", 1, ["a.txt"])
    second = cache.put("c1", 1, ["a.txt", "b.txt"])
    assert first.nav != second.nav
    assert cache.get(first.nav) is None
    assert cache.get(second.nav) is second


def test_conversation_token_survives_snapshot_replacement():
    cache = BrowserCache()
    token = cache.token_for("c1")
    cache.put("c1", 1, ["a.txt"])
    assert cache.conversation_for(token) == "c1"


def test_public_api_names_are_canonical():
    fields = BrowserState.__dataclass_fields__
    assert "conversation_id" in fields
    assert "conversaion_id" not in fields
    for name in ("entries", "page_entries", "page_count", "clamp_page"):
        assert callable(getattr(BrowserState, name))
    for name in ("entires", "page_entires"):
        assert not hasattr(BrowserState, name)
    for name in ("token_for", "conversation_for", "put", "get", "invalidate", "clear"):
        assert callable(getattr(BrowserCache, name))
    assert not hasattr(BrowserCache, "conversaion_for")
