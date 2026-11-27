"""Read-only GitHub API primitives for the automated review pipeline (R3).

The client only exposes GET operations. It never sends a token in a URL, never
follows redirects, never executes repository code, and never returns raw error
bodies. Every compare/Actions result is tied to an explicit 40-character SHA.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import quote, urlsplit

import httpx

GITHUB_API_DEFAULT = "https://api.github.com"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_PAGES = 10
DEFAULT_PER_PAGE = 100
MAX_TIMEOUT_SECONDS = 60.0
MAX_RESPONSE_BYTES_LIMIT = 16 * 1024 * 1024
MAX_PAGES_LIMIT = 100

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_AGENT_PREFIX = "agent/"


class GitHubError(RuntimeError):
    """Base safe error. Messages never contain the token or response body."""

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


class GitHubAuthError(GitHubError):
    pass


class GitHubForbiddenError(GitHubError):
    pass


class GitHubNotFoundError(GitHubError):
    pass


class GitHubRateLimitError(GitHubError):
    pass


class GitHubServerError(GitHubError):
    pass


class GitHubTransportError(GitHubError):
    pass


class GitHubResponseError(GitHubError):
    pass


class GitHubRedirectError(GitHubResponseError):
    """A redirect was observed; D-05 requires rejection, never following it."""


class GitHubRepositoryIdentityMismatch(GitHubResponseError):
    """The response canonical full name differs from the requested repository."""


class GitHubMalformedResponse(GitHubResponseError):
    pass


class GitHubResponseTooLarge(GitHubResponseError):
    pass


class GitHubPaginationError(GitHubResponseError):
    pass


class GitHubShaMismatchError(GitHubResponseError):
    pass


class GitHubRepoNotAllowed(GitHubError):
    pass


@dataclass(frozen=True)
class BranchInfo:
    name: str
    sha: str
    protected: bool = False


@dataclass(frozen=True)
class BranchVerification:
    repository: str
    branch: str
    expected_sha: str
    observed_sha: str | None
    status: str  # unchanged | moved | missing | blocked
    error_class: str | None = None


@dataclass(frozen=True)
class RepositoryIdentity:
    repository_id: int
    full_name: str
    owner_id: int
    owner_login: str
    private: bool
    fork: bool
    archived: bool
    default_branch: str | None


@dataclass(frozen=True)
class PullRequestIdentity:
    pr_number: int
    repository_id: int
    repository_full_name: str
    base_repository_id: int
    base_repository_full_name: str
    base_ref: str
    base_sha: str
    head_repository_id: int
    head_repository_full_name: str
    head_ref: str
    head_sha: str
    state: str
    merged: bool
    draft: bool


@dataclass(frozen=True)
class ChangedFile:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None = None


@dataclass(frozen=True)
class CompareResult:
    repository: str
    base_sha: str
    head_sha: str
    merge_base_sha: str | None
    status: str  # verified | base_sha_mismatch | head_sha_mismatch | merge_base_mismatch
    ahead_by: int
    behind_by: int
    files: tuple[ChangedFile, ...]
    commits: tuple[str, ...]
    observed_base_sha: str | None
    observed_head_sha: str | None


@dataclass(frozen=True)
class WorkflowRun:
    run_id: int
    name: str
    head_sha: str
    head_branch: str | None
    status: str
    conclusion: str | None
    event: str | None
    run_attempt: int
    created_at: str | None
    updated_at: str | None
    path: str | None = None


@dataclass(frozen=True)
class WorkflowRunsEvidence:
    repository: str
    head_sha: str
    runs: tuple[WorkflowRun, ...]
    status: str  # verified | sha_mismatch
    observed_head_shas: tuple[str, ...]
    ci_state: str  # success | pending | failure | cancelled | skipped | mixed | missing | stale

    @property
    def is_success(self) -> bool:
        """True only for a verified, non-empty, all-completed/all-success run set."""
        return self.status == "verified" and self.ci_state == "success" and bool(self.runs)


@dataclass(frozen=True)
class WorkflowJob:
    job_id: int
    run_id: int
    name: str
    head_sha: str
    status: str
    conclusion: str | None
    started_at: str | None
    completed_at: str | None


@dataclass(frozen=True)
class WorkflowJobsEvidence:
    repository: str
    run_id: int
    head_sha: str
    jobs: tuple[WorkflowJob, ...]
    status: str  # verified | sha_mismatch
    observed_head_shas: tuple[str, ...]


class GitHubClient:
    """Small read-only GitHub API client with injectable HTTPX transport."""

    def __init__(
        self,
        token: str,
        *,
        allowed_repositories: Iterable[str] = (),
        base_url: str = GITHUB_API_DEFAULT,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_pages: int = DEFAULT_MAX_PAGES,
        per_page: int = DEFAULT_PER_PAGE,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = _validate_token(token)
        self._allowed = _normalize_allowed_repositories(allowed_repositories)
        self._base = _validate_base_url(base_url)
        self._timeout = _validate_timeout(timeout)
        self._max_response_bytes = _validate_response_limit(max_response_bytes)
        self._max_pages = _validate_pages(max_pages)
        self._per_page = _validate_per_page(per_page)
        self._client = httpx.AsyncClient(
            base_url=self._base,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "OpenHandBot-review/0.1",
                "Accept-Encoding": "identity",
            },
            timeout=httpx.Timeout(self._timeout),
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        )

    def __repr__(self) -> str:
        return (
            f"GitHubClient(base_url={self._base!r}, "
            f"allowed_repositories={tuple(sorted(self._allowed))!r})"
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # --------------------------------------------------------------- validation
    def _repo(self, repository: str) -> str:
        if not _valid_repo(repository):
            raise ValueError("repository لازم يكون owner/repo صالح")
        normalized = repository.lower()
        if normalized not in self._allowed:
            raise GitHubRepoNotAllowed("المستودع غير موجود في allowlist المراجعة")
        return normalized

    @staticmethod
    def _branch(branch: str) -> str:
        if not _valid_branch(branch):
            raise ValueError("branch غير صالح")
        return branch

    @staticmethod
    def _sha(value: str, name: str = "sha") -> str:
        if not isinstance(value, str) or not _SHA_RE.match(value):
            raise ValueError(f"{name} لازم يكون 40 حرفًا hex صغيرًا")
        return value

    @staticmethod
    def _run_id(value: int) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError("run_id لازم يكون رقمًا موجبًا")
        return value

    @staticmethod
    def _pr_number(value: int) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError("pr_number لازم يكون رقمًا موجبًا")
        return value

    # ------------------------------------------------------------------- HTTP
    async def _request_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        try:
            async with self._client.stream("GET", path, params=params) as resp:
                if 300 <= resp.status_code < 400:
                    raise GitHubRedirectError(
                        "رد إعادة توجيه غير متوقّع من GitHub", status_code=resp.status_code
                    )
                if resp.status_code == 401:
                    raise GitHubAuthError("GitHub رفض المصادقة (401)", status_code=401)
                if resp.status_code == 403:
                    if _is_rate_limited(resp):
                        raise _rate_error(resp, 403)
                    raise GitHubForbiddenError("GitHub رفض الصلاحية (403)", status_code=403)
                if resp.status_code == 404:
                    raise GitHubNotFoundError("مورد GitHub غير موجود (404)", status_code=404)
                if resp.status_code == 429:
                    raise _rate_error(resp, 429)
                if resp.status_code >= 500:
                    raise GitHubServerError(
                        "خطأ مؤقت في GitHub API", status_code=resp.status_code
                    )
                if resp.status_code >= 400:
                    raise GitHubResponseError(
                        "رد GitHub غير متوقّع", status_code=resp.status_code
                    )
                encoding = _content_encoding(resp)
                if encoding is not None and encoding != "identity":
                    raise GitHubResponseError("ترميز محتوى غير متوقّع من GitHub")
                declared = _content_length(resp)
                if declared is not None and declared > self._max_response_bytes:
                    raise GitHubResponseTooLarge("رد GitHub أكبر من الحد الآمن")
                body = await _read_capped(resp, self._max_response_bytes)
        except GitHubError:
            raise
        except httpx.HTTPError as exc:
            raise GitHubTransportError(
                f"تعذّر الاتصال بـ GitHub ({type(exc).__name__})"
            ) from exc
        try:
            return json.loads(body)
        except (TypeError, ValueError) as exc:
            raise GitHubMalformedResponse("رد GitHub ليس JSON صالحًا") from exc

    async def _paginate(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        parser,
    ) -> list[Any]:
        items: list[Any] = []
        for page in range(1, self._max_pages + 1):
            page_params = dict(params or {})
            page_params.update({"per_page": self._per_page, "page": page})
            data = await self._request_json(path, params=page_params)
            page_items = parser(data)
            items.extend(page_items)
            if len(page_items) < self._per_page:
                return items
        raise GitHubPaginationError("تجاوز حد صفحات GitHub المسموح")

    # ---------------------------------------------------------------- branches
    async def list_agent_branches(self, repository: str) -> tuple[BranchInfo, ...]:
        repo = self._repo(repository)
        raw = await self._paginate(
            f"/repos/{quote(repo, safe='/')}/branches",
            parser=_as_list,
        )
        branches: list[BranchInfo] = []
        for item in raw:
            info = _parse_branch(item)
            if info.name.startswith(_AGENT_PREFIX):
                branches.append(info)
        return tuple(branches)

    async def get_branch(self, repository: str, branch: str) -> BranchInfo:
        repo = self._repo(repository)
        safe_branch = self._branch(branch)
        data = await self._request_json(
            f"/repos/{quote(repo, safe='/')}/branches/{quote(safe_branch, safe='/')}"
        )
        info = _parse_branch(data)
        if info.name != safe_branch:
            raise GitHubMalformedResponse("اسم الفرع في الرد لا يطابق الطلب")
        return info

    async def verify_branch_sha(
        self, repository: str, branch: str, expected_sha: str
    ) -> BranchVerification:
        repo = self._repo(repository)
        safe_branch = self._branch(branch)
        expected = self._sha(expected_sha, "expected_sha")
        try:
            info = await self.get_branch(repo, safe_branch)
        except GitHubNotFoundError:
            return BranchVerification(repo, safe_branch, expected, None, "missing")
        except GitHubError as exc:
            return BranchVerification(
                repo, safe_branch, expected, None, "blocked", type(exc).__name__
            )
        status = "unchanged" if info.sha == expected else "moved"
        return BranchVerification(repo, safe_branch, expected, info.sha, status)

    # ------------------------------------------------------------ repositories
    async def get_repository(self, repository: str) -> RepositoryIdentity:
        """Return immutable repository identity metadata for an allowlisted repo.

        The response canonical full name must still match the requested repository.
        This is a D-05 rename/transfer check at the HTTP boundary, in addition to the
        resolver's later identity and SHA checks.
        """
        repo = self._repo(repository)
        data = await self._request_json(f"/repos/{quote(repo, safe='/')}")
        identity = _parse_repository(data)
        if identity.full_name.casefold() != repo.casefold():
            raise GitHubRepositoryIdentityMismatch(
                "repository full_name لا يطابق المستودع المطلوب"
            )
        return identity

    # ---------------------------------------------------------- pull requests
    async def get_pull_request(self, repository: str, pr_number: int) -> PullRequestIdentity:
        """Return a PR's base/head repository identity and exact head SHA."""
        repo = self._repo(repository)
        number = self._pr_number(pr_number)
        data = await self._request_json(
            f"/repos/{quote(repo, safe='/')}/pulls/{number}"
        )
        return _parse_pull_request(data, requested_number=number)

    # ----------------------------------------------------------------- compare
    async def compare(self, repository: str, base_sha: str, head_sha: str) -> CompareResult:
        repo = self._repo(repository)
        base = self._sha(base_sha, "base_sha")
        head = self._sha(head_sha, "head_sha")
        data = await self._request_json(
            f"/repos/{quote(repo, safe='/')}/compare/{base}...{head}"
        )
        if not isinstance(data, dict):
            raise GitHubMalformedResponse("رد compare غير متوقّع")
        base_commit = data.get("base_commit")
        merge_commit = data.get("merge_base_commit")
        commits_raw = data.get("commits")
        files_raw = data.get("files", [])
        if not isinstance(base_commit, dict) or not isinstance(commits_raw, list):
            raise GitHubMalformedResponse("رد compare ناقص")
        if not isinstance(files_raw, list):
            raise GitHubMalformedResponse("files في compare غير متوقّعة")
        observed_base = _optional_sha(base_commit.get("sha"), "base_commit.sha")
        merge_base = (
            _optional_sha(merge_commit.get("sha"), "merge_base_commit.sha")
            if isinstance(merge_commit, dict)
            else None
        )
        commits = tuple(_commit_sha(item) for item in commits_raw)
        if base == head:
            observed_head = base
        else:
            observed_head = commits[-1] if commits else None

        status = "verified"
        if observed_base != base:
            status = "base_sha_mismatch"
        elif observed_head != head:
            status = "head_sha_mismatch"
        elif merge_base != base:
            status = "merge_base_mismatch"

        files = (
            tuple(_parse_changed_file(item) for item in files_raw)
            if status == "verified"
            else ()
        )
        # Never expose commits/files for a result that did not match the requested SHAs.
        safe_commits = commits if status == "verified" else ()
        ahead_by = _non_negative_int(data.get("ahead_by", 0), "ahead_by")
        behind_by = _non_negative_int(data.get("behind_by", 0), "behind_by")
        return CompareResult(
            repository=repo,
            base_sha=base,
            head_sha=head,
            merge_base_sha=merge_base,
            status=status,
            ahead_by=ahead_by,
            behind_by=behind_by,
            files=files,
            commits=safe_commits,
            observed_base_sha=observed_base,
            observed_head_sha=observed_head,
        )

    # ---------------------------------------------------------------- actions
    async def get_workflow_runs_for_sha(
        self, repository: str, head_sha: str
    ) -> WorkflowRunsEvidence:
        repo = self._repo(repository)
        sha = self._sha(head_sha, "head_sha")
        raw = await self._paginate(
            f"/repos/{quote(repo, safe='/')}/actions/runs",
            params={"head_sha": sha},
            parser=lambda data: _named_list(data, "workflow_runs"),
        )
        runs: list[WorkflowRun] = []
        observed: list[str] = []
        mismatch = False
        for item in raw:
            run = _parse_workflow_run(item)
            if run.head_sha not in observed:
                observed.append(run.head_sha)
            if run.head_sha != sha:
                mismatch = True
            runs.append(run)
        if mismatch:
            return WorkflowRunsEvidence(
                repository=repo,
                head_sha=sha,
                runs=(),
                status="sha_mismatch",
                observed_head_shas=tuple(observed),
                ci_state="stale",
            )
        return WorkflowRunsEvidence(
            repository=repo,
            head_sha=sha,
            runs=tuple(runs),
            status="verified",
            observed_head_shas=tuple(observed),
            ci_state=_ci_state(runs),
        )

    async def get_workflow_run(
        self, repository: str, run_id: int, *, expected_head_sha: str
    ) -> WorkflowRun:
        repo = self._repo(repository)
        rid = self._run_id(run_id)
        expected = self._sha(expected_head_sha, "expected_head_sha")
        data = await self._request_json(
            f"/repos/{quote(repo, safe='/')}/actions/runs/{rid}"
        )
        run = _parse_workflow_run(data)
        if run.run_id != rid:
            raise GitHubMalformedResponse("run id في الرد لا يطابق الطلب")
        if run.head_sha != expected:
            raise GitHubShaMismatchError(
                "run head_sha لا يطابق الـSHA المطلوب", status_code=None
            )
        return run

    async def list_run_jobs(
        self, repository: str, run_id: int, head_sha: str
    ) -> WorkflowJobsEvidence:
        repo = self._repo(repository)
        rid = self._run_id(run_id)
        sha = self._sha(head_sha, "head_sha")
        raw = await self._paginate(
            f"/repos/{quote(repo, safe='/')}/actions/runs/{rid}/jobs",
            parser=lambda data: _named_list(data, "jobs"),
        )
        jobs: list[WorkflowJob] = []
        observed: list[str] = []
        mismatch = False
        for item in raw:
            job = _parse_job(item)
            if job.head_sha not in observed:
                observed.append(job.head_sha)
            if job.head_sha != sha or job.run_id != rid:
                mismatch = True
            jobs.append(job)
        if mismatch:
            return WorkflowJobsEvidence(
                repository=repo,
                run_id=rid,
                head_sha=sha,
                jobs=(),
                status="sha_mismatch",
                observed_head_shas=tuple(observed),
            )
        return WorkflowJobsEvidence(
            repository=repo,
            run_id=rid,
            head_sha=sha,
            jobs=tuple(jobs),
            status="verified",
            observed_head_shas=tuple(observed),
        )


