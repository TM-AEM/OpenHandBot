from bot.messages import escape_html, format_conversation, split_message, state_label


def test_state_labels_arabic():
    assert state_label("finished") == "منتهي"
    assert state_label("running") == "شغال"
    assert state_label(None) == "غير معروف"
    assert state_label("weird") == "weird"


def test_split_short_unchanged():
    assert split_message("مرحبا") == ["مرحبا"]


def test_split_long_respects_limit():
    text = ("سطر " * 2000).strip()
    parts = split_message(text, limit=100)
    assert all(len(p) <= 100 for p in parts)
    assert "".join(p.replace("\n", "") for p in parts).replace(" ", "") == text.replace(" ", "")


def test_split_prefers_newline_boundary():
    text = "a" * 50 + "\n" + "b" * 50
    parts = split_message(text, limit=60)
    assert parts[0] == "a" * 50


def test_format_conversation_is_raw_text():
    conv = {"title": "<b>hack</b>", "selected_repository": "x/y", "execution_status": "running"}
    out = format_conversation(conv, "رد <س>")
    assert "<b>hack</b>" in out
    assert "شغال" in out
    assert "رد <س>" in out


def test_escape_html_neutralizes_markup():
    assert escape_html("<b>&</b>") == "&lt;b&gt;&amp;&lt;/b&gt;"
    assert escape_html("رد <س>") == "رد &lt;س&gt;"
