#!/usr/bin/env python3

import argparse
import json
import pathlib
from datetime import datetime, UTC


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("summary_files", nargs="+")
    return parser.parse_args()


def median(values: list[float]) -> float:
    if not values:
        return 0
    sorted_values = sorted(values)
    midpoint = len(sorted_values) // 2
    if len(sorted_values) % 2 == 1:
        return sorted_values[midpoint]
    return (sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2


def rate(num: int, den: int) -> float:
    if den == 0:
        return 0
    return num / den


def count_preferred(primary: list[str], secondary: list[str], fallback: int = 0) -> int:
    if primary:
        return len(primary)
    if secondary:
        return len(secondary)
    return fallback


def normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                normalized.append(cleaned)
    return normalized


def merge_string_lists(summary_payloads: list[dict], field_name: str) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for payload in summary_payloads:
        for value in normalize_string_list(payload.get(field_name)):
            if value in seen:
                continue
            seen.add(value)
            merged.append(value)
    return merged


def task_ids(tasks: list[dict]) -> list[str]:
    return [str(task["task_id"]) for task in tasks if isinstance(task.get("task_id"), str)]


def task_paths(tasks: list[dict]) -> list[str]:
    paths: list[str] = []
    for task in tasks:
        path = task.get("task_path") or task.get("task_file") or task.get("path")
        if isinstance(path, str) and path.strip():
            paths.append(path.strip())
    return paths


def merge_unique(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in [*primary, *secondary]:
        if value in seen:
            continue
        seen.add(value)
        merged.append(value)
    return merged


def merge_summaries(summary_payloads: list[dict]) -> dict:
    if not summary_payloads:
        raise ValueError("at least one summary is required")

    first = summary_payloads[0]
    tasks = []
    configured_tasks = 0
    executed_tasks = 0
    for payload in summary_payloads:
        configured_tasks += int(payload["totals"]["configured_tasks"])
        executed_tasks += int(payload["totals"]["executed_tasks"])
        tasks.extend(payload.get("tasks", []))

    selected_task_ids = merge_string_lists(summary_payloads, "selected_task_ids")
    selected_task_paths = merge_string_lists(summary_payloads, "selected_task_paths")
    executed_task_ids = merge_string_lists(summary_payloads, "executed_task_ids")
    executed_task_paths = merge_string_lists(summary_payloads, "executed_task_paths")
    unexecuted_task_ids = merge_string_lists(summary_payloads, "unexecuted_task_ids")
    unexecuted_task_paths = merge_string_lists(summary_payloads, "unexecuted_task_paths")
    unresolved_task_ids = merge_string_lists(summary_payloads, "unresolved_task_ids")
    unresolved_task_paths = merge_string_lists(summary_payloads, "unresolved_task_paths")

    total = len(tasks)
    failed_tasks = [task for task in tasks if task.get("status") != "passed"]
    passed = len([task for task in tasks if task["status"] == "passed"])
    clean_passed = len(
        [
            task
            for task in tasks
            if task["status"] == "passed"
            and task.get("recovered_nonzero_exit") is not True
            and (task.get("summary_repaired_by") or "none") == "none"
        ]
    )
    completed = len([task for task in tasks if task.get("completed") is True])
    verification_required = len([task for task in tasks if task.get("verification_required") is True])
    tests_run = len([task for task in tasks if task.get("tests_run") is True])
    tests_passed = len([task for task in tasks if task.get("tests_passed") is True])
    review_required = len([task for task in tasks if task.get("review_required") is True])
    review_present = len([task for task in tasks if task.get("review_present") is True])
    docs_required = len([task for task in tasks if task.get("docs_required") is True])
    docs_updated = len([task for task in tasks if task.get("docs_updated") is True])
    recovered_tasks = len([task for task in tasks if task.get("recovered_nonzero_exit") is True])
    timeout_recovered = len([task for task in tasks if task.get("timeout_recovered") is True])
    max_turns_recovered = len([task for task in tasks if task.get("max_turns_recovered") is True])
    summary_repaired = len([task for task in tasks if (task.get("summary_repaired_by") or "none") != "none"])
    policy_violations = sum(int(task.get("policy_violations", 0)) for task in tasks)
    tool_failures = sum(int(task.get("tool_failures", 0)) for task in tasks)
    selected_total = count_preferred(selected_task_ids, selected_task_paths, configured_tasks)
    unexecuted_total = count_preferred(
        unexecuted_task_ids,
        unexecuted_task_paths,
        max(selected_total - executed_tasks, 0),
    )
    unresolved_total = (
        count_preferred(
            unresolved_task_ids,
            unresolved_task_paths,
            len([task for task in tasks if task.get("status") != "passed"]) + unexecuted_total,
        )
    )

    if not executed_task_ids:
        executed_task_ids = task_ids(tasks)
    if not executed_task_paths:
        executed_task_paths = task_paths(tasks)
    if not unresolved_task_ids:
        unresolved_task_ids = merge_unique(task_ids(failed_tasks), unexecuted_task_ids)
    if not unresolved_task_paths:
        unresolved_task_paths = merge_unique(task_paths(failed_tasks), unexecuted_task_paths)

    return {
        "schema_version": first["schema_version"],
        "mode": first["mode"],
        "runner": first["runner"],
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_ref": first["source_ref"],
        "source_sha": first["source_sha"],
        "task_glob": first["task_glob"],
        "selected_task_ids": selected_task_ids,
        "selected_task_paths": selected_task_paths,
        "executed_task_ids": executed_task_ids,
        "executed_task_paths": executed_task_paths,
        "unexecuted_task_ids": unexecuted_task_ids,
        "unexecuted_task_paths": unexecuted_task_paths,
        "unresolved_task_ids": unresolved_task_ids,
        "unresolved_task_paths": unresolved_task_paths,
        "totals": {
            "configured_tasks": configured_tasks,
            "selected_tasks": selected_total,
            "executed_tasks": executed_tasks,
            "unexecuted_tasks": unexecuted_total,
            "unresolved_tasks": unresolved_total,
            "tasks": executed_tasks,
            "passed": passed,
            "clean_passed": clean_passed,
            "completed": completed,
            "verification_required": verification_required,
            "tests_run": tests_run,
            "tests_passed": tests_passed,
            "review_required": review_required,
            "review_present": review_present,
            "docs_required": docs_required,
            "docs_updated": docs_updated,
            "recovered_tasks": recovered_tasks,
            "timeout_recovered": timeout_recovered,
            "max_turns_recovered": max_turns_recovered,
            "summary_repaired": summary_repaired,
            "policy_violations": policy_violations,
            "tool_failures": tool_failures,
        },
        "rates": {
            "task_pass_rate": rate(passed, total),
            "clean_pass_rate": rate(clean_passed, total),
            "completion_rate": rate(completed, total),
            "verification_rate": rate(len([task for task in tasks if (task.get("verification_required") is False) or (task.get("tests_run") is True)]), total),
            "verification_pass_rate": rate(len([task for task in tasks if (task.get("verification_required") is False) or (task.get("tests_passed") is True)]), total),
            "review_compliance_rate": rate(len([task for task in tasks if (task.get("review_required") is False) or (task.get("review_present") is True)]), total),
            "docs_compliance_rate": rate(len([task for task in tasks if (task.get("docs_required") is False) or (task.get("docs_updated") is True)]), total),
            "recovered_task_rate": rate(recovered_tasks, total),
            "summary_repair_rate": rate(summary_repaired, total),
            "execution_coverage_rate": rate(executed_tasks, configured_tasks),
            "unexecuted_rate": rate(unexecuted_total, selected_total),
            "unresolved_rate": rate(unresolved_total, selected_total),
        },
        "median_runtime_seconds": median([float(task["runtime_seconds"]) for task in tasks]),
        "tasks": tasks,
    }


def main() -> None:
    args = parse_args()
    payloads = [
        json.loads(pathlib.Path(summary_file).read_text(encoding="utf-8"))
        for summary_file in args.summary_files
    ]
    merged = merge_summaries(payloads)
    pathlib.Path(args.output).write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
