"""Validate benchmark workflow configuration."""

import re
from pathlib import Path

import pytest

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
