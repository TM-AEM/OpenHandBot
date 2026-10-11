from bot import keyboards as kb


def _callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_main_menu_has_two_buttons():
    cbs = _callbacks(kb.main_menu())
    assert "list:first" in cbs
    assert "newchat" in cbs


def test_conversations_menu_uses_cursor_for_more():
    items = [{"id": "c1", "title": "ع", "execution_status": "finished"}]
    markup = kb.conversations_menu(items, next_page_id="cur123", has_more=True)
    cbs = _callbacks(markup)
    assert "open:c1" in cbs
    assert "list:cur123" in cbs


def test_conversations_menu_no_more_when_no_cursor():
    items = [{"id": "c1", "title": "ع", "execution_status": "running"}]
    markup = kb.conversations_menu(items, next_page_id=None, has_more=True)
    assert "list:cur123" not in _callbacks(markup)


def test_repositories_menu_has_search_and_pick():
    items = [{"full_name": "x/y"}]
    cbs = _callbacks(kb.repositories_menu(items, 0, "", has_more=False))
    assert "pickrepo:x/y" in cbs
    assert "reposearch" in cbs
