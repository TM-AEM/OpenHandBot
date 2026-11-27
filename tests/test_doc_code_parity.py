"""OHB2-WP-08 (NEW-DEF-08): اختبارات تكافؤ بين الكود والوثائق.

بتمنع انحراف صامت بين المصدر والوثائق التشغيلية:
- متغيّرات البيئة اللي بيعرّفها `bot/config.py` مقابل `.env.example` و`README.md`
  و`docs/OPERATIONS_RUNBOOK.md`.
- جداول SQLite اللي بيعملها `bot/db.py::_init_schema` مقابل ما بتذكره الوثائق.

Ownership: this module is the canonical WP-08 documentation/env/schema parity guard.
`tests/test_deploy_manifest.py` and `tests/test_zero_touch_contract.py` own runtime/deploy
contracts; they do not duplicate these documentation-parity assertions.

قراءة ملفات المستودع فقط؛ مفيش شبكة ولا قاعدة حقيقية (نستخرج أسماء الجداول من نص
`_init_schema` عبر `sqlite3` في الذاكرة بدون تشغيل منطق التطبيق).
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONFIG_SRC = (ROOT / "bot/config.py").read_text(encoding="utf-8")
DB_SRC = (ROOT / "bot/db.py").read_text(encoding="utf-8")
APP_SRC = (ROOT / "bot/app.py").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
RUNBOOK = (ROOT / "docs/OPERATIONS_RUNBOOK.md").read_text(encoding="utf-8")


def _config_env_names() -> set[str]:
    """أسماء متغيّرات البيئة اللي بيقراها `load_config` (عبر `_clean`/`_parse_bool`/...)."""
    names = set(re.findall(r'_clean\(\s*env,\s*"([A-Z_]+)"', CONFIG_SRC))
    names |= set(re.findall(r'_parse_bool\(\s*env,\s*"([A-Z_]+)"', CONFIG_SRC))
    names |= set(re.findall(r'_positive\(\s*"([A-Z_]+)"', CONFIG_SRC))
    names |= set(re.findall(r'_parse_bounded_int\(\s*env,\s*"([A-Z_]+)"', CONFIG_SRC))
    return names


def _env_example_names() -> set[str]:
    return set(re.findall(r"^([A-Z_]+)=", ENV_EXAMPLE, flags=re.M))


def _schema_tables() -> set[str]:
    """أسماء الجداول الفعلية من `_init_schema` (تشغيل SQL مقابل قاعدة في الذاكرة)."""
    start = DB_SRC.index("CREATE TABLE IF NOT EXISTS")
    schema_sql = DB_SRC[start: DB_SRC.index('"""', start)]
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema_sql)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    finally:
        conn.close()
    return {r[0] for r in rows}


def _doc_section(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(end, begin)]


def _runbook_env_names() -> set[str]:
    section = _doc_section(RUNBOOK, "## 3)", "## 4)")
    return set(re.findall(r"^\|\s*`([A-Z_]+)`\s*\|", section, re.M))


def _readme_env_names() -> set[str]:
    section = _doc_section(README, "متغيرات البيئة المطلوبة:", "## الاختبار")
    return set(re.findall(r"^\|\s*`([A-Z_]+)`\s*\|", section, re.M))


def _runbook_schema_inventory() -> tuple[int, list[str]]:
    """عدد الجداول وأسماؤها من قائمة §4 فقط، وليس من أي ذكر آخر في الوثيقة."""
    section = _doc_section(RUNBOOK, "## 4)", "## 5)")
    match = re.search(r"\*\*(\d+)\*\*\s+جدول\):\s*\n(.*?)\n\s*\(\+", section, re.S)
    assert match, "مش لاقي قائمة جداول §4 في OPERATIONS_RUNBOOK"
    return int(match.group(1)), re.findall(r"`([a-z_]+)`", match.group(2))


