"""بوابة اختبارات الواجهة (OHB2-07-FIX).

بتشغّل اختبارات Node المدمجة (node --test) على منطق دورة حياة معرّف العملية في
`bot/web/static/ops.js`. عشان `pytest -q` يغطّيها كمان، بس بتتخطّى بأمان لو Node
مش متاح في البيئة (CI مافيهوش خطوة Node، وده مقبول — الاختبارات لسه بتشتغل محليًا
وبأمر صريح).
"""
from __future__ import annotations

import glob
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js غير متاح")
def test_frontend_operation_logic() -> None:
    test_files = sorted(glob.glob(str(ROOT / "tests" / "frontend" / "*.test.js")))
    assert test_files, "مفيش ملفات اختبار واجهة"
    proc = subprocess.run(
        ["node", "--test", *test_files],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, "اختبارات الواجهة فشلت:\n" + output
    # تأكيد إن الاختبارات فعلاً اشتغلت ونجحت (مش صفر ملفات / صفر حالات).
    passed = re.search(r"pass (\d+)", output)
    failed = re.search(r"fail (\d+)", output)
    assert passed is not None and int(passed.group(1)) >= 7, output
    assert failed is not None and int(failed.group(1)) == 0, output
