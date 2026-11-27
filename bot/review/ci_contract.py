"""Documented CI job contracts for the repository's existing workflows (R7 F-01).

The contract is deliberately small and derived from the checked-in workflow files:

- ``.github/workflows/ci.yml``: two matrix jobs named ``Tests & lint`` and one
  ``Frontend tests (Node)`` job.
- ``.github/workflows/verify.yml``: one ``Validate requested SHA`` job, one
  ``Python 3.11 checks`` job, one ``Python 3.13 checks`` job, and one
  ``Frontend tests (Node)`` job.

A run whose workflow path/name is not in this contract has no established
expected-job set, so completeness must remain false (fail closed). This module
does not make network calls and does not invent workflow/job names.
"""
from __future__ import annotations

from dataclasses import dataclass

from bot.review.github import WorkflowJobsEvidence, WorkflowRun, WorkflowRunsEvidence


@dataclass(frozen=True)
class JobExpectation:
    name: str
    count: int = 1
    prefix: bool = False


_CI_EXPECTATIONS = (
    JobExpectation("Tests & lint", count=2, prefix=True),
    JobExpectation("Frontend tests (Node)"),
)
_VERIFY_EXPECTATIONS = (
    JobExpectation("Validate requested SHA"),
    JobExpectation("Python 3.11 checks"),
    JobExpectation("Python 3.13 checks"),
    JobExpectation("Frontend tests (Node)"),
)

_BY_PATH = {
    ".github/workflows/ci.yml": _CI_EXPECTATIONS,
    ".github/workflows/verify.yml": _VERIFY_EXPECTATIONS,
}
_BY_NAME = {
    "CI": _CI_EXPECTATIONS,
    "Verify agent branch": _VERIFY_EXPECTATIONS,
}


def expectations_for_run(run: WorkflowRun) -> tuple[JobExpectation, ...] | None:
    """Return the documented expectations for a workflow run, or None if unknown."""
    path = getattr(run, "path", None)
    if isinstance(path, str) and path:
        return _BY_PATH.get(path)
    return _BY_NAME.get(run.name)


def jobs_complete(
    runs: WorkflowRunsEvidence | None,
    jobs: tuple[WorkflowJobsEvidence, ...],
) -> bool:
    """Return True only for a fully retrieved, fully successful documented job set."""
    if runs is None or runs.status != "verified" or not runs.runs:
        return False
    if not isinstance(jobs, tuple) or not jobs:
        return False
    groups = {group.run_id: group for group in jobs}
    if len(groups) != len(jobs):
        return False
    expected_run_ids = {run.run_id for run in runs.runs}
    if len(expected_run_ids) != len(runs.runs):
        return False
    if set(groups) != expected_run_ids:
        return False

    for run in runs.runs:
        expectations = expectations_for_run(run)
        if expectations is None:
            return False
        group = groups[run.run_id]
        if (
            group.status != "verified"
            or group.head_sha != runs.head_sha
            or group.repository.casefold() != runs.repository.casefold()
        ):
            return False
        items = tuple(group.jobs)
        if not items:
            return False
        job_ids = [item.job_id for item in items]
        if len(set(job_ids)) != len(job_ids):
            return False
        if any(
            item.run_id != run.run_id
            or item.head_sha != runs.head_sha
            or item.status.lower() != "completed"
            or (item.conclusion or "").lower() != "success"
            for item in items
        ):
            return False

        used: set[int] = set()
        for expectation in expectations:
            matched = [
                index
                for index, item in enumerate(items)
                if item.name == expectation.name
                or (
                    expectation.prefix
                    and item.name.startswith(expectation.name + " ")
                )
            ]
            if len(matched) != expectation.count:
                return False
            used.update(matched)
        if used != set(range(len(items))):
            return False

    return True
