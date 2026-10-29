from bot.messages import (
    SANDBOX_ERROR,
    escape_html,
    format_conversation,
    format_cost,
    get_status,
    is_terminal,
    pr_url,
    split_message,
    state_label,
)


def test_state_labels_arabic():
    assert state_label("finished") == "منتهي"
    assert state_label("running") == "شغال"
    assert state_label(None) == "غير معروف"
    assert state_label("weird") == "weird"
    assert state_label(SANDBOX_ERROR) == "خطأ بيئة"


def test_get_status_is_the_single_canonical_derivation():
    # sandbox_status ∈ {ERROR, MISSING} ⇒ sandbox_error (بأي حالة أحرف)، وإلا execution_status.
    assert get_status({"execution_status": "finished"}) == "finished"
    assert get_status({"execution_status": "RUNNING"}) == "running"
    assert get_status({"execution_status": "finished", "sandbox_status": "ERROR"}) == SANDBOX_ERROR
    assert get_status({"execution_status": "finished", "sandbox_status": "MISSING"}) == SANDBOX_ERROR
    assert get_status({"execution_status": "running", "sandbox_status": "RUNNING"}) == "running"
    assert get_status({}) == "unknown"


def test_is_terminal_includes_sandbox_error():
    for s in ("finished", "error", "stuck", "waiting_for_confirmation", SANDBOX_ERROR):
        assert is_terminal(s)
    for s in ("running", "idle", "paused", None, "unknown"):
        assert not is_terminal(s)


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


# =====================================================================
# TASK 55 (المرحلة B): truncate + format_conversation_view
# =====================================================================
from bot.messages import (  # noqa: E402
    FOOTER_RESERVE,
    PROMPT_PREVIEW,
    REPLY_PREVIEW,
    TELEGRAM_LIMIT,
    format_conversation_view,
    truncate,
)

FOOTER = (
    "\n\n✉️ رسايلك الجاية هتتبعت للشات ده (10 دقايق من آخر نشاط). "
    "للإلغاء: زر إلغاء التوجيه أو /cancel."
)


def test_truncate_short_unchanged():
    assert truncate("مرحبا", 10) == ("مرحبا", False)


def test_truncate_long_marks_cut():
    text, cut = truncate("x" * 50, 10)
    assert cut is True
    assert text.endswith("…")
    assert text.startswith("x" * 10)


def test_truncate_empty_and_whitespace():
    assert truncate(None, 10) == ("", False)
    assert truncate("", 10) == ("", False)
    assert truncate("   \n ", 10) == ("", False)


def test_view_without_user_text():
    conv = {"title": "شات", "execution_status": "running"}
    out, cut = format_conversation_view(conv, None, "رد")
    assert "شات" in out and "شغال" in out
    assert "رد الـ agent:" in out
    assert "رد" in out
    assert "آخر برومت" not in out  # مفيش برومت ⇒ مفيش بلوك
    assert cut is False


def test_view_with_user_text_and_short_reply():
    conv = {"title": "شات", "execution_status": "finished"}
    out, cut = format_conversation_view(conv, "برومتي", "ردي")
    assert "آخر برومت منك:" in out and "برومتي" in out
    assert "رد الـ agent:" in out and "ردي" in out
    assert cut is False


def test_view_reply_none_shows_placeholder():
    conv = {"title": "شات", "execution_status": "running"}
    out, cut = format_conversation_view(conv, "برومتي", None)
    assert "لسه مفيش رد." in out
    assert cut is False


def test_view_long_reply_is_cut():
    conv = {"title": "شات", "execution_status": "finished"}
    out, cut = format_conversation_view(conv, None, "ر" * 5000)
    assert cut is True
    # المعاينة محصورة بحد الرد (REPLY_PREVIEW لما المساحة تسمح).
    assert len(out) < 2000
    assert "…" in out


def test_view_long_prompt_is_truncated():
    conv = {"title": "شات", "execution_status": "running"}
    out, _ = format_conversation_view(conv, "ب" * 5000, None)
    # معاينة البرومت عند PROMPT_PREVIEW (300) مش النص الكامل.
    assert len(out) < PROMPT_PREVIEW + 400


def test_view_very_long_title_stays_within_limit_with_footer():
    # عنوان طويل جداً يفعّل تصغير حد الرد؛ الإجمالي + الذيل لازم ≤ 4096.
    conv = {"title": "ع" * 3300, "execution_status": "running"}
    out, _ = format_conversation_view(conv, None, "ر" * 5000)
    assert len(out) + len(FOOTER) <= TELEGRAM_LIMIT


def test_view_reply_limit_never_below_floor():
    # الحد الأدنى 200 يمنع تقليص الرد لنص تافه لما الهيدر ياخد مساحة كبيرة.
    conv = {"title": "ع" * 100, "execution_status": "running"}
    out, _ = format_conversation_view(conv, None, "ر" * 5000)
    # الرد المعروض أطول من 200 حرف (مفيش تقليص مفرط).
    assert out.count("ر") >= 200
    assert REPLY_PREVIEW <= 800  # ثابت موثّق
    assert FOOTER_RESERVE == 250


def test_view_long_title_and_prompt_stay_within_limit():
    # انحراف مقصود: عنوان + برومت طويلين جداً ⇒ العنوان بيتقص عشان الضمان ≤4096
    # والأرضية 200 يفضلوا مضمونين مع بعض.
    conv = {"title": "ع" * 6000, "execution_status": "running", "selected_repository": "o/r"}
    out, _ = format_conversation_view(conv, "ب" * 6000, "ر" * 6000)
    assert len(out) + len(FOOTER) <= TELEGRAM_LIMIT
    assert out.count("ر") >= 200
