"""R3: read-only GitHub API primitives, SHA provenance, and safe errors."""
import asyncio
import json

import httpx
import pytest

from bot.review.github import (
    BranchVerification,
    GitHubAuthError,
    GitHubClient,
    GitHubForbiddenError,
    GitHubMalformedResponse,
    GitHubNotFoundError,
    GitHubPaginationError,
    GitHubRateLimitError,
    GitHubRepoNotAllowed,
    GitHubResponseError,
    GitHubResponseTooLarge,
    GitHubServerError,
    GitHubShaMismatchError,
    GitHubTransportError,
)

TOKEN = "ghp_FAKE_REVIEW_TOKEN_1234567890"
REPO = "Owner/Repo"
A = "a" * 40
B = "b" * 40
C = "c" * 40


def _run(handler, method, *args, client_kwargs=None, **kwargs):
    async def runner():
        async with GitHubClient(
            TOKEN,
            allowed_repositories={REPO},
            transport=httpx.MockTransport(handler),
            **(client_kwargs or {}),
        ) as client:
            return await getattr(client, method)(*args, **kwargs)

    return asyncio.run(runner())


def _branch(name, sha, protected=False):
    return {"name": name, "commit": {"sha": sha}, "protected": protected}


def _run_payload(head_sha=B, conclusion="success", status="completed", run_id=1):
    return {
        "id": run_id,
        "name": "CI",
        "head_sha": head_sha,
        "head_branch": "agent/x",
        "status": status,
        "conclusion": conclusion,
        "event": "push",
        "run_attempt": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _job_payload(head_sha=B, run_id=1, job_id=2):
    return {
        "id": job_id,
        "run_id": run_id,
        "name": "test",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": "success",
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:00:01Z",
    }


# --------------------------------------------------------------- branches
def test_list_agent_branches_filters_and_paginates_safely():
    seen = []

    def handler(request):
        assert request.method == "GET"
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        assert TOKEN not in str(request.url)
        seen.append(dict(request.url.params))
        if request.url.params["page"] == "1":
            return httpx.Response(
                200,
                json=[
                    _branch("agent/one", A),
                    _branch("main", B, protected=True),
                ],
            )
        return httpx.Response(200, json=[_branch("agent/two", C)])

    result = _run(
        handler,
        "list_agent_branches",
        REPO,
        client_kwargs={"per_page": 2, "max_pages": 3},
    )
    assert [b.name for b in result] == ["agent/one", "agent/two"]
    assert [p["page"] for p in seen] == ["1", "2"]
    assert all(p["per_page"] == "2" for p in seen)


def test_get_branch_returns_exact_metadata():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/repos/owner/repo/branches/agent/x"
        return httpx.Response(200, json=_branch("agent/x", A, protected=True))

    branch = _run(handler, "get_branch", REPO, "agent/x")
    assert branch.sha == A
    assert branch.protected is True


def test_missing_branch_is_not_found():
    def handler(request):
        return httpx.Response(404, json={"message": "not found"})

    with pytest.raises(GitHubNotFoundError) as exc:
        _run(handler, "get_branch", REPO, "agent/missing")
    assert TOKEN not in str(exc.value)
    assert exc.value.status_code == 404


def test_branch_movement_is_explicit():
    def handler(request):
        return httpx.Response(200, json=_branch("agent/x", A))

    assert _run(handler, "verify_branch_sha", REPO, "agent/x", A).status == "unchanged"
    moved = _run(handler, "verify_branch_sha", REPO, "agent/x", B)
    assert moved == BranchVerification("owner/repo", "agent/x", B, A, "moved")


def test_branch_missing_and_blocked_are_explicit():
    def missing(request):
        return httpx.Response(404, json={"message": "not found"})

    def forbidden(request):
        return httpx.Response(403, json={"message": "forbidden"})

    assert _run(missing, "verify_branch_sha", REPO, "agent/x", A).status == "missing"
    blocked = _run(forbidden, "verify_branch_sha", REPO, "agent/x", A)
    assert blocked.status == "blocked"
    assert blocked.error_class == "GitHubForbiddenError"


# ---------------------------------------------------------------- compare
def test_compare_is_bound_to_requested_base_and_head():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == f"/repos/owner/repo/compare/{A}...{B}"
        return httpx.Response(
            200,
            json={
                "base_commit": {"sha": A},
                "merge_base_commit": {"sha": A},
                "commits": [{"sha": A}, {"sha": B}],
                "files": [
                    {
                        "filename": "src/x.py",
                        "status": "modified",
                        "additions": 1,
                        "deletions": 1,
                        "changes": 2,
                        "patch": "@@ -1 +1 @@",
                    }
                ],
                "ahead_by": 1,
                "behind_by": 0,
            },
        )

    result = _run(handler, "compare", REPO, A, B)
    assert result.status == "verified"
    assert result.observed_base_sha == A
    assert result.observed_head_sha == B
    assert result.merge_base_sha == A
    assert result.commits == (A, B)
    assert result.files[0].filename == "src/x.py"
    assert result.files[0].patch == "@@ -1 +1 @@"


@pytest.mark.parametrize(
    "payload, expected",
    [
        (
            {
                "base_commit": {"sha": C},
                "merge_base_commit": {"sha": A},
                "commits": [{"sha": B}],
            },
            "base_sha_mismatch",
        ),
        (
            {
                "base_commit": {"sha": A},
                "merge_base_commit": {"sha": A},
                "commits": [{"sha": C}],
            },
            "head_sha_mismatch",
        ),
        (
            {
                "base_commit": {"sha": A},
                "merge_base_commit": {"sha": C},
                "commits": [{"sha": B}],
            },
            "merge_base_mismatch",
        ),
    ],
)
def test_compare_rejects_evidence_for_another_sha(payload, expected):
    def handler(request):
        return httpx.Response(200, json=payload)

    result = _run(handler, "compare", REPO, A, B)
    assert result.status == expected
    assert result.files == ()
    assert result.commits == ()


def test_compare_invalid_sha_is_rejected_before_http():
    called = {"n": 0}

    def handler(request):
        called["n"] += 1
        return httpx.Response(200, json={})

    with pytest.raises(ValueError):
        _run(handler, "compare", REPO, A.upper(), B)
    assert called["n"] == 0


# ----------------------------------------------------------------- actions
def test_workflow_runs_require_all_runs_on_the_requested_sha():
    def handler(request):
        assert request.method == "GET"
        assert request.url.params["head_sha"] == B
        return httpx.Response(200, json={"workflow_runs": [_run_payload()]})

    evidence = _run(handler, "get_workflow_runs_for_sha", REPO, B)
    assert evidence.status == "verified"
    assert evidence.ci_state == "success"
    assert evidence.is_success is True


def test_workflow_run_with_another_sha_is_stale():
    def handler(request):
        return httpx.Response(200, json={"workflow_runs": [_run_payload(head_sha=C)]})

    evidence = _run(handler, "get_workflow_runs_for_sha", REPO, B)
    assert evidence.status == "sha_mismatch"
    assert evidence.ci_state == "stale"
    assert evidence.runs == ()
    assert evidence.observed_head_shas == (C,)
    assert evidence.is_success is False


@pytest.mark.parametrize(
    "status, conclusion, expected",
    [
        ("queued", None, "pending"),
        ("in_progress", None, "pending"),
        ("completed", "failure", "failure"),
        ("completed", "cancelled", "cancelled"),
        ("completed", "skipped", "skipped"),
        ("completed", "success", "success"),
        ("completed", None, "mixed"),
    ],
)
def test_workflow_conclusions_are_not_treated_as_success(status, conclusion, expected):
    def handler(request):
        return httpx.Response(
            200,
            json={"workflow_runs": [_run_payload(status=status, conclusion=conclusion)]},
        )

    evidence = _run(handler, "get_workflow_runs_for_sha", REPO, B)
    assert evidence.ci_state == expected
    assert evidence.is_success is (expected == "success")


def test_existing_run_is_not_success_when_pending_or_empty():
    def pending(request):
        return httpx.Response(
            200, json={"workflow_runs": [_run_payload(status="queued", conclusion=None)]}
        )

    def empty(request):
        return httpx.Response(200, json={"workflow_runs": []})

    assert _run(pending, "get_workflow_runs_for_sha", REPO, B).is_success is False
    missing = _run(empty, "get_workflow_runs_for_sha", REPO, B)
    assert missing.ci_state == "missing"
    assert missing.is_success is False


def test_list_run_jobs_is_bound_to_run_and_sha():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/repos/owner/repo/actions/runs/1/jobs"
        return httpx.Response(200, json={"jobs": [_job_payload()]})

    evidence = _run(handler, "list_run_jobs", REPO, 1, B)
    assert evidence.status == "verified"
    assert evidence.jobs[0].head_sha == B
    assert evidence.jobs[0].run_id == 1


def test_jobs_with_another_sha_or_run_are_stale():
    def other_sha(request):
        return httpx.Response(200, json={"jobs": [_job_payload(head_sha=C)]})

    def other_run(request):
        return httpx.Response(200, json={"jobs": [_job_payload(run_id=9)]})

    for handler in (other_sha, other_run):
        evidence = _run(handler, "list_run_jobs", REPO, 1, B)
        assert evidence.status == "sha_mismatch"
        assert evidence.jobs == ()


def test_get_workflow_run_returns_exact_run():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/repos/owner/repo/actions/runs/1"
        return httpx.Response(200, json=_run_payload())

    run = _run(handler, "get_workflow_run", REPO, 1, expected_head_sha=B)
    assert run.run_id == 1
    assert run.head_sha == B
    assert run.conclusion == "success"


def test_get_workflow_run_checks_expected_sha():
    def handler(request):
        return httpx.Response(200, json=_run_payload(head_sha=C))

    with pytest.raises(GitHubShaMismatchError):
        _run(handler, "get_workflow_run", REPO, 1, expected_head_sha=B)


def test_get_workflow_run_invalid_expected_sha_makes_no_request():
    called = {"n": 0}

    def handler(request):
        called["n"] += 1
        return httpx.Response(200, json=_run_payload())

    with pytest.raises(ValueError):
        _run(handler, "get_workflow_run", REPO, 1, expected_head_sha="short")
    assert called["n"] == 0


# --------------------------------------------------------------- HTTP errors
@pytest.mark.parametrize(
    "code, expected",
    [
        (400, GitHubResponseError),
        (401, GitHubAuthError),
        (403, GitHubForbiddenError),
        (404, GitHubNotFoundError),
        (429, GitHubRateLimitError),
        (500, GitHubServerError),
        (502, GitHubServerError),
        (302, GitHubResponseError),
    ],
)
def test_http_statuses_map_to_safe_errors(code, expected):
    def handler(request):
        return httpx.Response(code, json={"message": "SECRET-RESPONSE-BODY"})

    with pytest.raises(expected) as exc:
        _run(handler, "get_branch", REPO, "agent/x")
    assert exc.value.status_code == code
    assert TOKEN not in str(exc.value)
    assert "SECRET-RESPONSE-BODY" not in str(exc.value)


def test_rate_limit_headers_are_exposed_safely():
    def handler(request):
        return httpx.Response(
            403,
            headers={
                "x-ratelimit-remaining": "0",
                "retry-after": "30",
                "x-ratelimit-reset": "1700000000",
            },
            json={"message": "rate limited"},
        )

    with pytest.raises(GitHubRateLimitError) as exc:
        _run(handler, "get_branch", REPO, "agent/x")
    assert exc.value.retry_after == 30
    assert exc.value.rate_limit_reset == 1700000000
    assert TOKEN not in str(exc.value)


def test_transport_and_timeout_errors_do_not_leak_token():
    def timeout(request):
        raise httpx.ConnectTimeout("timeout with token " + TOKEN)

    def connection(request):
        raise httpx.ConnectError("connection with token " + TOKEN)

    for handler in (timeout, connection):
        with pytest.raises(GitHubTransportError) as exc:
            _run(handler, "get_branch", REPO, "agent/x")
        assert TOKEN not in str(exc.value)
        assert TOKEN not in repr(exc.value)


def test_malformed_json_and_unexpected_shapes_are_safe():
    def malformed(request):
        return httpx.Response(200, content=b"<html>proxy error</html>")

    def unexpected(request):
        return httpx.Response(200, json=[1, 2, 3])

    with pytest.raises(GitHubMalformedResponse):
        _run(malformed, "get_branch", REPO, "agent/x")
    with pytest.raises(GitHubMalformedResponse):
        _run(unexpected, "get_branch", REPO, "agent/x")


def test_oversized_response_is_rejected():
    def handler(request):
        return httpx.Response(200, content=json.dumps({"x": "y" * 100}).encode())

    with pytest.raises(GitHubResponseTooLarge):
        _run(handler, "get_branch", REPO, "agent/x", client_kwargs={"max_response_bytes": 10})


class _RawBody(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"not actually gzip"


def test_non_identity_content_encoding_is_rejected():
    def handler(request):
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=_RawBody(),
        )

    with pytest.raises(GitHubResponseError):
        _run(handler, "get_branch", REPO, "agent/x")


def test_pagination_limit_is_explicit():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json=[_branch("agent/x", A)])

    with pytest.raises(GitHubPaginationError):
        _run(
            handler,
            "list_agent_branches",
            REPO,
            client_kwargs={"per_page": 1, "max_pages": 2},
        )
    assert calls["n"] == 2


