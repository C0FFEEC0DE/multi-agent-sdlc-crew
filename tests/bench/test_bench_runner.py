import importlib.util
import json
import subprocess
from pathlib import Path


def load_runner_module(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[2]
    task_file = tmp_path / "task.json"
    task_file.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("BENCH_REPO_ROOT", str(repo_root))
    monkeypatch.setenv("BENCH_TASK_FILE", str(task_file))
    monkeypatch.setenv("BENCH_WORKDIR", str(tmp_path / "workdir"))
    monkeypatch.setenv("BENCH_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")

    module_path = repo_root / "scripts" / "bench_runner_claude_code.py"
    spec = importlib.util.spec_from_file_location("bench_runner_claude_code", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_transcript(path, events):
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def test_detect_verification_target_prefers_npm_for_package_json(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    fixture = tmp_path / "node-app"
    fixture.mkdir()
    (fixture / "package.json").write_text("{}", encoding="utf-8")

    command, label = runner.detect_verification_target(fixture)

    assert command == ["npm", "test", "--silent"]
    assert label == "npm test"


def test_detect_verification_target_finds_python_tests(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    fixture = tmp_path / "python-app"
    tests_dir = fixture / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    command, label = runner.detect_verification_target(fixture)

    assert command == [runner.sys.executable, "-m", "pytest", "-q"]
    assert label == "pytest -q"


def test_detect_verification_target_returns_none_when_no_supported_target_exists(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    fixture = tmp_path / "empty"
    fixture.mkdir()

    command, label = runner.detect_verification_target(fixture)

    assert command is None
    assert label is None


def test_run_verification_uses_detected_command_and_label(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    fixture = tmp_path / "node-app"
    fixture.mkdir()
    (fixture / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(runner, "WORKDIR", fixture)

    calls = []

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return Completed()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    tests_run, tests_passed, output, label = runner.run_verification()

    assert tests_run is True
    assert tests_passed is True
    assert output == "ok"
    assert label == "npm test"
    assert calls[0][0][0] == ["npm", "test", "--silent"]
    assert calls[0][1]["cwd"] == fixture


def test_run_verification_reports_missing_target(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    fixture = tmp_path / "empty"
    fixture.mkdir()
    monkeypatch.setattr(runner, "WORKDIR", fixture)

    tests_run, tests_passed, output, label = runner.run_verification()

    assert tests_run is False
    assert tests_passed is False
    assert output == "No supported automated verification target was found in the fixture."
    assert label == "verification"


def test_verification_status_and_footer_use_dynamic_label(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)

    line = runner.verification_status_line(True, True, True, "npm test")
    footer = runner.synthesize_footer(True, True, True, "npm test", True, True)

    assert line == "Verification status: passed - npm test completed successfully."
    assert footer[0] == line
    assert footer[1] == "Review outcome: done - explicit review summary is present."
    assert footer[2] == "Remaining risks: the model omitted explicit remaining-risk and review summaries."


def test_build_prompt_mentions_fixture_specific_verification_command(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    task = {
        "id": "feature-node-app-multiply",
        "category": "feature",
        "review_required": True,
        "docs_required": True,
        "verification_required": True,
        "prompt": "Do the thing.",
        "success_criteria": ["It works."],
        "must_not": [],
    }

    prompt = runner.build_prompt(task, "npm test")

    assert "If verification is required, run the relevant tests locally (npm test)." in prompt
    assert "Verification status: passed - npm test completed successfully." in prompt


def test_build_prompt_includes_required_agent_and_transcript_contract(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    task = {
        "id": "subagent-bugbuster-zero-division-lite",
        "category": "bugfix",
        "review_required": True,
        "docs_required": True,
        "verification_required": True,
        "prompt": "Start by using @bug.",
        "success_criteria": ["Fix the bug."],
        "must_not": [],
        "required_used_agents": ["bug"],
        "required_transcript_patterns": [
            r"Findings:|Investigation",
            r"Changed files:|No files changed:",
            r"Verification status:",
        ],
    }

    prompt = runner.build_prompt(task, "pytest -q")

    assert "Start with an actual handoff to: @bug" in prompt
    assert "Findings: or Investigation:" in prompt
    assert "Changed files: or No files changed:" in prompt


def test_build_prompt_requires_real_ordered_handoffs_for_manager_workflows(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    task = {
        "id": "manager-explorer-reviewer-code-map",
        "category": "review",
        "review_required": True,
        "docs_required": True,
        "verification_required": False,
        "prompt": "Start with @m and send @e before @cr.",
        "success_criteria": ["Use @m, @e, and @cr in order."],
        "must_not": [],
        "required_used_agents": ["m", "e", "cr"],
        "required_transcript_patterns": [],
    }

    prompt = runner.build_prompt(task, "verification")

    assert "Every required role must be launched as a real handoff in this order: @m -> @e -> @cr" in prompt
    assert "For this manager-led run, launch @m first. Then the manager must launch the remaining required roles in order: @e -> @cr." in prompt
    assert "Keep the run terse and execution-first." in prompt
    assert "Preserve the existing fixture layout." in prompt
    assert "If @cr is the final required role, reserve time for it" in prompt
    assert "Keep the @cr review terse and findings-only" in prompt


def test_required_transcript_patterns_ignore_user_only_mentions(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    transcript_path = tmp_path / "session.jsonl"
    write_transcript(
        transcript_path,
        [
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Start with @e"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Task: Docs - small note"}]}},
        ],
    )

    scanned, misses = runner.required_transcript_pattern_misses(
        {"required_transcript_patterns": [r"@e"]},
        {"transcript_path": str(transcript_path)},
    )

    assert scanned is True
    assert misses == [r"@e"]


def test_required_transcript_patterns_scan_final_result_text_when_transcript_misses_headings(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    transcript_path = tmp_path / "session.jsonl"
    write_transcript(
        transcript_path,
        [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Updated README.md with the requested note."}],
                },
            }
        ],
    )

    scanned, misses = runner.required_transcript_pattern_misses(
        {"required_transcript_patterns": [r"Task:\s*Docs", r"Coverage:"]},
        {"transcript_path": str(transcript_path)},
        result_text="Task: Docs - quickstart\nCoverage: README.md quickstart guidance",
    )

    assert scanned is True
    assert misses == []


def test_required_transcript_patterns_match_assistant_entries(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    transcript_path = tmp_path / "session.jsonl"
    write_transcript(
        transcript_path,
        [
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Task: Explore - repo map\nLocations: calculator.py, test_calculator.py"}]}},
            {"type": "result", "result": "Outcome: mapped the fixture.\nChanged files: README.md\nVerification status: not run - docs-only mapping.\nRemaining risks: none"},
        ],
    )

    scanned, misses = runner.required_transcript_pattern_misses(
        {"required_transcript_patterns": [r"Task:\s*Explore", r"Locations:"]},
        {"transcript_path": str(transcript_path)},
    )

    assert scanned is True
    assert misses == []


def test_required_transcript_patterns_accept_markdown_role_heading_for_combo_workflows(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    transcript_path = tmp_path / "session.jsonl"
    write_transcript(
        transcript_path,
        [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "## Code Review — subtract helper\nReview outcome: done - reviewed the change.",
                        }
                    ],
                },
            }
        ],
    )

    scanned, misses = runner.required_transcript_pattern_misses(
        {
            "required_transcript_patterns": [
                r"Task:\s*(Explore|Design|Code Review|Testing)|(^|\n)##\s*(Explore|Design|Code Review|Testing)\b"
            ]
        },
        {"transcript_path": str(transcript_path)},
    )

    assert scanned is True
    assert misses == []


def test_required_transcript_patterns_still_reject_plain_summary_without_role_heading(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    transcript_path = tmp_path / "session.jsonl"
    write_transcript(
        transcript_path,
        [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "Feature workflow complete. Review outcome: done - all required roles were used.",
                        }
                    ],
                },
            }
        ],
    )

    scanned, misses = runner.required_transcript_pattern_misses(
        {
            "required_transcript_patterns": [
                r"Task:\s*(Explore|Design|Code Review|Testing)|(^|\n)##\s*(Explore|Design|Code Review|Testing)\b"
            ]
        },
        {"transcript_path": str(transcript_path)},
    )

    assert scanned is True
    assert misses == [r"Task:\s*(Explore|Design|Code Review|Testing)|(^|\n)##\s*(Explore|Design|Code Review|Testing)\b"]


def test_required_transcript_patterns_report_unavailable_transcript(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)

    scanned, misses = runner.required_transcript_pattern_misses(
        {"required_transcript_patterns": [r"Findings:"]},
        {"transcript_path": str(tmp_path / "missing.jsonl")},
    )

    assert scanned is False
    assert misses == ["<assistant transcript unavailable>"]


def test_effective_required_transcript_misses_ignores_unavailable_transcript_after_recovery(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)

    misses = runner.effective_required_transcript_misses(
        ["<assistant transcript unavailable>"],
        recovered_nonzero_exit=True,
    )

    assert misses == []


def test_effective_required_transcript_misses_keeps_real_pattern_misses_after_recovery(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)

    misses = runner.effective_required_transcript_misses(
        [r"Findings:", r"Outcome:"],
        recovered_nonzero_exit=True,
    )

    assert misses == [r"Findings:", r"Outcome:"]


def test_synthesize_required_transcript_lines_covers_docwriter_footer_shape(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)

    lines = runner.synthesize_required_transcript_lines(
        {
            "id": "subagent-docwriter-quickstart-lite",
            "agent_alias": "doc",
            "required_transcript_patterns": [
                r"Task:\s*Docs",
                r"Coverage:",
                r"Outcome:",
                r"Changed files:|No files changed:",
                r"Verification status:",
                r"Remaining risks:|Next step:",
            ],
        },
        changed_files=["README.md"],
        verification_required=False,
        tests_run=False,
        tests_passed=False,
        verification_label="verification",
        review_required=False,
        review_present=False,
    )

    assert "Task: Docs — benchmark handoff" in lines
    assert "Coverage: updated README.md." in lines
    assert "Changed files: README.md" in lines
    assert any(line.startswith("Outcome:") for line in lines)


def test_synthesize_required_transcript_lines_supports_standalone_next_step(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)

    lines = runner.synthesize_required_transcript_lines(
        {
            "id": "subagent-explorer-feature-handoff-lite",
            "agent_alias": "e",
            "required_transcript_patterns": [
                r"Task:\s*Explore",
                "Locations:",
                "Outcome:",
                "Changed files:|No files changed:",
                "Verification status:",
                "Next step:",
            ],
        },
        changed_files=["README.md", "calculator.py", "test_calculator.py"],
        verification_required=True,
        tests_run=True,
        tests_passed=True,
        verification_label="pytest -q",
        review_required=True,
        review_present=True,
    )

    assert "Next step: carry the verified handoff forward to the next required specialist." in lines


def test_extract_used_agent_aliases_counts_action_phrases_in_final_result_text(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)

    aliases = runner.extract_used_agent_aliases(
        "",
        None,
        result_text=(
            "Verification status: passed - pytest -q completed with 3 tests passing.\n"
            "Review outcome: done - @cr reviewed and approved the changes.\n"
            "Remaining risks: none.\n"
        ),
    )

    assert "cr" in aliases


def test_forbidden_transcript_patterns_catch_footer_repair_meta_chatter(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    transcript_path = tmp_path / "session.jsonl"
    write_transcript(
        transcript_path,
        [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "I see the issue - my markdown bold syntax is breaking the prefix match.",
                        }
                    ],
                },
            }
        ],
    )

    scanned, hits = runner.forbidden_transcript_pattern_hits(
        {"forbidden_transcript_patterns": [r"I see the issue", r"prefix match"]},
        {"transcript_path": str(transcript_path)},
    )

    assert scanned is True
    assert len(hits) == 2


