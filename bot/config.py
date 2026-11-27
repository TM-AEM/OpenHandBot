import os
import re
from dataclasses import dataclass, field
from ipaddress import ip_address
from urllib.parse import urlsplit

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    openhands_api_key: str
    allowed_telegram_ids: frozenset[int] = field(default_factory=frozenset)
    owner_id: int = 0
    openhands_base_url: str = "https://app.all-hands.dev"
    log_level: str = "INFO"
    watcher_interval: int = 25
    db_path: str = "bot_state.sqlite3"
    # رابط الـ Mini App (HTTPS). فاضي = الميزة متوقفة (الزر بيقول "غير متاحة").
    mini_app_url: str = ""
    # OHB2-05: خلفية الـ Mini App (ASGI). مقفولة افتراضيًا عشان ما تغيّرش سلوك البوت الحالي.
    mini_app_enabled: bool = False
    mini_app_port: int = 12000
    mini_app_initdata_max_age: int = 300
    mini_app_session_ttl: int = 3600
    mini_app_cookie_secure: bool = True
    # OHB2-06: أصول مسموح بيها لطلبات تغيّر الحالة (Origin check). بتتشتق من
    # MINI_APP_URL لو مش محدّدة صريحة.
    mini_app_allowed_origins: frozenset[str] = field(default_factory=frozenset)
    # OHB2-06: حدود المعدّل (نافذة منزلقة، في الذاكرة).
    mini_app_auth_rate_per_minute: int = 10
    mini_app_auth_rate_per_hour: int = 30
    mini_app_api_rate_per_minute: int = 60
    mini_app_rate_max_keys: int = 4096
    # OHB2-POST-PUB-01/F07: شبكات البروكسيات الموثوقة (IPs/CIDRs). فاضية افتراضيًا ⇒
    # ما بنصدّقش أي هيدر تحويل، وبنستخدم IP الاتصال الفعلي (fail closed).
    mini_app_trusted_proxies: tuple[str, ...] = ()
    # OHB2-LIFE-03: مفتاح إيقاف **مستقلّ** لاستقبال المستندات المحلي (Document intake).
    # OHB2-WP01/OD-03: الافتراضي **False** (opt-in صريح). True عبر
    # `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1` فقط؛ False ⇒ تعطيل استقبال المستندات فقط:
    # مفيش get_file/تنزيل/صف/ملف/نداء OpenHands/سجل outbox، مع رسالة صادقة. ما بيعطّلش
    # النصوص/الأزرار/Mini App ولا مسار رفض الوسائط غير المدعومة (اللي يفضل شغّالًا).
    attachment_document_intake_enabled: bool = False
    # OHB2-AUTO-REVIEW-R2: إعدادات المراجعة المستقلة (معطّلة افتراضيًا). لا تُطبع أي أسرار.
    review_enabled: bool = False
    review_repos: frozenset[str] = field(default_factory=frozenset)
    reviewer_provider: str = ""
    reviewer_api_base: str = ""
    reviewer_api_key: str = ""
    reviewer_model: str = ""
    review_github_token: str = ""
    review_max_input_chars: int = 120_000
    review_ci_timeout_min: int = 15
    review_autofix_rounds: int = 0

    @property
    def secrets(self) -> tuple[str, ...]:
        extras: list[str] = []
        for value in (self.reviewer_api_key, self.review_github_token):
            if (
                value
                and value not in (self.telegram_bot_token, self.openhands_api_key)
                and value not in extras
            ):
                extras.append(value)
        return (self.telegram_bot_token, self.openhands_api_key, *extras)

    def __repr__(self) -> str:  # ما نطبعش الأسرار لو الـ Config اتسجّل بالغلط
        return (
            f"Config(owner_id={self.owner_id}, base_url={self.openhands_base_url!r}, "
            f"interval={self.watcher_interval}, db_path={self.db_path!r}, "
            f"review_enabled={self.review_enabled})"
        )

    @property
    def api_base(self) -> str:
        return self.openhands_base_url.rstrip("/") + "/api/v1"

    def is_allowed(self, user_id: int | None) -> bool:
        return user_id in self.allowed_telegram_ids


class ConfigError(RuntimeError):
    """خطأ إعداد. الرسالة بتذكر اسم المتغير بس، مش قيمته (ممكن تكون سر)."""


