import json
import subprocess
from pathlib import Path


def test_build_benchmark_matrix_splits_tasks_across_three_shards(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "build-benchmark-matrix.py"
    task_list = tmp_path / "tasks.txt"
    task_list.write_text(
        "\n".join(
            [
                "bench/tasks/subagents/smoke/subagent-architect-rollout-lite.json",
                "bench/tasks/subagents/smoke/subagent-bugbuster-zero-division-lite.json",
                "bench/tasks/subagents/smoke/subagent-code-reviewer-note-lite.json",
                "bench/tasks/subagents/smoke/subagent-debugger-zero-division-lite.json",
                "bench/tasks/subagents/smoke/subagent-docwriter-quickstart-lite.json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        ["python3", str(script_path), "--task-list-file", str(task_list), "--max-shards", "3"],
        check=True,
        capture_output=True,
        text=True,
    )

    matrix = json.loads(completed.stdout)
    assert len(matrix) == 3
    assert matrix[0]["shard_index"] == 1
    assert matrix[0]["task_count"] == 2
    assert matrix[1]["shard_index"] == 2
    assert matrix[1]["task_count"] == 2
    assert matrix[2]["shard_index"] == 3
    assert matrix[2]["task_count"] == 1


def test_merge_benchmark_summaries_recomputes_totals_and_rates(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "merge-benchmark-summaries.py"
    shard_one = tmp_path / "shard-one.json"
    shard_two = tmp_path / "shard-two.json"
    output = tmp_path / "merged.json"

    shard_one.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "mode": "command",
                "runner": "runner",
                "generated_at": "2026-01-01T00:00:00Z",
                "source_ref": "refs/pull/8/merge",
                "source_sha": "abc123",
                "task_glob": "bench/tasks/subagents/smoke/*.json",
                "totals": {"configured_tasks": 2, "executed_tasks": 2},
                "tasks": [
                    {
                        "task_id": "task-a",
                        "status": "passed",
                        "completed": True,
                        "verification_required": False,
                        "tests_run": False,
                        "tests_passed": False,
                        "review_required": False,
                        "review_present": True,
                        "docs_required": True,
                        "docs_updated": True,
                        "policy_violations": 0,
                        "tool_failures": 0,
                        "runtime_seconds": 10,
                        "recovered_nonzero_exit": False,
                        "timeout_recovered": False,
                        "max_turns_recovered": False,
                        "summary_repaired_by": "none",
                    },
                    {
                        "task_id": "task-b",
                        "status": "passed",
                        "completed": True,
                        "verification_required": True,
                        "tests_run": True,
                        "tests_passed": True,
                        "review_required": True,
                        "review_present": True,
                        "docs_required": True,
                        "docs_updated": True,
                        "policy_violations": 0,
                        "tool_failures": 0,
                        "runtime_seconds": 20,
                        "recovered_nonzero_exit": False,
                        "timeout_recovered": False,
                        "max_turns_recovered": False,
                        "summary_repaired_by": "none",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    shard_two.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "mode": "command",
                "runner": "runner",
                "generated_at": "2026-01-01T00:00:00Z",
                "source_ref": "refs/pull/8/merge",
                "source_sha": "abc123",
                "task_glob": "bench/tasks/subagents/smoke/*.json",
                "totals": {"configured_tasks": 1, "executed_tasks": 1},
                "tasks": [
                    {
                        "task_id": "task-c",
                        "status": "failed",
                        "completed": True,
                        "verification_required": True,
                        "tests_run": True,
                        "tests_passed": False,
                        "review_required": True,
                        "review_present": True,
                        "docs_required": True,
                        "docs_updated": True,
                        "policy_violations": 0,
                        "tool_failures": 1,
                        "runtime_seconds": 30,
                        "recovered_nonzero_exit": True,
                        "timeout_recovered": True,
                        "max_turns_recovered": False,
                        "summary_repaired_by": "synthetic-footer",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        ["python3", str(script_path), "--output", str(output), str(shard_one), str(shard_two)],
        check=True,
        capture_output=True,
        text=True,
    )

    merged = json.loads(output.read_text(encoding="utf-8"))
    assert merged["totals"]["configured_tasks"] == 3
    assert merged["totals"]["executed_tasks"] == 3
    assert merged["totals"]["passed"] == 2
    assert merged["totals"]["recovered_tasks"] == 1
    assert merged["totals"]["summary_repaired"] == 1
    assert merged["totals"]["tool_failures"] == 1
    assert merged["rates"]["execution_coverage_rate"] == 1
    assert merged["rates"]["task_pass_rate"] == 2 / 3
    assert merged["median_runtime_seconds"] == 20