def test_forbidden_transcript_patterns_ignore_user_only_mentions(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    transcript_path = tmp_path / "session.jsonl"
    write_transcript(
        transcript_path,
        [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Do not say: I see the issue or prefix match."}],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Task: Explore - repo map\nLocations: calculator.py"}],
                },
            },
        ],
    )

    scanned, hits = runner.forbidden_transcript_pattern_hits(
        {"forbidden_transcript_patterns": [r"I see the issue", r"prefix match"]},
        {"transcript_path": str(transcript_path)},
    )

    assert scanned is True
    assert hits == []


def test_completed_task_recovery_mode_accepts_max_turns_after_successful_completion(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)

    recovery = runner.completed_task_recovery_mode(
        exit_code=1,
        payload_subtype="error_max_turns",
        fatal_error="",
        completed=True,
        verification_required=True,
        tests_run=True,
        tests_passed=True,
        verification_summary_present=True,
        review_required=True,
        review_present=True,
        risks_present=True,
        docs_required=True,
        docs_updated=True,
        category="bugfix",
        non_doc_changed_files=["calculator.py"],
        doc_pattern_hits=[],
    )

    assert recovery == "max_turns"


def test_completed_task_recovery_mode_rejects_max_turns_without_required_review(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)

    recovery = runner.completed_task_recovery_mode(
        exit_code=1,
        payload_subtype="error_max_turns",
        fatal_error="",
        completed=True,
        verification_required=True,
        tests_run=True,
        tests_passed=True,
        verification_summary_present=True,
        review_required=True,
        review_present=False,
        risks_present=True,
        docs_required=False,
        docs_updated=False,
        category="bugfix",
        non_doc_changed_files=["calculator.py"],
        doc_pattern_hits=[],
    )

    assert recovery == "none"