# ------------------------------------------------------------------ helpers
def _validate_token(token: str) -> str:
    if (
        not isinstance(token, str)
        or len(token) < 8
        or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in token)
    ):
        raise ValueError("GitHub token غير صالح")
    return token


def _normalize_allowed_repositories(values: Iterable[str]) -> frozenset[str]:
    allowed: set[str] = set()
    for value in values:
        if not _valid_repo(value):
            raise ValueError("allowed_repositories يحتوي owner/repo غير صالح")
        normalized = value.lower()
        if normalized in allowed:
            raise ValueError("allowed_repositories يحتوي مستودع مكرر")
        allowed.add(normalized)
    return frozenset(allowed)


def _valid_repo(value: str) -> bool:
    if not isinstance(value, str) or not _REPO_RE.fullmatch(value):
        return False
    owner, repo = value.split("/")
    return owner not in {".", ".."} and repo not in {".", ".."}


def _validate_base_url(base_url: str) -> str:
    if not isinstance(base_url, str):
        raise ValueError("GitHub base_url غير صالح")
    parts = urlsplit(base_url)
    if (
        parts.scheme != "https"
        or not parts.netloc
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or ".." in parts.path.split("/")
    ):
        raise ValueError("GitHub base_url لازم يكون https بلا credentials/query/fragment/traversal")
    return base_url.rstrip("/")