def test_env_example_covers_every_config_variable():
    config_names = _config_env_names()
    example_names = _env_example_names()
    missing = config_names - example_names
    assert not missing, f".env.example ناقص: {sorted(missing)}"


def test_config_has_no_env_var_absent_from_config_sources():
    # العكس: أي متغيّر في .env.example لازم يقرأه config.py (ما عدا ملفات لا يقرأها).
    config_names = _config_env_names()
    example_names = _env_example_names()
    unexpected = example_names - config_names
    assert not unexpected, f".env.example فيه متغيّرات مش معرّفة في config.py: {sorted(unexpected)}"


def test_readme_documents_every_config_variable():
    config_names = _config_env_names()
    readme_names = _readme_env_names()
    missing = config_names - readme_names
    unexpected = readme_names - config_names
    assert not missing and not unexpected, (
        f"README متغيّرات ناقصة: {sorted(missing)}؛ "
        f"متغيّرات غير معرّفة في config.py: {sorted(unexpected)}"
    )


def test_runbook_documents_every_config_variable():
    config_names = _config_env_names()
    runbook_names = _runbook_env_names()
    missing = config_names - runbook_names
    unexpected = runbook_names - config_names
    assert not missing and not unexpected, (
        f"OPERATIONS_RUNBOOK §3 متغيّرات ناقصة: {sorted(missing)}؛ "
        f"متغيّرات غير معرّفة في config.py: {sorted(unexpected)}"
    )


def test_runbook_documents_every_schema_table():
    _, documented = _runbook_schema_inventory()
    tables = _schema_tables()
    missing = tables - set(documented)
    unexpected = set(documented) - tables
    duplicates = len(documented) - len(set(documented))
    assert not missing and not unexpected and duplicates == 0, (
        f"OPERATIONS_RUNBOOK §4 جداول ناقصة: {sorted(missing)}؛ "
        f"جداول غير موجودة في المخطط: {sorted(unexpected)}؛ "
        f"تكرارات: {duplicates}"
    )


def test_runbook_table_count_matches_schema():
    documented_count, documented = _runbook_schema_inventory()
    tables = _schema_tables()
    assert documented_count == len(tables), (
        f"RUNBOOK يذكر {documented_count} جدولًا، والمخطط فيه {len(tables)}"
    )
    assert len(documented) == len(tables) and set(documented) == tables, (
        "قائمة جداول §4 وعددها لازم يطابقا المخطط معًا"
    )


def _runbook_poller_section() -> str:
    """قسم الاستقبال في Runbook فقط، وليس أي ذكر آخر في الوثيقة."""
    return _doc_section(RUNBOOK, "- **الاستقبال:**", "- **الحالة المستقرة:**")


def test_runbook_poller_concurrency_matches_application():
    """الـ Runbook لازم يوصف الـ Application التسلسلي الحالي، مش إعدادًا قديمًا."""
    section = _runbook_poller_section()
    assert ".concurrent_updates(False)" in APP_SRC, (
        "bot/app.py لم يعد يستخدم concurrent_updates(False)"
    )
    assert "concurrent_updates(False)" in section, (
        "Runbook لا يذكر concurrent_updates(False) في قسم الاستقبال"
    )
    assert "concurrent_updates(True)" not in section, (
        "Runbook يذكر concurrent_updates(True) القديم في قسم الاستقبال"
    )


