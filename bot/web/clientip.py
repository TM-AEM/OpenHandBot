"""تحديد عنوان العميل الحقيقي خلف الـ ingress (OHB2-06 / S3).

اكتشاف فعلي (probe على الـ runtime): الـ ingress (Traefik) **ما بينضّفش** أي
`X-Forwarded-For` جاي من العميل — بيعمل **إلحاق** للند الحقيقي على اليمين:

    عميل مزوّر:  X-Forwarded-For: 203.0.113.7            (من العميل)
    اللي وصل:    X-Forwarded-For: 203.0.113.7, 10.1.1.62 (Traefik لحق 10.1.1.62)
    وكمان:       X-Real-Ip: 10.1.1.62 ، TCP client = 10.2.97.6 (hop داخلي تاني)

النتيجة الأمنية:
- `X-Forwarded-For` كله **غير موثوق** هنا (أي حاجة على الشمال مزوّرة من العميل).
- `X-Real-Ip` = الند المباشر (بود الـ Traefik) — مش IP المستخدم النهائي، ومش سري.
- IP المستخدم النهائي مش ممكن نستخرجه بثقة بسبب الـ hop الداخلي الزيادة.

لذلك:
- ما بنستخدمش `uvicorn --proxy-headers` (لأنه بياخد أول قيمة غير موثوقة من اليمين،
  واللي بتكون القيمة المزوّرة من العميل ⇒ انتحال).
- بنستخدم IP الاتصال الفعلي (`request.client.host`) كمعرّف، وبنسقط لأي IP، وبندرّج
  كل القيم المحلية/غير الصالحة تحت مفتاح واحد. في الـ topology دي ده معناه إن تحديد
  المعدّل «لكل IP» بيقرب من «عام» (كل العملاء المباشرين عبر نفس الـ hop). ده **الخيار
  المتحفّظ الآمن** (fail closed): ما بنصدّقش أي هيدر يزوّره العميل، وما بنفترضش إن IP
  شفناه هو المستخدم النهائي. توثيق القيد في docs/MINI_APP.md.
"""
from __future__ import annotations

import ipaddress

UNKNOWN = "unknown"


def _is_private(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast


def resolve_client_ip(request) -> str:
    """يرجّع معرّف العميل الآمن من IP الاتصال الفعلي بس (مفيش ثقة في الهيدرز).

    - IP عام ⇒ المعرّف نفسه (يعمل كـ per-IP صح لما نكون خلف proxy موثوق نضيفه إحنا).
    - غير صالح/محلي/مجهول ⇒ `"unknown"` (كلهم على نفس الدلو ⇒ حد عام متحفّظ).
    """
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    if not host:
        return UNKNOWN
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return UNKNOWN
    return UNKNOWN if _is_private(host) else host
