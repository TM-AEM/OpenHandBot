"""Security assertions for the agent-branch verification workflow.

The repository does not ship a YAML parser. These tests therefore use a small
structural extractor for the GitHub Actions subset used by ``verify.yml`` and
``ci.yml``. They are intentionally stricter than substring checks: they parse
top-level blocks, job blocks, steps and ``run:`` scripts before asserting.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

try:  # PyYAML is installed transitively by bandit/pip-audit in requirements-dev.txt.
    import yaml
except ImportError:  # pragma: no cover - only when dev requirements are absent
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = ROOT / ".github/workflows/verify.yml"
CI_PATH = ROOT / ".github/workflows/ci.yml"
VERIFY = VERIFY_PATH.read_text(encoding="utf-8")
CI = CI_PATH.read_text(encoding="utf-8")

REQUIRED_COMMANDS = (
    "python -m pyflakes bot/ automation/ tools/ main.py tests/",
    "python -m pip_audit -r requirements-dev.txt",
    "python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613",
    "python -m pytest -q",
    "npm ci",
    "node --test tests/frontend/*.test.js",
    "npm run build",
    "npm run lint",
)

FORBIDDEN_RUN_COMMANDS = (
    "git push",
    "npm publish",
    "gh release",
    "docker push",
    "deploy",
    "autopush",
    "start.sh",
    "pip install openhands",
)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _top_block(text: str, key: str) -> str:
    """Return the lines of a top-level YAML block (``key:`` at column 0)."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(f"{key}:")), None)
    if start is None:
        return ""
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if line and not line.startswith((" ", "\t", "#")):
            break
        block.append(line)
    return "\n".join(block)


