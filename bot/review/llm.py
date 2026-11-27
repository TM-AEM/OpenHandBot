"""Provider-neutral direct model adapter and bounded stage execution (R4).

The adapter is deliberately small and OpenAI-chat-compatible. Provider-specific
differences belong here, not in prompts, schemas, evidence, or verdict logic.
No retry is performed for an ambiguous provider request; the only second request
is an explicit, bounded schema-correction request after a valid provider response.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

import httpx

from bot.review.prompts import PromptBuildError, PromptRequest, build_correction_request
from bot.review.redact import redact_text
from bot.review.schema import (
    STAGE_ADVERSARIAL,
    STAGE_BLIND,
    AdversarialReviewOutput,
    BlindReviewOutput,
    SchemaError,
    parse_adversarial_review,
    parse_blind_review,
)

DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_REQUEST_BYTES = 256 * 1024
MAX_REQUEST_BYTES_LIMIT = 2 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES_LIMIT = 4 * 1024 * 1024


class ProviderError(RuntimeError):
    """Safe provider error; never includes API keys, prompts, or raw bodies."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: int | None = None,
        rate_limit_reset: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.rate_limit_reset = rate_limit_reset


class ProviderConfigError(ProviderError):
    pass


class ProviderSnapshotMismatch(ProviderConfigError):
    pass


class ProviderAuthError(ProviderError):
    pass


class ProviderForbiddenError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    pass


class ProviderServerError(ProviderError):
    pass


class ProviderTransportError(ProviderError):
    pass


class ProviderResponseError(ProviderError):
    pass


class ProviderMalformedResponse(ProviderResponseError):
    pass


class ProviderResponseTooLarge(ProviderResponseError):
    pass


class ProviderRequestTooLarge(ProviderResponseError):
    pass


@dataclass(frozen=True)
class ProviderSnapshot:
    provider: str
    api_base: str
    model: str
    config_fingerprint: str
    settings: Mapping[str, Any] = field(default_factory=dict)
    snapshot_id: int | None = None

    @classmethod
    def from_db_snapshot(cls, snapshot: Any) -> "ProviderSnapshot":
        if snapshot is None:
            raise ProviderConfigError("provider snapshot is missing")
        try:
            provider = snapshot.provider
            api_base = snapshot.api_base
            model = snapshot.model
            fingerprint = snapshot.config_fingerprint
            config_json = snapshot.config_json
            snapshot_id = getattr(snapshot, "id", None)
        except AttributeError as exc:
            raise ProviderConfigError("provider snapshot shape is invalid") from exc
        if not isinstance(config_json, str):
            raise ProviderConfigError("provider snapshot config is invalid")
        try:
            payload = json.loads(config_json)
        except (TypeError, ValueError) as exc:
            raise ProviderConfigError("provider snapshot config is invalid") from exc
        if not isinstance(payload, dict) or set(payload) - {
            "provider",
            "api_base",
            "model",
            "settings",
        }:
            raise ProviderConfigError("provider snapshot config is invalid")
        settings = payload.get("settings", {})
        if not isinstance(settings, dict) or _contains_secretish_key(settings):
            raise ProviderConfigError("provider snapshot settings are invalid")
        settings_scan = redact_text(
            json.dumps(settings, sort_keys=True), max_input_chars=20_000
        )
        if not settings_scan.safe or settings_scan.redactions:
            raise ProviderConfigError("provider snapshot settings are invalid")
        if (
            payload.get("provider") != provider
            or payload.get("api_base") != api_base
            or payload.get("model") != model
        ):
            raise ProviderConfigError("provider snapshot identity mismatch")
        if snapshot_id is not None and (
            not isinstance(snapshot_id, int)
            or isinstance(snapshot_id, bool)
            or snapshot_id <= 0
        ):
            raise ProviderConfigError("provider snapshot id is invalid")
        return cls(
            provider=_bounded_identity(provider, "provider"),
            api_base=_validate_api_base(api_base),
            model=_bounded_identity(model, "model"),
            config_fingerprint=_fingerprint(fingerprint),
            settings=settings,
            snapshot_id=snapshot_id,
        )

    def __repr__(self) -> str:
        return (
            f"ProviderSnapshot(provider={self.provider!r}, api_base={self.api_base!r}, "
            f"model={self.model!r}, config_fingerprint={self.config_fingerprint!r})"
        )