_TOKEN_RE = re.compile(r"^\d{3,}:[A-Za-z0-9_-]{8,}$")
_URL_RE = re.compile(r"^https?://[^\s/]+(/\S*)?$")
MIN_INTERVAL = 5
MAX_INTERVAL = 3600
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_LOOPBACK_HOSTS = {"localhost"}

# OHB2-AUTO-REVIEW-R2: حدود إعدادات المراجعة. القيم الافتراضية محايدة (مفيش provider/model
# حقيقي مثبّت)، والميزة نفسها معطّلة افتراضيًا.
REVIEW_MAX_INPUT_CHARS_DEFAULT = 120_000
REVIEW_MAX_INPUT_CHARS_MIN = 1_000
REVIEW_MAX_INPUT_CHARS_MAX = 1_000_000
REVIEW_CI_TIMEOUT_MIN_DEFAULT = 15
REVIEW_CI_TIMEOUT_MIN_MIN = 1
REVIEW_CI_TIMEOUT_MIN_MAX = 120
_REVIEW_PROVIDER_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_REVIEW_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_REVIEW_REPO_PART_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _is_loopback_host(host: str) -> bool:
    """هل المضيف loopback (تطوير محلي)؟ أي حاجة تانية بتتطلب HTTPS."""
    if not host:
        return False
    if host in _LOOPBACK_HOSTS:
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _clean(env, name: str, default: str = "") -> str:
    """يقرأ متغير بيئة، يشيل المسافات والأسطر الزيادة وعلامات التنصيص المحيطة."""
    value = (env.get(name) or default).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


_TRUE = {"1", "true", "yes", "on", "y"}
_FALSE = {"0", "false", "no", "off", "n"}


def _parse_bool(env, name: str, default: bool) -> bool:
    """يقرأ متغير بيئة منطقي بصرامة (OHB2-POST-PUB-01/F05).

    - غايب أو **فاضي صراحةً** ⇒ القيمة الافتراضية الموثّقة (سلوك متوافق للخلف).
    - قيم صحيحة معروفة (`1/true/yes/on/y` و `0/false/no/off/n`، غير حسّاسة لحالة الأحرف
      ومع تجاهل المسافات) ⇒ مقبولة.
    - أي قيمة **غير فاضية وغير معروفة** ⇒ `ConfigError`. الرسالة بتذكر اسم المتغيّر بس
      والقيم المقبولة، **مش** القيمة المزوّدة (ممكن تكون سر اتلزق بالغلط).
    """
    raw = (env.get(name) or "").strip().lower()
    if raw == "":
        return default
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ConfigError(
        f"{name} لازم يكون قيمة منطقية معروفة (1/0, true/false, yes/no, on/off)"
    )


def _parse_trusted_proxies(env) -> tuple[str, ...]:
    """يقرأ MINI_APP_TRUSTED_PROXIES (IPs/CIDRs مفصولة بفواصل). قيمة غير صالحة تُرفض.

    بنستخدم `clientip.parse_trusted_proxies` للتحقق، وبنرجّع النص المطبَّع (كـ tuple) عشان
    الـ Config يفضل قابل للتمثيل/المقارنة. الرسالة بتذكر اسم المتغيّر بس (بدون القيمة).
    """
    from .web.clientip import parse_trusted_proxies

    raw = _clean(env, "MINI_APP_TRUSTED_PROXIES")
    if not raw:
        return ()
    try:
        networks = parse_trusted_proxies(raw)
    except ValueError as exc:
        raise ConfigError(f"MINI_APP_TRUSTED_PROXIES فيه شبكة غير صالحة ({exc})") from exc
    return tuple(str(net) for net in networks)


def _parse_origins(env) -> frozenset[str]:
    """يقرأ MINI_APP_ALLOWED_ORIGINS (مفصولة بفواصل). كل أصل لازم يكون scheme://host[:port]."""
    raw = _clean(env, "MINI_APP_ALLOWED_ORIGINS")
    origins: set[str] = set()
    for chunk in raw.split(","):
        value = chunk.strip()
        if not value:
            continue
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ConfigError(
                "MINI_APP_ALLOWED_ORIGINS: كل أصل لازم يكون بالشكل scheme://host[:port]"
            )
        origins.add(f"{parts.scheme}://{parts.netloc}")
    return frozenset(origins)


