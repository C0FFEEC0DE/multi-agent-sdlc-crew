"""Unit tests for lib.sh hook functions: effective_started_roles, infer_started_roles_from_transcript, session_agent_enforcement_reason.

Tests the fixes for:
- Generic Task tool types (general-purpose, workflow-subagent) not blocking agent enforcement
- @alias transcript inference patterns
- Edge cases: empty state, missing transcript, mixed roles, deduplication
"""

import json
import subprocess
import tempfile
from pathlib import Path


HOOKS_DIR = Path(__file__).resolve().parents[2] / "claudecfg" / "hooks"
LIB_SH = HOOKS_DIR / "lib.sh"
ALIASES_JSON = HOOKS_DIR.parent / "agents" / "aliases.json"


def _run_lib_function(
    function_name: str,
    *,
    state_json: dict | None = None,
    transcript_lines: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
    extra_setup: str = "",
) -> tuple[int, str, str]:
    """Run a lib.sh function in an isolated environment and return (exit_code, stdout, stderr)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home_dir = Path(tmpdir) / "home"
        state_dir = home_dir / ".claude" / "state"
        state_dir.mkdir(parents=True)
        session_id = "test-session"
        state_file = state_dir / f"{session_id}.json"

        if state_json is not None:
            state_file.write_text(json.dumps(state_json), encoding="utf-8")

        transcript_path = None
        if transcript_lines is not None:
            transcript_path = Path(tmpdir) / "transcript.jsonl"
            transcript_path.write_text(
                "\n".join(transcript_lines) + "\n", encoding="utf-8"
            )

        # Build the bash command that sources lib.sh, sets up state_file()
        # resolution, and calls the function
        env_setup = f'export HOME="{home_dir}"'
        if extra_env:
            for k, v in extra_env.items():
                env_setup += f'\nexport {k}="{v}"'

        # Override state_file() and resolve_transcript_path() to use our temp files
        transcript_echo = f'echo "{transcript_path}"' if transcript_path else 'echo ""'
        overrides = f"""
state_file() {{
    echo "{state_file}"
}}
resolve_transcript_path() {{
    {transcript_echo}
}}
"""

        cmd = f"""
