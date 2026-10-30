"""مساعدات مشتركة لاختبارات الـ Mini App (OHB2-05).

بيولّد `initData` صالح بنفس خوارزمية تيليجرام، عشان الاختبارات تختبر الكود الحقيقي
مش نسخة مزيّفة.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


def sign_init_data(fields: dict[str, str], bot_token: str = BOT_TOKEN) -> str:
    """يبني initData موقّع صح من الحقول المطلوبة (بترتيب تيليجرام)."""
    data_check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": digest})


def make_init_data(
    user_id: int,
    *,
    bot_token: str = BOT_TOKEN,
    auth_date: int | None = None,
    first_name: str = "أحمد",
    extra: dict[str, str] | None = None,
) -> str:
    """initData صالح للمستخدم `user_id` بتاريخ مصادقة محدّد (افتراضيًا الآن)."""
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAF",
        "user": json.dumps(
            {"id": user_id, "first_name": first_name, "language_code": "ar"},
            ensure_ascii=False,
        ),
    }
    if extra:
        fields.update(extra)
    return sign_init_data(fields, bot_token)