# ---------------------------------------------------------------------------
# OHB2-WP07-DEF011-F03: عقيدة دورة حياة الوثائق (Document Supersession)
#
# F-03 مش عيب كود: وثيقتان تاريخيتان (اقتراح القبول + تقرير التثبيت) لسه فيهم
# ادّعاءات بزمن المضارع عن DEF-011 بقت غلط بعد ما DEF-011-B اتنفّذ. الإصلاح
# **إضافي فقط**: بنضيف إشعار تصحيح مؤرّخ، والنص التاريخي يفضل زي ما هو بايت-ببايت.
#
# الاختبارات دي بتمنع 4 أشكال انحراف:
#   T-1  التكافؤ الحالي: الإشعار بيوصف حالة الكود الفعلية (B منفّذ، A/C لأ).
#   T-2  الثبات التاريخي: §2.2 و§7 والادّعاءات الأصلية ما اتغيّروش.
#   T-3  منع الادّعاء الزائد: DEF-011 لسه مفتوح، ومفيش ادّعاء إنه مقفول.
#   T-4  اتساق الوثيقتين: نفس التاريخ ونفس الحالة ونفس النطاق.
# ---------------------------------------------------------------------------

PROPOSAL = (
    ROOT / "docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md"
).read_text(encoding="utf-8")
BATCH_REPORT = (
    ROOT / "docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md"
).read_text(encoding="utf-8")
F01_REPORT = (
    ROOT / "docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md"
).read_text(encoding="utf-8")
F03_IMPLEMENTATION_REPORT = (
    ROOT / "docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md"
).read_text(encoding="utf-8")
ATTACHMENTS_SRC = (ROOT / "bot/attachments.py").read_text(encoding="utf-8")

CORRECTION_MARKER = "LATER CORRECTION"
F03_DATE = "2026-11-21"

# النص التاريخي المحمي — لازم يفضل بايت-ببايت زي ما كان قبل التصحيح.
_GOLDEN_SECTION_2_2 = (
'### 2.2 Verification against the current tree\n\n| Item | Present? | Evidence |\n|---|---|---|\n| A-1 | **YES** | `def add_watched_and_record_outcome` ×1 in `bot/db.py` |\n| A-2 | **YES** | `def remove_watched_completing` ×1, `_remove_watched_nocommit` ×1 |\n| A-3 | **YES** | `def clear_awaiting_and_record_outcome` ×1, `def set_awaiting_and_record_outcome` ×1 |\n| A-4 | **YES** | `_remove_watched_with_retry` retains single-arg path |\n| A-5 | **YES** | all six handlers defined; 14 F-1 tests pass |\n\n**All five accepted items remain intact and unmodified in substance.**\n\n'
)

_GOLDEN_SECTION_7 = (
'## 7. Explicit non-authorizations\n\nEven if the owner later grants acceptance:\n\n- **No Git publication** — commit, push, PR, merge, tag, or release are **not** authorized.\n- **No WP-06 Part 2 implementation** — O-7 remains a separate gate.\n- **No deployment or release.**\n- **No Autopush activation.**\n- **No schema change** — the 17-table baseline remains authoritative (O-5, C-5.7).\n- **No DEF-011 implementation.**\n- **No OD-04 resolution** — that is a separate owner decision.\n- **No scope expansion** beyond what is explicitly named.\n\n---\n\n'
)

# الادّعاءات التاريخية المتقادمة — لازم تفضل موجودة حرفيًا (ممنوع إعادة كتابتها).
_HISTORICAL_STALE_LINES = (
    "- an entirely **unimplemented** finding (DEF-011).",
    "| **R9** | **DEF-011 is entirely unimplemented** while inside WP-07's authoritative "
    "scope. | 0 `to_thread` in `attachments.py`; 0 quota ledger |",
    "| 1 | **DEF-011 is entirely unimplemented** (no `asyncio.to_thread` in `attachments.py`, "
    "no quota ledger) though inside WP-07's authoritative scope | WP-07 is **not** "
    "implementation-complete |",
)


def _section(text: str, start: str, end: str) -> str:
    """يقطع قسم كامل من الوثيقة بحدود نصّية صريحة (مش أرقام سطور)."""
    begin = text.index(start)
    return text[begin : text.index(end, begin)]