def _parse_ids(raw: str) -> list[int]:
    """يرجّع الـ IDs بترتيبهم في النص (بعد إزالة التكرار).

    القرار 5: مستخدم واحد بس مسموح. لو النص فيه أكتر من ID مختلف، بنرفض بوضوح
    (من غير ما نطبع القيم نفسها — ممكن تكون أسرار اتلزقت بالغلط).
    """
    ids: list[int] = []
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            value = int(chunk)
        except ValueError as exc:
            # ما نكرّرش القيمة في الرسالة: ممكن حد يكون لزّق سر بالغلط.
            raise ConfigError("ALLOWED_TELEGRAM_ID فيه قيمة مش رقم صحيح") from exc
        if value <= 0:
            raise ConfigError("ALLOWED_TELEGRAM_ID لازم يكون أرقام موجبة")
        if value not in ids:
            ids.append(value)
    if len(ids) > 1:
        raise ConfigError(
            "ALLOWED_TELEGRAM_ID لازم يكون مستخدم واحد بس (القرار 5) — "
            "شيل الزيادة وسيب ID واحد"
        )
    return ids


def _parse_review_repos(raw: str) -> frozenset[str]:
    """يطبّع REVIEW_REPOS إلى owner/repo صغير ومُتحقَّق منه (بدون طباعة القيم)."""
    repos: set[str] = set()
    for chunk in raw.replace(";", ",").split(","):
        value = chunk.strip()
        if not value:
            continue
        parts = value.split("/")
        if len(parts) != 2:
            raise ConfigError("REVIEW_REPOS: كل مستودع لازم يكون بالشكل owner/repo")
        owner, repo = (part.strip().lower() for part in parts)
        if not owner or not repo or owner in {".", ".."} or repo in {".", ".."}:
            raise ConfigError("REVIEW_REPOS: كل مستودع لازم يكون بالشكل owner/repo")
        if not _REVIEW_REPO_PART_RE.match(owner) or not _REVIEW_REPO_PART_RE.match(repo):
            raise ConfigError("REVIEW_REPOS: اسم المالك/المستودع فيه محارف غير مسموحة")
        normalized = f"{owner}/{repo}"
        if normalized in repos:
            raise ConfigError("REVIEW_REPOS: مستودع مكرر")
        repos.add(normalized)
    return frozenset(repos)


def _parse_reviewer_provider(raw: str) -> str:
    if not raw:
        return ""
    value = raw.lower()
    if not _REVIEW_PROVIDER_RE.match(value):
        raise ConfigError(
            "REVIEWER_PROVIDER لازم يكون معرّف provider صالح (حروف صغيرة/أرقام/_/-)"
        )
    return value


def _parse_reviewer_model(raw: str) -> str:
    if not raw:
        return ""
    if not _REVIEW_MODEL_RE.match(raw):
        raise ConfigError("REVIEWER_MODEL لازم يكون معرّف موديل صالح بدون مسافات/محارف تحكّم")
    return raw


def _parse_reviewer_api_base(raw: str) -> str:
    if not raw:
        return ""
    if not _URL_RE.match(raw):
        raise ConfigError("REVIEWER_API_BASE لازم يبدأ بـ http:// أو https://")
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ConfigError("REVIEWER_API_BASE لازم يكون رابط صالح")
    if parts.username or parts.password:
        raise ConfigError("REVIEWER_API_BASE ما يحتويش على اسم مستخدم/كلمة سر")
    if parts.fragment:
        raise ConfigError("REVIEWER_API_BASE ما يحتويش على fragment (#...)")
    if parts.query:
        raise ConfigError("REVIEWER_API_BASE ما يحتويش على query (?...)")
    if parts.scheme != "https" and not _is_loopback_host(parts.hostname or ""):
        raise ConfigError("REVIEWER_API_BASE لازم يكون https:// لمضيف خارجي")
    return raw.rstrip("/")


def _parse_review_credential(raw: str, name: str) -> str:
    if not raw:
        return ""
    if len(raw) < 8 or any(ch.isspace() or ord(ch) < 32 for ch in raw):
        raise ConfigError(f"{name} شكله غلط (فيه مسافات أو قصير جداً)")
    return raw