set -euo pipefail
SCRIPT_DIR="{HOOKS_DIR}"
{env_setup}
source "{LIB_SH}"
{overrides}
{extra_setup}
{function_name}
"""
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout, result.stderr


class TestEffectiveStartedRoles:
    """Tests for effective_started_roles filtering of generic Task tool types."""

    def test_filters_general_purpose_from_explicit_roles(self):
        """general-purpose should not appear in effective started roles."""
        state = {
            "subagents_started": ["general-purpose", "e", "cr"],
        }
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert "general-purpose" not in roles
        assert "e" in roles
        assert "cr" in roles

    def test_filters_workflow_subagent_from_explicit_roles(self):
        """workflow-subagent should not appear in effective started roles."""
        state = {
            "subagents_started": ["workflow-subagent", "a"],
        }
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert "workflow-subagent" not in roles
        assert "a" in roles

    def test_empty_when_only_generic_types(self):
        """When all roles are generic types, effective roles should be empty."""
        state = {
            "subagents_started": ["general-purpose", "workflow-subagent"],
        }
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert roles == []

    def test_preserves_real_roles(self):
        """Real agent roles should be preserved."""
        state = {
            "subagents_started": ["e", "a", "cr", "t", "bug", "dbg", "doc", "m"],
        }
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert set(roles) == {"a", "bug", "cr", "dbg", "doc", "e", "m", "t"}

    def test_deduplicates_across_explicit_and_transcript(self):
        """Same role in both state and transcript should appear only once."""
        state = {
            "subagents_started": ["cr"],
        }
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Code Reviewer(review)\\n  Done"}]}}',
        ]
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert roles.count("cr") == 1


class TestInferStartedRolesFromTranscript:
    """Tests for infer_started_roles_from_transcript @alias pattern detection."""

    def test_detects_alias_nerd_as_explorer(self):
        """@nerd should infer the e (explorer) role."""
        state = {"subagents_started": []}
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@nerd no-op verify · 2 tool uses"}]}}',
        ]
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert "e" in roles

    def test_detects_alias_toxic_senior_as_code_reviewer(self):
        """@toxic-senior should infer the cr (code-reviewer) role."""
        state = {"subagents_started": []}
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@toxic-senior no-op confirm · 0 tool uses"}]}}',
        ]
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert "cr" in roles

    def test_detects_alias_paranoid_as_tester(self):
        """@paranoid should infer the t (tester) role."""
        state = {"subagents_started": []}
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@paranoid no-op confirm · 0 tool uses"}]}}',
        ]
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert "t" in roles

    def test_detects_short_alias_cr(self):
        """@cr should infer the cr role."""
        state = {"subagents_started": []}
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@cr no-op confirm · 0 tool uses"}]}}',
        ]
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert "cr" in roles

    def test_detects_short_alias_e(self):
        """@e should infer the e role."""
        state = {"subagents_started": []}
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@e no-op verify · 1 tool use"}]}}',
        ]
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert "e" in roles

    def test_no_false_positive_on_email(self):
        """@email and @example should not trigger role detection."""
        state = {"subagents_started": []}
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Sent email to @example.com and checked @email-settings"}]}}',
        ]
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert "e" not in roles
        assert "cr" not in roles
        assert roles == []

    def test_detects_multiple_aliases(self):
        """Multiple @alias mentions should all be detected."""
        state = {"subagents_started": []}
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@nerd verified"}]}}',
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@toxic-senior confirmed"}]}}',
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@paranoid tested"}]}}',
        ]
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert "e" in roles
        assert "cr" in roles
        assert "t" in roles

    def test_deduplicates_alias_and_explicit_pattern(self):
        """Same role detected by both @alias and explicit pattern should appear once."""
        state = {"subagents_started": []}
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@cr confirmed"}]}}',
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Code Reviewer(review)\\n  Done"}]}}',
        ]
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert roles.count("cr") == 1

    def test_empty_transcript_returns_empty(self):
        """Empty transcript should not produce any roles."""
        state = {"subagents_started": []}
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
            transcript_lines=[],
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert roles == []

    def test_missing_transcript_returns_empty(self):
        """Missing transcript file should not produce any roles."""
        state = {"subagents_started": []}
        exit_code, stdout, _ = _run_lib_function(
            "effective_started_roles",
            state_json=state,
            transcript_lines=None,
        )
        assert exit_code == 0
        roles = [r for r in stdout.strip().split("\n") if r]
        assert roles == []


class TestSessionAgentEnforcementReason:
    """Tests for session_agent_enforcement_reason with generic types and @alias inference."""

    def test_blocks_when_only_generic_types_and_no_transcript(self):
        """Feature with only generic types in state and no transcript should block."""
        state = {
            "task_type": "feature",
            "subagents_started": ["general-purpose", "workflow-subagent"],
            "required_subagents": ["t", "cr"],
            "required_subagent_any_of": [["e", "a"]],
            "tests_ok": True,
            "detected_test_command": "pytest",
        }
        exit_code, stdout, stderr = _run_lib_function(
            "session_agent_enforcement_reason",
            state_json=state,
        )
        assert exit_code == 0
        assert "Missing required roles" in stdout
        assert "general-purpose" not in stdout
        assert "workflow-subagent" not in stdout

    def test_allows_when_generic_types_with_transcript_inference(self):
        """Feature with generic types but @cr and @e in transcript should pass."""
        state = {
            "task_type": "feature",
            "subagents_started": ["general-purpose"],
            "required_subagents": ["t", "cr"],
            "required_subagent_any_of": [["e", "a"]],
            "tests_ok": True,
            "detected_test_command": "pytest",
        }
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@cr confirmed"}]}}',
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@nerd verified"}]}}',
        ]
        exit_code, stdout, stderr = _run_lib_function(
            "session_agent_enforcement_reason",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 1
        assert stdout == ""

    def test_allows_when_real_roles_present_with_generic_types(self):
        """Feature with real roles and generic types should pass."""
        state = {
            "task_type": "feature",
            "subagents_started": ["general-purpose", "e", "cr"],
            "required_subagents": ["t", "cr"],
            "required_subagent_any_of": [["e", "a"]],
            "tests_ok": True,
            "detected_test_command": "pytest",
        }
        exit_code, stdout, stderr = _run_lib_function(
            "session_agent_enforcement_reason",
            state_json=state,
        )
        assert exit_code == 1
        assert stdout == ""

    def test_blocks_when_required_roles_missing_even_with_generic_types(self):
        """Feature with generic types and only @e started should still block for missing @cr."""
        state = {
            "task_type": "feature",
            "subagents_started": ["general-purpose", "e"],
            "required_subagents": ["t", "cr"],
            "required_subagent_any_of": [["e", "a"]],
            "tests_ok": True,
            "detected_test_command": "pytest",
        }
        exit_code, stdout, stderr = _run_lib_function(
            "session_agent_enforcement_reason",
            state_json=state,
        )
        assert exit_code == 0
        assert "Missing required roles" in stdout
        assert "@cr" in stdout

    def test_message_format_excludes_generic_types(self):
        """The 'Used so far' message should not include generic types."""
        state = {
            "task_type": "feature",
            "subagents_started": ["general-purpose", "workflow-subagent"],
            "required_subagents": ["t", "cr"],
            "required_subagent_any_of": [["e", "a"]],
            "tests_ok": True,
            "detected_test_command": "pytest",
        }
        exit_code, stdout, stderr = _run_lib_function(
            "session_agent_enforcement_reason",
            state_json=state,
        )
        assert exit_code == 0
        assert "Used so far" in stdout
        used_section = stdout.split("Used so far:")[1].strip().rstrip(".")
        assert "general-purpose" not in used_section
        assert "workflow-subagent" not in used_section

    def test_review_task_blocks_without_cr(self):
        """Review task without @cr should block."""
        state = {
            "task_type": "review",
            "subagents_started": [],
            "required_subagents": ["cr"],
            "required_subagent_any_of": [],
            "tests_ok": False,
        }
        exit_code, stdout, stderr = _run_lib_function(
            "session_agent_enforcement_reason",
            state_json=state,
        )
        assert exit_code == 0
        assert "Missing required roles" in stdout
        assert "@cr" in stdout

    def test_review_task_allows_with_alias_cr_in_transcript(self):
        """Review task with @cr in transcript should pass."""
        state = {
            "task_type": "review",
            "subagents_started": [],
            "required_subagents": ["cr"],
            "required_subagent_any_of": [],
            "tests_ok": False,
        }
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@cr no-op confirm · 0 tool uses"}]}}',
        ]
        exit_code, stdout, stderr = _run_lib_function(
            "session_agent_enforcement_reason",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 1
        assert stdout == ""

    def test_bugfix_task_allows_explorer_in_one_of_group(self):
        """Bugfix task with @e in transcript should satisfy one-of group."""
        state = {
            "task_type": "bugfix",
            "subagents_started": ["cr"],
            "required_subagents": ["t", "cr"],
            "required_subagent_any_of": [["bug", "e", "dbg"]],
            "tests_ok": True,
            "detected_test_command": "pytest",
        }
        transcript = [
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"@nerd traced the bug"}]}}',
        ]
        exit_code, stdout, stderr = _run_lib_function(
            "session_agent_enforcement_reason",
            state_json=state,
            transcript_lines=transcript,
        )
        assert exit_code == 1
        assert stdout == ""
