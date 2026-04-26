#!/usr/bin/env python3
"""Tests for transcript pattern validation logic in bench_runner_claude_code.py."""

import os
import sys
import pathlib

# Set required environment variables before importing bench_runner_claude_code
os.environ["BENCH_REPO_ROOT"] = "/tmp/test-repo"
os.environ["BENCH_TASK_FILE"] = "/tmp/test-task.json"
os.environ["BENCH_WORKDIR"] = "/tmp/test-workdir"
os.environ["BENCH_OUTPUT_DIR"] = "/tmp/test-output"
os.environ["OLLAMA_MODEL"] = "test-model"

# Add scripts directory to path for imports
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / "scripts"))

from bench_runner_claude_code import (
    canonicalize_subagent_label,
)


class TestCanonicalizeSubagentLabel:
    """Tests for canonicalize_subagent_label function."""

    def test_known_aliases(self):
        """Known aliases should canonicalize correctly."""
        assert canonicalize_subagent_label("code-reviewer") == "cr"
        assert canonicalize_subagent_label("cr") == "cr"
        assert canonicalize_subagent_label("explorer") == "e"
        assert canonicalize_subagent_label("e") == "e"
        assert canonicalize_subagent_label("architect") == "a"
        assert canonicalize_subagent_label("a") == "a"
        assert canonicalize_subagent_label("tester") == "t"
        assert canonicalize_subagent_label("t") == "t"
        assert canonicalize_subagent_label("bugbuster") == "bug"
        assert canonicalize_subagent_label("bug") == "bug"
        assert canonicalize_subagent_label("debugger") == "dbg"
        assert canonicalize_subagent_label("dbg") == "dbg"
        assert canonicalize_subagent_label("manager") == "m"
        assert canonicalize_subagent_label("m") == "m"
        assert canonicalize_subagent_label("docwriter") == "doc"
        assert canonicalize_subagent_label("doc") == "doc"

    def test_case_insensitive(self):
        """Should handle case insensitively."""
        assert canonicalize_subagent_label("Code-Reviewer") == "cr"
        assert canonicalize_subagent_label("CODE_REVIEWER") == "cr"
        assert canonicalize_subagent_label("EXPLORER") == "e"

    def test_underscore_to_hyphen(self):
        """Should convert underscores to hyphens."""
        assert canonicalize_subagent_label("code_reviewer") == "cr"
        assert canonicalize_subagent_label("bugbuster") == "bug"

    def test_unknown_label(self):
        """Unknown labels should return None."""
        assert canonicalize_subagent_label("unknown-agent") is None
        assert canonicalize_subagent_label("") is None
        assert canonicalize_subagent_label("   ") is None