@dataclass(frozen=True)
class ProviderBinding:
    snapshot: ProviderSnapshot
    api_key: str = field(repr=False)

    @classmethod
    def from_config(cls, config: Any, snapshot: Any) -> "ProviderBinding":
        bound = (
            snapshot
            if isinstance(snapshot, ProviderSnapshot)
            else ProviderSnapshot.from_db_snapshot(snapshot)
        )
        if (
            getattr(config, "reviewer_provider", None) != bound.provider
            or getattr(config, "reviewer_api_base", None) != bound.api_base
            or getattr(config, "reviewer_model", None) != bound.model
        ):
            raise ProviderSnapshotMismatch("current reviewer config does not match snapshot")
        key = getattr(config, "reviewer_api_key", "")
        return cls(bound, _validate_api_key(key))

    def __repr__(self) -> str:
        return f"ProviderBinding(snapshot={self.snapshot!r})"


@dataclass(frozen=True)
class ModelRequest:
    stage: str
    system: str
    user: str
    input_fingerprint: str


@dataclass(frozen=True)
class ModelResponse:
    text: str
    status_code: int
    provider: str
    model: str


class ReviewProvider(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...


class DirectProviderAdapter:
    """OpenAI-compatible direct adapter with bounded HTTP and no automatic retries."""

    def __init__(
        self,
        binding: ProviderBinding,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    ) -> None:
        if not isinstance(binding, ProviderBinding):
            raise ProviderConfigError("provider binding is required")
        self._binding = binding
        self._timeout = _validate_timeout(timeout)
        self._max_request_bytes = _validate_limit(
            max_request_bytes, MAX_REQUEST_BYTES_LIMIT, "max_request_bytes"
        )
        self._max_response_bytes = _validate_limit(
            max_response_bytes, MAX_RESPONSE_BYTES_LIMIT, "max_response_bytes"
        )
        self._endpoint = _completion_endpoint(binding.snapshot.api_base)
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {binding.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": "OpenHandBot-review/0.1",
            },
            timeout=httpx.Timeout(
                connect=self._timeout,
                read=self._timeout,
                write=self._timeout,
                pool=self._timeout,
            ),
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        )

    @property
    def binding(self) -> ProviderBinding:
        return self._binding

    def __repr__(self) -> str:
        return f"DirectProviderAdapter(binding={self._binding!r})"

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "DirectProviderAdapter":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def complete(self, request: ModelRequest) -> ModelResponse:
        if not isinstance(request, ModelRequest):
            raise ProviderConfigError("model request is invalid")
        if request.stage not in (STAGE_BLIND, STAGE_ADVERSARIAL):
            raise ProviderConfigError("unsupported review stage")
        payload = {
            "model": self._binding.snapshot.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "stream": False,
            "temperature": 0,
        }
        try:
            body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ProviderConfigError("model request could not be serialized") from exc
        if len(body) > self._max_request_bytes:
            raise ProviderRequestTooLarge("model request exceeds safe limit")
        try:
            async with self._client.stream("POST", self._endpoint, content=body) as resp:
                if 300 <= resp.status_code < 400:
                    raise ProviderResponseError(
                        "provider redirect is not allowed", status_code=resp.status_code
                    )
                if resp.status_code == 401:
                    raise ProviderAuthError("provider rejected credentials", status_code=401)
                if resp.status_code == 403:
                    raise ProviderForbiddenError("provider rejected access", status_code=403)
                if resp.status_code == 429:
                    raise _rate_error(resp)
                if resp.status_code >= 500:
                    raise ProviderServerError(
                        "provider server error", status_code=resp.status_code
                    )
                if not 200 <= resp.status_code < 300:
                    raise ProviderResponseError(
                        "unexpected provider response", status_code=resp.status_code
                    )
                encoding = (resp.headers.get("content-encoding") or "").strip().lower()
                if encoding and encoding != "identity":
                    raise ProviderMalformedResponse("unsupported response encoding")
                declared = _content_length(resp)
                if declared is not None and declared > self._max_response_bytes:
                    raise ProviderResponseTooLarge("provider response exceeds safe limit")
                raw = await _read_capped(resp, self._max_response_bytes)
        except ProviderError:
            raise
        except httpx.HTTPError as exc:
            raise ProviderTransportError(
                f"provider transport failure ({type(exc).__name__})"
            ) from exc
        try:
            data = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ProviderMalformedResponse("provider response is not valid JSON") from exc
        if not isinstance(data, dict):
            raise ProviderMalformedResponse("provider response is not an object")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderMalformedResponse("provider response has no choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ProviderMalformedResponse("provider response has no message")
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise ProviderMalformedResponse("provider response has no content")
        return ModelResponse(
            text=text,
            status_code=resp.status_code,
            provider=self._binding.snapshot.provider,
            model=self._binding.snapshot.model,
        )


@dataclass(frozen=True)
class StageExecution:
    stage: str
    status: str  # ok | invalid_output | provider_error | blocked
    output: BlindReviewOutput | AdversarialReviewOutput | None
    error_code: str | None
    correction_used: bool
    request_fingerprint: str

    @property
    def ok(self) -> bool:
        return self.status == "ok" and self.output is not None


async def execute_stage(
    adapter: ReviewProvider,
    request: PromptRequest,
    *,
    allow_correction: bool = True,
) -> StageExecution:
    """Run one stage with no provider retries and at most one schema correction."""
    if not isinstance(request, PromptRequest):
        return StageExecution("", "blocked", None, "invalid_request", False, "")
    model_request = ModelRequest(
        stage=request.stage,
        system=request.system,
        user=request.user,
        input_fingerprint=request.input_fingerprint,
    )
    try:
        response = await adapter.complete(model_request)
    except ProviderError as exc:
        return StageExecution(
            request.stage,
            "provider_error",
            None,
            type(exc).__name__,
            False,
            request.input_fingerprint,
        )
    except Exception as exc:  # adapter must not leak details; fail closed
        return StageExecution(
            request.stage,
            "provider_error",
            None,
            type(exc).__name__,
            False,
            request.input_fingerprint,
        )
    if not isinstance(response, ModelResponse):
        return StageExecution(
            request.stage,
            "provider_error",
            None,
            "invalid_response",
            False,
            request.input_fingerprint,
        )
    try:
        output = _parse_response(request.stage, response.text)
        return StageExecution(
            request.stage, "ok", output, None, False, request.input_fingerprint
        )
    except SchemaError as first_error:
        if not allow_correction:
            return StageExecution(
                request.stage,
                "invalid_output",
                None,
                first_error.code,
                False,
                request.input_fingerprint,
            )
        try:
            correction = build_correction_request(
                request,
                response.text,
                first_error,
                max_input_chars=request.max_input_chars,
            )
        except PromptBuildError:
            return StageExecution(
                request.stage,
                "invalid_output",
                None,
                first_error.code,
                False,
                request.input_fingerprint,
            )
        try:
            corrected = await adapter.complete(
                ModelRequest(
                    stage=correction.stage,
                    system=correction.system,
                    user=correction.user,
                    input_fingerprint=correction.input_fingerprint,
                )
            )
        except ProviderError as exc:
            return StageExecution(
                request.stage,
                "provider_error",
                None,
                type(exc).__name__,
                True,
                request.input_fingerprint,
            )
        except Exception as exc:
            return StageExecution(
                request.stage,
                "provider_error",
                None,
                type(exc).__name__,
                True,
                request.input_fingerprint,
            )
        if not isinstance(corrected, ModelResponse):
            return StageExecution(
                request.stage,
                "provider_error",
                None,
                "invalid_response",
                True,
                request.input_fingerprint,
            )
        try:
            output = _parse_response(request.stage, corrected.text)
            return StageExecution(
                request.stage, "ok", output, None, True, request.input_fingerprint
            )
        except SchemaError as second_error:
            return StageExecution(
                request.stage,
                "invalid_output",
                None,
                second_error.code,
                True,
                request.input_fingerprint,
            )


def _parse_response(
    stage: str, text: str
) -> BlindReviewOutput | AdversarialReviewOutput:
    if stage == STAGE_BLIND:
        return parse_blind_review(text)
    if stage == STAGE_ADVERSARIAL:
        return parse_adversarial_review(text)
    raise SchemaError("unsupported_stage")


def _validate_api_key(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) < 8
        or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value)
    ):
        raise ProviderConfigError("reviewer API key is invalid")
    return value


