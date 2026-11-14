from bot import keyboards as kb


def _callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_main_menu_has_two_buttons():
    cbs = _callbacks(kb.main_menu())
    assert "list:0" in cbs
    assert "newchat" in cbs
    # OHB2-09-06: «متابعاتي» اتسترجعت (ظاهرة افتراضيًا).
    assert "watched:0" in cbs


def test_main_menu_shows_followups_when_unhidden(monkeypatch):
    monkeypatch.setattr(kb.features, "DEFERRED_FEATURES_HIDDEN", False)
    assert "watched:0" in _callbacks(kb.main_menu())


def test_main_menu_hides_followups_when_flag_on(monkeypatch):
    monkeypatch.setattr(kb.features, "DEFERRED_FEATURES_HIDDEN", True)
    assert "watched:0" not in _callbacks(kb.main_menu())


def test_conversation_actions_shows_watch_toggle():
    # OHB2-09-06: زر تابع/إلغاء المتابعة اليدوي اتسترجعت (ظاهر افتراضيًا).
    assert "watch:c1" in _callbacks(kb.conversation_actions("c1", watched=False))
    assert "unwatch:c1" in _callbacks(kb.conversation_actions("c1", watched=True))


def test_conversation_actions_shows_watch_toggle_when_unhidden(monkeypatch):
    monkeypatch.setattr(kb.features, "DEFERRED_FEATURES_HIDDEN", False)
    assert "watch:c1" in _callbacks(kb.conversation_actions("c1", watched=False))
    assert "unwatch:c1" in _callbacks(kb.conversation_actions("c1", watched=True))


def test_watches_menu_lists_open_and_unwatch():
    from bot.db import Watched

    items = [Watched("c1", "شات", "running")]
    cbs = _callbacks(kb.watches_menu(items, 0, has_more=False))
    assert "open:c1" in cbs
    assert "unwatch:c1" in cbs


def test_watches_menu_pagination():
    from bot.db import Watched

    cbs = _callbacks(kb.watches_menu([Watched("c1", "شات", "running")], 2, has_more=True))
    assert "watched:1" in cbs
    assert "watched:3" in cbs


def test_conversations_menu_uses_page_number_for_more():
    items = [{"id": "c1", "title": "ع", "execution_status": "finished"}]
    markup = kb.conversations_menu(items, page=0, has_more=True)
    cbs = _callbacks(markup)
    assert "open:c1" in cbs
    assert "list:1" in cbs


def test_conversations_menu_no_more_when_last_page():
    items = [{"id": "c1", "title": "ع", "execution_status": "running"}]
    markup = kb.conversations_menu(items, page=0, has_more=False)
    cbs = _callbacks(markup)
    assert "list:1" not in cbs
    assert "open:c1" in cbs


def test_conversations_menu_second_page_has_previous():
    items = [{"id": "c1", "title": "ع", "execution_status": "running"}]
    cbs = _callbacks(kb.conversations_menu(items, page=2, has_more=True))
    assert "list:1" in cbs
    assert "list:3" in cbs


def test_conversation_actions_has_new_buttons():
    cbs = _callbacks(kb.conversation_actions("c1"))
    # الأساسيات (رد/تحديث/حالة/رجوع/إلغاء التوجيه) بتفضل ظاهرة.
    for expected in ("reply:c1", "open:c1", "status:c1", "list:0", "cancelroute"):
        assert expected in cbs
    # OHB2-09-06: الملفات/التكلفة/التصدير اتسترجعت (ظاهرة افتراضيًا).
    for restored in ("files:c1:0", "cost:c1", "export:c1"):
        assert restored in cbs


def test_conversation_actions_shows_deferred_when_unhidden(monkeypatch):
    monkeypatch.setattr(kb.features, "DEFERRED_FEATURES_HIDDEN", False)
    cbs = _callbacks(kb.conversation_actions("c1"))
    for expected in ("files:c1:0", "cost:c1", "export:c1", "watch:c1"):
        assert expected in cbs


