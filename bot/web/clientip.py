"""تحديد عنوان العميل الحقيقي خلف الـ ingress (OHB2-06 / S3 / OHB2-POST-PUB-01/F07).

اكتشاف فعلي (probe على الـ runtime): الـ ingress (Traefik) **ما بينضّفش** أي
`X-Forwarded-For` جاي من العميل — بيعمل **إلحاق** للند الحقيقي على اليمين:

    عميل مزوّر:  X-Forwarded-For: 203.0.113.7            (من العميل)
    اللي وصل:    X-Forwarded-For: 203.0.113.7, 10.1.1.62 (Traefik لحق 10.1.1.62)
    وكمان:       X-Real-Ip: 10.1.1.62 ، TCP client = 10.2.97.6 (hop داخلي تاني)

النتيجة الأمنية:
- `X-Forwarded-For` كله **غير موثوق** من غير بروكسي موثوق مُعرَّف صراحةً (أي حاجة على
  الشمال مزوّرة من العميل).
- `X-Real-Ip` = الند المباشر — مش IP المستخدم النهائي، ومش سري.

السياسة (F07):
- **الافتراضي (فاضية trusted proxies)**: بنستخدم IP الاتصال الفعلي (`request.client.host`)
  كمعرّف بس، وبنسقط لأي IP خاص/غير صالح لمفتاح واحد `unknown`. أي هيدر تحويل بيتجاهَل
  بالكامل ⇒ مفيش انتحال IP. ده الخيار المتحفّظ الآمن (fail closed).
- **مع `MINI_APP_TRUSTED_PROXIES` مُعرَّفة**: بنثق في `X-Forwarded-For` **بس** لو الند
  المباشر (`request.client.host`) نفسه جوه شبكة موثوقة (IP/CIDR صريح). بعدها ناخد أول
  عنوان **غير موثوق** من اليمين للشمال = العميل الأصلي. أي عنصر مش صالح ⇒ `unknown`
  (ما بنثقش في أي حاجة على شماله). الند مش موثوق ⇒ الهيدر يتجاهَل بالكامل.
- **عملاء كتير على بروكسي غير معروف**: كلهم بيتجمّعوا تحت `unknown` ⇒ مفتاح تحديد معدّل
  مشترك (تحديد «لكل IP» بيقرب من «عام»). ده مقصود: أأمن من نصدّق IP مزوّر. توثيق القيد
  في docs/MINI_APP.md.

بنستخدم `request.client.host` (الند المباشر اللي شافه الـ ASGI) ومش `uvicorn
--proxy-headers`، عشان القرار يفضل تحت إيدينا ومسيطر عليه بالإعداد الصريح.
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


def parse_trusted_proxies(raw: str | None) -> tuple:
    """يحوّل قايمة مفصولة بفواصل (IPs/CIDRs) لقايمة شبكات. قيمة غير صالحة تُرفض.

    تُستخدم عند الإقلاع (config) عشان نرفض الإعداد الغلط بدل ما نتجاهله بصمت.
    """
    networks = []
    for chunk in (raw or "").replace(";", ",").split(","):
        value = chunk.strip()
        if not value:
            continue
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError as exc:
            raise ValueError(f"شبكة بروكسي غير صالحة: {value!r}") from exc
    return tuple(networks)


def _parse_ip(host: str):
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _in_trusted(ip, trusted) -> bool:
    return any(ip in net for net in trusted)


def _normalize(host: str, trusted) -> str:
    """يرجّع معرّف العميل من عنوان واحد: العنوان لو عام، وإلا `unknown`.

    عنوان ضمن قايمة البروكسيات الموثوقة لا يُرجَع أبدًا كعميل.
    """
    ip = _parse_ip(host)
    if ip is None:
        return UNKNOWN
    if _is_private(host):
        return UNKNOWN
    if trusted and _in_trusted(ip, trusted):
        return UNKNOWN
    return host


def resolve_client_ip(request, trusted_proxies=()) -> str:
    """يرجّع معرّف العميل الآمن (OHB2-POST-PUB-01/F07).

    - من غير trusted proxies: IP الاتصال الفعلي بس (مفيش ثقة في الهيدرز) — fail closed.
    - مع trusted proxies: بنثق في `X-Forwarded-For` **بس** لو الند المباشر نفسه موثوق،
      وبعدها ناخد أول عنوان غير موثوق من اليمين للشمال (العميل الأصلي). أي عنوان مش صالح
      ⇒ `unknown`. الند المباشر مش موثوق ⇒ الهيدر يتجاهَل بالكامل.
    """
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None

    if trusted_proxies:
        peer_ip = _parse_ip(host) if host else None
        if peer_ip is not None and _in_trusted(peer_ip, trusted_proxies):
            header = request.headers.get("x-forwarded-for")
            if header:
                parts = [p.strip() for p in header.split(",") if p.strip()]
                for candidate in reversed(parts):
                    ip = _parse_ip(candidate)
                    if ip is None:
                        # عنصر مش صالح ⇒ ما نثقش في أي حاجة على شماله.
                        return UNKNOWN
                    if not _in_trusted(ip, trusted_proxies):
                        return _normalize(candidate, trusted_proxies)
            # مفيش هيدر (أو كله بروكسيات موثوقة) ⇒ الند المباشر آخر ملاحظة نعرفها.
            return _normalize(host, trusted_proxies)

    if not host:
        return UNKNOWN
    if _parse_ip(host) is None:
        return UNKNOWN
    return UNKNOWN if _is_private(host) else host