def _correction_notice(text: str) -> str:
    """إشعار التصحيح من بداية العلامة لحد نهاية الاقتباس (سطر فاضي)."""
    start = text.index(CORRECTION_MARKER)
    # الإشعار كله اقتباس Markdown (كل سطر بيبدأ بـ `>`)، فبناخد لحد أول سطر مش اقتباس.
    lines = text[start:].splitlines()
    body = []
    for line in lines:
        if body and line.strip() and not line.lstrip().startswith(">"):
            break
        body.append(line)
    return "\n".join(body)


def _latest_correction_notice(text: str) -> str:
    """آخر إشعار تصحيح مضاف — عشان التصحيحات اللاحقة تفضل قابلة للاختبار."""
    start = text.rindex(CORRECTION_MARKER)
    lines = text[start:].splitlines()
    body = []
    for line in lines:
        if body and line.strip() and not line.lstrip().startswith(">"):
            break
        body.append(line)
    return "\n".join(body)


def _sub_defect_status(notice: str, sub_defect: str) -> str:
    """حالة تحت-عيب معيّن من صف الجدول اللي بيبدأ بـ `**`DEF-011-X`**`."""
    for line in notice.splitlines():
        if f"`{sub_defect}`" in line and line.lstrip().startswith(">"):
            row = line.lstrip("> ").strip()
            if "IMPLEMENTED" in row and "NOT IMPLEMENTED" in row:
                return "NOT IMPLEMENTED"
            if "NOT IMPLEMENTED" in row:
                return "NOT IMPLEMENTED"
            if "IMPLEMENTED" in row:
                return "IMPLEMENTED"
    raise AssertionError(f"مفيش صف حالة لـ {sub_defect} في إشعار التصحيح")


# --- T-1: التكافؤ الحالي بين الإشعار والكود ---------------------------------


def test_t1_correction_notice_matches_actual_implementation_state():
    """T-1: الإشعار لازم يوصف حالة الكود الحقيقية: B منفّذ، A و C لأ."""
    notice = _correction_notice(PROPOSAL)

    assert _sub_defect_status(notice, "DEF-011-B") == "IMPLEMENTED", (
        "DEF-011-B لازم يتسجّل IMPLEMENTED في الإشعار"
    )
    assert _sub_defect_status(notice, "DEF-011-A") == "NOT IMPLEMENTED", (
        "DEF-011-A لازم يتسجّل NOT IMPLEMENTED في الإشعار"
    )
    assert _sub_defect_status(notice, "DEF-011-C") == "IMPLEMENTED", (
        "DEF-011-C لازم يتسجّل IMPLEMENTED بعد إضافة النص المحلي الصريح"
    )

    # الدليل الفعلي على إن B منفّذ: offload حقيقي بـ anyio في مسار المرفقات.
    assert "from anyio import to_thread" in ATTACHMENTS_SRC, (
        "DEF-011-B مفترض يكون منفّذ عبر anyio.to_thread في bot/attachments.py"
    )
    assert "to_thread.run_sync" in ATTACHMENTS_SRC, (
        "DEF-011-B مفترض يكون فيه استدعاء to_thread.run_sync فعلي"
    )

    # الإشعار بيقول "ستة" occurrences — لازم يطابق العدد الفعلي في الكود.
    assert ATTACHMENTS_SRC.count("to_thread") == 6, (
        "عدد to_thread في attachments.py اتغيّر؛ الإشعار لازم يتحدّث مع الكود"
    )
    assert "six" in notice and "to_thread" in notice, (
        "الإشعار لازم يذكر عدد to_thread المطابق للكود"
    )


def test_t1_reservation_ledger_absence_still_accurate():
    """T-1 (تكملة): ادّعاء "0 quota ledger" لسه صح، فـ A لسه مش منفّذ."""
    assert not any(
        token in ATTACHMENTS_SRC
        for token in ("reserv", "in_flight", "_ledger")
    ), "لو ظهر reservation ledger، لازم DEF-011-A يتحدّث ويخرج من حالة NOT IMPLEMENTED"


# --- T-2: الثبات التاريخي ----------------------------------------------------


