"""OHB2-N10-18 (CRITICAL-1): حارس قائمة النشر — يمنع إن دليل النشر ينسى حزمة مطلوبة للتشغيل.

بيحسب **إغلاق الاستيراد الحقيقي** انطلاقًا من `main.py` (بالـ AST، من غير تشغيل البوت)،
ويستخرج كل الوحدات/الحزم المحلية اللي بيتحمّلها وقت التشغيل. بعدين:

1. يتأكد إن كل استيراد محلي بيتحلّ لملف موجود فعلًا (مفيش استيراد مكسور).
2. يتأكد إن دليل `docs/DEPLOY_KATABUMP.md` بيذكر كل مدخل جذري مطلوب للتشغيل.
3. يبني مجلد مؤقت فيه **بس** الملفات المطلوبة للتشغيل ويستورد `main` جواه — إثبات إن
   القائمة كافية من غير باقي المستودع (fixture معزول، مفيش لمس لشجرة العمل الحقيقية).

الاختبار ده هو اللي كان هيصطاد N10-17 CRITICAL-1 (`tools/` ناقصة من الدليل).
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_DOC = ROOT / "docs" / "DEPLOY_KATABUMP.md"


def _resolve(modname: str) -> Path | None:
    """يحلّ اسم وحدة (نقطة = مسار) لملف `.py` أو مجلد حزمة، أو None لو مش محلي."""
    parts = modname.split(".")
    f = ROOT.joinpath(*parts).with_suffix(".py")
    if f.is_file():
        return f
    d = ROOT.joinpath(*parts)
    if (d / "__init__.py").is_file():
        return d
    return None


def _import_closure(entry: Path) -> tuple[set[str], set[str]]:
    """يرجّع (الملفات المحلية المطلوبة, أسماء الحزم الجذرية المحلية)."""
    seen: set[str] = set()
    local_files: set[str] = set()
    local_tops: set[str] = set()

    def proc(modname: str) -> None:
        if not modname:
            return
        target = _resolve(modname)
        if target is None:
            return
        local_tops.add(modname.split(".")[0])
        walk(target, modname)

    def walk(target: Path, modname: str) -> None:
        if str(target) in seen:
            return
        seen.add(str(target))
        if target.is_file():
            local_files.add(str(target.relative_to(ROOT)))
            tree = ast.parse(target.read_text())
            pkg = modname.rsplit(".", 1)[0] if "." in modname else ""
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        proc(a.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        base = pkg
                        for _ in range(node.level - 1):
                            base = base.rsplit(".", 1)[0] if "." in base else ""
                        if node.module:
                            proc(f"{base}.{node.module}" if base else node.module)
                        else:
                            for a in node.names:
                                proc(f"{base}.{a.name}" if base else a.name)
                        proc(base)
                    elif node.module:
                        proc(node.module)
        else:
            local_files.add(str(target.relative_to(ROOT)) + "/")
            init = target / "__init__.py"
            if init.is_file():
                walk(init, modname + ".__init__")

    walk(entry, entry.stem)
    return local_files, local_tops


def test_runtime_imports_all_resolve():
    """كل استيراد محلي من main.py لازم يتحلّ لملف موجود (مفيش مرجع مكسور)."""
    local_files, _ = _import_closure(ROOT / "main.py")
    assert local_files, "إغلاق الاستيراد طلع فاضي — في مشكلة في الحساب"
    for rel in local_files:
        assert (ROOT / rel.rstrip("/")).exists(), f"استيراد محلي مكسور: {rel}"


def test_deploy_doc_covers_runtime_roots():
    """الدليل لازم يذكر كل حزمة جذرية مطلوبة للتشغيل (والنواة مش محتاجة `tools/`)."""
    _, tops = _import_closure(ROOT / "main.py")
    doc = DEPLOY_DOC.read_text()
    # المدخلات الجذرية المطلوبة = حزم الاستيراد المحلية + ملف الإقلاع.
    required = {f"{t}/" for t in tops} | {"main.py"}
    # `bot/` لازم تظهر صريحة (مش أي حزمة تانية).
    assert "bot/" in required
    for entry in sorted(required):
        assert entry in doc, (
            f"دليل النشر ناقص مدخل مطلوب للتشغيل: {entry!r} — "
            "حدّث قائمة الرفع في docs/DEPLOY_KATABUMP.md"
        )
    # OHB2-N10-25: النواة مستقلة عن النسخ ⇒ `tools/` **مش** مطلوبة للتشغيل، والدليل
    # لازم يذكر إنها **مستبعدة** صريحًا.
    assert "tools/" not in required
    assert "tools/" in doc
    assert "tools/" in doc.split("ما ترفعش")[1]


def _copy_runtime(tmp_path: Path) -> None:
    """ينسخ بس الملفات المطلوبة للتشغيل (النواة، بدون `tools/`) لمجلد معزول."""
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copy2(ROOT / "main.py", tmp_path / "main.py")
    shutil.copytree(ROOT / "bot", tmp_path / "bot", ignore=ignore)
    shutil.copy2(ROOT / "requirements.txt", tmp_path / "requirements.txt")


def test_documented_manifest_is_import_sufficient(tmp_path):
    """نسخة فيها الملفات المطلوبة بس (بدون `tools/`) لازم تستورد `main`."""
    _copy_runtime(tmp_path)
    # نتأكد إن المستودع الحقيقي مش على sys.path (الاختبار لازم يكون معزول فعلاً).
    assert not (tmp_path / "tests").exists()
    assert not (tmp_path / "tools").exists()  # النواة مش محتاجة أدوات النسخ
    proc = subprocess.run(
        [sys.executable, "-c", "import main"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": str(tmp_path),
        },
        timeout=120,
    )
    assert proc.returncode == 0, f"استيراد main فشل:\n{proc.stdout}\n{proc.stderr}"


def test_manifest_does_not_require_tools():
    """OHB2-N10-25: النواة مستقلة عن النسخ ⇒ `tools/` **مش** جزء من إغلاق استيراد main."""
    files, _ = _import_closure(ROOT / "main.py")
    assert not any(f.startswith("tools/") for f in files), "المفروض tools/ مش مطلوبة للتشغيل"


def test_static_assets_are_documented():
    """ملفات الواجهة الثابتة بتتقرأ من القرص وقت التشغيل ⇒ لازم تكون موثّقة."""
    doc = DEPLOY_DOC.read_text()
    assert "bot/web/static" in doc or "static/" in doc
    assert (ROOT / "bot" / "web" / "static" / "index.html").is_file()


def test_doc_excludes_dev_only_material():
    """الدليل لازم يستبعد الاختبارات وسكربتات الأتمتة صريحًا."""
    doc = DEPLOY_DOC.read_text()
    for dev in ("tests/", "automations/", "automation"):
        assert dev in doc, f"الدليل مش بيستبعد مادة تطوير: {dev}"


def test_deploy_doc_mentions_required_env_and_entrypoint():
    doc = DEPLOY_DOC.read_text()
    assert "python main.py" in doc
    for var in ("TELEGRAM_BOT_TOKEN", "OPENHANDS_API_KEY", "ALLOWED_TELEGRAM_ID"):
        assert re.search(rf"\b{var}\b", doc), f"متغيّر مطلوب مش موثّق: {var}"
