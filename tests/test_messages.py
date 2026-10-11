from bot.messages import (
    escape_html,
    format_conversation,
    format_cost,
    pr_url,
    split_message,
    state_label,
)


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


def test_pr_url_handles_list_and_scalar():
    assert pr_url({"selected_repository": "x/y", "pr_number": [1]}) == "https://github.com/x/y/pull/1"
    assert pr_url({"selected_repository": "x/y", "pr_number": 7}) == "https://github.com/x/y/pull/7"
    assert pr_url({"selected_repository": "x/y", "pr_number": []}) is None
    assert pr_url({"selected_repository": "x/y"}) is None
    assert pr_url({"pr_number": [1]}) is None


def test_format_conversation_includes_pr_link():
    conv = {"title": "t", "selected_repository": "x/y", "pr_number": [3]}
    out = format_conversation(conv, None)
    assert "https://github.com/x/y/pull/3" in out


def test_format_cost():
    out = format_cost(
        {
            "model_name": "claude",
            "accumulated_cost": 1.25,
            "accumulated_token_usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }
    )
    assert "$1.25" in out
    assert "claude" in out
    assert "100" in out and "20" in out
    assert format_cost(None) == "مفيش بيانات تكلفة."