# --------------------------------------------------------------- validation
def test_allowlist_is_fail_closed_and_checked_before_http():
    called = {"n": 0}

    def handler(request):
        called["n"] += 1
        return httpx.Response(200, json=[])

    with pytest.raises(GitHubRepoNotAllowed):
        _run(handler, "list_agent_branches", "other/repo")
    assert called["n"] == 0


def test_invalid_repo_branch_and_sha_are_rejected_before_http():
    called = {"n": 0}

    def handler(request):
        called["n"] += 1
        return httpx.Response(200, json={})

    for args in [
        ("bad repo", "agent/x"),
        ("owner/..", "agent/x"),
        (REPO, "../agent/x"),
        (REPO, "agent/x?bad"),
    ]:
        with pytest.raises(ValueError):
            _run(handler, "get_branch", *args)
    assert called["n"] == 0


def test_client_validation_and_repr_never_include_token():
    with pytest.raises(ValueError):
        GitHubClient("short", allowed_repositories={REPO})
    with pytest.raises(ValueError):
        GitHubClient(TOKEN, allowed_repositories={REPO}, base_url="http://api.github.com")
    with pytest.raises(ValueError):
        GitHubClient(
            TOKEN,
            allowed_repositories={REPO},
            base_url="https://api.github.com/../evil",
        )
    with pytest.raises(ValueError):
        GitHubClient(TOKEN, allowed_repositories={REPO}, timeout=0)
    with pytest.raises(ValueError):
        GitHubClient(TOKEN, allowed_repositories={REPO}, max_pages=0)
    client = GitHubClient(
        TOKEN,
        allowed_repositories={REPO},
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])),
    )
    try:
        assert TOKEN not in repr(client)
        assert "api.github.com" in repr(client)
    finally:
        asyncio.run(client.aclose())


def test_branch_response_name_mismatch_is_malformed():
    def handler(request):
        return httpx.Response(200, json=_branch("agent/other", A))

    with pytest.raises(GitHubMalformedResponse):
        _run(handler, "get_branch", REPO, "agent/x")


def test_malformed_branch_and_actions_items_are_rejected():
    def bad_branch(request):
        return httpx.Response(200, json=[{"name": "agent/x", "commit": {"sha": "short"}}])

    def bad_runs(request):
        return httpx.Response(200, json={"not_runs": []})

    def bad_jobs(request):
        return httpx.Response(200, json={"not_jobs": []})

    with pytest.raises(GitHubMalformedResponse):
        _run(bad_branch, "list_agent_branches", REPO)
    with pytest.raises(GitHubMalformedResponse):
        _run(bad_runs, "get_workflow_runs_for_sha", REPO, B)
    with pytest.raises(GitHubMalformedResponse):
        _run(bad_jobs, "list_run_jobs", REPO, 1, B)
