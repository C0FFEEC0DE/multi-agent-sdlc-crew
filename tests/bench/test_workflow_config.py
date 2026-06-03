"""Validate benchmark workflow configuration."""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def test_subagent_smoke_max_turns_is_at_least_eight():
    """Smoke suite must allow enough turns for multi-step subagent conversations."""
    path = WORKFLOWS_DIR / "behavior-benchmark-subagents-smoke.yml"
    assert path.exists()
    content = path.read_text()
    # Find the default value in the shell script: max_turns="${INPUT_MAX_TURNS:-N}"
    match = re.search(r'max_turns="\$\{INPUT_MAX_TURNS:-(\d+)\}"', content)
    assert match is not None, "max_turns default not found"
    default = int(match.group(1))
    assert default >= 8, f"default max_turns is {default}, expected >= 8"


def test_security_scan_checkout_fetches_full_history():
    """TruffleHog needs full history to diff BASE and HEAD commits."""
    path = WORKFLOWS_DIR / "security-scan.yml"
    assert path.exists()
    with open(path) as f:
        workflow = yaml.safe_load(f)

    checkout = workflow["jobs"]["security-scan"]["steps"][0]
    assert checkout["uses"] == "actions/checkout@v5"
    assert checkout["with"]["fetch-depth"] == 0, "fetch-depth must be 0 so TruffleHog can diff commits"


def test_security_scan_trufflehog_base_is_not_literal_main():
    """TruffleHog base should point to PR base sha, not literal 'main' ref."""
    path = WORKFLOWS_DIR / "security-scan.yml"
    assert path.exists()
    content = path.read_text()
    assert "base: main" not in content, "literal 'base: main' breaks on PRs where HEAD == BASE"
    assert "github.event.pull_request.base.sha" in content, "should use PR base sha for TruffleHog base"


def test_python_tests_workflow_runs_full_pytest_suite():
    """CI must not silently skip repository pytest modules."""
    path = WORKFLOWS_DIR / "python-tests.yml"
    assert path.exists()
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["python-tests"]["steps"]
    run_commands = [str(step.get("run", "")) for step in steps]

    assert any("pip install" in command and "pyyaml" in command for command in run_commands)
    assert any("python -m pytest -v" in command for command in run_commands)
    assert not any(
        "python -m pytest tests/bench/test_bench_runner.py" in command
        for command in run_commands
    ), "python-tests workflow should run the full pytest suite, not a hand-picked subset"