def test_t2_protected_sections_are_byte_for_byte_unchanged():
    """T-2: §2.2 و§7 ممنوع يتغيّروا بأي حرف."""
    assert _section(
        PROPOSAL,
        "### 2.2 Verification against the current tree",
        "### 2.3",
    ) == _GOLDEN_SECTION_2_2, "§2.2 اتغيّر — ممنوع تعديل القسم التاريخي"

    assert _section(
        PROPOSAL,
        "## 7. Explicit non-authorizations",
        "## 8.",
    ) == _GOLDEN_SECTION_7, "§7 اتغيّر — ممنوع تحويل حدود التفويض التاريخية لادّعاء تنفيذ"


def test_t2_historical_stale_claims_are_preserved_verbatim():
    """T-2: الادّعاءات التاريخية المتقادمة لازم تفضل موجودة، مش مُعاد كتابتها."""
    for line in _HISTORICAL_STALE_LINES:
        assert line in PROPOSAL or line in BATCH_REPORT, (
            f"ادّعاء تاريخي اتمسح أو اتعاد كتابته: {line[:60]}..."
        )

    # الادّعاء الأصلي "0 to_thread" لازم يفضل حرفيًا في الاقتراح.
    assert "0 `to_thread` in `attachments.py`; 0 quota ledger" in PROPOSAL, (
        "الادّعاء التاريخي عن صفر to_thread اتمسح — الإصلاح لازم يكون إضافي فقط"
    )


# --- T-3: منع الادّعاء الزائد ------------------------------------------------


def test_t3_both_documents_state_def011_remains_open():
    """T-3: الوثيقتين لازم يقولوا صراحةً إن DEF-011 لسه مفتوح ومش مقفول."""
    for name, text in (("proposal", PROPOSAL), ("batch report", BATCH_REPORT)):
        notice = _correction_notice(text)
        lowered = notice.lower()
        assert "remains open" in lowered or "still open" in lowered, (
            f"{name}: الإشعار لازم يصرّح إن DEF-011 لسه مفتوح"
        )
        assert "not closed" in lowered or "not** closed" in lowered, (
            f"{name}: الإشعار لازم يصرّح إن DEF-011 مش مقفول"
        )


def test_t3_no_claim_that_all_sub_defects_are_implemented():
    """T-3: ممنوع أي قراءة بتقول إن A و B و C كلهم منفّذين."""
    for name, text in (("proposal", PROPOSAL), ("batch report", BATCH_REPORT)):
        notice = _correction_notice(text).lower()
        assert "not implemented" in notice, (
            f"{name}: الإشعار لازم يوضّح إن فيه تحت-عيوب لسه NOT IMPLEMENTED"
        )
        # أي ذكر لـ "fully implemented" لازم يكون منفيًّا.
        for fragment in notice.split("fully implemented")[:-1]:
            tail = fragment.rsplit(".", 1)[-1]
            assert "not" in tail, (
                f"{name}: ادّعاء زائد إن DEF-011 fully implemented من غير نفي"
            )


# --- T-4: اتساق الوثيقتين ----------------------------------------------------


def test_t4_both_notices_share_date_status_and_scope_language():
    """T-4: الإشعارين بنفس التاريخ وبنفس تصنيف الحالة والنطاق."""
    proposal_notice = _correction_notice(PROPOSAL)
    report_notice = _correction_notice(BATCH_REPORT)

    assert F03_DATE in proposal_notice, "إشعار الاقتراح لازم يحمل تاريخ التصحيح"
    assert F03_DATE in report_notice, "إشعار تقرير التثبيت لازم يحمل نفس التاريخ"

    for token in ("DEF-011-B", "DEF-011-A", "DEF-011-C"):
        assert token in proposal_notice, f"إشعار الاقتراح لازم يذكر {token}"
        assert token in report_notice, f"إشعار تقرير التثبيت لازم يذكر {token}"

    # نفس تصنيف الحالة في الوثيقتين.
    assert "NOT implemented" in report_notice or "NOT IMPLEMENTED" in report_notice, (
        "تقرير التثبيت لازم يوضّح إن A لسه NOT implemented"
    )
    assert "six" in proposal_notice and "six" in report_notice, (
        "الوثيقتين لازم يذكروا نفس العدد (ستة) لـ to_thread"
    )


