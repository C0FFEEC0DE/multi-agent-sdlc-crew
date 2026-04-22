import json
import os
import subprocess
from pathlib import Path


def write_task(path: Path, task_id: str, fixture: str, category: str) -> None:
    path.write_text(
        json.dumps(
            {
                "id": task_id,
                "category": category,
                "fixture": fixture,
                "review_required": False,
                "docs_required": False,
                "verification_required": False,
            }
        ),
        encoding="utf-8",
    )


def test_run_benchmark_records_unexecuted_tasks_after_fail_fast(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "run-benchmark.sh"
    runner = tmp_path / "fake-runner.sh"
    task_list = tmp_path / "tasks.txt"
    output_dir = tmp_path / "bench-output"
    profile_dir = tmp_path / "claude-profile"
    first_task = tmp_path / "first.json"
    second_task = tmp_path / "second.json"

    profile_dir.mkdir()
    write_task(first_task, "fail-fast-first", "python-math", "bugfix")
    write_task(second_task, "unexecuted-second", "text-report", "docs")
    task_list.write_text(f"{first_task}\n{second_task}\n", encoding="utf-8")

    runner.write_text(
        """#!/bin/bash
set -euo pipefail
mkdir -p "$BENCH_OUTPUT_DIR"
status="passed"
if [ "$BENCH_TASK_ID" = "fail-fast-first" ]; then
  status="failed"
fi
jq -n \
  --arg task_id "$BENCH_TASK_ID" \
  --arg task_path "${BENCH_TASK_FILE#"$BENCH_REPO_ROOT"/}" \
  --arg status "$status" \
  '{
    task_id: $task_id,
    task_path: $task_path,
    status: $status,
    completed: true,
    verification_required: false,
    tests_run: false,
    tests_passed: false,
    review_required: false,
    review_present: false,
    docs_required: false,
    docs_updated: false,
    policy_violations: 0,
    tool_failures: 0,
    runtime_seconds: 1,
    notes: "synthetic result"
  }' > "$BENCH_OUTPUT_DIR/result.json"
""",
        encoding="utf-8",
    )
    runner.chmod(0o755)

    env = os.environ.copy()
    env["BENCH_RUNNER_CMD"] = str(runner)
    env["BENCH_FAIL_FAST"] = "1"
    env["BENCH_CLAUDE_PROFILE_DIR"] = str(profile_dir)

    result = subprocess.run(
        [
            "bash",
            str(script),
            "--output-dir",
            str(output_dir),
            "--mode",
            "command",
            "--task-list-file",
            str(task_list),
            "--task-label",
            "task-list:test",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary["selected_task_ids"] == ["fail-fast-first", "unexecuted-second"]
    assert summary["executed_task_ids"] == ["fail-fast-first"]
    assert summary["unexecuted_task_ids"] == ["unexecuted-second"]
    assert summary["unresolved_task_ids"] == ["fail-fast-first", "unexecuted-second"]
    assert summary["totals"]["configured_tasks"] == 2
    assert summary["totals"]["selected_tasks"] == 2
    assert summary["totals"]["executed_tasks"] == 1
    assert summary["totals"]["unexecuted_tasks"] == 1
    assert summary["totals"]["unresolved_tasks"] == 2