def _validate_api_base(value: Any) -> str:
    if not isinstance(value, str):
        raise ProviderConfigError("provider api_base is invalid")
    parts = urlsplit(value)
    if (
        parts.scheme not in ("https", "http")
        or not parts.netloc
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or ".." in parts.path.split("/")
    ):
        raise ProviderConfigError("provider api_base is invalid")
    if parts.scheme != "https" and parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ProviderConfigError("provider api_base must be https for remote hosts")
    return value.rstrip("/")


def _completion_endpoint(api_base: str) -> str:
    if api_base.rstrip("/").endswith("/chat/completions"):
        return api_base.rstrip("/")
    return api_base.rstrip("/") + "/chat/completions"


def _bounded_identity(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(ord(ch) < 32 for ch in value)
    ):
        raise ProviderConfigError(f"provider {name} is invalid")
    return value


def _fingerprint(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise ProviderConfigError("provider snapshot fingerprint is invalid")
    return value


def _contains_secretish_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and any(
                marker in key.casefold()
                for marker in (
                    "token",
                    "api_key",
                    "apikey",
                    "secret",
                    "password",
                    "credential",
                    "authorization",
                )
            ):
                return True
            if _contains_secretish_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_secretish_key(item) for item in value)
    return False


def _validate_timeout(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ProviderConfigError("provider timeout is invalid")
    value = float(value)
    if not 0 < value <= MAX_TIMEOUT_SECONDS:
        raise ProviderConfigError("provider timeout is out of bounds")
    return value


def _validate_limit(value: Any, maximum: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
        raise ProviderConfigError(f"{name} is out of bounds")
    return value


def _rate_error(resp: httpx.Response) -> ProviderRateLimitError:
    retry_after = _int_header(resp, "retry-after")
    reset = _int_header(resp, "x-ratelimit-reset")
    return ProviderRateLimitError(
        "provider rate limit",
        status_code=resp.status_code,
        retry_after=retry_after,
        rate_limit_reset=reset,
    )


def _int_header(resp: httpx.Response, name: str) -> int | None:
    raw = (resp.headers.get(name) or "").strip()
    return int(raw) if raw.isdigit() else None


def _content_length(resp: httpx.Response) -> int | None:
    raw = (resp.headers.get("content-length") or "").strip()
    return int(raw) if raw.isdigit() else None


async def _read_capped(resp: httpx.Response, limit: int) -> bytes:
    if getattr(resp, "is_stream_consumed", False):
        body = resp.content
        if len(body) > limit:
            raise ProviderResponseTooLarge("provider response exceeds safe limit")
        return body
    buf = bytearray()
    async for chunk in resp.aiter_raw():
        if len(buf) + len(chunk) > limit:
            raise ProviderResponseTooLarge("provider response exceeds safe limit")
        buf += chunk
    return bytes(buf)