def _validate_timeout(value: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("timeout غير صالح")
    value = float(value)
    if not 0 < value <= MAX_TIMEOUT_SECONDS:
        raise ValueError("timeout خارج الحدود")
    return value


def _validate_response_limit(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_RESPONSE_BYTES_LIMIT:
        raise ValueError("max_response_bytes خارج الحدود")
    return value


def _validate_pages(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_PAGES_LIMIT:
        raise ValueError("max_pages خارج الحدود")
    return value


def _validate_per_page(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 100:
        raise ValueError("per_page خارج الحدود")
    return value


def _valid_branch(value: str) -> bool:
    if not isinstance(value, str) or not value or len(value) > 255:
        return False
    if value.startswith(("/", ".")) or value.endswith(("/", ".")):
        return False
    if ".." in value or "@{" in value or "\\" in value:
        return False
    if any(ord(ch) < 32 or ch.isspace() for ch in value):
        return False
    return not any(ch in "~^:?*[" for ch in value)


def _optional_sha(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA_RE.match(value):
        raise GitHubMalformedResponse(f"{name} غير صالح")
    return value


def _commit_sha(value: Any) -> str:
    if not isinstance(value, dict):
        raise GitHubMalformedResponse("commit في compare غير متوقّع")
    sha = value.get("sha")
    if not isinstance(sha, str) or not _SHA_RE.match(sha):
        raise GitHubMalformedResponse("commit sha غير صالح")
    return sha


def _parse_branch(value: Any) -> BranchInfo:
    if not isinstance(value, dict):
        raise GitHubMalformedResponse("branch غير متوقّع")
    name = value.get("name")
    commit = value.get("commit")
    if not _valid_branch(name) or not isinstance(commit, dict):
        raise GitHubMalformedResponse("branch name/commit غير صالح")
    sha = commit.get("sha")
    if not isinstance(sha, str) or not _SHA_RE.match(sha):
        raise GitHubMalformedResponse("branch sha غير صالح")
    protected = value.get("protected", False)
    if not isinstance(protected, bool):
        raise GitHubMalformedResponse("branch protected غير صالح")
    return BranchInfo(name=name, sha=sha, protected=protected)


def _positive_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise GitHubMalformedResponse(f"{name} غير صالح")
    return value


def _bool_field(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise GitHubMalformedResponse(f"{name} غير صالح")
    return value


def _parse_repository(value: Any) -> RepositoryIdentity:
    if not isinstance(value, dict):
        raise GitHubMalformedResponse("repository غير متوقّع")
    repository_id = _positive_int(value.get("id"), "repository.id")
    full_name = value.get("full_name")
    if not _valid_repo(full_name):
        raise GitHubMalformedResponse("repository.full_name غير صالح")
    owner = value.get("owner")
    if not isinstance(owner, dict):
        raise GitHubMalformedResponse("repository.owner غير متوقّع")
    owner_id = _positive_int(owner.get("id"), "repository.owner.id")
    owner_login = owner.get("login")
    if (
        not isinstance(owner_login, str)
        or not owner_login
        or len(owner_login) > 100
        or any(ch.isspace() or ord(ch) < 32 for ch in owner_login)
    ):
        raise GitHubMalformedResponse("repository.owner.login غير صالح")
    default_branch = value.get("default_branch")
    if default_branch is not None and not _valid_branch(default_branch):
        raise GitHubMalformedResponse("repository.default_branch غير صالح")
    return RepositoryIdentity(
        repository_id=repository_id,
        full_name=full_name,
        owner_id=owner_id,
        owner_login=owner_login,
        private=_bool_field(value.get("private"), "repository.private"),
        fork=_bool_field(value.get("fork"), "repository.fork"),
        archived=_bool_field(value.get("archived"), "repository.archived"),
        default_branch=default_branch,
    )


def _parse_pull_request_ref(value: Any, name: str) -> tuple[str, str, int, str]:
    if not isinstance(value, dict):
        raise GitHubMalformedResponse(f"pull request {name} غير متوقّع")
    ref = value.get("ref")
    if not _valid_branch(ref):
        raise GitHubMalformedResponse(f"pull request {name}.ref غير صالح")
    sha = value.get("sha")
    if not isinstance(sha, str) or not _SHA_RE.match(sha):
        raise GitHubMalformedResponse(f"pull request {name}.sha غير صالح")
    repo = value.get("repo")
    if not isinstance(repo, dict):
        raise GitHubMalformedResponse(f"pull request {name}.repo غير متوقّع")
    repository_id = _positive_int(repo.get("id"), f"pull request {name}.repo.id")
    full_name = repo.get("full_name")
    if not _valid_repo(full_name):
        raise GitHubMalformedResponse(f"pull request {name}.repo.full_name غير صالح")
    return ref, sha, repository_id, full_name


def _parse_pull_request(value: Any, *, requested_number: int) -> PullRequestIdentity:
    if not isinstance(value, dict):
        raise GitHubMalformedResponse("pull request غير متوقّع")
    number = _positive_int(value.get("number"), "pull request.number")
    if number != requested_number:
        raise GitHubMalformedResponse("pull request.number لا يطابق الطلب")
    state = value.get("state")
    if state not in ("open", "closed"):
        raise GitHubMalformedResponse("pull request.state غير صالح")
    merged = _bool_field(value.get("merged"), "pull request.merged")
    draft = value.get("draft", False)
    if not isinstance(draft, bool):
        raise GitHubMalformedResponse("pull request.draft غير صالح")
    base_ref, base_sha, base_repo_id, base_repo_full_name = _parse_pull_request_ref(
        value.get("base"), "base"
    )
    head_ref, head_sha, head_repo_id, head_repo_full_name = _parse_pull_request_ref(
        value.get("head"), "head"
    )
    return PullRequestIdentity(
        pr_number=number,
        repository_id=base_repo_id,
        repository_full_name=base_repo_full_name,
        base_repository_id=base_repo_id,
        base_repository_full_name=base_repo_full_name,
        base_ref=base_ref,
        base_sha=base_sha,
        head_repository_id=head_repo_id,
        head_repository_full_name=head_repo_full_name,
        head_ref=head_ref,
        head_sha=head_sha,
        state=state,
        merged=merged,
        draft=draft,
    )


def _parse_changed_file(value: Any) -> ChangedFile:
    if not isinstance(value, dict):
        raise GitHubMalformedResponse("changed file غير متوقّع")
    filename = value.get("filename")
    status = value.get("status")
    if not isinstance(filename, str) or not filename or not isinstance(status, str):
        raise GitHubMalformedResponse("changed file filename/status غير صالح")
    additions = _non_negative_int(value.get("additions", 0), "additions")
    deletions = _non_negative_int(value.get("deletions", 0), "deletions")
    changes = _non_negative_int(value.get("changes", 0), "changes")
    patch = value.get("patch")
    if patch is not None and not isinstance(patch, str):
        raise GitHubMalformedResponse("patch غير صالح")
    return ChangedFile(filename, status, additions, deletions, changes, patch)


def _parse_workflow_run(value: Any) -> WorkflowRun:
    if not isinstance(value, dict):
        raise GitHubMalformedResponse("workflow run غير متوقّع")
    run_id = value.get("id")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise GitHubMalformedResponse("workflow run id غير صالح")
    head_sha = value.get("head_sha")
    if not isinstance(head_sha, str) or not _SHA_RE.match(head_sha):
        raise GitHubMalformedResponse("workflow run head_sha غير صالح")
    name = value.get("name")
    status = value.get("status")
    if not isinstance(name, str) or not isinstance(status, str):
        raise GitHubMalformedResponse("workflow run name/status غير صالح")
    conclusion = value.get("conclusion")
    if conclusion is not None and not isinstance(conclusion, str):
        raise GitHubMalformedResponse("workflow run conclusion غير صالح")
    run_attempt = value.get("run_attempt", 1)
    if not isinstance(run_attempt, int) or isinstance(run_attempt, bool) or run_attempt < 1:
        raise GitHubMalformedResponse("workflow run attempt غير صالح")
    head_branch = value.get("head_branch")
    event = value.get("event")
    path = value.get("path")
    for item, label in ((head_branch, "head_branch"), (event, "event"), (path, "path")):
        if item is not None and not isinstance(item, str):
            raise GitHubMalformedResponse(f"workflow run {label} غير صالح")
    return WorkflowRun(
        run_id=run_id,
        name=name,
        head_sha=head_sha,
        head_branch=head_branch,
        status=status,
        conclusion=conclusion,
        event=event,
        run_attempt=run_attempt,
        created_at=_optional_str(value.get("created_at")),
        updated_at=_optional_str(value.get("updated_at")),
        path=path,
    )


def _parse_job(value: Any) -> WorkflowJob:
    if not isinstance(value, dict):
        raise GitHubMalformedResponse("job غير متوقّع")
    job_id = value.get("id")
    run_id = value.get("run_id")
    if not isinstance(job_id, int) or isinstance(job_id, bool) or job_id <= 0:
        raise GitHubMalformedResponse("job id غير صالح")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise GitHubMalformedResponse("job run_id غير صالح")
    head_sha = value.get("head_sha")
    if not isinstance(head_sha, str) or not _SHA_RE.match(head_sha):
        raise GitHubMalformedResponse("job head_sha غير صالح")
    name = value.get("name")
    status = value.get("status")
    if not isinstance(name, str) or not isinstance(status, str):
        raise GitHubMalformedResponse("job name/status غير صالح")
    conclusion = value.get("conclusion")
    if conclusion is not None and not isinstance(conclusion, str):
        raise GitHubMalformedResponse("job conclusion غير صالح")
    return WorkflowJob(
        job_id=job_id,
        run_id=run_id,
        name=name,
        head_sha=head_sha,
        status=status,
        conclusion=conclusion,
        started_at=_optional_str(value.get("started_at")),
        completed_at=_optional_str(value.get("completed_at")),
    )


def _ci_state(runs: list[WorkflowRun]) -> str:
    if not runs:
        return "missing"
    if any(run.status.lower() != "completed" for run in runs):
        return "pending"
    conclusions = [(run.conclusion or "").lower() for run in runs]
    if any(c in {"failure", "timed_out", "action_required", "startup_failure"} for c in conclusions):
        return "failure"
    if any(c == "cancelled" for c in conclusions):
        return "cancelled"
    if all(c == "success" for c in conclusions):
        return "success"
    if any(c in {"skipped", "neutral"} for c in conclusions):
        return "skipped"
    return "mixed"


def _as_list(data: Any) -> list[Any]:
    if not isinstance(data, list):
        raise GitHubMalformedResponse("رد GitHub ليس قائمة")
    return data


def _named_list(data: Any, field: str) -> list[Any]:
    if not isinstance(data, dict) or not isinstance(data.get(field), list):
        raise GitHubMalformedResponse(f"رد GitHub لا يحتوي {field} كقائمة")
    return data[field]


def _non_negative_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise GitHubMalformedResponse(f"{name} غير صالح")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise GitHubMalformedResponse("قيمة نصية غير صالحة في رد GitHub")
    return value


def _is_rate_limited(resp: httpx.Response) -> bool:
    return (
        (resp.headers.get("x-ratelimit-remaining") or "").strip() == "0"
        or bool((resp.headers.get("retry-after") or "").strip())
    )


def _rate_error(resp: httpx.Response, status: int) -> GitHubRateLimitError:
    retry_after = _int_header(resp, "retry-after")
    reset = _int_header(resp, "x-ratelimit-reset")
    return GitHubRateLimitError(
        "GitHub API rate limit",
        status_code=status,
        retry_after=retry_after,
        rate_limit_reset=reset,
    )


def _int_header(resp: httpx.Response, name: str) -> int | None:
    raw = (resp.headers.get(name) or "").strip()
    if not raw.isdigit():
        return None
    return int(raw)


def _content_length(resp: httpx.Response) -> int | None:
    raw = (resp.headers.get("content-length") or "").strip()
    if not raw.isdigit():
        return None
    return int(raw)


def _content_encoding(resp: httpx.Response) -> str | None:
    raw = (resp.headers.get("content-encoding") or "").strip().lower()
    return raw or None


async def _read_capped(resp: httpx.Response, limit: int) -> bytes:
    # MockTransport may pre-load the body, so aiter_raw() is already consumed.
    if getattr(resp, "is_stream_consumed", False):
        body = resp.content
        if len(body) > limit:
            raise GitHubResponseTooLarge("رد GitHub أكبر من الحد الآمن")
        return body
    buf = bytearray()
    async for chunk in resp.aiter_raw():
        if len(buf) + len(chunk) > limit:
            raise GitHubResponseTooLarge("رد GitHub أكبر من الحد الآمن")
        buf += chunk
    return bytes(buf)