def _job_block(text: str, name: str) -> str:
    """Return one job block from ``jobs:`` (job keys are indented two spaces)."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line == f"  {name}:"), None)
    if start is None:
        return ""
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if re.match(r"^  [A-Za-z0-9_-]+:", line):
            break
        block.append(line)
    return "\n".join(block)


def _steps(job: str) -> list[str]:
    if "    steps:\n" not in job:
        return []
    body = job.split("    steps:\n", 1)[1]
    lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("    ") and not line.startswith("      ") and line.strip():
            break
        lines.append(line)
    parts = re.split(r"(?m)^      - ", "\n".join(lines))
    return [part for part in parts[1:]]


def _run_scripts(job: str) -> str:
    scripts: list[str] = []
    for step in _steps(job):
        lines = step.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("        run: |"):
                block: list[str] = []
                for following in lines[index + 1 :]:
                    if following.strip() and _indent(following) < 10:
                        break
                    block.append(following)
                scripts.append("\n".join(block))
            elif line.startswith("        run: "):
                scripts.append(line[len("        run: ") :])
    return "\n".join(scripts)


def _all_run_scripts(text: str) -> str:
    return "\n".join(_run_scripts(_job_block(text, job)) for job in ("validate", "python", "frontend"))


def _python_versions(text: str) -> list[str]:
    match = re.search(r"python-version:\s*\[(.*?)\]", text)
    if not match:
        return []
    return re.findall(r'"(\d+\.\d+)"', match.group(1))


def _ci_errors(ci_text: str) -> list[str]:
    errors: list[str] = []
    if "name: CI" not in ci_text:
        errors.append("ci.yml name changed")
    if ci_text.count("branches: [main]") != 2:
        errors.append("ci.yml main-only push/PR triggers changed")
    if "pull_request:" not in ci_text:
        errors.append("ci.yml pull_request trigger missing")
    if "agent/**" in ci_text:
        errors.append("ci.yml now contains agent/** (verify workflow leaked into ci.yml)")
    if "head_sha" in ci_text:
        errors.append("ci.yml now contains head_sha (verify workflow leaked into ci.yml)")
    return errors


def validate_workflow(text: str, ci_text: str = CI) -> list[str]:
    """Return human-readable security errors for a candidate verify workflow."""
    errors: list[str] = []

    on_block = _top_block(text, "on")
    if "push:" not in on_block:
        errors.append("push trigger missing")
    if "agent/**" not in on_block:
        errors.append("push trigger does not cover agent/**")
    if "workflow_dispatch:" not in on_block:
        errors.append("workflow_dispatch missing")
    if "head_sha:" not in on_block:
        errors.append("workflow_dispatch head_sha input missing")
    if "required: true" not in on_block:
        errors.append("head_sha input is not required")
    if "type: string" not in on_block:
        errors.append("head_sha input is not a string")

    permissions = _top_block(text, "permissions")
    if "contents: read" not in permissions:
        errors.append("permissions must include contents: read")
    if "write" in permissions.lower():
        errors.append("permissions must not include write")

    if "continue-on-error" in text:
        errors.append("continue-on-error is forbidden (failures must propagate)")
    if "|| true" in text or "set +e" in text:
        errors.append("silent failure suppression is forbidden")

    for job in ("validate", "python", "frontend"):
        if not _job_block(text, job):
            errors.append(f"job missing: {job}")

    validate_run = _run_scripts(_job_block(text, "validate"))
    if "EVENT_NAME" not in validate_run or "INPUT_HEAD_SHA" not in validate_run:
        errors.append("workflow_dispatch input must be passed through env, not interpolated")
    if "workflow_dispatch" not in validate_run:
        errors.append("manual dispatch branch is not explicit")
    if "[0-9a-f]{40}" not in validate_run:
        errors.append("requested SHA format validation missing")
    if "inputs.head_sha" in validate_run:
        errors.append("untrusted inputs.head_sha interpolated directly into run")

    if text.count("ref: ${{ needs.validate.outputs.sha }}") < 2:
        errors.append("checkout is not pinned to the validated SHA in both jobs")
    if "git rev-parse HEAD" not in text:
        errors.append("checked-out SHA is not read back")
    if "git cat-file -e" not in text:
        errors.append("requested commit existence is not verified")
    if "${actual}" not in text or "${REQUESTED_SHA}" not in text:
        errors.append("checked-out SHA is not compared to the requested SHA")

    for command in REQUIRED_COMMANDS:
        if command not in text:
            errors.append(f"required CI command missing: {command}")

    versions = _python_versions(text)
    if "3.11" not in versions:
        errors.append("Python 3.11 coverage missing")
    if "3.13" not in versions:
        errors.append("Python 3.13 coverage missing")
    if not re.search(r'node-version:\s*"24"', text):
        errors.append("Node 24 coverage missing")

    runs = _all_run_scripts(text).lower()
    for command in FORBIDDEN_RUN_COMMANDS:
        if command in runs:
            errors.append(f"forbidden run command present: {command}")

    errors.extend(_ci_errors(ci_text))
    return errors


def test_validator_accepts_the_real_workflow():
    assert validate_workflow(VERIFY) == []


def test_push_trigger_covers_agent_branches():
    on_block = _top_block(VERIFY, "on")
    assert "push:" in on_block
    assert "agent/**" in on_block


def test_manual_dispatch_accepts_explicit_head_sha():
    on_block = _top_block(VERIFY, "on")
    assert "workflow_dispatch:" in on_block
    assert "head_sha:" in on_block
    assert "required: true" in on_block
    assert "type: string" in on_block


def test_permissions_are_read_only():
    permissions = _top_block(VERIFY, "permissions")
    assert "contents: read" in permissions
    assert "write" not in permissions.lower()


def test_sha_is_validated_and_checked_out():
    validate_run = _run_scripts(_job_block(VERIFY, "validate"))
    assert "INPUT_HEAD_SHA" in validate_run
    assert "EVENT_NAME" in validate_run
    assert "workflow_dispatch" in validate_run
    assert "[0-9a-f]{40}" in validate_run
    assert "inputs.head_sha" not in validate_run
    assert VERIFY.count("ref: ${{ needs.validate.outputs.sha }}") == 2


def test_checkout_sha_is_verified():
    assert "git rev-parse HEAD" in VERIFY
    assert "git cat-file -e" in VERIFY
    assert "${actual}" in VERIFY
    assert "${REQUESTED_SHA}" in VERIFY


def test_required_ci_checks_are_present():
    for command in REQUIRED_COMMANDS:
        assert command in VERIFY, command


def test_python_versions_are_covered():
    versions = _python_versions(VERIFY)
    assert "3.11" in versions
    assert "3.13" in versions


def test_node_tests_are_present():
    assert 'node-version: "24"' in VERIFY
    assert "npm ci" in VERIFY
    assert "node --test tests/frontend/*.test.js" in VERIFY


def test_failures_are_not_silently_ignored():
    assert "continue-on-error" not in VERIFY
    assert "|| true" not in VERIFY
    assert "set +e" not in VERIFY
    assert "set -euo pipefail" in _all_run_scripts(VERIFY)


def test_ci_workflow_is_not_replaced():
    assert CI_PATH.exists()
    assert _ci_errors(CI) == []
    assert VERIFY_PATH.read_text(encoding="utf-8") != CI


@pytest.mark.parametrize(
    "mutated, expected_fragment",
    [
        (
            VERIFY.replace("contents: read", "contents: write", 1),
            "permissions must not include write",
        ),
        (
            VERIFY.replace("  workflow_dispatch:\n", "  # disabled:\n", 1),
            "workflow_dispatch missing",
        ),
        (
            VERIFY.replace(
                'if [[ ! "${sha}" =~ ^[0-9a-f]{40}$ ]]; then',
                "if false; then",
                1,
            ),
            "requested SHA format validation missing",
        ),
        (
            VERIFY.replace('["3.11", "3.13"]', '["3.11"]', 1),
            "Python 3.13 coverage missing",
        ),
        (
            VERIFY.replace(
                "      - name: SAST (bandit)\n        run: python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613\n",
                "",
                1,
            ),
            "required CI command missing: python -m bandit",
        ),
        (
            VERIFY.replace(
                'sha="${INPUT_HEAD_SHA}"',
                'sha="${{ inputs.head_sha }}"',
                1,
            ),
            "untrusted inputs.head_sha interpolated directly into run",
        ),
        (
            VERIFY.replace(
                "      - name: Frontend lint\n        run: npm run lint\n",
                "      - name: Frontend lint\n        continue-on-error: true\n        run: npm run lint\n",
                1,
            ),
            "continue-on-error is forbidden",
        ),
        (
            VERIFY.replace('actual="$(git rev-parse HEAD)"', 'actual="true"'),
            "checked-out SHA is not read back",
        ),
        (
            VERIFY.replace("run: npm run lint", "run: npm run lint && git push", 1),
            "forbidden run command present: git push",
        ),
    ],
)
def test_negative_controls_reject_insecure_workflows(mutated, expected_fragment):
    errors = validate_workflow(mutated)
    assert any(expected_fragment in error for error in errors), errors


def test_workflow_files_parse_as_yaml():
    if yaml is None:
        pytest.skip("PyYAML is not installed")
    for path in (VERIFY_PATH, CI_PATH):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), path
        assert isinstance(data.get("jobs"), dict), path
    verify_data = yaml.safe_load(VERIFY)
    on_key = True if True in verify_data else "on"
    assert isinstance(verify_data[on_key], dict)
    assert "push" in verify_data[on_key]
    assert "workflow_dispatch" in verify_data[on_key]


def test_negative_control_rejects_replaced_ci_workflow():
    mutated_ci = CI + "\n# agent/** head_sha\n"
    errors = validate_workflow(VERIFY, ci_text=mutated_ci)
    assert any("ci.yml now contains" in error for error in errors), errors