def test_completed_task_recovery_mode_accepts_max_turns_with_zero_exit_when_contract_is_satisfied(
    tmp_path, monkeypatch
):
    runner = load_runner_module(tmp_path, monkeypatch)

    recovery = runner.completed_task_recovery_mode(
        exit_code=0,
        payload_subtype="error_max_turns",
        fatal_error="Claude result text is missing or empty.",
        completed=True,
        verification_required=True,
        tests_run=True,
        tests_passed=True,
        verification_summary_present=True,
        review_required=True,
        review_present=True,
        risks_present=True,
        docs_required=True,
        docs_updated=True,
        category="bugfix",
        non_doc_changed_files=["calculator.py"],
        doc_pattern_hits=[],
    )

    assert recovery == "max_turns"


def test_extract_used_agent_aliases_normalizes_hook_labels_and_recorded_handoffs(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    debug_log = """
2026-04-03T12:40:16.646Z [DEBUG] "Hook SubagentStart:Code Reviewer (SubagentStart) success:
{
  "hookSpecificOutput": {
    "additionalContext": "Recorded subagent handoff: @cr."
  }
}
"
2026-04-03T12:42:29.426Z [DEBUG] "Hook SubagentStart:Explore (SubagentStart) success:
{
  "hookSpecificOutput": {
    "additionalContext": "Recorded subagent handoff: @explore."
  }
}
"
2026-04-03T12:42:33.723Z [DEBUG] "Hook SubagentStart:Architect (SubagentStart) success:
{
  "hookSpecificOutput": {
    "additionalContext": "Recorded subagent handoff: @a."
  }
}
"
"""

    assert runner.extract_used_agent_aliases(debug_log) == ["cr", "e", "a"]


def test_extract_used_agent_aliases_accepts_recorded_handoff_without_hook_label(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    debug_log = """
2026-04-03T12:40:16.646Z [DEBUG] "Recorded subagent handoff: @cr. Parallel same-role handoffs are allowed."
"""

    assert runner.extract_used_agent_aliases(debug_log) == ["cr"]


def test_extract_used_agent_aliases_falls_back_to_transcript_roles(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    transcript_path = tmp_path / "transcript.jsonl"
    write_transcript(
        transcript_path,
        [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Explorer(Map reporter.py and README.md first)"}],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Code Reviewer(Review mapped files after Explorer)"}],
                },
            },
        ],
    )
    payload = {"transcript_path": str(transcript_path)}

    assert runner.extract_used_agent_aliases("", payload) == ["cr", "e"]


