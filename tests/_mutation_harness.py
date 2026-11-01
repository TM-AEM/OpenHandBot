"""OHB2-09-BATCH-C (FC3): حزمة تنفيذ بطارية الطفرات (mutation battery harness).

**ليست** ملف اختبار (الاسم بيبدأ بـ `_` فـ pytest ما بيجمعهوش). بتُشغَّل يدويًا:

    .venv/bin/python tests/_mutation_harness.py --all --outdir docs/reviews/evidence/batch-c

لكل طفرة: تنسخ الملف الأصلي لمكان آمن خارج المستودع (`/tmp`)، تطبّق تعديلاً **واحدًا
محدّدًا**، تشغّل الاختبارات اللي المفروض تكشفه، تسجّل النتيجة، ترجّع الملف الأصلي
بايت-بايت، وتتأكّد من التطابق. مفيش أي أوامر git (لا checkout/reset/stash) ولا أي
نشر. الطفرات مالهاش أي علاقة بمسارات محمية.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "bin" / "python")

# كل طفرة: id + الملف + النص الأصلي + النص المبدَّل + كاشف (pytest nodes أو node files).
MUTATIONS: list[dict] = [
    {
        "id": "M1",
        "target": "Bypass conversation-owner comparison",
        "file": "bot/files.py",
        "old": (
            "    if not isinstance(created_by, str) or created_by != owner:\n"
            "        return None, FileStatus.UNAUTHORIZED, None"
        ),
        "new": (
            "    if False:  # M1 mutation: owner comparison bypassed\n"
            "        return None, FileStatus.UNAUTHORIZED, None"
        ),
        "detect": ["pytest",
                   "tests/test_files_service.py::test_list_files_denies_other_owner",
                   "tests/test_a2_conversation_authz.py::test_read_route_other_owner_forbidden"],
    },
    {
        "id": "M2",
        "target": "Skip conversation-ID validation",
        "file": "bot/web/services.py",
        "old": (
            '    text = (value or "").strip()\n'
            "    if not is_valid_conversation_id(text):\n"
            '        raise ValidationError("معرّف غير صالح")\n'
            "    return text"
        ),
        "new": (
            '    text = (value or "").strip()\n'
            "    # M2 mutation: id-shape validation skipped (weak space/length check only)\n"
            '    if not text or len(text) > 200 or " " in text:\n'
            '        raise ValidationError("معرّف غير صالح")\n'
            "    return text"
        ),
        "detect": ["pytest",
                   "tests/test_a2_conversation_authz.py::test_space_free_invalid_id_is_400_and_no_upstream_across_all_read_routes"],
    },
    {
        "id": "M3",
        "target": "Allow NaN or Infinity (Mini App cost)",
        "file": "bot/web/services.py",
        "old": ("    if isinstance(value, float) and not math.isfinite(value):\n"
                "        return None"),
        "new": ("    if False:  # M3 mutation: NaN/Infinity allowed\n"
                "        return None"),
        "detect": ["pytest",
                   "tests/test_a2_cost_numeric.py::test_as_number_rejects_non_finite_and_non_numbers",
                   "tests/test_a2_cost_numeric.py::test_route_nan_infinity_never_reach_frontend"],
    },
    {
        "id": "M4",
        "target": "Allow boolean cost values (Mini App cost)",
        "file": "bot/web/services.py",
        "old": ("    if isinstance(value, bool) or not isinstance(value, (int, float)):\n"
                "        return None"),
        "new": ("    if not isinstance(value, (int, float)):  # M4 mutation: bool allowed\n"
                "        return None"),
        "detect": ["pytest",
                   "tests/test_a2_cost_numeric.py::test_as_number_rejects_non_finite_and_non_numbers",
                   "tests/test_miniapp_cost.py::test_cost_bool_is_not_a_number"],
    },
    {
        "id": "M5",
        "target": "Remove finite-number validation from message data (Telegram cost)",
        "file": "bot/messages.py",
        "old": ("    if isinstance(value, bool) or not isinstance(value, (int, float)):\n"
                "        return None"),
        "new": ("    if not isinstance(value, (int, float)):  # M5 mutation: bool allowed in messages\n"
                "        return None"),
        "detect": ["pytest",
                   "tests/test_messages.py::test_format_cost_no_currency_and_rejects_non_finite"],
    },
    {
        "id": "M6",
        "target": "Remove export authorization",
        "file": "bot/handlers.py",
        "old": (
            "    conv, message = await _authorized_conversation(client, context, conversation_id)\n"
            "    if conv is None:\n"
            '        log.info("export: رفض تفويض الشات (ref=%s)", conversation_id)\n'
            "        await _safe_edit(q, message)\n"
            "        return"
        ),
        "new": (
            "    conv, message = await _authorized_conversation(client, context, conversation_id)\n"
            "    # M6 mutation: export authorization bypassed"
        ),
        "detect": ["pytest",
                   "tests/test_a2_export_auth.py::test_export_other_owner_cannot_export",
                   "tests/test_a2_export_auth.py::test_export_null_owner_cannot_export",
                   "tests/test_a2_export_auth.py::test_export_authorization_precedes_download"],
    },
    {
        "id": "M7-A",
        "target": "Remove only the sequence guard",
        "file": "bot/web/static/app.js",
        "old": "    function current() { return state.detailSeq === seq && state.currentChat === id; }",
        "new": "    function current() { return state.currentChat === id; }",
        "detect": ["node", "tests/frontend/detail_stale.test.js",
                   "tests/frontend/detail_stale_extra.test.js"],
    },
    {
        "id": "M7-B",
        "target": "Remove only the current-chat identity guard",
        "file": "bot/web/static/app.js",
        "old": "    function current() { return state.detailSeq === seq && state.currentChat === id; }",
        "new": "    function current() { return state.detailSeq === seq; }",
        "detect": ["node", "tests/frontend/detail_stale.test.js",
                   "tests/frontend/detail_stale_extra.test.js"],
    },
    {
        "id": "M9",
        "target": "Bypass Mini App /prompt authorization",
        "file": "bot/web/services.py",
        "old": "        await self._authorize_conversation(cid)",
        "new": "        pass  # M9 mutation: prompt authorization bypassed",
        "detect": ["pytest",
                   "tests/test_a2_conversation_authz.py::test_prompt_other_owner_forbidden_no_outbox",
                   "tests/test_batch_c_integration.py::test_prompt_cross_owner_denied_creates_no_row_and_no_protected_fetch"],
    },
    {
        "id": "M10",
        "target": "Bypass Telegram reply_prompt authorization",
        "file": "bot/handlers.py",
        "old": (
            "    conv, message = await _authorized_conversation(\n"
            '        context.bot_data["client"], context, conversation_id\n'
            "    )\n"
            "    if conv is None:\n"
            "        await _safe_edit(q, message)\n"
            "        return\n"
            '    db.set_awaiting(update.effective_user.id, conversation_id, "reply")'
        ),
        "new": (
            "    conv, message = await _authorized_conversation(\n"
            '        context.bot_data["client"], context, conversation_id\n'
            "    )\n"
            "    # M10 mutation: reply_prompt authorization bypassed\n"
            '    db.set_awaiting(update.effective_user.id, conversation_id, "reply")'
        ),
        "detect": ["pytest",
                   "tests/test_b06_file_routing.py::test_reply_prompt_other_owner_denied_no_awaiting",
                   "tests/test_batch_c_integration.py::test_telegram_reply_prompt_denied_sets_no_awaiting_and_no_upstream"],
    },
    {
        "id": "M11",
        "target": "Weaken file allowlist or path validation",
        "file": "bot/files.py",
        "old": (
            "def is_safe_workspace_path(path: str | None) -> bool:\n"
            '    """مسار نسبي آمن داخل مساحة العمل؟\n'
            "\n"
            "    بيرفض: الفاضي، المطلق، الشرطة العكسية، أي محرف تحكّم (بما فيه NUL)، أي مقطع\n"
            "    فاضي/`.`/`..`، وأي مسار ما بيساويش صورته المطبّعة (نمنع `a/../b` وأمثاله).\n"
            '    """\n'
            "    if not isinstance(path, str) or not path or len(path) > MAX_PATH_LEN:\n"
            "        return False\n"
            '    if path.startswith("/"):\n'
            "        return False\n"
            '    if "\\\\" in path:\n'
            "        return False\n"
            '    if any(ord(ch) < 0x20 or ch == "\\x7f" for ch in path):\n'
            "        return False\n"
            '    parts = path.split("/")\n'
            '    if any(part in ("", ".", "..") for part in parts):\n'
            "        return False\n"
            "    if posixpath.normpath(path) != path:\n"
            "        return False\n"
            "    return True"
        ),
        "new": (
            "def is_safe_workspace_path(path: str | None) -> bool:\n"
            '    """M11 mutation: weakened path validation (only rejects absolute/empty)."""\n'
            "    if not isinstance(path, str) or not path:\n"
            "        return False\n"
            '    return not path.startswith("/")'
        ),
        "detect": ["pytest",
                   "tests/test_files_service.py::test_unsafe_paths",
                   "tests/test_files_service.py::test_read_preview_rejects_traversal_before_fetch"],
    },
    {
        "id": "M12",
        "target": "Weaken outbox compare-and-set transition protection",
        "file": "bot/db.py",
        "old": (
            '            f"WHERE id=? AND status IN ({placeholders})",\n'
            "            (new_status, error, now, outbox_id, *allowed),"
        ),
        "new": (
            '            f"WHERE id=?",  # M12 mutation: status guard removed\n'
            "            (new_status, error, now, outbox_id),"
        ),
        "detect": ["pytest",
                   "tests/test_miniapp_reconcile.py::test_reconcile_discard_uses_atomic_cas_under_concurrency",
                   "tests/test_miniapp_reconcile.py::test_set_outbox_status_if_in_is_compare_and_set"],
    },
    {
        "id": "M13",
        "target": "Break identity-cache isolation or lifecycle",
        "file": "bot/handlers.py",
        "old": "    if entry is not None and entry[0] is client:",
        "new": "    if entry is not None:  # M13 mutation: cache not scoped per client",
        "detect": ["pytest",
                   "tests/test_a2_owner_cache.py::test_identity_cache_rebuilds_when_client_object_changes"],
    },
    {
        "id": "M14",
        "target": "Leak detailed upstream errors to the caller",
        "file": "bot/errors.py",
        "old": "    detail = redact((detail or \"\").strip())",
        "new": "    detail = (detail or \"\").strip()  # M14 mutation: no redaction of upstream detail",
        "detect": ["pytest",
                   "tests/test_4b.py::test_describe_status_redacts_upstream_detail"],
    },
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_detector(detect: list[str]) -> tuple[str, int, str]:
    if detect[0] == "pytest":
        cmd = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", *detect[1:]]
    else:  # node
        cmd = ["node", "--test", *detect[1:]]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    return " ".join(cmd), proc.returncode, (proc.stdout + proc.stderr)


