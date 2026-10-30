"""تطبيق الـ Mini App (ASGI) — طبقة الـ web الرقيقة فوق نفس خدمات البوت (OHB2-05).

مبادئ:
- مفيش منطق أعمال هنا: الطلبات بتنادي نفس طبقة الخدمات/قاعدة البيانات اللي البوت بيستخدمها.
- مفيش اتصال SQLite تاني: نفس كائن `Database` المملوك للعملية الواحدة.
- مفيش تسريب أسرار: توكن البوت ومفتاح OpenHands ما بيتنقلوش للعميل أبدًا.
- مصادقة صارمة: التحقق من initData على السيرفر + قايمة المالك المسموح.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from ..config import Config
from ..features import is_hidden
from .initdata import DEFAULT_MAX_AGE, InitDataError, TelegramUser, validate_init_data
from .sessions import SessionStore

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"
COOKIE_NAME = "ohb_session"
MAX_BODY_BYTES = 16 * 1024
API_PREFIX = "/api/v1"

_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
}

# مسارات الـ API مسموح تشارك عبر نفس الأصل بس (same-origin)، وممنوع تتكاش.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "SAMEORIGIN",
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
# نفس الأصل + تحميل Telegram WebApp من cdn + ستايل/سكربت داخليين. مفيش مصادر خارجية تانية.
_API_CSP = (
    "default-src 'none'; frame-ancestors https://web.telegram.org https://*.telegram.org; "
    "base-uri 'none'; form-action 'none'"
)
_STATIC_CSP = (
    "default-src 'self'; script-src 'self' https://telegram.org; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors https://web.telegram.org https://*.telegram.org; "
    "base-uri 'none'; form-action 'none'; object-src 'none'"
)


def _json(payload: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status, headers=dict(_SECURITY_HEADERS))


def _error(status: int, code: str, message: str) -> JSONResponse:
    return _json({"error": code, "message": message}, status=status)


class MiniApp:
    """يملك حالة الـ web (مخزن الجلسات + الإعدادات) ويبني تطبيق Starlette.

    `db` هو **نفس** كائن قاعدة بيانات البوت (مفيش اتصال تاني) — بنقرأ منه قراءة فقط.
    """

    def __init__(self, config: Config, db=None) -> None:
        self._config = config
        self._db = db
        self.sessions = SessionStore(config.mini_app_session_ttl)
        self.max_age = config.mini_app_initdata_max_age or DEFAULT_MAX_AGE
        self.owner_id = config.owner_id
        self.router = Starlette(routes=self._routes())

    # ------------------------------------------------------------- helpers
    def _allowed(self, user_id: int) -> bool:
        return self._config.is_allowed(user_id)

    def _session_from_cookie(self, request):
        return self.sessions.get(request.cookies.get(COOKIE_NAME))

    def _set_session_cookie(self, response: Response, token: str) -> None:
        response.set_cookie(
            COOKIE_NAME,
            token,
            max_age=self._config.mini_app_session_ttl,
            httponly=True,
            secure=self._config.mini_app_cookie_secure,
            samesite="strict",
            path="/",
        )

    async def _read_body(self, request) -> dict:
        length = request.headers.get("content-length")
        if length is not None:
            try:
                declared = int(length)
            except ValueError:
                raise _BadJson() from None
            if declared > MAX_BODY_BYTES:
                raise _BodyTooLarge()
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            raise _BodyTooLarge()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise _BadJson() from exc
        if not isinstance(data, dict):
            raise _BadJson()
        return data

    # -------------------------------------------------------------- routes
    def _routes(self) -> list[Route]:
        return [
            Route("/health", self.health, methods=["GET"]),
            Route(f"{API_PREFIX}/auth", self.auth, methods=["POST"]),
            Route(f"{API_PREFIX}/auth/logout", self.logout, methods=["POST"]),
            Route(f"{API_PREFIX}/app/bootstrap", self.bootstrap, methods=["GET"]),
            Route(f"{API_PREFIX}/{{path:path}}", self.api_not_found, methods=["GET", "POST", "PUT", "PATCH", "DELETE"]),
            Route("/", self.index, methods=["GET"]),
            Route("/mini/", self.index, methods=["GET"]),
            Route("/mini/{path:path}", self.static_file, methods=["GET"]),
        ]

    async def health(self, request):
        return _json({"status": "ok", "service": "openhandbot-mini", "version": 1})

    async def auth(self, request):
        try:
            body = await self._read_body(request)
        except _BodyTooLarge:
            return _error(413, "payload_too_large", "الطلب كبير أوي.")
        except _BadJson:
            return _error(400, "bad_request", "صيغة الطلب غير صحيحة.")

        raw = body.get("initData")
        if not isinstance(raw, str) or not raw:
            return _error(401, "missing_initdata", "مفيش بيانات تهيئة.")

        try:
            user: TelegramUser = validate_init_data(
                raw, self._config.telegram_bot_token, max_age=self.max_age
            )
        except InitDataError as exc:
            log.warning("فشل التحقق من initData: %s", type(exc).__name__)
            return _error(401, "invalid_initdata", "تعذّر التحقق من الهوية.")

        if not self._allowed(user.id):
            log.warning("محاولة دخول من مستخدم غير مسموح (%s)", user.id)
            return _error(403, "forbidden", "الحساب ده مش مسموح له.")

        session = self.sessions.create(
            user.id,
            {
                "display_name": user.display_name,
                "username": user.username,
                "language_code": user.language_code,
            },
        )
        response = _json({"ok": True, "expires_in": self._config.mini_app_session_ttl})
        self._set_session_cookie(response, session.token)
        return response

    async def logout(self, request):
        self.sessions.revoke(request.cookies.get(COOKIE_NAME))
        response = _json({"ok": True})
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    async def bootstrap(self, request):
        session = self._session_from_cookie(request)
        if session is None:
            return _error(401, "unauthenticated", "محتاج تسجيل دخول.")
        if not self._allowed(session.user_id):
            self.sessions.revoke(session.token)
            return _error(403, "forbidden", "الحساب ده مش مسموح له.")
        return _json(
            {
                "user": {"display_name": session.profile.get("display_name", "")},
                "settings": {"notifications_enabled": self._config_notifications()},
                "mini_app": {"version": 1, "locale": "ar", "direction": "rtl"},
                "features": {
                    name: not is_hidden(name)
                    for name in ("files", "export", "cost", "followups")
                },
            }
        )

    def _config_notifications(self) -> bool:
        """لقطة قراءة-فقط من قاعدة بيانات البوت. لو حصل خطأ نرجّع الافتراضي (مفعّل)."""
        if self._db is None:
            return True
        try:
            return bool(self._db.get_notifications_enabled())
        except Exception:  # noqa: BLE001 - القراءة ما تكسّرش الصفحة
            return True

    async def api_not_found(self, request):
        return _error(404, "not_found", "المسار مش موجود.")

    async def index(self, request):
        return self._file_response(INDEX_FILE, fallback_to_index=True)

    async def static_file(self, request):
        rel = request.path_params.get("path", "")
        return self._serve_relative(rel)

    # -------------------------------------------------------------- static
    def _safe_path(self, rel: str) -> Path | None:
        if not rel:
            return None
        candidate = (STATIC_DIR / rel).resolve()
        try:
            candidate.relative_to(STATIC_DIR)
        except ValueError:
            return None
        return candidate

    def _serve_relative(self, rel: str) -> Response:
        candidate = self._safe_path(rel)
        if candidate is None or not candidate.is_file():
            # SPA: أي مسار مش ملف حقيقي ⇒ رجّع الصفحة الرئيسية (حالة "مش موجود" في الواجهة).
            return self._file_response(INDEX_FILE, fallback_to_index=False)
        return self._file_response(candidate, fallback_to_index=False)

    def _file_response(self, path: Path, fallback_to_index: bool) -> Response:
        try:
            body = path.read_bytes()
        except OSError:
            if fallback_to_index:
                return _error(500, "server_error", "الخدمة مش متاحة دلوقتي.")
            return self._file_response(INDEX_FILE, fallback_to_index=False)
        suffix = path.suffix.lower()
        content_type = _MIME_TYPES.get(suffix, "application/octet-stream")
        is_html = suffix == ".html"
        headers = {
            "Content-Type": content_type,
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": _STATIC_CSP if is_html else "default-src 'none'; frame-ancestors https://web.telegram.org https://*.telegram.org",
        }
        if is_html:
            # الصفحة نفسها ما تتكاشش، لكن الأصول ذات النسخة تتكاش من مسار /mini/.
            # ملاحظة: ما بنحطّش X-Frame-Options هنا عشان Telegram Web (iframe) يقدر يعرض
            # الـ Mini App؛ التقييد بالـ CSP frame-ancestors اللي بيسمح لتيليجرام بس.
            headers["Cache-Control"] = "no-store"
        else:
            headers["Cache-Control"] = "public, max-age=604800, immutable"
        return Response(body, media_type=content_type, headers=headers)


class _BodyTooLarge(Exception):
    pass


class _BadJson(Exception):
    pass


def build_web_app(config: Config, db=None) -> Starlette:
    """يبني تطبيق ASGI مربوط بنفس قاعدة بيانات البوت (بدون اتصال تاني)."""
    return MiniApp(config, db).router
