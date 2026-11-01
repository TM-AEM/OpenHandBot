"""تطبيق الـ Mini App (ASGI) — طبقة الـ web الرقيقة فوق نفس خدمات البوت (OHB2-05/06).

مبادئ:
- مفيش منطق أعمال هنا: الطلبات بتنادي نفس طبقة الخدمات/قاعدة البيانات اللي البوت بيستخدمها.
- مفيش اتصال SQLite تاني: نفس كائن `Database` المملوك للعملية الواحدة.
- مفيش تسريب أسرار: توكن البوت ومفتاح OpenHands ما بيتنقلوش للعميل أبدًا.
- مصادقة صارمة: التحقق من initData على السيرفر + قايمة المالك المسموح.
- OHB2-06: تحديد معدّل (لكل IP على /auth، ولكل جلسة على المسارات المصادَقة)،
  وحماية Origin لطلبات تغيّر الحالة، وتحديد IP العميل بشكل متحفّظ (بدون ثقة في الهيدرز).
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from ..config import Config
from ..errors import ApiError, error_text
from .clientip import resolve_client_ip
from .initdata import DEFAULT_MAX_AGE, InitDataError, TelegramUser, validate_init_data
from .ratelimit import api_limiter, auth_limiter
from .services import MiniAppService, ValidationError
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


def _json(payload: dict, status: int = 200, headers: dict | None = None) -> JSONResponse:
    merged = dict(_SECURITY_HEADERS)
    if headers:
        merged.update(headers)
    return JSONResponse(payload, status_code=status, headers=merged)


def _error(status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
    return _json({"error": code, "message": message}, status=status, headers=headers)


class MiniApp:
    """يملك حالة الـ web (مخزن الجلسات + الإعدادات) ويبني تطبيق Starlette.

    `db` هو **نفس** كائن قاعدة بيانات البوت (مفيش اتصال تاني) — بنقرأ منه قراءة فقط.
    """

    def __init__(self, config: Config, db=None, client=None, application=None) -> None:
        self._config = config
        self._db = db
        self._service = MiniAppService(config, db, client, application)
        self.sessions = SessionStore(config.mini_app_session_ttl)
        self.max_age = config.mini_app_initdata_max_age or DEFAULT_MAX_AGE
        self.owner_id = config.owner_id
        self.allowed_origins = set(config.mini_app_allowed_origins)
        self.auth_limiter = auth_limiter(config)
        self.api_limiter = api_limiter(config)
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

    def _rate_limited(self, limiter, key: str) -> JSONResponse | None:
        allowed, retry = limiter.allow(key)
        if allowed:
            return None
        retry_int = max(1, int(math.ceil(retry))) if retry > 0 else 1
        return _error(
            429,
            "rate_limited",
            "طلبات كتير أوي، جرّب تاني بعد شوية.",
            headers={"Retry-After": str(retry_int)},
        )

    def _origin_ok(self, request) -> bool:
        """طلبات تغيّر الحالة لازم تكون من نفس الأصل (دفاع CSRF على طبقة الـ Origin).

        `Sec-Fetch-Site` إشارة إضافية (مش بديل): لو المتصفح قال صريح `cross-site`،
        نرفض على طول. غياب الهيدر ما بيرفضش (عملاء مش متصفحات)، والـ Origin هو الحكم.
        """
        if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
            return False
        origin = request.headers.get("origin")
        if not origin:
            return False
        if origin in self.allowed_origins:
            return True
        # شبكة أمان للتطوير: نفس الأصل المطلق لطلب الـ http المحلي.
        host = request.headers.get("host")
        if host and origin in (f"http://{host}", f"https://{host}"):
            return True
        return False

    # -------------------------------------------------------------- routes
    def _routes(self) -> list[Route]:
        return [
            Route("/health", self.health, methods=["GET"]),
            Route(f"{API_PREFIX}/auth", self.auth, methods=["POST"]),
            Route(f"{API_PREFIX}/auth/logout", self.logout, methods=["POST"]),
            Route(f"{API_PREFIX}/app/bootstrap", self.bootstrap, methods=["GET"]),
            Route(f"{API_PREFIX}/app/notifications", self.notifications, methods=["POST"]),
            Route(f"{API_PREFIX}/notifications", self.notification_inbox, methods=["GET"]),
            Route(
                f"{API_PREFIX}/notifications/read-all",
                self.notifications_read_all,
                methods=["POST"],
            ),
            Route(
                f"{API_PREFIX}/notifications/{{item_id}}/read",
                self.notification_read,
                methods=["POST"],
            ),
            Route(f"{API_PREFIX}/conversations", self.conversations, methods=["GET"]),
            Route(
                f"{API_PREFIX}/conversations/{{conversation_id}}",
                self.conversation_detail,
                methods=["GET"],
            ),
            Route(
                f"{API_PREFIX}/conversations/{{conversation_id}}/status",
                self.conversation_status,
                methods=["GET"],
            ),
            Route(
                f"{API_PREFIX}/conversations/{{conversation_id}}/cost",
                self.conversation_cost,
                methods=["GET"],
            ),
            Route(
                f"{API_PREFIX}/conversations/{{conversation_id}}/files",
                self.conversation_files,
                methods=["GET"],
            ),
            Route(
                f"{API_PREFIX}/conversations/{{conversation_id}}/file",
                self.conversation_file_preview,
                methods=["GET"],
            ),
            Route(
                f"{API_PREFIX}/conversations/{{conversation_id}}/prompt",
                self.conversation_prompt,
                methods=["POST"],
            ),
            Route(f"{API_PREFIX}/operations/outbox", self.outbox_operation, methods=["GET"]),
            Route(f"{API_PREFIX}/operations/creation", self.creation_operation, methods=["GET"]),
            Route(
                f"{API_PREFIX}/operations/outbox/reconcile",
                self.outbox_reconcile,
                methods=["POST"],
            ),
            Route(
                f"{API_PREFIX}/conversations/{{conversation_id}}/watch",
                self.conversation_watch,
                methods=["POST"],
            ),
            Route(
                f"{API_PREFIX}/conversations/{{conversation_id}}/watch",
                self.conversation_unwatch,
                methods=["DELETE"],
            ),
            Route(f"{API_PREFIX}/watches", self.watches, methods=["GET"]),
            Route(f"{API_PREFIX}/repositories", self.repositories, methods=["GET"]),
            Route(f"{API_PREFIX}/chats", self.create_chat, methods=["POST"]),
            Route(
                f"{API_PREFIX}/{{path:path}}",
                self.api_not_found,
                methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            ),
            Route("/", self.index, methods=["GET"]),
            Route("/mini/", self.index, methods=["GET"]),
            Route("/mini/{path:path}", self.static_file, methods=["GET"]),
        ]

    # --------------------------------------------------------------- guard
    async def _guarded(self, request, *, state_changing: bool):
        """يرجّع (session, error_response). بيفحص المعدّل والجلسة والـ Origin.

        ترتيب الفحص: حد المعدّل (قبل أي شغل) ⇒ الجلسة ⇒ Origin (لو طلب بيغيّر الحالة).
        """
        session = self._session_from_cookie(request)
        key = session.token if session is not None else f"ip:{resolve_client_ip(request)}"
        limited = self._rate_limited(self.api_limiter, key)
        if limited is not None:
            return None, limited
        if session is None:
            return None, _error(401, "unauthenticated", "محتاج تسجيل دخول.")
        if not self._allowed(session.user_id):
            self.sessions.revoke(session.token)
            return None, _error(403, "forbidden", "الحساب ده مش مسموح له.")
        if state_changing and not self._origin_ok(request):
            return None, _error(403, "bad_origin", "الطلب جاي من أصل غير مسموح.")
        return session, None

    # -------------------------------------------------------------- health
    async def health(self, request):
        return _json({"status": "ok", "service": "openhandbot-mini", "version": 1})

    # ---------------------------------------------------------------- auth
    async def auth(self, request):
        limited = self._rate_limited(self.auth_limiter, resolve_client_ip(request))
        if limited is not None:
            return limited
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
        session, err = await self._guarded(request, state_changing=True)
        if err is not None:
            return err
        self.sessions.revoke(session.token)
        response = _json({"ok": True})
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    # ----------------------------------------------------------- bootstrap
    async def bootstrap(self, request):
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        return _json(self._service.bootstrap(session))

    async def notifications(self, request):
        session, err = await self._guarded(request, state_changing=True)
        if err is not None:
            return err
        try:
            body = await self._read_body(request)
        except _BodyTooLarge:
            return _error(413, "payload_too_large", "الطلب كبير أوي.")
        except _BadJson:
            return _error(400, "bad_request", "صيغة الطلب غير صحيحة.")
        enabled = body.get("enabled")
        if not isinstance(enabled, bool):
            return _error(400, "bad_request", "قيمة الإشعارات لازم تكون true أو false.")
        try:
            state = self._service.set_notifications(enabled)
        except ApiError as exc:
            return self._api_error(exc)
        return _json({"ok": True, "notifications_enabled": state})

    # ---------------------------------------------------- notification inbox
    async def notification_inbox(self, request):
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        try:
            page = int(request.query_params.get("page", "0") or 0)
        except ValueError:
            return _error(400, "bad_request", "رقم الصفحة غير صالح.")
        unread_only = request.query_params.get("unread") in ("1", "true")
        try:
            data = self._service.list_notifications(page=page, unread_only=unread_only)
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def notification_read(self, request):
        session, err = await self._guarded(request, state_changing=True)
        if err is not None:
            return err
        try:
            data = self._service.mark_notification_read(request.path_params.get("item_id", ""))
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def notifications_read_all(self, request):
        session, err = await self._guarded(request, state_changing=True)
        if err is not None:
            return err
        try:
            data = self._service.mark_all_notifications_read()
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    # ------------------------------------------------------- conversations
    async def conversations(self, request):
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        try:
            page = int(request.query_params.get("page", "0") or 0)
        except ValueError:
            return _error(400, "bad_request", "رقم الصفحة غير صالح.")
        refresh = request.query_params.get("refresh") == "1"
        try:
            data = await self._service.list_conversations(page=page, refresh=refresh)
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def conversation_detail(self, request):
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        try:
            data = await self._service.get_conversation(
                request.path_params.get("conversation_id", "")
            )
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def conversation_status(self, request):
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        try:
            data = await self._service.get_status(request.path_params.get("conversation_id", ""))
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def conversation_cost(self, request):
        """OHB2-09-04: تكلفة/استهلاك شات (read-only، مصادَقة)."""
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        try:
            data = await self._service.get_cost(request.path_params.get("conversation_id", ""))
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def conversation_files(self, request):
        """OHB2-09-02: قايمة ملفات شات مصرّح به (read-only، مصادَقة)."""
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        try:
            data = await self._service.list_files(
                request.path_params.get("conversation_id", "")
            )
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def conversation_file_preview(self, request):
        """OHB2-09-02: معاينة نصية محدودة لملف من قايمة الشات."""
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        try:
            data = await self._service.read_file_preview(
                request.path_params.get("conversation_id", ""),
                request.query_params.get("path", ""),
            )
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def conversation_prompt(self, request):
        session, err = await self._guarded(request, state_changing=True)
        if err is not None:
            return err
        try:
            body = await self._read_body(request)
        except _BodyTooLarge:
            return _error(413, "payload_too_large", "الطلب كبير أوي.")
        except _BadJson:
            return _error(400, "bad_request", "صيغة الطلب غير صحيحة.")
        try:
            data = await self._service.send_prompt(
                request.path_params.get("conversation_id", ""),
                body.get("text", ""),
                body.get("client_ref"),
            )
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def outbox_operation(self, request):
        """حالة عملية برومت: بـ id= أو بـ conversation_id + client_ref (بعد نتيجة غامضة)."""
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        try:
            data = self._lookup_outbox(request)
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    def _lookup_outbox(self, request) -> dict:
        raw_id = (request.query_params.get("id") or "").strip()
        ref = (request.query_params.get("client_ref") or "").strip()
        if raw_id:
            try:
                outbox_id = int(raw_id)
            except ValueError:
                raise ValidationError("رقم العملية غير صالح") from None
            return self._service.outbox_operation(outbox_id)
        if ref:
            conversation_id = request.query_params.get("conversation_id") or ""
            found = self._service.find_outbox_operation(conversation_id, ref)
            if found is None:
                raise ApiError("العملية مش موجودة.", 404)
            return found
        raise ValidationError("لازم تحدّد id أو client_ref")

    async def creation_operation(self, request):
        """حالة عملية إنشاء شات: بـ id= أو بـ client_ref (بعد نتيجة غامضة)."""
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        try:
            data = self._lookup_creation(request)
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def outbox_reconcile(self, request):
        """OHB2-09-05: تسوية يدوية لعملية برومت (discard/mark_sent) — parity مع البوت."""
        session, err = await self._guarded(request, state_changing=True)
        if err is not None:
            return err
        try:
            body = await self._read_body(request)
        except _BodyTooLarge:
            return _error(413, "payload_too_large", "الطلب كبير أوي.")
        except _BadJson:
            return _error(400, "bad_request", "صيغة الطلب غير صحيحة.")
        raw_id = body.get("id")
        try:
            outbox_id = int(raw_id)
        except (TypeError, ValueError):
            return _error(400, "bad_request", "رقم العملية غير صالح")
        try:
            data = self._service.reconcile_outbox(outbox_id, (body.get("action") or "").strip())
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    def _lookup_creation(self, request) -> dict:
        raw_id = (request.query_params.get("id") or "").strip()
        ref = (request.query_params.get("client_ref") or "").strip()
        if raw_id:
            try:
                job_id = int(raw_id)
            except ValueError:
                raise ValidationError("رقم العملية غير صالح") from None
            return self._service.creation_operation(job_id)
        if ref:
            found = self._service.find_creation_operation(ref)
            if found is None:
                raise ApiError("العملية مش موجودة.", 404)
            return found
        raise ValidationError("لازم تحدّد id أو client_ref")

    async def conversation_watch(self, request):
        session, err = await self._guarded(request, state_changing=True)
        if err is not None:
            return err
        try:
            data = await self._service.watch(request.path_params.get("conversation_id", ""))
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def conversation_unwatch(self, request):
        session, err = await self._guarded(request, state_changing=True)
        if err is not None:
            return err
        try:
            data = self._service.unwatch(request.path_params.get("conversation_id", ""))
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def watches(self, request):
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        try:
            page = int(request.query_params.get("page", "0") or 0)
        except ValueError:
            page = 0
        try:
            data = self._service.list_watches(page=page)
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def repositories(self, request):
        session, err = await self._guarded(request, state_changing=False)
        if err is not None:
            return err
        try:
            page = int(request.query_params.get("page", "0") or 0)
        except ValueError:
            page = 0
        try:
            data = await self._service.list_repositories(
                query=request.query_params.get("q", ""), page=page
            )
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    async def create_chat(self, request):
        session, err = await self._guarded(request, state_changing=True)
        if err is not None:
            return err
        try:
            body = await self._read_body(request)
        except _BodyTooLarge:
            return _error(413, "payload_too_large", "الطلب كبير أوي.")
        except _BadJson:
            return _error(400, "bad_request", "صيغة الطلب غير صحيحة.")
        try:
            data = await self._service.create_chat(
                body.get("repository", ""), body.get("text", ""), body.get("client_ref")
            )
        except ValidationError as exc:
            return _error(400, "bad_request", str(exc))
        except ApiError as exc:
            return self._api_error(exc)
        return _json(data)

    def _api_error(self, exc: ApiError) -> JSONResponse:
        status = exc.status_code if exc.status_code and 400 <= exc.status_code < 600 else 502
        if status >= 500:
            log.warning("خطأ خدمة في الـ Mini App: %s", type(exc).__name__)
        code = getattr(exc, "code", None) or "api_error"
        return _error(status, code, error_text(exc))

    async def api_not_found(self, request):
        return _error(404, "not_found", "المسار مش موجود.")

    # -------------------------------------------------------------- static
    async def index(self, request):
        return self._file_response(INDEX_FILE, fallback_to_index=True)

    async def static_file(self, request):
        rel = request.path_params.get("path", "")
        return self._serve_relative(rel)

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


def build_web_app(config: Config, db=None, client=None, application=None) -> Starlette:
    """يبني تطبيق ASGI مربوط بنفس قاعدة بيانات البوت (بدون اتصال تاني)."""
    return MiniApp(config, db, client, application).router
