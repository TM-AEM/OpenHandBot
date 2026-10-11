from bot import keyboards as kb


def _callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_main_menu_has_two_buttons():
    cbs = _callbacks(kb.main_menu())
    assert "list:0" in cbs
    assert "newchat" in cbs


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
    for expected in ("reply:c1", "open:c1", "status:c1", "files:c1:0", "cost:c1", "export:c1"):
        assert expected in cbs


def test_files_menu_uses_index_not_path():
    markup = kb.files_menu("c1", ["a/b/very_long_name.py", "x.py"], start=0, page=0, has_more=False)
    cbs = _callbacks(markup)
    assert "file:c1:0" in cbs
    assert "file:c1:1" in cbs
    assert all(len(cb.encode()) <= 64 for cb in cbs)


def test_files_menu_pagination():
    markup = kb.files_menu("c1", ["x.py"], start=20, page=2, has_more=True)
    cbs = _callbacks(markup)
    assert "files:c1:1" in cbs
    assert "files:c1:3" in cbs


def test_repositories_menu_has_search_and_pick():
    items = [{"full_name": "x/y"}]
    cbs = _callbacks(kb.repositories_menu(items, 0, "", has_more=False))
    assert "pickrepo:x/y" in cbs
    assert "reposearch" in cbs
