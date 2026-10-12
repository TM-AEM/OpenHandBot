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
    # النص كامل بلا فقد (بما فيه السطور الجديدة).
    assert "".join(parts) == text


def test_split_prefers_newline_boundary():
    text = "a" * 50 + "\n" + "b" * 50
    parts = split_message(text, limit=60)
    assert parts[0] == "a" * 50


def test_split_is_lossless_with_newlines():
    # النص القديم كان بيرمي السطور الجديدة عند الحد (lstrip) — دلوقتي لازم يتّحفظ.
    text = "aaa\n\nbbb"
    parts = split_message(text, limit=4)
    assert "".join(parts) == text
    assert all(len(p) <= 4 for p in parts)


def test_split_handles_long_unbroken_text():
    text = "x" * 250
    parts = split_message(text, limit=100)
    assert "".join(parts) == text
    assert all(len(p) <= 100 for p in parts)
    assert [len(p) for p in parts] == [100, 100, 50]


def test_format_conversation_is_raw_text():
    conv = {"title": "<b>hack</b>", "selected_repository": "x/y", "execution_status": "running"}
    out = format_conversation(conv, "رد <س>")
    assert "<b>hack</b>" in out
    assert "شغال" in out
    assert "رد <س>" in out


def test_escape_html_neutralizes_markup():
    assert escape_html("<b>&</b>") == "&lt;b&gt;&amp;&lt;/b&gt;"
    assert escape_html("رد <س>") == "رد &lt;س&gt;"


def _html_unescape(text: str) -> str:
    import html

    return html.unescape(text)


def test_split_message_handles_html_escaping_correctly():
    # نص طويل فيه < و > و & — بعد التهريب بيتحوّل لكيانات، وطول تيليجرام بيتقاس
    # على النص بعد فك الكيانات (raw)، فالحد لازم يتطبق على الـ raw.
    raw = ("a<b>&c " * 1000).strip()
    parts = split_message(raw)
    assert "".join(parts) == raw  # مفيش فقد
    for part in parts:
        escaped = escape_html(part)
        # الـ HTML source مفكوك بيرجّع نفس النص، وطوله جوه حد تيليجرام.
        assert _html_unescape(escaped) == part
        assert len(_html_unescape(escaped)) <= 4096


def test_split_message_handles_unicode_and_emoji():
    # عربي + إيموجي غير BMP + markup. حد تيليجرام بيتقاس بعد فك الكيانات أي بطول
    # النص الخام (code points)، والإيموجي غير BMP بيتحسب نقطة واحدة مش وحدتين.
    # إحنا مابنستخدمش MessageEntity offsets (مفيش entities)، فمفيش حسابات UTF-16.
    mixed = ("😀 مرحبا <b> " * 800).strip()
    parts = split_message(mixed)
    assert "".join(parts) == mixed  # ترتيب ومحتوى كامل بلا فقد
    for part in parts:
        decoded = _html_unescape(escape_html(part))
        assert decoded == part  # الـ HTML source صالح وبيفكّ لنفس النص
        assert len(decoded) <= 4096

    # سلسلة إيموجي متصلة طويلة تتقسّم بأمان وبلا فقد.
    emoji = "😀" * 5000
    emoji_parts = split_message(emoji)
    assert "".join(emoji_parts) == emoji
    assert all(len(p) <= 4096 for p in emoji_parts)


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