# =====================================================================
# TASK 55 (المرحلة B): صف النسخ (نسخ الرد / عرض كامل)
# =====================================================================
def test_conversation_actions_default_shape_unchanged():
    # الافتراضي (has_reply=False) بيسيب الشكل القديم بالظبط: مفيش أي زر نسخ.
    cbs = _callbacks(kb.conversation_actions("c1"))
    assert "copy:c1" not in cbs and "full:c1" not in cbs


def test_conversation_actions_has_reply_adds_copy_row():
    markup = kb.conversation_actions("c1", has_reply=True)
    cbs = _callbacks(markup)
    assert "copy:c1" in cbs
    assert "full:c1" not in cbs  # الرد مش مقصوص ⇒ مفيش "عرض كامل"
    # صف النسخ أول صف.
    assert markup.inline_keyboard[0][0].callback_data == "copy:c1"


def test_conversation_actions_reply_cut_adds_full_reply():
    markup = kb.conversation_actions("c1", has_reply=True, reply_cut=True)
    cbs = _callbacks(markup)
    assert "copy:c1" in cbs and "full:c1" in cbs


def test_conversation_actions_copy_callback_within_limit():
    cbs = _callbacks(kb.conversation_actions("a" * 36, has_reply=True, reply_cut=True))
    assert all(len(cb.encode()) <= 64 for cb in cbs)


def test_files_menu_uses_index_not_path():
    markup = kb.files_menu("c1", ["a/b/very_long_name.py", "x.py"], start=0, page=0, has_more=False, gen=3)
    cbs = _callbacks(markup)
    assert "file:c1:3:0" in cbs
    assert "file:c1:3:1" in cbs
    assert all(len(cb.encode()) <= 64 for cb in cbs)


def test_files_menu_pagination():
    markup = kb.files_menu("c1", ["x.py"], start=20, page=2, has_more=True, gen=1)
    cbs = _callbacks(markup)
    assert "files:c1:1:1" in cbs
    assert "files:c1:1:3" in cbs


def test_repositories_menu_has_search_and_pick():
    items = [{"full_name": "x/y"}]
    cbs = _callbacks(kb.repositories_menu(items, 0, has_more=False, gen=7))
    assert "pickrepo:7:0" in cbs
    assert "reposearch" in cbs


# =====================================================================
# OHB2-03: زر الـ Mini App (web_app) في القائمة
# =====================================================================
def test_main_menu_without_url_has_no_web_app_button():
    markup = kb.main_menu()
    assert all(b.web_app is None for row in markup.inline_keyboard for b in row)


def test_main_menu_with_url_has_web_app_button_first():
    markup = kb.main_menu("https://app.example.com/mini")
    first = markup.inline_keyboard[0][0]
    assert first.web_app is not None
    assert first.web_app["url"] == "https://app.example.com/mini"
    # باقي الأزرار الأساسية لسه موجودة.
    cbs = _callbacks(markup)
    assert "list:0" in cbs and "newchat" in cbs and kb.NOTIF_MENU in cbs


def test_mini_app_launch_is_web_app_only():
    markup = kb.mini_app_launch("https://app.example.com/mini")
    row = markup.inline_keyboard[0]
    assert len(row) == 1
    assert row[0].web_app is not None
    assert row[0].callback_data is None


def test_copy_reply_label_clarifies_manual_copy():
    assert kb.COPY_REPLY == "📄 عرض للنسخ اليدوي"
    markup = kb.conversation_actions("c1", has_reply=True)
    assert markup.inline_keyboard[0][0].text == "📄 عرض للنسخ اليدوي"


def test_conversation_actions_with_mini_app_url_adds_web_app_when_has_reply():
    markup = kb.conversation_actions("c1", has_reply=True, mini_app_url="https://app.example.com/mini")
    web_btns = [b for row in markup.inline_keyboard for b in row if b.web_app is not None]
    assert len(web_btns) == 1
    assert web_btns[0].text == kb.COPY_MINI_APP
    assert web_btns[0].web_app["url"] == "https://app.example.com/mini"
    # بدون رد، ما يظهرش زر النسخ من التطبيق
    markup_no_reply = kb.conversation_actions("c1", has_reply=False, mini_app_url="https://app.example.com/mini")
    assert all(b.web_app is None for row in markup_no_reply.inline_keyboard for b in row)
