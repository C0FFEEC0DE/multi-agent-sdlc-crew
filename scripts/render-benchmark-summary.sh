#!/bin/bash

set -euo pipefail

[ $# -eq 1 ] || {
    echo "Usage: $0 SUMMARY_JSON" >&2
    exit 1
}

summary_file="$1"

jq -r '
    def pct($value): (($value * 1000 | round) / 10 | tostring) + "%";
    def sanitize($value):
        ($value // "" | tostring)
        | gsub("\r?\n"; " / ")
        | gsub("\\|"; "\\\\|");
    def truncate_cell($value; $limit):
        (sanitize($value)) as $clean
        | if ($clean | length) > $limit then $clean[0:($limit - 3)] + "..." else $clean end;
    def list_or_dash($items; $limit):
        if ($items | type) == "array" and ($items | length) > 0 then
            truncate_cell(($items | join(", ")); $limit)
        else
            "—"
        end;
    def task_rows($ids; $paths):
        ($ids // []) as $ids
        | ($paths // []) as $paths
        | ([($ids | length), ($paths | length)] | max) as $count
        | if $count == 0 then []
          else [range(0; $count) | {id: ($ids[.] // ""), path: ($paths[.] // "")}]
          end;
    def render_task_section($title; $ids; $paths):
        task_rows($ids; $paths) as $rows
        | if ($rows | length) == 0 then empty
          else
            "",
            "### \($title)",
            "",
            "| Task ID | Task Path |",
            "| --- | --- |",
            ($rows[] | "| `\(.id)` | `\(.path)` |")
          end;
    def verification_status:
        if .verification_required == true then
            if .tests_run == true then
                if .tests_passed == true then "passed" else "failed" end
            else
                "not-run"
            end
        else
            "not-required"
        end;
    def review_status:
        if .review_required == true then
            if .review_present == true then "done" else "missing" end
        else
            "not-required"
        end;
    def docs_status:
        if .docs_required == true then
            if .docs_updated == true then "updated" else "missing" end
        else
            "not-required"
        end;
    def recovery_status:
        if .timeout_recovered == true then "timeout"
        elif .max_turns_recovered == true then "max-turns"
        elif .recovered_nonzero_exit == true then "recovered"
        else "none"
        end;
    "### Overview",
    "",
    "| Metric | Value |",
    "| --- | ---: |",
    "| Configured tasks | \(.totals.configured_tasks) |",
    "| Selected tasks | \(.totals.selected_tasks // .totals.configured_tasks) |",
    "| Executed tasks | \(.totals.executed_tasks) |",
    "| Unexecuted tasks | \(.totals.unexecuted_tasks // 0) |",
    "| Unresolved tasks | \(.totals.unresolved_tasks // 0) |",
    "| Execution coverage | \(pct(.rates.execution_coverage_rate)) |",
    "| Pass rate | \(pct(.rates.task_pass_rate)) |",
    "| Clean pass rate | \(pct(.rates.clean_pass_rate)) |",
    "| Recovered tasks | \(.totals.recovered_tasks) |",
    "| Summary repaired tasks | \(.totals.summary_repaired) |",
    "| Median runtime (s) | \(.median_runtime_seconds) |",
    (
        if (.totals.unexecuted_tasks // 0) > 0 then
            "",
            "> Note: \(.totals.unexecuted_tasks) selected task(s) did not execute. These are the primary resume candidates after a fail-fast stop."
        elif .totals.executed_tasks < .totals.configured_tasks then
            "",
            "> Note: only \(.totals.executed_tasks) of \(.totals.configured_tasks) selected tasks executed."
        else empty end
    ),
    "",
    "### Executed Tasks",
    "",
    "| Task | Status | Runtime (s) | Verification | Review | Docs | Changed Files | Recovery | Summary Repair | Failures |",
    "| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    (
        if (.tasks | length) == 0 then
            "| — | — | — | — | — | — | — | — | — | No executed tasks |"
        else
            (.tasks[] | "| `\(.task_id)` | `\(.status)` | \(.runtime_seconds) | `\(verification_status)` | `\(review_status)` | `\(docs_status)` | \(list_or_dash(.changed_files; 72)) | `\(recovery_status)` | `\((.summary_repaired_by // "none"))` | \(list_or_dash(.failures; 96)) |")
        end
    ),
    render_task_section("Unexecuted Tasks"; .unexecuted_task_ids; .unexecuted_task_paths),
    render_task_section("Unresolved Tasks"; .unresolved_task_ids; .unresolved_task_paths)
' "$summary_file"