def run_one(m: dict, backup_dir: Path, outdir: Path) -> dict:
    path = ROOT / m["file"]
    original = path.read_bytes()
    orig_sha = hashlib.sha256(original).hexdigest()
    backup = backup_dir / f"{m['id']}_{path.name}"
    backup.write_bytes(original)

    text = original.decode("utf-8")
    count = text.count(m["old"])
    record = {"id": m["id"], "target": m["target"], "file": m["file"],
              "occurrences": count, "orig_sha": orig_sha}
    if count != 1:
        record.update({"classification": "BLOCKED",
                       "note": f"target text appears {count} times (need exactly 1)"})
        return record

    try:
        path.write_text(text.replace(m["old"], m["new"]), encoding="utf-8")
        mut_sha = _sha(path)
        cmd, code, out = _run_detector(m["detect"])
        record.update({"mut_sha": mut_sha, "detect_cmd": cmd, "exit_code": code,
                       "detected": code != 0,
                       "classification": "CAUGHT" if code != 0 else "MISSED"})
        # احفظ آخر أسطر المخرَج كدليل.
        (outdir / f"fc3-{m['id'].replace('-', '')}-detector.txt").write_text(
            f"$ {cmd}\nexit={code}\n\n{out[-4000:]}", encoding="utf-8")
    finally:
        path.write_bytes(original)
        restored_sha = _sha(path)
        record["restore_sha"] = restored_sha
        record["restore_ok"] = restored_sha == orig_sha
        if not record["restore_ok"]:
            record["classification"] = "BLOCKED"
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--id", default=None)
    ap.add_argument("--outdir", default="docs/reviews/evidence/batch-c")
    args = ap.parse_args()

    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    backup_dir = Path(tempfile.mkdtemp(prefix="fc3_mut_"))

    if args.id:
        selected = [m for m in MUTATIONS if m["id"] == args.id]
    elif args.all:
        selected = MUTATIONS
    else:
        print("use --all or --id <ID>", file=sys.stderr)
        return 2

    results = [run_one(m, backup_dir, outdir) for m in selected]
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
