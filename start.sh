#!/usr/bin/env sh
# OpenHandBot — نقطة تشغيل واحدة (OHB2-N10-23).
#
# الاستخدام:  sh start.sh
#
# ليه؟ المنصة ممكن تشتغل من غير تثبيت حزم تلقائي، أو من مجلد عمل مختلف. السكربت ده:
#   1) يشتغل من مجلد السكربت نفسه (عشان `.env` و`DB_PATH` النسبي يتحلّوا صح).
#   2) يتأكد إن Python موجود ونسخته >= الحد المدعوم (قبل أي استيراد للتطبيق).
#   3) يتأكد إن الحزم المطلوبة للتشغيل متاحة (وإلا رسالة واضحة).
#   4) يثبّت الحزم **بس** لو المتغيّر OPENHANDBOT_AUTO_INSTALL=1 وفي حزم ناقصة فعلاً.
#   5) يشغّل `main.py` بالظبط مرة واحدة عبر `exec` ⇒ نفس العملية، الإشارات والـ exit
#      code بيوصلوا للتطبيق مباشرة، مفيش عملية تانية.
#
# متغيّرات السكربت (اختيارية):
#   OPENHANDBOT_PYTHON       مسار مفسّر Python صريح (الافتراضي: python3 ثم python).
#   OPENHANDBOT_AUTO_INSTALL =1 لتفعيل التثبيت من requirements.txt لو فيه حزم ناقصة.
#                            الافتراضي 0 (مفيش تثبيت) — المنصات اللي بتثبّت تلقائيًا مش
#                            محتاجة التفعيل ده، وبنمنع تكرار التثبيت بلا داعي.
#
# مفيش حذف/استبدال لقاعدة البيانات، ومفيش ترقيات حزم غير مضبوطة (الملف مثبّت بإصدارات).
set -eu

# --- 1) نشتغل من مجلد السكربت -------------------------------------------------
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

# --- 2) اختيار مفسّر Python ---------------------------------------------------
PY="${OPENHANDBOT_PYTHON:-}"
if [ -z "$PY" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PY=python3
    elif command -v python >/dev/null 2>&1; then
        PY=python
    else
        echo "ERROR: مفيش Python على السيرفر. المنصة لازم توفّر python3 (>= 3.11)." >&2
        exit 1
    fi
fi

# --- 3) فحص نسخة Python (قبل أي استيراد للتطبيق) -----------------------------
# الحد لازم يطابق bot/bootstrap.py::MIN_PYTHON (فيه اختبار بيمنع الانحراف).
if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)'; then
    VER=$("$PY" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null || echo "unknown")
    echo "ERROR: مطلوب Python 3.11 أو أحدث، الموجود: $VER" >&2
    exit 1
fi

# --- 4) فحص توفّر حزم التشغيل -------------------------------------------------
# أسماء الاستيراد للحزم المطلوبة للتشغيل (المُثبّتة في requirements.txt).
# ملاحظة: `paramiko` مش هنا — استيراده مؤجّل لوجهة SFTP (خارج نطاق تشغيل البوت العادي)،
# فغيابه مايمنعش الإقلاع (زي السلوك الحالي بالظبط).
deps_missing() {
    "$PY" - <<'PY'
import importlib.util as u

mods = ("telegram", "httpx", "dotenv", "starlette", "uvicorn")
missing = []
for m in mods:
    try:
        if u.find_spec(m) is None:
            missing.append(m)
    except (ImportError, ValueError):
        missing.append(m)
print(" ".join(missing))
PY
}

MISSING=$(deps_missing) || {
    echo "ERROR: فحص حزم Python فشل (المفسّر $PY مش شغّال صح)." >&2
    exit 1
}
if [ -n "$MISSING" ]; then
    echo "ERROR: حزم Python مطلوبة ناقصة: $MISSING" >&2
    if [ "${OPENHANDBOT_AUTO_INSTALL:-0}" = "1" ]; then
        if [ ! -f requirements.txt ]; then
            echo "ERROR: requirements.txt مش موجود جنب start.sh — مش ممكن التثبيت." >&2
            exit 1
        fi
        echo "INFO: OPENHANDBOT_AUTO_INSTALL=1 — بثبّت من requirements.txt ..." >&2
        if ! "$PY" -m pip install --disable-pip-version-check -r requirements.txt; then
            echo "ERROR: تثبيت الحزم فشل. صلّح بيئة pip أو ثبّت requirements.txt يدويًا." >&2
            exit 1
        fi
        MISSING=$(deps_missing) || {
            echo "ERROR: فحص الحزم بعد التثبيت فشل." >&2
            exit 1
        }
        if [ -n "$MISSING" ]; then
            echo "ERROR: الحزم دي لسه ناقصة بعد التثبيت: $MISSING" >&2
            exit 1
        fi
    else
        echo "ERROR: مش ممكن البدء من غير الحزم. لو المنصة بتثبّت requirements.txt تلقائيًا" >&2
        echo "       أعد التشغيل؛ وإلا فعّل OPENHANDBOT_AUTO_INSTALL=1 (محتاج pip + شبكة)." >&2
        exit 1
    fi
fi

# --- 5) تشغيل التطبيق (عملية واحدة، إشارات و exit code مباشرة) ----------------
if [ ! -f main.py ]; then
    echo "ERROR: main.py مش موجود في مجلد التشغيل ($SCRIPT_DIR)." >&2
    exit 1
fi

exec "$PY" main.py