def _parse_bounded_int(
    env, name: str, default: int, min_value: int, max_value: int
) -> int:
    raw = _clean(env, name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(
            f"{name} لازم يكون رقم صحيح بين {min_value} و{max_value}"
        ) from exc
    if not min_value <= value <= max_value:
        raise ConfigError(f"{name} لازم يكون بين {min_value} و{max_value}")
    return value


def _parse_review_autofix_rounds(env) -> int:
    raw = _clean(env, "REVIEW_AUTOFIX_ROUNDS", "0")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(
            "REVIEW_AUTOFIX_ROUNDS لازم يكون 0 (الإصلاح التلقائي غير منفّذ في R2)"
        ) from exc
    if value != 0:
        raise ConfigError(
            "REVIEW_AUTOFIX_ROUNDS لازم يكون 0 (الإصلاح التلقائي غير منفّذ في R2)"
        )
    return value


def load_config(env: dict | None = None) -> Config:
    if env is None:
        load_dotenv()
        env = os.environ

    token = _clean(env, "TELEGRAM_BOT_TOKEN")
    api_key = _clean(env, "OPENHANDS_API_KEY")
    allowed_raw = _clean(env, "ALLOWED_TELEGRAM_ID")

    missing = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", token),
            ("OPENHANDS_API_KEY", api_key),
            ("ALLOWED_TELEGRAM_ID", allowed_raw),
        )
        if not value
    ]
    if missing:
        raise ConfigError("متغيرات بيئة ناقصة: " + ", ".join(missing))

    if not _TOKEN_RE.match(token):
        raise ConfigError("TELEGRAM_BOT_TOKEN شكله غلط (المفروض زي 123456:ABC...)، راجع القيمة في BotFather")
    if len(api_key) < 8 or any(ch.isspace() or ord(ch) < 32 for ch in api_key):
        raise ConfigError("OPENHANDS_API_KEY شكله غلط (فيه مسافات أو قصير جداً)، انسخه تاني من الموقع")

    allowed = _parse_ids(allowed_raw)
    if not allowed:
        raise ConfigError("ALLOWED_TELEGRAM_ID لازم يحتوي رقم واحد على الأقل")

    base_url = _clean(env, "OPENHANDS_BASE_URL") or "https://app.all-hands.dev"
    if not _URL_RE.match(base_url):
        raise ConfigError("OPENHANDS_BASE_URL لازم يبدأ بـ http:// أو https://")
    # ممنوع إرسال مفتاح الـ API على HTTP عادي لمضيف خارجي (غير loopback).
    parts = urlsplit(base_url)
    if parts.scheme != "https" and not _is_loopback_host(parts.hostname or ""):
        raise ConfigError(
            "OPENHANDS_BASE_URL لازم يكون https:// لمضيف خارجي — "
            "HTTP العادي مسموح بس للتطوير المحلي (localhost/127.0.0.1)"
        )

    interval_raw = _clean(env, "WATCHER_INTERVAL", "25")
    try:
        interval = int(interval_raw)
    except ValueError as exc:
        raise ConfigError(
            f"WATCHER_INTERVAL لازم يكون رقم صحيح بين {MIN_INTERVAL} و{MAX_INTERVAL} ثانية"
        ) from exc
    if not MIN_INTERVAL <= interval <= MAX_INTERVAL:
        raise ConfigError(
            f"WATCHER_INTERVAL لازم يكون بين {MIN_INTERVAL} و{MAX_INTERVAL} ثانية"
        )

    log_level = (_clean(env, "LOG_LEVEL", "INFO") or "INFO").upper()
    if log_level not in _LOG_LEVELS:
        raise ConfigError("LOG_LEVEL لازم يكون واحد من: " + ", ".join(sorted(_LOG_LEVELS)))

    db_path = _clean(env, "DB_PATH") or "bot_state.sqlite3"

    # رابط الـ Mini App (اختياري). لو موجود لازم يكون https:// عام صالح.
    mini_app_url = _clean(env, "MINI_APP_URL")
    if mini_app_url:
        if not _URL_RE.match(mini_app_url) or not mini_app_url.startswith("https://"):
            raise ConfigError("MINI_APP_URL لازم يكون رابط https:// صالح")
        parts = urlsplit(mini_app_url)
        # OHB2-MINIAPP: رابط web_app لازم يكون نضيف: ممنوع userinfo (مستخدم:كلمة سر)،
        # وممنوع fragment (#...)، وممنوع query (?...) — تيليجرام بيفتح الرابط كما هو
        # وأي جزء إضافي ممكن يهرّب اعتماد أو يكسّر المصادقة. المسار مسموح (/mini/).
        if parts.username or parts.password:
            raise ConfigError("MINI_APP_URL ما يحتويش على اسم مستخدم/كلمة سر")
        if parts.fragment:
            raise ConfigError("MINI_APP_URL ما يحتويش على fragment (#...)")
        if parts.query:
            raise ConfigError("MINI_APP_URL ما يحتويش على query (?...)")
        host = parts.hostname or ""
        if _is_loopback_host(host):
            raise ConfigError("MINI_APP_URL لازم يكون رابط عام (مش loopback) لأن تيليجرام بيفتحه من جهاز المستخدم")

    # OHB2-05: خلفية الـ Mini App (ASGI). مقفولة افتراضيًا.
    mini_app_enabled = _parse_bool(env, "MINI_APP_ENABLED", False)
    # OHB2-N10-22: لو الميزة مفعّلة، الرابط العام بقى إعداد **مطلوب** — نفشل هنا برسالة
    # واضحة (ConfigError) بدل ما نفشل متأخر عند بناء التطبيق بـ RuntimeError. لو الميزة
    # مقفولة، الرابط مالوش أي تأثير (مفيش كسر لأي تشغيل مش بيستخدم الـ Mini App).
    if mini_app_enabled and not mini_app_url:
        raise ConfigError(
            "MINI_APP_ENABLED=1 لكن MINI_APP_URL فاضي — لازم رابط https عام للـ Mini App "
            "(أو اقفل الميزة بـ MINI_APP_ENABLED=0)"
        )
    port_raw = _clean(env, "MINI_APP_PORT", "12000")
    try:
        mini_app_port = int(port_raw)
    except ValueError as exc:
        raise ConfigError("MINI_APP_PORT لازم يكون رقم منفذ صحيح (1..65535)") from exc
    if not 1 <= mini_app_port <= 65535:
        raise ConfigError("MINI_APP_PORT لازم يكون بين 1 و 65535")

    def _positive(name: str, default: int) -> int:
        raw = _clean(env, name, str(default))
        try:
            value = int(raw)
        except ValueError as exc:
            raise ConfigError(f"{name} لازم يكون رقم صحيح موجب") from exc
        if value <= 0:
            raise ConfigError(f"{name} لازم يكون رقم موجب")
        return value

    # مهلة صلاحية initData (ثواني). افتراضي 300 (5 دقايق) زي توصية تيليجرام.
    mini_app_initdata_max_age = _positive("MINI_APP_INITDATA_MAX_AGE", 300)
    # عمر جلسة الـ Mini App (ثواني).
    mini_app_session_ttl = _positive("MINI_APP_SESSION_TTL", 3600)
    # كوكي الـ session لازم Secure في الإنتاج؛ ممكن يتقفل للتطوير المحلي على http.
    mini_app_cookie_secure = _parse_bool(env, "MINI_APP_COOKIE_SECURE", True)

    # OHB2-06: أصول مسموح بيها. افتراضيًا أصل MINI_APP_URL (scheme://host[:port]).
    # ممكن تتوسّع بـ MINI_APP_ALLOWED_ORIGINS (مفصولة بفواصل) للـ localhost أثناء التطوير.
    allowed_origins = _parse_origins(env)
    if mini_app_url and not allowed_origins:
        parts = urlsplit(mini_app_url)
        allowed_origins = frozenset({f"{parts.scheme}://{parts.netloc}"})

    # OHB2-06: حدود المعدّل (كلها أرقام موجبة).
    mini_app_auth_rate_per_minute = _positive("MINI_APP_AUTH_RATE_PER_MINUTE", 10)
    mini_app_auth_rate_per_hour = _positive("MINI_APP_AUTH_RATE_PER_HOUR", 30)
    mini_app_api_rate_per_minute = _positive("MINI_APP_API_RATE_PER_MINUTE", 60)
    mini_app_rate_max_keys = _positive("MINI_APP_RATE_MAX_KEYS", 4096)

    # OHB2-POST-PUB-01/F07: بروكسيات موثوقة صريحة (IPs/CIDRs مفصولة بفواصل). فاضية =
    # مفيش ثقة في أي هيدر تحويل. قيمة غير صالحة ⇒ ConfigError (نرفض الإعداد الغلط بدل
    # ما نتجاهله بصمت، وإلا نفتح باب تزوير IP).
    mini_app_trusted_proxies = _parse_trusted_proxies(env)

    # OHB2-WP01/OD-03: افتراضي **False** (opt-in صريح عبر =1)؛ القيمة غير الصالحة ترفض.
    attachment_document_intake_enabled = _parse_bool(
        env, "ATTACHMENT_DOCUMENT_INTAKE_ENABLED", False
    )

    # OHB2-AUTO-REVIEW-R2: إعدادات المراجعة. الميزة معطّلة افتراضيًا، والتحقق من المطلوب
    # بيحصل فقط عند REVIEW_ENABLED=1. أي قيمة غير صالحة ترفض بـ ConfigError بدون طبع القيمة.
    review_enabled = _parse_bool(env, "REVIEW_ENABLED", False)
    review_repos = _parse_review_repos(_clean(env, "REVIEW_REPOS"))
    reviewer_provider = _parse_reviewer_provider(_clean(env, "REVIEWER_PROVIDER"))
    reviewer_api_base = _parse_reviewer_api_base(_clean(env, "REVIEWER_API_BASE"))
    reviewer_api_key = _parse_review_credential(
        _clean(env, "REVIEWER_API_KEY"), "REVIEWER_API_KEY"
    )
    reviewer_model = _parse_reviewer_model(_clean(env, "REVIEWER_MODEL"))
    review_github_token = _parse_review_credential(
        _clean(env, "REVIEW_GITHUB_TOKEN"), "REVIEW_GITHUB_TOKEN"
    )
    review_max_input_chars = _parse_bounded_int(
        env,
        "REVIEW_MAX_INPUT_CHARS",
        REVIEW_MAX_INPUT_CHARS_DEFAULT,
        REVIEW_MAX_INPUT_CHARS_MIN,
        REVIEW_MAX_INPUT_CHARS_MAX,
    )
    review_ci_timeout_min = _parse_bounded_int(
        env,
        "REVIEW_CI_TIMEOUT_MIN",
        REVIEW_CI_TIMEOUT_MIN_DEFAULT,
        REVIEW_CI_TIMEOUT_MIN_MIN,
        REVIEW_CI_TIMEOUT_MIN_MAX,
    )
    review_autofix_rounds = _parse_review_autofix_rounds(env)

    if review_enabled:
        missing_review = [
            name
            for name, value in (
                ("REVIEW_REPOS", review_repos),
                ("REVIEWER_PROVIDER", reviewer_provider),
                ("REVIEWER_API_BASE", reviewer_api_base),
                ("REVIEWER_API_KEY", reviewer_api_key),
                ("REVIEWER_MODEL", reviewer_model),
                ("REVIEW_GITHUB_TOKEN", review_github_token),
            )
            if not value
        ]
        if missing_review:
            raise ConfigError(
                "متغيرات مراجعة ناقصة عند REVIEW_ENABLED=1: " + ", ".join(missing_review)
            )

    return Config(
        telegram_bot_token=token,
        openhands_api_key=api_key,
        allowed_telegram_ids=frozenset(allowed),
        owner_id=allowed[0],
        openhands_base_url=base_url,
        log_level=log_level,
        watcher_interval=interval,
        db_path=db_path,
        mini_app_url=mini_app_url,
        mini_app_enabled=mini_app_enabled,
        mini_app_port=mini_app_port,
        mini_app_initdata_max_age=mini_app_initdata_max_age,
        mini_app_session_ttl=mini_app_session_ttl,
        mini_app_cookie_secure=mini_app_cookie_secure,
        mini_app_allowed_origins=allowed_origins,
        mini_app_auth_rate_per_minute=mini_app_auth_rate_per_minute,
        mini_app_auth_rate_per_hour=mini_app_auth_rate_per_hour,
        mini_app_api_rate_per_minute=mini_app_api_rate_per_minute,
        mini_app_rate_max_keys=mini_app_rate_max_keys,
        mini_app_trusted_proxies=mini_app_trusted_proxies,
        attachment_document_intake_enabled=attachment_document_intake_enabled,
        review_enabled=review_enabled,
        review_repos=review_repos,
        reviewer_provider=reviewer_provider,
        reviewer_api_base=reviewer_api_base,
        reviewer_api_key=reviewer_api_key,
        reviewer_model=reviewer_model,
        review_github_token=review_github_token,
        review_max_input_chars=review_max_input_chars,
        review_ci_timeout_min=review_ci_timeout_min,
        review_autofix_rounds=review_autofix_rounds,
    )