def test_extract_used_agent_aliases_falls_back_to_result_text_handoff_bullets(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    result_text = """
All required agent handoffs are now complete:
- **@m** (Manager) - coordinated workflow
- **@e** (Explorer) - mapped reporter.py and README.md
- **@cr** (Code Reviewer) - reviewed the mapped files
"""

    assert runner.extract_used_agent_aliases("", result_text=result_text) == ["m", "e", "cr"]


def test_required_used_agent_misses_report_missing_roles(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    task = {
        "required_used_agents": ["m", "cr"],
        "required_used_agent_groups": [["e", "a", "t"]],
    }

    assert runner.required_used_agent_misses(task, ["m", "e"]) == ["cr"]
    assert runner.required_used_agent_group_misses(task, ["m", "cr"]) == [["e", "a", "t"]]


def test_required_used_agent_groups_accept_any_alias_in_group(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    task = {"required_used_agent_groups": [["e", "a", "t"], ["doc", "hk"]]}

    assert runner.required_used_agent_group_misses(task, ["a", "doc"]) == []


def test_try_budget_retry_returns_effective_retry_debug_log_path(tmp_path, monkeypatch):
    runner = load_runner_module(tmp_path, monkeypatch)
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runner, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(runner, "CLAUDE_CODE_MAX_OUTPUT_TOKENS", "1024")

    def fake_run_claude(prompt, debug_log_path, stderr_log_path, max_turns=runner.MAX_TURNS, max_output_tokens=None):
        debug_log_path.write_text(
            '2026-04-03T12:40:16.646Z [DEBUG] "Recorded subagent handoff: @m. Retry success."\n',
            encoding="utf-8",
        )
        stderr_log_path.write_text("", encoding="utf-8")
        return 0, json.dumps({"result": "Verification status: passed - retry ok."}), ""

    monkeypatch.setattr(runner, "run_claude", fake_run_claude)

    (
        _exit_code,
        _raw_stdout,
        _raw_stderr,
        _payload,
        _result_text,
        _fatal_error,
        retry_summaries,
        retry_source,
        effective_debug_log_path,
        effective_stderr_log_path,
    ) = runner.try_budget_retry(
        prompt="retry me",
        exit_code=1,
        raw_stdout="",
        raw_stderr="",
        payload=None,
        result_text="requested up to 1024 tokens, but can only afford 768",
        fatal_error="provider affordability error",
        debug_log_path=output_dir / "claude-debug.log",
        stderr_log_path=output_dir / "claude-stderr.log",
    )

    assert retry_source == "output-budget"
    assert len(retry_summaries) == 1
    assert effective_debug_log_path.name == "claude-debug-budget-retry-1.log"
    assert effective_stderr_log_path.name == "claude-stderr-budget-retry-1.log"


def test_render_benchmark_summary_outputs_task_status_table(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "render-benchmark-summary.sh"
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "totals": {
                    "configured_tasks": 3,
                    "executed_tasks": 2,
                    "recovered_tasks": 1,
                    "summary_repaired": 0,
                },
                "rates": {
                    "execution_coverage_rate": 2 / 3,
                    "task_pass_rate": 0.5,
                    "clean_pass_rate": 0.5,
                },
                "median_runtime_seconds": 12.34,
                "tasks": [
                    {
                        "task_id": "bugfix-zero-division-lite",
                        "status": "passed",
                        "runtime_seconds": 10.5,
                        "verification_required": True,
                        "tests_run": True,
                        "tests_passed": True,
                        "review_required": True,
                        "review_present": True,
                        "docs_required": True,
                        "docs_updated": True,
                        "changed_files": ["calculator.py", "README.md"],
                        "recovered_nonzero_exit": False,
                        "timeout_recovered": False,
                        "max_turns_recovered": False,
                        "summary_repaired_by": "none",
                        "failures": [],
                    },
                    {
                        "task_id": "feature-manager-no-agent-choice",
                        "status": "failed",
                        "runtime_seconds": 14.18,
                        "verification_required": True,
                        "tests_run": True,
                        "tests_passed": False,
                        "review_required": True,
                        "review_present": True,
                        "docs_required": True,
                        "docs_updated": True,
                        "changed_files": ["calculator.py", "test_calculator.py", "README.md"],
                        "recovered_nonzero_exit": True,
                        "timeout_recovered": True,
                        "max_turns_recovered": False,
                        "summary_repaired_by": "retry",
                        "failures": ["verification_failed", "required_used_agents_missing"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        ["bash", str(script_path), str(summary_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    output = completed.stdout
    assert "### Overview" in output
    assert "| Metric | Value |" in output
    assert "### Executed Tasks" in output
    assert "| Task | Status | Runtime (s) | Verification | Review | Docs | Changed Files | Recovery | Summary Repair | Failures |" in output
    assert "| `bugfix-zero-division-lite` | `passed` | 10.5 | `passed` | `done` | `updated` | calculator.py, README.md | `none` | `none` | — |" in output
    assert "| `feature-manager-no-agent-choice` | `failed` | 14.18 | `failed` | `done` | `updated` | calculator.py, test_calculator.py, README.md | `timeout` | `retry` | verification_failed, required_used_agents_missing |" in output
    assert "> Note: only 2 of 3 selected tasks executed." in output
