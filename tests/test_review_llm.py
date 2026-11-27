"""R4: provider adapter, snapshot binding, bounded HTTP, and stage execution."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from bot.db import AutoReviewProviderSnapshot

from bot.review.llm import (
    DirectProviderAdapter,
    ModelRequest,
    ModelResponse,
    ProviderAuthError,
    ProviderForbiddenError,
    ProviderBinding,
    ProviderConfigError,
    ProviderMalformedResponse,
    ProviderRateLimitError,
    ProviderRequestTooLarge,
    ProviderResponseError,
    ProviderResponseTooLarge,
    ProviderServerError,
    ProviderSnapshot,
    ProviderSnapshotMismatch,
    ProviderTransportError,
    execute_stage,
)
from bot.review.prompts import BlindReviewInput, build_blind_request

KEY = "sk-reviewer-SENTINEL-123456"
A = "a" * 40
B = "b" * 40
FP = "f" * 64


def snapshot(**over):
    value = {
        "provider": "testprovider",
        "api_base": "https://reviewer.invalid/v1",
        "model": "reviewer-model-v1",
        "config_fingerprint": FP,
        "config_json": json.dumps(
            {
                "provider": "testprovider",
                "api_base": "https://reviewer.invalid/v1",
                "model": "reviewer-model-v1",
                "settings": {},
            }
        ),
    }
    value.update(over)
    return SimpleNamespace(**value)


def binding(**over):
    snap = snapshot()
    cfg = SimpleNamespace(
        reviewer_provider="testprovider",
        reviewer_api_base="https://reviewer.invalid/v1",
        reviewer_model="reviewer-model-v1",
        reviewer_api_key=KEY,
    )
    for key, value in over.items():
        setattr(cfg, key, value)
    return ProviderBinding.from_config(cfg, snap)


def run_adapter(handler, *, timeout=20.0, max_request_bytes=256 * 1024, max_response_bytes=1024):
    async def runner():
        async with DirectProviderAdapter(
            binding(),
            transport=httpx.MockTransport(handler),
            timeout=timeout,
            max_request_bytes=max_request_bytes,
            max_response_bytes=max_response_bytes,
        ) as adapter:
            return await adapter.complete(
                ModelRequest("blind", "system", "user", "f" * 64)
            )

    return asyncio.run(runner())


def test_snapshot_accepts_the_r2_database_dataclass():
    db_snapshot = AutoReviewProviderSnapshot(
        id=1,
        provider="testprovider",
        api_base="https://reviewer.invalid/v1",
        model="reviewer-model-v1",
        config_json=json.dumps(
            {
                "provider": "testprovider",
                "api_base": "https://reviewer.invalid/v1",
                "model": "reviewer-model-v1",
                "settings": {},
            }
        ),
        config_fingerprint=FP,
        created_at="2026-11-24T00:00:00+00:00",
    )
    bound = ProviderSnapshot.from_db_snapshot(db_snapshot)
    assert bound.config_fingerprint == FP
    assert bound.model == "reviewer-model-v1"



def test_snapshot_and_binding_are_immutable_identity_checks():
    snap = ProviderSnapshot.from_db_snapshot(snapshot())
    assert snap.provider == "testprovider"
    assert snap.model == "reviewer-model-v1"
    assert snap.config_fingerprint == FP
    assert KEY not in repr(snap)
    bound = binding()
    assert KEY not in repr(bound)
    assert KEY not in str(bound)


@pytest.mark.parametrize(
    "over",
    [
        {"reviewer_provider": "other"},
        {"reviewer_api_base": "https://other.invalid/v1"},
        {"reviewer_model": "other-model"},
    ],
)

def test_current_config_cannot_silently_replace_snapshot(over):
    with pytest.raises(ProviderSnapshotMismatch):
        binding(**over)


def test_snapshot_rejects_secret_values_in_settings():
    bad = snapshot(
        config_json=json.dumps(
            {
                "provider": "testprovider",
                "api_base": "https://reviewer.invalid/v1",
                "model": "reviewer-model-v1",
                "settings": {"note": "ghp_SNAPSHOT_SECRET_1234567890"},
            }
        )
    )
    with pytest.raises(ProviderConfigError):
        ProviderSnapshot.from_db_snapshot(bad)


def test_snapshot_rejects_secretish_settings_and_identity_mismatch():
    bad = snapshot(
        config_json=json.dumps(
            {
                "provider": "testprovider",
                "api_base": "https://reviewer.invalid/v1",
                "model": "reviewer-model-v1",
                "settings": {"api_key": "must-not-be-here"},
            }
        )
    )
    with pytest.raises(ProviderConfigError):
        ProviderSnapshot.from_db_snapshot(bad)
    mismatch = snapshot(
        config_json=json.dumps(
            {
                "provider": "other",
                "api_base": "https://reviewer.invalid/v1",
                "model": "reviewer-model-v1",
                "settings": {},
            }
        )
    )
    with pytest.raises(ProviderConfigError):
        ProviderSnapshot.from_db_snapshot(mismatch)


def test_adapter_sends_expected_body_and_never_puts_token_in_url_or_repr():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    response = run_adapter(handler)
    assert response.text == "ok"
    assert response.provider == "testprovider"
    assert seen["url"] == "https://reviewer.invalid/v1/chat/completions"
    assert KEY not in seen["url"]
    assert seen["authorization"].startswith("Bearer ")
    assert seen["body"]["model"] == "reviewer-model-v1"
    assert seen["body"]["messages"][0]["role"] == "system"
    assert "stream" in seen["body"] and seen["body"]["stream"] is False


@pytest.mark.parametrize(
    "response,error",
    [
        (httpx.Response(401, json={}), ProviderAuthError),
        (httpx.Response(403, json={}), ProviderForbiddenError),
        (httpx.Response(500, json={}), ProviderServerError),
        (
            httpx.Response(302, headers={"location": "https://elsewhere.invalid"}),
            ProviderResponseError,
        ),
        (httpx.Response(429, headers={"retry-after": "7"}), ProviderRateLimitError),
        (httpx.Response(200, content=b"not-json"), ProviderMalformedResponse),
        (httpx.Response(200, json={}), ProviderMalformedResponse),
        (httpx.Response(200, json={"choices": []}), ProviderMalformedResponse),
        (httpx.Response(200, json={"choices": [{"message": {}}]}), ProviderMalformedResponse),
    ],
)

def test_adapter_maps_provider_failures_without_retry(response, error):
    calls = []

    def handler(request):
        calls.append(request)
        return response

    with pytest.raises(error):
        run_adapter(handler)
    assert len(calls) == 1


def test_adapter_maps_timeout_and_transport_errors():
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(ProviderTransportError):
        run_adapter(handler)


def test_adapter_bounds_response_and_request_sizes():
    def handler(request):
        return httpx.Response(
            200,
            headers={"content-length": "999999"},
            content=b"{}",
        )

    with pytest.raises(ProviderResponseTooLarge):
        run_adapter(handler, max_response_bytes=10)
    with pytest.raises(ProviderRequestTooLarge):
        run_adapter(
            lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
            max_request_bytes=10,
        )


def test_adapter_rejects_unsupported_encoding_and_redirect():
    def handler(request):
        return httpx.Response(200, headers={"content-encoding": "custom"}, content=b"{}")

    with pytest.raises(ProviderMalformedResponse):
        run_adapter(handler)


def test_adapter_validates_timeout_and_limit_bounds():
    with pytest.raises(ProviderConfigError):
        DirectProviderAdapter(binding(), timeout=0)
    with pytest.raises(ProviderConfigError):
        DirectProviderAdapter(binding(), max_response_bytes=0)
    with pytest.raises(ProviderConfigError):
        ProviderBinding.from_config(
            SimpleNamespace(
                reviewer_provider="testprovider",
                reviewer_api_base="https://reviewer.invalid/v1",
                reviewer_model="reviewer-model-v1",
                reviewer_api_key="",
            ),
            snapshot(),
        )


def blind_request():
    return build_blind_request(
        BlindReviewInput(
            repository="owner/repo",
            pr_number=1,
            branch="agent/x",
            base_sha=A,
            head_sha=B,
            diff_text=(
                "diff --git a/src/x.py b/src/x.py\n"
                "--- a/src/x.py\n"
                "+++ b/src/x.py\n"
                "@@ -1 +1 @@\n"
                "-old\n+new\n"
            ),
            ci_runs=None,
            ci_jobs=(),
            architecture_decisions=(),
            review_instructions=(),
        ),
        max_input_chars=10_000,
    )


def valid_blind_json():
    return json.dumps(
        {
            "schema_version": "r4.v1",
            "stage": "blind",
            "assessment": "clean",
            "summary": "clean",
            "findings": [],
            "reviewed_files": ["src/x.py"],
            "evidence_gaps": [],
        }
    )


class FakeAdapter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, request):
        self.calls.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return ModelResponse(item, 200, "testprovider", "reviewer-model-v1")


def test_execute_stage_accepts_valid_output():
    adapter = FakeAdapter([valid_blind_json()])
    result = asyncio.run(execute_stage(adapter, blind_request()))
    assert result.ok is True
    assert result.correction_used is False
    assert len(adapter.calls) == 1


def test_execute_stage_uses_one_bounded_correction_then_succeeds():
    adapter = FakeAdapter(["not-json", valid_blind_json()])
    result = asyncio.run(execute_stage(adapter, blind_request()))
    assert result.ok is True
    assert result.correction_used is True
    assert len(adapter.calls) == 2
    assert "CORRECTION" in adapter.calls[1].user
    assert "not-json" in adapter.calls[1].user


def test_execute_stage_blocks_after_second_invalid_output():
    adapter = FakeAdapter(["not-json", "still-not-json"])
    result = asyncio.run(execute_stage(adapter, blind_request()))
    assert result.ok is False
    assert result.status == "invalid_output"
    assert result.correction_used is True
    assert len(adapter.calls) == 2


def test_execute_stage_does_not_retry_provider_failure():
    adapter = FakeAdapter([ProviderAuthError("provider rejected credentials")])
    result = asyncio.run(execute_stage(adapter, blind_request()))
    assert result.ok is False
    assert result.status == "provider_error"
    assert result.correction_used is False
    assert len(adapter.calls) == 1
    assert KEY not in str(result)


def test_execute_stage_rejects_a_non_model_response():
    class BadAdapter:
        async def complete(self, request):
            return "not a model response"

    result = asyncio.run(execute_stage(BadAdapter(), blind_request()))
    assert result.status == "provider_error"
    assert result.error_code == "invalid_response"
    assert result.correction_used is False


def test_execute_stage_can_disable_correction():
    adapter = FakeAdapter(["not-json", valid_blind_json()])
    result = asyncio.run(
        execute_stage(adapter, blind_request(), allow_correction=False)
    )
    assert result.status == "invalid_output"
    assert len(adapter.calls) == 1


def test_correction_request_redacts_secret_from_invalid_output():
    adapter = FakeAdapter([f"not-json {KEY}", valid_blind_json()])
    result = asyncio.run(execute_stage(adapter, blind_request()))
    assert result.ok is True
    assert KEY not in adapter.calls[1].user
    assert "REDACTED" in adapter.calls[1].user
