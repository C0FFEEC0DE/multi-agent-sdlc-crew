#!/usr/bin/env python3
"""Tests for transcript pattern validation logic in bench_runner_claude_code.py."""

import json
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
    infer_used_agent_aliases_from_transcript,
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

    def test_generic_types_return_none(self):
        """Generic Task tool types should not be valid agent aliases."""
        assert canonicalize_subagent_label("general-purpose") is None
        assert canonicalize_subagent_label("workflow-subagent") is None


class TestInferUsedAgentAliasesFromTranscript:
    """Tests for infer_used_agent_aliases_from_transcript @alias pattern detection."""

    def _make_payload(self, text: str, tmp_path: pathlib.Path) -> dict:
        transcript = tmp_path / "transcript.jsonl"
        lines = text.strip().splitlines()
        with transcript.open("w", encoding="utf-8") as f:
            for line in lines:
                entry = {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": line}],
                    },
                }
                f.write(json.dumps(entry) + "\n")
        return {"transcript_path": str(transcript)}

    def test_detects_alias_cr(self, tmp_path):
        """@cr in transcript should infer cr role."""
        payload = self._make_payload("@cr no-op confirm · 0 tool uses", tmp_path)
        result = infer_used_agent_aliases_from_transcript(payload)
        assert "cr" in result

    def test_detects_alias_e(self, tmp_path):
        """@e in transcript should infer e role."""
        payload = self._make_payload("@e no-op verify · 1 tool use", tmp_path)
        result = infer_used_agent_aliases_from_transcript(payload)
        assert "e" in result

    def test_detects_alias_nerd_as_explorer(self, tmp_path):
        """@nerd in transcript should infer e role via alias canonicalization."""
        payload = self._make_payload("@nerd traced the issue", tmp_path)
        result = infer_used_agent_aliases_from_transcript(payload)
        assert "e" in result

    def test_detects_alias_toxic_senior_as_cr(self, tmp_path):
        """@toxic-senior in transcript should infer cr role."""
        payload = self._make_payload("@toxic-senior confirmed the fix", tmp_path)
        result = infer_used_agent_aliases_from_transcript(payload)
        assert "cr" in result

    def test_detects_alias_paranoid_as_tester(self, tmp_path):
        """@paranoid in transcript should infer t role."""
        payload = self._make_payload("@paranoid ran the tests", tmp_path)
        result = infer_used_agent_aliases_from_transcript(payload)
        assert "t" in result

    def test_no_false_positive_on_email(self, tmp_path):
        """@email and @example should not trigger role detection."""
        payload = self._make_payload(
            "Sent email to @example.com and checked @email-settings", tmp_path
        )
        result = infer_used_agent_aliases_from_transcript(payload)
        assert "e" not in result
        assert "cr" not in result

    def test_detects_multiple_aliases(self, tmp_path):
        """Multiple @alias mentions should all be detected."""
        payload = self._make_payload(
            "@nerd verified\n@toxic-senior confirmed\n@paranoid tested", tmp_path
        )
        result = infer_used_agent_aliases_from_transcript(payload)
        assert "e" in result
        assert "cr" in result
        assert "t" in result

    def test_empty_payload_returns_empty(self):
        """Empty payload should return empty list."""
        result = infer_used_agent_aliases_from_transcript(None)
        assert result == []

    def test_no_messages_returns_empty(self):
        """Payload with no messages should return empty list."""
        result = infer_used_agent_aliases_from_transcript({})
        assert result == []

    def test_generic_types_not_detected(self, tmp_path):
        """general-purpose and workflow-subagent should not appear as aliases."""
        payload = self._make_payload(
            "Launched general-purpose agent and workflow-subagent", tmp_path
        )
        result = infer_used_agent_aliases_from_transcript(payload)
        assert "general-purpose" not in result
        assert "workflow-subagent" not in result

    def test_deduplicates_alias_and_skill_pattern(self, tmp_path):
        """Same role detected by both @alias and slash-skill should appear once."""
        payload = self._make_payload("@cr confirmed\nSkill(/review)", tmp_path)
        result = infer_used_agent_aliases_from_transcript(payload)
        assert result.count("cr") == 1

    def test_deduplicates_alias_and_agent_name_pattern(self, tmp_path):
        """Same role detected by both @alias and agent name should appear once."""
        payload = self._make_payload("@e explored\nexplorer(code)", tmp_path)
        result = infer_used_agent_aliases_from_transcript(payload)
        assert result.count("e") == 1
