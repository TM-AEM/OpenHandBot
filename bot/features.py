"""الميزات المؤجّلة (القرار 4): مخفية عن المستخدم مؤقتًا.

إحنا بنخفي نقاط الدخول بس (الأزرار + تسجيل الـ handlers). الكود والجداول والبيانات
لسه موجودين زي ما هي، فأي وظيفة داخلية بتعتمد عليها (زي المتابعة التلقائية بعد
البرومت) بتفضل شغالة. عشان نرجّع أي ميزة: شيلها من HIDDEN_FEATURES أو خلّي
DEFERRED_FEATURES_HIDDEN = False.
"""
from __future__ import annotations

# القرار 4: نخفي الملفات والتصدير والتكلفة والمتابعات (إدارة يدوية) مؤقتًا.
DEFERRED_FEATURES_HIDDEN = True

HIDDEN_FEATURES = frozenset({"files", "export", "cost", "followups"})


def is_hidden(feature: str) -> bool:
    """هل الميزة مخفية عن المستخدم دلوقتي؟"""
    return DEFERRED_FEATURES_HIDDEN and feature in HIDDEN_FEATURES