# --- T-5: تصحيح مرجع F-03 المتقادم في تقرير BATCH04-F01 ----------------------


def test_t5_batch04_f01_report_correction_notice():
    """T-5: تقرير F-01 التاريخي لازم يحمل إشعار تصحيح مؤرّخ لمرجع F-03 المتقادم."""
    notice = _correction_notice(F01_REPORT)

    # الإشعار موجود ومؤرّخ، ويسجّل حكم المراجعة المستقلة ويشير لتقريرها بالمسار الصحيح.
    assert F03_DATE in notice, "إشعار تصحيح BATCH04-F01 لازم يحمل تاريخ التصحيح"
    assert "F03_REVIEW_PASS" in notice, (
        "الإشعار لازم يسجّل حكم المراجعة المستقلة F03_REVIEW_PASS"
    )
    assert "docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md" in notice, (
        "الإشعار لازم يشير لتقرير المراجعة المستقلة بالمسار الصحيح"
    )

    # الادّعاء التاريخي الأصلي لازم يفضل موجود حرفيًا (مش اتمسح ولا اتعاد كتابته).
    assert (
        '| **F-03** (stale acceptance doc claiming "0 `to_thread`") '
        "| **OPEN / NOT FIXED** | Batch-03 DOC-01; not part of this task. |"
    ) in F01_REPORT, "الادّعاء التاريخي عن F-03 اتمسح — الإصلاح لازم يكون إضافي فقط"

    # ممنوع ادّعاء إن DEF-011 مقفول: الإشعار لازم يصرّح إنه لسه مفتوح وما بيقفلوش.
    lowered = notice.lower()
    assert "remains open" in lowered, "الإشعار لازم يصرّح إن DEF-011 لسه مفتوح"
    assert "not close" in lowered, "الإشعار لازم يوضّح إنه ما بيقفلش DEF-011"

    # FOLLOW-01: التصحيح اللاحق لازم يوصف C الحالية، مش يكرر ادّعاء NOT IMPLEMENTED القديم.
    latest = _latest_correction_notice(F01_REPORT)
    assert "2026-11-24" in latest, "إشعار FOLLOW-01 لازم يحمل تاريخه"
    assert _sub_defect_status(latest, "DEF-011-C") == "IMPLEMENTED", (
        "إشعار FOLLOW-01 لازم يسجّل DEF-011-C كـ IMPLEMENTED"
    )
    assert _sub_defect_status(latest, "DEF-011-A") == "NOT IMPLEMENTED", (
        "إشعار FOLLOW-01 لازم يبقي DEF-011-A NOT IMPLEMENTED"
    )
    assert "STORED" in latest and "ATTACHMENT_ACCEPTED_TEXT" in latest, (
        "إشعار FOLLOW-01 لازم يربط C بالنص المحلي وشرط STORED"
    )


# --- T-6: تصحيح تقرير تنفيذ F-03 المتقادم ------------------------------------


def test_t6_f03_implementation_report_correction_matches_current_count():
    """F-09: تقرير التنفيذ لازم يحمل تصحيحًا مؤرّخًا للعدد والحالة الحالية."""
    assert "LATER CORRECTION" in F03_IMPLEMENTATION_REPORT
    assert "six" in F03_IMPLEMENTATION_REPORT
    assert "DEF-011-C" in F03_IMPLEMENTATION_REPORT
    assert "IMPLEMENTED" in F03_IMPLEMENTATION_REPORT
    assert ATTACHMENTS_SRC.count("to_thread") == 6
